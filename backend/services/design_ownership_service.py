"""UAT 24 Okt (P1 + P6) — KEPEMILIKAN DESAIN & rantai desain → SKU.

SSOT kepemilikan ada di `design_gallery` (bukan di SKU):
  * `ownership`: "white" (white label — bebas dijual) | "customer" (customer label — milik satu pelanggan);
  * `owner_customer_id/name`, `ownership_source` (special_order / claim / manual), `ownership_history[]`;
  * `claims[]` — pelanggan mengajukan klaim; tetap white sampai Manajer memutus (P1-K1);
  * `ownership_allow_customer_ids` — pembeli LAMA saat desain diklaim: boleh repeat dari stok yang ada (P1-K1).

Turunan ke SKU (`products` ber-`design_id`) ditulis ulang setiap kali desain/kepemilikan berubah (`sync_products`):
  * P6 — `design_code/title`, `pattern_category_*`, `design_category_*`, `design_tags` (filter POS & Pusat Export);
  * P1.3 — customer label → `exclusive_customer_id/name` + `exclusive_source="design"`, sehingga SEMUA pagar eksklusif
    yang sudah ada (SO, POS, spesifikasi) ikut berlaku tanpa aturan kedua. Eksklusif hasil OD (tanpa
    `exclusive_source`) tidak pernah ditimpa.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core_utils import new_id, now_iso
from db import db

OWNERSHIP_LABEL = {"white": "White label", "customer": "Customer label"}
SOURCE_LABEL = {"special_order": "Pesanan Khusus", "claim": "Klaim pelanggan", "manual": "Ditetapkan manual"}
DESIGN_PRODUCT_FIELDS = ("design_id", "design_code", "design_title", "pattern_category_code", "pattern_category_name",
                         "design_category_code", "design_category_name", "design_tags")
LIVE_SO = {"$nin": ["cancelled", "draft", "rejected"]}


class OwnershipError(ValueError):
    pass


def view(doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Field kepemilikan untuk layar (galeri/detail) — dihitung, bawaan white untuk data lama."""
    d = doc or {}
    own = d.get("ownership") if d.get("ownership") in OWNERSHIP_LABEL else "white"
    pending = [c for c in d.get("claims") or [] if c.get("status") == "pending"]
    label = OWNERSHIP_LABEL[own] + (f" · {d.get('owner_customer_name')}" if own == "customer" and d.get("owner_customer_name") else "")
    return {"ownership": own, "ownership_label": label,
            "owner_customer_id": d.get("owner_customer_id", "") if own == "customer" else "",
            "owner_customer_name": d.get("owner_customer_name", "") if own == "customer" else "",
            "ownership_source": d.get("ownership_source", "") if own == "customer" else "",
            "ownership_source_label": SOURCE_LABEL.get(d.get("ownership_source", ""), "") if own == "customer" else "",
            "claim_pending": bool(pending), "pending_claims": pending}


def _product_fields(design: Dict[str, Any]) -> Dict[str, Any]:
    return {"design_id": design["id"], "design_code": design.get("code", ""), "design_title": design.get("title", ""),
            "pattern_category_code": design.get("category_code", ""), "pattern_category_name": design.get("category_name", ""),
            "design_category_code": design.get("design_category_code", ""),
            "design_category_name": design.get("design_category_name", ""),
            "design_tags": list(design.get("tags") or [])}


async def sync_products(design_id: str) -> int:
    """Tulis ulang turunan desain di SEMUA SKU ber-`design_id` ini (P6 + eksklusif P1.3)."""
    design = await db.design_gallery.find_one({"id": design_id}, {"_id": 0})
    if not design:
        return 0
    now = now_iso()
    n = (await db.products.update_many({"design_id": design_id},
                                       {"$set": {**_product_fields(design), "updated_at": now}})).modified_count
    if design.get("ownership") == "customer" and design.get("owner_customer_id"):
        await db.products.update_many(
            {"design_id": design_id, "$or": [{"exclusive_customer_id": {"$in": [None, ""]}},
                                             {"exclusive_source": "design"}]},
            {"$set": {"exclusive_customer_id": design["owner_customer_id"],
                      "exclusive_customer_name": design.get("owner_customer_name", ""),
                      "exclusive_source": "design", "exclusive_design_code": design.get("code", ""),
                      "exclusive_allow_customer_ids": list(design.get("ownership_allow_customer_ids") or []),
                      "catalog_scope": "customer", "updated_at": now}})
    else:
        await db.products.update_many(
            {"design_id": design_id, "exclusive_source": "design"},
            {"$set": {"catalog_scope": "", "updated_at": now},
             "$unset": {"exclusive_customer_id": "", "exclusive_customer_name": "", "exclusive_source": "",
                        "exclusive_design_code": "", "exclusive_allow_customer_ids": ""}})
    return n


async def link_products(design_id: str, product_ids: List[str]) -> int:
    """P1.2/P6.1 — tautkan SKU ke desain (form master produk/induk, realisasi OD) lalu salin turunannya."""
    ids = [p for p in product_ids or [] if p]
    if not design_id or not ids:
        return 0
    if not await db.design_gallery.find_one({"id": design_id}, {"_id": 0, "id": 1}):
        raise OwnershipError("Desain tidak ditemukan.")
    await db.products.update_many({"id": {"$in": ids}}, {"$set": {"design_id": design_id}})
    await sync_products(design_id)
    return len(ids)


async def unlink_products(product_ids: List[str]) -> int:
    ids = [p for p in product_ids or [] if p]
    if not ids:
        return 0
    res = await db.products.update_many(
        {"id": {"$in": ids}},
        {"$set": {"updated_at": now_iso()},
         "$unset": {**{f: "" for f in DESIGN_PRODUCT_FIELDS}, "exclusive_design_code": ""}})
    await db.products.update_many(
        {"id": {"$in": ids}, "exclusive_source": "design"},
        {"$set": {"catalog_scope": ""},
         "$unset": {"exclusive_customer_id": "", "exclusive_customer_name": "", "exclusive_source": "",
                    "exclusive_allow_customer_ids": ""}})
    return res.modified_count


async def usage(design_id: str) -> Dict[str, Any]:
    """P1.4 — data pendukung keputusan klaim: siapa membeli SKU ber-desain ini, berapa SO, qty & nilai."""
    products = await db.products.find({"design_id": design_id},
                                      {"_id": 0, "id": 1, "sku": 1, "name": 1, "lifecycle": 1}).to_list(500)
    pids = [p["id"] for p in products]
    by_cust: Dict[str, Dict[str, Any]] = {}
    orders = 0
    if pids:
        async for so in db.sales_orders.find({"items.product_id": {"$in": pids}, "status": LIVE_SO},
                                             {"_id": 0, "id": 1, "number": 1, "customer_id": 1, "customer_name": 1,
                                              "created_at": 1, "items": 1}).sort("created_at", 1):
            orders += 1
            c = by_cust.setdefault(so.get("customer_id") or "", {
                "customer_id": so.get("customer_id") or "", "customer_name": so.get("customer_name") or "—",
                "orders": 0, "qty_by_unit": {}, "value": 0.0, "first_order_number": so.get("number", ""),
                "first_order_at": so.get("created_at", ""), "last_order_number": "", "last_order_at": ""})
            c["orders"] += 1
            c["last_order_number"], c["last_order_at"] = so.get("number", ""), so.get("created_at", "")
            for it in so.get("items") or []:
                if it.get("product_id") in pids:
                    u = it.get("unit") or "-"
                    c["qty_by_unit"][u] = round(c["qty_by_unit"].get(u, 0.0) + float(it.get("quantity") or 0), 2)
                    c["value"] = round(c["value"] + float(it.get("line_total") or it.get("subtotal") or 0), 2)
    customers = sorted(by_cust.values(), key=lambda c: (-c["orders"], -c["value"]))
    for c in customers:
        c["repeat"] = c["orders"] >= 2
    return {"design_id": design_id, "products": products, "produced": bool(products),
            "orders": orders, "customers": customers,
            "repeat_customers": sum(1 for c in customers if c["repeat"])}


async def _load(design_id: str) -> Dict[str, Any]:
    d = await db.design_gallery.find_one({"id": design_id}, {"_id": 0})
    if not d:
        raise OwnershipError("Desain tidak ditemukan.")
    return d


async def _customer(customer_id: str, entity_id: str) -> Dict[str, Any]:
    c = await db.customers.find_one({"id": customer_id}, {"_id": 0, "id": 1, "name": 1, "entity_id": 1})
    if not c:
        raise OwnershipError("Pelanggan tidak ditemukan.")
    if entity_id and c.get("entity_id") and c["entity_id"] != entity_id:
        raise OwnershipError("Pelanggan itu milik badan usaha lain dari desain ini.")
    return c


def _hist(action: str, actor: Dict[str, Any], **kw: Any) -> Dict[str, Any]:
    return {"id": new_id("own"), "action": action, "by": actor.get("name", ""), "by_id": actor.get("id", ""),
            "at": now_iso(), **kw}


async def set_customer_owner(design_id: str, customer_id: str, source: str, actor: Dict[str, Any],
                             reason: str = "") -> Dict[str, Any]:
    """Jadikan customer label. Pembeli lama (selain pemilik) dicatat → boleh repeat dari stok (P1-K1)."""
    d = await _load(design_id)
    c = await _customer(customer_id, d.get("entity_id", ""))
    use = await usage(design_id)
    allow = sorted({x["customer_id"] for x in use["customers"] if x["customer_id"] and x["customer_id"] != c["id"]})
    await db.design_gallery.update_one({"id": design_id}, {
        "$set": {"ownership": "customer", "owner_customer_id": c["id"], "owner_customer_name": c.get("name", ""),
                 "ownership_source": source, "ownership_allow_customer_ids": allow, "updated_at": now_iso()},
        "$push": {"ownership_history": _hist("customer", actor, customer_id=c["id"], customer_name=c.get("name", ""),
                                             source=source, reason=reason, grandfathered=allow)}})
    await sync_products(design_id)
    return await db.design_gallery.find_one({"id": design_id}, {"_id": 0})


async def release_to_white(design_id: str, actor: Dict[str, Any], reason: str) -> Dict[str, Any]:
    if len((reason or "").strip()) < 5:
        raise OwnershipError("Alasan wajib diisi (minimal 5 huruf) — melepas kepemilikan pelanggan adalah keputusan bisnis.")
    d = await _load(design_id)
    if d.get("ownership") != "customer":
        raise OwnershipError("Desain ini sudah white label.")
    await db.design_gallery.update_one({"id": design_id}, {
        "$set": {"ownership": "white", "owner_customer_id": "", "owner_customer_name": "", "ownership_source": "",
                 "ownership_allow_customer_ids": [], "updated_at": now_iso()},
        "$push": {"ownership_history": _hist("white", actor, reason=reason.strip(),
                                             previous_customer=d.get("owner_customer_name", ""))}})
    await sync_products(design_id)
    return await db.design_gallery.find_one({"id": design_id}, {"_id": 0})


async def claim(design_id: str, customer_id: str, actor: Dict[str, Any], reason: str) -> Dict[str, Any]:
    """Pelanggan (lewat sales/Admin Sales) mengajukan klaim. Desain tetap white sampai diputus Manajer."""
    if len((reason or "").strip()) < 5:
        raise OwnershipError("Tulis alasan klaim (minimal 5 huruf) — dibaca Manajer saat memutus.")
    d = await _load(design_id)
    if d.get("ownership") == "customer":
        raise OwnershipError(f"Desain ini sudah customer label milik {d.get('owner_customer_name') or 'pelanggan lain'}.")
    c = await _customer(customer_id, d.get("entity_id", ""))
    if any(x.get("status") == "pending" for x in d.get("claims") or []):
        raise OwnershipError("Sudah ada klaim yang menunggu keputusan Manajer untuk desain ini.")
    cl = {"id": new_id("dclm"), "customer_id": c["id"], "customer_name": c.get("name", ""), "status": "pending",
          "reason": reason.strip(), "by": actor.get("name", ""), "by_id": actor.get("id", ""), "at": now_iso()}
    await db.design_gallery.update_one({"id": design_id}, {"$push": {"claims": cl}, "$set": {"updated_at": now_iso()}})
    try:
        from services import notification_service as notif
        await notif.create_notification(
            notif_type="design_claim_pending", title=f"Klaim desain {d.get('code', '')} menunggu keputusan",
            body=(f"{actor.get('name', '')} mengajukan klaim desain {d.get('code', '')} ({d.get('title', '')}) untuk "
                  f"pelanggan {c.get('name', '')}. Alasan: {reason.strip()}"),
            severity="info", link="design-gallery", entity_id=d.get("entity_id") or None,
            recipient_role="manager", ref=f"dclaim:{cl['id']}")
    except Exception:  # noqa: BLE001 — notifikasi tidak boleh menggagalkan klaim
        pass
    return await db.design_gallery.find_one({"id": design_id}, {"_id": 0})


async def decide_claim(design_id: str, claim_id: str, approve: bool, actor: Dict[str, Any],
                       reason: str = "") -> Dict[str, Any]:
    d = await _load(design_id)
    cl = next((x for x in d.get("claims") or [] if x.get("id") == claim_id), None)
    if not cl or cl.get("status") != "pending":
        raise OwnershipError("Klaim tidak ditemukan atau sudah diputus.")
    if cl.get("by_id") and cl["by_id"] == actor.get("id"):
        raise OwnershipError("Pengaju klaim tidak boleh memutus klaimnya sendiri.")
    if not approve and len((reason or "").strip()) < 5:
        raise OwnershipError("Menolak klaim wajib ber-alasan (minimal 5 huruf).")
    await db.design_gallery.update_one(
        {"id": design_id, "claims.id": claim_id},
        {"$set": {"claims.$.status": "approved" if approve else "rejected", "claims.$.decided_by": actor.get("name", ""),
                  "claims.$.decided_by_id": actor.get("id", ""), "claims.$.decided_at": now_iso(),
                  "claims.$.decision_reason": (reason or "").strip(), "updated_at": now_iso()}})
    if approve:
        await set_customer_owner(design_id, cl["customer_id"], "claim", actor, reason=reason or cl.get("reason", ""))
    try:
        from services import notification_service as notif
        await notif.create_notification(
            notif_type="design_claim_decided",
            title=f"Klaim desain {d.get('code', '')} {'DISETUJUI' if approve else 'DITOLAK'}",
            body=(f"Klaim {cl.get('customer_name', '')} atas desain {d.get('code', '')} "
                  f"{'disetujui — desain kini customer label' if approve else 'ditolak'} oleh {actor.get('name', '')}."
                  + (f" Alasan: {reason.strip()}" if (reason or "").strip() else "")),
            severity="info", link="design-gallery", entity_id=d.get("entity_id") or None,
            recipient_user=cl.get("by_id") or None, recipient_role="" if cl.get("by_id") else "manager",
            ref=f"dclaim-done:{claim_id}")
    except Exception:  # noqa: BLE001
        pass
    return await db.design_gallery.find_one({"id": design_id}, {"_id": 0})


async def on_special_order_design(design_id: str, special_order_id: str, actor: Dict[str, Any]) -> None:
    """P1.1/P1-K3 — desain dari pesanan khusus (OD sudah disetujui) otomatis customer label milik pemesannya."""
    if not design_id or not special_order_id:
        return
    od = await db.special_orders.find_one({"id": special_order_id}, {"_id": 0, "customer_id": 1, "status": 1})
    if not od or not od.get("customer_id") or od.get("status") in ("cancelled", "rejected", "draft"):
        return
    d = await db.design_gallery.find_one({"id": design_id}, {"_id": 0, "id": 1, "ownership": 1, "owner_customer_id": 1})
    if not d or (d.get("ownership") == "customer" and d.get("owner_customer_id") == od["customer_id"]):
        return
    try:
        await set_customer_owner(design_id, od["customer_id"], "special_order", actor,
                                 reason=f"Desain pesanan khusus {special_order_id}")
    except OwnershipError:
        pass
