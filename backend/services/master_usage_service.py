"""IMP-14 (P01) — jejak pemakaian master & kebijakan hapus.

Master yang sudah dipakai stok/transaksi tidak boleh dihapus (hanya nonaktif/arsip oleh
Admin atau MD — DEC-05). Master yang belum pernah dipakai boleh dihapus permanen.
"""
from typing import Any, Dict, List

from fastapi import HTTPException

from db import db
from role_registry import role_in  # peran acuan dikenali (keputusan owner 2026-10-21)

LIFECYCLE_ROLES = {"admin", "md"}

_PRODUCT_REFS = [
    ("inventory_rolls", {"product_id": "{id}"}, "Roll stok"),
    ("inventory_movements", {"product_id": "{id}"}, "Mutasi stok"),
    ("sales_orders", {"items.product_id": "{id}"}, "Pesanan penjualan"),
    ("purchase_orders", {"items.product_id": "{id}"}, "Purchase order"),
    ("purchase_requisitions", {"items.product_id": "{id}"}, "Permintaan pembelian"),
    ("goods_receipts", {"items.product_id": "{id}"}, "Penerimaan barang"),
    ("invoices", {"items.product_id": "{id}"}, "Faktur"),
    ("makloon_orders", {"$or": [{"items.product_id": "{id}"}, {"output_product_id": "{id}"}, {"input_product_id": "{id}"}]}, "Order makloon"),
    ("supplier_items", {"product_id": "{id}"}, "Barang supplier"),
    ("entity_prices", {"product_id": "{id}"}, "Harga per badan usaha"),
]
KINDS = {
    "product": ("products", _PRODUCT_REFS),
    "template": ("product_templates", [("products", {"template_id": "{id}"}, "SKU varian"),
                                       ("md_specs", {"template_id": "{id}"}, "Spesifikasi R&D")]),
    "color": ("color_library", [("products", {"$or": [{"color_id": "{id}"}, {"color_code": "{code}"}]}, "SKU bewarna ini"),
                                ("supplier_items", {"internal_color_code": "{code}"}, "Pemetaan warna supplier")]),
    "supplier_item": ("supplier_items", [("purchase_orders", {"items.supplier_item_id": "{id}"}, "Purchase order")]),
}


def _fill(q: Any, doc: Dict[str, Any]) -> Any:
    if isinstance(q, dict):
        return {k: _fill(v, doc) for k, v in q.items()}
    if isinstance(q, list):
        return [_fill(v, doc) for v in q]
    if isinstance(q, str) and q.startswith("{") and q.endswith("}"):
        return doc.get(q[1:-1]) or "__kosong__"
    return q


async def usage(kind: str, mid: str) -> Dict[str, Any]:
    if kind not in KINDS:
        raise HTTPException(status_code=400, detail=f"Jenis master tidak dikenal: {kind}")
    coll, refs = KINDS[kind]
    doc = await db[coll].find_one({"id": mid}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Master tidak ditemukan")
    rows: List[Dict[str, Any]] = []
    for ref_coll, q, label in refs:
        n = await db[ref_coll].count_documents(_fill(q, doc), limit=10000)
        if n:
            rows.append({"collection": ref_coll, "label": label, "count": n})
    if kind == "supplier_item" and int(doc.get("usage_count") or 0) and not rows:
        rows.append({"collection": "purchase_orders", "label": "Purchase order", "count": int(doc["usage_count"])})
    return {"kind": kind, "id": mid, "name": doc.get("name") or doc.get("supplier_sku") or doc.get("code") or mid,
            "status": doc.get("status", "active"), "in_use": bool(rows), "refs": rows,
            "can_delete": not rows,
            "policy": ("Dipakai stok/transaksi: tidak bisa dihapus, hanya dinonaktifkan/diarsipkan oleh Admin atau MD."
                       if rows else "Belum pernah dipakai: boleh dihapus permanen oleh Admin atau MD.")}


def assert_lifecycle_role(actor: Dict[str, Any], action: str = "menonaktifkan master") -> None:
    if not role_in((actor or {}).get("role"), LIFECYCLE_ROLES):
        raise HTTPException(status_code=403, detail=f"Hanya Admin atau MD yang boleh {action}.")


async def purge(kind: str, mid: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    assert_lifecycle_role(actor, "menghapus master")
    info = await usage(kind, mid)
    if info["in_use"]:
        refs = ", ".join(f"{r['label']} ({r['count']})" for r in info["refs"])
        raise HTTPException(status_code=409, detail={
            "code": "MASTER_IN_USE", "refs": info["refs"],
            "message": f"'{info['name']}' masih dipakai: {refs}. Hapus ditolak agar histori tetap utuh — nonaktifkan/arsipkan saja."})
    await db[KINDS[kind][0]].delete_one({"id": mid})
    return {"deleted": True, "kind": kind, "id": mid, "name": info["name"]}
