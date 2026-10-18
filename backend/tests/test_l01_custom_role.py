"""L01 LN-010/LN-015 — custom role: aktivitas diizinkan/ditolak sama di API, menu/tab per peran,
tidak bisa mengubah hak peran sendiri, ganti nama peran tidak mengubah izin efektif."""
import uuid

import pytest
import requests

from tests.test_p05_acceptance_acc31_33_34 import BASE, DB, _login


@pytest.fixture(scope="module")
def adm():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def role_and_user(adm):
    label = f"TEST_L01 PIC Proofing {uuid.uuid4().hex[:4]}"
    perms = {"rnd": ["view"], "product": ["view"]}
    r = requests.post(f"{BASE}/api/access/roles", json={"label": label, "permissions": perms}, headers=adm, timeout=30)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    email = f"test_l01_{uuid.uuid4().hex[:6]}@kainnusantara.id"
    import bcrypt
    from datetime import datetime, timezone
    admin = DB.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0})
    DB.users.insert_one({"id": f"user_{uuid.uuid4().hex[:12]}", "email": email, "name": "TEST_L01 PIC",
                         "role": rid, "status": "active", "home_entity_id": admin.get("home_entity_id"),
                         "entity_ids": admin.get("entity_ids") or [admin.get("home_entity_id")],
                         "password_hash": bcrypt.hashpw(b"demo1234", bcrypt.gensalt()).decode(),
                         "created_at": datetime.now(timezone.utc).isoformat()})
    yield rid, email
    DB.users.delete_many({"email": email})
    requests.delete(f"{BASE}/api/access/roles/{rid}", headers=adm, timeout=30)


def test_effective_permission_same_on_api(role_and_user):
    rid, email = role_and_user
    h = _login(email, "demo1234")
    assert requests.get(f"{BASE}/api/products?limit=1", headers=h, timeout=30).status_code == 200
    assert requests.get(f"{BASE}/api/sales-orders?limit=1", headers=h, timeout=30).status_code == 403
    assert requests.get(f"{BASE}/api/master-data/export-products", headers=h, timeout=30).status_code == 403
    me = requests.get(f"{BASE}/api/auth/me", headers=h, timeout=30).json()
    assert me["permissions"] == {"rnd": ["view"], "product": ["view"]}
    assert "view_resources" in me and "sales-orders" in me["view_resources"]
    # custom role tanpa field_visibility → grade/LOT/asal tersembunyi
    keys = set(requests.get(f"{BASE}/api/products?limit=20", headers=h, timeout=30).json()[0].keys()) \
        if isinstance(requests.get(f"{BASE}/api/products?limit=20", headers=h, timeout=30).json(), list) else set()
    assert "grade" not in keys


def test_hidden_tabs_roundtrip_and_rename_keeps_perms(adm, role_and_user):
    rid, email = role_and_user
    r = requests.patch(f"{BASE}/api/access/roles/{rid}", json={"hidden_views": ["rnd-labdip", "rnd-handfeel"]},
                       headers=adm, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["hidden_views"] == ["rnd-handfeel", "rnd-labdip"]
    assert requests.patch(f"{BASE}/api/access/roles/{rid}", json={"hidden_views": ["tidak-ada"]},
                          headers=adm, timeout=30).status_code == 400
    me = requests.get(f"{BASE}/api/auth/me", headers=_login(email, "demo1234"), timeout=30).json()
    assert set(me["hidden_views"]) == {"rnd-labdip", "rnd-handfeel"}
    r = requests.patch(f"{BASE}/api/access/roles/{rid}", json={"label": f"TEST_L01 Ganti {uuid.uuid4().hex[:4]}"},
                       headers=adm, timeout=30)
    assert r.status_code == 200 and r.json()["permissions"] == {"rnd": ["view"], "product": ["view"]}


def test_cannot_edit_own_role(adm):
    mgr = _login("manager@kainnusantara.id", "demo1234")
    m = DB.permission_settings.find_one({"id": "default"})["matrix"]
    had = "permission" in m["manager"]
    before = list(m["manager"].get("permission", []))
    DB.permission_settings.update_one({"id": "default"}, {"$set": {"matrix.manager.permission": ["view", "update"]}})
    try:
        r = requests.patch(f"{BASE}/api/access/roles/manager", json={"permissions": {"order": ["view"]}},
                           headers=mgr, timeout=30)
        assert r.status_code == 403, r.text
    finally:
        if had:
            DB.permission_settings.update_one({"id": "default"}, {"$set": {"matrix.manager.permission": before}})
        else:
            DB.permission_settings.update_one({"id": "default"}, {"$unset": {"matrix.manager.permission": ""}})
