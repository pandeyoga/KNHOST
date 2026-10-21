SO = "so_485cecbd17f4"
mdq = Api("mdquality@kainnusantara.id"); qc = Api("qc@kainnusantara.id"); mgr = Api("manager@kainnusantara.id"); sadm = Api("salesadmin@kainnusantara.id"); whadm=Api("wh.admin@kainnusantara.id")
c, ins = mgr.get("/inspections", params={"source": "receiving"})
I = next(x for x in ins["items"] if x.get("ref_doc_number") == "KSC/PO-00028")
qc_id = qc.user["id"]
for who, a in (("whadm", whadm), ("mgr", mgr)):
    c, b = a.post(f"/inspections/{I['id']}/assign", {"assigned_to": qc_id, "assigned_user_id": qc_id, "user_id": qc_id})
    if step(f"{who}: tugaskan SPK ke QC", c, {"s": b.get("status"), "to": b.get("assigned_name")} if isinstance(b, dict) and "status" in b else b, (200, 400, 403, 422)) and c == 200:
        break
c, b = qc.post(f"/inspections/{I['id']}/start"); step("QC: mulai", c, {"s": b.get("status")} if isinstance(b, dict) and "status" in b else b)
c, d = qc.get(f"/inspections/{I['id']}")
for l in d.get("lines", []):
    c, b = qc.post(f"/inspections/{I['id']}/lines/{l['id']}/inspect", {"part": "qc", "defects": [], "inspect_length_yard": 0, "decision": "terima"})
    step(f"QC: 4-point {l.get('roll_no')}", c, {"s": b.get("status")} if isinstance(b, dict) and "status" in b else b, (200, 400))
for who, a in (("qc", qc), ("whadm", whadm), ("mgr", mgr)):
    c, b = a.post(f"/inspections/{I['id']}/finish", {"decision": "terima", "remark": "UAT"})
    if step(f"{who}: tutup inspeksi (terima)", c, {"s": b.get("status")} if isinstance(b, dict) and "status" in b else b, (200, 400, 403)) and c == 200:
        break
c, so = sadm.get(f"/sales-orders/{SO}")
print("SO setelah barang lulus:", so.get("status"), so.get("stage"), so.get("sub_status"), [(x.get("backorder_qty"), x.get("reserved_qty"), x.get("status")) for x in so.get("backorders", [])])
import pymongo, os
mdb = pymongo.MongoClient(os.environ.get("MONGO_URL","mongodb://mongo:27017"))[os.environ.get("DB_NAME","test_database")]
for r in mdb.inventory_rolls.find({"roll_no": {"$in": ["RL-46500","RL-46501"]}}, {"_id":0,"roll_no":1,"status":1,"reserved_ref":1,"length_remaining":1,"unit":1,"grade":1,"earmarked_for":1}):
    print(r)
