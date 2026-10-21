S = "so_c92387a4c25b"
wh = Api("warehouse@kainnusantara.id"); sa = Api("sampleadmin@kainnusantara.id"); whadm = Api("wh.admin@kainnusantara.id"); fin = Api("finance@kainnusantara.id")
c, tasks = wh.get("/outbound/tasks")
t = [x for x in tasks if x.get("order_id") == S][0]
c, b = wh.post(f"/outbound/tasks/{t['id']}/cut-sample", {"roll_id": "roll_1c4a2e07ab21", "actual_length": 3.1})
step("NEG potong dari roll produk lain", c, short(b, 300), (400, 404, 409))
c, b = wh.post(f"/outbound/tasks/{t['id']}/cut-sample", {"roll_id": "roll_7a30aa907829", "actual_length": 3.1})
step("gudang: potong sample RL-36312 aktual 3,1 yd", c, {"cut": (b.get("cut") or {})} if isinstance(b, dict) and "cut" in b else b)
import pymongo, os
mdb = pymongo.MongoClient(os.environ.get("MONGO_URL","mongodb://mongo:27017"))[os.environ.get("DB_NAME","test_database")]
print("induk:", mdb.inventory_rolls.find_one({"id": "roll_7a30aa907829"}, {"_id": 0, "length_remaining": 1, "status": 1}))
c, t2 = wh.get("/outbound/tasks"); t2 = [x for x in t2 if x.get("order_id") == S]
print("tugas:", [(x["status"], x.get("picked_qty"), x.get("quantity")) for x in t2])
for x in t2:
    c, b = wh.post(f"/outbound/tasks/{x['id']}/dispatch")
    if c != 200:
        step("info dispatch sample", c, b, (400, 409))
        whadm.post(f"/outbound/so/{S}/loading-check/override", {"reason": "UAT tanpa RFID - manual"})
        c, b = wh.post(f"/outbound/tasks/{x['id']}/dispatch")
    step("gudang: kirim sample (SJ)", c, {"sj": (b.get("shipment") or {}).get("shipment_no"), "qty": (b.get("shipment") or {}).get("qty")} if isinstance(b, dict) and "shipment" in b else b, (200, 400, 409))
c, so = sa.get(f"/sales-orders/{S}")
print("SOS akhir:", so.get("status"), so.get("stage"), "bayar", so.get("payment_status"), so.get("sample_payment_status"), "grand", so.get("grand_total"), "qty item", [(i.get("quantity"), i.get("price")) for i in so["items"]])
