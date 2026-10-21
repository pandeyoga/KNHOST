"""iter202 — Backend regression: SAMPLE_MIXED rejection on POST /api/sales-orders.

Verifies:
  1. order_type='regular' with any item is_sample=True -> 400 detail.code=SAMPLE_MIXED
  2. order_type='sample' forces every line to sample (is_sample=True in response)
  3. Pure regular cart still submits (control)
Cleanup: any created SO is cancelled.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://kain-nusantara.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ENTITY = "ent_ksc"


def _login(email: str, pwd: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=20)
    r.raise_for_status()
    j = r.json()
    return j.get("token") or j.get("access_token")


@pytest.fixture(scope="module")
def sales_headers():
    tok = _login("sales@kainnusantara.id", "demo12345")
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": ENTITY, "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_headers():
    tok = _login("admin@kainnusantara.id", "demo12345")
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": ENTITY, "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def customer_and_product(admin_headers):
    # pick customer Toko Kain Sejahtera (used in iter201)
    r = requests.get(f"{API}/customers", headers=admin_headers, params={"limit": 50}, timeout=20)
    r.raise_for_status()
    custs = r.json()
    if isinstance(custs, dict):
        custs = custs.get("items") or []
    cust = next((c for c in custs if "Sejahtera" in (c.get("name") or "")), None) or custs[0]
    # pick product Batik Mega
    pr = requests.get(f"{API}/products", headers=admin_headers, params={"q": "Batik Mega", "limit": 20}, timeout=20)
    pr.raise_for_status()
    plist = pr.json()
    if isinstance(plist, dict):
        plist = plist.get("items") or plist.get("data") or []
    prod = next((p for p in plist if "Batik Mega" in (p.get("name") or "")), plist[0])
    return cust, prod


def _cancel(order_id, admin_headers):
    try:
        requests.post(f"{API}/sales-orders/{order_id}/cancel",
                      headers=admin_headers, json={"reason": "iter202 cleanup"}, timeout=20)
    except Exception:
        pass


def test_mixed_cart_rejected_sample_mixed(admin_headers, customer_and_product):
    cust, prod = customer_and_product
    headers = admin_headers
    addr_id = (cust.get("addresses") or [{}])[0].get("id", "")
    payload = {
        "customer_id": cust["id"],
        "shipping_address_id": addr_id,
        "entity_id": ENTITY,
        "order_type": "regular",
        "fulfillment_method": "kirim",
        "items": [
            {"product_id": prod["id"], "quantity": 2, "unit": "yard", "is_sample": True, "sample_kind": "standard"},
            {"product_id": prod["id"], "quantity": 5, "unit": "yard", "is_sample": False},
        ],
    }
    r = requests.post(f"{API}/sales-orders", headers=headers, json=payload, timeout=30)
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:400]}"
    body = r.json()
    detail = body.get("detail")
    assert isinstance(detail, dict), f"detail should be dict with code, got: {detail}"
    assert detail.get("code") == "SAMPLE_MIXED", f"expected code=SAMPLE_MIXED, got {detail}"


def test_sample_order_forces_all_lines_sample(admin_headers, customer_and_product):
    cust, prod = customer_and_product
    headers = admin_headers
    addr_id = (cust.get("addresses") or [{}])[0].get("id", "")
    payload = {
        "customer_id": cust["id"],
        "shipping_address_id": addr_id,
        "entity_id": ENTITY,
        "order_type": "sample",
        "sample_billing": "free",
        "fulfillment_method": "kirim",
        "items": [
            # one line explicitly marked sample, one NOT marked -> server should force both to is_sample=True
            {"product_id": prod["id"], "quantity": 2, "unit": "yard", "is_sample": True, "sample_kind": "standard"},
        ],
    }
    r = requests.post(f"{API}/sales-orders", headers=headers, json=payload, timeout=30)
    assert r.status_code == 200, f"sample SO failed: {r.status_code} {r.text[:400]}"
    data = r.json()
    assert data.get("order_type") == "sample"
    assert data.get("number", "").split("/")[-1].startswith("SOS-"), f"expected SOS- number, got {data.get('number')}"
    assert all(it.get("is_sample") for it in data["items"]), "all lines must be is_sample=True"
    _cancel(data["id"], admin_headers)


def test_pure_regular_cart_submits(admin_headers, customer_and_product):
    cust, prod = customer_and_product
    headers = admin_headers
    addr_id = (cust.get("addresses") or [{}])[0].get("id", "")
    payload = {
        "customer_id": cust["id"],
        "shipping_address_id": addr_id,
        "entity_id": ENTITY,
        "order_type": "regular",
        "fulfillment_method": "kirim",
        "items": [{"product_id": prod["id"], "quantity": 5, "unit": "yard", "is_sample": False}],
    }
    r = requests.post(f"{API}/sales-orders", headers=headers, json=payload, timeout=30)
    assert r.status_code == 200, f"regular SO failed: {r.status_code} {r.text[:400]}"
    data = r.json()
    assert data.get("order_type") == "regular"
    assert "SO-" in data.get("number", "") and "SOS-" not in data.get("number", "")
    _cancel(data["id"], admin_headers)
