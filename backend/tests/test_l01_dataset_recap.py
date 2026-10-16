"""L01 — impor dataset client (LN-011) & rekap susut/klaim mitra."""
import os

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]


def _login(email, pw):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def adm():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def sales():
    return _login("sales.kanda@kainnusantara.id", "demo1234")


def _csv(p, sup):
    return ("kode_artikel,nama_artikel,sku,tahap,jenis_kain,kategori,warna_internal,supplier,kode_artikel_supplier,"
            "nama_artikel_supplier,warna_supplier,kode_warna_supplier,warna_customer\n"
            f",,{p['sku']},finished,knitting,,,{sup['code']},TEST-L01-SUP,Test Item,Hitam Test,TST-01,TEST_L01 Hitam\n"
            "NOPE00000,,,greige,printing,,,Supplier Fiktif TEST,,,,,\n").encode()


class TestClientDataset:
    S = {}

    def test_sales_forbidden(self, sales):
        assert requests.get(f"{BASE}/api/client-dataset/batches", headers=sales, timeout=30).status_code == 403

    def test_dry_run_reports_without_writing(self, adm):
        p = DB.products.find_one({"sku": {"$regex": "^KN"}}, {"_id": 0, "id": 1, "sku": 1, "customer_color": 1})
        sup = DB.suppliers.find_one({"code": {"$nin": [None, ""]}}, {"_id": 0, "id": 1, "name": 1, "code": 1})
        r = requests.post(f"{BASE}/api/client-dataset/upload", headers=adm, timeout=60,
                          files={"file": ("ds.csv", _csv(p, sup), "text/csv")})
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        rows = d["report"]["rows"]
        assert rows[0]["status"] == "ok" and any("sinonim" in w for w in rows[0]["warnings"])
        assert rows[1]["status"] == "error"
        u = d["report"]["unknown_values"]
        assert "printing" in u["jenis_kain"] and "Supplier Fiktif TEST" in u["supplier"]
        assert "greige" not in u["tahap"]                       # sinonim baku → grey
        assert DB.products.find_one({"id": p["id"]}).get("customer_color") == p.get("customer_color")
        assert not DB.product_templates.find_one({"sku_prefix": "NOPE00000"})
        self.S.update(batch=d["id"], p=p, sup=sup)

    def test_commit_then_rollback(self, adm):
        b, p, sup = self.S["batch"], self.S["p"], self.S["sup"]
        r = requests.post(f"{BASE}/api/client-dataset/batches/{b}/commit", headers=adm, timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert DB.products.find_one({"id": p["id"]})["customer_color"] == "TEST_L01 Hitam"
        si = DB.supplier_items.find_one({"product_id": p["id"], "supplier_id": sup["id"]})
        assert si and si["supplier_color_code"] == "TST-01"
        assert requests.post(f"{BASE}/api/client-dataset/batches/{b}/commit", headers=adm, timeout=30).status_code == 409
        r = requests.post(f"{BASE}/api/client-dataset/batches/{b}/rollback", headers=adm, timeout=60)
        assert r.status_code == 200
        assert DB.products.find_one({"id": p["id"]}).get("customer_color") == p.get("customer_color")


class TestClaimRecap:
    def test_recap_shape_and_permission(self, adm, sales):
        r = requests.get(f"{BASE}/api/makloon-claims/recap", headers=adm, timeout=60)
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert {"partners", "rows", "totals"} <= set(d)
        for p in d["partners"]:
            assert p["receivable_total"] >= p["loss_claim"] - 0.01
        assert requests.get(f"{BASE}/api/makloon-claims/recap", headers=sales, timeout=30).status_code == 403

    def test_recap_matches_posted_losses(self, adm):
        d = requests.get(f"{BASE}/api/makloon-claims/recap", headers=adm, timeout=60).json()
        exp = sum(float(x.get("expense_value") or 0) for o in DB.makloon_orders.find({}, {"steps": 1})
                  for s in o.get("steps") or [] for x in s.get("material_losses") or [] if x.get("status") == "posted")
        assert d["totals"]["loss_expense"] == pytest.approx(exp, abs=1)
