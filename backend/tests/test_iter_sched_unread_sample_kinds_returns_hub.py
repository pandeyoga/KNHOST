"""Sesi: scheduler summary unread, sample kinds (limit/mixed/catalogue/knit), returns-hub endpoint access per role."""
import os

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
db = MongoClient(os.environ.get("MONGO_URL"))[os.environ.get("DB_NAME")]
CREATED = []


def _login(email, pw="demo1234"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=20)
    if r.status_code != 200 and pw == "demo1234":
        r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=20)
    r.raise_for_status()
    tok = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture(scope="module")
def admin():
    h = _login("admin@kainnusantara.id", "demo12345")
    yield h
    for oid in CREATED:
        requests.post(f"{BASE}/sales-orders/{oid}/cancel", json={"reason": "TEST cleanup sesi sample"}, headers=h, timeout=20)


@pytest.fixture(scope="module")
def cust():
    c = db.customers.find_one({"entity_id": "ent_ksc", "addresses.0": {"$exists": True}}, {"_id": 0})
    if not c:
        pytest.skip("no customer")
    return c


def _yard_prod(fabric="woven"):
    for r in db.inventory_rolls.find({"status": "available", "owner_entity_id": "ent_ksc", "length_remaining": {"$gte": 10}}, {"_id": 0}).limit(500):
        p = db.products.find_one({"id": r["product_id"]}, {"_id": 0})
        if not p:
            continue
        ft = str(p.get("fabric_type") or "woven").lower()
        if fabric == "woven" and ft == "woven" and (p.get("base_unit") or "yard") == "yard":
            return p
        if fabric == "knit" and ft == "knit":
            return p
    return None


def _so(h, c, items, order_type="sample"):
    body = {"customer_id": c["id"], "shipping_address_id": c["addresses"][0]["id"], "entity_id": "ent_ksc",
            "notes": "TEST_sesi sample", "order_type": order_type, "items": items}
    if order_type == "sample":
        body["sample_billing"] = "free"
    return requests.post(f"{BASE}/sales-orders", headers=h, json=body, timeout=40)


# Scheduler summary: notifications_unread == mongo count (read!=true & read_by empty)
def test_scheduler_unread_matches_mongo(admin):
    r = requests.get(f"{BASE}/scheduler/summary", headers=admin, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    expected = db.notifications.count_documents({"read": {"$ne": True}, "read_by.0": {"$exists": False}})
    assert d["notifications_unread"] == expected
    assert "escalation" in d


# Standard over 5 yd -> 400 SAMPLE_LIMIT; hanger over 0.5 -> 400 SAMPLE_LIMIT
@pytest.mark.parametrize("kind,qty,maxq", [("standard", 5.5, 5.0), ("hanger", 0.6, 0.5)])
def test_sample_limit_code(admin, cust, kind, qty, maxq):
    p = _yard_prod()
    if not p:
        pytest.skip("no woven yard product")
    r = _so(admin, cust, [{"product_id": p["id"], "quantity": qty, "unit": "yard", "is_sample": True, "sample_kind": kind}])
    if r.status_code == 200:
        CREATED.append(r.json()["id"])
    assert r.status_code == 400, r.text
    det = r.json()["detail"]
    assert det["code"] == "SAMPLE_LIMIT" and det["max_qty"] == maxq and det["kind"] == kind


# Regular order with is_sample line -> SAMPLE_MIXED
def test_sample_mixed(admin, cust):
    p = _yard_prod()
    r = _so(admin, cust, [{"product_id": p["id"], "quantity": 1, "unit": "yard", "is_sample": True},
                          {"product_id": p["id"], "quantity": 10, "unit": "yard"}], order_type="regular")
    if r.status_code == 200:
        CREATED.append(r.json()["id"])
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "SAMPLE_MIXED"


# Kinds endpoint exposes 3 kinds
def test_kinds(admin):
    r = requests.get(f"{BASE}/sample-orders/kinds", headers=admin, timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert set(d["kinds"]) == {"standard", "hanger", "catalogue"}
    assert d["catalogue"]["base_qty"] == 1 and d["catalogue"]["soft_qty"] == 2


# Catalogue: templates -> preview -> create SO -> appears in /sample-orders
def test_catalogue_create_flow(admin, cust):
    r = requests.get(f"{BASE}/sample-orders/catalogue/templates", headers=admin, timeout=30)
    assert r.status_code == 200, r.text
    tpls = r.json()
    if not tpls:
        pytest.skip("no catalogue templates")
    chosen = None
    for t in tpls[:20]:
        pv = requests.get(f"{BASE}/sample-orders/catalogue/preview", params={"template_id": t["id"]}, headers=admin, timeout=30)
        if pv.status_code == 200 and pv.json()["base"]:
            chosen = (t, pv.json())
            break
    assert chosen, "no previewable template"
    t, pv = chosen
    soft = None
    for b in pv["base"]:
        pv2 = requests.get(f"{BASE}/sample-orders/catalogue/preview", params={"template_id": t["id"], "soft_product_id": b["product_id"]},
                           headers=admin, timeout=30)
        if pv2.status_code == 200:
            soft = pv2.json()
            break
    assert soft and soft["soft"], "no soft color possible"
    assert soft["total_qty"] == len(soft["base"]) + 2
    body = {"customer_id": cust["id"], "shipping_address_id": cust["addresses"][0]["id"], "entity_id": "ent_ksc",
            "notes": "TEST_sesi catalogue", "order_type": "sample", "sample_billing": "free",
            "catalogue": {"template_id": t["id"], "soft_product_id": soft["soft"]["product_id"]}, "items": []}
    r = requests.post(f"{BASE}/sales-orders", headers=admin, json=body, timeout=60)
    assert r.status_code == 200, r.text
    so = r.json()
    CREATED.append(so["id"])
    assert all(i.get("sample_kind") == "catalogue" for i in so["items"])
    assert abs(sum(i["quantity"] for i in so["items"]) - soft["total_qty"]) < 0.01
    lst = requests.get(f"{BASE}/sample-orders", headers=admin, timeout=30).json()
    assert any(o["id"] == so["id"] for o in lst)


# Catalogue for knit (kg) template rejected CATALOGUE_UNIT
def test_catalogue_knit_rejected(admin):
    p = db.products.find_one({"base_unit": "kg", "template_id": {"$nin": ["", None]}}, {"_id": 0})
    if not p:
        pytest.skip("no kg product")
    r = requests.get(f"{BASE}/sample-orders/catalogue/preview", params={"template_id": p["template_id"]}, headers=admin, timeout=30)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "CATALOGUE_UNIT"


# Returns hub API access per role
@pytest.mark.parametrize("email,path,ok", [
    ("sales@kainnusantara.id", "/sales-returns", True),
    ("finance@kainnusantara.id", "/interco/returns", True),
])
def test_returns_access(email, path, ok):
    h = _login(email)
    r = requests.get(f"{BASE}{path}", headers=h, timeout=30)
    print(email, path, r.status_code)
    assert (r.status_code == 200) == ok, r.text[:300]
