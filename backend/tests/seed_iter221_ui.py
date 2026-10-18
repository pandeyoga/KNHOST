"""Seed/cleanup UI iter221: OD printing dengan 2 ronde proofing (R2 terbuka) + desain 2 ronde (paper 1/2).
python tests/seed_iter221_ui.py [--clear]"""
import copy
import os
import sys

import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ENT = "ent_ksc"
D_OD, D_CARD = "dsgn_TEST_ui221od", "dsgn_TEST_ui221card"

if "--clear" in sys.argv:
    ods = [o["id"] for o in DB.special_orders.find({"title": "TEST_UI221_PRINT"}, {"id": 1})]
    DB.md_samples.delete_many({"special_order_id": {"$in": ods}})
    DB.special_orders.delete_many({"id": {"$in": ods}})
    DB.design_requests.delete_many({"special_order_id": {"$in": ods}})
    DB.design_gallery.delete_many({"id": {"$in": [D_OD, D_CARD]}})
    print("cleared", ods)
    sys.exit(0)

H = {"Authorization": "Bearer " + requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}).json()["token"], "X-Entity-Id": ENT}
tpl = DB.product_templates.find_one({"status": "active"}, {"id": 1}, sort=[("name", 1)])["id"]
r = requests.post(f"{BASE}/special-orders", headers=H, json={"customer_id": "cust_toko_kain", "title": "TEST_UI221_PRINT", "entity_id": ENT,
    "expected_delivery": "2026-12-31", "submit_for_approval": True,
    "items": [{"source_type": "parent_product", "source_template_id": tpl, "description": "TEST UI221", "request_types": ["printing"], "quantity": 20}]})
od_id = r.json()["id"]
requests.post(f"{BASE}/special-orders/{od_id}/approve", json={"notes": "TEST"}, headers=H)
od = DB.special_orders.find_one({"id": od_id})
dr = od["items"][0].get("design_request_id") or od.get("design_request_id")
src = copy.deepcopy(DB.design_gallery.find_one({"entity_id": ENT, "id": {"$not": {"$regex": "^dsgn_TEST_"}}}, {"_id": 0}))
base = dict(src)
src.update({"id": D_OD, "code": "TUI221-OD", "title": "TEST_UI221 OD", "status": "in_review", "request_id": dr, "origin": "",
            "on_hold": False, "hold": {}, "version": 2, "versions": [{"version": 1}, {"version": 2}], "timeline": []})
DB.design_gallery.insert_one(src)
DB.design_requests.update_one({"id": dr}, {"$set": {"design_id": D_OD}})
if not od.get("design_request_id"):
    DB.special_orders.update_one({"id": od_id}, {"$set": {"design_request_id": dr}})
print("approve", requests.post(f"{BASE}/design-gallery/{D_OD}/lifecycle/approve", json={"score": 1.75, "note": "ACC"}, headers=H).status_code)
DB.md_samples.update_many({"special_order_id": od_id}, {"$set": {"status": "decided"}})
print("revisi", requests.post(f"{BASE}/special-orders/{od_id}/customer-decision", headers=H,
                              json={"decision": "revisi", "note": "warna kurang tajam", "decided_at": "2026-10-18"}).status_code)
card = dict(base)
card.update({"id": D_CARD, "code": "TUI221-CARD", "title": "TEST_UI221 CARD", "status": "draft", "request_id": "", "origin": "",
             "on_hold": False, "hold": {}, "version": 2, "versions": [{"version": 1}, {"version": 2}], "timeline": [],
             "round_paper_history": {}, "created_by": "Admin"})
DB.design_gallery.insert_one(card)
print("paper", requests.post(f"{BASE}/design-gallery/{D_CARD}/rounds/1/paper", json={"checked": True}, headers=H).status_code)
print("OD", od_id, od.get("number"))
