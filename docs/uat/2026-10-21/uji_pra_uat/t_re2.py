sadm = Api("salesadmin@kainnusantara.id"); sales = Api("sales@kainnusantara.id"); mgr = Api("manager@kainnusantara.id")
c, desk = sadm.get("/sales-admin/desk")
q = next((x for x in desk.get("queues", []) if x.get("key") == "jatuh_tempo"), {})
print("row keys:", list((q.get("rows") or [{}])[0].keys())[:12])
print([(r.get("number") or r.get("ref_number") or r.get("title"), r.get("subtitle")) for r in q.get("rows", [])])
import pymongo, os
mdb = pymongo.MongoClient(os.environ.get("MONGO_URL","mongodb://mongo:27017"))[os.environ.get("DB_NAME","test_database")]
print("SO-00045 status:", mdb.sales_orders.find_one({"number": "KSC/SO-00045"}, {"_id": 0, "status": 1, "payment_status": 1}))
# F-12 dengan roll lain (SJ-00006: RL-36312-1 28,41 yd)
c, rr = sales.get("/sales-returns/returnable", params={"order_id": "so_d9aa799376ff"})
print("returnable:", [(x.get("roll_no"), x.get("returnable_qty") or x.get("remaining_qty") or x.get("shipped_qty")) for x in rr.get("rolls", [])])
rid = next((x["roll_id"] for x in rr.get("rolls", []) if x.get("roll_no") == "RL-36312-1"), None)
c, r2 = sales.post("/sales-returns", {"order_id": "so_d9aa799376ff", "return_type": "retur", "items": [
    {"product_id": "prod_c854e5856251", "quantity_returned": 1, "unit": "yard", "reason": "recheck", "condition": "ok",
     "roll_ids": [rid], "roll_qtys": {rid: 1}}], "complaint_code": "lain", "submit_now": True})
print("buat retur:", c, short(r2, 150))
if isinstance(r2, dict) and r2.get("id"):
    mgr.post(f"/sales-returns/{r2['id']}/approve", {"notes": "x"})
    c3, b3 = sadm.post(f"/sales-returns/{r2['id']}/inspect/start")
    c4, b4 = sadm.post(f"/sales-returns/{r2['id']}/inspect/complete", {"inspections": [{"product_id": "prod_c854e5856251", "condition": "ok", "accepted_qty": 1}]})
    print("F-12 QC tanpa scan terima: start", c3, "complete", c4, short(b4, 120))
