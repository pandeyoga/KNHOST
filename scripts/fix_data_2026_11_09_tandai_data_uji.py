#!/usr/bin/env python3
"""FIX-1 (B1 K-B1-10, UI-05; B3a §8) — TANDAI residu data uji agar tidak tampil di pilihan kerja. TANPA menghapus.

Yang ditandai `is_test: true` (+ `test_marked_at`, `test_marked_by`) — hanya pola yang JELAS uji:
  * gudang  : kode berawalan `TEST-` atau nama berawalan `TEST_` (6 gudang `TEST_WH …` di data acuan);
  * site    : nama/kode berawalan `TEST_` (3 `TEST_SITE …`);
  * PT      : nama legal berawalan `PT Uji Provisioning` (3 PT).
Akibat penanda (kode FIX-1): gudang/site/PT bertanda tidak ditawarkan di pemilih bawaan (`/warehouses`,
`/warehouse-sites`, `/entities`, pengalih PT), tidak ikut penugasan dinamis admin/manajer, dan gedung bertanda tidak
ikut tampilan "Semua lokasi" daftar tugas/stok WMS-RFID. Datanya TIDAK berubah; layar master tetap bisa melihatnya
(`include_test=true`/`scope=all`). Uji otomatis yang membuat gudang uji BARU tidak terpengaruh (penanda hanya dipasang
skrip ini, bukan dari pola nama saat jalan).

Pembalik: `--undo` mencabut penanda yang dipasang skrip ini (berdasar `test_marked_by`).
Jejak: dokumen `migrations` (`id = fix_data_2026_11_09_tandai_data_uji`).

Pakai (di dalam kontainer backend, repo = /app):
    python /app/scripts/fix_data_2026_11_09_tandai_data_uji.py --db kn_test_trial            # dry-run (bawaan)
    python /app/scripts/fix_data_2026_11_09_tandai_data_uji.py --db kn_test_trial --apply
    python /app/scripts/fix_data_2026_11_09_tandai_data_uji.py --db kn_test_trial --undo --apply
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

ALLOWED_DBS = {"kn_test_trial", "test_database"}   # DB uji bersama & salinan di stack sementara


def _args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True, help=f"nama DB — hanya {sorted(ALLOWED_DBS)}")
    ap.add_argument("--apply", action="store_true", help="terapkan (tanpa ini = dry-run)")
    ap.add_argument("--undo", action="store_true", help="cabut penanda yang dipasang skrip ini")
    return ap.parse_args()


ARGS = _args()
if ARGS.db not in ALLOWED_DBS:
    print(f"DITOLAK: skrip ini hanya untuk DB uji {sorted(ALLOWED_DBS)}; --db {ARGS.db} tidak diproses.")
    sys.exit(2)
os.environ["DB_NAME"] = ARGS.db
BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402
from dependencies import audit  # noqa: E402

FLAG = "fix_data_2026_11_09_tandai_data_uji"
ACTOR = "Sistem (penanda data uji K-B1-10)"
RULES = {
    "warehouses": {"$or": [{"code": {"$regex": r"^TEST-", "$options": "i"}}, {"name": {"$regex": r"^TEST_", "$options": "i"}}]},
    "warehouse_sites": {"$or": [{"name": {"$regex": r"^TEST_", "$options": "i"}}, {"code": {"$regex": r"^TEST_", "$options": "i"}}]},
    "business_entities": {"legal_name": {"$regex": r"^PT Uji Provisioning", "$options": "i"}},
}
LABEL = {"warehouses": "gudang", "warehouse_sites": "site", "business_entities": "PT"}


def _name(coll: str, d: dict) -> str:
    if coll == "business_entities":
        return f"{d.get('legal_name', '')} ({d.get('id')})"
    return f"{d.get('code') or ''} {d.get('name', '')} ({d.get('id')})".strip()


async def forward() -> None:
    plan = {c: [d async for d in db[c].find({**q, "is_test": {"$ne": True}}, {"_id": 0})] for c, q in RULES.items()}
    total = sum(len(v) for v in plan.values())
    print(f"{'TERAPKAN' if ARGS.apply else 'DRY-RUN'} — DB {ARGS.db}: {total} data uji akan ditandai")
    for c, rows in plan.items():
        for d in rows:
            print(f"  {LABEL[c]:<6} {_name(c, d)}")
    if not ARGS.apply or not total:
        return
    log = []
    now = now_iso()
    for c, rows in plan.items():
        for d in rows:
            res = await db[c].update_one({"id": d["id"], "is_test": {"$ne": True}},
                                         {"$set": {"is_test": True, "test_marked_at": now, "test_marked_by": FLAG}})
            if res.modified_count:
                log.append({"collection": c, "id": d["id"], "label": _name(c, d)})
                await audit(ACTOR, "test_data_marked", c, d["id"], {"is_test": True}, reason=FLAG)
    await db.migrations.update_one({"id": FLAG}, {"$set": {"id": FLAG, "applied_at": now, "by": ACTOR},
                                                  "$push": {"runs": {"at": now, "marked": log}}}, upsert=True)
    print(f"Selesai: {len(log)} data ditandai (jejak di migrations.{FLAG}).")


async def undo() -> None:
    plan = {c: [d async for d in db[c].find({"test_marked_by": FLAG}, {"_id": 0})] for c in RULES}
    total = sum(len(v) for v in plan.values())
    print(f"{'TERAPKAN' if ARGS.apply else 'DRY-RUN'} UNDO — DB {ARGS.db}: {total} penanda dicabut")
    for c, rows in plan.items():
        for d in rows:
            print(f"  {LABEL[c]:<6} {_name(c, d)}")
    if not ARGS.apply or not total:
        return
    for c, rows in plan.items():
        for d in rows:
            await db[c].update_one({"id": d["id"], "test_marked_by": FLAG},
                                   {"$unset": {"is_test": "", "test_marked_at": "", "test_marked_by": ""}})
            await audit(ACTOR, "test_data_unmarked", c, d["id"], {"is_test": False}, reason=FLAG)
    await db.migrations.update_one({"id": FLAG}, {"$set": {"undone_at": now_iso()}})
    print(f"Selesai: {total} penanda dicabut.")


if __name__ == "__main__":
    asyncio.run(undo() if ARGS.undo else forward())
