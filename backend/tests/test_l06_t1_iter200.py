"""T1 iter200 — Verify POS sample limits (standard/hanger over-limit) and
Meja Cutting wait-time instrumentation (wait_thresholds, late_count, cut_at,
wait_minutes sort + banner level math, and transition to 'ready' with
received_at delta).

Covers review-request Features A (sample limits backend) and B (cutting desk
waiting time).
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ENT_KSC = "ent_ksc"
CUST, ADDR, PROD_WOVEN = "cust_butik_bali", "addr_002", "prod_batik_mega"
TAG = "T1I200"


def _login(email, pw="demo1234"):
    DB.login_attempts.delete_many({})
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT_KSC}


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def sampleadmin():
    return _login("sampleadmin@kainnusantara.id")


@pytest.fixture(scope="module")
def knit_product():
    """Pick any knit (kg) product; sample limit check uses product.fabric_type regardless of stock."""
    p = DB.products.find_one({"base_unit": "kg", "fabric_type": "knit", "exclusive_customer_id": {"$in": [None, ""]}}, {"_id": 0, "id": 1, "name": 1})
    if not p:
        pytest.skip("no knit product in DB")
    return p


@pytest.fixture(scope="module")
def created_sos(admin):
    ids = []
    yield ids
    for sid in ids:
        try:
            requests.post(f"{BASE}/sales-orders/{sid}/cancel",
                          json={"reason": f"{TAG} cleanup"}, headers=admin, timeout=60)
        except Exception:
            pass
        DB.wms_tasks.delete_many({"order_id": sid, "task_subtype": "sample_cut"})


# ────────────────────────────────────────────────────────────────────────
# A. Sample limits (SAMPLE_LIMIT 400)
# ────────────────────────────────────────────────────────────────────────
def _mk_sample_so(headers, product_id, qty, kind, unit):
    return requests.post(f"{BASE}/sales-orders", headers=headers, timeout=60, json={
        "customer_id": CUST, "shipping_address_id": ADDR, "entity_id": ENT_KSC,
        "order_type": "sample", "sample_billing": "free",
        "items": [{"product_id": product_id, "quantity": qty, "unit": unit,
                   "base_quantity": qty, "is_sample": True, "sample_kind": kind}]})


def test_sample_woven_standard_within_limit_ok(admin, created_sos):
    r = _mk_sample_so(admin, PROD_WOVEN, 5.0, "standard", "yard")
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    created_sos.append(j["id"])
    it = j["items"][0]
    assert it.get("is_sample") and it.get("sample_kind") == "standard"
    assert abs(float(it.get("quantity")) - 5.0) < 0.01


def test_sample_woven_standard_over_limit_400(admin):
    r = _mk_sample_so(admin, PROD_WOVEN, 6.0, "standard", "yard")
    assert r.status_code == 400, r.text[:300]
    detail = r.json().get("detail")
    assert isinstance(detail, dict) and detail.get("code") == "SAMPLE_LIMIT"
    assert detail.get("kind") == "standard"
    assert float(detail.get("max_qty")) == 5.0


def test_sample_woven_hanger_at_limit_ok(admin, created_sos):
    r = _mk_sample_so(admin, PROD_WOVEN, 0.5, "hanger", "yard")
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    created_sos.append(j["id"])
    assert j["items"][0]["sample_kind"] == "hanger"


def test_sample_woven_hanger_over_limit_400(admin):
    r = _mk_sample_so(admin, PROD_WOVEN, 1.0, "hanger", "yard")
    assert r.status_code == 400, r.text[:300]
    d = r.json().get("detail")
    assert d.get("code") == "SAMPLE_LIMIT" and d.get("kind") == "hanger"
    assert float(d.get("max_qty")) == 0.5


def test_sample_knit_standard_over_limit_400(admin, knit_product):
    r = _mk_sample_so(admin, knit_product["id"], 3.0, "standard", "kg")
    # Must be 400 SAMPLE_LIMIT (limit check happens before any stock lookup).
    assert r.status_code == 400, r.text[:300]
    d = r.json().get("detail")
    assert isinstance(d, dict) and d.get("code") == "SAMPLE_LIMIT", d
    assert float(d.get("max_qty")) == 2.0


def test_sample_knit_hanger_over_limit_400(admin, knit_product):
    r = _mk_sample_so(admin, knit_product["id"], 2.5, "hanger", "kg")
    assert r.status_code == 400, r.text[:300]
    d = r.json().get("detail")
    assert isinstance(d, dict) and d.get("code") == "SAMPLE_LIMIT"
    # knit hanger limit = 2 kg per spec
    assert float(d.get("max_qty")) == 2.0


# ────────────────────────────────────────────────────────────────────────
# B. Cutting desk waiting time
# ────────────────────────────────────────────────────────────────────────
def test_cutting_desk_shape_thresholds(sampleadmin):
    r = requests.get(f"{BASE}/cutting/desk", headers=sampleadmin, timeout=30)
    assert r.status_code == 200, r.text[:200]
    j = r.json()
    th = j.get("wait_thresholds") or {}
    assert th.get("warn_minutes") == 120 and th.get("late_minutes") == 240, th
    assert "late_count" in j and isinstance(j["late_count"], int)
    # queue keys and ordering
    keys = [q["key"] for q in j["queues"]]
    assert keys == ["awaiting_internal", "to_cut", "to_receive", "ready"]
    # every to_receive/ready row has cut_at + wait_minutes keys; others wait_minutes None
    for q in j["queues"]:
        for row in q["rows"]:
            assert "cut_at" in row and "wait_minutes" in row
            if q["key"] in ("to_receive", "ready"):
                # wait_minutes may be None if cut_at missing on legacy rows but should be int otherwise
                if row.get("cut_at"):
                    assert isinstance(row["wait_minutes"], int)


@pytest.fixture
def aged_cut_tasks(admin):
    """Create 2 synthetic sample_cut tasks aged 3h (warn) and 5h (late)."""
    roll = DB.inventory_rolls.find_one({"owner_entity_id": "ent_ksc", "status": "available",
                                        "length_remaining": {"$gt": 1.0}, "warehouse_id": "wh_jakarta"})
    if not roll:
        pytest.skip("no ksc roll in wh_jakarta available")
    now = datetime.now(timezone.utc)
    tasks = []
    for secs_hours, suffix in [(3, "warn"), (5, "late")]:
        tid = f"wt_{TAG}_wait_{suffix}"
        DB.wms_tasks.delete_one({"id": tid})
        cut_at = (now - timedelta(hours=secs_hours)).isoformat()
        DB.wms_tasks.insert_one({
            "id": tid, "task_subtype": "sample_cut", "entity_id": "ent_ksc",
            "order_id": f"so_{TAG}_wait_{suffix}", "order_number": f"{TAG}/SO-{suffix.upper()}",
            "warehouse_id": roll["warehouse_id"], "roll_id": roll["id"],
            "product_id": roll["product_id"], "unit": "yard",
            "child_roll_no": f"CHILD-{suffix}", "parent_roll_no": roll.get("roll_no", ""),
            "quantity": 1.0, "status": "picked",
            "created_at": (now - timedelta(hours=secs_hours + 1)).isoformat(),
            "cut_at": cut_at,
            "customer_name": "T1I200", "product_name": "T1I200 test"})
        tasks.append(tid)
    yield tasks
    for tid in tasks:
        DB.wms_tasks.delete_one({"id": tid})


def test_cutting_desk_wait_levels_sort_and_banner(admin, aged_cut_tasks):
    r = requests.get(f"{BASE}/cutting/desk", headers=admin, timeout=30)
    assert r.status_code == 200
    j = r.json()
    to_receive = next(q for q in j["queues"] if q["key"] == "to_receive")["rows"]
    rows_by_id = {r["task_id"]: r for r in to_receive}
    warn_id, late_id = aged_cut_tasks
    assert warn_id in rows_by_id and late_id in rows_by_id, list(rows_by_id)
    warn, late = rows_by_id[warn_id], rows_by_id[late_id]
    # wait_minutes approx (allow 2 min skew)
    assert 178 <= warn["wait_minutes"] <= 182, warn["wait_minutes"]
    assert 298 <= late["wait_minutes"] <= 302, late["wait_minutes"]
    # longer-wait first (late before warn)
    idx = [r["task_id"] for r in to_receive]
    assert idx.index(late_id) < idx.index(warn_id), idx
    # late_count counted at least our aged late one
    assert j["late_count"] >= 1


def test_cutting_desk_receive_moves_to_ready_with_delta(admin, aged_cut_tasks):
    """Receive one aged task; it moves to 'ready' queue with wait_minutes equal to
    elapsed minutes from cut_at to received_at (approx)."""
    warn_id, _late_id = aged_cut_tasks
    task_before = DB.wms_tasks.find_one({"id": warn_id}, {"_id": 0, "warehouse_id": 1})
    r = requests.post(f"{BASE}/cutting/tasks/{warn_id}/receive",
                     json={"to_warehouse_id": task_before["warehouse_id"]}, headers=admin, timeout=60)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert (body.get("cutting_handoff") or {}).get("received_at")

    r2 = requests.get(f"{BASE}/cutting/desk", headers=admin, timeout=30)
    j = r2.json()
    ready = next(q for q in j["queues"] if q["key"] == "ready")["rows"]
    row = next((x for x in ready if x["task_id"] == warn_id), None)
    assert row is not None, "received task not in ready queue"
    # should still be approx 180 min (3h) since receive is same-warehouse near-instant
    assert 178 <= row["wait_minutes"] <= 185, row["wait_minutes"]
    assert row.get("cut_at")
    # banner thresholds echoed
    assert j["wait_thresholds"]["warn_minutes"] == 120


# ────────────────────────────────────────────────────────────────────────
# Convert sample-over-limit to retail path (FE-side) — backend regression:
# we at least verify that creating a regular (non-sample) retail SO with the
# same product+quantity that was rejected as hanger over-limit DOES succeed.
# ────────────────────────────────────────────────────────────────────────
def test_regular_retail_at_over_sample_qty_ok(admin, created_sos):
    """1 yd of woven is over hanger limit — but as a regular (ecer) retail SO it
    is accepted (the frontend 'Jadikan ecer' button toggles is_sample off)."""
    r = requests.post(f"{BASE}/sales-orders", headers=admin, timeout=60, json={
        "customer_id": CUST, "shipping_address_id": ADDR, "entity_id": ENT_KSC,
        "items": [{"product_id": PROD_WOVEN, "quantity": 1.0, "unit": "yard",
                   "base_quantity": 1.0}]})
    # retail SO may 200 or 409 for credit — we only care there's no SAMPLE_LIMIT.
    if r.status_code == 200:
        created_sos.append(r.json()["id"])
    elif r.status_code in (400, 409):
        txt = r.text.lower()
        assert "sample_limit" not in txt, r.text[:300]
    else:
        pytest.fail(f"unexpected status {r.status_code}: {r.text[:200]}")
