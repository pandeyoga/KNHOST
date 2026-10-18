"""Iter 62 — Warna Pelanggan (customer colors) tests."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://poc-refactor.preview.emergentagent.com").rstrip("/")


def _login(email: str, password: str = "demo12345") -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login('admin@kainnusantara.id')}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture(scope="module")
def finance_headers():
    return {"Authorization": f"Bearer {_login('finance@kainnusantara.id')}", "X-Entity-Id": "ent_ksc"}


class TestCustomerColorsEndpoint:
    """GET /api/color-library/customer-colors"""

    def test_customer_colors_ksc(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/color-library/customer-colors", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        groups = r.json()
        by_cid = {g["customer_id"]: g for g in groups}
        assert "cust_butik_bali" in by_cid, f"missing butik bali: {list(by_cid)}"
        assert "cust_toko_kain" in by_cid, f"missing toko kain: {list(by_cid)}"

        bali = by_cid["cust_butik_bali"]
        codes_bali = {c["code"]: c for c in bali["colors"]}
        assert "KN-GRN-03" in codes_bali
        assert "KN-PUR-01" in codes_bali

        grn = codes_bali["KN-GRN-03"]
        assert grn["owned"] is False
        assert grn["general_products_count"] == 0
        assert any(p["sku"] == "SGK-BLI-TSK-01" for p in grn["products"])

        pur = codes_bali["KN-PUR-01"]
        assert pur["owned"] is False
        assert pur["general_products_count"] >= 1
        assert any(p["sku"] == "SGK-BLI-UNG-01" for p in pur["products"])

        toko = by_cid["cust_toko_kain"]
        sjt = next((c for c in toko["colors"] if c["code"] == "KN-SJT-01"), None)
        assert sjt is not None
        assert sjt["owned"] is True
        assert sjt["products"] == []

    def test_customer_colors_kanda_empty(self, admin_headers):
        h = {**admin_headers, "X-Entity-Id": "ent_kanda"}
        r = requests.get(f"{BASE_URL}/api/color-library/customer-colors", headers=h, timeout=30)
        assert r.status_code == 200
        # cust_butik_bali & cust_toko_kain shouldn't be visible from ent_kanda
        cids = {g["customer_id"] for g in r.json()}
        assert "cust_butik_bali" not in cids
        assert "cust_toko_kain" not in cids

    def test_customer_colors_filter_by_customer(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/color-library/customer-colors?customer_id=cust_butik_bali",
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200
        groups = r.json()
        assert len(groups) == 1
        assert groups[0]["customer_id"] == "cust_butik_bali"

    def test_customer_colors_finance_forbidden(self, finance_headers):
        r = requests.get(f"{BASE_URL}/api/color-library/customer-colors", headers=finance_headers, timeout=30)
        assert r.status_code == 403


class TestScopeParam:
    """GET /api/color-library?scope=internal|customer"""

    def test_scope_internal(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/color-library?scope=internal", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        codes = {c["code"] for c in r.json()}
        assert "KN-GRN-03" not in codes
        assert "KN-SJT-01" not in codes
        assert "KN-PUR-01" in codes

    def test_scope_customer(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/color-library?scope=customer", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        codes = {c["code"] for c in r.json()}
        assert "KN-GRN-03" in codes
        assert "KN-SJT-01" in codes
        assert "KN-PUR-01" not in codes

    def test_no_scope_all_have_flag(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/color-library", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        rows = r.json()
        for r_ in rows:
            assert "is_customer_color" in r_
            assert isinstance(r_["is_customer_color"], bool)


class TestCreatePatchCustomerColor:
    def test_create_with_valid_customer(self, admin_headers):
        payload = {"code": "TEST-CC-01", "name": "TEST CC", "hex": "#123456",
                   "exclusive_customer_id": "cust_butik_bali"}
        r = requests.post(f"{BASE_URL}/api/color-library", json=payload, headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["exclusive_customer_id"] == "cust_butik_bali"
        assert data["exclusive_customer_name"]
        cid = data["id"]
        # patch to empty -> release
        r2 = requests.patch(f"{BASE_URL}/api/color-library/{cid}", json={"exclusive_customer_id": ""},
                            headers=admin_headers, timeout=30)
        assert r2.status_code == 200
        assert r2.json()["exclusive_customer_id"] == ""
        # cleanup
        requests.delete(f"{BASE_URL}/api/color-library/{cid}", headers=admin_headers, timeout=30)

    def test_create_with_invalid_customer_400(self, admin_headers):
        payload = {"code": "TEST-CC-02", "name": "TEST CC2", "hex": "#123456",
                   "exclusive_customer_id": "cust_does_not_exist"}
        r = requests.post(f"{BASE_URL}/api/color-library", json=payload, headers=admin_headers, timeout=30)
        assert r.status_code == 400
        assert "Pelanggan tidak ditemukan" in r.text

    def test_patch_move_between_customers(self, admin_headers):
        payload = {"code": "TEST-CC-03", "name": "TEST CC3", "hex": "#abcdef",
                   "exclusive_customer_id": "cust_butik_bali"}
        r = requests.post(f"{BASE_URL}/api/color-library", json=payload, headers=admin_headers, timeout=30)
        assert r.status_code == 200
        cid = r.json()["id"]
        r2 = requests.patch(f"{BASE_URL}/api/color-library/{cid}",
                            json={"exclusive_customer_id": "cust_toko_kain"},
                            headers=admin_headers, timeout=30)
        assert r2.status_code == 200
        assert r2.json()["exclusive_customer_id"] == "cust_toko_kain"
        requests.delete(f"{BASE_URL}/api/color-library/{cid}", headers=admin_headers, timeout=30)


def test_zzz_cleanup():
    """Hard delete any TEST- rows we may have left."""
    from pymongo import MongoClient
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    client = MongoClient(mongo_url)
    client[db_name].color_library.delete_many({"code": {"$regex": "^TEST-CC-"}})
