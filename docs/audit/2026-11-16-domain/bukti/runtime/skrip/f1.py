from flow import *
print("== F-S1 / prasyarat D: SO roll-mode KSC woven 2 roll → kirim → terkirim")
so,p,rolls,c=make_so()
print("produk",p["sku"],p.get("stage"),"rolls",rolls,"cust",c["name"])
if "id" in so:
    push(so["id"]); snap(so["id"])
