from d2 import *
print("== D-S2/D-S3 retur rusak → disposisi (scrap / klaim supplier)")
rid=d.sales_returns.find_one({"number":"SRET-00009"})["id"]; roll="roll_4cde1de07f78"
call("POST",f"/sales-returns/{rid}/approve","manager",{"notes":TAG},ent=E,show=80)
call("POST",f"/sales-returns/{rid}/journey/scan","warehouse",{"stage":"received","codes":[roll],"warehouse_id":"wh_jakarta","note":TAG},ent=E,show=80)
ins=d.inspections.find_one({"ref_doc_id":rid,"status":{"$nin":["closed","cancelled"]}})
qcu=d.users.find_one({"email":"qc@kainnusantara.id"})["id"]
call("POST",f"/inspections/{ins['id']}/assign","whadmin",{"assigned_to":qcu,"bagian":"QC"},ent=E,show=60)
call("POST",f"/inspections/{ins['id']}/start","qc",{},ent=E,show=60)
ln=ins["lines"][0]
call("POST",f"/inspections/{ins['id']}/lines/{ln['id']}/inspect","qc",{"part":"qc","defects":[{"point_value":4,"count":30,"defect_type":"sobek"}],"grade":"C","decision":"turun_grade","remark":TAG},ent=E,show=300)
call("POST",f"/inspections/{ins['id']}/finish","qc",{"decision":"turun_grade","remark":TAG},ent=E,show=200)
r=ret_snap(rid)
print("  insp",{k:(r.get("inspection") or {}).get(k) for k in ("status","grade","recommended_outcome")}, (r["items"][0].get("inspection") or {}))
s,j=call("GET",f"/sales-returns/{rid}/disposition","manager",ent=E,show=1500)
call("GET",f"/sales-returns/{rid}/grade-impairments","manager",ent=E,show=500)
