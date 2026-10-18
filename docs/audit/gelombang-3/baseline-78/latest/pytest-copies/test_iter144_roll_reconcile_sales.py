"""Iter144 — Sales role calling preview-roll-reconcile with all_entities=true must NOT 403.

The fix (sales_orders_extra.py preview_roll_reconcile) silently downgrades all_entities
for non-cross-entity roles instead of 403'ing.
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8006").rstrip("/")


def _login(email: str, password: str = "demo12345") -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    j = r.json()
    return j.get("token") or j.get("access_token")


@pytest.fixture(scope="module")
def sales_headers():
    tok = _login("sales@kainnusantara.id")
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_headers():
    tok = _login("admin@kainnusantara.id")
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _any_product_id(headers):
    r = requests.get(f"{BASE_URL}/api/products?entity=ent_ksc&limit=5", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else (data.get("items") or data.get("data") or [])
    for p in items:
        pid = p.get("id") or p.get("_id") or p.get("product_id")
        if pid:
            return pid, p.get("selling_unit") or p.get("unit") or "meter"
    pytest.skip("no products available")


def test_sales_roll_reconcile_all_entities_true_no_403(sales_headers):
    """Core fix: all_entities=true as sales must NOT 403 — should silently downgrade and 200."""
    pid, unit = _any_product_id(sales_headers)
    r = requests.post(
        f"{BASE_URL}/api/sales-orders/preview-roll-reconcile",
        headers=sales_headers,
        json={
            "entity_id": "ent_ksc",
            "all_entities": True,
            "items": [{"product_id": pid, "target_qty": 25, "selling_unit": unit}],
        },
        timeout=30,
    )
    assert r.status_code != 403, f"regression: 403 returned. body={r.text[:300]}"
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:300]}"
    body = r.json()
    assert isinstance(body, list)


def test_sales_roll_reconcile_all_entities_false_still_200(sales_headers):
    pid, unit = _any_product_id(sales_headers)
    r = requests.post(
        f"{BASE_URL}/api/sales-orders/preview-roll-reconcile",
        headers=sales_headers,
        json={
            "entity_id": "ent_ksc",
            "all_entities": False,
            "items": [{"product_id": pid, "target_qty": 25, "selling_unit": unit}],
        },
        timeout=30,
    )
    assert r.status_code == 200
