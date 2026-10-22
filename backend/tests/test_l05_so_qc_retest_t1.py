"""L05 LN-050-T01 retest (T1, iter 197) — real cut-length SO w/ QC full: SPK lines, inspect+finish, dispatch guard,
re-allocation relisting + status reset, SO number field, /wms/tasks/{id}/advance guard."""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ENT = "ent_ksc"
CUST, ADDR, PROD = "cust_butik_bali", "addr_002", "prod_batik_mega"


def _login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def ctx(admin):
    state = {"ids": [], "restore": []}
    yield state
    for sid in state["ids"]:
        requests.post(f"{BASE}/sales-orders/{sid}/cancel", json={"reason": "TEST cleanup T1 retest"}, headers=admin, timeout=60)
        DB.inspections.delete_many({"ref_doc_id": sid})
        DB.wms_tasks.delete_many({"order_id": sid, "_test_t1": True})
    for doc in state["restore"]:
        DB.inventory_rolls.replace_one({"id": doc["id"]}, doc)


def _alloc(sid):
    return list(DB.inventory_rolls.find({"$or": [{"reserved_ref.id": sid, "status": "reserved"},
                                                 {"length_reservations": {"$elemMatch": {"ref.id": sid, "status": "reserved"}}}]},
                                        {"_id": 0}))


def _refdocs(h):
    return requests.get(f"{BASE}/inspections/meta/ref-docs", params={"kind": "sales_order"}, headers=h, timeout=30).json()["items"]


def _finish(h, doc, decision):
    uid = DB.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0, "id": 1})["id"]
    requests.post(f"{BASE}/inspections/{doc['id']}/assign", json={"assigned_to": uid}, headers=h, timeout=30)
    requests.post(f"{BASE}/inspections/{doc['id']}/start", json={}, headers=h, timeout=30)
    for ln in doc["lines"]:
        r = requests.post(f"{BASE}/inspections/{doc['id']}/lines/{ln['id']}/inspect",
                          json={"part": "qc", "grade": "A", "defects": [], "inspect_length_yard": 10}, headers=h, timeout=30)
        assert r.status_code == 200, r.text[:200]
    return requests.post(f"{BASE}/inspections/{doc['id']}/finish", json={"decision": decision, "remark": "TEST T1 alasan keputusan"},
                         headers=h, timeout=30)


def test_real_cut_length_full_flow(admin, ctx):
    r = requests.post(f"{BASE}/sales-orders", json={
        "customer_id": CUST, "shipping_address_id": ADDR, "entity_id": ENT, "qc_request": "full",
        "items": [{"product_id": PROD, "quantity": 10.0, "unit": "yard", "base_quantity": 10.0}]}, headers=admin, timeout=120)
    assert r.status_code == 200, r.text[:300]
    so = r.json()
    sid = so["id"]
    ctx["ids"].append(sid)
    ctx["sid"] = sid
    number = DB.sales_orders.find_one({"id": sid})["number"]
    assert number
    alloc = _alloc(sid)
    print("alloc:", [(a["id"], a["status"], a.get("length_reservations")) for a in alloc])
    assert alloc, "real cut-length SO has no allocated roll"
    cut = [a for a in alloc if any(lr.get("ref", {}).get("id") == sid for lr in a.get("length_reservations") or [])]
    assert cut, "expected a length_reservation (partial roll) allocation"
    # picker label contains SO number
    opt = [o for o in _refdocs(admin) if o["value"] == sid]
    assert opt and number in opt[0]["label"], opt
    # guard message with number
    tid = f"wt_t1_{uuid.uuid4().hex[:8]}"
    DB.wms_tasks.insert_one({"id": tid, "flow_type": "outbound", "status": "staging", "entity_id": ENT,
                             "stages": ["created", "picking", "packing", "staging", "dispatched"],
                             "order_id": sid, "order_number": number, "product_id": PROD, "warehouse_id": alloc[0].get("warehouse_id"),
                             "quantity": 10, "picked_qty": 10, "shipped_qty": 0, "unit": "yard", "_test_t1": True})
    ctx["tid"] = tid
    d = requests.post(f"{BASE}/outbound/tasks/{tid}/dispatch", headers=admin, timeout=60)
    assert d.status_code == 400 and f"Pesanan {number} meminta QC" in d.text, d.text[:300]
    a = requests.post(f"{BASE}/wms/tasks/{tid}/advance", headers=admin, timeout=60)
    assert a.status_code == 400 and "meminta QC" in a.text, a.text[:300]
    assert DB.wms_tasks.find_one({"id": tid})["status"] == "staging"
    # SPK with the cut roll
    s = requests.post(f"{BASE}/inspections", json={"kind": "sales_order", "ref_doc_id": sid}, headers=admin, timeout=30)
    assert s.status_code == 200, s.text[:300]
    doc = s.json()
    assert doc["ref_doc_number"] == number
    assert {ln["roll_id"] for ln in doc["lines"]} == {a["id"] for a in alloc}
    f = _finish(admin, doc, "terima")
    assert f.status_code == 200, f.text[:300]
    assert DB.sales_orders.find_one({"id": sid})["qc_request"]["status"] == "passed"
    assert sid not in [o["value"] for o in _refdocs(admin)]
    d2 = requests.post(f"{BASE}/outbound/tasks/{tid}/dispatch", headers=admin, timeout=60)
    print("dispatch after QC:", d2.status_code, d2.text[:300])
    assert "meminta QC" not in d2.text and "belum di-QC" not in d2.text
    ctx["dispatched"] = d2.status_code == 200


def test_reallocation_relists_and_resets(admin, ctx):
    sid = ctx.get("sid")
    if not sid or ctx.get("dispatched"):
        pytest.skip("previous flow not available / already dispatched")
    taken = [a["id"] for a in _alloc(sid)]
    extra = DB.inventory_rolls.find_one({"status": "available", "owner_entity_id": ENT, "id": {"$nin": taken},
                                         "length_reservations.0": {"$exists": False}}, {"_id": 0})
    ctx["restore"].append(extra)
    DB.inventory_rolls.update_one({"id": extra["id"]}, {"$set": {"status": "reserved", "reserved_ref": {"type": "sales_order", "id": sid}}})
    print("SO state:", DB.sales_orders.find_one({"id": sid}, {"_id": 0, "status": 1, "qc_request.status": 1}),
          "extra:", extra["id"], DB.inventory_rolls.find_one({"id": extra["id"]}, {"_id": 0, "status": 1, "reserved_ref": 1}))
    assert sid in [o["value"] for o in _refdocs(admin)]
    a = requests.post(f"{BASE}/wms/tasks/{ctx['tid']}/advance", headers=admin, timeout=60)
    assert a.status_code == 400 and "belum di-QC" in a.text, a.text[:300]
    assert DB.sales_orders.find_one({"id": sid})["qc_request"]["status"] == "required"
    s = requests.post(f"{BASE}/inspections", json={"kind": "sales_order", "ref_doc_id": sid}, headers=admin, timeout=30)
    assert s.status_code == 200, s.text[:300]
    assert extra["id"] in {ln["roll_id"] for ln in s.json()["lines"]}
    assert _finish(admin, s.json(), "terima").status_code == 200
    assert sid not in [o["value"] for o in _refdocs(admin)]
    d = requests.post(f"{BASE}/outbound/tasks/{ctx['tid']}/dispatch", headers=admin, timeout=60)
    print("dispatch after re-QC:", d.status_code, d.text[:300])
    assert "meminta QC" not in d.text and "belum di-QC" not in d.text
