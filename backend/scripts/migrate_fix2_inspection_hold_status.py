"""FIX-2 (audit B3a SSOT-3, keputusan koordinator #2) — selaraskan roll yang DITAHAN inspeksi (MD Quality / 4-point,
`inspection.hold.held=true`) tetapi statusnya masih `available`/`quarantine` → status `blocked` lewat
`roll_hold_service.sync_inspection_hold` (+ rebuild saldo). Sesudah FIX-2 penahanan baru langsung memakai jalur itu;
skrip ini hanya untuk data lama. BAWAAN = dry-run (tidak menulis apa pun).

Pakai (di dalam kontainer backend):
  python /app/backend/scripts/migrate_fix2_inspection_hold_status.py            # dry-run: daftar kandidat
  python /app/backend/scripts/migrate_fix2_inspection_hold_status.py --apply    # tulis
Data acuan 9 Nov 2026: 0 kandidat (B3a C.6 "inspection.hold.held=true · 0").
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


async def main(apply: bool) -> int:
    from db import db
    from services.roll_hold_service import HOLDABLE_STATUSES, sync_inspection_hold
    q = {"inspection.hold.held": True, "status": {"$in": list(HOLDABLE_STATUSES)}}
    rows = await db.inventory_rolls.find(q, {"_id": 0, "id": 1, "roll_no": 1, "status": 1, "earmarked_for": 1}).to_list(None)
    print(f"kandidat: {len(rows)} roll (mode {'APPLY' if apply else 'dry-run'})")
    changed = 0
    for r in rows:
        note = " (dilewati: di-peg pelanggan)" if r.get("earmarked_for") else ""
        print(f"  {r.get('roll_no')} {r['id']} status={r.get('status')}{note}")
        if apply and not note:
            if await sync_inspection_hold(r["id"], {"name": "Migrasi FIX-2"}):
                changed += 1
    if apply:
        print(f"diubah: {changed}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    sys.exit(asyncio.run(main(ap.parse_args().apply)))
