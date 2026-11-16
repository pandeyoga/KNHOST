from d2 import *
rid=d.sales_returns.find_one({"number":"SRET-00010"})["id"]; r=d.sales_returns.find_one({"id":rid}); roll=r["items"][0]["roll_ids"][0]; cid="ctl_b30bc58cf2b3"
for role in ("whadmin","md","qc","salesadmin","manager"):
    s,j=call("POST",f"/sales-returns/{rid}/cutloss/{cid}/split",role,{},ent=E,show=260)
    if s==200: break
print("  roll & anak",[(x["id"],x.get("roll_no"),x["status"],x.get("length_remaining"),x.get("grade"),x.get("unit_cost"),x.get("warehouse_id")) for x in d.inventory_rolls.find({"$or":[{"id":roll},{"parent_roll_id":roll},{"split_from":roll},{"source_roll_id":roll}]})])
call("POST",f"/sales-returns/{rid}/cutloss/{cid}/return-shipment","salesadmin",{},ent=E,show=260)
s,j=call("GET",f"/sales-returns/{rid}/roll-settlement","manager",ent=E,show=10); print("  back",j.get("back_shipment") or j.get("pending_back") or [k for k in j.keys()])
call("POST",f"/sales-returns/{rid}/roll-settlement/back-shipment","warehouse",{"roll_ids":[roll]},ent=E,show=300)
print("  jurnal",[(j.get("number"),j.get("source_type"),[(l.get("account_code"),l.get("debit"),l.get("credit")) for l in j.get("lines",[])]) for j in d.journal_entries.find().sort("created_at",-1).limit(2)])
print("  roll & anak",[(x["id"],x.get("roll_no"),x["status"],x.get("length_remaining"),x.get("grade"),x.get("unit_cost")) for x in d.inventory_rolls.find({"$or":[{"id":roll},{"parent_roll_id":roll},{"split_from":roll},{"source_roll_id":roll}]})])
