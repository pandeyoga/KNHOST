"""GRN Fase 7 — beralih penuh: mode penerimaan per badan usaha (`receiving.mode` = legacy | grn).

Mode `grn`: stok dari supplier/makloon HANYA masuk lewat Kedatangan Barang yang ditutup. Tugas lama yang sudah
setengah jalan saat mode diganti ditandai `legacy_in_flight` dan tetap boleh diselesaikan di layar lama.
"""
from typing import Any, Dict, List

from fastapi import HTTPException

from core_utils import now_iso
from db import db
from dependencies import audit
from entity_scope import EntityContext
from services.config_resolver import ConfigWriteError, set_value, value_of

INBOUND_LIVE = ["waiting_goods", "receiving", "qc_check", "put_away"]
STARTED = {"$or": [{"status": {"$in": ["receiving", "qc_check", "put_away"]}}, {"received_qty": {"$gt": 0}}]}


async def mode_of(entity_id: str) -> str:
    return await value_of("receiving.mode", {"entity_id": entity_id or ""}) or "legacy"


async def guard_makloon_receive(order: Dict[str, Any]) -> None:
    """Terima hasil MKO langsung (layar lama) ditolak di entitas mode GRN — jalurnya lewat Kedatangan Barang."""
    if await mode_of(order.get("entity_id") or "") == "grn":
        raise HTTPException(status_code=409, detail={
            "code": "GRN_MODE",
            "message": "Penerimaan di badan usaha ini memakai Kedatangan Barang (surat jalan). "
                       "Terima hasil makloon lewat tombol 'Terima lewat Kedatangan (SJ)'."})


async def _entity_status(ent: Dict[str, Any]) -> Dict[str, Any]:
    eid = ent["id"]
    base = {"entity_id": eid, "flow_type": "inbound", "status": {"$in": INBOUND_LIVE}, "grn_active_id": {"$in": [None, ""]}}
    started = await db.wms_tasks.count_documents({**base, **STARTED, "legacy_in_flight": {"$ne": True}})
    in_flight = await db.wms_tasks.find({**base, "legacy_in_flight": True},
                                        {"_id": 0, "id": 1, "po_number": 1, "product_name": 1, "status": 1,
                                         "received_qty": 1, "expected_qty": 1, "unit": 1}).to_list(50)
    return {
        "entity_id": eid, "entity_name": ent.get("name") or ent.get("code") or eid, "code": ent.get("code", ""),
        "mode": await mode_of(eid),
        "waiting_tasks": await db.wms_tasks.count_documents({"entity_id": eid, "flow_type": "inbound",
                                                             "status": "waiting_goods"}),
        "started_legacy": started, "legacy_in_flight": in_flight,
        "open_grns": await db.goods_receipts.count_documents({"entity_id": eid, "status": {
            "$nin": ["closed", "cancelled", "rejected"]}}),
        "closed_grns": await db.goods_receipts.count_documents({"entity_id": eid, "status": "closed"}),
    }


async def status(ctx: EntityContext) -> Dict[str, Any]:
    ids = ctx.allowed_entity_ids or [ctx.active_entity_id]
    ents = await db.business_entities.find({"id": {"$in": ids}}, {"_id": 0}).sort("id", 1).to_list(50)
    rows: List[Dict[str, Any]] = [await _entity_status(e) for e in ents]
    return {"active_entity_id": ctx.active_entity_id or "", "entities": rows,
            "modes": {r["entity_id"]: r["mode"] for r in rows}}


async def switch(entity_id: str, mode: str, reason: str, actor: Dict[str, Any], ctx: EntityContext) -> Dict[str, Any]:
    if not ctx.can_access(entity_id):
        raise HTTPException(status_code=403, detail="Badan usaha di luar akses Anda.")
    ent = await db.business_entities.find_one({"id": entity_id}, {"_id": 0})
    if not ent:
        raise HTTPException(status_code=404, detail="Badan usaha tidak ditemukan.")
    prev = await mode_of(entity_id)
    if prev == mode:
        return await _entity_status(ent)
    try:
        await set_value("receiving.mode", mode, scope_type="entity", scope_id=entity_id, actor=actor["name"],
                        actor_id=actor.get("id", ""), reason=reason)
    except ConfigWriteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    marked = 0
    if mode == "grn":   # tugas yang sudah dimulai di layar lama boleh diselesaikan di sana
        res = await db.wms_tasks.update_many(
            {"entity_id": entity_id, "flow_type": "inbound", "status": {"$in": INBOUND_LIVE},
             "grn_active_id": {"$in": [None, ""]}, **STARTED},
            {"$set": {"legacy_in_flight": True, "legacy_in_flight_at": now_iso()}})
        marked = res.modified_count
    await audit(actor["name"], "receiving_mode_switched", "business_entity", entity_id,
                {"from": prev, "to": mode, "legacy_in_flight_marked": marked}, reason=reason, scope_entity_id=entity_id)
    return {**await _entity_status(ent), "legacy_in_flight_marked": marked}
