"""Seed/cleanup UI data for L09 LN-093 (testing agent). usage: python seed_l09_ui.py [--clear]"""
import os
import sys
import uuid
from pymongo import MongoClient

DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
TAG = "TEST_L093UI"
if "--clear" in sys.argv:
    ids = [d["id"] for d in DB.sales_returns.find({"notes": TAG}, {"id": 1})]
    prs = [p["id"] for p in DB.purchase_returns.find({"origin_sales_return_id": {"$in": ids}}, {"id": 1})]
    DB.purchase_returns.delete_many({"id": {"$in": prs}})
    for c in ("doc_refs", "document_refs"):
        DB[c].delete_many({"$or": [{"from_id": {"$in": prs + ids}}, {"to_id": {"$in": prs + ids}}]})
    DB.inventory_rolls.delete_many({"notes": TAG})
    DB.sales_returns.delete_many({"notes": TAG})
    DB.atomic_claims.delete_many({"doc_id": {"$in": ids}})
    print("cleared", len(ids), len(prs))
    sys.exit(0)
A = DB.purchase_orders.find_one({"po_number": "KSC/PO-00001"})
B = DB.purchase_orders.find_one({"po_number": "CST/PO-00001"})
T = DB.inventory_rolls.find_one({"owner_entity_id": "ent_ksc", "status": "available", "warehouse_id": "wh_jakarta"})
so = DB.sales_orders.find_one({"entity_id": "ent_ksc"}) or {}
rid = f"sret_{TAG}_{uuid.uuid4().hex[:6]}"
num = f"{TAG}-{rid[-6:]}"
DB.sales_returns.insert_one({"id": rid, "number": num, "notes": TAG, "entity_id": "ent_ksc",
                             "order_id": so.get("id", ""), "order_number": so.get("order_number", ""),
                             "customer_name": "TEST Pelanggan", "return_type": "retur",
                             "status": "refund_settled", "items": [], "created_at": "2026-10-17T00:00:00+00:00"})
for i, prov in enumerate([{"supplier_id": A["supplier_id"], "po_id": A["id"], "po_number": A["po_number"]},
                          {"supplier_id": B["supplier_id"], "po_id": B["id"], "po_number": B["po_number"]}, {}]):
    d = {k: v for k, v in T.items() if k not in ("_id", "supplier_id", "po_id", "po_number", "supplier_name",
                                                  "acquired", "acquired_history")}
    d.update({"id": f"roll_{TAG}_{uuid.uuid4().hex[:8]}", "roll_no": f"{TAG}-{rid[-6:]}-{i}", "status": "quarantine",
              "origin_type": "return", "return_id": rid, "notes": TAG, "length_remaining": 10.0,
              "length_initial": 10.0, "length_reserved": 0, "rfid_tag": "", "tag_id": ""}, **prov)
    DB.inventory_rolls.insert_one(d)
print(rid, num)
