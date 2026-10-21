SO = "so_485cecbd17f4"; PO = "po_fbc7d6de16f9"
qc = Api("qc@kainnusantara.id"); sadm = Api("salesadmin@kainnusantara.id"); wh = Api("warehouse@kainnusantara.id")
c, q = qc.get("/inbound/qc/queue")
ql = [t for t in (q if isinstance(q, list) else []) if t.get("po_id") == PO]
step("QC: antrean karantina kedatangan", c, [(t["id"], t.get("quarantine_qty"), t.get("status")) for t in ql])
for t in ql:
    c, b = qc.post(f"/inbound/tasks/{t['id']}/qc-decision", {"accept_qty": t.get("quarantine_qty"), "reject_qty": 0, "reason": "UAT lulus", "accept_grade": "A"})
    step("QC: keputusan karantina -> terima", c, short(b, 400))
c, so = sadm.get(f"/sales-orders/{SO}")
print("SO setelah karantina dilepas:", so.get("status"), so.get("stage"), so.get("sub_status"), [(x.get("backorder_qty"), x.get("reserved_qty"), x.get("status")) for x in so.get("backorders", [])])
import pymongo, os
mdb = pymongo.MongoClient(os.environ.get("MONGO_URL","mongodb://mongo:27017"))[os.environ.get("DB_NAME","test_database")]
for r in mdb.inventory_rolls.find({"roll_no": {"$in": ["RL-46500","RL-46501"]}}, {"_id":0,"roll_no":1,"status":1,"reserved_ref":1,"bin_id":1,"journey":1}):
    print(r)
c, pa = wh.get("/putaway-orders"); print("putaway:", c, short(pa, 300))
