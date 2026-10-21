"""Regression: COMM-04 (biaya kampanye → jurnal Beban Pemasaran) + LN-042-T03 (reprint label roll, EPC tetap).
Runs against public URL; DB used only for verification / setup / cleanup (all TEST_ data removed)."""
import concurrent.futures as cf
import os

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def login(email, pw, ent="ent_ksc"):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login {email} failed {r.status_code}")
    tok = r.json().get("token") or r.json().get("session_token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    s.headers["X-Entity-Id"] = ent
    return s


def bal(code, ent="ent_ksc"):
    tot = 0.0
    for je in db.journal_entries.find({"entity_id": ent, "status": {"$ne": "void"}, "lines.account_code": code}):
        for ln in je["lines"]:
            if ln["account_code"] == code:
                tot += ln.get("debit", 0) - ln.get("credit", 0)
    return round(tot, 2)


@pytest.fixture(scope="module")
def admin():
    return login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def manager():
    return login("manager@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def sales():
    return login("sales@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def kanda():
    return login("sales.kanda@kainnusantara.id", "demo12345", ent="ent_kanda")


# ---------------- COMM-04 ----------------
@pytest.fixture(scope="module")
def campaign(admin):
    r = admin.post(f"{BASE}/marketing/campaigns", json={"name": "TEST_T1 Kampanye", "budget": 1000000})
    assert r.status_code in (200, 201), r.text
    c = r.json()
    yield c
    costs = list(db.mkt_campaign_costs.find({"campaign_id": c["id"]}))
    for cost in costs:
        cid = cost.get("cash_txn_id")
        if cid:
            db.journal_entries.delete_many({"source_id": cid})
            db.cash_transactions.delete_one({"id": cid})
    db.journal_entries.delete_many({"source_id": {"$in": [x["id"] for x in costs]}})
    db.mkt_campaign_costs.delete_many({"campaign_id": c["id"]})
    db.mkt_campaigns.delete_one({"id": c["id"]})


class TestComm04:
    state = {}

    def test_record_cost_posts_journal(self, admin, campaign):
        b0, k0 = bal("6-4700"), bal("1-1100")
        r = admin.post(f"{BASE}/marketing/campaigns/{campaign['id']}/costs",
                       json={"amount": 250000, "description": "Iklan IG", "date": "", "cash_type": "kas_besar"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "posted" and d["journal_entry_number"] and d["cash_txn_number"]
        je = db.journal_entries.find_one({"id": d["journal_entry_id"]})
        dr = [l for l in je["lines"] if l.get("debit", 0) > 0]
        cr = [l for l in je["lines"] if l.get("credit", 0) > 0]
        assert any(l["account_code"] == "6-4700" and l["debit"] == 250000 for l in dr), je["lines"]
        assert any(l["account_code"] == "1-1100" and l["credit"] == 250000 for l in cr), je["lines"]
        assert bal("6-4700") - b0 == 250000 and k0 - bal("1-1100") == 250000
        TestComm04.state["cost"] = d

    def test_summary_and_list(self, admin, campaign):
        s = admin.get(f"{BASE}/marketing/campaigns/{campaign['id']}/costs").json()
        assert (s["budget"], s["realized"], s["remaining"], s["over_budget"]) == (1000000, 250000, 750000, False)
        row = [x for x in admin.get(f"{BASE}/marketing/campaigns").json() if x["id"] == campaign["id"]][0]
        assert row["cost_realized"] == 250000 and row["budget_remaining"] == 750000

    @pytest.mark.parametrize("payload", [
        {"amount": 0, "description": "Iklan"},
        {"amount": -5, "description": "Iklan"},
        {"amount": 1000, "description": "ab"},
        {"amount": 1000, "description": "Iklan", "cash_type": "bank_xyz"},
    ])
    def test_validation_400(self, admin, campaign, payload):
        r = admin.post(f"{BASE}/marketing/campaigns/{campaign['id']}/costs", json=payload)
        assert r.status_code == 400, r.text

    def test_sales_forbidden_manager_allowed(self, sales, manager, campaign):
        assert sales.post(f"{BASE}/marketing/campaigns/{campaign['id']}/costs",
                          json={"amount": 1000, "description": "TEST_sales"}).status_code == 403
        r = manager.post(f"{BASE}/marketing/campaigns/{campaign['id']}/costs",
                         json={"amount": 1000, "description": "TEST_mgr", "cash_type": "kas_kecil"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "posted"
        TestComm04.state["mgr_cost"] = r.json()

    def test_other_entity_cannot_post(self, kanda, campaign):
        r = kanda.post(f"{BASE}/marketing/campaigns/{campaign['id']}/costs", json={"amount": 1000, "description": "TEST_x"})
        assert r.status_code in (403, 404), r.status_code

    def test_direct_cash_void_blocked(self, admin):
        cost = TestComm04.state["cost"]
        assert admin.post(f"{BASE}/cash-transactions/{cost['cash_txn_id']}/void").status_code == 409

    def test_over_budget(self, admin, campaign):
        r = admin.post(f"{BASE}/marketing/campaigns/{campaign['id']}/costs", json={"amount": 900000, "description": "TEST_over"})
        assert r.status_code == 200
        s = admin.get(f"{BASE}/marketing/campaigns/{campaign['id']}/costs").json()
        assert s["over_budget"] is True and s["remaining"] < 0
        TestComm04.state["over_cost"] = r.json()

    def test_void_flow_concurrent(self, admin, campaign):
        cost = TestComm04.state["cost"]
        url = f"{BASE}/marketing/campaigns/{campaign['id']}/costs/{cost['id']}/void"
        assert admin.post(url, json={"reason": "x"}).status_code == 400
        b0 = bal("6-4700")
        with cf.ThreadPoolExecutor(2) as ex:
            res = list(ex.map(lambda _: admin.post(url, json={"reason": "salah input biaya"}), range(2)))
        codes = sorted(r.status_code for r in res)
        assert codes == [200, 409], codes
        ok = [r for r in res if r.status_code == 200][0].json()
        assert ok["status"] == "void" and ok["void_journal_entry_number"]
        assert db.journal_entries.count_documents({"source_type": "cash_transaction_void", "source_id": cost["cash_txn_id"]}) == 1
        assert round(b0 - bal("6-4700"), 2) == 250000
        assert admin.post(url, json={"reason": "ulang lagi"}).status_code == 409
        s = admin.get(f"{BASE}/marketing/campaigns/{campaign['id']}/costs").json()
        assert s["realized"] == 901000

    def test_void_unknown_cost_404(self, admin, campaign):
        r = admin.post(f"{BASE}/marketing/campaigns/{campaign['id']}/costs/mcc_nope/void", json={"reason": "tidak ada"})
        assert r.status_code == 404


# ---------------- LN-042-T03 ----------------
@pytest.fixture(scope="module")
def roll_ctx():
    roll = db.inventory_rolls.find_one({"owner_entity_id": "ent_ksc", "status": "available",
                                        "rfid_tag_id": {"$in": [None, ""]}, "length_remaining": {"$gt": 5}}, {"_id": 0})
    if not roll:
        pytest.skip("no roll")
    snap = dict(roll)
    ctx = {"roll": roll, "jobs": []}
    yield ctx
    # restore roll exactly + remove side effects
    tags = list(db.rfid_tags.find({"roll_id": roll["id"]}, {"id": 1}))
    db.rfid_tags.delete_many({"roll_id": roll["id"]})
    db.rfid_print_jobs.delete_many({"id": {"$in": ctx["jobs"]}})
    db.roll_label_prints.delete_many({"roll_id": roll["id"]})
    db.inventory_rolls.replace_one({"id": roll["id"]}, snap)
    print("cleanup tags", len(tags))


class TestLn042T03:
    def test_print_job_rfid_creates_tag_and_history(self, admin, roll_ctx):
        roll = roll_ctx["roll"]
        r = admin.post(f"{BASE}/rfid/print-jobs", json={"roll_ids": [roll["id"]]})
        assert r.status_code == 200, r.text
        job = r.json(); roll_ctx["jobs"].append(job["id"])
        assert job["kind"] == "rfid_tag"
        epc = job["items"][0]["epc"]; roll_ctx["epc"] = epc
        m = admin.post(f"{BASE}/rfid/print-jobs/{job['id']}/mark-printed")
        assert m.status_code == 200, m.text
        rows = list(db.roll_label_prints.find({"roll_id": roll["id"]}))
        assert len(rows) == 1 and rows[0]["channel"] == "print_queue" and rows[0]["epc"] == epc
        again = admin.post(f"{BASE}/rfid/print-jobs/{job['id']}/mark-printed")
        assert again.status_code in (400, 409)
        assert db.roll_label_prints.count_documents({"roll_id": roll["id"]}) == 1

    def test_second_job_reuses_tag(self, admin, roll_ctx):
        roll = roll_ctx["roll"]
        n_tags = db.rfid_tags.count_documents({"roll_id": roll["id"]})
        job = admin.post(f"{BASE}/rfid/print-jobs", json={"roll_ids": [roll["id"]]}).json()
        roll_ctx["jobs"].append(job["id"])
        assert job["items"][0]["epc"] == roll_ctx["epc"] and job["items"][0]["reprint"] is True
        assert admin.post(f"{BASE}/rfid/print-jobs/{job['id']}/mark-printed").status_code == 200
        assert db.rfid_tags.count_documents({"roll_id": roll["id"]}) == n_tags
        last = db.roll_label_prints.find_one({"roll_id": roll["id"]}, sort=[("at", -1)])
        assert last["print_seq"] == 2 and last["reprint"] is True and last["epc"] == roll_ctx["epc"]

    def test_browser_print_then_reprint_after_saldo_change(self, admin, roll_ctx):
        roll = roll_ctx["roll"]
        p1 = admin.post(f"{BASE}/rfid/rolls/{roll['id']}/label-prints", json={})
        assert p1.status_code == 200, p1.text
        p1 = p1.json()
        assert p1["epc"] == roll_ctx["epc"] and p1["qty"] == roll["length_remaining"] and p1["print_seq"] == 3
        db.inventory_rolls.update_one({"id": roll["id"]}, {"$inc": {"length_remaining": -1.5}})
        new_qty = roll["length_remaining"] - 1.5
        lk = admin.get(f"{BASE}/rfid/lookup", params={"code": roll["roll_no"], "record": "false"}).json()
        assert lk["label"]["label_outdated"] is True and abs(lk["label"]["current_qty"] - new_qty) < 1e-6
        assert lk["label"]["epc"] == roll_ctx["epc"]
        # lookup via EPC (RFID read) also returns ERP saldo
        lk2 = admin.get(f"{BASE}/rfid/lookup", params={"code": roll_ctx["epc"], "record": "false"}).json()
        assert lk2["via"] == "rfid" and abs(lk2["roll"]["length_remaining"] - new_qty) < 1e-6
        p2 = admin.post(f"{BASE}/rfid/rolls/{roll['id']}/label-prints", json={}).json()
        assert p2["reprint"] and p2["print_seq"] == 4 and abs(p2["qty"] - new_qty) < 1e-6
        assert p2["epc"] == roll_ctx["epc"] and p2["roll_id"] == roll["id"]
        assert db.inventory_rolls.count_documents({"roll_no": roll["roll_no"]}) == 1
        h = admin.get(f"{BASE}/rfid/rolls/{roll['id']}/print-history").json()
        assert h["label_outdated"] is False and h["prints_count"] == 4
        seqs = [p["print_seq"] for p in h["prints"]]
        assert seqs == sorted(seqs, reverse=True), seqs

    def test_entity_isolation(self, kanda, roll_ctx):
        rid = roll_ctx["roll"]["id"]
        assert kanda.get(f"{BASE}/rfid/rolls/{rid}/print-history").status_code in (403, 404)
        assert kanda.post(f"{BASE}/rfid/rolls/{rid}/label-prints", json={}).status_code in (403, 404)

    def test_unknown_roll_404(self, admin):
        assert admin.get(f"{BASE}/rfid/rolls/roll_nope/print-history").status_code == 404
