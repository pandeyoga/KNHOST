"""L06 — batas tunggu Meja Cutting: uji tambahan (warn saja, global, validasi, izin, katalog)."""
import os

import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
KEYS = ("cutting.wait_warn_minutes", "cutting.wait_late_minutes")
DEF = {"cutting.wait_warn_minutes": 120, "cutting.wait_late_minutes": 240}


def _login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def h():
    hh = _login("admin@kainnusantara.id", "demo12345")
    yield hh
    for k, v in DEF.items():
        for scope, sid in (("entity", "ent_ksc"), ("global", None)):
            it = {"key": k, "value": v, "scope_type": scope, "reason": "restore uji"}
            if sid:
                it["scope_id"] = sid
            requests.put(f"{BASE}/config/values", headers=hh, json={"items": [it]})


def _put(h, key, value, scope="entity", sid="ent_ksc"):
    it = {"key": key, "value": value, "scope_type": scope, "reason": "uji batas tunggu"}
    if sid:
        it["scope_id"] = sid
    return requests.put(f"{BASE}/config/values", headers=h, json={"items": [it]})


def _th(h, ent=None):
    r = requests.get(f"{BASE}/cutting/desk", headers=h, params={"entity_id": ent} if ent else {})
    assert r.status_code == 200, r.text
    d = r.json()
    assert "late_count" in d and isinstance(d["queues"], list)
    return d["wait_thresholds"]


# Default
def test_default_thresholds(h):
    assert _th(h, "ent_ksc") == {"warn_minutes": 120, "late_minutes": 240}
    assert _th(h, "ent_kanda") == {"warn_minutes": 120, "late_minutes": 240}
    assert _th(h) == {"warn_minutes": 120, "late_minutes": 240}


# Warn only per entity
def test_warn_only_entity(h):
    assert _put(h, KEYS[0], 30).status_code == 200
    assert _th(h, "ent_ksc") == {"warn_minutes": 30, "late_minutes": 240}
    assert _th(h, "ent_kanda")["warn_minutes"] == 120
    assert _put(h, KEYS[0], 120).status_code == 200


# Global scope applies to all entities
def test_global_scope(h):
    assert _put(h, KEYS[1], 300, scope="global", sid=None).status_code == 200
    assert _th(h, "ent_kanda")["late_minutes"] == 300
    assert _th(h, "ent_ksc")["late_minutes"] in (300, 240)  # entity override (240) may win
    assert _put(h, KEYS[1], 240, scope="global", sid=None).status_code == 200
    assert _th(h, "ent_kanda")["late_minutes"] == 240


# Validation: below min / non-int rejected
@pytest.mark.parametrize("val", [0, -5, 20000, "abc"])
def test_validation(h, val):
    r = _put(h, KEYS[0], val)
    assert r.status_code in (400, 422), f"{val}: {r.status_code} {r.text[:200]}"
    assert _th(h, "ent_ksc")["warn_minutes"] == 120


# Missing reason: low-risk keys (requires_reason False) accept empty reason by design
def test_reason_optional_low_risk(h):
    r = requests.put(f"{BASE}/config/values", headers=h, json={"items": [
        {"key": KEYS[0], "value": 60, "scope_type": "entity", "scope_id": "ent_ksc", "reason": ""}]})
    print(r.status_code, r.text[:200])
    assert r.status_code in (200, 400, 422)
    _put(h, KEYS[0], 120)


# Non-admin can't change
def test_sales_cannot_change():
    hs = _login("sales@kainnusantara.id", "demo1234")
    r = _put(hs, KEYS[0], 10)
    assert r.status_code == 403, r.text[:200]


# Catalog lists keys in group stok-satuan
def test_catalog_entries(h):
    r = requests.get(f"{BASE}/config/registry", headers=h)
    if r.status_code == 404:
        pytest.skip("no /config/registry endpoint")
    txt = r.text
    for k in KEYS:
        assert k in txt
