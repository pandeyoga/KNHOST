import json
b=json.load(open("before.json")); a=json.load(open("after.json"))
print(len(b["users"]), b["users"])
rows=[];diff=[];nz=0;errs=0;orders=set();nlines=0
for k in sorted(b["data"]):
    x,y=b["data"][k],a["data"][k]
    if x["error"] or y["error"]: errs+=1
    tx,ty=x["total_incentive"] or 0,y["total_incentive"] or 0
    if tx or ty: nz+=1
    for l in y["lines"]:
        nlines+=1; orders.add(l["order_id"])
    lb=json.dumps(x["lines"],sort_keys=True); la=json.dumps(y["lines"],sort_keys=True)
    rows.append((k,tx,ty,ty-tx,lb==la))
    if tx!=ty or lb!=la: diff.append(k)
print("combos",len(rows),"nonzero",nz,"errors",errs,"lines",nlines,"orders",len(orders),"diff",diff)
print("payroll", b["payroll_engine"], a["payroll_engine"])
print({k:v for k,v in a.items() if k.startswith("count")}, {k:v for k,v in b.items() if k.startswith("count")})
print("keys before",b["data"][rows[0][0]]["keys"]); print("keys after",a["data"][rows[0][0]]["keys"])
for r in rows:
    if r[1] or r[2]: print(r)
print(set(v["error"] for v in a["data"].values()), set(v["error"] for v in b["data"].values()))
print([ (k,v["carry_in"],v["carry_out"],v["commission_raw"]) for k,v in a["data"].items() if v["carry_in"] or v["carry_out"]][:5])
