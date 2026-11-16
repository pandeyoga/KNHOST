from e1 import *
print("== E-S1c dua pintu keputusan tak direkonsiliasi: QC 4-point 'tolak' vs MD Quality 'terima' (PO-00003, 1 roll 300 yd)")
po=d.purchase_orders.find_one({"po_number":"KSC/PO-00003"}); t=d.wms_tasks.find_one({"po_id":po["id"],"flow_type":"inbound"}); spk=d.inspections.find_one({"task_id":t["id"],"kind":"po_receipt"})
qcu=d.users.find_one({"email":"qc@kainnusantara.id"})["id"]; rid=spk["lines"][0]["roll_id"]
s,q4=call("POST","/inspections/qc-4point","qc",{"inspection_id":spk["id"],"remark":TAG},ent=E,show=60)
call("POST",f"/inspections/{q4['id']}/start","qc",{},ent=E,show=60)
call("POST",f"/inspections/{q4['id']}/lines/{q4['lines'][0]['id']}/inspect","qc",{"part":"qc","defects":[{"point_value":4,"count":90,"defect_type":"sobek"}],"grade":"BS","decision":"tolak","remark":TAG},ent=E,show=60)
call("POST",f"/inspections/{q4['id']}/finish","qc",{"decision":"tolak","remark":TAG,"reject_disposition":"return","rejected_roll_ids":[rid],"return_remedy":"replace","return_remedy_reason":TAG},ent=E,show=60)
print("  sesudah QC tolak:",[(r.get("roll_no"),r["status"],r.get("grade")) for r in d.inventory_rolls.find({"id":rid})])
call("POST",f"/inspections/{spk['id']}/assign","whadmin",{"assigned_to":d.users.find_one({"email":"mdquality@kainnusantara.id"})["id"],"bagian":"MD Quality"},ent=E,show=60)
call("POST",f"/inspections/{spk['id']}/start","mdquality",{},ent=E,show=60)
call("POST",f"/inspections/{spk['id']}/lines/{spk['lines'][0]['id']}/inspect","mdquality",{"part":"md_quality","color_result":"sesuai","handfeel_result":"sesuai","remark":TAG},ent=E,show=60)
call("POST",f"/inspections/{spk['id']}/finish","mdquality",{"decision":"terima","remark":TAG},ent=E,show=200)
print("  akhir:",[(r.get("roll_no"),r["status"],r.get("grade"),r.get("length_remaining")) for r in d.inventory_rolls.find({"id":rid})],"task",d.wms_tasks.find_one({"id":t["id"]})["status"],"retur beli",d.purchase_returns.count_documents({"po_id":po["id"]}))
