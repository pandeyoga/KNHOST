"""UAT 24 Okt (P8, fase F1) — stok per LOKASI untuk katalog POS / HP.

Dulu katalog sengaja "TOTAL GLOBAL" (`ProductQuickView`: "Inventory POS = TOTAL GLOBAL saja"), sehingga sales di
Jakarta melihat stok Rancamalang seolah siap di depannya. Pemilik: pengguna memilih lokasi dulu, katalog menonjolkan
stok DI LOKASI ITU, roll dipilih lokasi dulu lalu FIFO.

Satu agregasi roll `available` per produk untuk gudang AKTIF di lokasi itu:
* `own_qty`   — milik PT penjual (bisa langsung dijual),
* `group_qty` — milik PT lain grup di lokasi yang sama (perlu transfer antar-PT; di gudang bersama cukup ganti pemilik),
* `rolls`     — jumlah roll milik PT penjual.
Satuan = satuan roll (satuan dasar produk) — tidak pernah dijumlah lintas satuan.
"""
from typing import Any, Dict, List, Optional

from db import db


async def site_warehouse_ids(site_id: str) -> List[str]:
    return [w["id"] async for w in db.warehouses.find({"site_id": site_id, "active": {"$ne": False}}, {"_id": 0, "id": 1})]


async def site_stock(site_id: str, entity_id: Optional[str], product_ids: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
    if not site_id:
        return {}
    whs = await site_warehouse_ids(site_id)
    if not whs:
        return {}
    match: Dict[str, Any] = {"warehouse_id": {"$in": whs}, "status": "available", "length_remaining": {"$gt": 0}}
    if product_ids:
        match["product_id"] = {"$in": list(product_ids)}
    own = entity_id if entity_id and entity_id != "all" else None
    pipeline = [
        {"$match": match},
        {"$group": {"_id": {"p": "$product_id", "u": "$unit", "own": {"$eq": ["$owner_entity_id", own]} if own else True},
                    "qty": {"$sum": "$length_remaining"}, "n": {"$sum": 1}}},
    ]
    out: Dict[str, Dict[str, Any]] = {}
    async for r in db.inventory_rolls.aggregate(pipeline):
        k = r["_id"]
        slot = out.setdefault(k["p"], {"own_qty": 0.0, "group_qty": 0.0, "rolls": 0, "unit": k.get("u") or ""})
        if k.get("own"):
            slot["own_qty"] = round(slot["own_qty"] + float(r["qty"] or 0), 2)
            slot["rolls"] += int(r["n"] or 0)
        else:
            slot["group_qty"] = round(slot["group_qty"] + float(r["qty"] or 0), 2)
    return out
