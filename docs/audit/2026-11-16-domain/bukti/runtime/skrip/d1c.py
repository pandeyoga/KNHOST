from d1b import spk, rid, roll
from d1 import *
print("-- inspect/complete dgn grade A lewat pintu retur")
call("POST",f"/sales-returns/{rid}/inspect/complete","qc",{"inspections":[{"index":0,"grade":"A","condition":"ok","disposition":"restock","accepted_qty":117.37,"note":TAG}],"notes":TAG},ent="ent_ksc",show=200)
spk(); ret_snap(rid)
call("GET",f"/sales-returns/{rid}/roll-settlement","manager",ent="ent_ksc",show=900)
print("-- settle refund (header) oleh manager")
s,j=call("POST",f"/sales-returns/{rid}/settle","manager",{"outcome":"refund","notes":TAG,"decision_note":TAG},ent="ent_ksc",show=400)
spk(); ret_snap(rid)
print("-- ulangi settle (klik ganda)")
call("POST",f"/sales-returns/{rid}/settle","manager",{"outcome":"refund","notes":TAG},ent="ent_ksc",show=200)
print("-- SPK QC yatim: coba kerjakan SPK sesudah retur selesai")
ins=d.inspections.find_one({"ref_doc_id":rid})
qcu=d.users.find_one({"email":"qc@kainnusantara.id"})["id"]
call("POST",f"/inspections/{ins['id']}/assign","whadmin",{"assigned_to":qcu,"bagian":"QC"},ent="ent_ksc",show=200)
call("POST",f"/inspections/{ins['id']}/start","qc",{},ent="ent_ksc",show=200)
print("so",d.sales_orders.find_one({"id":"so_5b747c3430d0"},{"_id":0,"grand_total":1,"payment_status":1,"status":1,"returned_amount":1}))
print("bal",{k:v for k,v in d.customer_balances.find_one({"customer_id":"cust_toko_kain","entity_id":"ent_ksc"},{"_id":0}).items() if k in("ar_delivered","deposit_balance","store_credit_balance","open_orders_amount")})
print("jurnal baru",[(j.get("number"),j.get("source_type"),j.get("description","")[:60],[(l.get("account_code"),l.get("debit"),l.get("credit")) for l in j.get("lines",[])]) for j in d.journal_entries.find().sort("created_at",-1).limit(4)])
