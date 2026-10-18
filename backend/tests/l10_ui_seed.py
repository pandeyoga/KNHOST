"""L10 T1 — seed/cleanup rolls for UI test of opname per roll (W11 Level 1). Usage: python tests/l10_ui_seed.py [--clear]"""
import sys
from pymongo import MongoClient

env = open("/app/backend/.env").read()
DB = MongoClient(env.split("MONGO_URL=")[1].split()[0].strip('"'))[env.split("DB_NAME=")[1].split()[0].strip('"')]
if "--clear" in sys.argv:
    ids = [r["id"] for r in DB.inventory_rolls.find({"id": {"$regex": "^roll_TEST_UI"}}, {"id": 1})]
    ss = [s["id"] for s in DB.cycle_count_sessions.find({"name": {"$regex": "^TEST_"}}, {"id": 1})]
    DB.inventory_movements.delete_many({"roll_id": {"$in": ids}})
    for s in ss:
        DB.journal_entries.delete_many({"source_id": {"$regex": s}})
    print("rolls", DB.inventory_rolls.delete_many({"id": {"$in": ids}}).deleted_count,
          "sessions", DB.cycle_count_sessions.delete_many({"id": {"$in": ss}}).deleted_count)
    sys.exit(0)
prod = DB.products.find_one({"fabric_type": "woven", "status": "active"}, {"_id": 0, "id": 1})
for i, b in enumerate(["bin_sim_wh_jkt_w11_l1_01", "bin_sim_wh_jkt_w11_l1_01", "bin_sim_wh_jkt_w11_l1_02"]):
    DB.inventory_rolls.update_one({"id": f"roll_TEST_UI_{i}"}, {"$set": {
        "id": f"roll_TEST_UI_{i}", "roll_no": f"TEST-UI-{i}", "product_id": prod["id"], "warehouse_id": "wh_jakarta",
        "owner_entity_id": "ent_ksc", "length_remaining": 50, "length_initial": 50, "unit": "yard", "status": "available",
        "bin_id": b, "bin_code": b[-8:], "grade": "A", "unit_cost": 10}}, upsert=True)
print("seeded")
