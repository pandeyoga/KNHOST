"""COMM-04 retest: Idempotency-Key on POST /api/marketing/campaigns/{cid}/costs (double submit → one cost, one JE)."""
import concurrent.futures as cf
import uuid

import pytest

from test_comm04_ln042t03_regression import BASE, db, login


@pytest.fixture(scope="module")
def admin():
    return login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def campaign(admin):
    r = admin.post(f"{BASE}/marketing/campaigns", json={"name": "TEST_T1 Idem", "budget": 1000000})
    assert r.status_code in (200, 201), r.text
    c = r.json()
    yield c
    costs = list(db.mkt_campaign_costs.find({"campaign_id": c["id"]}))
    for cost in costs:
        cid = cost.get("cash_txn_id")
        if cid:
            db.journal_entries.delete_many({"source_id": cid})
            db.cash_transactions.delete_one({"id": cid})
        for k in ("journal_entry_id", "void_journal_entry_id"):
            if cost.get(k):
                db.journal_entries.delete_one({"id": cost[k]})
    db.journal_entries.delete_many({"source_id": {"$in": [x["id"] for x in costs]}})
    db.mkt_campaign_costs.delete_many({"campaign_id": c["id"]})
    db.mkt_campaigns.delete_one({"id": c["id"]})
    db.idempotency_keys.delete_many({"path": {"$regex": c["id"]}})


def _url(c):
    return f"{BASE}/marketing/campaigns/{c['id']}/costs"


class TestIdempotency:
    def test_same_key_sequential_replay(self, admin, campaign):
        key = f"TEST_{uuid.uuid4().hex}"
        body = {"amount": 12345, "description": "TEST_idem seq", "cash_type": "kas_besar"}
        r1 = admin.post(_url(campaign), json=body, headers={"Idempotency-Key": key})
        r2 = admin.post(_url(campaign), json=body, headers={"Idempotency-Key": key})
        assert r1.status_code == 200, r1.text
        assert r2.status_code == 200, r2.text
        assert r1.json()["id"] == r2.json()["id"]
        assert r2.headers.get("X-Idempotent-Replay") == "true"
        docs = list(db.mkt_campaign_costs.find({"campaign_id": campaign["id"], "description": "TEST_idem seq"}))
        assert len(docs) == 1
        assert db.journal_entries.count_documents({"id": docs[0]["journal_entry_id"]}) == 1
        assert db.cash_transactions.count_documents({"id": docs[0]["cash_txn_id"]}) == 1

    def test_same_key_different_payload_409(self, admin, campaign):
        key = f"TEST_{uuid.uuid4().hex}"
        r1 = admin.post(_url(campaign), json={"amount": 1000, "description": "TEST_idem a"}, headers={"Idempotency-Key": key})
        assert r1.status_code == 200
        r2 = admin.post(_url(campaign), json={"amount": 2000, "description": "TEST_idem a"}, headers={"Idempotency-Key": key})
        assert r2.status_code == 409
        assert r2.json()["detail"]["code"] == "IDEMPOTENCY_KEY_REUSED"

    def test_same_key_concurrent(self, admin, campaign):
        key = f"TEST_{uuid.uuid4().hex}"
        body = {"amount": 777, "description": "TEST_idem conc"}
        with cf.ThreadPoolExecutor(4) as ex:
            rs = list(ex.map(lambda _: admin.post(_url(campaign), json=body, headers={"Idempotency-Key": key}), range(4)))
        codes = sorted(r.status_code for r in rs)
        assert all(c in (200, 409) for c in codes), codes
        assert db.mkt_campaign_costs.count_documents({"campaign_id": campaign["id"], "description": "TEST_idem conc"}) == 1
        ids = {r.json()["id"] for r in rs if r.status_code == 200}
        assert len(ids) == 1

    def test_different_keys_create_two(self, admin, campaign):
        body = {"amount": 500, "description": "TEST_idem diff"}
        for _ in range(2):
            assert admin.post(_url(campaign), json=body, headers={"Idempotency-Key": f"TEST_{uuid.uuid4().hex}"}).status_code == 200
        assert db.mkt_campaign_costs.count_documents({"campaign_id": campaign["id"], "description": "TEST_idem diff"}) == 2

    def test_summary_realized(self, admin, campaign):
        s = admin.get(_url(campaign)).json()
        # 12345 + 1000 + 777 + 500*2
        assert s["realized"] == 15122, s
