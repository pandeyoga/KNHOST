"""T1 helper: create TEST_ campaign + pending bill as manager (prints ids). --clean removes TEST_UI_ data."""
import os, sys, requests
from pymongo import MongoClient
B = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def h(e, pw="demo12345"):
    t = requests.post(f"{B}/auth/login", json={"email": e, "password": pw}).json()["token"]
    return {"Authorization": f"Bearer {t}", "X-Entity-Id": "ent_ksc"}


if "--clean" in sys.argv:
    cids = [c["id"] for c in DB.mkt_campaigns.find({"name": {"$regex": "^TEST_UI"}})]
    bills = [b["id"] for b in DB.vendor_bills.find({"campaign_id": {"$in": cids}})]
    DB.journal_entries.delete_many({"source_id": {"$in": bills}})
    DB.vendor_bills.delete_many({"id": {"$in": bills}})
    DB.notifications.delete_many({"ref": {"$in": [f"mkt_bill:{b}" for b in bills]}})
    DB.mkt_campaign_costs.delete_many({"campaign_id": {"$in": cids}}) if "mkt_campaign_costs" in DB.list_collection_names() else None
    for coll in DB.list_collection_names():
        if coll.startswith("mkt_") and coll != "mkt_campaigns":
            DB[coll].delete_many({"campaign_id": {"$in": cids}})
    DB.mkt_campaigns.delete_many({"id": {"$in": cids}})
    print("cleaned", len(cids), len(bills))
else:
    m = h("manager@kainnusantara.id")
    c = requests.post(f"{B}/marketing/campaigns", json={"name": "TEST_UI_NOTIF", "budget": 2000000,
                                                         "start_date": "2026-10-01", "end_date": "2026-11-30"}, headers=m).json()
    sup = requests.get(f"{B}/marketing/vendor-options", headers=m).json()[0]["id"]
    b = requests.post(f"{B}/marketing/campaigns/{c['id']}/vendor-bills", headers=m, json={
        "supplier_id": sup, "description": "TEST_UI Iklan IG", "amount": 500000, "bill_date": "2026-10-05"}).json()
    n = DB.notifications.find_one({"ref": f"mkt_bill:{b['id']}"}, {"_id": 0, "id": 1})
    print("CAMPAIGN", c["id"], "BILL", b["id"], b["bill_number"], "NOTIF", n["id"])
