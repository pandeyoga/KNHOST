"""Iter89 review-request tests.

Covers:
- E. amendment_service._sync_backorders unit behaviour.
- D. rolls_without_cost API + banner data shape.
- A/B. Seeded makloon partial demo integrity (mko_4e0b3f8f8fcd / KSC/GRN-00004).
"""
import os
import sys
import pytest
import requests

sys.path.insert(0, "/app/backend")
from services.amendment_service import _sync_backorders  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ENT = "ent_ksc"


# ---------- E. _sync_backorders unit ----------
class TestSyncBackorders:
    def test_fulfilled_entries_untouched(self):
        bos = [
            {"id": "bo1", "product_id": "P1", "backorder_qty": 5, "status": "fulfilled"},
            {"id": "bo2", "product_id": "P1", "backorder_qty": 10, "status": "open"},
        ]
        items = [{"product_id": "P1", "backorder_qty": 3}]
        out = _sync_backorders(bos, items)
        # First entry (fulfilled) untouched
        assert out[0]["status"] == "fulfilled"
        assert out[0]["backorder_qty"] == 5
        # Second (first open) gets the new qty
        assert out[1]["backorder_qty"] == 3
        assert out[1].get("status") != "fulfilled"

    def test_zero_qty_marks_fulfilled(self):
        bos = [{"id": "bo1", "product_id": "P1", "backorder_qty": 10, "status": "open"}]
        items = [{"product_id": "P1", "backorder_qty": 0}]
        out = _sync_backorders(bos, items)
        assert out[0]["backorder_qty"] == 0
        assert out[0]["status"] == "fulfilled"

    def test_product_without_backorder_qty_key_untouched(self):
        bos = [{"id": "bo1", "product_id": "P1", "backorder_qty": 4, "status": "open"}]
        items = [{"product_id": "P1"}]  # no backorder_qty key
        out = _sync_backorders(bos, items)
        assert out[0]["backorder_qty"] == 4

    def test_only_first_open_per_product_updated(self):
        bos = [
            {"id": "bo1", "product_id": "P1", "backorder_qty": 10, "status": "open"},
            {"id": "bo2", "product_id": "P1", "backorder_qty": 20, "status": "open"},
        ]
        items = [{"product_id": "P1", "backorder_qty": 7}]
        out = _sync_backorders(bos, items)
        assert out[0]["backorder_qty"] == 7
        # Second untouched (left already consumed to 0.0)
        assert out[1]["backorder_qty"] == 0.0


# ---------- D. rolls_without_cost API ----------
class TestRollsWithoutCost:
    @pytest.fixture(scope="class")
    def admin_token(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@kainnusantara.id", "password": "demo12345"})
        assert r.status_code == 200, r.text
        return r.json()["token"]

    @pytest.fixture(scope="class")
    def h(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}", "X-Entity-Id": ENT,
                "Content-Type": "application/json"}

    def test_create_roll_without_cost_and_query(self, h):
        # Create a test roll WITHOUT unit_cost
        payload = {"product_id": "prod_batik_mega", "warehouse_id": "wh_bandung",
                   "roll_no": "TESTB-NOCOST-1", "quantity": 10, "unit": "yard",
                   "lot": "TESTB-LOT"}
        r = requests.post(f"{BASE_URL}/api/inventory/initial-stock", headers=h, json=payload)
        assert r.status_code in (200, 201), r.text
        try:
            # GET rolls-without-cost
            r2 = requests.get(f"{BASE_URL}/api/inventory/rolls-without-cost", headers=h)
            assert r2.status_code == 200, r2.text
            data = r2.json()
            assert "total" in data
            assert data["total"] >= 1
            # Find our test roll
            rows = data.get("rows") or data.get("rolls") or []
            match = [row for row in rows if row.get("roll_no") == "TESTB-NOCOST-1"]
            assert match, f"created roll not present in rows: {rows[:3]}"
            row = match[0]
            # Should include sku + product_name + quantity (feedback from iter88)
            assert row.get("sku"), f"row missing sku: {row}"
            assert row.get("product_name"), f"row missing product_name: {row}"
            assert (row.get("quantity") or row.get("length_initial")), \
                f"row missing quantity: {row}"
        finally:
            # Cleanup
            from pymongo import MongoClient
            c = MongoClient("mongodb://localhost:27017")["test_database"]
            c.inventory_rolls.delete_many({"roll_no": "TESTB-NOCOST-1"})
            c.inventory_movements.delete_many({"roll_id": {"$exists": True},
                                               "reason": {"$regex": "TESTB", "$options": "i"}})
            c.inventory_lots.delete_many({"lot": "TESTB-LOT"})


# ---------- A. Demo MKO seed integrity ----------
class TestMakloonPartialSeed:
    @pytest.fixture(scope="class")
    def admin_h(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@kainnusantara.id", "password": "demo12345"})
        assert r.status_code == 200
        return {"Authorization": f"Bearer {r.json()['token']}",
                "X-Entity-Id": ENT}

    def test_mko_seed_has_step_issued_with_partial_receipt(self):
        from pymongo import MongoClient
        c = MongoClient("mongodb://localhost:27017")["test_database"]
        mko = c.makloon_orders.find_one({"id": "mko_4e0b3f8f8fcd"})
        assert mko, "seed MKO missing — re-run scripts/seed_makloon_partial_demo.py"
        step0 = mko["steps"][0]
        assert step0["status"] == "issued"
        prs = step0.get("partial_receipts") or []
        assert len(prs) == 1
        assert prs[0]["grn_number"] == "KSC/GRN-00003"
        assert float(prs[0]["out_qty"]) == 30.0
        assert prs[0].get("posted") is False

    def test_grn_00004_in_reconcile(self):
        from pymongo import MongoClient
        c = MongoClient("mongodb://localhost:27017")["test_database"]
        grn = c.goods_receipts.find_one({"number": "KSC/GRN-00004"})
        assert grn, "seed GRN-00004 missing"
        assert grn["status"] == "reconcile"

    def test_mko_detail_api_exposes_partial(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/makloon-orders/mko_4e0b3f8f8fcd", headers=admin_h)
        assert r.status_code == 200, r.text
        mko = r.json()
        step0 = mko["steps"][0]
        assert step0["status"] == "issued"
        assert step0.get("partial_receipts")
        assert step0["partial_receipts"][0]["grn_number"] == "KSC/GRN-00003"
