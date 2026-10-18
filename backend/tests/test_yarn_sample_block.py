"""Saring Sampel Benang — produk tahap 'yarn' tidak boleh dipesan sebagai sampel (SAMPLE_NOT_ALLOWED)."""
import os

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
db = MongoClient(os.environ.get("MONGO_URL"))[os.environ.get("DB_NAME")]

YARN_WOVEN = "prod_0e59de47cc17"
YARN_KNIT = "prod_7d64a9436792"
CREATED = []


def _login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=20)
    r.raise_for_status()
    j = r.json()
    return {"Authorization": f"Bearer {j.get('token') or j.get('access_token')}"}


@pytest.fixture(scope="module")
def ctx():
    admin = {**_login("admin@kainnusantara.id", "demo12345"), "X-Entity-Id": "ent_ksc"}
    fab_roll = db.inventory_rolls.find_one({"status": "available", "owner_entity_id": "ent_ksc", "length_remaining": {"$gte": 10},
                                           "product_id": {"$nin": [YARN_WOVEN, YARN_KNIT]}}, {"_id": 0, "product_id": 1})
    fab = db.products.find_one({"id": fab_roll["product_id"]}, {"_id": 0})
    assert str(fab.get("stage") or "").lower() != "yarn"
    cust = db.customers.find_one({"id": "cust_toko_kain"}, {"_id": 0})
    yield {"admin": admin, "fab": fab, "cust": cust}
    for oid in CREATED:
        requests.post(f"{BASE}/sales-orders/{oid}/cancel", json={"reason": "TEST_ cleanup uji sampel benang"}, headers=admin, timeout=20)


def _payload(ctx, items, order_type="sample", billing="free"):
    c = ctx["cust"]
    return {"customer_id": c["id"], "shipping_address_id": c["addresses"][0]["id"], "entity_id": "ent_ksc",
            "order_type": order_type, "sample_billing": billing, "notes": "TEST_yarn_sample", "items": items}


@pytest.mark.parametrize("pid", [YARN_WOVEN, YARN_KNIT])
def test_sample_order_with_yarn_rejected(ctx, pid):
    before = db.sales_orders.count_documents({})
    r = requests.post(f"{BASE}/sales-orders", headers=ctx["admin"], timeout=30, json=_payload(ctx, [
        {"product_id": pid, "quantity": 1, "unit": "kg", "is_sample": True}]))
    assert r.status_code == 400, r.text
    d = r.json()["detail"]
    assert d["code"] == "SAMPLE_NOT_ALLOWED" and d["product_id"] == pid
    assert "benang" in d["message"].lower() and "sampel" in d["message"].lower()
    assert db.sales_orders.count_documents({}) == before


def test_mixed_sample_fabric_plus_yarn_rejected_no_doc(ctx):
    fab = ctx["fab"]
    before = db.sales_orders.count_documents({})
    r = requests.post(f"{BASE}/sales-orders", headers=ctx["admin"], timeout=30, json=_payload(ctx, [
        {"product_id": fab["id"], "quantity": 1, "unit": fab["base_unit"], "is_sample": True},
        {"product_id": YARN_WOVEN, "quantity": 1, "unit": "kg", "is_sample": True}]))
    assert r.status_code == 400 and r.json()["detail"]["code"] == "SAMPLE_NOT_ALLOWED"
    assert db.sales_orders.count_documents({}) == before


def test_fabric_sample_ok(ctx):
    fab = ctx["fab"]
    r = requests.post(f"{BASE}/sales-orders", headers=ctx["admin"], timeout=30, json=_payload(ctx, [
        {"product_id": fab["id"], "quantity": 1, "unit": fab["base_unit"], "is_sample": True}]))
    assert r.status_code == 200, r.text
    so = r.json()
    CREATED.append(so["id"])
    assert so["order_type"] == "sample" and so["items"][0]["is_sample"] is True


def test_regular_yarn_order_by_admin_ok(ctx):
    r = requests.post(f"{BASE}/sales-orders", headers=ctx["admin"], timeout=30, json=_payload(ctx, [
        {"product_id": YARN_WOVEN, "quantity": 1, "unit": "kg"}], order_type="regular", billing=""))
    assert r.status_code == 200, r.text
    CREATED.append(r.json()["id"])
    assert r.json()["items"][0].get("is_sample") in (False, None)


@pytest.mark.parametrize("otype", ["regular", "sample"])
def test_sales_role_yarn_403(otype):
    h = {**_login("sales.kanda@kainnusantara.id", "demo1234"), "X-Entity-Id": "ent_kanda"}
    c = db.customers.find_one({"entity_id": "ent_kanda"}, {"_id": 0})
    r = requests.post(f"{BASE}/sales-orders", headers=h, timeout=30, json={
        "customer_id": c["id"], "shipping_address_id": c["addresses"][0]["id"], "entity_id": "ent_kanda",
        "order_type": otype, "sample_billing": "free" if otype == "sample" else "", "notes": "TEST_yarn_sales",
        "items": [{"product_id": YARN_WOVEN, "quantity": 1, "unit": "kg", "is_sample": otype == "sample"}]})
    print(otype, r.status_code, r.text[:300])
    if r.status_code == 200:
        CREATED.append(r.json()["id"])
    assert r.status_code == 403
    assert "bahan (tahap yarn)" in r.text
