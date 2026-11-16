from flow import *
import io,contextlib
oid="so_5b747c3430d0"
print("jurnal terbaru:",[(j.get("number"),j.get("source_type"),j.get("source_id") or j.get("reference_id"),j.get("description","")[:50],[(l.get("account_code"),l.get("debit"),l.get("credit")) for l in j.get("lines",[])]) for j in d.journal_entries.find().sort("created_at",-1).limit(3)])
print("customer_balances",d.customer_balances.find_one({"customer_id":"cust_toko_kain","entity_id":"ent_ksc"},{"_id":0}))
call("GET","/ar-aging","finance",ent="ent_ksc",show=300)
call("GET",f"/invoices","finance",q={"order_id":oid},ent="ent_ksc",show=400)
ids=[]
for i in range(5):
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf):
        so,p,rolls,c=make_so(skip=i+1)
        if "id" in so: push(so["id"])
    st=d.sales_orders.find_one({"id":so.get("id")},{"status":1,"number":1,"grand_total":1}) if "id" in so else so
    print("SO tambahan",st if "id" not in so else (st["number"],st["status"],st["grand_total"],p["sku"],[r["id"] for r in rolls]))
    if "id" in so and st["status"]!="done": print(buf.getvalue()[-900:])
