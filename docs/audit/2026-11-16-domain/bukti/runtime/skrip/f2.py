from flow import *
E="ent_ksc"
def bal(): 
    b=d.customer_balances.find_one({"customer_id":"cust_toko_kain","entity_id":E},{"_id":0}); return {k:b.get(k) for k in("ar_delivered","open_orders_amount","deposit_balance","store_credit_balance")}
def so_line(oid):
    so=d.sales_orders.find_one({"id":oid},{"_id":0}); it=so["items"][0]
    print("  SO",{k:so.get(k) for k in("number","status","grand_total","payment_status","paid_amount","amount_paid","has_backorder")},"qty",it.get("quantity"),"line_total",it.get("line_total"),"rolls",[(x.get("roll_id"),x.get("take_qty")) for x in it.get("roll_lines",[])])
    print("  roll dipegang",[(r["id"],r["status"],r["length_remaining"]) for r in d.inventory_rolls.find({"reserved_ref.id":oid})],"alok AR",[(a.get("number"),[(x.get("order_id")==oid,x.get("amount")) for x in a.get("allocations",[])]) for a in d.ar_receipts.find({"allocations.order_id":oid,"status":{"$ne":"void"}})])
    return so
if __name__=="__main__":
    print("== F-S2 realokasi roll sesudah DP dibayar"); print("  saldo awal",bal())
    so,p,rolls,c=make_so(skip=8)
    oid=so["id"]; s0=so_line(oid)
    dp=round(s0["grand_total"]*0.5)
    call("POST","/ar-receipts","finance",{"customer_id":s0["customer_id"],"amount":dp,"method":"transfer","entity_id":E,"notes":TAG,"allocations":[{"order_id":oid,"amount":dp}]},ent=E,show=160)
    so_line(oid); print("  saldo",bal())
    s,j=call("GET",f"/sales-orders/{oid}/items/{p['id']}/roll-candidates","salesadmin",ent=E,show=300)
    cand=[r for r in d.inventory_rolls.find({"product_id":p["id"],"owner_entity_id":E,"status":"available","grade":"A","reserved_ref":None}).sort("length_remaining",-1).limit(1)]
    print("  kandidat pengganti",[(r["id"],r["length_remaining"]) for r in cand])
    print("-- ganti 2 roll (%.2f) dengan 1 roll lain (%.2f)"%(sum(r["length_remaining"] for r in rolls),cand[0]["length_remaining"]))
    call("POST",f"/sales-orders/{oid}/items/{p['id']}/reallocate","salesadmin",{"roll_lines":[{"roll_id":cand[0]["id"],"take_qty":cand[0]["length_remaining"]}],"reason":TAG+" uji realokasi sesudah DP"},ent=E,show=350)
    s1=so_line(oid); print("  saldo",bal()); print("  DP",dp,"vs total baru",s1["grand_total"],"total lama",s0["grand_total"])
