"""Iter150: Stok & ATP numeric verification + config health regression (read-only)."""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8006").rstrip("/")
EMAIL = "admin@kainnusantara.id"
PASSWORD = "demo12345"
ENTITY = "ent_ksc"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json().get("token") or r.json().get("access_token")
    s.headers.update({"Authorization": f"Bearer {tok}", "X-Entity-Id": ENTITY, "Content-Type": "application/json"})
    return s


def test_config_health_green(client):
    r = client.get(f"{BASE}/api/config/health?entity_id={ENTITY}", timeout=30)
    assert r.status_code == 200
    data = r.json()
    summary = data.get("summary", {})
    assert summary.get("NOT_WIRED", 0) == 0, f"NOT_WIRED must be 0, got {summary}"
    assert summary.get("STALE_REF", 0) == 0, f"STALE_REF must be 0, got {summary}"
    assert summary.get("BAD_REF", 0) == 0, f"BAD_REF must be 0, got {summary}"
    print("Config health summary:", summary)


def test_audit_no_test_rows(client):
    r = client.get(f"{BASE}/api/audit-logs?limit=500&entity_id={ENTITY}", timeout=30)
    if r.status_code == 404:
        pytest.skip("audit-logs listing endpoint unavailable")
    assert r.status_code == 200, r.text
    items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    bad = [it for it in items if "TEST_" in (it.get("reason") or "") or "iter1" in (it.get("reason") or "").lower()]
    assert not bad, f"Found TEST-tagged audit rows: {bad[:3]}"


def test_atp_board_math(client):
    r = client.get(f"{BASE}/api/inventory/status-board?entity_id={ENTITY}", timeout=60)
    assert r.status_code == 200, r.text
    body = r.json()
    if isinstance(body, list):
        rows = body
        totals = {}
    else:
        rows = body.get("rows") or body.get("items") or []
        totals = body.get("totals") or {}
    assert rows, "No rows returned from status-board"

    atp_total = 0.0
    incoming_total = 0.0
    mismatches_atp = []
    mismatches_phys = []

    for row in rows:
        pid = row.get("product_id")
        available = float(row.get("total_available") or row.get("available") or 0)
        reserved = float(row.get("total_reserved") or row.get("reserved") or 0)
        incoming = float(row.get("total_incoming") or row.get("incoming") or 0)
        atp = float(row.get("total_atp") or row.get("atp") or 0)
        physical = float(row.get("total_on_hand") or row.get("physical") or row.get("on_hand") or 0)
        hold = float(row.get("total_hold") or 0)
        pending = float(row.get("total_pending_demand") or 0)

        atp_total += atp
        incoming_total += incoming

        # Formula from spec:
        # Tersedia + Incoming − tertunda = ATP
        # Tersedia + Dipesan + tertahan = Stok Fisik
        expected_atp = available + incoming - pending
        expected_phys = available + reserved + hold

        if abs(expected_atp - atp) > 0.5:
            mismatches_atp.append((pid, available, incoming, pending, atp, expected_atp))
        if abs(expected_phys - physical) > 0.5:
            mismatches_phys.append((pid, available, reserved, hold, physical, expected_phys))

    totals = totals or {}
    sum_total_atp = float(totals.get("total_atp") or totals.get("atp") or 0)
    sum_total_incoming = float(totals.get("total_incoming") or totals.get("incoming") or 0)

    print(f"Rows={len(rows)} atp_total(sum)={atp_total}")
    print(f"incoming_total(sum)={incoming_total}")
    print(f"ATP mismatches ({len(mismatches_atp)}): {mismatches_atp[:5]}")
    print(f"Physical mismatches ({len(mismatches_phys)}): {mismatches_phys[:5]}")

    assert not mismatches_atp, f"ATP formula mismatches: {mismatches_atp[:5]}"
    assert not mismatches_phys, f"Physical formula mismatches: {mismatches_phys[:5]}"
