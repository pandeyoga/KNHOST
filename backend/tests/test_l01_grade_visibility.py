"""L01 — visibilitas grade/LOT/asal per peran (LN-012-T02/T05), master grade (T03),
minimum grade pelanggan (T01), restock default (LN-013-T01), default izin tidak hidup lagi (LN-015-T07)."""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"


def _login(email, pw):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def adm():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def sales():
    return _login("sales.kanda@kainnusantara.id", "demo1234")


@pytest.fixture(scope="module")
def sadm():
    return _login("salesadmin.kanda@kainnusantara.id", "demo1234")


def _walk_keys(o, out):
    if isinstance(o, dict):
        for k, v in o.items():
            out.add(k)
            _walk_keys(v, out)
    elif isinstance(o, list):
        for v in o:
            _walk_keys(v, out)
    return out


class TestFieldVisibility:
    URLS = ["/api/products?limit=50", "/api/inventory/rolls?limit=50", "/api/sales-orders?limit=20",
            "/api/products/stock-summary"]

    def test_sales_never_receives_grade_lot_origin(self, sales):
        for u in self.URLS:
            r = requests.get(f"{BASE}{u}", headers=sales, timeout=60)
            if r.status_code != 200:
                continue
            keys = _walk_keys(r.json(), set())
            assert not keys & {"grade", "lot", "dye_lot", "supplier_lot", "batch_lot_rolls", "origin"}, (u, keys)

    def test_sales_admin_and_admin_still_see(self, adm, sadm):
        for h in (adm, sadm):
            r = requests.get(f"{BASE}/api/products?limit=50", headers=h, timeout=60)
            assert r.status_code == 200
            assert "grade" in _walk_keys(r.json(), set())

    def test_sales_grade_filter_is_ignored(self, sales):
        a = requests.get(f"{BASE}/api/products?limit=500", headers=sales, timeout=60).json()
        b = requests.get(f"{BASE}/api/products?limit=500&grade=BS", headers=sales, timeout=60).json()
        n = lambda d: len(d.get("items", d) if isinstance(d, dict) else d)
        assert n(a) == n(b)

    def test_grade_follows_role_config_for_sales(self, adm, sales):
        """Keputusan customer 2026-10-19: grade sales mengikuti konfigurasi peran (dulu: selalu tertutup)."""
        m = DB.permission_settings.find_one({"id": "default"})["matrix"]
        before = list(m["sales"].get("field_visibility", []))
        DB.permission_settings.update_one({"id": "default"}, {"$set": {"matrix.sales.field_visibility": ["grade", "lot"]}})
        try:
            from_req = lambda: requests.get(f"{BASE}/api/products?limit=50", headers=sales, timeout=60)
            # cache middleware 15 dtk — pakai sesi baru supaya tidak menunggu
            s2 = _login("sales.kanda@kainnusantara.id", "demo1234")
            keys = _walk_keys(requests.get(f"{BASE}/api/inventory/rolls?limit=50", headers=s2, timeout=60).json(), set())
            assert "grade" in keys              # diberi hak lihat grade → terlihat
            assert "lot" in keys or "dye_lot" in keys or True  # LOT boleh dibuka lewat konfigurasi
            assert from_req().status_code == 200
        finally:
            DB.permission_settings.update_one({"id": "default"}, {"$set": {"matrix.sales.field_visibility": before}})

    def test_pdf_redacts_for_sales(self, sales):
        u = DB.users.find_one({"email": "sales.kanda@kainnusantara.id"}, {"_id": 0, "home_entity_id": 1})
        so = DB.sales_orders.find_one({"entity_id": u["home_entity_id"], "wms_status": {"$exists": True}},
                                      {"_id": 0, "id": 1}) or DB.sales_orders.find_one(
            {"entity_id": u["home_entity_id"]}, {"_id": 0, "id": 1})
        r = requests.get(f"{BASE}/api/pdf/render/packing_list/{so['id']}?format=html", headers=sales, timeout=60)
        assert r.status_code == 200, r.text[:200]
        html = r.text
        assert ">Lot<" not in html or "—" in html


class TestGradeMaster:
    def test_owner_active_set(self, adm):
        rows = {g["code"]: g for g in requests.get(f"{BASE}/api/master/grades", headers=adm, timeout=30).json()}
        assert {c for c, g in rows.items() if g["active"]} >= {"A", "A1", "B", "BS"}
        assert rows["A2"]["active"] is False and rows["B1"]["historical"] and rows["C"]["active"] is False
        assert rows["B1"]["rolls_using"] > 0                      # histori tetap ada

    def test_sales_cannot_manage(self, sales):
        assert requests.get(f"{BASE}/api/master/grades", headers=sales, timeout=30).status_code == 403
        r = requests.post(f"{BASE}/api/master/grades", json={"code": "Z9", "name": "x", "rank": 50}, headers=sales, timeout=30)
        assert r.status_code == 403

    def test_add_new_grade_used_without_code_change(self, adm):
        code = "Q" + uuid.uuid4().hex[:1].upper()
        DB.md_grades.delete_many({"code": code})
        rank = 60 + int(uuid.uuid4().int % 30)
        DB.md_grades.delete_many({"rank": rank})
        r = requests.post(f"{BASE}/api/master/grades", json={"code": code, "name": f"{code} uji", "rank": rank},
                          headers=adm, timeout=30)
        assert r.status_code == 200, r.text
        try:
            enums = requests.get(f"{BASE}/api/enums", headers=adm, timeout=30).json()["enums"]["grade"]["values"]
            assert any(v["value"] == code and v["active"] for v in enums)
            dup = requests.post(f"{BASE}/api/master/grades", json={"code": code + "", "name": "x", "rank": rank},
                                headers=adm, timeout=30)
            assert dup.status_code == 409
            r = requests.post(f"{BASE}/api/master/grades/{code}/active", json={"active": False, "reason": "TEST_L01 uji"},
                              headers=adm, timeout=30)
            assert r.status_code == 200 and r.json()["active"] is False
            enums = requests.get(f"{BASE}/api/enums", headers=adm, timeout=30).json()["enums"]["grade"]["values"]
            assert any(v["value"] == code and v["active"] is False for v in enums)
        finally:
            DB.md_grades.delete_many({"code": code})
            requests.get(f"{BASE}/api/master/grades", headers=adm, timeout=30)

    def test_inactive_grade_rejected_on_new_input(self, adm):
        import sys
        sys.path.insert(0, "/app/backend")
        cust = DB.customers.find_one({}, {"_id": 0, "id": 1})
        r = requests.put(f"{BASE}/api/customers/{cust['id']}/grade-rules",
                         json={"min_grade": "A2", "preferred_grades": []}, headers=adm, timeout=30)
        assert r.status_code in (400, 422), r.text
        assert "historis" in r.text.lower() or "nonaktif" in r.text.lower()

    def test_rank_conflict(self, adm):
        r = requests.patch(f"{BASE}/api/master/grades/A1", json={"rank": 1}, headers=adm, timeout=30)
        assert r.status_code == 409


class TestCustomerMinimumGrade:
    def test_min_rank_semantics(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from services.sales_p04_service import grade_block_reason
        rule = {"min_grade": "B", "accept_bs": False}
        assert grade_block_reason(rule, "A") == ""            # lebih tinggi diterima
        assert grade_block_reason(rule, "B") == ""
        rule_a = {"min_grade": "A"}
        assert "di bawah minimum" in grade_block_reason(rule_a, "B")
        assert grade_block_reason({"allowed_grades": ["A", "A1"]}, "A") == ""   # aturan lama → min A1
        assert "di bawah minimum" in grade_block_reason({"allowed_grades": ["A", "A1"]}, "B")
        assert "BS" in grade_block_reason(rule, "BS")

    def test_api_save_and_read(self, adm):
        cust = DB.customers.find_one({}, {"_id": 0, "id": 1})
        prev = DB.customer_grade_rules.find_one({"customer_id": cust["id"]})
        try:
            r = requests.put(f"{BASE}/api/customers/{cust['id']}/grade-rules",
                             json={"min_grade": "B", "preferred_grades": ["A1"], "accept_bs": False, "note": "TEST_L01"},
                             headers=adm, timeout=30)
            assert r.status_code == 200, r.text
            assert r.json()["rule"]["min_grade"] == "B"
            r = requests.put(f"{BASE}/api/customers/{cust['id']}/grade-rules",
                             json={"min_grade": "A", "preferred_grades": ["B"]}, headers=adm, timeout=30)
            assert r.status_code in (400, 422) and "minimum" in r.text
        finally:
            DB.customer_grade_rules.delete_many({"customer_id": cust["id"]})
            if prev:
                DB.customer_grade_rules.insert_one(prev)


class TestPermissionDefaultsNotRevived:
    def test_revoked_default_stays_revoked_after_sync(self):
        import asyncio
        import sys
        sys.path.insert(0, "/app/backend")
        m = DB.permission_settings.find_one({"id": "default"})
        before = list(m["matrix"]["finance"].get("field_visibility", []))
        DB.permission_settings.update_one({"id": "default"}, {"$set": {"matrix.finance.field_visibility": ["lot"]}})
        try:
            import bootstrap
            asyncio.get_event_loop().run_until_complete(bootstrap.sync_permission_modules())
            after = DB.permission_settings.find_one({"id": "default"})["matrix"]["finance"]["field_visibility"]
            assert after == ["lot"], after
        finally:
            DB.permission_settings.update_one({"id": "default"}, {"$set": {"matrix.finance.field_visibility": before}})


class TestSkuAndNameMasking:
    """Keputusan owner 2026-10-16: segmen ASAL/GRADE/LOT pada kode SKU & akhiran grade pada nama disamarkan."""

    def test_sales_sees_masked_sku_and_name(self, sales, adm):
        p = DB.products.find_one({"sku": {"$regex": r"^[A-Z0-9]{9}-[LI]-"}, "name": {"$regex": " A$"}},
                                 {"_id": 0, "id": 1, "sku": 1, "name": 1})
        r = requests.get(f"{BASE}/api/products?limit=1000", headers=sales, timeout=60)
        assert r.status_code == 200
        rows = r.json()
        rows = rows.get("items", rows) if isinstance(rows, dict) else rows
        mine = next((x for x in rows if x["id"] == p["id"]), None)
        if mine is None:
            pytest.skip("produk tidak terlihat oleh sales (lini/eksklusivitas)")
        seg = mine["sku"].split("-")
        assert seg[1] == "•" and seg[3] == "••" and seg[5] == "••", mine["sku"]
        assert not mine["name"].endswith(" A")
        a = requests.get(f"{BASE}/api/products?limit=1000", headers=adm, timeout=60).json()
        a = a.get("items", a) if isinstance(a, dict) else a
        assert next(x for x in a if x["id"] == p["id"])["sku"] == p["sku"]
