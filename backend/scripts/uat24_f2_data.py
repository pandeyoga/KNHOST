"""UAT 24 Okt — data fase F2 (P11 penanda roll MD Quality / 4-point). Idempoten.

* P11.1 — penanda DATAR di roll diisi dari jejak bersarang yang sudah ada:
  `inspection.md_quality_at` → `md_quality_checked` (+ `_at/_by/_spk`);
  `inspection.inspected_at` + poin 4-point → `inspected_4point` (+ `_at/_by/_spk`).
* `qc_via_sampling` lama (keputusan lewat sampel, tanpa 4-point) → `four_point_pending`.
* Indeks untuk filter stok "belum MDQ" / "belum 4-point".

Pemakaian (di container backend): DB_NAME=<db> python scripts/uat24_f2_data.py [--dry-run]
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import db  # noqa: E402

DRY = "--dry-run" in sys.argv


async def main() -> None:
    print("DB:", os.environ.get("DB_NAME"), "(dry-run)" if DRY else "")
    n_md = n_4p = 0
    async for r in db.inventory_rolls.find(
            {"$or": [{"inspection.md_quality_at": {"$exists": True}, "md_quality_checked": {"$ne": True}},
                     {"inspection.inspected_at": {"$exists": True}, "inspected_4point": {"$ne": True}}]},
            {"_id": 0, "id": 1, "inspection": 1, "md_quality_checked": 1, "inspected_4point": 1}):
        ins = r.get("inspection") or {}
        sets = {}
        if ins.get("md_quality_at") and not r.get("md_quality_checked"):
            sets.update({"md_quality_checked": True, "md_quality_checked_at": ins["md_quality_at"],
                         "md_quality_checked_by": ins.get("md_quality_by", ""),
                         "md_quality_spk": ins.get("md_quality_doc_number") or ins.get("inspection_doc_number", "")})
            n_md += 1
        # `inspected_at` juga ditulis bagian MD lama (form gabungan) — 4-point hanya bila ada poin/grade 4-point.
        if ins.get("inspected_at") and not r.get("inspected_4point") and (
                ins.get("points") is not None or ins.get("grade") or ins.get("defect_points") is not None):
            sets.update({"inspected_4point": True, "inspected_4point_at": ins["inspected_at"],
                         "inspected_4point_by": ins.get("inspected_by", ""),
                         "inspected_4point_spk": ins.get("inspection_doc_number", "")})
            n_4p += 1
        if sets and not DRY:
            await db.inventory_rolls.update_one({"id": r["id"]}, {"$set": sets})
    print(f"  penanda MDQ diisi: {n_md} roll · penanda 4-point diisi: {n_4p} roll")
    q = {"qc_via_sampling": {"$exists": True}, "inspected_4point": {"$ne": True}, "four_point_pending": {"$ne": True}}
    n_pend = await db.inventory_rolls.count_documents(q)
    print(f"  qc_via_sampling → four_point_pending: {n_pend} roll")
    if n_pend and not DRY:
        await db.inventory_rolls.update_many(q, {"$set": {"four_point_pending": True}})
    if not DRY:
        await db.inventory_rolls.create_index([("md_quality_checked", 1), ("owner_entity_id", 1)])
        await db.inventory_rolls.create_index([("inspected_4point", 1), ("owner_entity_id", 1)])
        print("  indeks penanda dibuat")


if __name__ == "__main__":
    asyncio.run(main())
