from e1 import *
grey=d.products.find_one({"sku":"DMO-GRY-WVN-001"},{"_id":0}); sup=d.suppliers.find_one({"name":"CV Grey Mandiri Majalaya"},{"_id":0})
print("== E-S1b PO greige 300 yard, 6 roll (complete dgn rolls[]) → SPK QC → tolak 2 roll + retur potong tagihan")
s,po=call("POST","/purchase-orders","manager",{"supplier_id":sup["id"],"supplier_name":sup["name"],"warehouse_id":"wh_jakarta","items":[{"product_id":grey["id"],"quantity":300,"unit":"yard","price":14000,"expected_grade":"A"}],"entity_id":E,"tax_mode":"ppn","notes":TAG},ent=E,show=60)
t=d.wms_tasks.find_one({"po_id":po["id"],"flow_type":"inbound"})
call("POST",f"/inbound/tasks/{t['id']}/scan-receive","warehouse",{"product_id":t["product_id"],"actual_qty":300,"batch":"UJI1116B","lot":"UJI-LOT-B","grade":"A"},ent=E,show=60)
call("POST",f"/inbound/tasks/{t['id']}/complete","warehouse",{"dye_lot":"UJI-DL-B","grade":"A","rolls":[{"lot":"UJI-LOT-B","length":50,"grade":"A","dye_lot":""} for _ in range(6)]},ent=E,show=200)
spk=d.inspections.find_one({"task_id":t["id"]}); print("  task",d.wms_tasks.find_one({"id":t["id"]})["status"],"SPK",spk.get("number"),spk["status"],len(spk["lines"]))
qcu=d.users.find_one({"email":"qc@kainnusantara.id"})["id"]
print("-- pintu lama: qc-decision langsung di tugas (tanpa SPK)")
call("POST",f"/inbound/tasks/{t['id']}/qc-decision","qc",{"decision":"accept","notes":TAG},ent=E,show=300)
call("POST",f"/inbound/tasks/{t['id']}/qc-decision","whadmin",{"decision":"accept","notes":TAG},ent=E,show=300)
print("-- pintu lama: inspeksi 4-point per roll langsung (/inbound/rolls/{id}/inspect)")
rid0=spk["lines"][0]["roll_id"]
call("POST",f"/inbound/rolls/{rid0}/inspect","qc",{"defects":[],"notes":TAG},ent=E,show=300)
print("-- grade-override pada roll karantina oleh qc / warehouse / manager / mdquality (E-S6)")
for role in ("qc","warehouse","mdquality","whadmin","manager"):
    call("POST",f"/inventory/rolls/{rid0}/grade-override",role,{"grade":"B","reason":TAG+" uji izin"},ent=E,show=170)
print("  roll0",{k:v for k,v in d.inventory_rolls.find_one({"id":rid0},{"_id":0}).items() if k in("status","grade","qc_grade","qc_status")},"grade_history",d.grade_history.count_documents({"roll_id":rid0}))
call("POST",f"/inspections/{spk['id']}/assign","whadmin",{"assigned_to":qcu,"bagian":"QC"},ent=E,show=60)
call("POST",f"/inspections/{spk['id']}/start","qc",{},ent=E,show=60)
rej=[]
for i,ln in enumerate(spk["lines"]):
    bad=i>=4
    s,j=call("POST",f"/inspections/{spk['id']}/lines/{ln['id']}/inspect","qc",{"part":"qc","defects":[{"point_value":4,"count":40,"defect_type":"sobek"}] if bad else [],"grade":"BS" if bad else "A","decision":"tolak" if bad else "terima","remark":TAG},ent=E,show=110 if s!=200 else 60) if False else call("POST",f"/inspections/{spk['id']}/lines/{ln['id']}/inspect","qc",{"part":"qc","defects":[{"point_value":4,"count":40,"defect_type":"sobek"}] if bad else [],"grade":"BS" if bad else "A","decision":"tolak" if bad else "terima","remark":TAG},ent=E,show=110)
    if bad: rej.append(ln["roll_id"])
call("POST",f"/inspections/{spk['id']}/finish","qc",{"decision":"terima_sebagian","remark":TAG,"reject_disposition":"return","rejected_roll_ids":rej,"return_remedy":"bill_cut","return_remedy_reason":TAG},ent=E,show=400)
print("  task",d.wms_tasks.find_one({"id":t["id"]})["status"],"PO",{k:v for k,v in d.purchase_orders.find_one({"id":po["id"]},{"_id":0}).items() if k in("status","received_qty","po_number")})
print("  roll",[(r.get("roll_no"),r["status"],r.get("grade"),r.get("length_remaining")) for r in d.inventory_rolls.find({"batch":"UJI1116B"})])
print("  retur beli",[{k:p.get(k) for k in("id","number","status","doc_status","supplier_status","remedy","total","total_amount","source")} for p in d.purchase_returns.find({"po_id":po["id"]})])
J(4)
