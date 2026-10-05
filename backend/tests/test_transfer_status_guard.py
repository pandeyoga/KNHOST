"""Targeted tests for transfer status transition guards and inter-company bug fix."""
import os, uuid, requests, pytest
from pathlib import Path

def _load_be():
    envp = Path("/app/frontend/.env")
    for line in envp.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL missing")

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _load_be()).rstrip("/")
EMAIL = "admin@kainnusantara.id"
PWD = "demo12345"
ENT = "ent_ksc"


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PWD})
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    sess.headers.update({"Authorization": f"Bearer {tok}", "X-Entity-Id": ENT})
    return sess


def _find_roll(s):
    r = s.get(f"{BASE}/api/inventory/rolls", params={"warehouse_id": "wh_jakarta", "status": "available", "limit": 5})
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else (data.get("items") or [])
    return items[0] if items else None


def _create_transfer(s, roll):
    body = {
        "source_warehouse_id": "wh_jakarta",
        "dest_warehouse_id": "wh_bandung",
        "notes": f"TEST_guard_{uuid.uuid4().hex[:6]}",
        "items": [{"roll_ids": [roll["id"]], "product_id": roll["product_id"], "qty": 0, "unit": roll.get("unit", "meter")}],
    }
    r = s.post(f"{BASE}/api/transfers", json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()


def test_status_endpoint_rejects_dedicated_statuses(s):
    roll = _find_roll(s)
    if not roll:
        pytest.skip("no available roll in wh_jakarta")
    t = _create_transfer(s, roll)
    tid = t["id"]
    try:
        for status in ("cancelled", "approved", "rejected"):
            r = s.post(f"{BASE}/api/transfers/{tid}/status", json={"status": status})
            assert r.status_code == 400, f"{status} -> {r.status_code} {r.text}"
    finally:
        s.delete(f"{BASE}/api/transfers/{tid}", params={"reason": "TEST_cleanup"})


def test_skip_transition_rejected(s):
    roll = _find_roll(s)
    if not roll:
        pytest.skip("no available roll")
    t = _create_transfer(s, roll)
    tid = t["id"]
    try:
        ap = s.post(f"{BASE}/api/transfers/{tid}/approve", json={})
        assert ap.status_code == 200, ap.text
        # skip picking/staging -> dispatched should fail
        skip = s.post(f"{BASE}/api/transfers/{tid}/status", json={"status": "dispatched"})
        assert skip.status_code == 400, skip.text
    finally:
        s.delete(f"{BASE}/api/transfers/{tid}", params={"reason": "TEST_cleanup"})


def _get_roll(s, rid):
    for st in ("reserved", "available", "in_transit", "transferred"):
        r = s.get(f"{BASE}/api/inventory/rolls", params={"status": st, "limit": 500})
        data = r.json()
        items = data if isinstance(data, list) else (data.get("items") or [])
        for it in items:
            if it.get("id") == rid:
                return it
    return None


def test_delete_cancel_releases_rolls(s):
    roll = _find_roll(s)
    if not roll:
        pytest.skip("no available roll")
    t = _create_transfer(s, roll)
    tid = t["id"]
    rid = roll["id"]
    # roll should be reserved now
    rr = _get_roll(s, rid)
    assert rr is not None, "roll not found"
    assert rr.get("status") == "reserved", f"roll status: {rr.get('status')}"
    # cancel via DELETE
    d = s.delete(f"{BASE}/api/transfers/{tid}", params={"reason": "TEST_cancel"})
    assert d.status_code == 200, d.text
    g = s.get(f"{BASE}/api/transfers/{tid}")
    assert g.status_code == 200
    assert g.json().get("status") == "cancelled"
    assert "TEST_cancel" in (g.json().get("cancelled_reason") or "")
    # roll back to available
    rr2 = _get_roll(s, rid)
    assert rr2.get("status") == "available"
    assert rr2.get("reserved_ref") in (None, "", "null")


def test_inter_company_persists_doc(s):
    # need an inventory product id used across entities; pick first product with jakarta stock
    r = s.get(f"{BASE}/api/inventory/rolls", params={"warehouse_id": "wh_jakarta", "status": "available", "limit": 1})
    items = r.json() if isinstance(r.json(), list) else (r.json().get("items") or [])
    if not items:
        pytest.skip("no stock")
    roll = items[0]
    body = {
        "source_entity_id": "ent_ksc",
        "dest_entity_id": "ent_kanda",
        "notes": f"TEST_ic_{uuid.uuid4().hex[:6]}",
        "items": [{"product_id": roll["product_id"], "quantity": 1, "unit": roll.get("unit", "roll")}],
    }
    rr = s.post(f"{BASE}/api/transfers/inter-company", json=body)
    assert rr.status_code in (200, 201), rr.text
    tid = rr.json().get("id")
    assert tid, rr.text
    g = s.get(f"{BASE}/api/transfers/{tid}")
    assert g.status_code == 200, f"inter-company transfer not persisted: {g.status_code} {g.text}"
    # cleanup
    s.delete(f"{BASE}/api/transfers/{tid}", params={"reason": "TEST_cleanup"})
