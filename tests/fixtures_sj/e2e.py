import sys, json, requests, time
B = "http://localhost:8001/api"
T = requests.post(f"{B}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}).json()["token"]
H = {"Authorization": f"Bearer {T}", "X-Entity-Id": "ent_ksc"}
f = sys.argv[1]
g = requests.post(f"{B}/goods-receipts", headers=H, json={"partner_type": "supplier", "partner_id": "sup_44c069fa4f55", "warehouse_id": "wh_jakarta"})
g.raise_for_status(); g = g.json()
u = requests.post(f"{B}/goods-receipts/{g['id']}/files", headers=H, files={"file": (f.split('/')[-1], open(f, "rb"), "image/jpeg")}, data={"expected_version": g["version"]})
u.raise_for_status(); g = u.json()["grn"]
t0 = time.time()
r = requests.post(f"{B}/goods-receipts/{g['id']}/read", headers=H, json={"expected_version": g["version"]}, timeout=180)
print(f, r.status_code, f"{time.time()-t0:.1f}s")
d = r.json(); ex = d.get("extraction", {})
print(" status", d.get("status"), "failed", ex.get("read_failed"), ex.get("error_code"), ex.get("error_message"))
print(" orientation", ex.get("orientation"), "runs", [(x.get("model"), x.get("role"), x.get("status")) for x in ex.get("runs", [])])
print(" dn", json.dumps(d.get("dn"), ensure_ascii=False)[:400])
for l in d.get("lines", []): print("  line", json.dumps({k: l.get(k) for k in ("description", "po_ref", "qty", "unit", "rolls")}, ensure_ascii=False)[:300])
print(" warnings", ex.get("warnings"))
