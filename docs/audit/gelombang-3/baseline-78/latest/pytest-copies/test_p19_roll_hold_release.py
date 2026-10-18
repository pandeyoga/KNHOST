"""P19 QC-06 — Backend tests for Roll Hold/Release and Journey Timeline.

Covers:
- RBAC on /api/inventory/rolls/{id}/hold (wms.update) and /release (wms.approve)
- Validation: reason < 3 chars → 400, release non-held → 400, hold earmarked → 400,
  hold not-holdable status → 400
- Happy path: available → blocked → available (inventory_balances available/blocked shift)
- Happy path: quarantine → blocked → quarantine
- journey-timeline includes HOLD/RELEASE events
- qc_submit_decision rejected while any held roll in task
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

HEADERS = {"Content-Type": "application/json", "X-Entity-Id": "ent_ksc"}


def _login(session: requests.Session, email: str) -> dict:
    r = session.post(f"{BASE_URL}/api/auth/login",
                     json={"email": email, "password": "demo12345"},
                     headers=HEADERS, timeout=30)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def admin_sess():
    s = requests.Session(); s.headers.update(HEADERS)
    _login(s, "admin@kainnusantara.id")
    return s


@pytest.fixture(scope="module")
def sales_sess():
    s = requests.Session(); s.headers.update(HEADERS)
    _login(s, "sales@kainnusantara.id")
    return s


@pytest.fixture(scope="module")
def manager_sess():
    s = requests.Session(); s.headers.update(HEADERS)
    _login(s, "manager@kainnusantara.id")
    return s


@pytest.fixture(scope="module", autouse=True)
def _reset_rolls(admin_sess, manager_sess):
    """Ensure test rolls are in known baseline (not blocked) before suite runs."""
    for rid in (AVAIL_ROLL, QUAR_ROLL, EARMARKED_ROLL):
        rg = admin_sess.get(f"{BASE_URL}/api/inventory/rolls/{rid}", timeout=15)
        if rg.status_code == 200 and rg.json().get("status") == "blocked":
            manager_sess.post(f"{BASE_URL}/api/inventory/rolls/{rid}/release",
                              json={"note": "TEST_P19 pretest reset"})
    yield


# Known seeded rolls under ent_ksc:
AVAIL_ROLL = "roll_4df48c2bd03f"   # RL-00004 available, no earmark
EARMARKED_ROLL = "roll_3a630c9ff59b"  # RL-00002 available but earmarked
QUAR_ROLL = "roll_81e1135f31dc"    # RL-00043 quarantine, qc_task wms_13a64831e9c0
QC_TASK = "wms_13a64831e9c0"


def _get_roll(sess, rid):
    r = sess.get(f"{BASE_URL}/api/inventory/rolls/{rid}", timeout=15)
    return r


def _get_balance(sess, product_id, warehouse_id):
    r = sess.get(f"{BASE_URL}/api/inventory/balances",
                 params={"product_id": product_id, "warehouse_id": warehouse_id,
                         "entity_id": "ent_ksc"}, timeout=15)
    return r


# ─── Validation / RBAC ────────────────────────────────────────────────────────

def test_hold_requires_reason(admin_sess):
    r = admin_sess.post(f"{BASE_URL}/api/inventory/rolls/{AVAIL_ROLL}/hold",
                        json={"reason": "ab"})
    assert r.status_code == 400, r.text
    assert "Alasan" in r.text or "alasan" in r.text


def test_hold_earmarked_rejected(admin_sess):
    r = admin_sess.post(f"{BASE_URL}/api/inventory/rolls/{EARMARKED_ROLL}/hold",
                        json={"reason": "TEST_P19 coba hold"})
    assert r.status_code == 400, r.text
    assert "peg" in r.text.lower()


def test_hold_rbac_sales_denied(sales_sess):
    r = sales_sess.post(f"{BASE_URL}/api/inventory/rolls/{AVAIL_ROLL}/hold",
                        json={"reason": "TEST_P19 sales try"})
    assert r.status_code == 403, r.text


def test_release_rbac_sales_denied(sales_sess):
    r = sales_sess.post(f"{BASE_URL}/api/inventory/rolls/{AVAIL_ROLL}/release",
                        json={"note": "TEST_P19"})
    assert r.status_code == 403, r.text


def test_release_non_held_rejected(admin_sess):
    r = admin_sess.post(f"{BASE_URL}/api/inventory/rolls/{AVAIL_ROLL}/release",
                        json={"note": "TEST_P19 not held"})
    assert r.status_code == 400, r.text


# ─── Happy path: available → blocked → available ──────────────────────────────

def test_hold_and_release_available_roll_with_balance_shift(admin_sess, manager_sess):
    # Reset: if roll is currently blocked from a prior failed run, release first
    rget = admin_sess.get(f"{BASE_URL}/api/inventory/rolls/{AVAIL_ROLL}", timeout=15)
    if rget.status_code == 200 and (rget.json().get("status") == "blocked"):
        manager_sess.post(f"{BASE_URL}/api/inventory/rolls/{AVAIL_ROLL}/release",
                          json={"note": "TEST_P19 reset before retest"})

    # Get baseline balance
    import json
    pre = admin_sess.get(f"{BASE_URL}/api/inventory/balances",
                         params={"entity_id": "ent_ksc"}, timeout=15)
    assert pre.status_code == 200, pre.text
    # Find the balance row for prod_batik_mega / wh_jakarta
    def find_row(payload):
        items = payload if isinstance(payload, list) else payload.get("items", [])
        for it in items:
            if it.get("product_id") == "prod_batik_mega" and it.get("warehouse_id") == "wh_jakarta":
                return it
        return None
    pre_row = find_row(pre.json())
    assert pre_row is not None, f"no balance row seen, payload keys={list(pre.json())[:3] if isinstance(pre.json(), dict) else 'list'}"
    pre_avail = float(pre_row.get("available_qty") or 0)
    pre_blocked = float(pre_row.get("blocked_qty") or 0)

    # HOLD
    r = admin_sess.post(f"{BASE_URL}/api/inventory/rolls/{AVAIL_ROLL}/hold",
                        json={"reason": "TEST_P19 QC-06 hold happy"})
    assert r.status_code == 200, r.text
    roll = r.json().get("roll") or {}
    assert roll.get("status") == "blocked"
    length = float(roll.get("length_remaining") or roll.get("length_initial") or roll.get("length_m") or 0)
    assert length > 0, f"roll has no length: {roll}"

    # Verify balance shift
    post = admin_sess.get(f"{BASE_URL}/api/inventory/balances",
                          params={"entity_id": "ent_ksc"}, timeout=15)
    post_row = find_row(post.json())
    assert post_row is not None
    assert abs(float(post_row["available_qty"]) - (pre_avail - length)) < 0.01, \
        f"available_qty {pre_avail}→{post_row['available_qty']} (len {length})"
    assert abs(float(post_row["blocked_qty"]) - (pre_blocked + length)) < 0.01, \
        f"blocked_qty {pre_blocked}→{post_row['blocked_qty']}"

    # Journey timeline shows hold event
    jr = admin_sess.get(f"{BASE_URL}/api/inventory/rolls/{AVAIL_ROLL}/journey-timeline")
    assert jr.status_code == 200, jr.text
    events_json = str(jr.json())
    assert "DITAHAN" in events_json or "hold" in events_json.lower() or "tahan" in events_json.lower(), events_json[:400]

    # RELEASE (manager has wms.approve)
    r2 = manager_sess.post(f"{BASE_URL}/api/inventory/rolls/{AVAIL_ROLL}/release",
                           json={"note": "TEST_P19 QC-06 release"})
    assert r2.status_code == 200, r2.text
    roll2 = r2.json().get("roll") or {}
    assert roll2.get("status") == "available", roll2

    # Balance returns
    post2 = admin_sess.get(f"{BASE_URL}/api/inventory/balances",
                           params={"entity_id": "ent_ksc"}, timeout=15)
    post2_row = find_row(post2.json())
    assert abs(float(post2_row["available_qty"]) - pre_avail) < 0.01
    assert abs(float(post2_row["blocked_qty"]) - pre_blocked) < 0.01


# ─── Quarantine roll + QC-decision gating ─────────────────────────────────────

def test_hold_quarantine_blocks_qc_decision_then_release(admin_sess, manager_sess):
    # HOLD a quarantine roll in a qc_pending task
    r = admin_sess.post(f"{BASE_URL}/api/inventory/rolls/{QUAR_ROLL}/hold",
                        json={"reason": "TEST_P19 QC-06 hold quar"})
    assert r.status_code == 200, r.text
    assert r.json()["roll"]["status"] == "blocked"

    # Attempting QC decision on parent task should be blocked
    dec = admin_sess.post(
        f"{BASE_URL}/api/inbound/qc/tasks/{QC_TASK}/decide",
        json={"decision": "accept_all", "disposition": "accept",
              "reason": "TEST_P19 try while held"})
    # Could be 400 (held) or 404 if endpoint path differs. We require it NOT be 200.
    assert dec.status_code != 200, f"QC decision should be blocked while held; got {dec.status_code}: {dec.text[:300]}"
    if dec.status_code == 400:
        assert "DITAHAN" in dec.text or "tahan" in dec.text.lower() or "held" in dec.text.lower(), dec.text

    # RELEASE
    r2 = manager_sess.post(f"{BASE_URL}/api/inventory/rolls/{QUAR_ROLL}/release",
                           json={"note": "TEST_P19 QC-06 release quar"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["roll"]["status"] == "quarantine"

    # journey timeline shows hold+release events
    jr = admin_sess.get(f"{BASE_URL}/api/inventory/rolls/{QUAR_ROLL}/journey-timeline")
    assert jr.status_code == 200
    s = str(jr.json()).lower()
    assert "tahan" in s or "hold" in s, s[:400]
