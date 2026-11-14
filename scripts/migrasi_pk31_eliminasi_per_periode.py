"""PK-31 (IC-03, RP-10) — migrasi eliminasi antar-PT: entri otomatis LAMA → entri PER BULAN.

    python scripts/migrasi_pk31_eliminasi_per_periode.py           # baca-saja (bawaan): cetak, tidak menulis apa pun
    python scripts/migrasi_pk31_eliminasi_per_periode.py --apply   # hapus entri lama + tulis entri per bulan

Sebelum PK-31 tiap pasangan transaksi antar-PT punya SATU entri eliminasi otomatis (`source_g6_pair_id`, tanpa
`period_key`) yang ditimpa tiap kali angkanya berubah dan bertanggal efektif tanggal dokumen. Sejak PK-31 laporan
konsolidasi memakai entri PER BULAN dari mesin `services/interco_elimination_engine.py` (data bertanggal).

Mode baca-saja mencetak, per pasangan: entri lama, entri per bulan yang akan menggantikannya, dan selisih dampak
laba-rugi per tahun (lama → baru). Selisih itu adalah KOREKSI laba konsolidasi periode lalu (contoh: pendapatan 28 Des,
barang pindah 5 Jan → dulu 2026 −40 jt / 2027 0; kini 2026 −100 jt / 2027 +60 jt) — cetakannya wajib dilihat pemilik.

`--apply` menghapus entri otomatis tanpa `period_key` lalu menjalankan `sync_period` per pasangan (bulan yang sudah
ditutup di kedua PT disimpan beku). Aman diulang: jalan kedua tidak mengubah apa pun. Menjalankannya pada data nyata =
titik henti H3 (keputusan pemilik; ambil cadangan `intercompany_eliminations` lebih dulu). Dijalankan di dalam container
backend seperti skrip lain (butuh `backend/.env`).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

LAMA = {"source_g6_pair_id": {"$nin": [None, ""]},
        "$or": [{"period_key": {"$exists": False}}, {"period_key": {"$in": [None, ""]}}]}


def angka(x: float, tanda: bool = False) -> str:
    """Rupiah tanpa awalan, pemisah ribuan titik: -40.000.000 · +80.000.000 · 0."""
    v = round(float(x or 0))
    if v == 0:
        return "0"
    s = f"{abs(v):,.0f}".replace(",", ".")
    return ("-" if v < 0 else ("+" if tanda else "")) + s


def _laba(impact: Dict[str, Any]) -> float:
    return float(impact.get("revenue") or 0) - float(impact.get("cogs") or 0) - float(impact.get("opex") or 0)


async def kumpulkan(db) -> List[Dict[str, Any]]:
    """Per pasangan: entri lama, entri per bulan hasil mesin, dan dampak laba-rugi per tahun (baca-saja)."""
    from services import interco_elimination_engine as eng
    amap = await eng._amap()
    kode = await eng._kode_akun()
    lama: Dict[str, List[Dict[str, Any]]] = {}
    async for e in db.intercompany_eliminations.find(LAMA, {"_id": 0}):
        lama.setdefault(e["source_g6_pair_id"], []).append(e)
    sellers = {d["pair_id"]: d async for d in db.interco_transactions.find(
        {"role": "seller", "status": {"$ne": "draft"}}, {"_id": 0})}
    hasil: List[Dict[str, Any]] = []
    for pid in sorted(set(sellers) | set(lama)):
        seller = sellers.get(pid)
        f = await eng.facts(pid, seller, kode) if seller else None
        baru = []
        if f:
            for m in f["months"]:
                e = eng._entry(f, m, eng.akhir_bulan_sebelumnya(m), eng.akhir_bulan(m), amap)
                if e["lines"]:
                    baru.append(e)
        per_tahun: Dict[str, Dict[str, float]] = {}
        for jenis, rows in (("lama", lama.get(pid, [])), ("baru", baru)):
            for e in rows:
                y = (e.get("effective_date") or "")[:4] or "?"
                imp = e.get("impact") or eng._impact(e.get("lines") or [], amap)
                t = per_tahun.setdefault(y, {"lama": 0.0, "baru": 0.0})
                t[jenis] = round(t[jenis] + _laba(imp), 2)
        for t in per_tahun.values():
            t["selisih"] = round(t["baru"] - t["lama"], 2)
        hasil.append({"pair_id": pid, "number": (seller or {}).get("number", ""), "seller": seller,
                      "lama": lama.get(pid, []), "baru": baru, "per_tahun": dict(sorted(per_tahun.items())),
                      "dokumen_ada": bool(seller)})
    return hasil


def cetak(hasil: List[Dict[str, Any]]) -> None:
    for h in hasil:
        s = h["seller"] or {}
        print(f"Pasangan {h['number'] or '(dokumen tidak ada)'} ({h['pair_id']}) — "
              f"{s.get('seller_entity_name') or s.get('seller_entity_id', '')} → "
              f"{s.get('buyer_entity_name') or s.get('buyer_entity_id', '')}")
        print(f"  entri lama: {len(h['lama'])}" + "".join(
            f"\n    · {e.get('name', '')} · efektif {(e.get('effective_date') or '')[:10]}" for e in h["lama"]))
        print("  entri per bulan: " + (" · ".join(e["period_key"] for e in h["baru"]) or "(tidak ada)"))
        for y, t in h["per_tahun"].items():
            print(f"  dampak laba-rugi {y}: lama {angka(t['lama'])} · baru {angka(t['baru'])} · "
                  f"selisih {angka(t['selisih'], tanda=True)}")
        if not h["dokumen_ada"]:
            print("  PERHATIAN: dokumen antar-PT pasangan ini tidak ada — entri lamanya ikut dihapus pada --apply.")


async def terapkan(db, hasil: List[Dict[str, Any]]) -> Dict[str, int]:
    from services import interco_elimination_engine as eng
    n = {"lama_dihapus": 0, "created": 0, "updated": 0, "removed": 0}
    for h in hasil:
        ids = [e["id"] for e in h["lama"] if e.get("id")]
        if ids:
            res = await db.intercompany_eliminations.delete_many({"id": {"$in": ids}})
            n["lama_dihapus"] += int(res.deleted_count)
        if h["dokumen_ada"]:
            r = await eng.sync_period(pair_id=h["pair_id"])
            for k in ("created", "updated", "removed"):
                n[k] += int(r.get(k) or 0)
    return n


async def jalankan(argv=None, db=None) -> int:
    ap = argparse.ArgumentParser(description="Eliminasi antar-PT lama → entri per bulan (PK-31).")
    ap.add_argument("--apply", action="store_true",
                    help="hapus entri otomatis tanpa period_key dan tulis entri per bulan (data nyata = H3)")
    args = ap.parse_args(argv)
    if db is None:
        from db import db as _db
        db = _db
    hasil = await kumpulkan(db)
    cetak(hasil)
    n_lama = sum(len(h["lama"]) for h in hasil)
    print(f"Ringkasan: {len(hasil)} pasangan · {n_lama} entri lama · "
          f"{sum(len(h['baru']) for h in hasil)} entri per bulan hasil hitung")
    if not args.apply:
        print("Mode baca-saja: tidak ada yang diubah. Pakai --apply untuk menerapkan (data nyata = keputusan pemilik).")
        return 0
    n = await terapkan(db, hasil)
    if not any(n.values()):
        print("Tanpa perubahan: tidak ada entri lama, dan entri per bulan sudah sama dengan hitung ulang.")
        return 0
    print(f"Diterapkan: {n['lama_dihapus']} entri lama dihapus · {n['created']} entri per bulan ditulis · "
          f"{n['updated']} diperbarui · {n['removed']} kosong dihapus.")
    return 0


def main(argv=None) -> int:
    return asyncio.run(jalankan(argv))


if __name__ == "__main__":
    sys.exit(main())
