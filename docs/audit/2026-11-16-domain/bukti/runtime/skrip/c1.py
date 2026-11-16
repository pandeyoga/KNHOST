from flow import *
E="ent_ksc"
print("== C-S2 Pesanan Khusus → create-sku (pintu Pesanan Khusus) vs C-S1 spesifikasi R&D → release-product (pintu R&D)")
for sid in ("sord_ae9d5543756c","sord_e3b0981bfe7f"):
    s,j=call("POST",f"/special-orders/{sid}/create-sku","manager",{},ent=E,show=120)
    if s==200:
        p=j["product"]; print("  SKU lahir",{k:p.get(k) for k in("sku","name","stage","base_unit","category","lifecycle_status","needs_review","domain_gaps","gsm","width_cm","composition","line_code","is_orderable")})
        s2,j2=call("POST",f"/special-orders/{sid}/create-sku","manager",{},ent=E,show=10); print("  panggilan kedua (idempoten?) sku sama:",s2==200 and j2["product"]["id"]==p["id"])
        s3,j3=call("GET","/products","sales",q={"orderable_only":"true","q":p["sku"]},ent=E,show=10)
        it=j3.get("items",j3) if isinstance(j3,dict) else j3; print("  muncul di katalog POS/orderable?",[x.get("sku") for x in it if x.get("sku")==p["sku"]])
print("-- pintu R&D: spesifikasi minimal tanpa GSM/lebar/komposisi (stage finished)")
tpl=d.product_templates.find_one({},{"_id":0})
s,sp=call("POST","/rnd/specs","md",{"title":TAG+" spec uji","category":"woven","base_unit":"yard","line_code":"woven","template_id":tpl["id"],"notes":TAG},ent=E,show=260)
if s!=200: s,sp=call("POST","/rnd/specs","manager",{"title":TAG+" spec uji","category":"woven","base_unit":"yard","line_code":"woven","template_id":tpl["id"],"notes":TAG},ent=E,show=260)
if s==200:
    sid=sp["id"]; who="md"
    call("POST",f"/rnd/specs/{sid}/submit",who,{},ent=E,show=200)
    print("-- pembuat menyetujui sendiri?")
    s,j=call("POST",f"/rnd/specs/{sid}/approve",who,{"notes":TAG},ent=E,show=260)
    if s!=200: call("POST",f"/rnd/specs/{sid}/approve","manager",{"notes":TAG},ent=E,show=260)
    s,j=call("POST",f"/rnd/specs/{sid}/release-product","md",{},ent=E,show=300)
    x=d.md_specs.find_one({"id":sid},{"_id":0}) or {}; print("  spec",{k:x.get(k) for k in("status","product_id","sku","gate","required_tests")})
