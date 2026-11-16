from d2 import *
print("== D-S5 tukar barang (SO-00006 roll0, exchange) → pesanan pengganti")
rid,roll,ln=to_inspected("KSC/SO-00006")
via_spk(rid,grade="A")
call("POST",f"/sales-returns/{rid}/roll-settlement","manager",{"rolls":[{"roll_id":roll,"outcome":"exchange"}],"decision_note":TAG},ent=E,show=120)
r=ret_snap(rid); print("  type",r.get("return_type"),"bal sc",d.customer_balances.find_one({"customer_id":"cust_toko_kain","entity_id":E}).get("store_credit_balance"))
s,j=call("GET",f"/sales-returns/{rid}/replacement","salesadmin",ent=E,show=600)
pid=r["items"][0]["product_id"]
print("-- pesanan pengganti qty 2x kewajiban (uji batas)")
call("POST",f"/sales-returns/{rid}/replacement-order","salesadmin",{"items":[{"product_id":pid,"qty_yard":ln*2}]},ent=E,show=400)
s,j=call("POST",f"/sales-returns/{rid}/replacement-order","salesadmin",{"items":[{"product_id":pid,"qty_yard":ln}]},ent=E,show=400)
print("-- pesanan pengganti kedua (ganda)")
call("POST",f"/sales-returns/{rid}/replacement-order","salesadmin",{"items":[{"product_id":pid,"qty_yard":ln}]},ent=E,show=300)
r=d.sales_returns.find_one({"id":rid}); rep=d.sales_orders.find_one({"id":r.get("replacement_order_id")},{"_id":0}) or {}
print("  SO pengganti",{k:rep.get(k) for k in("number","status","grand_total","payment_status","order_type","payment_term_code")},"store credit",d.customer_balances.find_one({"customer_id":"cust_toko_kain","entity_id":E}).get("store_credit_balance"))
print("-- reverse retur sesudah pesanan pengganti dibuat")
call("POST",f"/sales-returns/{rid}/reverse","manager",{"reason":TAG},ent=E,show=300)
print("  retur",d.sales_returns.find_one({"id":rid})["status"],"SO pengganti",(d.sales_orders.find_one({"id":r.get("replacement_order_id")}) or {}).get("status"),"store credit",d.customer_balances.find_one({"customer_id":"cust_toko_kain","entity_id":E}).get("store_credit_balance"))
