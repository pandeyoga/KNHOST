"""TEST seed: logistics deliveries (one with SO qc_request, one without) for mobile QC badge check. --clear removes."""
import os, sys
from datetime import datetime, timezone
from pymongo import MongoClient

db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
if "--clear" in sys.argv:
    print(db.logistics_deliveries.delete_many({"_test_qcbadge": True}).deleted_count,
          db.sales_orders.delete_many({"_test_qcbadge": True}).deleted_count)
    sys.exit()
now = datetime.now(timezone.utc).isoformat()
for oid, qc in (("so_TEST_qc_a", {"mode": "full", "status": "required"}), ("so_TEST_qc_b", None)):
    db.sales_orders.insert_one({"id": oid, "number": f"KSC/{oid.upper()}", "entity_id": "ent_ksc", "_test_qcbadge": True,
                                "items": [], **({"qc_request": qc} if qc else {})})
for i, oid in enumerate(("so_TEST_qc_a", "so_TEST_qc_b")):
    db.logistics_deliveries.insert_one({"id": f"dlv_TEST_qc_{i}", "number": f"KSC/TEST_DLV-0{i}", "entity_id": "ent_ksc",
                                        "order_id": oid, "order_number": f"KSC/{oid.upper()}", "customer_name": "TEST Butik Bali",
                                        "mode": "expedition", "courier_name": "JNE", "status": "prepared", "eta": "2099-01-01",
                                        "shipment_nos": [], "positions": [], "photos": [], "created_at": now, "_test_qcbadge": True})
print("seeded")
