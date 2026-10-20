"""L01 iter-185 — (1) SKU/nama disamarkan untuk Sales, (2) jalur 'tagih ganti rugi' tetap jalan,
(3) toleransi kontrak inline (PATCH) & toleransi langkah MKO. Jalankan: -n0."""
import re

import pytest
import requests

from tests.test_p05_acceptance_acc31_33_34 import BASE, DB, _create, _login

RAW = re.compile(r"\b[A-Z0-9]{9}-[A-Z]-[A-Z0-9]{4}-[A-Z0-9]{2}-[A-Z0-9]{2}-[A-Z0-9]{2}\b")


def _items(r):
    d = r.json()
    return d if isinstance(d, list) else d.get("items") or d.get("products") or d.get("data") or []


@pytest.fixture(scope="module")
def sales():
    return _login("sales.kanda@kainnusantara.id", "demo12345", ent="ent_kanda")


@pytest.fixture(scope="module")
def adm():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def mgr():
    return _login("manager@kainnusantara.id", "demo12345")


# --- (1) SKU / name masking for Sales
class TestSkuMask:
    def test_products_masked_for_sales(self, sales):
        r = requests.get(f"{BASE}/api/products?limit=1000", headers=sales, timeout=60)
        assert r.status_code == 200
        assert not RAW.findall(r.text)
        alice = [p for p in _items(r) if p.get("sku", "").startswith("KNKNT0005-")]
        assert alice and all(re.fullmatch(r"KNKNT0005-•-[A-Z0-9]{4}-••-XX-••", p["sku"]) for p in alice)
        assert all(not p["name"].endswith(" A") for p in alice)
        assert any(p["name"] == "ALICE KNIT (94139 - 45) 10" for p in alice)

    def test_admin_sees_raw(self, adm):
        r = requests.get(f"{BASE}/api/products?limit=1000", headers=adm, timeout=60)
        skus = {p.get("sku") for p in _items(r)}
        assert "KNKNT0005-I-10XX-XA-XX-XX" in skus

    def test_sales_orders_and_rolls_masked(self, sales):
        for path in ("/api/sales-orders?limit=50", "/api/inventory/rolls?limit=200"):
            r = requests.get(f"{BASE}{path}", headers=sales, timeout=60)
            assert r.status_code == 200, path
            assert not RAW.findall(r.text), path

    def test_so_detail_masked(self, sales):
        lst = _items(requests.get(f"{BASE}/api/sales-orders?limit=20", headers=sales, timeout=60))
        if not lst:
            pytest.skip("no SO for sales.kanda")
        r = requests.get(f"{BASE}/api/sales-orders/{lst[0]['id']}", headers=sales, timeout=60)
        assert r.status_code == 200
        assert not RAW.findall(r.text)

    def test_grade_suffix_stripped_where_no_sku_sibling(self, sales):
        """product_name in stock-summary / SO restock_requests / inventory rolls has no grade/sku sibling key."""
        full = {p["name"] for p in DB.products.find({"grade": {"$nin": [None, ""]}}, {"_id": 0, "name": 1, "grade": 1})
                if p["name"].endswith(" " + p["grade"])}
        pid = DB.products.find_one({"sku": "KNKNT0005-I-10XX-XA-XX-XX"})["id"]
        leaks = {}
        for path in (f"/api/sales/stock-summary?product_id={pid}", "/api/sales-orders?limit=50", "/api/inventory/rolls?limit=300"):
            t = requests.get(f"{BASE}{path}", headers=sales, timeout=60).text
            hits = [n for n in full if f'"{n}"' in t]
            if hits:
                leaks[path] = hits[:2]
        assert not leaks, f"grade suffix still in names: {leaks}"

    def test_names_with_grade_and_lot_inside_not_leaking(self, sales, adm):
        """Names like 'BAMBU KNIT B - 1 A LOT B' (grade A + LOT B) — grade/lot should not stay visible."""
        a = {p["id"]: p for p in _items(requests.get(f"{BASE}/api/products?limit=1000", headers=adm, timeout=60))}
        s = _items(requests.get(f"{BASE}/api/products?limit=1000", headers=sales, timeout=60))
        leaks = [(a[p["id"]]["name"], p["name"]) for p in s
                 if p["id"] in a and a[p["id"]].get("grade") and re.search(r"\bLOT\b", p.get("name") or "")]
        assert not leaks, f"{len(leaks)} names still show grade/LOT: {leaks[:3]}"


# --- (2)+(3) MKO step tolerance + tagih_ganti path
class TestTagihGantiAndTolerance:
    S = {}

    def test_setup(self, adm):
        mko = _create(adm, 30, "TEST_L01 tagih ganti")
        r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/issue", json={"step_seq": 1}, headers=adm, timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/cancel", json={"reason": "TEST_L01 batal"},
                             headers=adm, timeout=60).status_code == 200
        self.S["mko"] = mko

    def test_tolerance_validation(self, adm, sales):
        url = f"{BASE}/api/makloon-orders/{self.S['mko']['id']}/steps/1/tolerance"
        assert requests.post(url, json={"tolerance_pct": -1, "reason": "TEST_L01 neg"}, headers=adm, timeout=30).status_code == 400
        assert requests.post(url, json={"tolerance_pct": 5, "reason": "x"}, headers=adm, timeout=30).status_code == 400
        assert requests.post(url, json={"tolerance_pct": 5, "reason": "TEST_L01 sales"}, headers=sales, timeout=30).status_code in (403, 404)
        r = requests.post(url, json={"tolerance_pct": 0, "reason": "TEST_L01 nol"}, headers=adm, timeout=30)
        assert r.status_code == 200 and r.json()["steps"][0]["tolerance_pct"] == 0
        g = requests.get(f"{BASE}/api/makloon-orders/{self.S['mko']['id']}", headers=adm, timeout=30).json()
        assert g["steps"][0]["tolerance_pct"] == 0
        assert any(t.get("event") == "tolerance_changed" for t in g.get("timeline", []))

    def test_potong_bon_without_bill_400(self, adm, mgr):
        url = f"{BASE}/api/makloon-orders/{self.S['mko']['id']}/steps/1/material-loss"
        r = requests.post(url, json={"reason": "TEST_L01 hilang semua"}, headers=adm, timeout=60)
        assert r.status_code == 200, r.text[:300]
        loss = r.json()["steps"][0]["material_losses"][-1]
        assert loss["status"] == "pending_approval"
        self.S["loss"] = loss
        dec = f"{url}/{loss['id']}/decide"
        assert requests.post(dec, json={"approve": True, "settle": "potong_bon"}, headers=mgr, timeout=30).status_code == 400
        assert requests.post(dec, json={"approve": True, "settle": "xx"}, headers=mgr, timeout=30).status_code == 400
        assert requests.post(dec, json={"approve": True, "settle": "potong_bon", "bill_id": "vb_nope"},
                             headers=mgr, timeout=30).status_code == 400

    def test_tagih_ganti_path(self, mgr):
        url = f"{BASE}/api/makloon-orders/{self.S['mko']['id']}/steps/1/material-loss/{self.S['loss']['id']}/decide"
        r = requests.post(url, json={"approve": True, "settle": "tagih_ganti", "note": "TEST_L01 ok"}, headers=mgr, timeout=60)
        assert r.status_code == 200, r.text[:300]
        loss = r.json()["steps"][0]["material_losses"][-1]
        assert loss["status"] == "posted" and loss["settle"] == "tagih_ganti" and loss["bill_id"] == ""
        assert loss["claim_value"] > 0
        je = list(DB.journal_entries.find({"source_type": "makloon_material_loss",
                                           "source_id": {"$regex": self.S["mko"]["id"]}}, {"_id": 0, "lines": 1}))
        codes = {ln["account_code"] for j in je for ln in j["lines"] if ln["debit"] > 0}
        assert "1-1260" in codes and "2-1100" not in codes

    def test_tolerance_after_closed_409(self, adm):
        url = f"{BASE}/api/makloon-orders/{self.S['mko']['id']}/steps/1/tolerance"
        assert requests.post(url, json={"tolerance_pct": 3, "reason": "TEST_L01 sesudah tutup"},
                             headers=adm, timeout=30).status_code == 409


# --- (3) contract tolerance inline PATCH
class TestContractTolerance:
    def test_patch_contract_tolerance(self, adm):
        r = requests.get(f"{BASE}/api/supplier-contracts?limit=50", headers=adm, timeout=30)
        assert r.status_code == 200
        rows = _items(r)
        assert rows
        c = rows[0]
        old = c.get("tolerance_pct")
        try:
            p = requests.patch(f"{BASE}/api/supplier-contracts/{c['id']}", json={"tolerance_pct": 4.5}, headers=adm, timeout=30)
            assert p.status_code == 200, p.text[:200]
            g = requests.get(f"{BASE}/api/supplier-contracts/{c['id']}", headers=adm, timeout=30).json()
            assert float(g.get("tolerance_pct")) == 4.5
            bad = requests.patch(f"{BASE}/api/supplier-contracts/{c['id']}", json={"tolerance_pct": 150}, headers=adm, timeout=30)
            assert bad.status_code in (400, 422), f"150% accepted: {bad.status_code}"
        finally:
            DB.supplier_contracts.update_one({"id": c["id"]}, {"$set": {"tolerance_pct": old}})
