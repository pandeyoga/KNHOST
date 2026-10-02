"""Tanya KN F5 — snapshot harian stok & piutang (23.55 WIB) → posisi `as_of` masa lalu di mesin analitik."""
from __future__ import annotations

from typing import Any, Dict, Optional

from db import db
from services import analytics_catalog as cat
from services.analytics_time import now_wib

_STOCK_KEYS = ("owner_entity_id", "warehouse_id", "product_id", "grade", "dye_lot", "unit", "fabric_type", "line_code")


async def snapshot_stock(day: str) -> int:
    rem = {"$ifNull": ["$length_remaining", 0]}
    pipe = [{"$match": {"status": {"$in": list(cat.PHYSICAL_ROLL_STATUSES)}}},
            {"$group": {"_id": {k: f"${k}" for k in _STOCK_KEYS}, "qty": {"$sum": rem}, "rolls": {"$sum": 1},
                        "value": {"$sum": {"$multiply": [rem, {"$ifNull": ["$unit_cost", 0]}]}},
                        "avail": {"$sum": {"$cond": [{"$eq": ["$status", "available"]}, rem, 0]}},
                        "reserved": {"$sum": {"$cond": [{"$in": ["$status", list(cat.RESERVED_ROLL_STATUSES)]}, rem, 0]}}}}]
    rows = [{"date": day, **{k: r["_id"].get(k) or "" for k in _STOCK_KEYS},
             **{k: r[k] for k in ("qty", "rolls", "value", "avail", "reserved")}}
            async for r in db.inventory_rolls.aggregate(pipe)]
    await db.fact_stock_daily.delete_many({"date": day})
    if rows:
        await db.fact_stock_daily.insert_many(rows)
    return len(rows)


async def snapshot_ar(day: str) -> int:
    from services.ar_aging_service import BUCKET_KEYS, aging_report
    from services.entity_context_service import all_active_entity_ids
    rows = []
    for ent in await all_active_entity_ids():
        rep = await aging_report(ent, None)
        for r in rep.get("customers") or []:
            for b in BUCKET_KEYS:
                amt = float(r.get(b) or 0)
                if amt:
                    rows.append({"date": day, "entity_id": ent, "customer_id": r.get("customer_id") or "",
                                 "sales_id": r.get("assigned_sales_id") or "", "aging_bucket": b,
                                 "ar_outstanding": amt, "ar_overdue": amt if b != "current" else 0.0})
    await db.fact_ar_daily.delete_many({"date": day})
    if rows:
        await db.fact_ar_daily.insert_many(rows)
    return len(rows)


async def job_snapshot_daily() -> Dict[str, Any]:
    day = now_wib().date().isoformat()
    for coll in ("fact_stock_daily", "fact_ar_daily"):
        await db[coll].create_index([("date", 1), ("entity_id" if coll == "fact_ar_daily" else "owner_entity_id", 1)])
    s, a = await snapshot_stock(day), await snapshot_ar(day)
    return {"scanned": s + a, "created": s + a, "detail": f"Snapshot {day}: {s} baris stok, {a} baris piutang"}


async def snapshot_for(coll: str, date_to) -> Optional[str]:
    """Tanggal snapshot terakhir ≤ `date_to` bila periode sudah lewat (sebelum hari ini WIB); selain itu None."""
    if date_to >= now_wib().date():
        return None
    doc = await db[coll].find_one({"date": {"$lte": date_to.isoformat()}}, {"_id": 0, "date": 1}, sort=[("date", -1)])
    return doc["date"] if doc else None


async def status() -> Dict[str, Any]:
    out = {}
    for coll in ("fact_stock_daily", "fact_ar_daily"):
        last = await db[coll].find_one({}, {"_id": 0, "date": 1}, sort=[("date", -1)])
        out[coll] = {"last_date": (last or {}).get("date"), "days": len(await db[coll].distinct("date"))}
    return out
