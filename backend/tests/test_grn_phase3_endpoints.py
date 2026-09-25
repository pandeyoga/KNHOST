"""GRN Fase 3 — new endpoints smoke tests (partners, supplier-variance, rolls)."""
import os
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ENT = "ent_ksc"


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": ENT, "Content-Type": "application/json"}


def test_partners_supplier_returns_list_with_open_docs():
    tok = _login("admin@kainnusantara.id", "demo12345")
    r = requests.get(f"{BASE}/api/goods-receipts/partners?partner_type=supplier", headers=_hdr(tok), timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    # each entry should have id/name and open_docs list (may be empty for some)
    for p in data:
        assert "partner_id" in p and "partner_name" in p
        assert "open_docs" in p and isinstance(p["open_docs"], list)


def test_partners_makloon_ok():
    tok = _login("admin@kainnusantara.id", "demo12345")
    r = requests.get(f"{BASE}/api/goods-receipts/partners?partner_type=makloon", headers=_hdr(tok), timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_supplier_variance_admin_view():
    tok = _login("admin@kainnusantara.id", "demo12345")
    r = requests.get(f"{BASE}/api/goods-receipts/supplier-variance", headers=_hdr(tok), timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    for row in data:
        # partner aggregates
        for k in ("partner_id", "partner_name", "grn_count"):
            assert k in row, f"missing key {k} in {row}"


def test_supplier_variance_permission_via_po_view():
    # sales user typically has po.view? Use manager (has both). Use warehouse too — should be allowed via goods_receipt.view.
    tok = _login("warehouse@kainnusantara.id", "demo12345")
    r = requests.get(f"{BASE}/api/goods-receipts/supplier-variance", headers=_hdr(tok), timeout=15)
    assert r.status_code == 200, r.text


def test_rolls_endpoint_404_for_bogus_id():
    tok = _login("admin@kainnusantara.id", "demo12345")
    r = requests.get(f"{BASE}/api/goods-receipts/does_not_exist/rolls", headers=_hdr(tok), timeout=15)
    assert r.status_code in (404, 400)


def test_route_ordering_partners_not_treated_as_id():
    # Confirms 'partners' path is NOT mis-routed into /{grn_id}
    tok = _login("admin@kainnusantara.id", "demo12345")
    r = requests.get(f"{BASE}/api/goods-receipts/partners?partner_type=supplier", headers=_hdr(tok), timeout=15)
    assert r.status_code == 200
    r2 = requests.get(f"{BASE}/api/goods-receipts/supplier-variance", headers=_hdr(tok), timeout=15)
    assert r2.status_code == 200
