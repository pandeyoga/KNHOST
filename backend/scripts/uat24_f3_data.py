"""UAT 24 Okt — data fase F3 (P1 kepemilikan desain, P6 tag desain di produk). Idempoten.

* P1.1 — desain asal pesanan khusus (OD sudah disetujui) → customer label milik pemesan (P1-K3). Desain lain tetap
  white label (bawaan, tidak perlu ditulis).
* P1.2 — rantai desain → SKU diisi dari jejak yang SUDAH ada: `md_specs.design_id` + `product_id`, item OD
  `source_design_id` + `product_id`, dan produk eksklusif OD yang desainnya lahir dari permintaan OD itu.
* P6.2 — kandidat pencocokan produk ↔ desain lewat nama/motif HANYA dilaporkan (ditinjau MD), tidak ditautkan.
* Indeks `products.design_id`.

Pemakaian (di container backend): DB_NAME=<db> python scripts/uat24_f3_data.py [--dry-run]
"""
import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import db  # noqa: E402
from services import design_ownership_service as own  # noqa: E402

DRY = "--dry-run" in sys.argv
ACTOR = {"id": "", "name": "Migrasi UAT 24 Okt (F3)"}
LIVE_OD = {"$nin": ["draft", "cancelled", "rejected", "pending_approval"]}


async def main() -> None:
    print("DB:", os.environ.get("DB_NAME"), "(dry-run)" if DRY else "")
    # 1 — desain OD → customer label
    async for d in db.design_gallery.find({"origin": "special_order", "special_order_id": {"$nin": [None, ""]}},
                                          {"_id": 0, "id": 1, "code": 1, "special_order_id": 1, "ownership": 1}):
        od = await db.special_orders.find_one({"id": d["special_order_id"], "status": LIVE_OD},
                                              {"_id": 0, "number": 1, "customer_name": 1})
        if not od:
            print(f"  desain {d['code']}: OD belum disetujui / batal — tetap white label")
            continue
        if d.get("ownership") == "customer":
            print(f"  desain {d['code']}: sudah customer label")
            continue
        print(f"  desain {d['code']}: customer label → {od.get('customer_name')} ({od.get('number')})")
        if not DRY:
            await own.on_special_order_design(d["id"], d["special_order_id"], ACTOR)
    # 2 — rantai desain → SKU dari jejak yang sudah ada
    links = {}
    async for sp in db.md_specs.find({"design_id": {"$nin": [None, ""]}, "product_id": {"$nin": [None, ""]}},
                                     {"_id": 0, "design_id": 1, "product_id": 1}):
        links.setdefault(sp["design_id"], set()).add(sp["product_id"])
    async for od in db.special_orders.find({}, {"_id": 0, "id": 1, "items": 1, "linked_product_id": 1, "pricing": 1}):
        for it in od.get("items") or []:
            if it.get("source_design_id") and it.get("product_id"):
                links.setdefault(it["source_design_id"], set()).add(it["product_id"])
        designs = [d["id"] async for d in db.design_gallery.find({"special_order_id": od["id"]}, {"_id": 0, "id": 1})]
        pids = {p for p in [od.get("linked_product_id"), (od.get("pricing") or {}).get("product_id")] if p}
        pids |= {p["id"] async for p in db.products.find({"special_order_id": od["id"]}, {"_id": 0, "id": 1})}
        if len(designs) == 1 and pids:
            links.setdefault(designs[0], set()).update(pids)
    for did, pids in links.items():
        have = {p["id"] async for p in db.products.find({"id": {"$in": list(pids)}, "design_id": did}, {"_id": 0, "id": 1})}
        todo = sorted(set(pids) - have)
        code = ((await db.design_gallery.find_one({"id": did}, {"_id": 0, "code": 1})) or {}).get("code", did)
        print(f"  desain {code}: {len(todo)} SKU ditautkan ({len(have)} sudah)")
        if todo and not DRY:
            await own.link_products(did, todo)
        elif not DRY:
            await own.sync_products(did)
    # 3 — kandidat pencocokan (laporan saja)
    cands = 0
    async for d in db.design_gallery.find({"status": {"$in": ["approved", "final_submitted", "active"]}},
                                          {"_id": 0, "id": 1, "code": 1, "title": 1}):
        keys = [k for k in [d.get("code"), d.get("title")] if k and len(k) >= 4]
        if not keys:
            continue
        rx = "|".join(re.escape(k) for k in keys)
        async for p in db.products.find({"design_id": {"$in": [None, ""]},
                                          "$or": [{"name": {"$regex": rx, "$options": "i"}},
                                                  {"motif": {"$regex": rx, "$options": "i"}}]},
                                         {"_id": 0, "sku": 1, "name": 1}).limit(20):
            cands += 1
            print(f"  KANDIDAT (tinjau MD): {p['sku']} {p['name']} ↔ desain {d['code']}")
    print(f"  kandidat pencocokan untuk ditinjau: {cands}")
    if not DRY:
        await db.products.create_index([("design_id", 1)])
        await db.design_gallery.create_index([("ownership", 1), ("owner_customer_id", 1)])
        print("  indeks dibuat")


if __name__ == "__main__":
    asyncio.run(main())
