from e1 import *
po=d.purchase_orders.find_one({"po_number":"KSC/PO-00004"}); t=d.wms_tasks.find_one({"po_id":po["id"],"flow_type":"inbound"}); spk=d.inspections.find_one({"task_id":t["id"],"kind":"po_receipt"})
rej=[r["id"] for r in d.inventory_rolls.find({"batch":"UJI1116B","grade":"BS"})]
print("  RL-46494 history",[(h.get("grade_before"),h.get("grade_after"),h.get("source")) for h in d.inventory_rolls.find_one({"roll_no":"RL-46494"}).get("grade_history") or []])
print("-- SPK penerimaan: bagian MD Quality mengisi warna/handfeel")
for i,ln in enumerate(spk["lines"]):
    s,j=call("POST",f"/inspections/{spk['id']}/lines/{ln['id']}/inspect","mdquality",{"part":"md_quality","color_result":"sesuai","handfeel_result":"sesuai","remark":TAG},ent=E,show=140 if i==0 else 40)
for role in ("mdquality","qc","whadmin","manager"):
    s,j=call("POST",f"/inspections/{spk['id']}/finish",role,{"decision":"terima_sebagian","remark":TAG,"reject_disposition":"return","rejected_roll_ids":rej,"return_remedy":"bill_cut","return_remedy_reason":TAG},ent=E,show=260)
    if s==200: break
print("  task",d.wms_tasks.find_one({"id":t["id"]})["status"],"SPK penerimaan",d.inspections.find_one({"id":spk["id"]})["status"])
print("  roll",[(r.get("roll_no"),r["status"],r.get("grade")) for r in d.inventory_rolls.find({"batch":"UJI1116B"})])
prs=list(d.purchase_returns.find({"$or":[{"po_id":po["id"]},{"po_number":"KSC/PO-00004"}]},{"_id":0}))
print("  retur beli",[{k:p.get(k) for k in("id","number","status","doc_status","supplier_status","remedy","return_remedy","grand_total","total_amount","source","origin")} for p in prs])
J(4)
print("  stok grey available",d.inventory_rolls.count_documents({"batch":"UJI1116B","status":"available"}))
