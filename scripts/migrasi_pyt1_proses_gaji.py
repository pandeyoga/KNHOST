"""PY-T1 (PY-13, D7) — proses gaji LAMA (sebelum PY-T1) diberi jenis proses dan kunci "satu reguler hidup per PT".

    python scripts/migrasi_pyt1_proses_gaji.py            # baca-saja (bawaan): cetak, tidak menulis apa pun
    python scripts/migrasi_pyt1_proses_gaji.py --apply    # isi run_type/seq/active_key proses lama

Sejak PY-T1 proses gaji punya `run_type` (`regular` · `thr` · `susulan`), `seq` (urutan per PT, periode, jenis), dan
`active_key` = "<PT>:<periode>:regular" pada proses REGULER yang tidak dibatalkan/dianulir, berindeks unik parsial
(`hr_payroll_runs.uq_active_key`, indeks wajib PK-14). Proses lama dibaca sebagai reguler oleh kode, tetapi belum
berkunci — jadi dua permintaan bersamaan untuk periode lama hanya dijaga pembacaan, bukan indeks.

Mode baca-saja mencetak: jumlah proses tanpa `run_type`, proses yang akan diberi `active_key`, PT+periode yang punya
LEBIH DARI SATU proses reguler hidup (kembar = titik henti H6: tidak diberi kunci, perlu keputusan pemilik), dan jumlah
slip tanpa `components` (TIDAK diubah: slip lama tetap dibaca dari kolomnya — membentuk komponen slip lama tidak perlu).
`--apply` menulis `run_type="regular"` + `seq` (urut `created_at`) ke proses tanpa jenis, dan `active_key` ke proses
reguler hidup yang tidak kembar. Aman diulang. Menjalankannya pada data nyata = titik henti H3 (keputusan pemilik; ambil
cadangan `hr_payroll_runs` lebih dulu). Dijalankan di dalam container backend (butuh `backend/.env`).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

MATI = ("cancelled", "void", "rejected")


async def kumpulkan(db) -> Dict[str, Any]:
    runs = await db.hr_payroll_runs.find({}, {"_id": 0, "id": 1, "number": 1, "entity_id": 1, "period": 1,
                                              "status": 1, "run_type": 1, "seq": 1, "active_key": 1,
                                              "created_at": 1}).sort([("created_at", 1), ("id", 1)]).to_list(None)
    tanpa_jenis = [r for r in runs if not r.get("run_type")]
    hidup: Dict[str, List[Dict[str, Any]]] = {}
    for r in runs:
        if (r.get("run_type") or "regular") == "regular" and r.get("status") not in MATI:
            hidup.setdefault(f"{r.get('entity_id')}:{r.get('period')}:regular", []).append(r)
    kembar = {k: v for k, v in hidup.items() if len(v) > 1}
    beri_kunci = [v[0] for k, v in hidup.items() if len(v) == 1 and v[0].get("active_key") != k]
    seq: Dict[str, int] = {}
    seq_baru = {}
    for r in runs:
        k = f"{r.get('entity_id')}:{r.get('period')}:{r.get('run_type') or 'regular'}"
        seq[k] = seq.get(k, 0) + 1
        if not r.get("run_type"):
            seq_baru[r["id"]] = seq[k]
    slip_lama = await db.hr_payslips.count_documents({"components": {"$exists": False}})
    return {"runs": runs, "tanpa_jenis": tanpa_jenis, "kembar": kembar, "beri_kunci": beri_kunci, "seq": seq_baru,
            "slip_lama": slip_lama}


async def jalankan(argv=None, db=None) -> int:
    ap = argparse.ArgumentParser(description="Proses gaji lama → jenis proses + kunci reguler hidup (PY-T1).")
    ap.add_argument("--apply", action="store_true", help="isi run_type/seq/active_key (data nyata = H3)")
    args = ap.parse_args(argv)
    if db is None:
        from db import db as _db
        db = _db
    h = await kumpulkan(db)
    for r in h["tanpa_jenis"]:
        print(f"Proses {r.get('number') or r['id']} · PT {r.get('entity_id')} · periode {r.get('period')} · "
              f"status {r.get('status')} → jenis reguler, urutan {h['seq'][r['id']]}")
    for r in h["beri_kunci"]:
        print(f"Kunci reguler hidup: {r.get('number') or r['id']} → {r.get('entity_id')}:{r.get('period')}:regular")
    for k, v in h["kembar"].items():
        print(f"KEMBAR (H6, tidak diberi kunci): {k} → " + ", ".join(x.get("number") or x["id"] for x in v))
    print(f"Ringkasan: {len(h['runs'])} proses · {len(h['tanpa_jenis'])} tanpa jenis · {len(h['beri_kunci'])} akan "
          f"diberi kunci · {len(h['kembar'])} PT+periode kembar · {h['slip_lama']} slip tanpa komponen (tidak diubah; "
          f"dibaca dari kolomnya)")
    if not args.apply:
        print("Mode baca-saja: tidak ada yang diubah. Pakai --apply untuk menulis (data nyata = keputusan pemilik).")
        return 0
    n_jenis = n_kunci = 0
    for r in h["tanpa_jenis"]:
        res = await db.hr_payroll_runs.update_one({"id": r["id"], "run_type": {"$in": [None, ""]}},
                                                  {"$set": {"run_type": "regular", "seq": h["seq"][r["id"]]}})
        n_jenis += res.modified_count
    for r in h["beri_kunci"]:
        k = f"{r.get('entity_id')}:{r.get('period')}:regular"
        res = await db.hr_payroll_runs.update_one({"id": r["id"], "status": {"$nin": list(MATI)}},
                                                  {"$set": {"active_key": k}})
        n_kunci += res.modified_count
    print(f"Diterapkan: {n_jenis} proses diberi jenis · {n_kunci} proses diberi kunci reguler hidup"
          + (f" · {len(h['kembar'])} PT+periode kembar menunggu keputusan pemilik (H6)." if h["kembar"] else "."))
    return 1 if h["kembar"] else 0


def main(argv=None) -> int:
    return asyncio.run(jalankan(argv))


if __name__ == "__main__":
    sys.exit(main())
