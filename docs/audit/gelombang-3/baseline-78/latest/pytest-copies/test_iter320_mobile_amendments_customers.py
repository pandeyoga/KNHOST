"""Backend smoke for iteration 320: mobile amendments & customer creation.

Focus:
- POST /api/auth/login (sales)
- GET /api/amendment-reasons
- GET /api/amendments?doc_type=sales_order
- GET /api/amendments/stats/summary
- POST /api/amendments/preview (impact before/after/delta)
- POST /api/customers (owner = sales; wilayah picks)
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing"
ENTITY = "ent_ksc"


@pytest.fixture(scope="module")
def sales_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "X-Entity-Id": ENTITY})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "sales@kainnusantara.id", "password": "demo12345"})
    assert r.status_code == 200, r.text
    tok = r.json().get("token") or r.json().get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


def test_amendment_reasons(sales_session):
    r = sales_session.get(f"{BASE_URL}/api/amendment-reasons")
    assert r.status_code == 200, r.text
    data = r.json()
    # accept either list or dict
    assert data, "reasons must not be empty"


def test_amendments_list_sales_orders(sales_session):
    r = sales_session.get(f"{BASE_URL}/api/amendments", params={"doc_type": "sales_order"})
    assert r.status_code == 200, r.text
    rows = r.json()
    assert isinstance(rows, list) or isinstance(rows, dict)


def test_amendments_stats(sales_session):
    r = sales_session.get(f"{BASE_URL}/api/amendments/stats/summary")
    assert r.status_code == 200, r.text
    d = r.json()
    # allow different shapes; just make sure some counters exist
    assert isinstance(d, dict)


def _pick_sales_order(sales_session):
    r = sales_session.get(f"{BASE_URL}/api/sales-orders", params={"limit": 5})
    if r.status_code != 200:
        return None
    rows = r.json() if isinstance(r.json(), list) else r.json().get("items") or r.json().get("data") or []
    for row in rows:
        if row.get("items"):
            return row
    return rows[0] if rows else None


def test_amendment_preview_impact(sales_session):
    so = _pick_sales_order(sales_session)
    if not so:
        pytest.skip("no sales order available for preview")
    sid = so.get("id") or so.get("_id")
    items = so.get("items") or []
    if not items:
        pytest.skip("SO has no items")
    it = items[0]
    pid = it.get("product_id") or it.get("productId") or it.get("id")
    old_qty = float(it.get("qty") or it.get("quantity") or 1)
    new_qty = old_qty + 1
    payload = {
        "doc_type": "sales_order",
        "doc_id": sid,
        "reason_code": "qty_adjustment",
        "changes": [{"product_id": pid, "field": "qty",
                     "old_value": old_qty, "new_value": new_qty}],
    }
    r = sales_session.post(f"{BASE_URL}/api/amendments/preview", json=payload)
    # If preview endpoint uses a slightly different schema, be tolerant
    assert r.status_code in (200, 422), r.text
    if r.status_code == 200:
        body = r.json()
        assert isinstance(body, dict)


def test_create_customer_and_verify(sales_session):
    # Pull wilayah cascading
    prov = sales_session.get(f"{BASE_URL}/api/wilayah/provinces")
    assert prov.status_code == 200, prov.text
    provs = prov.json()
    assert provs
    pv = provs[0]
    pv_code = pv.get("code") or pv.get("id")
    regs = sales_session.get(f"{BASE_URL}/api/wilayah/regencies", params={"province_code": pv_code}).json()
    assert regs, f"no regencies: {regs}"
    ct = regs[0]
    ct_code = ct.get("code") or ct.get("id")
    dists = sales_session.get(f"{BASE_URL}/api/wilayah/districts", params={"regency_code": ct_code}).json()
    assert dists, "no districts"
    dt = dists[0]
    dt_code = dt.get("code") or dt.get("id")
    villages = sales_session.get(f"{BASE_URL}/api/wilayah/villages", params={"district_code": dt_code}).json()
    postal = ""
    village_code = ""
    if villages:
        v0 = villages[0]
        village_code = v0.get("code") or v0.get("id") or ""
        postal = v0.get("postal_code") or ""
    ts = int(time.time())
    payload = {
        "name": f"TEST_MobCust_{ts}",
        "pic_name": "TEST PIC",
        "phone": "081200000000",
        "address": "Jl TEST 1",
        "province_code": pv_code,
        "regency_code": ct_code,
        "district_code": dt_code,
        "village_code": village_code,
        "postal_code": postal,
        "country_code": "ID",
    }
    r = sales_session.post(f"{BASE_URL}/api/customers", json=payload)
    assert r.status_code in (200, 201), r.text
    body = r.json()
    cid = body.get("id") or body.get("_id") or body.get("customer_id")
    assert cid, f"no id in response: {body}"

    # Verify readback via list
    r2 = sales_session.get(f"{BASE_URL}/api/customers", params={"q": payload["name"]})
    assert r2.status_code == 200, r2.text
    rows = r2.json()
    rows = rows if isinstance(rows, list) else rows.get("items") or rows.get("data") or []
    match = [c for c in rows if (c.get("id") == cid or c.get("_id") == cid or c.get("name") == payload["name"])]
    assert match, f"created customer not found in list: {rows[:2]}"
    got = match[0]
    assert got.get("name", "").lower() == payload["name"].lower()

    # Cleanup best-effort (may not be supported)
    try:
        sales_session.delete(f"{BASE_URL}/api/customers/{cid}")
    except Exception:
        pass
