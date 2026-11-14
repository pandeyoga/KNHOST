"""Iter274 — regresi ringan sesi ini.

Cakupan:
1. Auth admin/manager (login demo12345)
2. GET /api/approval-rules (daftar aturan)
3. PATCH /api/approval-rules/{id} — KP-T4: dimatikan (410), baris tidak berubah
4. GET /api/settings/effective — section 'ui' & 'role_home'
5. GET /api/price-approvals (manager) — >=1 pending (read-only)
"""
import os

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"
PWD = "demo12345"
ENT = "ent_ksc"


def _login(email):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": PWD}, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"login {email} -> {r.status_code}: {r.text[:300]}")
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"no token in login response: {r.text[:300]}"
    return tok


def _sess(email):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {_login(email)}", "X-Entity-Id": ENT,
                      "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin():
    return _sess("admin@kainnusantara.id")


@pytest.fixture(scope="module")
def manager():
    return _sess("manager@kainnusantara.id")


# --- Modul: approval-rules -------------------------------------------------
class TestApprovalRules:
    def test_list_rules(self, admin):
        r = admin.get(f"{API}/approval-rules")
        assert r.status_code == 200, r.text[:300]
        rules = r.json()
        assert isinstance(rules, list) and len(rules) > 0
        for k in ("id", "doc_type", "min_amount", "required_role"):
            assert k in rules[0], f"missing {k} in {rules[0]}"
        assert all("_id" not in x for x in rules)

    def test_patch_dimatikan_410(self, admin):
        """KP-T4 (disesuaikan): PATCH aturan lama dimatikan — aturan diubah di Aturan Persetujuan satu tabel."""
        rid = admin.get(f"{API}/approval-rules").json()[0]["id"]
        before = admin.get(f"{API}/approval-rules/{rid}").json()
        r = admin.patch(f"{API}/approval-rules/{rid}", json={"min_amount": 1})
        assert r.status_code == 410, r.text[:200]
        assert admin.get(f"{API}/approval-rules/{rid}").json()["min_amount"] == before["min_amount"]


# --- Modul: settings ------------------------------------------------------
class TestSettingsEffective:
    def test_ui_and_role_home_sections(self, admin):
        r = admin.get(f"{API}/settings/effective")
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        body = data.get("settings", data)
        assert "ui" in body, f"section 'ui' tidak ada. keys={list(body.keys())[:20]}"
        assert body["ui"].get("show_coming_soon") is True
        assert body["ui"].get("coming_soon_collapsed") is True
        assert "role_home" in body, f"section 'role_home' tidak ada. keys={list(body.keys())[:20]}"
        assert isinstance(body["role_home"], dict) and len(body["role_home"]) > 0


# --- Modul: price approvals (read-only) ----------------------------------
class TestPriceApprovals:
    def test_manager_list_has_pending(self, manager):
        r = manager.get(f"{API}/price-approvals")
        assert r.status_code == 200, r.text[:300]
        rows = r.json()
        assert isinstance(rows, list) and len(rows) > 0
        assert all("_id" not in x for x in rows)
        pending = [x for x in rows if x.get("status") == "pending"]
        assert len(pending) >= 1, f"tidak ada pending. statuses={{x.get('status') for x in rows}}"


# --- Modul: integritas data demo ----------------------------------------
class TestDemoDataIntact:
    @pytest.mark.parametrize("path,expected", [
        ("/makloon-orders", 5),
        ("/products", 20),
    ])
    def test_counts(self, admin, path, expected):
        r = admin.get(f"{API}{path}")
        assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"
        rows = r.json()
        rows = rows if isinstance(rows, list) else rows.get("items", rows.get("data", []))
        assert len(rows) == expected, f"{path} count {len(rows)} != {expected}"
