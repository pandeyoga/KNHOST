# L01 – Sales role field-visibility (grade/lot/origin hidden) regression via public URL
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
FORBIDDEN = {"grade", "lot", "dye_lot", "supplier_lot", "batch_lot_rolls", "origin"}


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login {email} failed {r.status_code}")
    tok = r.json().get("token") or r.json().get("access_token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    s.headers["X-Entity-Id"] = "ent_kanda"
    return s


def _keys(obj, out=None):
    out = set() if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(k)
            _keys(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _keys(v, out)
    return out


@pytest.fixture(scope="module")
def sales():
    return _login("sales.kanda@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def salesadmin():
    return _login("salesadmin.kanda@kainnusantara.id", "demo12345")


def _ids(s, path):
    r = s.get(f"{BASE_URL}{path}")
    assert r.status_code == 200, r.text[:200]
    d = r.json()
    items = d if isinstance(d, list) else (d.get("items") or d.get("data") or d.get("orders") or [])
    return r, items


class TestSalesHidden:
    @pytest.mark.parametrize("path", ["/api/products", "/api/inventory/rolls", "/api/sales-orders",
                                      "/api/sales/stock-summary?product_id=prod_batik_mega"])
    def test_list_no_forbidden_keys(self, sales, path):
        r = sales.get(f"{BASE_URL}{path}")
        assert r.status_code == 200, r.text[:200]
        leaked = _keys(r.json()) & FORBIDDEN
        assert not leaked, f"{path} leaked {leaked}"
        hdr = r.headers.get("x-kn-fields-hidden", "")
        assert "grade" in hdr and "lot" in hdr and "origin" in hdr, hdr

    def test_product_detail(self, sales):
        _, items = _ids(sales, "/api/products")
        assert items
        pid = items[0]["id"]
        # no GET /products/{id}; use detail sub-resources
        for sub in ("stock-breakdown", "purchase-history"):
            r = sales.get(f"{BASE_URL}/api/products/{pid}/{sub}")
            if r.status_code == 200:
                assert not (_keys(r.json()) & FORBIDDEN), f"{sub} leaked {_keys(r.json()) & FORBIDDEN}"

    def test_so_detail(self, sales):
        _, items = _ids(sales, "/api/sales-orders")
        if not items:
            pytest.skip("no SO")
        r = sales.get(f"{BASE_URL}/api/sales-orders/{items[0]['id']}")
        assert r.status_code == 200
        assert not (_keys(r.json()) & FORBIDDEN)


class TestPrivilegedSeesGrade:
    def test_admin_rolls_grade(self, admin):
        r = admin.get(f"{BASE_URL}/api/inventory/rolls")
        assert r.status_code == 200
        assert "grade" in _keys(r.json())

    def test_salesadmin_rolls_grade(self, salesadmin):
        r = salesadmin.get(f"{BASE_URL}/api/inventory/rolls")
        assert r.status_code == 200
        assert "grade" in _keys(r.json())
