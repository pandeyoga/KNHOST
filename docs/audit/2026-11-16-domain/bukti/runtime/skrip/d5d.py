from d2 import *
rid=d.sales_returns.find_one({"number":"SRET-00010"})["id"]; r=d.sales_returns.find_one({"id":rid}); roll=r["items"][0]["roll_ids"][0]; cid="ctl_b30bc58cf2b3"
for role in ("md","manager","admin"):
    s,j=call("POST",f"/sales-returns/{rid}/cutloss/{cid}/return-shipment",role,{},ent=E,show=400)
    if s==200: break
print("  roll & anak",[(x["id"],x.get("roll_no"),x["status"],x.get("length_remaining"),x.get("grade"),x.get("unit_cost")) for x in d.inventory_rolls.find({"$or":[{"id":roll},{"parent_roll_id":roll},{"split_from":roll},{"source_roll_id":roll},{"roll_no":{"$regex":"^RL-35413"}}]})])
print("  jurnal",[(j.get("number"),j.get("source_type"),j.get("description","")[:60],[(l.get("account_code"),l.get("debit"),l.get("credit")) for l in j.get("lines",[])]) for j in d.journal_entries.find().sort("created_at",-1).limit(3)])
print("  tugas/shipments baru",[(t.get("id"),t.get("flow_type"),t.get("task_subtype"),t.get("status")) for t in d.wms_tasks.find({"$or":[{"return_id":rid},{"ref_id":rid},{"source_id":rid}]})],[(s.get("number"),s.get("status"),s.get("kind")) for s in d.shipments.find({"$or":[{"return_id":rid},{"ref_id":rid}]})])
