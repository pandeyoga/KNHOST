"""Banding mesin komisi — bukti anti-tujuan 1 komisi per artikel ("komisi PT yang tidak disentuh tidak berubah angka").

Rancangan `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md` §3 (anti-tujuan 1). Skrip ini menjalankan
`services.sales_force_service.compute_commission` dari SATU pohon kode backend (lama atau baru) atas basis data yang
sedang dikonfigurasi (`MONGO_URL` + `DB_NAME`, atau `backend/.env` pohon itu), untuk setiap PT × sales daftar PT
(`incentive_targets.sales_roster`) × bulan dalam N bulan terakhir (ditambah triwulan dan tahun yang memuat bulan-bulan
itu), lalu menulis satu baris JSON per hitungan:
`{entity_id, sales_id, period, total_incentive, projection_full, strategy}` (galat hitung → `{…, galat}`).

HANYA MEMBACA: mesin komisi tidak menulis ke basis data selama pengali capaian mati (bawaan; bila menyala, pengumpul
Capaian menyegarkan fakta insentif). Skrip tidak menulis apa pun ke basis data.

Pemakaian (dari akar repo, lingkungan Python backend; `MONGO_URL`/`DB_NAME` terisi):

  # 1) kode LAMA (mis. worktree sementara di d7b367b) — SEBELUM kode baru pernah menyala di basis data itu
  python scripts/komisi/banding_mesin_komisi.py hitung --backend /tmp/wt_lama/backend --keluaran lama.jsonl --akhir 2026-11

  # 2) kode BARU sesudah aplikasi menyala sekali (isi awal potret pesanan selesai) — daftar hitungan sama dengan (1)
  python scripts/komisi/banding_mesin_komisi.py hitung --backend backend --keluaran baru.jsonl --daftar lama.jsonl

  # 3) banding: keluar 0 bila setiap baris sama persis (total_incentive & projection_full), 1 bila ada beda/hilang
  python scripts/komisi/banding_mesin_komisi.py banding lama.jsonl baru.jsonl

Pilihan `hitung`: `--bulan N` (bawaan 12) · `--akhir YYYY-MM` (bawaan bulan ini, WIB) · `--pt ent_a,ent_b` (bawaan semua
PT) · `--tanpa-triwulan` · `--daftar berkas.jsonl` (pakai pasangan PT·sales·periode dari keluaran sebelumnya — daftar
sales tidak dihitung ulang, jadi fakta yang berubah di antara dua jalan tidak mengubah apa yang dibandingkan).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

WIB = timezone(timedelta(hours=7))


def _bulan_mundur(akhir: str, n: int) -> List[str]:
    y, m = int(akhir[:4]), int(akhir[5:7])
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


async def _hitung(args: argparse.Namespace) -> int:
    backend = os.path.abspath(args.backend)
    keluaran = os.path.abspath(args.keluaran)
    daftar = os.path.abspath(args.daftar) if args.daftar else ""
    sys.path.insert(0, backend)
    os.chdir(backend)                                    # modul backend membaca berkas relatif ke akarnya
    from db import db                                    # noqa: E402 — sesudah sys.path diarahkan ke pohon pilihan
    from services import sales_force_service as sf       # noqa: E402
    from services.incentive_targets import sales_roster  # noqa: E402

    pasangan: List[Tuple[str, str, str]] = []
    if daftar:
        with open(daftar, encoding="utf-8") as f:
            for baris in f:
                if baris.strip():
                    r = json.loads(baris)
                    pasangan.append((r["entity_id"], r["sales_id"], r["period"]))
    else:
        akhir = args.akhir or datetime.now(WIB).strftime("%Y-%m")
        bulan = _bulan_mundur(akhir, args.bulan)
        pts = [p for p in (args.pt or "").split(",") if p] or sorted(
            {e["id"] async for e in db.business_entities.find({}, {"_id": 0, "id": 1}) if e.get("id") not in ("", "all")})
        for ent in pts:
            for b in bulan:
                for u in await sales_roster(ent, "month", b):
                    pasangan.append((ent, u["id"], b))
        if not args.tanpa_triwulan:   # triwulan & tahun yang memuat bulan itu (jalur jumlah per bulan / proyeksi)
            for ent, sid, b in list(pasangan):
                pasangan += [(ent, sid, f"{b[:4]}-Q{(int(b[5:7]) - 1) // 3 + 1}"), (ent, sid, b[:4])]
    mulai = time.time()
    n_galat = 0
    with open(keluaran, "w", encoding="utf-8") as out:
        for ent, sid, per in sorted(set(pasangan)):
            r: Dict[str, Any] = {"entity_id": ent, "sales_id": sid, "period": per}
            try:
                c = await sf.compute_commission(sid, per, entity_id=ent)
                r.update(total_incentive=c.get("total_incentive"), projection_full=c.get("projection_full"),
                         strategy=c.get("strategy"))
            except Exception as exc:  # noqa: BLE001 — dicatat per baris, banding menandainya
                n_galat += 1
                r["galat"] = f"{type(exc).__name__}: {exc}"
            out.write(json.dumps(r, sort_keys=True) + "\n")
    print(f"mesin: {sf.__file__}")
    print(f"{len(set(pasangan))} hitungan ({n_galat} galat) dari {backend} → {keluaran} "
          f"dalam {time.time() - mulai:.1f} dtk")
    return 0


def _muat(path: str) -> Dict[Tuple[str, str, str], Dict[str, Any]]:
    out = {}
    with open(path, encoding="utf-8") as f:
        for baris in f:
            if baris.strip():
                r = json.loads(baris)
                out[(r["entity_id"], r["sales_id"], r["period"])] = r
    return out


def _banding(args: argparse.Namespace) -> int:
    lama, baru = _muat(args.lama), _muat(args.baru)
    beda, hilang = [], sorted(set(lama) ^ set(baru))
    bukan_nol = 0
    for k in sorted(set(lama) & set(baru)):
        a, b = lama[k], baru[k]
        if any(float(a.get(f) or 0) != 0 for f in ("total_incentive", "projection_full")):
            bukan_nol += 1
        if "galat" in a or "galat" in b or any(a.get(f) != b.get(f) for f in ("total_incentive", "projection_full")):
            beda.append((k, a, b))
    per_pt: Dict[str, List[int]] = {}
    for k in set(lama) & set(baru):
        s = per_pt.setdefault(k[0], [0, 0, 0])
        s[0] += 1
        s[1] += 1 if any(float(lama[k].get(f) or 0) for f in ("total_incentive", "projection_full")) else 0
        s[2] += 1 if any(x[0] == k for x in beda) else 0
    print(f"Baris dibandingkan: {len(set(lama) & set(baru))} (bukan nol: {bukan_nol}) · beda: {len(beda)} · "
          f"hanya di satu sisi: {len(hilang)}")
    print("PT | baris | bukan nol | beda")
    for pt in sorted(per_pt):
        print(f"{pt} | {per_pt[pt][0]} | {per_pt[pt][1]} | {per_pt[pt][2]}")
    for k, a, b in beda[:50]:
        print(f"BEDA {k}: lama total={a.get('total_incentive')} proyeksi={a.get('projection_full')} {a.get('galat', '')}"
              f" · baru total={b.get('total_incentive')} proyeksi={b.get('projection_full')} {b.get('galat', '')}")
    for k in hilang[:50]:
        print(f"HANYA {'LAMA' if k in lama else 'BARU'} {k}")
    return 0 if not beda and not hilang else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Banding mesin komisi lama vs baru (anti-tujuan 1 komisi per artikel).")
    sub = ap.add_subparsers(dest="perintah", required=True)
    h = sub.add_parser("hitung", help="hitung komisi semua PT × sales × bulan dengan satu pohon kode backend")
    h.add_argument("--backend", required=True, help="folder backend pohon kode yang dipakai (mis. worktree lama)")
    h.add_argument("--keluaran", required=True, help="berkas JSON lines hasil")
    h.add_argument("--bulan", type=int, default=12, help="jumlah bulan ke belakang (bawaan 12)")
    h.add_argument("--akhir", default="", help="bulan terakhir YYYY-MM (bawaan bulan ini WIB)")
    h.add_argument("--pt", default="", help="daftar PT dipisah koma (bawaan semua PT)")
    h.add_argument("--daftar", default="", help="pakai pasangan PT·sales·bulan dari keluaran sebelumnya")
    h.add_argument("--tanpa-triwulan", action="store_true", help="hanya bulan (tanpa triwulan & tahun yang memuatnya)")
    b = sub.add_parser("banding", help="bandingkan dua keluaran `hitung`")
    b.add_argument("lama")
    b.add_argument("baru")
    args = ap.parse_args()
    if args.perintah == "hitung":
        return asyncio.run(_hitung(args))
    return _banding(args)


if __name__ == "__main__":
    sys.exit(main())
