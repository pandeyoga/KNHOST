"""Shipment service (Sub-fase 1.8) — partial/multi shipment, SSOT-safe.

dispatch_task: kirim sebagian/seluruh qty sebuah task outbound.
- Pindahkan roll order committed→in_transit_sales via roll_service.ship_order_rolls (BUKAN $inc).
- Update task.shipped_qty + status (partially_shipped/dispatched).
- Catat 1 record `shipments` (No. Surat Jalan SJ-####) per event dispatch.
- recompute_so_status(order) → status SO terderivasi otomatis.

Qty selalu BASE UNIT (UOM-safe untuk Sub-fase 1.13).
"""
import logging
from typing import Any, Dict, Optional, Tuple, List
from fastapi import HTTPException
from pymongo import ReturnDocument
from db import db
from services import dual_qty_service as _dual  # FASE U — dua satuan (roll + ukuran)
from core_utils import new_id, now_iso, safe_doc, next_doc_number
from services.roll_service import ship_order_rolls
from services.fulfillment_status import recompute_so_status
logger = logging.getLogger(__name__)


EPS = 0.01
NON_DISPATCHABLE = {"dispatched", "cancelled", "escalated"}


async def _next_shipment_no(entity_id: Optional[str] = None) -> str:
    return await next_doc_number("shipments", "shipment_no", "SJ-", entity_id=entity_id)


def picked_roll_ids(task: Dict[str, Any]) -> List[str]:
    """AX-01 — roll hasil scan pick (server-resolved) yang belum ikut surat jalan task ini."""
    shipped = {r for e in task.get("scan_log", []) if e.get("scan_type") == "dispatch" for r in e.get("rolls", [])}
    out: List[str] = []
    for e in task.get("scan_log", []):
        rid = e.get("roll_id") if e.get("scan_type") == "pick" else None
        if rid and rid not in shipped and rid not in out:
            out.append(rid)
    return out


async def dispatch_task(
    task: Dict[str, Any], ship_qty: Optional[float], actor_name: str
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Dispatch (kirim) task outbound, mendukung pengiriman parsial. Return (task, shipment)."""
    if task.get("flow_type") != "outbound":
        raise HTTPException(status_code=400, detail="Task ini bukan outbound task")
    if task.get("status") in NON_DISPATCHABLE:
        raise HTTPException(status_code=400, detail=f"Task tidak bisa dispatch (status: {task.get('status')})")

    quantity = round(float(task.get("quantity", 0) or 0), 2)
    already = round(float(task.get("shipped_qty", 0) or 0), 2)
    picked = round(float(task.get("picked_qty", 0) or 0), 2)
    remaining = round(quantity - already, 2)
    pickable = round(picked - already, 2)             # yang sudah di-pick tapi belum dikirim
    max_ship = round(min(remaining, pickable), 2)
    if max_ship <= EPS:
        raise HTTPException(
            status_code=400,
            detail="Belum ada qty ter-pick yang siap dikirim (pick dulu sebelum dispatch).")

    qty = max_ship if (ship_qty is None or float(ship_qty) <= 0) else round(float(ship_qty), 2)
    if qty > max_ship + EPS:
        raise HTTPException(
            status_code=400,
            detail=f"Qty kirim ({qty}) melebihi yang siap dikirim ({max_ship}).")

    # Sesi 12 — klaim saga SESUDAH semua validasi, SEBELUM roll dipindah/surat jalan ditulis.
    from services import atomic_claim as _saga
    fresh = await _saga.claim("wms_tasks", task["id"], "dispatch", actor=actor_name,
                              precondition={"status": {"$nin": list(NON_DISPATCHABLE)}})
    # AX-03 — progres dibaca ulang dari dokumen hasil klaim (bukan snapshot sebelum kunci).
    quantity = round(float(fresh.get("quantity", 0) or 0), 2)
    already = round(float(fresh.get("shipped_qty", 0) or 0), 2)
    fresh_max = round(min(quantity - already, float(fresh.get("picked_qty", 0) or 0) - already), 2)
    if qty > fresh_max + EPS:
        await _saga.release("wms_tasks", task["id"])
        raise HTTPException(status_code=409, detail=(
            f"Progres tugas berubah (siap kirim kini {max(fresh_max, 0)}) — muat ulang lalu kirim lagi."))
    try:
        # AX-01 — roll yang DIPINDAI saat pick adalah roll yang dikirim (bukan dipilih ulang).
        res = await ship_order_rolls(task["order_id"], task["product_id"], task["warehouse_id"], qty,
                                     roll_ids=picked_roll_ids(fresh))
    except Exception:
        await _saga.release("wms_tasks", task["id"])
        raise
    shipped_now = round(res["shipped"], 2)
    new_shipped = round(already + shipped_now, 2)
    new_status = "dispatched" if new_shipped + EPS >= quantity else "partially_shipped"

    # AX-02 — surat jalan DITULIS sebelum tugas dinyatakan dispatched & kunci dilepas. Gagal di
    # tengah → kunci saga dibiarkan + ditandai gagal (terlihat di Kunci Saga), bukan task palsu.
    try:
        shipment = {
            "id": new_id("shp"), "shipment_no": await _next_shipment_no(task.get("entity_id")),
            "entity_id": task.get("entity_id"),
            "order_id": task["order_id"], "order_number": task.get("order_number", ""),
            "task_id": task["id"], "allocation_id": task.get("allocation_id"),
            "warehouse_id": task["warehouse_id"], "warehouse_name": task.get("warehouse_name", ""),
            "warehouse_city": task.get("warehouse_city", ""),
            "product_id": task["product_id"], "product_name": task.get("product_name", ""),
            "sku": task.get("sku", ""), "qty": shipped_now, "unit": task.get("unit", "meter"),
            # FASE U — dua satuan pada surat jalan: jumlah roll DIHITUNG dari roll yang
            # benar-benar keluar gudang (`res["rolls"]`), ukurannya tetap `qty` + `unit`.
            "qty_rolls": (len(res["rolls"]) if res.get("rolls") else None),
            "rolls": res["rolls"], "is_partial": new_status == "partially_shipped",
            "status": "dispatched", "created_by": actor_name, "created_at": now_iso(),
        }
        await db.wms_tasks.update_one({"id": task["id"]}, {"$set": {
            f"{_saga.LOCK}.operation": {"shipment_id": shipment["id"], "shipment_no": shipment["shipment_no"],
                                        "rolls": [r["roll_id"] for r in res["rolls"]], "qty": shipped_now}}})
        await db.shipments.insert_one(dict(shipment))
        updated = await db.wms_tasks.find_one_and_update(
            {"id": task["id"]},
            {**_saga.finish_set({"shipped_qty": new_shipped, "status": new_status, "updated_at": now_iso(),
                                 "last_shipment_id": shipment["id"]}),
             "$push": {"scan_log": {"id": new_id("scan"), "scan_type": "dispatch",
                                    "actual_qty": shipped_now, "actor": actor_name, "timestamp": now_iso(),
                                    "shipment_id": shipment["id"],
                                    "rolls": [r["roll_id"] for r in res["rolls"]]}}},
            projection={"_id": 0}, return_document=ReturnDocument.AFTER,
        )
    except Exception as exc:
        await _saga.mark_failed("wms_tasks", task["id"], f"dispatch setelah roll dipindah: {exc}")
        raise
    # FASE G-4 — jejak dua arah: surat jalan ↔ pesanan (dan tugas pengambilannya).
    from services import doc_refs_service as _refs
    await _refs.safe_link(("shipment", shipment["id"]), ("sales_order", task["order_id"]),
                          "parent", note="pengiriman atas pesanan")
    await _refs.safe_link(("shipment", shipment["id"]), ("picking_task", task["id"]),
                          "fulfills", note="dari tugas pengambilan")
    await recompute_so_status(task["order_id"])
    # Fase 4 OD — Surat Jalan terbit untuk SO hasil pesanan khusus → OD Dikirim.
    try:
        from services import special_order_phase2 as _p2
        await _p2.on_shipment_dispatched(task["order_id"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("[dispatch_task] efek samping gagal diabaikan: %s", exc)  # KN-C10
    # F-01 (audit 2026-09-02) — pendapatan & HPP diakui SAAT barang keluar, bukan
    # menunggu backfill saat restart. Best-effort: kegagalan GL tidak membatalkan
    # surat jalan yang sudah terbit (dicatat ke log; backfill akan mengulanginya).
    try:
        from services import gl_service as _gl
        await _gl.post_order_revenue_and_cogs(task["order_id"])
        await db.shipments.update_one({"id": shipment["id"]}, {"$set": {"gl_status": "posted"}})
        shipment["gl_status"] = "posted"
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger("shipment").error(
            "GL pendapatan order %s gagal saat dispatch: %s", task["order_id"], exc)
        # AX-02 — kegagalan finansial terlihat di surat jalan (backfill/retry idempotent menyusul).
        await db.shipments.update_one({"id": shipment["id"]}, {"$set": {
            "gl_status": "failed", "gl_error": str(exc)[:300]}})
        shipment["gl_status"] = "failed"
    return safe_doc(updated), safe_doc(shipment)
