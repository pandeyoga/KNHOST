"""2026-10 — HARGA INTERNAL antar-PT (kontrak `supplier_contracts` contract_type=internal).

Penetap harga (keputusan pemilik): MD, Finance, Admin — izin `interco_price.set`.
Satu kontrak = satu barang untuk satu pasangan PT penjual → pembeli (arah berlaku).
"""
from typing import Any, Dict, List, Optional

from db import db
from core_utils import now_iso, parse_decimal
from services import contract_service as cs
from services import interco_service as ics
from services import pricelist_service as pls


class InternalPriceError(Exception):
    """Galat ber-alasan (dipetakan ke 400)."""


async def _entity_names() -> Dict[str, str]:
    rows = await db.business_entities.find({}, {"_id": 0, "id": 1, "short_name": 1, "legal_name": 1}).to_list(200)
    return {e["id"]: e.get("short_name") or e.get("legal_name") or e["id"] for e in rows}


async def pricing_mode(seller_entity_id: str) -> str:
    return (await ics._config("antar_entitas.pricing_mode", seller_entity_id) or "fixed_price")


async def price_status(seller: str, buyer: str, product_id: str) -> Dict[str, Any]:
    """Apakah transfer seller→buyer untuk barang ini bisa dihargai SEKARANG."""
    mode = await pricing_mode(seller)
    try:
        pr = await ics._resolve_price(seller, buyer, product_id, None, mode)
        return {"price_ready": True, "unit_price": pr["unit_price"], "price_source": pr["source"],
                "pricing_mode": mode, "price_message": ""}
    except ics.IntercoError as exc:
        return {"price_ready": False, "unit_price": 0, "price_source": "", "pricing_mode": mode,
                "price_message": str(exc)}


async def _seller_stock(seller: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    async for b in db.inventory_balances.find({"owner_entity_id": seller, "available_qty": {"$gt": 0}},
                                              {"_id": 0, "product_id": 1, "available_qty": 1}):
        out[b["product_id"]] = round(out.get(b["product_id"], 0.0) + float(b.get("available_qty") or 0), 2)
    return out


async def _priced_pids(seller: str, buyer: str) -> set:
    today = now_iso()[:10]
    pids = set()
    async for c in db.supplier_contracts.find(
            {"entity_id": seller, "partner_kind": "entity", "partner_id": buyer, "status": "active"},
            {"_id": 0, "product_id": 1, "valid_from": 1, "valid_to": 1, "tariff_rate": 1}):
        if (c.get("valid_from") or "") > today or (c.get("valid_to") and c["valid_to"] < today):
            continue
        if float(c.get("tariff_rate") or 0) > 0:
            pids.add(c.get("product_id"))
    return pids


async def missing(seller: str, buyer: str, q: str = "", only_stock: bool = True) -> Dict[str, Any]:
    """Barang yang BELUM punya harga internal aktif untuk pasangan seller→buyer."""
    if not seller or not buyer or seller == buyer:
        raise InternalPriceError("Pilih PT penjual dan PT pembeli yang berbeda.")
    stock = await _seller_stock(seller)
    priced = await _priced_pids(seller, buyer)
    flt: Dict[str, Any] = {"status": {"$ne": "inactive"}}
    if only_stock:
        flt["id"] = {"$in": list(stock)}
    term = (q or "").strip()
    if term:
        flt["$or"] = [{"sku": {"$regex": term, "$options": "i"}}, {"name": {"$regex": term, "$options": "i"}}]
    prods = await db.products.find(flt, {"_id": 0, "id": 1, "sku": 1, "name": 1, "base_unit": 1, "price": 1}) \
        .sort("sku", 1).to_list(5000)
    todo = [p for p in prods if p["id"] not in priced]
    sell = await pls.resolve_many(seller, [p["id"] for p in todo], {p["id"]: p for p in todo})
    rows = [{"product_id": p["id"], "sku": p.get("sku", ""), "product_name": p.get("name", ""),
             "unit": p.get("base_unit", ""), "seller_stock": stock.get(p["id"], 0.0),
             "sell_price": float((sell.get(p["id"]) or {}).get("price") or 0)} for p in todo]
    return {"seller_entity_id": seller, "buyer_entity_id": buyer, "pricing_mode": await pricing_mode(seller),
            "total": len(rows), "priced": len(priced), "rows": rows}


async def summary() -> Dict[str, Any]:
    """Jumlah barang ber-stok yang belum punya harga internal, per pasangan PT (dua arah)."""
    names = await _entity_names()
    ents = [e["id"] async for e in db.business_entities.find({"status": "active"}, {"_id": 0, "id": 1})]
    pairs = []
    for s in ents:
        stock = await _seller_stock(s)
        for b in ents:
            if s == b:
                continue
            priced = await _priced_pids(s, b)
            pairs.append({"seller_entity_id": s, "seller_name": names.get(s, s),
                          "buyer_entity_id": b, "buyer_name": names.get(b, b),
                          "stocked": len(stock), "missing": len([p for p in stock if p not in priced])})
    return {"pairs": pairs, "missing_total": sum(p["missing"] for p in pairs)}


async def bulk_set(seller: str, buyer: str, items: List[Dict[str, Any]], actor: Dict[str, Any],
                   valid_from: str = "", notes: str = "") -> Dict[str, Any]:
    if not seller or not buyer or seller == buyer:
        raise InternalPriceError("Pilih PT penjual dan PT pembeli yang berbeda.")
    names = await _entity_names()
    if seller not in names or buyer not in names:
        raise InternalPriceError("PT penjual/pembeli tidak dikenal.")
    clean = []
    for it in items or []:
        price = parse_decimal(it.get("unit_price"), 2)
        if not it.get("product_id") or price <= 0:
            continue
        clean.append({"product_id": it["product_id"], "unit_price": price})
    if not clean:
        raise InternalPriceError("Isi minimal satu harga internal (> 0).")
    pids = [c["product_id"] for c in clean]
    known = {p["id"] async for p in db.products.find({"id": {"$in": pids}}, {"_id": 0, "id": 1})}
    created = []
    for c in clean:
        if c["product_id"] not in known:
            raise InternalPriceError(f"Barang {c['product_id']} tidak ditemukan.")
        doc = await cs.create_contract({
            "contract_type": "internal", "partner_id": buyer, "partner_name": names[buyer],
            "title": f"Harga internal {names[seller]} → {names[buyer]}",
            "product_id": c["product_id"], "tariff_basis": "lumpsum", "tariff_rate": c["unit_price"],
            "valid_from": valid_from or "", "status": "active", "notes": (notes or "").strip()[:300],
        }, entity_id=seller, actor=actor.get("name", ""))
        created.append({"id": doc["id"], "contract_number": doc["contract_number"],
                        "product_id": doc["product_id"], "sku": doc.get("product_sku", ""),
                        "unit_price": doc["tariff_rate"]})
    return {"created": created, "count": len(created)}


async def request_price(seller: str, buyer: str, product_id: str, actor: Dict[str, Any],
                        order_id: str = "", note: str = "") -> Dict[str, Any]:
    """Peran tanpa wewenang menetapkan → kirim permintaan ke pemegang `interco_price.set`."""
    from services import notification_service as ns
    names = await _entity_names()
    p = await db.products.find_one({"id": product_id}, {"_id": 0, "sku": 1, "name": 1}) or {}
    order = await db.sales_orders.find_one({"id": order_id}, {"_id": 0, "number": 1}) if order_id else None
    body = (f"{actor.get('name', 'Pengguna')} meminta harga internal {p.get('sku') or product_id} "
            f"({p.get('name', '')}) untuk transfer {names.get(seller, seller)} → {names.get(buyer, buyer)}"
            + (f" · pesanan {order.get('number')}" if order else "") + (f". Catatan: {note.strip()[:200]}" if note else "."))
    sent = await ns.create_addressed(
        permission=("interco_price", "set"), notif_type="interco_price_request",
        title="Permintaan harga internal", body=body, severity="warning",
        link=f"?view=internal-prices&seller={seller}&buyer={buyer}&q={p.get('sku', '')}",
        ref=f"icprice:{seller}:{buyer}:{product_id}")
    return {"sent": len(sent), "message": (f"Permintaan dikirim ke {len(sent)} orang (MD/Finance/Admin)."
                                           if sent else "Permintaan serupa sudah terkirim dan belum dibaca.")}


async def ready_for(seller: str, buyer: str, product_ids: List[str]) -> Optional[List[Dict[str, Any]]]:
    """Daftar barang yang BELUM bisa dihargai (None bila semua siap)."""
    out = []
    for pid in product_ids:
        st = await price_status(seller, buyer, pid)
        if not st["price_ready"]:
            p = await db.products.find_one({"id": pid}, {"_id": 0, "sku": 1, "name": 1}) or {}
            out.append({"product_id": pid, "sku": p.get("sku", ""), "product_name": p.get("name", ""),
                        "seller_entity_id": seller, "buyer_entity_id": buyer, "message": st["price_message"]})
    return out or None
