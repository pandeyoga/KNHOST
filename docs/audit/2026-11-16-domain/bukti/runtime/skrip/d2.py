from d1 import *
E="ent_ksc"
def via_spk(rid, defects=None, decision="terima", grade=None):
    ins=d.inspections.find_one({"ref_doc_id":rid,"status":{"$nin":["closed","cancelled"]}})
    qcu=d.users.find_one({"email":"qc@kainnusantara.id"})["id"]
    call("POST",f"/inspections/{ins['id']}/assign","whadmin",{"assigned_to":qcu,"bagian":"QC"},ent=E,show=120)
    call("POST",f"/inspections/{ins['id']}/start","qc",{},ent=E,show=120)
    for ln in ins.get("lines",[]):
        b={"part":"qc","defects":defects or [],"remark":TAG}
        if grade: b["grade"]=grade
        call("POST",f"/inspections/{ins['id']}/lines/{ln['id']}/inspect","qc",b,ent=E,show=260)
    call("POST",f"/inspections/{ins['id']}/finish","qc",{"decision":decision,"remark":TAG},ent=E,show=260)
    return ins["id"]
def to_inspected(so_no, **kw):
    rid,roll,ln=mk_ret(so_no, **kw)
    call("POST",f"/sales-returns/{rid}/approve","manager",{"notes":TAG},ent=E,show=100)
    call("POST",f"/sales-returns/{rid}/journey/scan","warehouse",{"stage":"received","codes":[roll],"warehouse_id":"wh_jakarta","note":TAG},ent=E,show=100)
    via_spk(rid)
    return rid,roll,ln
if __name__=="__main__":
    print("== D-S1b retur SO LUNAS lewat SPK QC → roll-settlement refund tunai → reverse")
    so=d.sales_orders.find_one({"number":"KSC/SO-00003"})
    call("POST","/ar-receipts","finance",{"customer_id":so["customer_id"],"amount":so["grand_total"],"method":"transfer","entity_id":E,"notes":TAG,"allocations":[{"order_id":so["id"],"amount":so["grand_total"]}]},ent=E,show=200)
    rid,roll,ln=to_inspected("KSC/SO-00003")
    r=ret_snap(rid)
    s,j=call("GET",f"/sales-returns/{rid}/roll-settlement","manager",ent=E,show=100)
    print("  opsi",[(o["value"],o["ok"],o.get("why","")[:60]) for o in j["rows"][0]["options"]], "grade",j["rows"][0].get("grade"))
    call("POST",f"/sales-returns/{rid}/roll-settlement/preview","manager",{"rolls":[{"roll_id":roll,"outcome":"refund"}]},ent=E,show=700)
    call("POST",f"/sales-returns/{rid}/roll-settlement","manager",{"rolls":[{"roll_id":roll,"outcome":"refund"}],"decision_note":TAG},ent=E,show=300)
    r=ret_snap(rid)
    print("  settlement events",[(e.get("id"),e.get("status"),e.get("outcome"),e.get("amount") or e.get("gross_amount")) for e in (r.get("settlements") or r.get("settlement",{}).get("events") or [])], {k:r.get(k) for k in("refund_due","refund_paid","credit_note_amount")})
    print("  so",d.sales_orders.find_one({"id":so["id"]},{"_id":0,"payment_status":1,"grand_total":1}))
