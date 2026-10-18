"""UI fixtures for L03 LN-030 (python tests/ui_fixtures_l03.py up|down)."""
import copy
import sys

from pymongo import MongoClient

DB = MongoClient("mongodb://localhost:27017")["test_database"]


def up():
    base = DB.design_gallery.find_one({"id": "dsgn_10afb8f116c2"}, {"_id": 0})
    for did, code, hold in (("dsgn_TEST_ui_ok", "TST-UI-OK", False), ("dsgn_TEST_ui_hold", "TST-UI-HOLD", True)):
        d = copy.deepcopy(base)
        d.update({"id": did, "code": code, "title": f"TEST_{code}", "status": "approved", "on_hold": hold,
                  "hold": {"reason": "TEST hold"} if hold else {}, "origin": ""})
        DB.design_gallery.replace_one({"id": did}, d, upsert=True)
    print("up")


def down():
    ods = [o["id"] for o in DB.special_orders.find({"$or": [{"title": {"$regex": "TEST_UI"}}, {"customer_name": {"$exists": True}, "items.source_design_id": {"$regex": "dsgn_TEST_ui"}}]}, {"id": 1})]
    specs = [s.get("spec_id") for s in DB.md_samples.find({"special_order_id": {"$in": ods}}, {"spec_id": 1})]
    DB.md_samples.delete_many({"special_order_id": {"$in": ods}})
    DB.md_specs.delete_many({"id": {"$in": specs}})
    DB.design_requests.delete_many({"special_order_id": {"$in": ods}})
    DB.special_orders.delete_many({"id": {"$in": ods}})
    DB.design_gallery.delete_many({"id": {"$regex": "^dsgn_TEST_"}})
    print("down", len(ods))


{"up": up, "down": down}[sys.argv[1]]()
