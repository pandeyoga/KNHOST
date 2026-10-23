"""UAT 24 Okt — data fase F0 (ANALISIS_TEMUAN_UAT_23OKT.md P14, keputusan pemilik 24 Okt). Idempoten.

1. Pelanggan KSC tanpa sales (Toko Kain Sejahtera, Butik Bali Indah, Moda Surabaya Fashion) → milik Bima
   Saputra (sales2) — keputusan pemilik P14-K1.
2. Satu "Pelanggan Umum (Walk-in)" per PT (`shared_walk_in`) yang boleh dipakai semua sales PT itu (P14-K2).
3. SO TERBUKA milik pelanggan pada butir 1 yang belum punya sales (dibuat admin "atas nama") mewarisi tim sales
   pelanggan, supaya muncul di "Pesanan Saya" / Keep & Pending sales pemiliknya (P13).

Pemakaian (di container backend): DB_NAME=<db> python scripts/uat24_f0_data.py [--dry-run]
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core_utils import new_id, next_doc_number, now_iso  # noqa: E402
from db import db  # noqa: E402

DRY = "--dry-run" in sys.argv
OWNER_EMAIL = "sales2@kainnusantara.id"
CUSTOMERS = ["Toko Kain Sejahtera", "Butik Bali Indah", "Moda Surabaya Fashion"]
CLOSED_SO = ["done", "completed", "cancelled", "closed"]


async def main() -> None:
    print("DB:", os.environ.get("DB_NAME"), "(dry-run)" if DRY else "")
    owner = await db.users.find_one({"email": OWNER_EMAIL}, {"_id": 0, "id": 1, "name": 1})
    if not owner:
        raise SystemExit(f"Akun {OWNER_EMAIL} tidak ada")
    team = [{"sales_id": owner["id"], "name": owner["name"], "role": "pic", "split_pct": 100.0}]
    # 1 — pelanggan → Bima (hanya yang belum punya sales; tidak menimpa pemilik yang sudah ada)
    custs = await db.customers.find({"name": {"$in": CUSTOMERS}}, {"_id": 0}).to_list(20)
    for c in custs:
        if c.get("assigned_sales_id") and c.get("assigned_sales_id") != owner["id"]:
            print(f"  lewati {c['name']}: sudah milik {c.get('assigned_sales_name') or c['assigned_sales_id']}")
            continue
        print(f"  {c['name']} ({c.get('entity_id')}) → {owner['name']}")
        if not DRY:
            await db.customers.update_one({"id": c["id"]}, {"$set": {
                "assigned_sales_id": owner["id"], "assigned_sales_name": owner["name"], "sales_pic": owner["name"],
                "sales_team": team, "updated_at": now_iso()}})
    # 3 — SO terbuka pelanggan tsb tanpa sales → mewarisi tim pelanggan
    ids = [c["id"] for c in custs]
    q = {"customer_id": {"$in": ids}, "status": {"$nin": CLOSED_SO},
         "$and": [{"$or": [{"sales_id": {"$in": [None, ""]}}, {"sales_id": {"$exists": False}}]},
                  {"$or": [{"sales_team": {"$exists": False}}, {"sales_team": {"$size": 0}}]}]}
    async for so in db.sales_orders.find(q, {"_id": 0, "id": 1, "number": 1, "customer_name": 1, "status": 1}):
        print(f"  SO {so['number']} ({so['customer_name']}, {so['status']}) → tim sales {owner['name']}")
        if not DRY:
            await db.sales_orders.update_one({"id": so["id"]}, {"$set": {
                "sales_team": team, "sales_id": owner["id"], "sales_name": owner["name"], "updated_at": now_iso()}})
    # 2 — walk-in per PT
    async for ent in db.business_entities.find({}, {"_id": 0, "id": 1, "name": 1, "doc_prefix": 1, "city": 1}):
        if await db.customers.find_one({"entity_id": ent["id"], "shared_walk_in": True}, {"_id": 0, "id": 1}):
            print(f"  walk-in {ent.get('doc_prefix')}: sudah ada")
            continue
        print(f"  walk-in {ent.get('doc_prefix')}: dibuat")
        if DRY:
            continue
        code = await next_doc_number("customers", "code", "CUST-", width=4)
        city = ent.get("city") or ""
        await db.customers.insert_one({
            "id": new_id("cust"), "code": code, "name": "Pelanggan Umum (Walk-in)", "pic_name": "", "phone": "",
            "email": "", "type": "Walk-in", "segment": "Umum", "city": city, "country": "Indonesia", "country_code": "ID",
            "npwp": "", "credit_limit": 0, "entity_id": ent["id"], "status": "active", "shared_walk_in": True,
            "assigned_sales_id": "", "assigned_sales_name": "", "sales_team": [], "tags": ["walk-in"], "contacts": [],
            "payment_profile": {"allowed_methods": ["tunai"], "default_method": "tunai", "term_days": 0, "dp_percent": 0,
                                "installment_count": 0, "installment_interval_days": 30},
            "addresses": [{"id": new_id("addr"), "label": "Ambil di toko / gudang", "recipient_name": "Pelanggan umum",
                           "phone": "", "city": city, "address": "Diambil langsung (walk-in)", "is_primary": True,
                           "country": "Indonesia", "country_code": "ID"}],
            "allocation_policy": {}, "lot_policy": "", "enforce_single_dye_lot": False,
            "created_by": "uat24_f0_data", "created_at": now_iso(), "updated_at": now_iso()})
    print("selesai")


if __name__ == "__main__":
    asyncio.run(main())
