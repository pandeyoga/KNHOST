"""PR-T2 — di MongoDB ASLI (lingkungan A, data acuan): gerbang nama peran sudah menjadi izin.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); akun & sesi peran uji disisipkan langsung ke
database uji lokal (`MONGO_URL`/`DB_NAME`) dan dihapus lagi. Tidak untuk database berisi data nyata.
Padanan `docs/audit/konfigurasi-peran-2026-11-13/bukti/t3_escalation.py` baris (e1)/(e2): peran kustom beracuan Manajer
dengan semua modul "Tidak ada" kini 403 di HPP dan beranda Manajer; peran yang ada tidak kehilangan akses.
"""
import datetime
import os
import uuid

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
ID = "prt2:gerbang-peran"


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _sesi_peran(rid):
    """Akun + sesi sisipan untuk peran `rid` (dibersihkan oleh pemanggil lewat `_bersihkan`)."""
    uid = f"usr_bp_prt2_{uuid.uuid4().hex[:8]}"
    now = datetime.datetime.now(datetime.timezone.utc)
    DB.users.insert_one({"id": uid, "name": f"Uji PR-T2 {rid}", "email": f"{uid}@uji.id", "role": rid,
                         "status": "active", "home_entity_id": "ent_ksc", "allowed_entity_ids": ["ent_ksc"],
                         "created_at": now.isoformat()})
    tok = "tok_bp_prt2_" + uuid.uuid4().hex
    DB.sessions.insert_one({"token": tok, "user_id": uid, "created_at": now,
                            "expires_at": now + datetime.timedelta(hours=2)})
    return uid, {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}


def _bersihkan(uid):
    DB.sessions.delete_many({"user_id": uid})
    DB.users.delete_one({"id": uid})


def test_migrasi_tercatat_sekali():
    rec = DB.permission_settings.find_one({"id": "default"})
    assert rec["migrations_applied"].count(ID) == 1
    assert DB.audit_logs.count_documents({"action": "role_gates_migrated"}) == 1
    for res in ("costing", "manager_home", "sales_force", "system_tools", "ai"):
        assert rec["matrix"]["manager"].get(res), res


def test_e1_e2_manajer_kosong_403_manajer_200():
    adm = _login()
    mods = requests.get(f"{BASE}/access/modules", headers=adm, timeout=30).json()["modules"]
    r = requests.post(f"{BASE}/access/roles", headers=adm, timeout=30, json={
        "label": f"Manajer Kosong BP {uuid.uuid4().hex[:4]}", "base_role": "manager", "description": "uji PR-T2",
        "levels": {m["id"]: "none" for m in mods}})
    assert r.status_code == 200, r.text
    rid = (r.json().get("role") or r.json())["id"]
    uid, h = _sesi_peran(rid)
    try:
        for jalur in ("/costing/wac", "/home/manager", "/sales/leaderboard", "/incentive-rates", "/ai/usage",
                      "/data-hygiene/summary"):
            assert requests.get(f"{BASE}{jalur}", headers=h, timeout=60).status_code == 403, jalur
        mgr = _login("manager@kainnusantara.id")
        for jalur in ("/costing/wac", "/home/manager", "/sales/leaderboard", "/incentive-rates", "/ai/usage"):
            assert requests.get(f"{BASE}{jalur}", headers=mgr, timeout=60).status_code == 200, jalur
        assert requests.get(f"{BASE}/saga-locks", headers=mgr, timeout=60).status_code == 403
    finally:
        _bersihkan(uid)
        requests.delete(f"{BASE}/access/roles/{rid}", headers=adm, timeout=30)


def test_peran_kustom_lama_tidak_kehilangan_akses():
    """Peran kustom data acuan beracuan Manajer (mis. Wakil Manajer) tetap membuka beranda Manajer & HPP."""
    customs = list(DB.custom_roles.find({"base_role": "manager"}, {"_id": 0, "id": 1, "created_at": 1}))
    rec = DB.permission_settings.find_one({"id": "default"})
    lama = [c for c in customs if (rec["matrix"].get(c["id"]) or {}).get("manager_home")]
    if not lama:
        pytest.skip("data acuan tanpa peran kustom beracuan Manajer yang ada sebelum PR-T2")
    uid, h = _sesi_peran(lama[0]["id"])
    try:
        assert requests.get(f"{BASE}/home/manager", headers=h, timeout=60).status_code == 200
        assert requests.get(f"{BASE}/costing/wac", headers=h, timeout=60).status_code == 200
    finally:
        _bersihkan(uid)


def test_tanpa_acuan_berizin_hpp_200():
    adm = _login()
    r = requests.post(f"{BASE}/access/roles", headers=adm, timeout=30, json={
        "label": f"Tanpa Acuan BP {uuid.uuid4().hex[:4]}", "base_role": "", "description": "uji PR-T2",
        "permissions": {"costing": ["view"], "rnd": ["view", "manage_org"]}})
    assert r.status_code == 200, r.text
    rid = (r.json().get("role") or r.json())["id"]
    uid, h = _sesi_peran(rid)
    try:
        assert requests.get(f"{BASE}/costing/wac", headers=h, timeout=60).status_code == 200
        assert requests.get(f"{BASE}/rnd/divisions", headers=h, timeout=60).status_code == 200
        assert requests.get(f"{BASE}/home/manager", headers=h, timeout=60).status_code == 403
    finally:
        _bersihkan(uid)
        requests.delete(f"{BASE}/access/roles/{rid}", headers=adm, timeout=30)
