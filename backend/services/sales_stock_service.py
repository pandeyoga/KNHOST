"""Stok GLOBAL untuk layar sales (Kasir/POS, katalog): sales tidak memilah per entitas —
pemenuhan lintas entitas (transfer / PO) diputuskan admin. Barang datang dipisah:
untuk SO (sudah terikat pesanan, tidak bisa dijanjikan lagi) vs untuk restock (boleh dijanjikan)."""
from typing import Any, Dict, List

from db import db
from services.roll_service import OPEN_PO_STATUSES
from services.stock_bucket_service import INCOMING_INTERCO_STATUSES


async def _sum_by_product(coll: str, match: Dict[str, Any], fields: List[str]) -> Dict[str, Dict[str, float]]:
    group: Dict[str, Any] = {"_id": "$product_id"}
    group.update({f: {"$sum": f"${f}"} for f in fields})
    return {r["_id"]: r for r in await db[coll].aggregate([{"$match": match}, {"$group": group}]).to_list(None)}


async def global_available(pid: str) -> float:
    bal = await _sum_by_product("inventory_balances", {"product_id": pid}, ["available_qty"])
    mk = await _sum_by_product("material_reservations", {"status": "active", "product_id": pid}, ["qty"])
    return round(max(float((bal.get(pid) or {}).get("available_qty") or 0) - float((mk.get(pid) or {}).get("qty") or 0), 0.0), 2)


async def apply_global(products: List[Dict[str, Any]], entity_id: str = "") -> None:
    ids = [p["id"] for p in products]
    if not ids:
        return
    if entity_id:
        own = await _sum_by_product("inventory_balances", {"product_id": {"$in": ids}, "owner_entity_id": entity_id}, ["available_qty"])
        for p in products:
            p.setdefault("available_qty", round(float((own.get(p["id"]) or {}).get("available_qty") or 0), 2))
    bal = await _sum_by_product("inventory_balances", {"product_id": {"$in": ids}},
                                ["available_qty", "reserved_qty", "on_hand_qty", "roll_count", "on_hand_roll_count"])
    mk = await _sum_by_product("material_reservations", {"status": "active", "product_id": {"$in": ids}}, ["qty"])
    inc_so: Dict[str, float] = {}
    inc_rs: Dict[str, float] = {}
    idset = set(ids)
    async for po in db.purchase_orders.find({"status": {"$in": OPEN_PO_STATUSES}, "items.product_id": {"$in": ids}},
                                            {"_id": 0, "items": 1, "source_so_ids": 1}):
        bound = bool(po.get("source_so_ids"))
        for it in po.get("items") or []:
            pid = it.get("product_id")
            if pid not in idset:
                continue
            open_qty = float(it.get("quantity", it.get("qty", 0)) or 0) - float(it.get("received_qty", 0) or 0)
            if open_qty > 0.01:
                tgt = inc_so if (bound or it.get("source_so_id")) else inc_rs
                tgt[pid] = tgt.get(pid, 0.0) + open_qty
    async for d in db.interco_transactions.find({"role": "buyer", "status": {"$in": INCOMING_INTERCO_STATUSES},
                                                 "items.product_id": {"$in": ids}},
                                                {"_id": 0, "items": 1, "source_order_id": 1}):
        for it in d.get("items") or []:
            pid = it.get("product_id")
            qty = float(it.get("quantity", it.get("qty", 0)) or 0)
            if pid in idset and qty > 0.01:
                tgt = inc_so if d.get("source_order_id") else inc_rs
                tgt[pid] = tgt.get(pid, 0.0) + qty
    for p in products:
        b = bal.get(p["id"], {})
        if "available_qty" in p:
            p["entity_available_qty"] = p.get("available_qty")
        makloon = round(float((mk.get(p["id"]) or {}).get("qty") or 0), 2)
        p.update({
            "available_qty": round(max(float(b.get("available_qty") or 0) - makloon, 0.0), 2),
            "reserved_qty": round(float(b.get("reserved_qty") or 0), 2),
            "on_hand_qty": round(float(b.get("on_hand_qty") or 0), 2),
            "roll_count": int(b.get("roll_count") or 0),
            "on_hand_roll_count": int(b.get("on_hand_roll_count") or 0),
            "makloon_reserved_qty": makloon,
            "incoming_so_qty": round(inc_so.get(p["id"], 0.0), 2),
            "incoming_restock_qty": round(inc_rs.get(p["id"], 0.0), 2),
            "stock_scope": "global",
        })
