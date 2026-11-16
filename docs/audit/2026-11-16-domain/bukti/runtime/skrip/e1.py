from flow import *
E="ent_ksc"
def J(n=3): print("  jurnal",[(j.get("number"),j.get("source_type"),j.get("description","")[:45],[(l.get("account_code"),l.get("debit"),l.get("credit")) for l in j.get("lines",[])]) for j in d.journal_entries.find({"entity_id":E}).sort("created_at",-1).limit(n)])
if __name__=="__main__":
    print("== E-S1 / A-S5 PO greige (yard) → terima ber-QC → tolak sebagian + retur (potong tagihan)")
    grey=d.products.find_one({"sku":"DMO-GRY-WVN-001"},{"_id":0}); sup=d.suppliers.find_one({"name":"CV Grey Mandiri Majalaya"},{"_id":0})
    print("  produk",grey["sku"],grey.get("stage"),grey.get("base_unit"),"supplier",sup["name"])
    print("-- A-S5: PO greige dengan satuan kg (bukan satuan dasar) & satuan ngawur")
    for u in ("kg","lusin"):
        call("POST","/purchase-orders","manager",{"supplier_id":sup["id"],"supplier_name":sup["name"],"warehouse_id":"wh_jakarta","items":[{"product_id":grey["id"],"quantity":10,"unit":u,"price":14000,"expected_grade":"A"}],"entity_id":E,"tax_mode":"ppn","notes":TAG},ent=E,show=260)
    s,po=call("POST","/purchase-orders","manager",{"supplier_id":sup["id"],"supplier_name":sup["name"],"warehouse_id":"wh_jakarta","items":[{"product_id":grey["id"],"quantity":300,"unit":"yard","price":14000,"expected_grade":"A"}],"entity_id":E,"tax_mode":"ppn","notes":TAG},ent=E,show=200)
    for role in ("manager","md"):
        s,j=call("POST",f"/purchase-orders/{po['id']}/approve",role,{},ent=E,show=120)
    po=d.purchase_orders.find_one({"id":po["id"]}); print("  PO",po.get("po_number"),po["status"],po.get("grand_total"))
    for t in d.wms_tasks.find({"po_id":po["id"],"flow_type":"inbound"}):
        for i in range(6):
            call("POST",f"/inbound/tasks/{t['id']}/scan-receive","warehouse",{"product_id":t["product_id"],"actual_qty":50,"batch":"UJI1116","lot":"UJI-LOT-1116","grade":"A","roll_id":f"UJI1116-{i+1:03d}"},ent=E,show=90)
        call("POST",f"/inbound/tasks/{t['id']}/complete","warehouse",{"dye_lot":"UJI-DL-1116","grade":"A"},ent=E,show=160)
        print("  task",d.wms_tasks.find_one({"id":t["id"]})["status"])
        spk=d.inspections.find_one({"task_id":t["id"]}); print("  SPK",spk.get("number"),spk.get("kind"),spk["status"],len(spk.get("lines",[])))
    print("  roll",[(r.get("roll_no"),r["status"],r.get("grade"),r.get("stage"),r.get("unit"),r.get("unit_cost")) for r in d.inventory_rolls.find({"batch":"UJI1116"})][:3]); J(2)
