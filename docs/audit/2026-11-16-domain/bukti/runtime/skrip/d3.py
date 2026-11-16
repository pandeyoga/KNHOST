from d2 import *
def rolls_of(rid):
    r=d.sales_returns.find_one({"id":rid}); ids=[y for i in r["items"] for y in i.get("roll_ids",[])]
    return [(x["id"],x["status"],x.get("warehouse_id"),x.get("grade"),x.get("stock_class") or x.get("bucket")) for x in d.inventory_rolls.find({"id":{"$in":ids}})]
print("== D-S8a tolak retur yang masih menunggu ACC (SRET-00006)")
rid=d.sales_returns.find_one({"number":"SRET-00006"})["id"]
call("POST",f"/sales-returns/{rid}/reject","manager",{"notes":TAG},ent=E,show=120); print("  ",rolls_of(rid))
print("== D-S8b buang draf")
rid,roll,ln=mk_ret("KSC/SO-00004",submit=False)
call("POST",f"/sales-returns/{rid}/cancel-draft","salesadmin",{},ent=E,show=100)
print("== D-S8c tolak SESUDAH barang diterima gudang (approved + scan terima) — nasib roll?")
rid,roll,ln=mk_ret("KSC/SO-00004")
call("POST",f"/sales-returns/{rid}/approve","manager",{"notes":TAG},ent=E,show=80)
call("POST",f"/sales-returns/{rid}/journey/scan","warehouse",{"stage":"received","codes":[roll],"warehouse_id":"wh_jakarta","note":TAG},ent=E,show=80)
print("  sebelum tolak",rolls_of(rid))
call("POST",f"/sales-returns/{rid}/reject","manager",{"notes":TAG},ent=E,show=160)
r=d.sales_returns.find_one({"id":rid}); print("  status",r["status"],"roll",rolls_of(rid))
print("  SPK",[(i.get("number"),i.get("status")) for i in d.inspections.find({"ref_doc_id":rid})])
call("GET",f"/sales-returns/{rid}/roll-settlement","manager",ent=E,show=260)
call("POST",f"/sales-returns/{rid}/roll-settlement/back-shipment","warehouse",{"roll_ids":[roll]},ent=E,show=260)
call("GET",f"/sales-returns/{rid}/quarantine","warehouse",ent=E,show=260)
call("POST",f"/sales-returns/{rid}/quarantine/release","whadmin",{"decisions":[{"roll_id":roll,"action":"release"}],"notes":TAG},ent=E,show=260)
print("  akhir",rolls_of(rid))
call("GET","/sales-returns/returnable","salesadmin",q={"order_id":r["order_id"]},ent=E,show=10)
mk_ret("KSC/SO-00004")
