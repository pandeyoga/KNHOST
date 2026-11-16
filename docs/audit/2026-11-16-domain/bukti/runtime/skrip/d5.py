from d2 import *
print("== D-S4 cutloss sebagian roll (SO-00005 roll0)")
rid,roll,ln=to_inspected("KSC/SO-00005")
r=d.sales_returns.find_one({"id":rid}); pid=r["items"][0]["product_id"]
via_spk(rid,grade="A")
call("POST",f"/sales-returns/{rid}/cutloss","md",{"product_id":pid,"roll_id":roll,"defect_from":10,"defect_to":25,"defect_yard":15,"note":TAG,"treatment":"cut"},ent=E,show=350)
call("POST",f"/sales-returns/{rid}/cutloss","manager",{"product_id":pid,"roll_id":roll,"defect_from":10,"defect_to":25,"defect_yard":15,"note":TAG,"treatment":"cut"},ent=E,show=350)
call("GET",f"/sales-returns/{rid}/compensation","finance",ent=E,show=500)
call("POST",f"/sales-returns/{rid}/compensation","finance",{"lines":[{"kind":"cutloss","product_id":pid,"qty":15,"amount":15*25000}],"note":TAG},ent=E,show=400)
print("-- kompensasi melebihi nilai roll (uji batas): 99 juta")
call("POST",f"/sales-returns/{rid}/compensation","finance",{"lines":[{"kind":"cutloss","product_id":pid,"qty":15,"amount":99000000}],"note":TAG},ent=E,show=300)
s,j=call("GET",f"/sales-returns/{rid}/roll-settlement","manager",ent=E,show=10); print("  opsi",[(o["value"],o["ok"],o.get("why","")[:60]) for o in j["rows"][0]["options"]])
call("POST",f"/sales-returns/{rid}/roll-settlement/preview","manager",{"rolls":[{"roll_id":roll,"outcome":"cutloss"}]},ent=E,show=600)
