# Iter193 setup: campaign + vendor bill (manager) and MKO return fixture (admin)
import os, sys, json, requests
from pymongo import MongoClient
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]


def login(email, pw="demo1234", ent="ent_ksc"):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ent}


def bill():
    h = login("manager@kainnusantara.id")
    c = requests.post(f"{BASE}/api/marketing/campaigns", json={"name": "TEST_RT", "budget": 1000000}, headers=h, timeout=30)
    print("campaign", c.status_code, c.text[:200]); cid = c.json()["id"]
    vo = requests.get(f"{BASE}/api/marketing/vendor-options", headers=h, timeout=30).json()
    sup = (vo.get("suppliers") if isinstance(vo, dict) else vo) or vo
    sid = sup[0]["id"]
    b = requests.post(f"{BASE}/api/marketing/campaigns/{cid}/vendor-bills",
                      json={"supplier_id": sid, "description": "Iklan", "amount": 100000}, headers=h, timeout=30)
    print("bill", b.status_code, b.text[:300])
    bid = b.json().get("id") or b.json().get("bill", {}).get("id")
    n = list(DB.notifications.find({"ref": {"$regex": "mkt_bill"}}, {"_id": 0, "id": 1, "ref": 1, "action_role": 1, "action_type": 1, "title": 1, "recipient_user": 1, "roles": 1}).sort("created_at", -1).limit(3))
    print(json.dumps({"cid": cid, "bid": bid, "notifs": n}, default=str))


def mko():
    sys.path.insert(0, os.path.dirname(__file__))
    import test_p05_acceptance_acc31_33_34 as t
    h = login("admin@kainnusantara.id", "demo12345")
    out = DB.products.find_one({"id": t._tpl()["steps"][0]["output_product_id"]}, {"_id": 0, "template_id": 1})
    DB.product_templates.update_one({"id": out["template_id"]}, {"$set": {"restock_source": {"mode": "makloon", "note": "TEST_P05ACC"}}})
    m = t._create(h, 60, "iter193 ui")
    r = requests.post(f"{BASE}/api/makloon-orders/{m['id']}/issue", json={"step_seq": 1, "doc_uom": "yard", "doc_qty": 60}, headers=h, timeout=60)
    print("issue", r.status_code, r.text[:200])
    r = requests.post(f"{BASE}/api/makloon-orders/{m['id']}/cancel", json={"reason": "TEST_P05ACC batal uji UI"}, headers=h, timeout=60)
    print("cancel", r.status_code, r.text[:200])
    pr = requests.get(f"{BASE}/api/makloon-orders/{m['id']}/steps/1/partner-rolls", headers=h, timeout=30).json()
    print(json.dumps({"mko": m["id"], "num": m.get("mko_number"), "rolls": [(x["id"], x.get("roll_no"), x.get("length_remaining")) for x in pr.get("rolls", [])]}))


if __name__ == "__main__":
    {"bill": bill, "mko": mko}[sys.argv[1]]()
