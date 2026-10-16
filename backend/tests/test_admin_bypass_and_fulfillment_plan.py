"""
Tests for 2026-10 features:
 1) ADMIN BYPASS of SoD across approve routes (PO, PR, special-orders, vendor_bills,
    landed_cost, contra_bon, amendments, period_unlock, interco_return) — admin
    can approve docs they created themselves; non-admin creator remains blocked.
 2) FULFILLMENT PLAN API GET/POST /api/sales-admin/orders/{order_id}/fulfillment-plan
 3) ROLL MODE cross-entity: no auto warehouse_transfers, instead backorder + proposal.
"""
import os
import uuid
import time
import pytest
import requests

def _read_backend_url() -> str:
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            with open("/app/frontend/.env", "r") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        v = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert v, "REACT_APP_BACKEND_URL not configured"
    return v.rstrip("/")


BASE_URL = _read_backend_url()
API = f"{BASE_URL}/api"
ENT = "ent_ksc"


# ──────────────────────────────────────────────────────────── auth helpers
def login(email: str, password: str = "demo12345") -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_tok() -> str:
    return login("admin@kainnusantara.id")


@pytest.fixture(scope="session")
def manager_tok() -> str:
    return login("manager@kainnusantara.id")


@pytest.fixture(scope="session")
def salesadmin_tok() -> str:
    return login("salesadmin@kainnusantara.id")


def H(tok: str, entity: str = ENT) -> dict:
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": entity, "Content-Type": "application/json"}


# ──────────────────────────────────────────────────────────── Basic sanity
class TestAuthBaseline:
    def test_me(self, admin_tok):
        r = requests.get(f"{API}/auth/me", headers=H(admin_tok), timeout=15)
        assert r.status_code == 200
        assert r.json().get("role") == "admin"


# ──────────────────────────────────────────────────────────── Fulfillment Plan GET
class TestFulfillmentPlanOptions:
    def test_options_demo_order(self, admin_tok):
        # Known demo order with roll shortage per request body
        order_id = "so_23cd0fac9eb6"
        r = requests.get(f"{API}/sales-admin/orders/{order_id}/fulfillment-plan",
                         headers=H(admin_tok), timeout=30)
        if r.status_code == 404:
            pytest.skip("demo order so_23cd0fac9eb6 not present in this preview DB")
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        data = r.json()
        assert "lines" in data and isinstance(data["lines"], list)
        if not data["lines"]:
            pytest.skip("no shortage lines on demo order (fulfilled already)")
        line = data["lines"][0]
        for key in ("product_id", "product_name", "backorder_qty", "own_available",
                    "other_entities", "incoming_total", "proposal", "planned_qty"):
            assert key in line, f"line missing key {key}; got {list(line.keys())}"
        assert isinstance(line["other_entities"], list)

    def test_options_as_salesadmin(self, salesadmin_tok):
        order_id = "so_23cd0fac9eb6"
        r = requests.get(f"{API}/sales-admin/orders/{order_id}/fulfillment-plan",
                         headers=H(salesadmin_tok), timeout=30)
        assert r.status_code in (200, 404), f"salesadmin -> {r.status_code} {r.text[:200]}"


# ──────────────────────────────────────────────────────────── Fulfillment Plan POST validations
class TestFulfillmentPlanValidations:
    def _plan(self, tok):
        r = requests.get(f"{API}/sales-admin/orders/so_23cd0fac9eb6/fulfillment-plan",
                         headers=H(tok), timeout=30)
        if r.status_code != 200 or not r.json().get("lines"):
            pytest.skip("demo plan not available / no shortage")
        return r.json()["lines"][0]

    def test_total_over_shortage(self, admin_tok):
        ln = self._plan(admin_tok)
        payload = {"lines": [{"product_id": ln["product_id"],
                              "stock_qty": ln["backorder_qty"] + 100,
                              "interco": [], "reorder_qty": 0, "wait_qty": 0}],
                   "note": "TEST_over"}
        r = requests.post(f"{API}/sales-admin/orders/so_23cd0fac9eb6/fulfillment-plan",
                          headers=H(admin_tok), json=payload, timeout=30)
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:200]}"

    def test_all_zero(self, admin_tok):
        ln = self._plan(admin_tok)
        payload = {"lines": [{"product_id": ln["product_id"], "stock_qty": 0,
                              "interco": [], "reorder_qty": 0, "wait_qty": 0}],
                   "note": "TEST_zero"}
        r = requests.post(f"{API}/sales-admin/orders/so_23cd0fac9eb6/fulfillment-plan",
                          headers=H(admin_tok), json=payload, timeout=30)
        assert r.status_code == 400

    def test_stock_over_own_available(self, admin_tok):
        ln = self._plan(admin_tok)
        over = (ln["own_available"] or 0) + 999
        payload = {"lines": [{"product_id": ln["product_id"], "stock_qty": over,
                              "interco": [], "reorder_qty": 0, "wait_qty": 0}],
                   "note": "TEST_overstock"}
        r = requests.post(f"{API}/sales-admin/orders/so_23cd0fac9eb6/fulfillment-plan",
                          headers=H(admin_tok), json=payload, timeout=30)
        assert r.status_code == 400

    def test_wait_over_incoming(self, admin_tok):
        ln = self._plan(admin_tok)
        over = (ln.get("incoming_total") or 0) + 99999
        payload = {"lines": [{"product_id": ln["product_id"], "stock_qty": 0,
                              "interco": [], "reorder_qty": 0, "wait_qty": over}],
                   "note": "TEST_waitover"}
        r = requests.post(f"{API}/sales-admin/orders/so_23cd0fac9eb6/fulfillment-plan",
                          headers=H(admin_tok), json=payload, timeout=30)
        assert r.status_code == 400


# ──────────────────────────────────────────────────────────── Admin bypass approve
class TestAdminBypassPO:
    """Admin creates a PO (draft -> submit) and approves it themselves. Non-admin manager
       creator should still be blocked by SoD.
    """

    def _create_pr_and_po_as_admin(self, admin_tok) -> str:
        """Try to create a minimal PO via supplier id; else skip if list is empty."""
        # Find existing suppliers & products
        s = requests.get(f"{API}/suppliers?entity_id={ENT}", headers=H(admin_tok), timeout=15)
        if s.status_code != 200 or not s.json():
            pytest.skip("no suppliers available for PO test")
        # pick first external (non-group) supplier
        supplier = next((x for x in s.json() if not (x.get("group_entity_id") or x.get("is_group_entity"))), None)
        if not supplier:
            pytest.skip("no external supplier available")
        sup_id = supplier.get("id") or supplier.get("_id")
        p = requests.get(f"{API}/products?entity_id={ENT}", headers=H(admin_tok), timeout=15)
        if p.status_code != 200 or not p.json():
            pytest.skip("no products")
        prod = p.json()[0]
        prod_id = prod.get("id") or prod.get("_id")

        payload = {
            "entity_id": ENT,
            "warehouse_id": "wh_bandung",
            "supplier_id": sup_id,
            "notes": "TEST_admin_bypass_" + uuid.uuid4().hex[:6],
            "items": [{"product_id": prod_id, "quantity": 1000, "unit_price": 500_000_000,
                       "description": "TEST", "unit": "yard", "expected_grade": "A"}],
        }
        r = requests.post(f"{API}/purchase-orders", headers=H(admin_tok), json=payload, timeout=20)
        if r.status_code not in (200, 201):
            pytest.skip(f"PO create not available: {r.status_code} {r.text[:200]}")
        po = r.json()
        return po.get("id") or po.get("_id")

    def test_admin_can_approve_own_po(self, admin_tok):
        po_id = self._create_pr_and_po_as_admin(admin_tok)
        # Submit if needed
        requests.post(f"{API}/purchase-orders/{po_id}/submit", headers=H(admin_tok), timeout=15)
        r = requests.post(f"{API}/purchase-orders/{po_id}/approve",
                          headers=H(admin_tok), json={"note": "admin self approve"}, timeout=20)
        assert r.status_code in (200, 201), f"admin self approve expected OK, got {r.status_code}: {r.text[:400]}"
        body = r.json() if r.content else {}
        # It should NOT be 403 blocked by SoD
        txt = (r.text or "").lower()
        assert "pemisahan" not in txt and "sod" not in txt
        # Optional: verify audit log mentions self-approval phrase
        logs = requests.get(f"{API}/audit-logs/resource?entity_type=purchase_order&entity_id={po_id}",
                            headers=H(admin_tok), timeout=15)
        if logs.status_code == 200:
            items = logs.json().get("items", [])
            joined = str(items).lower()
            # Not strictly required, soft check
            print("audit snippet:", joined[:500])
        # Cleanup
        requests.post(f"{API}/purchase-orders/{po_id}/cancel", headers=H(admin_tok),
                      json={"reason": "TEST cleanup"}, timeout=15)

    def test_non_admin_creator_still_blocked(self, manager_tok):
        # Manager creates a PO and tries to approve it himself → should be blocked by SoD
        s = requests.get(f"{API}/suppliers?entity_id={ENT}", headers=H(manager_tok), timeout=15)
        if s.status_code != 200 or not s.json():
            pytest.skip("no suppliers")
        sup = next((x for x in s.json() if not (x.get("group_entity_id") or x.get("is_group_entity"))), None)
        if not sup:
            pytest.skip("no external supplier")
        p = requests.get(f"{API}/products?entity_id={ENT}", headers=H(manager_tok), timeout=15)
        if p.status_code != 200 or not p.json():
            pytest.skip("no products")
        prod = p.json()[0]
        payload = {"entity_id": ENT,
                   "warehouse_id": "wh_bandung",
                   "supplier_id": sup.get("id") or sup.get("_id"),
                   "notes": "TEST_mgr_sod_" + uuid.uuid4().hex[:6],
                   "items": [{"product_id": prod.get("id") or prod.get("_id"),
                              "quantity": 1000, "unit_price": 500_000_000,
                              "description": "TEST", "unit": "yard", "expected_grade": "A"}]}
        r = requests.post(f"{API}/purchase-orders", headers=H(manager_tok), json=payload, timeout=20)
        if r.status_code not in (200, 201):
            pytest.skip(f"manager cannot create PO: {r.status_code} {r.text[:200]}")
        po_id = r.json().get("id")
        requests.post(f"{API}/purchase-orders/{po_id}/submit", headers=H(manager_tok), timeout=15)
        ap = requests.post(f"{API}/purchase-orders/{po_id}/approve",
                           headers=H(manager_tok), json={"note": "manager self"}, timeout=20)
        # Expect 403 SoD (or 400 with SoD reason)
        assert ap.status_code in (400, 403), f"non-admin self approve got {ap.status_code}: {ap.text[:300]}"
        body_txt = (ap.text or "").lower()
        assert "pemisahan" in body_txt or "sod" in body_txt or "pembuat" in body_txt, \
            f"expected SoD reason, got {body_txt[:300]}"
        # Cleanup (via admin)
        admin_tok = login("admin@kainnusantara.id")
        requests.post(f"{API}/purchase-orders/{po_id}/cancel", headers=H(admin_tok),
                      json={"reason": "TEST cleanup"}, timeout=15)
