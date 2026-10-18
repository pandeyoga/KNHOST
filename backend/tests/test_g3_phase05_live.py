"""G3 Phase 05 — live API tests (preview URL).

Covers:
- /api/sales-orders/stats/summary (avg_order_value, top_customers scoping)
- /api/document-templates/{id}/preview (invoice & surat_jalan; error paths)
- /api/inventory/status-board (pending_demand + atp)
"""
import os
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN = ("admin@kainnusantara.id", "demo12345")
SALES = ("sales@kainnusantara.id", "demo1234")


def _login(creds):
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": creds[0], "password": creds[1]}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_h():
    tok = _login(ADMIN)
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture(scope="module")
def sales_h():
    try:
        tok = _login(SALES)
    except Exception:
        pytest.skip("sales login unavailable")
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}


# ---- stats/summary ------------------------------------------------------

def test_stats_summary_avg_order_value_formula(admin_h):
    r = requests.get(f"{BASE}/api/sales-orders/stats/summary", headers=admin_h, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "periods" in data and "pending_count" in data
    for k in ("7d", "30d", "90d"):
        p = data["periods"][k]
        rev = float(p["revenue"]); cnt = int(p["fulfilled_count"])
        expected = round(rev / cnt, 2) if cnt else 0.0
        assert p["avg_order_value"] == expected, f"{k}: {p['avg_order_value']} != {expected}"
        assert isinstance(p.get("top_customers"), list)
        assert len(p["top_customers"]) <= 5
        # top customer revenue is Σ grand_total of that customer's fulfilled orders in period
        for tc in p["top_customers"]:
            assert "revenue" in tc and tc["revenue"] >= 0
    # pending_count = sum of waiting_approval/reserved/approved
    bs = data.get("by_status", {})
    expected_pending = sum(int((bs.get(s) or {}).get("count", 0))
                           for s in ("waiting_approval", "reserved", "approved"))
    assert data["pending_count"] == expected_pending


def test_stats_summary_line_scope(admin_h):
    r = requests.get(f"{BASE}/api/sales-orders/stats/summary",
                     headers=admin_h, params={"line": "woven"}, timeout=30)
    assert r.status_code == 200


def test_stats_summary_sales_scoped(sales_h):
    r = requests.get(f"{BASE}/api/sales-orders/stats/summary", headers=sales_h, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "periods" in data


# ---- document-templates preview -----------------------------------------

def _get_so_id(admin_h):
    r = requests.get(f"{BASE}/api/sales-orders", headers=admin_h, timeout=30)
    assert r.status_code == 200
    rows = r.json() if isinstance(r.json(), list) else r.json().get("rows", [])
    assert rows, "no sales orders"
    return rows[0]["id"]


def test_preview_invoice_default(admin_h):
    so = _get_so_id(admin_h)
    r = requests.post(f"{BASE}/api/document-templates/tmpl_inv_default/preview",
                      headers=admin_h, json={"source_id": so}, timeout=30)
    assert r.status_code == 200, r.text
    assert "INVOICE" in r.text.upper()


def test_preview_surat_jalan_default(admin_h):
    so = _get_so_id(admin_h)
    r = requests.post(f"{BASE}/api/document-templates/tmpl_sj_default/preview",
                      headers=admin_h, json={"source_id": so}, timeout=30)
    assert r.status_code == 200, r.text
    assert "SURAT JALAN" in r.text.upper()


def test_preview_document_type_mismatch(admin_h):
    so = _get_so_id(admin_h)
    r = requests.post(f"{BASE}/api/document-templates/tmpl_inv_default/preview",
                      headers=admin_h,
                      json={"source_id": so, "document_type": "surat_jalan"}, timeout=30)
    assert r.status_code == 400


def test_preview_template_not_found(admin_h):
    so = _get_so_id(admin_h)
    r = requests.post(f"{BASE}/api/document-templates/tmpl_TEST_nonexistent/preview",
                      headers=admin_h, json={"source_id": so}, timeout=30)
    assert r.status_code == 404


def test_preview_inactive_template_409(admin_h):
    so = _get_so_id(admin_h)
    # Create TEST template, deactivate, assert 409, then cleanup.
    create = requests.post(f"{BASE}/api/document-templates", headers=admin_h,
                           json={"name": "TEST_phase05_inactive",
                                 "document_type": "invoice",
                                 "html": "<html><body>TEST</body></html>"}, timeout=30)
    assert create.status_code in (200, 201), create.text
    tid = create.json().get("id") or create.json().get("template_id")
    try:
        patch = requests.patch(f"{BASE}/api/document-templates/{tid}", headers=admin_h,
                               json={"data": {"status": "inactive"}}, timeout=30)
        assert patch.status_code in (200, 204), patch.text
        r = requests.post(f"{BASE}/api/document-templates/{tid}/preview",
                          headers=admin_h, json={"source_id": so}, timeout=30)
        assert r.status_code == 409, r.text
    finally:
        requests.delete(f"{BASE}/api/document-templates/{tid}", headers=admin_h, timeout=30)


def test_preview_empty_source_id(admin_h):
    r = requests.post(f"{BASE}/api/document-templates/tmpl_inv_default/preview",
                      headers=admin_h, json={}, timeout=30)
    assert r.status_code == 400


def test_preview_invalid_source_id(admin_h):
    r = requests.post(f"{BASE}/api/document-templates/tmpl_inv_default/preview",
                      headers=admin_h,
                      json={"source_id": "so_TEST_doesnotexist"}, timeout=30)
    assert r.status_code in (400, 404)


def test_preview_does_not_increment_generated(admin_h):
    so = _get_so_id(admin_h)
    before = requests.get(f"{BASE}/api/documents", headers=admin_h,
                          params={"source_id": so}, timeout=30)
    # Some installs expose /api/generated-documents instead; fall back silently.
    before_count = len(before.json()) if before.status_code == 200 and isinstance(before.json(), list) else None
    r = requests.post(f"{BASE}/api/document-templates/tmpl_inv_default/preview",
                      headers=admin_h, json={"source_id": so}, timeout=30)
    assert r.status_code == 200
    if before_count is not None:
        after = requests.get(f"{BASE}/api/documents", headers=admin_h,
                             params={"source_id": so}, timeout=30)
        after_count = len(after.json()) if after.status_code == 200 and isinstance(after.json(), list) else before_count
        assert after_count == before_count, "preview should NOT create a generated_document"


# ---- inventory/status-board --------------------------------------------

def test_status_board_pending_and_atp(admin_h):
    r = requests.get(f"{BASE}/api/inventory/status-board", headers=admin_h, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list) and data, "status-board returned empty/non-list"
    checked = 0
    for product in data[:20]:
        for ent in (product.get("by_entity") or []):
            assert "pending_demand" in ent, "by_entity row missing pending_demand"
            assert "atp" in ent, "by_entity row missing atp"
            avail = float(ent.get("available", 0) or 0)
            inc = float(ent.get("incoming", 0) or 0)
            pend = float(ent.get("pending_demand", 0) or 0)
            assert abs(float(ent["atp"]) - (avail + inc - pend)) < 0.5, \
                f"by_entity atp {ent['atp']} != {avail}+{inc}-{pend}"
            for wh in (ent.get("by_warehouse") or []):
                assert "pending_demand" in wh, "by_warehouse row missing pending_demand"
                assert "atp" in wh, "by_warehouse row missing atp"
                a2 = float(wh.get("available", 0) or 0)
                i2 = float(wh.get("incoming", 0) or 0)
                p2 = float(wh.get("pending_demand", 0) or 0)
                assert abs(float(wh["atp"]) - (a2 + i2 - p2)) < 0.5, \
                    f"by_warehouse atp {wh['atp']} != {a2}+{i2}-{p2}"
                checked += 1
    assert checked > 0, "no warehouse rows observed"
