"""Create 3 GRNs via API for P19 UAT (PO-A/B/C) — allowed as per brief fallback."""
import os, sys, requests, json
BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE}/api"
ENT = "ent_ksc"

s = requests.Session()
r = s.post(f"{API}/auth/login", json={"email":"admin@kainnusantara.id","password":"demo12345"})
tok = r.json()["token"]
s.headers.update({"Authorization": f"Bearer {tok}", "X-Entity-Id": ENT, "Content-Type":"application/json"})

def ok(r):
    assert r.status_code == 200, f"{r.request.method} {r.url} → {r.status_code} {r.text[:400]}"
    return r.json()

POS = [
    ("po_7199abc8a08c", "KSC/PO-00016", [50], "TEST_P19-SJ-A", "TEST_P19-A"),
    ("po_731de52efd3a", "KSC/PO-00017", [40], "TEST_P19-SJ-B", "TEST_P19-B"),
    ("po_7513a9f0203f", "KSC/PO-00018", [50,50,50], "TEST_P19-SJ-C", "TEST_P19-C"),
]

grns = []
for po_id, po_num, lens, dn, lot in POS:
    tasks = ok(s.get(f"{API}/wms/tasks?po_id={po_id}&flow_type=inbound"))
    task = tasks[0]
    g = ok(s.post(f"{API}/goods-receipts", json={"partner_type":"supplier","partner_id":"sup_0b7c2a9eb7aa","warehouse_id":"wh_jakarta","po_ids":[po_id]}))
    g = ok(s.post(f"{API}/goods-receipts/{g['id']}/manual-entry", json={"expected_version":g["version"]}))
    g = ok(s.patch(f"{API}/goods-receipts/{g['id']}/dn", json={"expected_version":g["version"], "number":dn, "date":"2026-10-03","recipient_name":"TEST_P19"}))
    g = ok(s.post(f"{API}/goods-receipts/{g['id']}/lines", json={
        "expected_version":g["version"],
        "declared":{"qty":sum(lens),"unit":"yard","rolls":len(lens)},
        "target":{"type":"po_task","task_id":task["id"]},
        "description":f"TEST_P19 {po_num}"
    }))
    g = ok(s.post(f"{API}/goods-receipts/{g['id']}/start-count", json={"expected_version":g["version"]}))
    for n in lens:
        ok(s.post(f"{API}/goods-receipts/{g['id']}/lines/1/rolls", json={"length":n,"lot":lot}))
    # refetch version
    g2 = ok(s.get(f"{API}/goods-receipts/{g['id']}"))
    g = ok(s.post(f"{API}/goods-receipts/{g['id']}/finish-count", json={"expected_version":g2["version"]}))
    g = ok(s.post(f"{API}/goods-receipts/{g['id']}/close", json={"expected_version":g["version"]}))
    grn = g.get("grn", g)
    grns.append({"po": po_num, "grn_id": grn["id"], "grn_number": grn.get("number") or grn.get("grn_number"), "status": grn.get("status")})
    print(f"GRN for {po_num}: {grn.get('number') or grn.get('grn_number')} status={grn.get('status')}")

print(json.dumps(grns, indent=2))
with open("/tmp/grns.json","w") as f: json.dump(grns, f)
