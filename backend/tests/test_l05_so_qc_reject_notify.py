"""L05 — re-QC ditolak membatalkan lulus lama (per roll), notifikasi petugas QC, qc_status di daftar pengiriman."""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

from tests.test_l05_so_qc_retest_t1 import BASE, CUST, ADDR, ENT, PROD, _finish, admin  # noqa: F401

DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def so(admin):  # noqa: F811
    r = requests.post(f"{BASE}/sales-orders", json={
        "customer_id": CUST, "shipping_address_id": ADDR, "entity_id": ENT, "qc_request": "full",
        "items": [{"product_id": PROD, "quantity": 10.0, "unit": "yard", "base_quantity": 10.0}]}, headers=admin, timeout=120)
    assert r.status_code == 200, r.text[:300]
    doc = r.json()
    dlv = f"dlv_t_{uuid.uuid4().hex[:6]}"
    DB.logistics_deliveries.insert_one({"id": dlv, "number": "DLV-TEST", "order_id": doc["id"], "order_number": doc["number"],
                              "entity_id": ENT, "status": "prepared", "mode": "expedition", "created_at": "2099-01-01"})
    yield doc
    requests.post(f"{BASE}/sales-orders/{doc['id']}/cancel", json={"reason": "TEST cleanup reqc"}, headers=admin, timeout=60)
    DB.inspections.delete_many({"ref_doc_id": doc["id"]})
    DB.notifications.delete_many({"ref": {"$regex": f"^so_qc:{doc['id']}"}})
    DB.logistics_deliveries.delete_one({"id": dlv})


def _advance(admin, so):  # noqa: F811
    tid = f"wt_rq_{uuid.uuid4().hex[:8]}"
    DB.wms_tasks.insert_one({"id": tid, "flow_type": "outbound", "status": "staging", "entity_id": ENT,
                             "stages": ["created", "picking", "packing", "staging", "dispatched"],
                             "order_id": so["id"], "order_number": so["number"], "product_id": PROD,
                             "quantity": 10, "picked_qty": 10, "shipped_qty": 0, "unit": "yard", "_test_t1": True})
    try:
        return requests.post(f"{BASE}/wms/tasks/{tid}/advance", headers=admin, timeout=60)
    finally:
        DB.wms_tasks.delete_one({"id": tid})


def _qc_status(admin, sid):  # noqa: F811
    rows = requests.get(f"{BASE}/logistics/deliveries", params={"order_id": sid}, headers=admin, timeout=30).json()
    rows = rows.get("items", rows) if isinstance(rows, dict) else rows
    return rows[0].get("qc_status")


def test_notification_sent_to_qc_users(so):
    notes = list(DB.notifications.find({"type": "so_qc_requested", "ref": {"$regex": f"^so_qc:{so['id']}#"}}, {"_id": 0}))
    assert notes, "petugas QC tidak menerima notifikasi"
    assert all(n["recipient_user"] and n["entity_id"] == ENT for n in notes)
    assert so["number"] in notes[0]["title"]


def test_badge_and_reject_after_pass_blocks(admin, so):  # noqa: F811
    sid = so["id"]
    assert _qc_status(admin, sid) == "required"
    s1 = requests.post(f"{BASE}/inspections", json={"kind": "sales_order", "ref_doc_id": sid}, headers=admin, timeout=30)
    assert s1.status_code == 200, s1.text[:300]
    assert _finish(admin, s1.json(), "terima").status_code == 200
    assert _qc_status(admin, sid) == "passed"
    s2 = requests.post(f"{BASE}/inspections", json={"kind": "sales_order", "ref_doc_id": sid}, headers=admin, timeout=30)
    assert s2.status_code == 200, s2.text[:300]
    assert _finish(admin, s2.json(), "tolak").status_code == 200
    a = _advance(admin, so)
    assert a.status_code == 400 and "meminta QC" in a.text, a.text[:300]
    assert _qc_status(admin, sid) == "failed"
