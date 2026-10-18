"""L02 LN-022 retest (iteration_211): evidence-form path (/price-approvals draft→attach→submit) bound to SO gate,
non-admin requesters, SoD, reject mirror, stale via /price-approvals, concurrent submits."""
import os
import concurrent.futures as cf

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ENT = "ent_ksc"
P1, P2 = [r["_id"] for r in DB.inventory_rolls.aggregate([
    {"$match": {"status": "available", "owner_entity_id": ENT, "unit": "yard"}},
    {"$group": {"_id": "$product_id", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 2}])]
ADDR = (DB.customers.find_one({"id": "cust_butik_bali"}) or {}).get("addresses", [{}])[0].get("id")
CREATED = []
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _tok(email):
    pwd = "demo12345" if email.startswith("admin@") else "demo1234"
    return requests.post(f"{BASE}/auth/login", json={"email": email, "password": pwd}).json()["token"]


@pytest.fixture(scope="module")
def H():
    hs = {k: {"Authorization": f"Bearer {_tok(v)}", "X-Entity-Id": ENT}
          for k, v in (("admin", "admin@kainnusantara.id"), ("manager", "manager@kainnusantara.id"),
                       ("sa", "salesadmin@kainnusantara.id"))}
    yield hs
    for sid in CREATED:
        requests.post(f"{BASE}/sales-orders/{sid}/cancel", headers=hs["admin"], json={"reason": "TEST_T1 cleanup"})
    DB.price_approvals.delete_many({"so_id": {"$in": CREATED}})
    DB.sales_orders.delete_many({"id": {"$in": CREATED}})


def _so(h):
    r = requests.post(f"{BASE}/sales-orders", headers=h, json={
        "customer_id": "cust_butik_bali", "shipping_address_id": ADDR, "entity_id": ENT,
        "notes": "TEST_T1_L022_FORM", "confirm_mixed_lot": True, "allow_backorder": True,
        "items": [{"product_id": P1, "quantity": 20, "unit": "yard"},
                  {"product_id": P2, "quantity": 20, "unit": "yard"}]})
    assert r.status_code in (200, 201), r.text[:400]
    CREATED.append(r.json()["id"])
    return r.json()


def _draft(h, sid, pid, price):
    d = requests.post(f"{BASE}/price-approvals", headers=h, json={
        "customer_id": "cust_butik_bali", "product_id": pid, "requested_price": price, "reason": "TEST_T1 form",
        "submit_now": False, "entity_id": ENT, "scope": "order", "so_id": sid})
    assert d.status_code == 200, d.text[:300]
    pra = d.json()["id"]
    up = requests.post(f"{BASE}/price-approvals/{pra}/attachments", headers=h,
                       files={"file": ("bukti.png", PNG, "image/png")})
    assert up.status_code == 200, up.text[:300]
    return pra


def _form(h, sid, pid, price):
    pra = _draft(h, sid, pid, price)
    s = requests.post(f"{BASE}/price-approvals/{pra}/submit", headers=h)
    assert s.status_code == 200, s.text[:300]
    assert s.json()["status"] == "pending"
    return pra


def _entry(sid, pra):
    so = DB.sales_orders.find_one({"id": sid}, {"_id": 0})
    return next((p for p in so.get("pending_approvals") or [] if p.get("ref_id") == pra), None), so


# Form path by salesadmin creates SO entry; second form submit supersedes first (SO entry + pra doc)
def test_form_path_salesadmin_and_supersede(H):
    so = _so(H["admin"])
    pra1 = _form(H["sa"], so["id"], P1, 9000)
    e1, _ = _entry(so["id"], pra1)
    assert e1 and e1["status"] == "pending" and e1["alloc_sig"].startswith(P1 + "|")
    pra2 = _form(H["sa"], so["id"], P1, 9500)
    e1, cur = _entry(so["id"], pra1)
    e2, _ = _entry(so["id"], pra2)
    assert e1["status"] == "superseded" and e1["superseded_by"] == e2["id"]
    assert DB.price_approvals.find_one({"id": pra1})["status"] == "superseded"
    assert e2["status"] == "pending"
    # PATCH pending SO-bound -> 409
    p = requests.patch(f"{BASE}/price-approvals/{pra2}", headers=H["sa"], json={"data": {"requested_price": 1}})
    assert p.status_code == 409, p.text[:200]
    # approving superseded pra via /price-approvals -> 409
    a = requests.post(f"{BASE}/price-approvals/{pra1}/approve", headers=H["manager"], json={})
    assert a.status_code == 409, a.text[:200]
    # approve current via /price-approvals as manager
    a = requests.post(f"{BASE}/price-approvals/{pra2}/approve", headers=H["manager"], json={"decision_notes": "ok"})
    assert a.status_code == 200, a.text[:300]
    assert a.json()["status"] == "approved"
    e2, cur = _entry(so["id"], pra2)
    assert e2["status"] == "approved"
    line = next(i for i in cur["items"] if i["product_id"] == P1)
    assert line["price"] == 9500 and line["price_source"] == "special_approval" and line["special_price_id"] == pra2
    assert "saga_lock" not in cur or not cur.get("saga_lock")


# Reject via /price-approvals mirrors into SO entry
def test_reject_via_price_approvals_mirrors_so(H):
    so = _so(H["admin"])
    pra = _form(H["sa"], so["id"], P2, 8000)
    r = requests.post(f"{BASE}/price-approvals/{pra}/reject", headers=H["manager"], json={"decision_notes": "no"})
    assert r.status_code == 200, r.text[:300]
    assert r.json()["status"] == "rejected"
    e, cur = _entry(so["id"], pra)
    assert e["status"] == "rejected"
    assert next(i for i in cur["items"] if i["product_id"] == P2).get("price_source") != "special_approval"


# SoD: manager requests via form, cannot approve own via /price-approvals (403)
def test_sod_own_request_price_approvals_403(H):
    so = _so(H["admin"])
    pra = _form(H["manager"], so["id"], P1, 9100)
    r = requests.post(f"{BASE}/price-approvals/{pra}/approve", headers=H["manager"], json={})
    assert r.status_code == 403, r.text[:300]
    e, _ = _entry(so["id"], pra)
    assert e["status"] == "pending"


# SoD on SO panel path: manager requested; same manager approves via /decide (should also be blocked)
def test_sod_own_request_so_panel(H):
    so = _so(H["admin"])
    pra = _form(H["manager"], so["id"], P2, 9200)
    e, _ = _entry(so["id"], pra)
    r = requests.post(f"{BASE}/sales-orders/{so['id']}/approvals/{e['id']}/decide", headers=H["manager"],
                      json={"decision": "approve", "notes": "self"})
    print("self-approve via SO panel:", r.status_code, r.text[:200])
    assert r.status_code == 403, f"SoD bypass via SO panel: {r.status_code}"


# Stale (qty override) -> approve via /price-approvals 409 'ajukan ulang', no lock left
def test_stale_via_price_approvals_409(H):
    so = _so(H["admin"])
    pra = _form(H["sa"], so["id"], P2, 8800)
    r = requests.post(f"{BASE}/sales-orders/{so['id']}/override", headers=H["admin"],
                      json={"note": "TEST_T1 ubah qty", "lines": [{"product_id": P2, "quantity": 23}]})
    assert r.status_code == 200, r.text[:300]
    a = requests.post(f"{BASE}/price-approvals/{pra}/approve", headers=H["manager"], json={})
    assert a.status_code == 409 and "ajukan ulang" in a.text, a.text[:300]
    cur = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert not cur.get("saga_lock"), cur.get("saga_lock")
    assert DB.price_approvals.find_one({"id": pra})["status"] == "pending"
    # retry same -> still 409 (not locked 'sedang diproses')
    a2 = requests.post(f"{BASE}/price-approvals/{pra}/approve", headers=H["manager"], json={})
    assert a2.status_code == 409 and "ajukan ulang" in a2.text


# Concurrent submits for the same SO/product: no lost entries, exactly one pending
def test_concurrent_submits(H):
    so = _so(H["admin"])
    pras = [_draft(H["sa"], so["id"], P1, 9000 + i) for i in range(3)]
    with cf.ThreadPoolExecutor(3) as ex:
        res = list(ex.map(lambda p: requests.post(f"{BASE}/price-approvals/{p}/submit", headers=H["sa"]), pras))
    codes = [r.status_code for r in res]
    print("concurrent submit codes", codes, [r.text[:120] for r in res if r.status_code != 200])
    assert all(c in (200, 409) for c in codes)
    for r in res:
        if r.status_code == 409:
            assert "diproses" in r.text or "SAGA_IN_PROGRESS" in r.text
    ok = [p for p, r in zip(pras, res) if r.status_code == 200]
    cur = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    sp = [p for p in cur["pending_approvals"] if p["type"] == "special_price"]
    assert sorted(p["ref_id"] for p in sp) == sorted(ok), "lost or extra SO entries"
    assert sum(1 for p in sp if p["status"] == "pending") == 1
    pend_docs = DB.price_approvals.count_documents({"so_id": so["id"], "status": "pending"})
    assert pend_docs == 1, f"{pend_docs} pending pra docs"
    for p, r in zip(pras, res):
        if r.status_code == 409:
            assert DB.price_approvals.find_one({"id": p})["status"] == "draft"
    assert not cur.get("saga_lock")
