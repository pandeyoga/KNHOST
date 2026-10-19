"""L06 LN-060 sample_kind (standard/hanger) on POS sample SO + L08 LN-080 returns-hub access modules."""
import os

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
db = MongoClient(os.environ.get("MONGO_URL"))[os.environ.get("DB_NAME")]
CREATED = []


def _login(email, pw="demo1234"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=20)
    r.raise_for_status()
    tok = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture(scope="module")
def ctx():
    admin = _login("admin@kainnusantara.id", "demo12345")
    roll = db.inventory_rolls.find_one({"status": "available", "owner_entity_id": "ent_ksc", "length_remaining": {"$gte": 10}}, {"_id": 0})
    if not roll:
        pytest.skip("no roll")
    prod = db.products.find_one({"id": roll["product_id"], "base_unit": "yard"}, {"_id": 0})
    if not prod:
        roll2 = None
        for r in db.inventory_rolls.find({"status": "available", "owner_entity_id": "ent_ksc", "length_remaining": {"$gte": 10}}, {"_id": 0}).limit(200):
            p = db.products.find_one({"id": r["product_id"], "base_unit": "yard"}, {"_id": 0})
            if p:
                prod, roll2 = p, r
                break
        if not prod:
            pytest.skip("no yard product")
    cust = db.customers.find_one({"entity_id": "ent_ksc", "addresses.0": {"$exists": True}}, {"_id": 0})
    yield {"admin": admin, "prod": prod, "cust": cust}
    for oid in CREATED:
        requests.post(f"{BASE}/sales-orders/{oid}/cancel", json={"reason": "TEST cleanup sample kind"}, headers=admin, timeout=20)


def _so(ctx, qty, kind):
    p, c = ctx["prod"], ctx["cust"]
    return requests.post(f"{BASE}/sales-orders", headers=ctx["admin"], timeout=30, json={
        "customer_id": c["id"], "shipping_address_id": c["addresses"][0]["id"], "entity_id": "ent_ksc",
        "notes": "TEST_L06 sample kind", "order_type": "sample", "sample_billing": "free",
        "items": [{"product_id": p["id"], "quantity": qty, "unit": p["base_unit"], "is_sample": True,
                   "sample_price": 1000, "sample_kind": kind}]})


# Sample SO hanger 0.5 yard accepted & persisted sample_kind
def test_hanger_sample_persisted(ctx):
    r = _so(ctx, 0.5, "hanger")
    assert r.status_code == 200, r.text
    so = r.json()
    CREATED.append(so["id"])
    assert so["items"][0]["sample_kind"] == "hanger"
    doc = db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert doc["items"][0]["sample_kind"] == "hanger" and doc["items"][0]["is_sample"]


# Hanger above 0.5 yard rejected
def test_hanger_over_limit_rejected(ctx):
    r = _so(ctx, 1.0, "hanger")
    if r.status_code == 200:
        CREATED.append(r.json()["id"])
    assert r.status_code in (400, 422), r.text


# Standard 5 yard OK, 5.5 rejected
def test_standard_limits(ctx):
    r = _so(ctx, 5, "standard")
    assert r.status_code == 200, r.text
    CREATED.append(r.json()["id"])
    assert r.json()["items"][0]["sample_kind"] == "standard"
    r2 = _so(ctx, 5.5, "standard")
    if r2.status_code == 200:
        CREATED.append(r2.json()["id"])
    assert r2.status_code in (400, 422)


# Unknown kind rejected
def test_unknown_kind(ctx):
    r = _so(ctx, 0.5, "bogus")
    if r.status_code == 200:
        CREATED.append(r.json()["id"])
    assert r.status_code in (400, 422)


# Sales user can also create hanger sample order
def test_sales_user_hanger(ctx):
    h = _login("sales@kainnusantara.id")
    p, c = ctx["prod"], ctx["cust"]
    r = requests.post(f"{BASE}/sales-orders", headers=h, timeout=30, json={
        "customer_id": c["id"], "shipping_address_id": c["addresses"][0]["id"], "entity_id": "ent_ksc",
        "notes": "TEST_L06 sales hanger", "order_type": "sample", "sample_billing": "free",
        "items": [{"product_id": p["id"], "quantity": 0.5, "unit": p["base_unit"], "is_sample": True, "sample_kind": "hanger"}]})
    if r.status_code == 200:
        CREATED.append(r.json()["id"])
        assert r.json()["items"][0]["sample_kind"] == "hanger"
    else:
        pytest.fail(f"sales hanger sample failed {r.status_code} {r.text[:300]}")
