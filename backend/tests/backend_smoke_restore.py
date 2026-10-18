"""Smoke tests after repo restore — read-only checks."""
import os
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    # fallback: read frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE = line.split("=", 1)[1].strip().rstrip("/")
                break

EMAIL = "admin@kainnusantara.id"
PASSWORD = "demo12345"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    tok = data.get("access_token") or data.get("token") or data.get("session_token")
    assert tok, f"no token in response keys={list(data.keys())}"
    return tok


def H(tok, ent="ent_ksc"):
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": ent}


def test_root_api():
    r = requests.get(f"{BASE}/api/", timeout=15)
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"


def test_login_returns_token(token):
    assert isinstance(token, str) and len(token) > 10


def test_interco_settlements_transfer_posted(token):
    # per request: use entity header for ent_kanda (payer/buyer)
    r = requests.get(f"{BASE}/api/interco/settlements",
                     headers=H(token, "ent_kanda"), timeout=30)
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("settlements") or []
    assert len(items) >= 1, f"no settlements returned: {str(data)[:300]}"
    match = [s for s in items
             if (s.get("method") == "transfer") and (s.get("status") == "posted")]
    assert match, f"no settlement with method=transfer status=posted; sample={items[0]}"


def test_design_gallery_parang_modern(token):
    r = requests.get(f"{BASE}/api/design-gallery",
                     headers=H(token, "ent_ksc"), timeout=30)
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("designs") or []
    parang = [d for d in items if "Parang Modern Monokrom" in (d.get("title") or "")]
    assert parang, f"design 'Parang Modern Monokrom' not found in {len(items)} designs"
    d = parang[0]
    status = d.get("status") or d.get("lifecycle_status")
    assert status == "approved", f"expected approved, got status={status}, design={d}"


def test_interco_transactions_min4_with_draft_and_confirmed(token):
    r = requests.get(f"{BASE}/api/interco/transactions",
                     headers=H(token, "ent_ksc"), timeout=30)
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("transactions") or []
    assert len(items) >= 4, f"expected >=4 interco tx, got {len(items)}"
    statuses = {s.get("status") for s in items}
    assert "draft" in statuses, f"no draft transaction; statuses={statuses}"
    assert statuses & {"confirmed", "settled", "posted"}, \
        f"no confirmed/settled transaction; statuses={statuses}"
