P = "prod_c854e5856251"   # woven yard, stok Jakarta
sales = Api("sales@kainnusantara.id"); sa = Api("sampleadmin@kainnusantara.id"); wh = Api("warehouse@kainnusantara.id"); fin = Api("finance@kainnusantara.id"); whadm = Api("wh.admin@kainnusantara.id")
base = {"customer_id": "cust_toko_kain", "shipping_address_id": "", "entity_id": "ent_ksc", "order_type": "sample"}
c, b = sales.post("/sales-orders", {**base, "sample_billing": "free", "items": [{"product_id": P, "quantity": 6, "unit": "yard", "sample_kind": "standard"}]})
step("NEG sample standar woven 6 yd (>5) ditolak", c, b, (400,))
c, b = sales.post("/sales-orders", {**base, "items": [{"product_id": P, "quantity": 5, "unit": "yard"}]})
step("NEG sample tanpa pilih gratis/berbayar", c, b, (400,))
c, b = sales.post("/sales-orders", {**base, "order_type": "regular", "items": [{"product_id": P, "quantity": 5, "unit": "yard", "is_sample": True}, {"product_id": P, "quantity": 50, "unit": "yard"}]})
step("NEG campur baris sample + roll biasa", c, b, (400,))
c, so = sales.post("/sales-orders", {**base, "sample_billing": "paid", "items": [{"product_id": P, "quantity": 3, "unit": "yard", "sample_kind": "standard"}]})
so = need("sales: sample berbayar 3 yd", c, so)
S = so["id"]; print("SOS", so["number"], so["status"], so.get("sample_payment_status"), so.get("grand_total"))
c, b = sa.post(f"/sample-orders/{S}/confirm"); step("NEG teruskan ke gudang sebelum bayar disetujui", c, b, (409,))
c, b = sales.post(f"/sample-orders/{S}/approve-payment", {"note": "x"}); step("NEG sales setujui bayar sample", c, b, (403,))
c, b = fin.post(f"/sample-orders/{S}/approve-payment", {"note": "UAT transfer diterima"}); step("finance: setujui pembayaran sample", c, {"s": b.get("status")} if isinstance(b, dict) and "status" in b else b)
c, b = sa.post(f"/sample-orders/{S}/confirm"); step("admin sample: teruskan ke gudang", c, {"s": b.get("status"), "tasks": b.get("tasks_created")} if isinstance(b, dict) and "status" in b else b)
c, tasks = wh.get("/outbound/tasks")
tl = [t for t in (tasks if isinstance(tasks, list) else []) if t.get("order_id") == S]
step("gudang: tugas potong sample", c, [(t["id"], t.get("status"), t.get("subtype") or t.get("task_subtype"), t.get("quantity")) for t in tl])
import pymongo, os
mdb = pymongo.MongoClient(os.environ.get("MONGO_URL","mongodb://mongo:27017"))[os.environ.get("DB_NAME","test_database")]
parent = mdb.inventory_rolls.find_one({"product_id": P, "owner_entity_id": "ent_ksc", "status": "available", "warehouse_id": "wh_jakarta", "length_reserved": {"$in": [0, None]}, "length_remaining": {"$gt": 20}}, {"_id": 0, "id": 1, "roll_no": 1, "length_remaining": 1})
print("roll induk:", parent)
for t in tl:
    c, b = wh.post(f"/outbound/tasks/{t['id']}/cut-sample", {"roll_code": parent["roll_no"], "code": parent["roll_no"], "length": 3.1, "actual_length": 3.1})
    step("gudang: potong sample dari roll induk (aktual 3,1 yd)", c, short(b, 500), (200, 400, 422))
c, so = sa.get(f"/sales-orders/{S}"); print("SOS setelah potong:", so.get("status"), so.get("stage"))
print("induk setelah potong:", mdb.inventory_rolls.find_one({"id": parent["id"]}, {"_id": 0, "length_remaining": 1, "status": 1}))
print("SAMPLE", S)
