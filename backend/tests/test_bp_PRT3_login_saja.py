"""PR-T3 — di MongoDB ASLI (lingkungan A, data acuan): endpoint yang dulu cukup dengan login kini berizin / tersaring.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); akun & sesi peran uji disisipkan langsung ke
database uji lokal (`MONGO_URL`/`DB_NAME`) dan dihapus lagi. Hanya membaca selain akun/sesi sisipan itu. Tidak untuk
database berisi data nyata. Padanan lapis B: `backend/tests_mem/test_PRT3_login_saja.py`, `test_PRT3_sapuan.py`.
"""
import datetime
import os
import uuid

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
KUNCI_S2 = {"id", "code", "name", "short_name", "legal_name", "type", "is_pkp", "currency", "status", "doc_prefix",
            "logo_url", "is_group", "write_locked", "city"}


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture
def sopir():
    uid = f"usr_bp_prt3_{uuid.uuid4().hex[:8]}"
    now = datetime.datetime.now(datetime.timezone.utc)
    DB.users.insert_one({"id": uid, "name": "Uji PR-T3 Sopir", "email": f"{uid}@uji.id", "role": "driver",
                         "status": "active", "home_entity_id": "ent_ksc", "allowed_entity_ids": ["ent_ksc"],
                         "created_at": now.isoformat()})
    tok = "tok_bp_prt3_" + uuid.uuid4().hex
    DB.sessions.insert_one({"token": tok, "user_id": uid, "created_at": now,
                            "expires_at": now + datetime.timedelta(hours=2)})
    try:
        yield {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}
    finally:
        DB.sessions.delete_many({"user_id": uid})
        DB.users.delete_one({"id": uid})


def test_sopir_ditolak_atau_tersaring(sopir):
    for jalur in ("/sales-targets", "/sales-incentives", "/sales-users", "/entities/ent_ksc",
                  "/entities/ent_ksc/readiness", "/entities/count", "/finance/period-unlocks",
                  "/purchase-orders/resolve-sourcing?product_id=x"):
        assert requests.get(f"{BASE}{jalur}", headers=sopir, timeout=60).status_code == 403, jalur
    r = requests.get(f"{BASE}/entities", headers=sopir, timeout=60)
    assert r.status_code == 200 and r.json()
    assert all(set(row) == KUNCI_S2 for row in r.json())
    d = requests.get(f"{BASE}/dashboard", headers=sopir, timeout=120).json()
    assert d["orders"] == [] and d["customers"] == [] and d["products"] == [] and d["warehouses"] == []
    assert d["metrics"]["active_orders"] == 0 and d["stock_scope"] == {}
    for jalur in ("/enums", "/wilayah/provinces", "/notifications", "/roles", "/payment-terms", "/auth/me",
                  "/finance/period-unlocks/active"):
        assert requests.get(f"{BASE}{jalur}", headers=sopir, timeout=60).status_code != 403, jalur


def test_manajer_tidak_kehilangan_isi():
    mgr = _login("manager@kainnusantara.id")
    d = requests.get(f"{BASE}/dashboard", headers=mgr, timeout=120).json()
    assert d["products"] and d["warehouses"] and d["metrics"]["available_by_unit"] is not None
    rows = requests.get(f"{BASE}/entities", headers=mgr, timeout=60).json()
    assert rows and all("user_count" in r for r in rows)
    for jalur in ("/sales-targets", "/sales-users", "/finance/period-unlocks", "/entities/ent_ksc"):
        assert requests.get(f"{BASE}{jalur}", headers=mgr, timeout=60).status_code == 200, jalur


def test_sales_hanya_target_miliknya():
    sls = _login("sales@kainnusantara.id")
    me = requests.get(f"{BASE}/auth/me", headers=sls, timeout=30).json()
    uid = (me.get("user") or me)["id"]
    r = requests.get(f"{BASE}/sales-targets", headers=sls, timeout=60)
    assert r.status_code == 200
    assert all(t.get("sales_id") == uid for t in r.json())
