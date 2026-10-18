"""DATA ACUAN P01 — penugasan lokasi akun demo, pembatasan lokasi aktif, contoh pemetaan supplier/warna.

Idempoten. Dijalankan sesudah seed_simulasi_bin_kn.py (lihat deploy/setup_demo_lengkap.sh).
  python scripts/seed_p01_kn.py
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from db import db  # noqa: E402
from core_utils import now_iso  # noqa: E402
from services import supplier_item_service as sis  # noqa: E402
from services.config_resolver import set_value, value_of  # noqa: E402

BATCH = "P01_DATA_ACUAN"
ASSIGN = {"warehouse@kainnusantara.id": "Jakarta", "warehouse.soreang@kainnusantara.id": "Soreang",
          "warehouse.rancamalang@kainnusantara.id": "Rancamalang"}


async def assign_locations() -> int:
    sites = {s["name"]: s["id"] async for s in db.warehouse_sites.find({}, {"_id": 0, "id": 1, "name": 1})}
    n = 0
    for email, site in ASSIGN.items():
        if site in sites:
            r = await db.users.update_one({"email": email, "$or": [{"location_site_ids": {"$exists": False}},
                                                                     {"location_site_ids": {"$size": 0}, "location_warehouse_ids": {"$in": [[], None]}}]},
                                          {"$set": {"location_site_ids": [sites[site]], "location_warehouse_ids": [],
                                                    "updated_at": now_iso()}})
            n += r.modified_count
    return n


async def enable_scope() -> bool:
    if await value_of("wms.location_scope_enforced"):
        return False
    await set_value("wms.location_scope_enforced", True, scope_type="global", actor="Data acuan P01",
                    reason="Data acuan P01: akun demo gudang sudah dipetakan ke site")
    return True


async def supplier_mappings() -> dict:
    if await db.supplier_items.count_documents({"demo_batch": BATCH}):
        return {"skipped": True}
    sups = await db.suppliers.find({}, {"_id": 0, "id": 1, "name": 1}).sort("name", 1).to_list(2)
    prods = await db.products.find({"stage": "finished", "color_code": {"$nin": ["", None]}, "status": "active"},
                                   {"_id": 0, "id": 1, "sku": 1, "color_code": 1}).sort("sku", 1).to_list(2)
    if len(sups) < 2 or len(prods) < 2:
        return {"skipped": "supplier/produk kurang"}
    a, b = sups
    p1, p2 = prods
    rows = [(a, p1, "SUP-A-001", "WRN-77", p1["color_code"]), (b, p1, "SUP-B-9001", "B-COL-12", p1["color_code"]),
            (a, p2, "SUP-A-002", "WRN-77", p2["color_code"])]
    out = []
    for sup, prod, ssku, scode, icode in rows:
        doc = await sis.create_item({"supplier_id": sup["id"], "product_id": prod["id"], "supplier_sku": ssku,
                                     "supplier_item_name": f"Kain versi {sup['name']}", "supplier_color": scode,
                                     "supplier_color_code": scode, "internal_color_code": icode},
                                    entity_id="ent_ksc", actor="Data acuan P01")
        await db.supplier_items.update_one({"id": doc["id"]}, {"$set": {"demo_batch": BATCH}})
        out.append((ssku, doc["review_status"]))
    return {"created": out}


async def main() -> None:
    print("Akun dipetakan:", await assign_locations())
    print("Pembatasan lokasi dinyalakan:", await enable_scope())
    print("Pemetaan supplier/warna:", await supplier_mappings())


if __name__ == "__main__":
    asyncio.run(main())
