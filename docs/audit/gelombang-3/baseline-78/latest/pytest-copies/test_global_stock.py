"""Tests for A1/A3 — global stock scope and lots filters (B3)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8006").rstrip("/")


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@kainnusantara.id", "password": "demo12345"},
                      timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def sales_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "sales@kainnusantara.id", "password": "demo12345"},
                      timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# --- A1: Dashboard & products return global stock fields ---
class TestA1GlobalStock:
    def test_dashboard_has_global_fields(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/dashboard?entity_id=ent_kanda",
                         headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        prods = data.get("products") or []
        assert prods, "No products returned"
        # Pick one with required attrs
        sample = prods[0]
        for key in ("stock_scope", "available_qty", "entity_available_qty",
                    "incoming_so_qty", "incoming_restock_qty"):
            assert key in sample, f"missing {key} in product payload"
        assert sample["stock_scope"] == "global"

    def test_dashboard_btk_mega_001(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/dashboard?entity_id=ent_kanda",
                         headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        prods = r.json().get("products") or []
        target = next((p for p in prods if (p.get("sku") == "BTK-MEGA-001" or "BTK-MEGA-001" in (p.get("code") or ""))), None)
        if not target:
            pytest.skip("BTK-MEGA-001 not seeded in current env")
        print("BTK-MEGA-001:", {k: target.get(k) for k in
              ("available_qty", "entity_available_qty", "incoming_restock_qty", "incoming_so_qty")})
        assert target["available_qty"] > target.get("entity_available_qty", 0)
        assert target["incoming_restock_qty"] >= 0
        assert target["incoming_so_qty"] >= 0

    def test_products_endpoint_has_global_fields(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/products?entity_id=ent_kanda&page=1&page_size=5",
                         headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        payload = r.json()
        items = payload if isinstance(payload, list) else (payload.get("items") or payload.get("products") or [])
        assert items, "no products"
        sample = items[0]
        for key in ("stock_scope", "available_qty", "entity_available_qty",
                    "incoming_so_qty", "incoming_restock_qty"):
            assert key in sample, f"missing {key} in /api/products item (keys={list(sample.keys())})"


# --- A3: preview-allocation still per-seller-entity, makloon blocks still 409 ---
class TestA3PreviewAllocation:
    def test_preview_allocation_endpoint_exists(self, sales_token, admin_token):
        # Grab a product to construct a preview payload
        r = requests.get(f"{BASE_URL}/api/dashboard?entity_id=ent_ksc",
                         headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        prods = r.json().get("products") or []
        prod = next((p for p in prods if p.get("available_qty", 0) > 0), prods[0] if prods else None)
        if not prod:
            pytest.skip("no product")
        payload = {
            "entity_id": "ent_ksc",
            "mode": "qty",
            "items": [{"product_id": prod["id"], "quantity": 1, "qty": 1}],
        }
        r = requests.post(f"{BASE_URL}/api/sales-orders/preview-allocation",
                          headers=_h(admin_token), json=payload, timeout=30)
        assert r.status_code in (200, 400, 409), r.text


# --- B3: lots filters/counts ---
class TestB3Lots:
    def _count(self, admin_token, params):
        r = requests.get(f"{BASE_URL}/api/lots", headers=_h(admin_token), params=params, timeout=30)
        assert r.status_code == 200, r.text
        js = r.json()
        return js.get("total", js.get("count", 0)), js

    def test_total(self, admin_token):
        total, _ = self._count(admin_token, {"page": 1, "page_size": 5})
        assert total == 34, f"expected 34 got {total}"

    def test_source_receiving(self, admin_token):
        total, _ = self._count(admin_token, {"source": "receiving", "page": 1, "page_size": 5})
        assert total == 1, total

    def test_source_makloon(self, admin_token):
        total, _ = self._count(admin_token, {"source": "makloon", "page": 1, "page_size": 5})
        assert total == 10, total

    def test_stage_yarn(self, admin_token):
        total, _ = self._count(admin_token, {"stage": "yarn", "page": 1, "page_size": 5})
        assert total == 3, total

    def test_status_karantina(self, admin_token):
        total, _ = self._count(admin_token, {"lot_status": "karantina", "page": 1, "page_size": 5})
        assert total == 6, total

    def test_q_btk(self, admin_token):
        total, _ = self._count(admin_token, {"q": "BTK", "page": 1, "page_size": 5})
        assert total == 13, total
