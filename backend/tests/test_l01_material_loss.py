"""L01 — susut/hilang bahan di mitra (keputusan owner 2026-10-16): toleransi → beban,
di atas toleransi → persetujuan terpisah → klaim mitra (1-1260). Pencatat ≠ penyetuju."""
import pytest
import requests

from tests.test_p05_acceptance_acc31_33_34 import BASE, DB, _create, _login, _tpl, _wip, cancel_test_mkos


@pytest.fixture(scope="module")
def adm():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def mgr():
    return _login("manager@kainnusantara.id", "demo1234")


@pytest.fixture(scope="module", autouse=True)
def output_is_makloon():
    out = DB.products.find_one({"id": _tpl()["steps"][0]["output_product_id"]}, {"_id": 0, "template_id": 1})
    tpl = DB.product_templates.find_one({"id": out["template_id"]}, {"_id": 0, "id": 1, "restock_source": 1})
    before = tpl.get("restock_source")
    DB.product_templates.update_one({"id": tpl["id"]}, {"$set": {"restock_source": {"mode": "makloon", "note": "TEST_L01"}}})
    cancel_test_mkos()
    yield
    cancel_test_mkos()
    if before:
        DB.product_templates.update_one({"id": tpl["id"]}, {"$set": {"restock_source": before}})


def _je(mko_number, code):
    tot = 0.0
    for j in DB.journal_entries.find({"source_type": "makloon_material_loss", "source_label": {"$regex": f"^{mko_number}"}},
                                     {"_id": 0, "lines": 1}):
        tot += sum(float(ln.get("debit") or 0) for ln in j["lines"] if ln["account_code"] == code)
    return round(tot, 2)


class TestMaterialLoss:
    S = {}

    def test_setup_cancelled_mko(self, adm):
        mko = _create(adm, 30, "TEST_L01 susut")
        r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/issue", json={"step_seq": 1}, headers=adm, timeout=60)
        assert r.status_code == 200, r.text[:300]
        self.S.update(mko=mko, value=float(r.json()["steps"][0]["material_value"]))
        assert requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/cancel", json={"reason": "TEST_L01 batal"},
                             headers=adm, timeout=60).status_code == 200
        d = requests.get(f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/partner-rolls", headers=adm, timeout=30).json()
        assert d["tolerance_pct"] >= 0 and d["rolls"]
        self.S["rolls"] = d["rolls"]
        self.S["tol"] = d["tolerance_pct"]

    def test_sales_cannot_record(self):
        s = _login("sales.kanda@kainnusantara.id", "demo1234")
        mko = self.S["mko"]
        r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/material-loss",
                          json={"reason": "TEST_L01 x"}, headers=s, timeout=30)
        assert r.status_code in (403, 404)

    def test_over_tolerance_pending_and_sod(self, adm, mgr):
        mko, roll = self.S["mko"], self.S["rolls"][0]
        url = f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/material-loss"
        r = requests.post(url, json={"reason": "TEST_L01 hilang di mitra", "roll_ids": [roll["id"]]}, headers=adm, timeout=60)
        assert r.status_code == 200, r.text[:300]
        loss = r.json()["steps"][0]["material_losses"][-1]
        q = float(roll["length_remaining"])
        assert loss["status"] == "pending_approval"
        assert loss["within_qty"] == pytest.approx(min(q, 30 * self.S["tol"] / 100), abs=0.05)
        assert _wip(mko["mko_number"]) == pytest.approx(self.S["value"], abs=1)      # belum dibukukan
        # roll yang sama tidak bisa dicatat dua kali selagi menunggu
        assert requests.post(url, json={"reason": "TEST_L01 ganda", "roll_ids": [roll["id"]]},
                             headers=adm, timeout=30).status_code == 409
        dec = f"{url}/{loss['id']}/decide"
        assert requests.post(dec, json={"approve": True}, headers=adm, timeout=30).status_code == 403   # pencatat
        r = requests.post(dec, json={"approve": True, "note": "TEST_L01 setuju"}, headers=mgr, timeout=60)
        assert r.status_code == 200, r.text[:300]
        loss = r.json()["steps"][0]["material_losses"][-1]
        assert loss["status"] == "posted" and loss["claim_value"] > 0
        assert _je(mko["mko_number"], "1-1260") == pytest.approx(loss["claim_value"], abs=0.5)
        assert _je(mko["mko_number"], "5-9500") == pytest.approx(loss["expense_value"], abs=0.5)
        assert _wip(mko["mko_number"]) == pytest.approx(self.S["value"] - loss["value"], abs=1)
        assert requests.post(dec, json={"approve": True}, headers=mgr, timeout=30).status_code == 409

    def test_within_tolerance_auto_and_closes(self, adm):
        mko = self.S["mko"]
        if len(self.S["rolls"]) < 2:   # data-dependent: one issued roll is fully consumed by the previous test
            pytest.skip("Hanya 1 roll dikirim ke mitra — tidak ada sisa untuk uji dalam toleransi")
        DB.makloon_orders.update_one({"id": mko["id"]}, {"$set": {"steps.0.tolerance_pct": 100.0}})
        r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/material-loss",
                          json={"reason": "TEST_L01 susut sisa"}, headers=adm, timeout=60)
        assert r.status_code == 200, r.text[:300]
        st = r.json()["steps"][0]
        assert st["material_losses"][-1]["status"] == "posted"
        assert st["material_losses"][-1]["claim_value"] == pytest.approx(0, abs=0.01)
        assert st["status"] == "returned" and r.json()["material_at_partner"] is False
        assert _wip(mko["mko_number"]) == pytest.approx(0, abs=1)


class TestLossDeductBillAndTolerance:
    S = {}

    def test_setup(self, adm):
        mko = _create(adm, 30, "TEST_L01 potong bon")
        r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/issue", json={"step_seq": 1}, headers=adm, timeout=60)
        assert r.status_code == 200, r.text[:300]
        step = r.json()["steps"][0]
        assert requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/cancel", json={"reason": "TEST_L01 batal"},
                             headers=adm, timeout=60).status_code == 200
        import uuid
        small, big = f"vb_test_{uuid.uuid4().hex[:8]}", f"vb_test_{uuid.uuid4().hex[:8]}"
        base = {"makloon_id": step["makloon_id"], "supplier_id": step["makloon_id"], "entity_id": mko["entity_id"],
                "status": "posted", "amount_paid": 0.0, "created_at": "2026-10-16T00:00:00+00:00", "notes": "TEST_L01"}
        DB.vendor_bills.insert_many([{**base, "id": small, "bill_number": "TEST-L01-S", "grand_total": 1.0, "net_amount": 1.0},
                                     {**base, "id": big, "bill_number": "TEST-L01-B", "grand_total": 9e7, "net_amount": 9e7}])
        self.S.update(mko=mko, small=small, big=big, value=float(step["material_value"]))

    def test_step_tolerance_endpoint(self, adm):
        mko = self.S["mko"]
        url = f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/tolerance"
        assert requests.post(url, json={"tolerance_pct": 150, "reason": "TEST_L01 x"}, headers=adm, timeout=30).status_code == 400
        r = requests.post(url, json={"tolerance_pct": 0, "reason": "TEST_L01 tanpa toleransi"}, headers=adm, timeout=30)
        assert r.status_code == 200, r.text[:200]
        assert r.json()["steps"][0]["tolerance_pct"] == 0

    def test_deduct_bill(self, adm, mgr):
        mko = self.S["mko"]
        url = f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/material-loss"
        r = requests.post(url, json={"reason": "TEST_L01 hilang semua"}, headers=adm, timeout=60)
        assert r.status_code == 200, r.text[:300]
        loss = r.json()["steps"][0]["material_losses"][-1]
        assert loss["status"] == "pending_approval" and loss["within_qty"] == 0
        bills = requests.get(f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/deductible-bills", headers=mgr, timeout=30).json()
        assert {self.S["small"], self.S["big"]} <= {b["id"] for b in bills}
        dec = f"{url}/{loss['id']}/decide"
        r = requests.post(dec, json={"approve": True, "settle": "potong_bon", "bill_id": self.S["small"]}, headers=mgr, timeout=60)
        assert r.status_code == 409, r.text[:200]                       # sisa tagihan tidak cukup
        assert DB.inventory_rolls.count_documents({"bucket_ref.id": r.request and DB.makloon_orders.find_one(
            {"id": mko["id"]})["steps"][0]["issue_ref"], "status": "subcon"}) > 0   # roll tidak terkonsumsi
        assert DB.vendor_bills.find_one({"id": self.S["small"]})["grand_total"] == pytest.approx(1.0)
        r = requests.post(dec, json={"approve": True, "settle": "potong_bon", "bill_id": self.S["big"]}, headers=mgr, timeout=60)
        assert r.status_code == 200, r.text[:300]
        loss = r.json()["steps"][0]["material_losses"][-1]
        assert loss["status"] == "posted" and loss["settle"] == "potong_bon"
        assert loss["claim_value"] == pytest.approx(self.S["value"], abs=1)
        bill = DB.vendor_bills.find_one({"id": self.S["big"]})
        assert bill["grand_total"] == pytest.approx(9e7 - loss["claim_value"], abs=0.5)
        assert _je(mko["mko_number"], "2-1100") == pytest.approx(loss["claim_value"], abs=0.5)
        assert _wip(mko["mko_number"]) == pytest.approx(0, abs=1)

    def test_cleanup(self):
        DB.vendor_bills.delete_many({"id": {"$in": [self.S["small"], self.S["big"]]}})
