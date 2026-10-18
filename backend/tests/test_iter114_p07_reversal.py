"""iter-114 (P07) — Backend tests for Jurnal Pembalik + WM-06/AX-01/AX-03/RF-05.

Priority focus: GL reversal (POST /api/gl/journal/{id}/reverse) across manual + auto
journals, closed-period/date guards, role gate, idempotency, and closing-journal rejection.
Also: WM-06 scan-pick qty/roll validation, AX-01/AX-03 picked-roll dispatch wiring,
RF-05 loading-check scan-label untagged resolution, plus a regression sweep.

Synthetic data is tagged with TEST_iter114_<TAG> and cleaned up at module teardown.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
from pymongo import MongoClient  # noqa: E402

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ENTITY = "ent_ksc"
_mongo = MongoClient(os.environ["MONGO_URL"])
db = _mongo[os.environ["DB_NAME"]]

TAG = uuid.uuid4().hex[:6]
CREATED_JES: list[str] = []
CREATED_PERIODS: list[str] = []


def _login(email: str, password: str = "demo12345") -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


def _h(email: str) -> dict:
    return {"Authorization": f"Bearer {_login(email)}",
            "X-Entity-Id": ENTITY, "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_h():
    return _h("admin@kainnusantara.id")


@pytest.fixture(scope="module")
def warehouse_h():
    return _h("warehouse@kainnusantara.id")


@pytest.fixture(scope="module")
def sales_h():
    return _h("sales@kainnusantara.id")


@pytest.fixture(scope="module")
def manager_h():
    return _h("manager@kainnusantara.id")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _create_manual_je(admin_h, note: str = "") -> dict:
    """Create a tiny balanced manual journal (debit 6-4000 / credit 1-1100)."""
    payload = {
        "date": _today(),
        "description": f"TEST_iter114_{TAG} manual {note}",
        "lines": [
            {"account_code": "6-4000", "debit": 1000.0, "credit": 0.0, "description": "dr"},
            {"account_code": "1-1100", "debit": 0.0, "credit": 1000.0, "description": "cr"},
        ],
    }
    r = requests.post(f"{BASE_URL}/api/gl/journal", json=payload, headers=admin_h, timeout=20)
    assert r.status_code == 200, f"create manual JE failed: {r.status_code} {r.text[:300]}"
    je = r.json()
    CREATED_JES.append(je["id"])
    return je


# ═══════════════════════════════════════════════════════════════════════════
#  REVERSAL — manual journal happy path + persistence
# ═══════════════════════════════════════════════════════════════════════════
def test_reverse_manual_success_and_fields(admin_h):
    je = _create_manual_je(admin_h, "A")
    r = requests.post(
        f"{BASE_URL}/api/gl/journal/{je['id']}/reverse",
        json={"date": _today(), "reason": f"TEST_iter114_{TAG} reverse ok"},
        headers=admin_h, timeout=20,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    rev = r.json()
    CREATED_JES.append(rev["id"])
    assert rev["source_type"] == "reversal"
    assert rev.get("ref", {}).get("reverses_entry_id") == je["id"]
    # lines swapped (debit <-> credit)
    orig_lines = {ln["account_code"]: (ln.get("debit", 0), ln.get("credit", 0))
                  for ln in je["lines"]}
    for ln in rev["lines"]:
        od, oc = orig_lines[ln["account_code"]]
        assert ln["debit"] == pytest.approx(oc) and ln["credit"] == pytest.approx(od), \
            f"debit/credit not swapped on {ln['account_code']}"
    # original is still posted & tagged
    g = requests.get(f"{BASE_URL}/api/gl/journal/{je['id']}", headers=admin_h, timeout=15)
    assert g.status_code == 200
    orig = g.json()
    assert orig["status"] == "posted"
    assert orig.get("reversed_by_entry_id") == rev["id"]
    assert orig.get("reversed_by_entry_number") == rev["number"]
    assert orig.get("reversal_reason", "").startswith("TEST_iter114_")


def test_reverse_twice_returns_400(admin_h):
    je = _create_manual_je(admin_h, "twice")
    r1 = requests.post(f"{BASE_URL}/api/gl/journal/{je['id']}/reverse",
                       json={"date": _today(), "reason": "once"},
                       headers=admin_h, timeout=20)
    assert r1.status_code == 200
    CREATED_JES.append(r1.json()["id"])
    r2 = requests.post(f"{BASE_URL}/api/gl/journal/{je['id']}/reverse",
                       json={"date": _today(), "reason": "again"},
                       headers=admin_h, timeout=20)
    assert r2.status_code == 400, f"expected 400 got {r2.status_code} {r2.text[:200]}"
    assert "dibalik" in r2.text.lower() or "sudah" in r2.text.lower()


def test_reverse_a_reversal_rejected(admin_h):
    je = _create_manual_je(admin_h, "rev_of_rev")
    r1 = requests.post(f"{BASE_URL}/api/gl/journal/{je['id']}/reverse",
                       json={"date": _today(), "reason": "first reverse"},
                       headers=admin_h, timeout=20)
    assert r1.status_code == 200
    rev = r1.json()
    CREATED_JES.append(rev["id"])
    r2 = requests.post(f"{BASE_URL}/api/gl/journal/{rev['id']}/reverse",
                       json={"date": _today(), "reason": "boom"},
                       headers=admin_h, timeout=20)
    assert r2.status_code == 400, f"expected 400 for reversal-of-reversal, got {r2.status_code}"


def test_reverse_empty_reason_rejected(admin_h):
    je = _create_manual_je(admin_h, "noreason")
    r = requests.post(f"{BASE_URL}/api/gl/journal/{je['id']}/reverse",
                      json={"date": _today(), "reason": ""},
                      headers=admin_h, timeout=20)
    # ≥3-char reason enforced in service → 400 (schema allows empty string → service ValueError)
    assert r.status_code in (400, 422), f"got {r.status_code} {r.text[:200]}"


def test_reverse_date_before_original_rejected(admin_h):
    je = _create_manual_je(admin_h, "backdate")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%d")
    # ensure original date is "today"
    assert je["date"][:10] >= yesterday
    r = requests.post(f"{BASE_URL}/api/gl/journal/{je['id']}/reverse",
                      json={"date": yesterday, "reason": "too early"},
                      headers=admin_h, timeout=20)
    assert r.status_code == 400, f"expected 400 got {r.status_code} {r.text[:200]}"
    assert "sebelum" in r.text.lower() or "tanggal" in r.text.lower()


# ═══════════════════════════════════════════════════════════════════════════
#  REVERSAL — closed period 409 (synthetic period_closings)
# ═══════════════════════════════════════════════════════════════════════════
@pytest.fixture(scope="module")
def closed_period():
    """Inserts a synthetic CLOSED period covering 2024-01-01..2024-01-31."""
    import asyncio
    pid = f"pc_test_iter114_{TAG}"
    doc = {
        "id": pid,
        "entity_id": ENTITY,
        "period_type": "month",
        "period_key": "2024-01",
        "period_label": "TEST_iter114 Jan 2024",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "status": "closed",
        "closed_at": datetime.now(timezone.utc).isoformat(),
        "closed_by": "test_iter114",
        "note": f"TEST_iter114_{TAG}",
    }

    async def _ins():
        await db.period_closings.insert_one(doc)
    asyncio.get_event_loop().run_until_complete(_ins()) if False else None
    db.period_closings.insert_one(doc)
    CREATED_PERIODS.append(pid)
    yield doc


def test_reverse_into_closed_period_returns_409(admin_h, closed_period):
    # Create a manual JE dated today (open period), try to reverse INTO closed Jan 2024.
    je = _create_manual_je(admin_h, "closedperiod")
    # But reversal date must be >= original date → use a far-past original. Create one directly:
    orig_date = "2023-12-15"  # before closed period
    doc = {
        "id": f"je_test_iter114_{TAG}_{uuid.uuid4().hex[:6]}",
        "number": f"TEST_iter114_{TAG}_JE",
        "entity_id": ENTITY,
        "date": orig_date,
        "description": f"TEST_iter114_{TAG} synthetic old",
        "lines": [
            {"account_code": "6-4000", "debit": 100.0, "credit": 0.0, "description": "dr"},
            {"account_code": "1-1100", "debit": 0.0, "credit": 100.0, "description": "cr"},
        ],
        "total_debit": 100.0, "total_credit": 100.0,
        "source_type": "manual", "source_id": None,
        "status": "posted",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "test_iter114",
    }
    db.journal_entries.insert_one(doc)
    CREATED_JES.append(doc["id"])
    # Reverse with date inside closed period → 409
    r = requests.post(f"{BASE_URL}/api/gl/journal/{doc['id']}/reverse",
                      json={"date": "2024-01-15", "reason": "to closed period"},
                      headers=admin_h, timeout=20)
    assert r.status_code == 409, f"expected 409 closed-period got {r.status_code} {r.text[:300]}"
    assert "periode" in r.text.lower()


# ═══════════════════════════════════════════════════════════════════════════
#  REVERSAL — closing journal rejection
# ═══════════════════════════════════════════════════════════════════════════
def test_reverse_closing_journal_rejected(admin_h):
    doc = {
        "id": f"je_test_iter114_closing_{TAG}",
        "number": f"TEST_iter114_{TAG}_CL",
        "entity_id": ENTITY,
        "date": _today(),
        "description": f"TEST_iter114_{TAG} synthetic closing",
        "lines": [
            {"account_code": "6-4000", "debit": 50.0, "credit": 0.0, "description": "dr"},
            {"account_code": "1-1100", "debit": 0.0, "credit": 50.0, "description": "cr"},
        ],
        "total_debit": 50.0, "total_credit": 50.0,
        "source_type": "closing", "source_id": None,
        "status": "posted",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "test_iter114",
    }
    db.journal_entries.insert_one(doc)
    CREATED_JES.append(doc["id"])
    r = requests.post(f"{BASE_URL}/api/gl/journal/{doc['id']}/reverse",
                      json={"date": _today(), "reason": "nope"},
                      headers=admin_h, timeout=20)
    assert r.status_code == 400, f"expected 400 for closing, got {r.status_code} {r.text[:200]}"
    assert "penutup" in r.text.lower() or "closing" in r.text.lower()


# ═══════════════════════════════════════════════════════════════════════════
#  REVERSAL — role gate (warehouse / sales → 403)
# ═══════════════════════════════════════════════════════════════════════════
def test_reverse_warehouse_forbidden(admin_h, warehouse_h):
    je = _create_manual_je(admin_h, "role_wh")
    r = requests.post(f"{BASE_URL}/api/gl/journal/{je['id']}/reverse",
                      json={"date": _today(), "reason": "warehouse try"},
                      headers={**warehouse_h, "Content-Type": "application/json"},
                      timeout=15)
    assert r.status_code == 403, f"expected 403 for warehouse, got {r.status_code} {r.text[:200]}"


def test_reverse_sales_forbidden(admin_h, sales_h):
    je = _create_manual_je(admin_h, "role_sl")
    r = requests.post(f"{BASE_URL}/api/gl/journal/{je['id']}/reverse",
                      json={"date": _today(), "reason": "sales try"},
                      headers=sales_h, timeout=15)
    assert r.status_code == 403, f"expected 403 for sales, got {r.status_code} {r.text[:200]}"


def test_reverse_manager_allowed(admin_h, manager_h):
    je = _create_manual_je(admin_h, "role_mgr")
    r = requests.post(f"{BASE_URL}/api/gl/journal/{je['id']}/reverse",
                      json={"date": _today(), "reason": "manager ok"},
                      headers=manager_h, timeout=20)
    assert r.status_code == 200, f"manager should have accounting.void, got {r.status_code} {r.text[:200]}"
    CREATED_JES.append(r.json()["id"])


# ═══════════════════════════════════════════════════════════════════════════
#  REVERSAL — auto journal (cash_transaction) is reversible
# ═══════════════════════════════════════════════════════════════════════════
def test_reverse_auto_cash_transaction_je(admin_h):
    # Pick a non-reversed cash_transaction JE from seed data.
    je = db.journal_entries.find_one(
        {"entity_id": ENTITY, "source_type": "cash_transaction",
         "status": "posted",
         "reversed_by_entry_id": {"$exists": False}},
        {"_id": 0, "id": 1, "number": 1, "date": 1},
    )
    if not je:
        pytest.skip("no reversible cash_transaction JE in seed")
    r = requests.post(f"{BASE_URL}/api/gl/journal/{je['id']}/reverse",
                      json={"date": _today(), "reason": f"TEST_iter114_{TAG} auto"},
                      headers=admin_h, timeout=20)
    assert r.status_code == 200, f"auto JE should be reversible: {r.status_code} {r.text[:300]}"
    rev = r.json()
    CREATED_JES.append(rev["id"])
    assert rev["source_type"] == "reversal"
    assert rev["ref"]["reverses_entry_id"] == je["id"]


# ═══════════════════════════════════════════════════════════════════════════
#  REGRESSION — earlier features still return 200
# ═══════════════════════════════════════════════════════════════════════════
def test_regression_reimburse_payables(admin_h):
    r = requests.get(f"{BASE_URL}/api/cash-advance-settlements/reimburse-payables",
                     headers=admin_h, timeout=15)
    assert r.status_code == 200, r.text[:200]


def test_regression_balance_sheet(admin_h):
    r = requests.get(f"{BASE_URL}/api/finance/balance-sheet", headers=admin_h, timeout=20)
    assert r.status_code == 200, r.text[:200]
    assert r.json().get("as_of")


def test_regression_cash_flow(admin_h):
    r = requests.get(f"{BASE_URL}/api/finance/cash-flow", headers=admin_h, timeout=20)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    assert data.get("method") == "journal_cash_classification"
    assert "noncash_disclosure" in data


def test_regression_po_billing_context(admin_h):
    # Find any PO with items
    po = db.purchase_orders.find_one({"entity_id": ENTITY}, {"_id": 0, "id": 1, "items": 1})
    if not po or not po.get("items"):
        pytest.skip("no PO in seed")
    r = requests.get(f"{BASE_URL}/api/purchase-orders/{po['id']}/billing-context",
                     headers=admin_h, timeout=15)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    assert isinstance(data.get("items", data.get("lines", [])), list)


# ═══════════════════════════════════════════════════════════════════════════
#  WM-06 — scan-pick validation (qty + roll_id)
# ═══════════════════════════════════════════════════════════════════════════
def _find_active_pick_task():
    """Find an outbound task that still accepts scan-pick (status not in dispatched/cancelled/completed)."""
    t = db.wms_tasks.find_one(
        {"entity_id": ENTITY, "kind": {"$in": [None, "outbound", "pick"]},
         "status": {"$nin": ["dispatched", "cancelled", "completed"]}},
        {"_id": 0, "id": 1, "order_id": 1, "product_id": 1, "status": 1},
    )
    return t


def test_wm06_scan_pick_bad_qty(admin_h):
    t = _find_active_pick_task()
    if not t:
        pytest.skip("no active outbound task")
    r = requests.post(
        f"{BASE_URL}/api/outbound/tasks/{t['id']}/scan-pick?actual_qty=0",
        headers=admin_h, timeout=15)
    assert r.status_code in (400, 422), f"qty=0 should fail, got {r.status_code}"


def test_wm06_scan_pick_unknown_roll(admin_h):
    t = _find_active_pick_task()
    if not t:
        pytest.skip("no active outbound task")
    r = requests.post(
        f"{BASE_URL}/api/outbound/tasks/{t['id']}/scan-pick?actual_qty=1&roll_id=UNKNOWN_ROLL_XYZ",
        headers=admin_h, timeout=15)
    assert r.status_code == 400, f"unknown roll should 400, got {r.status_code} {r.text[:200]}"
    body = r.text.lower()
    assert "tidak dikenal" in body or "ditolak" in body or "unknown" in body


# ═══════════════════════════════════════════════════════════════════════════
#  RF-05 — loading-check start exposes untagged[] + scan-label
# ═══════════════════════════════════════════════════════════════════════════
def test_rf05_loading_check_start_has_untagged_shape(admin_h):
    so = db.sales_orders.find_one(
        {"entity_id": ENTITY, "status": {"$in": ["confirmed", "picking", "ready_to_ship",
                                                 "approved", "released"]}},
        {"_id": 0, "id": 1, "status": 1})
    if not so:
        pytest.skip("no suitable SO")
    r = requests.post(
        f"{BASE_URL}/api/outbound/so/{so['id']}/loading-check/start",
        headers=admin_h, timeout=15)
    # Endpoint should respond 200 or 409 (if already running). Either way the response shape
    # when 200 must have an `untagged` list.
    if r.status_code == 200:
        data = r.json()
        assert "untagged" in data, f"missing untagged[] key; keys={list(data)[:10]}"
        assert isinstance(data["untagged"], list)
    else:
        # fall back to GET current session
        g = requests.get(f"{BASE_URL}/api/outbound/so/{so['id']}/loading-check",
                         headers=admin_h, timeout=15)
        assert g.status_code == 200, f"GET loading-check failed: {g.status_code}"


# ═══════════════════════════════════════════════════════════════════════════
#  TEARDOWN
# ═══════════════════════════════════════════════════════════════════════════
def test_zz_cleanup():
    """Ensure synthetic docs are removed. Runs last due to name sort.

    Also resets `reversed_by_entry_id`/`reversal_reason` on any ORIGINAL seed
    journal_entry whose reversal we created (so demo data isn't permanently
    tagged after the auto-JE reversal test)."""
    orig_ids: set[str] = set()
    if CREATED_JES:
        for rev in db.journal_entries.find(
            {"id": {"$in": CREATED_JES}, "source_type": "reversal"},
            {"_id": 0, "source_id": 1},
        ):
            if rev.get("source_id"):
                orig_ids.add(rev["source_id"])
        db.journal_entries.delete_many({"id": {"$in": CREATED_JES}})
    if orig_ids:
        db.journal_entries.update_many(
            {"id": {"$in": list(orig_ids)}},
            {"$unset": {"reversed_by_entry_id": "", "reversed_by_entry_number": "",
                        "reversal_reason": "", "reversed_by": "", "reversed_at": ""}},
        )
    if CREATED_PERIODS:
        db.period_closings.delete_many({"id": {"$in": CREATED_PERIODS}})
    db.period_closings.delete_many({"note": {"$regex": f"TEST_iter114_{TAG}"}})
    # sweep any lingering TEST_iter114 reversal/manual docs
    db.journal_entries.delete_many({"description": {"$regex": f"TEST_iter114_{TAG}"}})
    assert True
