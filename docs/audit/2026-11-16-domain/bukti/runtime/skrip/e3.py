from e1 import *
r=d.inventory_rolls.find_one({"id":"roll_4cde1de07f78"},{"_id":0}); print("roll retur A→BS: grade",r["grade"],"grade_source",r.get("grade_source"),"history",[(h.get("grade_before"),h.get("grade_after"),h.get("source")) for h in r.get("grade_history") or []])
r=d.inventory_rolls.find_one({"id":"roll_f2d7f5f31ffe"},{"_id":0}); print("potongan cutloss BS: grade",r["grade"],"history",[(h.get("grade_before"),h.get("grade_after"),h.get("source")) for h in r.get("grade_history") or []])
po=d.purchase_orders.find_one({"po_number":"KSC/PO-00004"}); t=d.wms_tasks.find_one({"po_id":po["id"],"flow_type":"inbound"}); spk=d.inspections.find_one({"task_id":t["id"],"kind":"po_receipt"})
qcu=d.users.find_one({"email":"qc@kainnusantara.id"})["id"]
print("-- warehouse mencoba inspeksi 4-point langsung (pintu /inbound/rolls/{id}/inspect)")
call("POST",f"/inbound/rolls/{spk['lines'][1]['roll_id']}/inspect","warehouse",{"defects":[{"point_value":4,"count":50,"defect_type":"sobek"}],"notes":TAG},ent=E,show=300)
x=d.inventory_rolls.find_one({"id":spk['lines'][1]['roll_id']}); print("  roll1",x["status"],x["grade"],x.get("grade_source"))
print("-- SPK QC 4-point tersendiri dari SPK penerimaan")
s,q4=call("POST","/inspections/qc-4point","qc",{"inspection_id":spk["id"],"remark":TAG},ent=E,show=200)
if s!=200: s,q4=call("POST","/inspections/qc-4point","qc",{"task_id":t["id"],"remark":TAG},ent=E,show=200)
if s==200:
    print("  q4",q4.get("number"),q4.get("kind"),q4["status"],len(q4["lines"]))
    call("POST",f"/inspections/{q4['id']}/assign","whadmin",{"assigned_to":qcu,"bagian":"QC"},ent=E,show=60)
    call("POST",f"/inspections/{q4['id']}/start","qc",{},ent=E,show=60)
    rej=[]
    for i,ln in enumerate(q4["lines"]):
        bad=i>=4
        call("POST",f"/inspections/{q4['id']}/lines/{ln['id']}/inspect","qc",{"part":"qc","defects":[{"point_value":4,"count":40,"defect_type":"sobek"}] if bad else [],"grade":"BS" if bad else "A","decision":"tolak" if bad else "terima","remark":TAG},ent=E,show=110)
        if bad: rej.append(ln["roll_id"])
    call("POST",f"/inspections/{q4['id']}/finish","qc",{"decision":"terima_sebagian","remark":TAG,"reject_disposition":"return","rejected_roll_ids":rej,"return_remedy":"bill_cut","return_remedy_reason":TAG},ent=E,show=300)
    print("  sesudah tutup SPK 4-point: task",d.wms_tasks.find_one({"id":t["id"]})["status"],"SPK penerimaan",d.inspections.find_one({"id":spk["id"]})["status"])
    print("  roll",[(r.get("roll_no"),r["status"],r.get("grade")) for r in d.inventory_rolls.find({"batch":"UJI1116B"})])
    print("-- tutup SPK penerimaan (keputusan karantina)")
    call("POST",f"/inspections/{spk['id']}/finish","qc",{"decision":"terima_sebagian","remark":TAG,"reject_disposition":"return","rejected_roll_ids":rej,"return_remedy":"bill_cut","return_remedy_reason":TAG},ent=E,show=300)
    call("POST",f"/inspections/{spk['id']}/finish","whadmin",{"decision":"terima_sebagian","remark":TAG,"reject_disposition":"return","rejected_roll_ids":rej,"return_remedy":"bill_cut","return_remedy_reason":TAG},ent=E,show=300)
    print("  task",d.wms_tasks.find_one({"id":t["id"]})["status"],"SPK penerimaan",d.inspections.find_one({"id":spk["id"]})["status"])
    print("  roll",[(r.get("roll_no"),r["status"],r.get("grade")) for r in d.inventory_rolls.find({"batch":"UJI1116B"})])
    print("  retur beli",[{k:p.get(k) for k in("id","number","status","doc_status","supplier_status","remedy","grand_total","total_amount","source")} for p in d.purchase_returns.find({"po_id":po["id"]})])
    J(3)
