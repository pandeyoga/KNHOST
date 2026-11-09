#!/usr/bin/env python3
"""FIX-1 (K-GDG-07, B2a FLW-IN-07/FLW-IN-20, B1 K-B1-02) — gedung KHUSUS PT yang bertentangan dengan keputusan pemilik
"semua gedung dipakai bersama semua PT" diubah menjadi BERSAMA. HANYA DB uji/salinan.

Data acuan (snapshot 8 Nov): `SRG-01` (Soreang · Gudang Kanda, khusus Kanda) dan `WH-JKT` (Jakarta, khusus Sukacita)
masih `dedicated` → PO PT lain ke Soreang ditolak, tugas PT lain di gedung yang sama tidak bisa dibuat.

Yang diubah: gedung AKTIF ber-`sharing_mode: dedicated`, BUKAN data uji (`is_test`, kode `TEST-…`, nama `TEST_…`).
Gedung nonaktif (WH-BDG, GU-*) & gedung uji dilewati. Mengubah khusus → bersama tidak pernah mengurung stok (pagar
`dedication_blockers` hanya untuk arah sebaliknya). Yang TIDAK disentuh: stok, roll, bin, aturan simpan, gate.

Jejak & pembalik: satu dokumen `migrations` (`id = fix_data_2026_11_09_gedung_bersama`) menyimpan nilai SEBELUM per
gedung + audit per gedung; `--undo` mengembalikan nilai itu (hanya bila gedung belum diubah orang lain sesudahnya).

Pakai (di dalam kontainer backend, repo = /app):
    python /app/scripts/fix_data_2026_11_09_gedung_bersama.py --db kn_test_trial            # dry-run (bawaan)
    python /app/scripts/fix_data_2026_11_09_gedung_bersama.py --db kn_test_trial --apply
    python /app/scripts/fix_data_2026_11_09_gedung_bersama.py --db kn_test_trial --undo --apply
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
    ap.add_argument("--undo", action="store_true", help="kembalikan nilai sebelum dari jejak migrations")
    return ap.parse_args()


ARGS = _args()
if ARGS.db not in ALLOWED_DBS:
    print(f"DITOLAK: skrip ini hanya untuk DB uji {sorted(ALLOWED_DBS)}; --db {ARGS.db} tidak diproses.")
    sys.exit(2)
os.environ["DB_NAME"] = ARGS.db          # db.py membaca DB_NAME saat di-import
BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402
from dependencies import audit  # noqa: E402

FLAG = "fix_data_2026_11_09_gedung_bersama"
ACTOR = "Sistem (K-GDG-07 gedung dipakai bersama)"


def is_test_warehouse(w: dict) -> bool:
    code, name = str(w.get("code") or ""), str(w.get("name") or "")
    return bool(w.get("is_test")) or code.upper().startswith("TEST-") or name.upper().startswith("TEST_")


async def plan() -> list:
    rows = []
    async for w in db.warehouses.find({"active": {"$ne": False}, "sharing_mode": "dedicated"}, {"_id": 0}).sort("code", 1):
        if is_test_warehouse(w):
            continue
        rows.append(w)
    return rows


async def apply_forward() -> None:
    rows = await plan()
    print(f"{'TERAPKAN' if ARGS.apply else 'DRY-RUN'} — DB {ARGS.db}: {len(rows)} gedung khusus PT → bersama")
    for w in rows:
        print(f"  {w.get('code', ''):<14} {str(w.get('name', ''))[:40]:<40} khusus {w.get('entity_ids') or []} → bersama")
    if not ARGS.apply or not rows:
        return
    log = []
    for w in rows:
        res = await db.warehouses.update_one({"id": w["id"], "sharing_mode": "dedicated", "updated_at": w.get("updated_at")},
                                             {"$set": {"sharing_mode": "shared", "entity_ids": [], "updated_at": now_iso()}})
        if not res.modified_count:
            print(f"  LEWAT {w.get('code')}: gedung berubah bersamaan — jalankan ulang skrip.")
            continue
        before = {"sharing_mode": w.get("sharing_mode"), "entity_ids": w.get("entity_ids") or []}
        log.append({"warehouse_id": w["id"], "code": w.get("code"), "before": before,
                    "after": {"sharing_mode": "shared", "entity_ids": []}})
        await audit(ACTOR, "warehouse_sharing_fixed", "warehouse", w["id"], {"before": before, "after": "shared"}, reason=FLAG)
    await db.migrations.update_one({"id": FLAG}, {"$set": {"id": FLAG, "applied_at": now_iso(), "by": ACTOR},
                                                  "$push": {"runs": {"at": now_iso(), "changes": log}}}, upsert=True)
    print(f"Selesai: {len(log)} gedung diperbarui (jejak di migrations.{FLAG}).")


async def apply_undo() -> None:
    mig = await db.migrations.find_one({"id": FLAG}, {"_id": 0}) or {}
    changes = [c for run in mig.get("runs") or [] for c in run.get("changes") or []]
    print(f"{'TERAPKAN' if ARGS.apply else 'DRY-RUN'} UNDO — DB {ARGS.db}: {len(changes)} gedung dari jejak")
    for c in changes:
        print(f"  {c.get('code', ''):<14} bersama → {c['before']}")
    if not ARGS.apply or not changes:
        return
    n = 0
    for c in changes:
        res = await db.warehouses.update_one({"id": c["warehouse_id"], "sharing_mode": "shared"},
                                             {"$set": {**c["before"], "updated_at": now_iso()}})
        if res.modified_count:
            n += 1
            await audit(ACTOR, "warehouse_sharing_fix_undone", "warehouse", c["warehouse_id"], c["before"], reason=FLAG)
        else:
            print(f"  LEWAT {c.get('code')}: gedung sudah diubah sesudah skrip — tidak dikembalikan.")
    await db.migrations.update_one({"id": FLAG}, {"$set": {"undone_at": now_iso()}, "$unset": {"runs": ""}})
    print(f"Selesai: {n} gedung dikembalikan.")


if __name__ == "__main__":
    asyncio.run(apply_undo() if ARGS.undo else apply_forward())
