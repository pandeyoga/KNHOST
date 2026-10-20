"""Helper: create TEST_ SO for L022 UI retest (print id/number/products). Use --clean <id> to cancel+delete."""
import os, sys, requests
from pymongo import MongoClient
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
_e = os.environ.get("SEED_EMAIL", "admin@kainnusantara.id")
tok = requests.post(f"{BASE}/auth/login", json={"email": _e, "password": "demo12345" if _e.startswith("admin@") else "demo12345"}).json()["token"]
H = {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}
if len(sys.argv) > 2 and sys.argv[1] == "--clean":
    for sid in sys.argv[2:]:
        print(requests.post(f"{BASE}/sales-orders/{sid}/cancel", headers=H, json={"reason": "TEST_T1 cleanup"}).status_code)
        DB.price_approvals.delete_many({"so_id": sid}); DB.sales_orders.delete_many({"id": sid})
    sys.exit()
P = [r["_id"] for r in DB.inventory_rolls.aggregate([
    {"$match": {"status": "available", "owner_entity_id": "ent_ksc", "unit": "yard"}},
    {"$group": {"_id": "$product_id", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 2}])]
ADDR = DB.customers.find_one({"id": "cust_butik_bali"})["addresses"][0]["id"]
r = requests.post(f"{BASE}/sales-orders", headers=H, json={
    "customer_id": "cust_butik_bali", "shipping_address_id": ADDR, "entity_id": "ent_ksc", "notes": "TEST_T1_UI_L022",
    "confirm_mixed_lot": True, "allow_backorder": True,
    "items": [{"product_id": p, "quantity": 15, "unit": "yard"} for p in P]})
so = r.json()
print(so["id"], so["number"], so["status"], [(i["product_id"], i["product_name"], i["price"], i.get("price_source")) for i in so["items"]])
