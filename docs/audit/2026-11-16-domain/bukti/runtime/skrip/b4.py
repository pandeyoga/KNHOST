from b1 import *
a="mko_e50c274be5c3"; m=d.makloon_orders.find_one({"id":a}); s=m["steps"][0]
print("  MKO-00004 step printing: stage_from_stage",s.get("stage_from_stage"),"stage_to_stage",s.get("stage_to_stage"),"| bahan masuk stage:",P("DMO-GRY-KNT-001")["stage"])
def stock(): return round(sum(r["length_remaining"] for r in d.inventory_rolls.find({"product_id":P("DMO-GRY-KNT-001")["id"],"owner_entity_id":C,"status":"available"})),1), d.inventory_rolls.count_documents({"product_id":P("DMO-GRY-KNT-001")["id"],"owner_entity_id":C,"status":{"$in":["at_subcon","subcon","in_subcon","issued_makloon"]}}), sorted(set(r["status"] for r in d.inventory_rolls.find({"product_id":P("DMO-GRY-KNT-001")["id"],"owner_entity_id":C})))
print("  stok greige (tersedia, di mitra, status2)",stock())
print("== B-S6 batal saat bahan 50 kg sudah di mitra")
call("POST",f"/makloon-orders/{a}/cancel","manager",{"reason":TAG+" batal di tengah"},ent=C,show=300)
ms(a); JJ(2); print("  stok greige",stock())
call("POST",f"/makloon-orders/{a}/steps/1/return-material","manager",{"qty":50,"warehouse_id":W("RCM-KNITTING"),"reason":TAG+" bahan ditarik"},ent=C,show=300)
call("POST",f"/makloon-orders/{a}/cancel","manager",{"reason":TAG+" batal di tengah"},ent=C,show=300)
ms(a); JJ(2); print("  stok greige",stock())
print("== B-S5/B-S8 klaim susut MKO-00006: nilai saran vs nilai sebenarnya")
call("POST","/makloon-orders/mko_d8f1975c5d85/claim","manager",{"step_seq":1,"action":"claim","amount":10880000,"reason":TAG+" klaim sesuai saran sistem"},ent=C,show=300)
