from flow import *
C="ent_95a87a634457"
P=lambda sku: d.products.find_one({"sku":sku},{"_id":0})
M=lambda n: d.makloons.find_one({"name":n},{"_id":0})
W=lambda c: d.warehouses.find_one({"code":c})["id"]
def JJ(n=3,ent=C): print("  jurnal",[(j.get("number"),j.get("source_type"),j.get("description","")[:50],[(l.get("account_code"),l.get("debit"),l.get("credit")) for l in j.get("lines",[])]) for j in d.journal_entries.find({"entity_id":ent}).sort("created_at",-1).limit(n)])
def mk(steps,mat,qty,unit,wh,note):
    return call("POST","/makloon-orders","manager",{"mode":"process_only","material_product_id":mat["id"],"material_qty":qty,"material_unit":unit,"from_warehouse_id":wh,"target_warehouse_id":wh,"entity_id":C,"steps":steps,"notes":TAG+" "+note,"manual_material_reason":TAG+" resep belum diisi","route_reason":TAG+" uji audit jalur makloon"},ent=C,show=330)
def ms(mid):
    m=d.makloon_orders.find_one({"id":mid},{"_id":0}); print("  SPK",m.get("mko_number"),m["status"],[(s.get("seq"),s.get("process_type"),s.get("status"),s.get("from_stage"),s.get("to_stage"),s.get("input_qty"),s.get("issued_qty"),s.get("received_qty") or s.get("output_qty"),s.get("service_cost") or s.get("rate")) for s in m["steps"]]); return m
if __name__=="__main__":
    gk,pfd,pfp,yw=P("DMO-GRY-KNT-001"),P("DMO-PFD-KNT-001"),P("DMO-PFP-WVN-001"),P("DMO-YRN-WVN-30S")
    fin=d.products.find_one({"import_batch":"MIGRASI_MASTER_PRODUK_KN","line_code":"knit","entity_ids":C},{"_id":0})
    celup,prn=M("PT Celup Warna Dayeuhkolot"),M("CV Printing Sablon Cimahi"); w=W("RCM-KNITTING")
    print("stok bahan",[(p["sku"],p["stage"],p["base_unit"],round(sum(r["length_remaining"] for r in d.inventory_rolls.find({"product_id":p["id"],"owner_entity_id":C,"status":"available"})),1)) for p in (gk,pfd,pfp,yw)], "mitra printing process_types",prn.get("process_types"),"celup",celup.get("process_types"))
    print("== A-S6 langkah tak cocok stage lewat API")
    print("-- (1) printing langsung dari GREIGE (belum PFP), hasil = bahan jadi")
    s,a1=mk([{"process_type":"printing","stage_code":"printing","makloon_id":prn["id"],"input_product_id":gk["id"],"output_product_id":fin["id"],"input_qty":50,"colors":2}],gk,50,"kg",w,"A-S6 printing dari greige")
    print("-- (2) celup dengan mitra PRINTING (process_types mitra tak cocok), bahan BENANG, hasil bahan jadi")
    s,a2=mk([{"process_type":"celup","stage_code":"celup","makloon_id":prn["id"],"input_product_id":yw["id"],"output_product_id":fin["id"],"input_qty":20}],yw,20,"kg",W("RCM-WOVEN"),"A-S6 celup benang di mitra printing")
    print("-- (3) hasil langkah = BENANG dari bahan jadi (transisi mundur)")
    s,a3=mk([{"process_type":"celup","stage_code":"celup","makloon_id":celup["id"],"input_product_id":fin["id"],"output_product_id":yw["id"],"input_qty":20}],fin,20,fin["base_unit"],w,"A-S6 transisi mundur")
    for a in (a1,a2,a3):
        if isinstance(a,dict) and a.get("id"): ms(a["id"])
