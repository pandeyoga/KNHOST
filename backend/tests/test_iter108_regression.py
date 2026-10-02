"""Regression smoke for iter108: verify login for all roles + a handful of key endpoints for ent_ksc."""
import os, requests, pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://knhost-audit.preview.emergentagent.com").rstrip("/")
API = BASE + "/api"

CREDS = {
    "admin": ("admin@kainnusantara.id", "demo12345"),
    "manager": ("manager@kainnusantara.id", "demo12345"),
    "finance": ("finance@kainnusantara.id", "demo12345"),
    "warehouse": ("warehouse@kainnusantara.id", "demo12345"),
    "sales": ("sales@kainnusantara.id", "demo12345"),
}


def _login(role):
    email, pw = CREDS[role]
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, f"{role} login {r.status_code} {r.text[:200]}"
    s.headers.update({"X-Entity-Id": "ent_ksc"})
    return s


@pytest.mark.parametrize("role", list(CREDS.keys()))
def test_login_ok(role):
    s = _login(role)
    r = s.get(f"{API}/auth/me", timeout=15)
    assert r.status_code == 200


def test_pos_best_sellers_admin():
    s = _login("admin")
    r = s.get(f"{API}/pos/best-sellers", timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, (list, dict))


def test_pos_substitutes_needs_product():
    s = _login("admin")
    # first fetch a product id from best sellers or products list
    r = s.get(f"{API}/products?limit=1", timeout=20)
    if r.status_code == 200:
        items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        if items:
            pid = items[0].get("id") or items[0].get("product_id")
            if pid:
                r2 = s.get(f"{API}/pos/substitutes", params={"product_id": pid}, timeout=20)
                assert r2.status_code in (200, 404), r2.text[:200]


def test_rfid_cycle_counts_warehouse():
    s = _login("warehouse")
    r = s.get(f"{API}/rfid/cycle-counts", timeout=20)
    assert r.status_code == 200


def test_rfid_print_jobs_warehouse():
    s = _login("warehouse")
    r = s.get(f"{API}/rfid/print-jobs", timeout=20)
    assert r.status_code == 200


def test_rfid_devices_admin_no_api_key_field():
    s = _login("admin")
    r = s.get(f"{API}/rfid/devices", timeout=20)
    assert r.status_code == 200
    data = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    for d in data:
        assert "api_key" not in d and "api_key_hash" not in d, f"leaked key in {d}"
        assert "has_api_key" in d


def test_rfid_devices_warehouse_no_api_key_field():
    s = _login("warehouse")
    r = s.get(f"{API}/rfid/devices", timeout=20)
    assert r.status_code == 200
    data = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    for d in data:
        assert "api_key" not in d and "api_key_hash" not in d


def test_store_credit_open_orders_finance():
    s = _login("finance")
    # try any customer id from customers list
    rc = s.get(f"{API}/customers?limit=1", timeout=15)
    if rc.status_code == 200:
        items = rc.json() if isinstance(rc.json(), list) else rc.json().get("items", [])
        if items:
            cid = items[0].get("id") or items[0].get("customer_id")
            if cid:
                r = s.get(f"{API}/store-credit/open-orders", params={"customer_id": cid}, timeout=15)
                assert r.status_code in (200, 404)
