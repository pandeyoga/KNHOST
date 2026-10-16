"""Iter 321 — GET /api/inventory/rolls limit/skip/q + paged mode + outbound scan.

Verifies:
 - Bare-array mode honors ?limit, ?skip, ?q (search by roll_no/lot & product SKU/name).
 - Paged mode (?page=1&page_size=100) still returns envelope {items,total,has_more}.
 - Outbound scan style ?q=<roll_no>&status=available&limit=5.
"""
import os
import pytest
import requests

def _load_base_url() -> str:
    url = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not url:
        try:
            with open("C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/frontend/.env") as fh:
                for line in fh:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
        except FileNotFoundError:
            pass
    return url.rstrip("/")


BASE_URL = _load_base_url()
API = f"{BASE_URL}/api"
ENTITY = "ent_ksc"


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": "admin@kainnusantara.id",
                                          "password": "demo12345"})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok
    s.headers.update({"Authorization": f"Bearer {tok}",
                      "X-Entity-Id": ENTITY,
                      "Content-Type": "application/json"})
    return s


# ------------------- Bare array respects ?limit -------------------
def test_bare_default_has_capped_limit(admin_client):
    r = admin_client.get(f"{API}/inventory/rolls")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    # default limit is 5000 (capped), not the entire ~22985 rolls
    assert len(data) <= 5000


def test_bare_limit_100(admin_client):
    r = admin_client.get(f"{API}/inventory/rolls?limit=100")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 100, f"expected 100, got {len(data)}"


def test_bare_skip_returns_different_rows(admin_client):
    r0 = admin_client.get(f"{API}/inventory/rolls?limit=5&skip=0")
    r1 = admin_client.get(f"{API}/inventory/rolls?limit=5&skip=5")
    assert r0.status_code == 200 and r1.status_code == 200
    a = r0.json(); b = r1.json()
    assert len(a) == 5 and len(b) == 5
    ids_a = {x.get("id") or x.get("roll_no") for x in a}
    ids_b = {x.get("id") or x.get("roll_no") for x in b}
    assert ids_a.isdisjoint(ids_b), "skip should return different rolls"


def test_bare_q_filters_by_product_sku(admin_client):
    # pick an SKU in KSC scope
    r = admin_client.get(f"{API}/inventory/rolls?limit=1")
    assert r.status_code == 200
    rows = r.json()
    assert rows, "no rolls in KSC scope"
    sku = rows[0].get("sku")
    assert sku
    rq = admin_client.get(f"{API}/inventory/rolls", params={"q": sku, "limit": 200})
    assert rq.status_code == 200
    filtered = rq.json()
    assert filtered, "q by SKU returned empty"
    for r_ in filtered:
        assert r_.get("sku") == sku, f"row with sku {r_.get('sku')} slipped into q={sku}"


# ------------------- Paged mode envelope -------------------
def test_paged_envelope(admin_client):
    r = admin_client.get(f"{API}/inventory/rolls?page=1&page_size=100")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    for key in ("items", "total", "has_more"):
        assert key in data, f"missing {key}"
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 100
    assert data["total"] >= 100
    assert data["has_more"] is True


def test_paged_q_still_filters(admin_client):
    # search by known roll_no
    probe = admin_client.get(f"{API}/inventory/rolls?limit=1").json()
    rn = probe[0]["roll_no"]
    r = admin_client.get(f"{API}/inventory/rolls",
                         params={"page": 1, "page_size": 20, "q": rn})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert any(it.get("roll_no") == rn for it in data["items"])


# ------------------- Outbound scan style -------------------
def test_outbound_scan_q_available(admin_client):
    r = admin_client.get(f"{API}/inventory/rolls",
                         params={"q": "RL-00004", "status": "available", "limit": 5})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) <= 5
    # Must return matching roll if it exists in scope; if empty, that's still acceptable
    # (roll may belong to another entity). But if returned it must be available and match.
    for r_ in data:
        assert r_.get("status") == "available"
        assert "RL-00004" in (r_.get("roll_no", ""))
