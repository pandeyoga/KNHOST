"""Iteration 124: AUTH-05 permission matrix optimistic concurrency + GN-15 settings resolver smoke."""
import os
import copy
import threading
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ENTITY = "ent_ksc"
ADMIN_EMAIL = "admin@kainnusantara.id"
ADMIN_PASSWORD = "demo12345"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "X-Entity-Id": ENTITY})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s


@pytest.fixture(scope="module")
def original_matrix(admin_session):
    """Fetch original matrix, yield (matrix, initial_version); restore at end."""
    r = admin_session.get(f"{BASE_URL}/api/permissions")
    assert r.status_code == 200
    data = r.json()
    original = copy.deepcopy(data["matrix"])
    initial_version = int(data["version"])
    yield original, initial_version
    # Restore
    cur = admin_session.get(f"{BASE_URL}/api/permissions").json()
    restore = admin_session.put(
        f"{BASE_URL}/api/permissions",
        json={"matrix": original, "version": int(cur["version"])},
    )
    assert restore.status_code == 200, f"restore failed: {restore.text}"


# --- AUTH-05 tests ---

def test_get_permissions_shape(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/permissions")
    assert r.status_code == 200
    data = r.json()
    assert "matrix" in data and isinstance(data["matrix"], dict)
    assert "version" in data and isinstance(data["version"], int)


def test_put_without_version_returns_400(admin_session, original_matrix):
    matrix, _ = original_matrix
    r = admin_session.put(f"{BASE_URL}/api/permissions", json={"matrix": matrix})
    assert r.status_code == 400, r.text


def test_put_with_current_version_increments(admin_session, original_matrix):
    matrix, _ = original_matrix
    cur = admin_session.get(f"{BASE_URL}/api/permissions").json()
    v = int(cur["version"])
    r = admin_session.put(f"{BASE_URL}/api/permissions",
                          json={"matrix": matrix, "version": v})
    assert r.status_code == 200, r.text
    assert r.json()["version"] == v + 1
    # GET verifies persistence
    cur2 = admin_session.get(f"{BASE_URL}/api/permissions").json()
    assert int(cur2["version"]) == v + 1


def test_put_with_stale_version_returns_409(admin_session, original_matrix):
    matrix, _ = original_matrix
    cur = admin_session.get(f"{BASE_URL}/api/permissions").json()
    stale = int(cur["version"]) - 1
    if stale < 0:
        pytest.skip("version too low for stale test")
    r = admin_session.put(f"{BASE_URL}/api/permissions",
                          json={"matrix": matrix, "version": stale})
    assert r.status_code == 409, r.text
    detail = r.json().get("detail", "")
    assert "sudah diubah" in detail.lower() or "matriks" in detail.lower(), detail


def test_concurrent_puts_only_one_succeeds(admin_session, original_matrix):
    matrix, _ = original_matrix
    cur = admin_session.get(f"{BASE_URL}/api/permissions").json()
    v = int(cur["version"])
    results = []

    def do_put():
        s = requests.Session()
        s.headers.update(admin_session.headers)
        resp = s.put(f"{BASE_URL}/api/permissions",
                     json={"matrix": matrix, "version": v})
        results.append(resp.status_code)

    threads = [threading.Thread(target=do_put) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [200, 409], f"got {results}"


# --- GN-15 settings resolver smoke ---

@pytest.mark.parametrize("path", [
    "/api/lots/settings",
    "/api/uom-conversions/settings",
    "/api/receiving/uom-settings",
    "/api/supplier-contracts/policy",
])
def test_gn15_settings_endpoints_ok(admin_session, path):
    r = admin_session.get(f"{BASE_URL}{path}")
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
    assert isinstance(r.json(), dict)


def test_tanya_kn_analytics_smoke(admin_session):
    # analytics catalog endpoint
    for p in ["/api/analytics/catalog", "/api/tanya-kn/catalog"]:
        r = admin_session.get(f"{BASE_URL}{p}")
        if r.status_code == 404:
            continue
        assert r.status_code in (200, 403), f"{p} -> {r.status_code} {r.text[:200]}"
        return
    pytest.skip("no analytics catalog endpoint found")
