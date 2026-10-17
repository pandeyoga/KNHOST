"""L06 LN-061 — Meja Cutting/Admin Cutting: kemampuan lokasi, antrean potong, serah-terima hasil potong."""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core_utils import new_id, now_iso, safe_doc
from db import db
from services import sample_sale_service as smp
from services.roll_service import rebuild_balance

QUEUES = (("awaiting_internal", "Menunggu pembelian internal (stok milik PT lain)"),
          ("to_cut", "Menunggu dipotong gudang"),
          ("to_receive", "Hasil potong — menunggu diterima Admin Cutting"),
          ("ready", "Diterima Admin Cutting — siap kirim/ambil"))


async def list_locations() -> List[Dict[str, Any]]:
    rows = await db.warehouses.find({}, {"_id": 0, "id": 1, "name": 1, "city": 1, "cutting_caps": 1}).sort("name", 1).to_list(500)
    return [{**r, "cutting_caps": smp.warehouse_caps(r), "configured": r.get("cutting_caps") is not None} for r in rows]


async def set_location_caps(wid: str, caps: List[str], actor: str) -> Dict[str, Any]:
    bad = [c for c in caps if c not in smp.ALL_CAPS]
    if bad:
        raise HTTPException(status_code=400, detail=f"Kemampuan tidak dikenal: {', '.join(bad)}.")
    wh = await db.warehouses.find_one_and_update(
        {"id": wid}, {"$set": {"cutting_caps": [c for c in smp.ALL_CAPS if c in caps],
                               "cutting_caps_by": actor, "cutting_caps_at": now_iso()}},
        projection={"_id": 0, "id": 1, "name": 1, "cutting_caps": 1}, return_document=True)
    if not wh:
        raise HTTPException(status_code=404, detail="Lokasi tidak ditemukan.")
    return wh


def _queue_of(task: Dict[str, Any], line: Dict[str, Any]) -> Optional[str]:
    if task.get("status") in ("cancelled", "dispatched", "shipped", "delivered", "done"):
        return None
    if (task.get("cutting_handoff") or {}).get("received_at"):
        return "ready"
    if task.get("roll_id"):
        return "to_receive"
    return "awaiting_internal" if line.get("sample_cut_status") == "awaiting_internal" else "to_cut"


async def desk(scope: Dict[str, Any]) -> Dict[str, Any]:
    tasks = await db.wms_tasks.find({**scope, "task_subtype": "sample_cut"}, {"_id": 0}).sort("created_at", 1).to_list(500)
    orders = {o["id"]: o for o in await db.sales_orders.find(
        {"id": {"$in": list({t["order_id"] for t in tasks})}}, {"_id": 0, "id": 1, "items": 1, "number": 1, "catalogue": 1}).to_list(500)}
    whs = {w["id"]: w.get("name", "") async for w in db.warehouses.find({}, {"_id": 0, "id": 1, "name": 1})}
    buckets: Dict[str, List[Dict[str, Any]]] = {k: [] for k, _ in QUEUES}
    for t in tasks:
        o = orders.get(t["order_id"]) or {}
        line = next((i for i in o.get("items", []) if i.get("product_id") == t.get("product_id") and i.get("is_sample")), {})
        q = _queue_of(t, line)
        if not q:
            continue
        buckets[q].append({
            "task_id": t["id"], "order_id": t["order_id"], "order_number": t.get("order_number", ""),
            "customer_name": t.get("customer_name", ""), "product_name": t.get("product_name", ""), "sku": t.get("sku", ""),
            "sample_kind": line.get("sample_kind") or ("catalogue" if o.get("catalogue") else "standard"),
            "quantity": t.get("quantity"), "unit": t.get("unit"), "status": t.get("status"),
            "warehouse_id": t.get("warehouse_id"), "warehouse_name": whs.get(t.get("warehouse_id"), ""),
            "child_roll_no": t.get("child_roll_no", ""), "parent_roll_no": t.get("parent_roll_no", ""),
            "source_owner_entity_id": line.get("source_owner_entity_id", ""), "handoff": t.get("cutting_handoff")})
    return {"queues": [{"key": k, "label": lbl, "rows": buckets[k]} for k, lbl in QUEUES]}


async def receive(task_id: str, to_warehouse_id: str, actor: Dict[str, Any], scope_entities: List[str]) -> Dict[str, Any]:
    """Admin Cutting menerima hasil potong. Beda lokasi → roll anak dipindah nyata (asal→tujuan) + mutasi tercatat."""
    task = await db.wms_tasks.find_one({"id": task_id, "task_subtype": "sample_cut"}, {"_id": 0})
    if not task or (scope_entities and task.get("entity_id") not in scope_entities):
        raise HTTPException(status_code=404, detail="Tugas potong tidak ditemukan.")
    if (task.get("cutting_handoff") or {}).get("received_at"):
        return safe_doc(task)   # idempoten
    if not task.get("roll_id"):
        raise HTTPException(status_code=409, detail="Belum dipotong gudang — belum ada hasil potong untuk diterima.")
    src = task.get("warehouse_id")
    dst = (to_warehouse_id or "").strip() or src
    if not await db.warehouses.find_one({"id": dst}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Lokasi tujuan Admin Cutting tidak ditemukan.")
    now = now_iso()
    handoff = {"from_warehouse_id": src, "to_warehouse_id": dst, "received_by": actor.get("name", ""),
               "received_by_id": actor.get("id", ""), "received_at": now, "transferred": dst != src}
    claimed = await db.wms_tasks.find_one_and_update(
        {"id": task_id, "cutting_handoff.received_at": {"$exists": False}},
        {"$set": {"cutting_handoff": handoff, "warehouse_id": dst, "updated_at": now},
         "$push": {"scan_log": {"id": new_id("scan"), "scan_type": "cutting_handoff", "actor": actor.get("name", ""),
                                "timestamp": now, "from": src, "to": dst}}},
        projection={"_id": 0}, return_document=True)
    if not claimed:
        return safe_doc(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}))
    if dst != src:
        roll = await db.inventory_rolls.find_one_and_update(
            {"id": task["roll_id"]}, {"$set": {"warehouse_id": dst, "bin_id": "", "updated_at": now}},
            projection={"_id": 0}, return_document=False)
        base = {"product_id": roll["product_id"], "owner_entity_id": roll.get("owner_entity_id"), "roll_id": roll["id"],
                "unit": task.get("unit"), "source_document": task.get("order_number", ""), "reference_id": task["order_id"],
                "timestamp": now, "created_by": actor.get("name", ""), "qty_rolls": 1}
        qty = float(roll.get("length_remaining") or 0)
        await db.inventory_movements.insert_many([
            {**base, "id": f"mov_cho_{task_id}", "movement_type": "cutting_handoff_out", "warehouse_id": src, "quantity": -qty,
             "to_warehouse_id": dst},
            {**base, "id": f"mov_chi_{task_id}", "movement_type": "cutting_handoff_in", "warehouse_id": dst, "quantity": qty,
             "from_warehouse_id": src}])
        for w in (src, dst):
            await rebuild_balance(roll["product_id"], w, roll.get("owner_entity_id"))
        await db.sales_orders.update_one({"id": task["order_id"], "allocations.roll_ids": roll["id"]},
                                         {"$set": {"allocations.$.warehouse_id": dst}})
    await db.sales_orders.update_one(
        {"id": task["order_id"]},
        {"$push": {"timeline": {"event": "cutting_handoff", "label": "Hasil potong diterima Admin Cutting",
                                "actor": actor.get("name", ""), "at": now,
                                "note": f"{task.get('product_name', '')} · {task.get('child_roll_no', '')}" + (" (dipindah lokasi)" if dst != src else "")}}})
    return safe_doc(claimed)


async def pending_handoffs(order_id: str) -> List[str]:
    rows = await db.wms_tasks.find({"order_id": order_id, "task_subtype": "sample_cut", "roll_id": {"$nin": ["", None]},
                                    "status": {"$nin": ["cancelled"]}, "cutting_handoff.received_at": {"$exists": False}},
                                   {"_id": 0, "child_roll_no": 1}).to_list(200)
    return [r.get("child_roll_no", "") for r in rows]


async def change_catalogue_soft(order: Dict[str, Any], soft_product_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """LN-060-T02 — ganti warna soft: hanya komponen +2 yd berpindah; komponen dasar 1 yd TIDAK disentuh."""
    cat = order.get("catalogue")
    if not cat:
        raise HTTPException(status_code=400, detail="Pesanan ini bukan catalogue.")
    if order.get("status") not in ("waiting_approval", "approved"):
        raise HTTPException(status_code=409, detail="Warna soft hanya bisa diganti sebelum diteruskan ke gudang.")
    if soft_product_id not in {c["product_id"] for c in cat["base"]}:
        raise HTTPException(status_code=400, detail="Warna soft harus salah satu warna dasar catalogue.")
    fresh = await smp.build_catalogue(cat["template_id"], order.get("entity_id", ""), soft_product_id)
    new_cat = {**cat, "soft": fresh["soft"],
               "total_qty": round(len(cat["base"]) * smp.CATALOGUE_BASE_QTY + smp.CATALOGUE_SOFT_QTY, 2)}
    want = smp.catalogue_items(new_cat)
    items = [dict(i) for i in order.get("items", [])]
    for it in items:
        q = want.get(it["product_id"], 0.0)
        it["quantity"] = q
        it["base_quantity"] = q
    from services.config_service import compute_order_pricing
    pricing = await compute_order_pricing(items, order.get("entity_id"), 0,
                                          tax_override=(order.get("tax_override") or "").strip().lower() or None)
    old = (cat.get("soft") or {}).get("color", "—")
    await db.sales_orders.update_one({"id": order["id"]}, {"$set": {
        "catalogue": new_cat, "items": pricing["items"], "total_amount": pricing["total_amount"],
        "discount_total": pricing["discount_total"], "net_subtotal": pricing["net_subtotal"], "dpp": pricing["dpp"],
        "ppn_amount": pricing["ppn_amount"], "grand_total": pricing["grand_total"], "approval_amount": pricing["grand_total"],
        "updated_at": now_iso()},
        "$push": {"timeline": {"event": "catalogue_soft_changed", "label": "Warna soft catalogue diganti",
                               "actor": actor.get("name", ""), "at": now_iso(), "note": f"{old} → {fresh['soft']['color']}"}}})
    return safe_doc(await db.sales_orders.find_one({"id": order["id"]}, {"_id": 0}))
