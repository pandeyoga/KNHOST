"""Link a TEST design to the redesign OD's design request (UI fixture for design-detail-origin-ref)."""
import copy
import os

import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient("mongodb://localhost:27017")["test_database"]
tok = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}).json()["token"]
h = {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}
rd = DB.special_orders.find_one({"redesign_of.special_order_id": "sord_647ffe81a96d"})
print("redesign", rd["id"], rd["status"])
print("submit", requests.post(f"{BASE}/special-orders/{rd['id']}/submit", json={}, headers=h).status_code)
print("approve", requests.post(f"{BASE}/special-orders/{rd['id']}/approve", json={}, headers=h).status_code)
dr = DB.design_requests.find_one({"special_order_id": rd["id"]})
print("dr", dr["id"], dr["status"], dr.get("parent_design_code"))
uid = DB.users.find_one({"email": "designer@kainnusantara.id"})["id"]
if dr["status"] not in ("assigned", "in_progress", "revision"):
    print("assign", requests.post(f"{BASE}/design-requests/{dr['id']}/assign", json={"assigned_to": uid}, headers=h).status_code)
base = copy.deepcopy(DB.design_gallery.find_one({"id": "dsgn_10afb8f116c2"}, {"_id": 0}))
base.update({"id": "dsgn_TEST_ui_link", "code": "TST-UI-LNK", "title": "TEST_TST-UI-LNK", "status": "draft", "entity_id": "ent_ksc",
             "request_id": "", "request_number": "", "origin": "", "on_hold": False, "hold": {}})
DB.design_gallery.replace_one({"id": base["id"]}, base, upsert=True)
r = requests.post(f"{BASE}/design-requests/{dr['id']}/link-design", json={"gallery_id": "dsgn_TEST_ui_link"}, headers=h)
print("link", r.status_code)
g = DB.design_gallery.find_one({"id": "dsgn_TEST_ui_link"})
print("gallery origin", g.get("origin"), g.get("special_order_number"), g.get("parent_design_id"), g.get("parent_design_code"))
