# Regression: Web Push endpoints, notifications for mobile sheet, permission editor single door (Badan Usaha & Akses)
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


def _login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed {email}: {r.status_code}")
    tok = r.json().get("token") or r.json().get("access_token")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def sales():
    return _login("sales@kainnusantara.id", "demo12345")


# --- Push ---
class TestPush:
    def test_public_key_requires_login(self):
        r = requests.get(f"{BASE_URL}/api/push/public-key", timeout=30)
        assert r.status_code in (401, 403)

    def test_public_key_non_empty(self, sales):
        r = sales.get(f"{BASE_URL}/api/push/public-key", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d["public_key"], str) and len(d["public_key"]) > 40
        assert d["enabled"] is True

    def test_status(self, sales):
        r = sales.get(f"{BASE_URL}/api/push/status", timeout=30)
        assert r.status_code == 200
        assert r.json()["enabled"] is True
        assert isinstance(r.json()["devices"], int)

    def test_subscribe_validation(self, sales):
        r = sales.post(f"{BASE_URL}/api/push/subscribe", json={"endpoint": "x"}, timeout=30)
        assert r.status_code == 422

    def test_subscribe_unsubscribe_roundtrip(self, sales):
        ep = "https://fcm.googleapis.com/fcm/send/TEST_iter_notif_endpoint_123"
        before = sales.get(f"{BASE_URL}/api/push/status", timeout=30).json()["devices"]
        r = sales.post(f"{BASE_URL}/api/push/subscribe", json={"endpoint": ep, "keys": {"p256dh": "TEST_p", "auth": "TEST_a"}, "device_label": "TEST"}, timeout=30)
        assert r.status_code == 200 and r.json()["ok"] is True
        assert sales.get(f"{BASE_URL}/api/push/status", timeout=30).json()["devices"] == before + 1
        r = sales.post(f"{BASE_URL}/api/push/unsubscribe", json={"endpoint": ep}, timeout=30)
        assert r.status_code == 200 and r.json()["removed"] == 1
        assert sales.get(f"{BASE_URL}/api/push/status", timeout=30).json()["devices"] == before

    def test_push_test_without_devices(self, admin):
        st = admin.get(f"{BASE_URL}/api/push/status", timeout=30).json()
        r = admin.post(f"{BASE_URL}/api/push/test", timeout=60)
        if st["devices"] == 0:
            assert r.status_code == 404
        else:
            assert r.status_code == 200


# --- Notifications used by mobile sheet ---
class TestNotifications:
    def test_list_notifications_sales(self, sales):
        r = sales.get(f"{BASE_URL}/api/notifications", timeout=30)
        assert r.status_code == 200
        d = r.json()
        items = d if isinstance(d, list) else (d.get("items") or d.get("notifications") or [])
        assert isinstance(items, list)
        for n in items[:5]:
            assert "id" in n and "_id" not in n


# --- Permission matrix single door ---
class TestPermissions:
    def test_me_has_permissions(self, sales):
        r = sales.get(f"{BASE_URL}/api/auth/me", timeout=30)
        if r.status_code == 404:
            r = sales.get(f"{BASE_URL}/api/me", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json().get("permissions"), dict)


# --- Role editor (single door) writes to the same effective permission matrix ---
class TestRoleEditorSave:
    def test_custom_role_patch_level_persists_and_matrix_updates(self, admin):
        r = admin.post(f"{BASE_URL}/api/access/roles", json={"label": "TEST_iter_notif_role", "base_role": "sales"}, timeout=30)
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        try:
            g = admin.get(f"{BASE_URL}/api/access/roles/{rid}", timeout=30).json()
            assert g["levels"]["supplier"]["level"] == "view"
            p = admin.patch(f"{BASE_URL}/api/access/roles/{rid}", json={"levels": {"supplier": "manage"}, "expected_version": g.get("version")}, timeout=30)
            assert p.status_code == 200, p.text
            g2 = admin.get(f"{BASE_URL}/api/access/roles/{rid}", timeout=30).json()
            assert g2["levels"]["supplier"]["level"] == "manage"
            perms = g2["permissions"].get("supplier", [])
            assert "create" in perms or "update" in perms
            m = admin.get(f"{BASE_URL}/api/permissions", timeout=30).json()["matrix"]
            assert rid in m, "custom role effective permissions should be in permission_settings.matrix"
            assert set(m[rid].get("supplier", [])) == set(perms)
        finally:
            d = admin.delete(f"{BASE_URL}/api/access/roles/{rid}", timeout=30)
            assert d.status_code == 200
            assert admin.get(f"{BASE_URL}/api/access/roles/{rid}", timeout=30).status_code == 404
