"""Tautan Pesanan Khusus (OD) ↔ SKU hasil R&D: SKU yang lahir dari OD otomatis jadi katalog eksklusif pelanggan."""
from typing import Any, Dict, Optional

from core_utils import now_iso
from db import db


async def resolve_product_id(od: Dict[str, Any]) -> str:
    """Cari SKU hasil OD: tautan langsung → harga terkunci → spesifikasi → produk bertanda OD → keputusan sample."""
    pid = od.get("linked_product_id") or (od.get("pricing") or {}).get("product_id") or ""
    if pid:
        return pid
    spec_ids = [s for s in [od.get("spec_id")] if s]
    async for sp in db.md_specs.find({"$or": [{"special_order_id": od["id"]}, {"id": {"$in": spec_ids}}],
                                      "product_id": {"$nin": ["", None]}}, {"_id": 0, "product_id": 1}):
        return sp["product_id"]
    p = await db.products.find_one({"special_order_id": od["id"]}, {"_id": 0, "id": 1})
    if p:
        return p["id"]
    async for s in db.md_samples.find({"$or": [{"special_order_id": od["id"]}, {"id": {"$in": od.get("sample_ids") or []}}],
                                       "decision.product_id": {"$nin": ["", None]}}, {"_id": 0, "decision.product_id": 1}):
        return s["decision"]["product_id"]
    return ""


async def ensure_exclusive(product_id: str, od: Dict[str, Any]) -> None:
    """Tandai SKU sebagai katalog eksklusif pelanggan pemesan + tautkan balik ke OD."""
    if not (product_id and od):
        return
    await db.products.update_one({"id": product_id}, {"$set": {
        "exclusive_customer_id": od.get("customer_id", ""), "exclusive_customer_name": od.get("customer_name", ""),
        "special_order_id": od["id"], "special_order_number": od.get("number", ""), "catalog_scope": "customer",
        "updated_at": now_iso()}})
    if not od.get("linked_product_id"):
        sku = ((await db.products.find_one({"id": product_id}, {"_id": 0, "sku": 1})) or {}).get("sku", "")
        await db.special_orders.update_one({"id": od["id"]}, {"$set": {"linked_product_id": product_id, "linked_product_sku": sku}})


async def link_for_spec(spec_id: str, product_id: str) -> None:
    """Dipanggil saat spesifikasi R&D di-ACC: bila spesifikasi berasal dari OD, SKU langsung eksklusif pelanggan."""
    od = await db.special_orders.find_one({"spec_id": spec_id}, {"_id": 0})
    if not od:
        sp = await db.md_specs.find_one({"id": spec_id}, {"_id": 0, "special_order_id": 1})
        if (sp or {}).get("special_order_id"):
            od = await db.special_orders.find_one({"id": sp["special_order_id"]}, {"_id": 0})
    if od:
        await ensure_exclusive(product_id, od)


async def repair_pr_lines(pr: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """PR dari OD yang dibuat sebelum SKU lahir → baris tanpa produk. Isi produknya sekarang (idempoten)."""
    if pr.get("source") != "special_order" or not pr.get("source_ref_id"):
        return None
    if all(it.get("product_id") for it in pr.get("items") or []):
        return None
    od = await db.special_orders.find_one({"id": pr["source_ref_id"]}, {"_id": 0})
    pid = await resolve_product_id(od) if od else ""
    if not pid:
        return None
    prod = await db.products.find_one({"id": pid}, {"_id": 0}) or {}
    items = pr.get("items") or []
    for it in items:
        if not it.get("product_id"):
            it.update({"product_id": pid, "sku": prod.get("sku", ""), "product_name": prod.get("name", ""),
                       "base_unit": prod.get("base_unit", it.get("unit", ""))})
    await db.purchase_requisitions.update_one({"id": pr["id"]}, {"$set": {"items": items, "updated_at": now_iso()}})
    await ensure_exclusive(pid, od)
    if prod.get("lifecycle") not in (None, "", "produksi"):
        released = False
        if prod.get("spec_id"):
            from services import rnd_spec_service as spec_svc
            try:
                await spec_svc.release_product(prod["spec_id"], {"name": "Sistem (OD)", "role": "admin"},
                                               note=f"Otomatis — PR {pr.get('number')} direalisasi")
                released = True
            except Exception:  # noqa: BLE001
                released = False
        if not released:
            await db.products.update_one({"id": pid}, {"$set": {"lifecycle": "produksi", "updated_at": now_iso()}})
    return {**pr, "items": items}
