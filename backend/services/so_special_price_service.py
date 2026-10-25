"""Trial 22 Okt 2026 (E10, keputusan pemilik) — harga khusus yang diminta di CHECKOUT berlaku **hanya untuk pesanan
ini**: SO lahir dengan harga normal, lalu tiap permintaan langsung menjadi pengajuan berlingkup pesanan (`scope=order`,
`so_id`) lewat satu pintu `routers.so_approvals.attach_order_price`. ACC Manajer menulis harga baris & menghitung ulang
total; penolakan membuka pilihan sales (ajukan harga lain / lanjut harga normal / batalkan).

Dulu checkout membuat pengajuan harga LANGGANAN tanpa SO: SO tetap berharga normal, gerbang persetujuan SO tidak tahu
ada pengajuan, dan ACC kemudian tidak mengubah SO itu.
"""
from typing import Any, Dict, List, Optional

from core_utils import DEFAULT_ENTITY_ID, new_id, now_iso, safe_doc
from db import db


async def attach_checkout_requests(order_id: str, lines: List[Any], actor: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    from routers.so_approvals import attach_order_price
    order = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0})) or {}
    result = None
    for ln in lines:
        idx, item = next(((i, it) for i, it in enumerate(order.get("items") or [])
                          if it.get("product_id") == ln.product_id and not it.get("is_sample")), (None, None))
        if item is None:
            continue
        pra = {
            "id": new_id("pra"), "customer_id": order.get("customer_id"), "customer_name": order.get("customer_name"),
            "product_id": item.get("product_id"), "product_name": item.get("product_name"),
            "normal_price": float(item.get("price", 0) or 0), "requested_price": float(ln.requested_price),
            "unit": item.get("unit", ""), "min_quantity": 0, "valid_until": "",
            "reason": (ln.special_price_reason or "").strip(), "entity_id": order.get("entity_id", DEFAULT_ENTITY_ID),
            "status": "pending", "scope": "order", "so_id": order_id, "so_item_index": idx, "source": "checkout",
            "attachments": [], "requested_by": actor["name"], "requested_by_name": actor["name"], "requested_by_id": actor["id"],
            "created_at": now_iso(), "updated_at": now_iso(),
        }
        await db.price_approvals.insert_one(dict(pra))
        result = await attach_order_price(order_id, pra, actor)
    return result
