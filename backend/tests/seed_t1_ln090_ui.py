"""TEST seed (T1) — retur penggantian credit_settled 2 item: grade jual dari roll + produk kg tanpa faktor yard. --clear untuk hapus."""
import os
import sys
from pymongo import MongoClient

DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
RID, SO = "sr_TEST_T1UI_ln090", "so_TEST_T1UI_ln090"

if "--clear" in sys.argv:
    DB.sales_returns.delete_many({"id": RID})
    DB.sales_orders.delete_many({"id": SO})
    print("cleared")
    sys.exit(0)

src = DB.sales_orders.find_one({"number": "KSC/SO-00003"}, {"_id": 0})
roll = DB.inventory_rolls.find_one({"product_id": "prod_batik_mega", "owner_entity_id": "ent_ksc", "grade": "A"}, {"_id": 0, "id": 1})
DB.sales_returns.delete_many({"id": RID})
DB.sales_orders.delete_many({"id": SO})
DB.sales_orders.insert_one({**{k: src[k] for k in ("customer_id", "customer_name", "shipping_address_id", "entity_id")},
                            "id": SO, "number": "TEST_SO-T1UI", "status": "shipped", "payment_term_code": "NET30",
                            "items": [{"product_id": "prod_batik_mega", "quantity": 20, "base_quantity": 20, "line_total": 600000},
                                      {"product_id": "prod_3cb8c021e54c", "quantity": 10, "base_quantity": 10, "line_total": 500000}],
                            "grand_total": 1100000, "qc_request": {"mode": "none"}})
DB.sales_returns.insert_one({"id": RID, "number": "TEST_RET-T1UI", "order_id": SO, "order_number": "TEST_SO-T1UI", "entity_id": "ent_ksc",
                             "customer_id": src["customer_id"], "customer_name": src["customer_name"], "return_type": "penggantian",
                             "status": "credit_settled", "created_at": "2026-10-19T10:00:00+00:00", "updated_at": "2026-10-19T10:00:00+00:00",
                             "items": [{"product_id": "prod_batik_mega", "product_name": "TEST Batik Mega", "unit": "yard", "quantity_returned": 4,
                                        "roll_ids": [roll["id"]], "inspection": {"accepted_qty": 4, "grade": "B"}},
                                       {"product_id": "prod_3cb8c021e54c", "product_name": "TEST Audia kg", "unit": "kg", "quantity_returned": 3,
                                        "inspection": {"accepted_qty": 3, "grade": "A"}}]})
print("seeded", RID)
