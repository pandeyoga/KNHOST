from flow import *
def ret_snap(rid):
    r=d.sales_returns.find_one({"id":rid},{"_id":0})
    print("RET",{k:r.get(k) for k in ("number","status","outcome","refund_amount","refund_due","credit_note_id","total_amount","return_type")})
    for i in r.get("items",[]): print("  item",{k:i.get(k) for k in ("quantity_returned","unit_price","line_total","roll_ids","condition","disposition","outcome","accepted_qty")})
    print("  rolls",[(x["id"],x["status"],x.get("warehouse_id"),x.get("length_remaining"),x.get("grade"),x.get("reserved_ref")) for x in d.inventory_rolls.find({"id":{"$in":[y for i in r.get("items",[]) for y in i.get("roll_ids",[])]}})])
    print("  jurnal",[(j.get("number"),j.get("source_type"),[(l.get("account_code"),l.get("debit"),l.get("credit")) for l in j.get("lines",[])]) for j in d.journal_entries.find({"$or":[{"source_id":rid},{"source_id":{"$regex":rid}},{"description":{"$regex":r.get("number") or "zzz"}}]})])
    print("  credit_notes",[(c.get("number"),c.get("amount"),c.get("status")) for c in d.credit_notes.find({"return_id":rid})], "cash",[(c.get("direction"),c.get("amount"),c.get("category")) for c in d.cash_transactions.find({"$or":[{"ref_id":rid},{"reference_id":rid},{"source_id":rid}]})])
    return r
def mk_ret(so_no, roll_ix=0, qty=None, rtype="retur", role="salesadmin", cond="ok", code="warna_beda", submit=True, extra=None):
    so=d.sales_orders.find_one({"number":so_no},{"_id":0}); it=so["items"][0]
    call("GET","/sales-returns/returnable",role,q={"order_id":so["id"]},ent="ent_ksc",show=500)
    rl=[x["roll_id"] for x in it["roll_lines"]]; rid=rl[roll_ix]
    L=d.shipments.find_one({"order_id":so["id"]})
    ln=next(r for r in L["rolls"] if r.get("roll_id")==rid or r.get("id")==rid)["length"]
    item={"product_id":it["product_id"],"quantity_returned":qty or ln,"unit":it.get("unit","meter"),"reason":TAG,"condition":cond,"roll_ids":[rid],"qty_rolls":1}
    if qty: item["roll_qtys"]={rid:qty}
    body={"order_id":so["id"],"return_type":rtype,"items":[item],"notes":TAG,"complaint_code":code,"complaint_note":TAG,"submit_now":False}
    if extra: body.update(extra)
    s,j=call("POST","/sales-returns",role,body,ent="ent_ksc",show=300)
    if s==200 and submit: call("POST",f"/sales-returns/{j['id']}/submit",role,{},ent="ent_ksc",show=120)
    return (j.get("id") if s==200 else None), rid, ln
if __name__=="__main__":
    print("== D-S1 retur jual per roll: SO terkirim → ACC → scan karantina → inspeksi → masuk stok → refund")
    rid,roll,ln=mk_ret("KSC/SO-00002")
    call("POST",f"/sales-returns/{rid}/approve","manager",{"notes":TAG},ent="ent_ksc",show=200)
    ret_snap(rid)
    call("POST",f"/sales-returns/{rid}/inspect/start","qc",{},ent="ent_ksc",show=300)
    wh=d.shipments.find_one({"order_id":d.sales_returns.find_one({"id":rid})["order_id"]}).get("warehouse_id") or d.inventory_rolls.find_one({"id":roll})["warehouse_id"]
    call("POST",f"/sales-returns/{rid}/journey/scan","warehouse",{"stage":"received","codes":[roll],"warehouse_id":wh,"note":TAG},ent="ent_ksc",show=300)
    call("POST",f"/sales-returns/{rid}/inspect/start","qc",{},ent="ent_ksc",show=300)
    call("GET",f"/sales-returns/{rid}","manager",ent="ent_ksc",show=100)
    r=ret_snap(rid)
    print("  inspection docs",[(i.get("number"),i.get("status"),i.get("kind") or i.get("type"),len(i.get("lines",[]))) for i in d.inspections.find({"$or":[{"return_id":rid},{"source_id":rid},{"ref_id":rid}]})])
