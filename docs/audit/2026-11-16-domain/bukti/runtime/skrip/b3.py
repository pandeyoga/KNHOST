from b1 import *
mid="mko_d8f1975c5d85"; m=d.makloon_orders.find_one({"id":mid},{"_id":0}); s1=m["steps"][0]
print("  step1",{k:s1.get(k) for k in s1 if any(x in k for x in("qty","loss","yield","susut","cost","rate","status","claim","stage","partial"))})
print("  SPK",{k:m.get(k) for k in m if any(x in k for x in("loss","claim","cost","status","total"))})
rl=list(d.inventory_rolls.find({"$or":[{"makloon_order_id":mid},{"source_ref.id":mid},{"mko_id":mid}]},{"_id":0}))
print("  roll hasil",[(r.get("roll_no"),r["status"],r.get("stage"),r.get("length_remaining"),r.get("unit"),r.get("unit_cost"),r.get("lot")) for r in rl])
print("  loss/claim docs",{c:d[c].count_documents({}) for c in d.list_collection_names() if "makloon" in c or "subcon" in c})
print("  vendor bill jasa",[(v.get("bill_number"),v.get("status"),v.get("grand_total"),v.get("source")) for v in d.vendor_bills.find({"$or":[{"mko_id":mid},{"makloon_order_id":mid}]})])
print("-- terima lagi sisa 100 kg (langkah sudah 'received')")
call("POST",f"/makloon-orders/{mid}/receive","manager",{"step_seq":1,"actual_output_qty":100,"output_warehouse_id":W("RCM-KNITTING"),"supplier_dn":"SJ-UJI-2","supplier_invoice_no":"INV-UJI-2","rolls":[{"lot":"UJI-MK2","length":25,"grade":"A","dye_lot":""} for _ in range(4)]},ent=C,show=260)
print("== B-S6 batal di tengah saat bahan sudah di mitra (MKO-00004: printing dari greige)")
a="mko_e50c274be5c3"
call("POST",f"/makloon-orders/{a}/issue","manager",{"step_seq":1,"from_warehouse_id":W("RCM-KNITTING")},ent=C,show=160); ms(a)
import subprocess; print(subprocess.run("grep -nE '@router\\.(post|put|delete)\\(' /app/backend/routers/makloon_orders.py | cut -c1-110",shell=True,capture_output=True,text=True).stdout)
