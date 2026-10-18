"""DASHBOARD KESEHATAN GUDANG — satu layar ringkas per gudang:
insiden terbuka, red reads hari ini, antrean putaway, PA terbuka, gate exception,
roll tanpa tag, akurasi cycle count terakhir, device stale. Read-only agregasi.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from db import db
from services.rfid_service import PHYSICAL_STATUSES
from services.rfid_incident_service import HEARTBEAT_STALE_SECONDS
from services.analytics_time import now_wib, wib_midnight_utc

CC_INVALID_STATUSES = {"void", "rejected", "cancelled"}
logger = logging.getLogger(__name__)



async def health_dashboard(scope_ids: List[str]) -> Dict[str, Any]:
    whs = await db.warehouses.find({"active": {"$ne": False}},
                                   {"_id": 0, "id": 1, "name": 1, "roles": 1,
                                    "site_id": 1, "gate_config": 1}).to_list(200)
    rows = {w["id"]: {
        "warehouse_id": w["id"], "warehouse_name": w.get("name", ""),
        "roles": w.get("roles") or [],
        "open_incidents": 0, "red_reads_today": 0, "putaway_ready": 0,
        "putaway_pending": 0, "putaway_blocked": 0, "putaway_blocked_by_reason": {},
        "pa_open": 0, "gate_exceptions": 0, "untagged": 0,
        "last_cc": None, "latest_cc_status": None, "devices_total": 0, "devices_stale": 0,
    } for w in whs}

    # G3 D4-WMS-01 — hari bisnis WIB [00:00, 24:00) dikonversi ke UTC (bukan prefix tanggal UTC).
    d = now_wib().date()
    day_range = {"$gte": wib_midnight_utc(d), "$lt": wib_midnight_utc(d + timedelta(days=1))}
    async for r in db.rfid_incidents.aggregate([
            {"$match": {"status": "open"}},
            {"$group": {"_id": "$warehouse_id", "n": {"$sum": 1}}}]):
        if r["_id"] in rows:
            rows[r["_id"]]["open_incidents"] = r["n"]
    async for r in db.rfid_reads.aggregate([
            {"$match": {"result": "red", "timestamp": day_range,
                        "read_type": {"$in": ["gate_in", "gate_out"]}}},
            {"$group": {"_id": "$warehouse_id", "n": {"$sum": 1}}}]):
        if r["_id"] in rows:
            rows[r["_id"]]["red_reads_today"] = r["n"]
    # G3 D4-WMS-04 — resolver kelayakan SAMA dengan suggest/create putaway; sisanya blocked per alasan.
    from services.putaway_order_service import putaway_block_reason
    async for r in db.inventory_rolls.find(
            {"owner_entity_id": {"$in": scope_ids}, "length_remaining": {"$gt": 0},
             "journey.stage": "tag_verified", "journey.routing": {"$ne": "cross_dock"}}, {"_id": 0}):
        row = rows.get(r.get("warehouse_id"))
        if not row:
            continue
        row["putaway_pending"] += 1
        reason = await putaway_block_reason(r)
        if reason:
            row["putaway_blocked"] += 1
            row["putaway_blocked_by_reason"][reason] = row["putaway_blocked_by_reason"].get(reason, 0) + 1
        else:
            row["putaway_ready"] += 1
    async for r in db.putaway_orders.aggregate([
            {"$match": {"status": {"$in": ["open", "in_transit"]},
                        "owner_entity_id": {"$in": scope_ids}}},
            {"$group": {"_id": "$to_warehouse_id", "n": {"$sum": 1}}}]):
        if r["_id"] in rows:
            rows[r["_id"]]["pa_open"] = r["n"]
    async for r in db.inventory_rolls.aggregate([
            {"$match": {"journey.stage": "gate_exception",
                        "owner_entity_id": {"$in": scope_ids}}},
            {"$group": {"_id": "$warehouse_id", "n": {"$sum": 1}}}]):
        if r["_id"] in rows:
            rows[r["_id"]]["gate_exceptions"] = r["n"]
    async for r in db.inventory_rolls.aggregate([
            {"$match": {"owner_entity_id": {"$in": scope_ids}, "length_remaining": {"$gt": 0},
                        "status": {"$in": PHYSICAL_STATUSES},
                        "$or": [{"rfid_tag_id": None}, {"rfid_tag_id": ""},
                                {"rfid_tag_id": {"$exists": False}}]}},
            {"$group": {"_id": "$warehouse_id", "n": {"$sum": 1}}}]):
        if r["_id"] in rows:
            rows[r["_id"]]["untagged"] = r["n"]
    # G3 D4-WMS-02 — akurasi terakhir = hitungan SELESAI yang terukur (0% tetap 0%);
    # status sesi terbaru (mis. open) dilaporkan terpisah dan tidak menimpa angka terukur.
    async for cc in db.rfid_cycle_counts.aggregate([
            {"$match": {"accuracy_pct": {"$type": "number"},
                        "status": {"$nin": list(CC_INVALID_STATUSES)}}},
            {"$sort": {"created_at": -1}},
            {"$group": {"_id": "$warehouse_id", "doc": {"$first": "$$ROOT"}}}]):
        if cc["_id"] in rows:
            d = cc["doc"]
            rows[cc["_id"]]["last_cc"] = {"cc_number": d.get("cc_number"),
                                          "accuracy_pct": d.get("accuracy_pct"),
                                          "missing_count": d.get("missing_count"),
                                          "status": d.get("status", "completed"),
                                          "at": d.get("created_at")}
    async for s in db.rfid_verify_sessions.aggregate([
            {"$match": {"kind": "cycle_count"}}, {"$sort": {"created_at": -1}},
            {"$group": {"_id": "$warehouse_id", "doc": {"$first": "$$ROOT"}}}]):
        if s["_id"] in rows:
            rows[s["_id"]]["latest_cc_status"] = {"status": s["doc"].get("status"),
                                                  "at": s["doc"].get("created_at")}
    now = datetime.now(timezone.utc)
    async for d in db.rfid_devices.find({}, {"_id": 0, "warehouse_id": 1,
                                             "last_heartbeat": 1, "status": 1}):
        if d.get("warehouse_id") not in rows:
            continue
        rows[d["warehouse_id"]]["devices_total"] += 1
        hb = d.get("last_heartbeat")
        stale = True
        if hb:
            try:
                stale = (now - datetime.fromisoformat(hb.replace("Z", "+00:00"))) \
                    .total_seconds() > HEARTBEAT_STALE_SECONDS
            except ValueError as exc:
                logger.warning("[health_dashboard] efek samping gagal diabaikan: %s", exc)  # KN-C10
        if stale and d.get("status") == "online":
            rows[d["warehouse_id"]]["devices_stale"] += 1

    out = sorted(rows.values(),
                 key=lambda x: -(x["open_incidents"] * 100 + x["gate_exceptions"] * 10
                                 + x["putaway_ready"]))
    totals = {k: sum(r[k] for r in out) for k in
              ("open_incidents", "red_reads_today", "putaway_ready", "putaway_pending", "putaway_blocked", "pa_open",
               "gate_exceptions", "untagged", "devices_stale")}
    return {"totals": totals, "warehouses": out}
