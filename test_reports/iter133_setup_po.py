"""Create a fresh PO for P19 iter 133 GRN-01 full-UI test."""
import os, json, requests
BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://textile-erp-uat.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
ENT = "ent_ksc"
s = requests.Session()
r = s.post(f"{API}/auth/login", json={"email":"admin@kainnusantara.id","password":"demo12345"})
tok = r.json()["token"]
s.headers.update({"Authorization": f"Bearer {tok}", "X-Entity-Id": ENT, "Content-Type":"application/json"})

# find Cirebon Craft
sup = s.get(f"{API}/suppliers", params={"q":"Cirebon"}).json()
items = sup if isinstance(sup, list) else sup.get("items", [])
cirebon = None
for x in items:
    name = x.get("name","")
    if "Cirebon" in name:
        if x.get("entity_id") == ENT:
            cirebon = x; break
        if cirebon is None:
            cirebon = x
print("Supplier:", cirebon.get("id"), cirebon.get("name"), "ent=", cirebon.get("entity_id"))

po_body = {
    "supplier_id": cirebon["id"],
    "warehouse_id": "wh_jakarta",
    "notes": "TEST_P19 GRN UI iter133",
    "items": [{"product_id":"prod_batik_mega","quantity":50,"unit":"yard","price":100000,"expected_grade":"A"}]
}
r = s.post(f"{API}/purchase-orders", json=po_body)
print("PO create:", r.status_code, r.text[:300])
po = r.json()
print(json.dumps({"id":po.get("id"),"number":po.get("number") or po.get("po_number"),"status":po.get("status")}, indent=2))
with open("/tmp/iter133_po.json","w") as f: json.dump(po, f)

# approve if needed
pid = po["id"]
# check status
got = s.get(f"{API}/purchase-orders/{pid}").json()
print("PO status after create:", got.get("status"))
if got.get("status") in ("draft","pending_approval","submitted"):
    for action in ("submit","approve"):
        rr = s.post(f"{API}/purchase-orders/{pid}/{action}")
        print(action, rr.status_code, rr.text[:200])
got = s.get(f"{API}/purchase-orders/{pid}").json()
print("PO final status:", got.get("status"), "number:", got.get("number") or got.get("po_number"))
with open("/tmp/iter133_po.json","w") as f: json.dump(got, f)
