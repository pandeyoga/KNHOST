"""TEST seed: synthetic sample_cut tasks for Meja Cutting wait badge UI checks. --clear removes."""
import os, sys
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient

db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
if "--clear" in sys.argv:
    print(db.wms_tasks.delete_many({"_test_cutwait": True}).deleted_count,
          db.sales_orders.delete_many({"_test_cutwait": True}).deleted_count)
    sys.exit()
now = datetime.now(timezone.utc)
db.sales_orders.insert_one({"id": "so_TEST_cutwait", "number": "KSC/TEST_CUTWAIT", "entity_id": "ent_ksc", "_test_cutwait": True,
                            "items": [{"product_id": "prod_batik_mega", "is_sample": True, "sample_kind": "standard"}]})
roll = db.inventory_rolls.find_one({"owner_entity_id": "ent_ksc"}, {"_id": 0, "id": 1})
for i, mins in enumerate((300, 180, 30)):
    db.wms_tasks.insert_one({"id": f"task_TEST_cutwait_{i}", "task_subtype": "sample_cut", "entity_id": "ent_ksc",
                             "order_id": "so_TEST_cutwait", "order_number": "KSC/TEST_CUTWAIT", "customer_name": "TEST Butik",
                             "product_id": "prod_batik_mega", "product_name": "Batik Mega Mendung", "sku": "TEST",
                             "quantity": 1, "unit": "yard", "status": "in_progress", "warehouse_id": "wh_bandung",
                             "roll_id": roll["id"], "child_roll_no": f"TEST-C{i}", "parent_roll_no": "TEST-P",
                             "cut_at": (now - timedelta(minutes=mins)).isoformat(), "created_at": now.isoformat(),
                             "_test_cutwait": True})
print("seeded")
