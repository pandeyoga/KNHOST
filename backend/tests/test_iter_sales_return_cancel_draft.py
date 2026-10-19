# Retest: sales return reject on draft -> 400; new cancel-draft endpoint (draft->cancelled, else 400, no stock/GL effects)
import os
import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
_db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
SO_NUMBER = "KSC/SO-00002"


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=20)
    assert r.status_code == 200
    tok = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture(scope="module")
def draft(admin):
    so = _db.sales_orders.find_one({"number": SO_NUMBER}, {"_id": 0})
    it = so["items"][0]
    body = {"order_id": so["id"], "return_type": "retur", "notes": "TEST_cancel_draft", "submit_now": False,
            "items": [{"product_id": it["product_id"], "product_name": it.get("product_name", ""),
                       "quantity_returned": 1, "unit": it.get("unit", "yard"), "reason": "TEST"}]}
    r = requests.post(f"{BASE}/sales-returns", headers=admin, json=body, timeout=40)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "draft"
    yield d
    _db.sales_returns.delete_one({"id": d["id"]})
    _db.audit_logs.delete_many({"entity_id": d["id"]})


def test_reject_draft_returns_400(admin, draft):
    r = requests.post(f"{BASE}/sales-returns/{draft['id']}/reject", headers=admin, json={"notes": "TEST"}, timeout=20)
    assert r.status_code == 400, r.text
    assert isinstance(r.json().get("detail"), str)


def test_cancel_draft_ok_and_no_side_effects(admin, draft):
    mv_before = _db.stock_movements.count_documents({"reference_id": draft["id"]}) if "stock_movements" in _db.list_collection_names() else 0
    r = requests.post(f"{BASE}/sales-returns/{draft['id']}/cancel-draft", headers=admin, json={}, timeout=20)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"
    assert "_id" not in r.json()
    g = requests.get(f"{BASE}/sales-returns/{draft['id']}", headers=admin, timeout=20)
    assert g.status_code == 200 and g.json()["status"] == "cancelled"
    refs = {"$or": [{"reference_id": draft["id"]}, {"source_id": draft["id"]}, {"ref_id": draft["id"]}]}
    for coll in ("stock_movements", "journal_entries", "inventory_movements", "gl_entries"):
        if coll in _db.list_collection_names():
            assert _db[coll].count_documents(refs) == (mv_before if coll == "stock_movements" else 0), coll


def test_cancel_draft_twice_400(admin, draft):
    r = requests.post(f"{BASE}/sales-returns/{draft['id']}/cancel-draft", headers=admin, json={}, timeout=20)
    assert r.status_code == 400


def test_cancel_non_draft_400(admin):
    other = _db.sales_returns.find_one({"status": {"$in": ["pending_approval", "approved"]}}, {"_id": 0, "id": 1, "status": 1})
    if not other:
        pytest.skip("no non-draft return")
    r = requests.post(f"{BASE}/sales-returns/{other['id']}/cancel-draft", headers=admin, json={}, timeout=20)
    assert r.status_code == 400
    assert _db.sales_returns.find_one({"id": other["id"]})["status"] == other["status"]


def test_cancel_missing_404(admin):
    r = requests.post(f"{BASE}/sales-returns/sret_TEST_nope/cancel-draft", headers=admin, json={}, timeout=20)
    assert r.status_code == 404
