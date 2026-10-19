"""Tests for GET /api/sales/my-rank and /api/sales/leaderboard (iteration 238)."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")


def _login(email: str, password: str = "demo1234") -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def sales_sess():
    return _login("sales@kainnusantara.id")


@pytest.fixture(scope="module")
def sales_kanda_sess():
    return _login("sales.kanda@kainnusantara.id")


@pytest.fixture(scope="module")
def manager_sess():
    return _login("manager@kainnusantara.id")


def test_my_rank_sales_ok(sales_sess):
    r = sales_sess.get(f"{BASE_URL}/api/sales/my-rank", params={"period": "2026-01"}, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ("period", "rank", "total", "total_sales"):
        assert k in data
    assert isinstance(data["total"], int)
    assert isinstance(data["total_sales"], (int, float))


def test_my_rank_sales_kanda_ok(sales_kanda_sess):
    r = sales_kanda_sess.get(f"{BASE_URL}/api/sales/my-rank", params={"period": "2026-01"}, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "rank" in data and "total_sales" in data


def test_my_rank_ignores_other_sales_id(sales_sess, sales_kanda_sess):
    """sales_id param must be ignored for sales role (scope guard)."""
    # fetch own
    own = sales_sess.get(f"{BASE_URL}/api/sales/my-rank", params={"period": "2026-01"}, timeout=20).json()
    # try to spoof another sales id
    spoof = sales_sess.get(f"{BASE_URL}/api/sales/my-rank",
                            params={"period": "2026-01", "sales_id": "someone_else"}, timeout=20)
    assert spoof.status_code == 200
    assert spoof.json().get("total_sales") == own.get("total_sales")


def test_leaderboard_forbidden_for_sales(sales_sess):
    r = sales_sess.get(f"{BASE_URL}/api/sales/leaderboard", params={"period": "2026-01"}, timeout=20)
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"


def test_leaderboard_ok_for_manager(manager_sess):
    r = manager_sess.get(f"{BASE_URL}/api/sales/leaderboard", params={"period": "2026-01"}, timeout=20)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)
