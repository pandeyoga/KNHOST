from d1 import *
rid=d.sales_returns.find_one({"number":"SRET-00004"})["id"]; roll="roll_c12bec196c26"
def spk(): print("  SPK",[(i.get("number"),i.get("kind"),i.get("status"),i.get("assigned_to"),[(l.get("roll_id"),l.get("status"),l.get("result")) for l in i.get("lines",[])]) for i in d.inspections.find({"ref_doc_id":rid})])
spk()
print("-- pintu 1: inspect/complete langsung di retur (tanpa menyentuh SPK QC)")
call("POST",f"/sales-returns/{rid}/inspect/complete","qc",{"inspections":[{"index":0,"condition":"ok","disposition":"restock","accepted_qty":117.37,"note":TAG}],"notes":TAG},ent="ent_ksc",show=300)
spk(); ret_snap(rid)
call("POST",f"/sales-returns/{rid}/settle-preview","manager",{"outcome":"refund","notes":TAG},ent="ent_ksc",show=700)
call("GET",f"/sales-returns/{rid}/roll-settlement","manager",ent="ent_ksc",show=700)
