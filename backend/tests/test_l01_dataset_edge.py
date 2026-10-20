"""L01 LN-011 edge cases — client dataset import re-import after rollback, permissions, parsing; recap filters."""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
HDR = ("kode_artikel,nama_artikel,sku,tahap,jenis_kain,kategori,warna_internal,supplier,kode_artikel_supplier,"
       "nama_artikel_supplier,warna_supplier,kode_warna_supplier,warna_customer\n")


def _login(email, pw):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def adm():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def pair():
    """product+supplier with NO existing supplier_items link (forces the 'created' path)."""
    sups = list(DB.suppliers.find({"code": {"$nin": [None, ""]}}, {"_id": 0, "id": 1, "code": 1, "name": 1}).limit(20))
    for p in DB.products.find({"sku": {"$regex": "^KN"}}, {"_id": 0, "id": 1, "sku": 1}).limit(200):
        for s in sups:
            if not DB.supplier_items.find_one({"product_id": p["id"], "supplier_id": s["id"]}):
                return p, s
    pytest.skip("no free product/supplier pair")


def _upload(adm, body, name="edge.csv"):
    return requests.post(f"{BASE}/api/client-dataset/upload", headers=adm, timeout=60,
                         files={"file": (name, body, "text/csv")})


class TestDatasetEdge:
    def test_template_download(self, adm):
        r = requests.get(f"{BASE}/api/client-dataset/template", headers=adm, timeout=30)
        assert r.status_code == 200 and "kode_artikel" in r.content.decode("utf-8-sig").splitlines()[0]

    def test_empty_file_400(self, adm):
        r = _upload(adm, b"foo,bar\n1,2\n")
        assert r.status_code == 400

    def test_semicolon_csv(self, adm, pair):
        p, s = pair
        body = (HDR.replace(",", ";") + f";;{p['sku']};finished;knit;;;{s['code']};;;;;\n").encode()
        r = _upload(adm, body)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["report"]["rows"][0]["status"] in ("ok", "same")

    def test_reimport_after_rollback_reactivates_supplier_item(self, adm, pair):
        p, s = pair
        body = (HDR + f",,{p['sku']},,,,,{s['code']},TEST-EDGE-{uuid.uuid4().hex[:6]},,Merah Edge,EDG-01,\n").encode()
        b1 = _upload(adm, body).json()["id"]
        assert requests.post(f"{BASE}/api/client-dataset/batches/{b1}/commit", headers=adm, timeout=60).status_code == 200
        si = DB.supplier_items.find_one({"product_id": p["id"], "supplier_id": s["id"]})
        assert si and si["status"] == "active"
        assert requests.post(f"{BASE}/api/client-dataset/batches/{b1}/rollback", headers=adm, timeout=60).status_code == 200
        assert DB.supplier_items.find_one({"id": si["id"]})["status"] == "inactive"
        # second import of the same mapping
        b2 = _upload(adm, body).json()["id"]
        assert requests.post(f"{BASE}/api/client-dataset/batches/{b2}/commit", headers=adm, timeout=60).status_code == 200
        st = DB.supplier_items.find_one({"id": si["id"]})["status"]
        requests.post(f"{BASE}/api/client-dataset/batches/{b2}/rollback", headers=adm, timeout=60)
        assert st == "active", f"re-imported supplier mapping stays '{st}' after previous rollback"

    def test_rollback_twice_409(self, adm, pair):
        p, s = pair
        b = _upload(adm, (HDR + f",,{p['sku']},,,,,,,,,,TEST_EDGE cust\n").encode()).json()["id"]
        assert requests.post(f"{BASE}/api/client-dataset/batches/{b}/commit", headers=adm, timeout=60).status_code == 200
        assert requests.post(f"{BASE}/api/client-dataset/batches/{b}/rollback", headers=adm, timeout=60).status_code == 200
        assert requests.post(f"{BASE}/api/client-dataset/batches/{b}/rollback", headers=adm, timeout=60).status_code == 409

    def test_manager_access(self):
        m = _login("manager@kainnusantara.id", "demo12345")
        # impor dataset = izin product.import (Admin; peran lain lewat custom role) — tab hanya untuk Admin
        assert requests.get(f"{BASE}/api/client-dataset/batches", headers=m, timeout=30).status_code == 403
        assert requests.get(f"{BASE}/api/makloon-claims/recap", headers=m, timeout=30).status_code == 200
        f = _login("finance@kainnusantara.id", "demo12345")
        assert requests.get(f"{BASE}/api/makloon-claims/recap", headers=f, timeout=30).status_code == 200


class TestRecapFilters:
    def test_future_range_empty(self, adm):
        d = requests.get(f"{BASE}/api/makloon-claims/recap", headers=adm, timeout=60,
                         params={"date_from": "2099-01-01"}).json()
        assert d["rows"] == [] and d["totals"]["loss_expense"] == 0

    def test_partner_filter(self, adm):
        d = requests.get(f"{BASE}/api/makloon-claims/recap", headers=adm, timeout=60).json()
        if not d["partners"]:
            pytest.skip("no partners")
        mid = d["partners"][0]["makloon_id"]
        f = requests.get(f"{BASE}/api/makloon-claims/recap", headers=adm, timeout=60, params={"makloon_id": mid}).json()
        assert all(r["makloon_id"] == mid for r in f["rows"]) and len(f["partners"]) == 1


# Iteration 187 retest: LIFO rollback guard + existing inactive supplier_item reactivated & restored
class TestDatasetLifo:
    def test_rollback_older_batch_while_newer_committed_409(self, adm, pair):
        p, s = pair
        b1 = _upload(adm, (HDR + f",,{p['sku']},,,,,,,,,,TEST_LIFO one\n").encode()).json()["id"]
        assert requests.post(f"{BASE}/api/client-dataset/batches/{b1}/commit", headers=adm, timeout=60).status_code == 200
        b2 = _upload(adm, (HDR + f",,{p['sku']},,,,,,,,,,TEST_LIFO two\n").encode()).json()["id"]
        assert requests.post(f"{BASE}/api/client-dataset/batches/{b2}/commit", headers=adm, timeout=60).status_code == 200
        try:
            r = requests.post(f"{BASE}/api/client-dataset/batches/{b1}/rollback", headers=adm, timeout=60)
            assert r.status_code == 409, r.text
        finally:
            assert requests.post(f"{BASE}/api/client-dataset/batches/{b2}/rollback", headers=adm, timeout=60).status_code == 200
            assert requests.post(f"{BASE}/api/client-dataset/batches/{b1}/rollback", headers=adm, timeout=60).status_code == 200

    def test_existing_inactive_supplier_item_reactivated_then_restored(self, adm):
        si = DB.supplier_items.find_one({"status": "inactive", "supplier_sku": {"$nin": [None, ""]}}, {"_id": 0})
        if not si:
            pytest.skip("no inactive supplier_item")
        p = DB.products.find_one({"id": si["product_id"]}, {"_id": 0, "sku": 1})
        s = DB.suppliers.find_one({"id": si["supplier_id"]}, {"_id": 0, "code": 1})
        if not (p and s and s.get("code")):
            pytest.skip("no product/supplier code")
        b = _upload(adm, (HDR + f",,{p['sku']},,,,,{s['code']},TEST-REACT,,,,\n").encode()).json()["id"]
        assert requests.post(f"{BASE}/api/client-dataset/batches/{b}/commit", headers=adm, timeout=60).status_code == 200
        st = DB.supplier_items.find_one({"id": si["id"]})["status"]
        assert requests.post(f"{BASE}/api/client-dataset/batches/{b}/rollback", headers=adm, timeout=60).status_code == 200
        after = DB.supplier_items.find_one({"id": si["id"]}, {"_id": 0})
        assert st == "active"
        assert after["status"] == "inactive" and after.get("supplier_sku") == si.get("supplier_sku")

    def test_two_skus_same_supplier_article_code_no_500(self, adm):
        """Iteration 187 bug: dry-run says ok but commit hits uq_supplier_sku (supplier_id, supplier_sku) → 500."""
        s = DB.suppliers.find_one({"code": "SUP-00002"}, {"_id": 0})
        ps = [p for p in DB.products.find({"sku": {"$regex": "^KNKNT0007"}}, {"_id": 0, "id": 1, "sku": 1}).limit(50)
              if not DB.supplier_items.find_one({"product_id": p["id"], "supplier_id": s["id"]})][:2]
        if len(ps) < 2:
            pytest.skip("need 2 free SKUs")
        code = f"TEST-DUP-{uuid.uuid4().hex[:6]}"
        body = HDR + "".join(f",,{p['sku']},,,,,{s['code']},{code},,W{i},C{i},\n" for i, p in enumerate(ps))
        u = _upload(adm, body.encode()).json()
        c = requests.post(f"{BASE}/api/client-dataset/batches/{u['id']}/commit", headers=adm, timeout=60)
        requests.post(f"{BASE}/api/client-dataset/batches/{u['id']}/rollback", headers=adm, timeout=60)
        left_active = DB.supplier_items.count_documents({"supplier_sku": code, "status": "active"})
        DB.supplier_items.delete_many({"supplier_sku": code})
        assert c.status_code != 500 or u["report"]["summary"]["error"] > 0, "dry-run ok but commit 500 (dup supplier_sku)"
        assert left_active == 0, "rollback of failed batch left created supplier_item active"
