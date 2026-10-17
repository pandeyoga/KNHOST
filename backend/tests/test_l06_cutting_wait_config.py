"""L06 — batas tunggu Meja Cutting (kuning/merah) dapat diatur per entitas lewat Pusat Pengaturan."""
import os

import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"


def _h():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _set(h, key, value, scope="ent_ksc"):
    r = requests.put(f"{BASE}/config/values", headers=h, json={"items": [
        {"key": key, "value": value, "scope_type": "entity", "scope_id": scope, "reason": "uji batas tunggu"}]})
    assert r.status_code == 200, r.text


def _th(h, ent):
    return requests.get(f"{BASE}/cutting/desk", headers=h, params={"entity_id": ent}).json()["wait_thresholds"]


def test_thresholds_per_entity_and_late_not_below_warn():
    h = _h()
    try:
        _set(h, "cutting.wait_warn_minutes", 30)
        _set(h, "cutting.wait_late_minutes", 20)
        assert _th(h, "ent_ksc") == {"warn_minutes": 30, "late_minutes": 30}
        assert _th(h, "ent_kanda") == {"warn_minutes": 120, "late_minutes": 240}
    finally:
        _set(h, "cutting.wait_warn_minutes", 120)
        _set(h, "cutting.wait_late_minutes", 240)
    assert _th(h, "ent_ksc") == {"warn_minutes": 120, "late_minutes": 240}
