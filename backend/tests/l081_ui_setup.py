# L08 LN-081 UI test helper: `setup` creates TEST_L081_UI return, `cleanup` removes it and restores rolls
import json, os, sys
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
TAG = "TEST_L081_UI"
SNAP = "/tmp/l081_ui_snapshot.json"


def hdr():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def setup():
    h = hdr()
    so = DB.sales_orders.find_one({"number": "KSC/SO-00001"})
    before = {r["id"]: r for r in DB.inventory_rolls.find({"status": "delivered"}, {"_id": 0})}
    json.dump(before, open(SNAP, "w"), default=str)
    data = requests.get(f"{BASE}/sales-returns/returnable", headers=h, params={"order_id": so["id"]}).json()
    roll = [r for r in data["rolls"] if r["remaining"] >= r["shipped_qty"] - 0.01][0]
    r = requests.post(f"{BASE}/sales-returns", headers=h, json={
        "order_id": so["id"], "return_type": "retur", "notes": TAG, "submit_now": True,
        "items": [{"product_id": roll["product_id"], "quantity_returned": roll["remaining"], "unit": roll["unit"],
                   "roll_ids": [roll["roll_id"]], "roll_qtys": {roll["roll_id"]: roll["remaining"]}, "reason": "cacat"}]})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    a = requests.post(f"{BASE}/sales-returns/{rid}/approve", headers=h, json={"notes": ""})
    print(json.dumps({"return_id": rid, "number": r.json().get("number"), "approve": a.status_code,
                      "roll_id": roll["roll_id"], "roll_no": roll["roll_no"], "unit": roll["unit"]}))


def cleanup():
    ids = [d["id"] for d in DB.sales_returns.find({"notes": TAG}, {"id": 1})]
    DB.inventory_rolls.delete_many({"return_id": {"$in": ids}, "returned_identity": {"$ne": True}})
    if os.path.exists(SNAP):
        before = json.load(open(SNAP))
        for rid, doc in before.items():
            cur = DB.inventory_rolls.find_one({"id": rid}, {"return_history": 1, "status": 1})
            if cur and (cur.get("status") != "delivered" or any(x.get("return_id") in ids for x in cur.get("return_history") or [])):
                DB.inventory_rolls.replace_one({"id": rid}, doc)
    for coll in ("credit_notes", "journal_entries", "cash_transactions", "inventory_movements"):
        DB[coll].delete_many({"$or": [{"return_id": {"$in": ids}}, {"ref_id": {"$in": ids}}, {"source_id": {"$in": ids}}]})
    n = DB.sales_returns.delete_many({"notes": TAG}).deleted_count
    print(f"cleaned {n} returns {ids}")


if __name__ == "__main__":
    {"setup": setup, "cleanup": cleanup}[sys.argv[1]]()
