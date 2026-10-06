"""Backorder service (Sub-fase 1.6) — auto-fulfill lifecycle.

Saat barang masuk via Goods Receipt (inbound complete) membuat `inventory_rolls`
baru berstatus `available`, service ini mencoba **memenuhi otomatis** Sales Order
yang berstatus `waiting_stock` untuk (produk × entitas penjual) tersebut.

Prinsip:
- FIFO: order paling lama (created_at) dipenuhi lebih dulu (adil + anti-hoarding).
- Owner-scoped: hanya order milik `owner_entity_id` yang sama (jaga invarian D3).
- Reservasi nyata tetap lewat `roll_service.allocate_and_reserve_rolls(allow_partial=True)`
  (atomic find_one_and_update → aman dari race). Sisa yang belum terpenuhi tetap
  tercatat sebagai backorder hingga GR berikutnya.
- Saat seluruh backorder sebuah order terpenuhi → status kembali ke `reserved`
  (lanjut alur approval normal).
- 2026-10 — Admin Sales juga bisa memenuhi SEBAGIAN dari stok sendiri (`fulfill_from_stock`).
"""
import logging
from typing import Any, Dict, List, Optional
from db import db
from core_utils import now_iso
from services.roll_service import allocate_and_reserve_rolls
logger = logging.getLogger(__name__)


EPS = 0.01
ACTIVE = ["waiting_stock", "reserved", "waiting_approval", "approved", "confirmed"]


async def _fill_order(order: Dict[str, Any], product_id: str, owner_entity_id: str,
                      cap: Optional[float] = None, actor_name: str = "system",
                      reason: str = "Auto-fulfill backorder saat barang masuk (GR)") -> Dict[str, Any]:
    """G3 D4-BACKORDER-01 — demand SO DIKLAIM (kunci saga) lalu dibaca ULANG sebelum reservasi, sehingga
    dua pemenuhan bersamaan tidak sama-sama mereservasi kekurangan yang sama (80+80 > 100)."""
    from fastapi import HTTPException as _HE
    from services import atomic_claim as _saga
    try:
        fresh = await _saga.claim("sales_orders", order["id"], "backorder_fill",
                                  precondition={"status": {"$in": ACTIVE}}, actor=actor_name)
    except _HE:
        return {"got": 0.0, "exhausted": False, "completed": False, "busy": True}
    try:
        return await _fill_order_locked(fresh, product_id, owner_entity_id, cap, actor_name, reason)
    finally:
        await _saga.release("sales_orders", order["id"], fresh[_saga.LOCK]["token"])


async def _fill_order_locked(order: Dict[str, Any], product_id: str, owner_entity_id: str,
                             cap: Optional[float] = None, actor_name: str = "system",
                             reason: str = "Auto-fulfill backorder saat barang masuk (GR)") -> Dict[str, Any]:
    """Isi backorder (produk) satu pesanan dari stok entitas. `cap` = batas qty (None = sebanyak mungkin)."""
    order_got = 0.0
    exhausted = False
    new_allocs: List[Dict[str, Any]] = []   # KN-B07 — dikumpulkan untuk $push
    for bo in order.get("backorders", []):
        if bo.get("product_id") != product_id or bo.get("status") == "fulfilled":
            continue
        need = float(bo.get("backorder_qty", 0) or 0)
        if cap is not None:
            need = min(need, round(cap - order_got, 2))
        if need <= EPS:
            continue
        allocs = await allocate_and_reserve_rolls(
            product_id, need, bo.get("customer_city", ""), owner_entity_id, order["id"],
            allow_partial=True,
        )
        got = round(sum(float(a.get("quantity", 0) or 0) for a in allocs), 2)
        if got <= EPS:
            exhausted = True
            break
        bo["reserved_qty"] = round(float(bo.get("reserved_qty", 0) or 0) + got, 2)
        bo["backorder_qty"] = round(float(bo.get("backorder_qty", 0) or 0) - got, 2)
        if bo["backorder_qty"] <= EPS:
            bo["backorder_qty"] = 0.0
            bo["status"] = "fulfilled"
        bo["updated_at"] = now_iso()
        order["allocations"] = list(order.get("allocations", [])) + allocs
        new_allocs.extend(allocs)
        for it in order.get("items", []):
            if it.get("product_id") == product_id:
                it["reserved_qty"] = round(float(it.get("reserved_qty", 0) or 0) + got, 2)
                it["backorder_qty"] = round(max(0.0, float(it.get("backorder_qty", 0) or 0) - got), 2)
        order_got += got
        if got + EPS < need:
            exhausted = True
            break

    out = {"got": round(order_got, 2), "exhausted": exhausted, "completed": False}
    if order_got <= EPS:
        return out
    still_bo = any(float(b.get("backorder_qty", 0) or 0) > EPS for b in order.get("backorders", []))
    prev_status = order.get("status")
    # Decouple status dari backorder (Sub-fase 1.6.1)
    new_status = "reserved" if prev_status == "waiting_stock" else prev_status
    _bo_set = {"items": order["items"], "backorders": order["backorders"],
               "has_backorder": still_bo, "status": new_status, "updated_at": now_iso()}
    from services.so_status import stage_fields
    _bo_set.update(stage_fields({**order, **_bo_set}))
    await db.sales_orders.update_one(
        {"id": order["id"]},
        {"$set": _bo_set, "$push": {"allocations": {"$each": new_allocs}}})
    # Auto-commit (4a): order sudah approved/confirmed → roll baru langsung di-commit.
    if new_status in ("approved", "confirmed"):
        from services.roll_service import set_order_rolls_status
        await set_order_rolls_status(order["id"], "committed")
    from dependencies import audit
    await audit(actor_name, "backorder_auto_fulfilled", "sales_order", order["id"], {
        "product_id": product_id, "qty_fulfilled": round(order_got, 2),
        "status": new_status, "fully_fulfilled": not still_bo,
        "auto_committed": new_status in ("approved", "confirmed"),
    }, reason)
    try:
        from services import alert_ops_service as _ops
        await _ops.notify_backorder_ready(
            {**order, "status": new_status}, product_id, kind="fulfilled", qty=round(order_got, 2))
    except Exception as exc:  # noqa: BLE001 — notifikasi tidak boleh menggagalkan fulfillment
        logger.warning("[backorder] efek samping gagal diabaikan: %s", exc)  # KN-C10
    out["completed"] = not still_bo
    return out


async def auto_fulfill_backorders(product_id: str, owner_entity_id: str) -> Dict[str, Any]:
    """Penuhi otomatis backorder untuk (produk × entitas) setelah stok baru masuk."""
    orders = await db.sales_orders.find(
        {"has_backorder": True, "status": {"$in": ACTIVE},
         "entity_id": owner_entity_id, "backorders.product_id": product_id},
        {"_id": 0},
    ).sort("created_at", 1).to_list(500)
    result: Dict[str, Any] = {
        "product_id": product_id, "owner_entity_id": owner_entity_id,
        "orders_touched": 0, "orders_completed": 0, "qty_fulfilled": 0.0,
    }
    for order in orders:
        r = await _fill_order(order, product_id, owner_entity_id)
        if r["got"] > EPS:
            result["orders_touched"] += 1
            result["qty_fulfilled"] += r["got"]
            result["orders_completed"] += 1 if r["completed"] else 0
        if r["exhausted"]:
            break
    result["qty_fulfilled"] = round(result["qty_fulfilled"], 2)
    return result


async def fulfill_from_stock(order_id: str, product_id: str, qty: float,
                             actor_name: str) -> float:
    """Keputusan Admin Sales: penuhi `qty` kekurangan dari stok entitas penjual. Return qty tercadang."""
    order = await db.sales_orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        return 0.0
    r = await _fill_order(order, product_id, order.get("entity_id") or "", cap=qty,
                          actor_name=actor_name, reason="Admin Sales: penuhi kekurangan dari stok")
    if r.get("busy"):
        from fastapi import HTTPException as _HE
        raise _HE(status_code=409, detail="Pesanan sedang diproses pemenuhan lain — coba lagi sebentar.")
    return r["got"]
