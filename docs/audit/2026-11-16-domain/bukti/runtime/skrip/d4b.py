from d2 import *
rid=d.sales_returns.find_one({"number":"SRET-00009"})["id"]; roll="roll_4cde1de07f78"
ins=d.inspections.find_one({"ref_doc_id":rid,"status":{"$nin":["closed","cancelled"]}}); ln=ins["lines"][0]
call("POST",f"/inspections/{ins['id']}/lines/{ln['id']}/inspect","qc",{"part":"qc","defects":[{"point_value":4,"count":30,"defect_type":"sobek"}],"grade":"BS","decision":"turun_grade","remark":TAG},ent=E,show=120)
call("POST",f"/inspections/{ins['id']}/finish","qc",{"decision":"turun_grade","remark":TAG},ent=E,show=120)
r=ret_snap(rid)
print("  grade_history",[(g.get("from_grade"),g.get("to_grade"),g.get("source"),g.get("by")) for g in d.grade_history.find({"roll_id":roll})])
s,j=call("GET",f"/sales-returns/{rid}/roll-settlement","manager",ent=E,show=10); print("  opsi",[(o["value"],o["ok"],o.get("why","")[:50]) for o in j["rows"][0]["options"]],"grade",j["rows"][0].get("grade"))
print("-- disposisi SEBELUM penyelesaian uang: buang (BS)")
call("POST",f"/sales-returns/{rid}/disposition/supplier","manager",{"roll_ids":[roll],"decision":"dispose","reason":TAG},ent=E,show=400)
call("POST",f"/sales-returns/{rid}/disposition/supplier","md",{"roll_ids":[roll],"decision":"dispose","reason":TAG},ent=E,show=400)
call("POST",f"/sales-returns/{rid}/disposition/supplier","admin",{"roll_ids":[roll],"decision":"dispose","reason":TAG},ent=E,show=400)
print("-- refund per roll")
call("POST",f"/sales-returns/{rid}/roll-settlement","manager",{"rolls":[{"roll_id":roll,"outcome":"refund"}],"decision_note":TAG},ent=E,show=120)
r=ret_snap(rid)
call("GET",f"/sales-returns/{rid}/grade-impairments","manager",ent=E,show=500)
s,j=call("GET",f"/sales-returns/{rid}/disposition","manager",ent=E,show=10); print("  disp row",{k:j["rows"][0].get(k) for k in("grade","status","stage","internal","supplier","sellable")})
print("-- disposisi SESUDAH penyelesaian: buang (BS)")
for role in ("manager","md","admin"):
    s,_=call("POST",f"/sales-returns/{rid}/disposition/supplier",role,{"roll_ids":[roll],"decision":"dispose","reason":TAG},ent=E,show=300)
    if s==200: break
r=ret_snap(rid)
print("  jurnal terbaru",[(j.get("number"),j.get("source_type"),j.get("description","")[:50],[(l.get("account_code"),l.get("debit"),l.get("credit")) for l in j.get("lines",[])]) for j in d.journal_entries.find().sort("created_at",-1).limit(3)])
print("-- batal scrap (reverse-writeoff)")
call("POST",f"/sales-returns/{rid}/reverse-writeoff","manager",{"roll_ids":[roll],"reason":TAG},ent=E,show=300)
r=ret_snap(rid)
