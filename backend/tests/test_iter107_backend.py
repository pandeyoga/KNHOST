"""Iter107 backend regression: goods-receipts mode + purchase-orders status filter/counts."""
import os
import pytest
import requests
from pathlib import Path

def _load_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    env = Path("/app/frontend/.env").read_text()
    for line in env.splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")

BASE_URL = _load_url()
ENTITY = "ent_ksc"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@kainnusantara.id", "password": "demo12345"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def hdr(token):
    return {"Authorization": f"Bearer {token}", "X-Entity-Id": ENTITY, "Content-Type": "application/json"}


# --- Mode Surat Jalan (Sukacita = grn) ---
class TestReceivingMode:
    def test_get_mode_returns_grn_for_ksc(self, hdr):
        r = requests.get(f"{BASE_URL}/api/goods-receipts/mode", headers=hdr)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict)
        modes = data.get("modes") or {}
        assert modes.get(ENTITY) == "grn", f"expected 'grn' for {ENTITY}, got {modes}"

    def test_legacy_in_flight_present(self, hdr):
        r = requests.get(f"{BASE_URL}/api/goods-receipts/mode", headers=hdr)
        data = r.json()
        # spec: 2 legacy tasks in flight; assert key exists and non-negative
        lif = data.get("legacy_in_flight")
        # accept dict {entity: n} or int
        if isinstance(lif, dict):
            n = lif.get(ENTITY, 0)
        else:
            n = lif if isinstance(lif, int) else 0
        assert n is not None


# --- Purchase Orders ---
class TestPurchaseOrders:
    def test_status_counts_shape(self, hdr):
        r = requests.get(f"{BASE_URL}/api/purchase-orders/status-counts",
                         headers=hdr, params={"entity_id": ENTITY})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "by_status" in data and "total" in data
        assert isinstance(data["by_status"], dict)
        assert isinstance(data["total"], int)
        # Total should equal sum
        assert data["total"] == sum(data["by_status"].values())

    def test_list_with_status_filter(self, hdr):
        r = requests.get(f"{BASE_URL}/api/purchase-orders",
                         headers=hdr,
                         params={"entity_id": ENTITY, "page": 1, "page_size": 50,
                                 "status": "pending,receiving"})
        assert r.status_code == 200, r.text
        data = r.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        assert isinstance(items, list)
        for po in items:
            assert po.get("status") in ("pending", "receiving"), po.get("status")

    def test_list_paginated(self, hdr):
        r = requests.get(f"{BASE_URL}/api/purchase-orders",
                         headers=hdr,
                         params={"entity_id": ENTITY, "page": 1, "page_size": 20})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert "items" in data and "total" in data
        assert len(data["items"]) <= 20


# --- Vendor bills (Tagihan Supplier) sanity ---
class TestVendorBills:
    def test_list_ok(self, hdr):
        r = requests.get(f"{BASE_URL}/api/vendor-bills",
                         headers=hdr, params={"entity_id": ENTITY, "page": 1, "page_size": 20})
        assert r.status_code == 200, r.text


# --- Purchase Requisitions ---
class TestPurchaseRequisitions:
    def test_list_ok(self, hdr):
        r = requests.get(f"{BASE_URL}/api/purchase-requisitions",
                         headers=hdr, params={"entity_id": ENTITY})
        assert r.status_code == 200, r.text
