import sys; sys.path.insert(0,'/tmp'); from kn import *
d=db()
TAG="[UJI-AUDIT-1116]"
def stocked(owner,line,minq, stage="finished"):
    rows=d.inventory_rolls.aggregate([{"$match":{"owner_entity_id":owner,"status":"available","grade":"A","stage":stage,"line_code":line,"reserved_ref":None}},{"$group":{"_id":"$product_id","q":{"$sum":"$length_remaining"},"n":{"$sum":1}}},{"$match":{"q":{"$gte":minq}}},{"$sort":{"q":-1}},{"$limit":60}])
    out=[]
    for r in rows:
        p=d.products.find_one({"id":r["_id"]},{"_id":0})
        if p and d.entity_prices.find_one({"entity_id":owner,"product_id":p["id"]}): out.append(p)
    return out
def make_so(ent="ent_ksc",line="woven",nroll=2,cust=None,skip=0,term="NET30",sales="sales",extra=None, cut=None):
    p=stocked(ent,line,200)[skip]
    rolls=list(d.inventory_rolls.find({"product_id":p["id"],"owner_entity_id":ent,"status":"available","grade":"A","reserved_ref":None},{"_id":0,"id":1,"length_remaining":1}).sort("created_at",1).limit(nroll))
    c=d.customers.find_one({"name":cust} if cust else {"entity_ids":ent},{"_id":0}) or d.customers.find_one({},{"_id":0})
    it={"product_id":p["id"],"quantity":round(sum(r["length_remaining"] for r in rolls),2),"unit":p["base_unit"],"purchase_mode":"roll","roll_lines":[{"roll_id":r["id"],"take_qty":r["length_remaining"]} for r in rolls],"qty_rolls":len(rolls)}
    if cut: it={"product_id":p["id"],"quantity":cut,"unit":p["base_unit"]}
    body={"customer_id":c["id"],"shipping_address_id":(c.get("addresses") or [{}])[0].get("id",""),"items":[it],"entity_id":ent,"payment_term_code":term,"allow_backorder":False,"confirm_mixed_lot":True,"notes":TAG}
    if extra: body.update(extra)
    s,j=call("POST","/sales-orders",sales,body,ent=ent,show=250)
    return j,p,rolls,c
def push(oid,ent="ent_ksc",upto="delivered",sa="salesadmin",wh="warehouse"):
    call("POST",f"/sales-orders/{oid}/verify",sa,{"note":TAG},ent=ent,show=160)
    so=d.sales_orders.find_one({"id":oid})
    if so["status"] in ("waiting_approval","pending_approval") or so.get("approval_required"):
        call("POST",f"/sales-orders/{oid}/submit-for-approval",sa,{},ent=ent,show=160)
        call("POST",f"/sales-orders/{oid}/approve","manager",{"note":TAG},ent=ent,show=160)
    call("POST",f"/sales-orders/{oid}/confirm",sa,{},ent=ent,show=160)
    if upto=="confirmed": return
    for t in d.wms_tasks.find({"order_id":oid,"flow_type":"outbound"}):
        call("POST",f"/outbound/tasks/{t['id']}/release",wh,{},ent=ent,show=120)
        rl=[r["id"] for r in d.inventory_rolls.find({"reserved_ref":oid,"product_id":t.get("product_id")})] or [x["roll_id"] for i in so.get("items",[]) if i.get("product_id")==t.get("product_id") for x in i.get("roll_lines",[])]
        for rid in rl: call("POST",f"/outbound/tasks/{t['id']}/scan-pick",wh,{},ent=ent,q={"roll_id":rid},show=160)
    if upto=="picked": return
    call("POST",f"/outbound/so/{oid}/loading-check/override","manager",{"reason":TAG+" roll belum bertag RFID"},ent=ent,show=160)
    for t in d.wms_tasks.find({"order_id":oid,"flow_type":"outbound"}):
        call("POST",f"/outbound/tasks/{t['id']}/dispatch",wh,{},ent=ent,show=200)
    if upto=="delivered": call("POST",f"/sales-orders/{oid}/mark-delivered",sa,{},ent=ent,show=160)
def snap(oid):
    so=d.sales_orders.find_one({"id":oid},{"_id":0})
    print("SNAP",{k:so.get(k) for k in ("number","status","payment_status","subtotal","grand_total","total","amount_paid","outstanding","invoice_id")})
    for i in so.get("items",[]): print("  item",{k:i.get(k) for k in ("product_id","quantity","qty_shipped","unit_price","line_total","purchase_mode","status")})
    print("  shipments",[(s.get("number"),s.get("status"),sum(r.get("length",0) for r in s.get("rolls",[]))) for s in d.shipments.find({"order_id":oid})])
    print("  jurnal",[(j.get("number"),j.get("source_type"),j.get("total_debit")) for j in d.journal_entries.find({"$or":[{"source_id":oid},{"ref_id":oid},{"order_id":oid}]})])
    return so
