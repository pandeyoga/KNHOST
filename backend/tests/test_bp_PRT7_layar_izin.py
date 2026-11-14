"""PR-T7 — di MongoDB ASLI (lingkungan A, data acuan): konteks izin sejak login, tautan karyawan, bendera tombol sample.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); peran uji dibuat lewat API, akun uji disisipkan
langsung ke database uji lokal (`MONGO_URL`/`DB_NAME`) dengan sandi data acuan, lalu dihapus lagi. Tidak untuk database
berisi data nyata. Padanan lapis B: `backend/tests_mem/test_PRT7_layar_izin.py`. Uji jalan layar U10–U15 (peramban,
`docs/audit/konfigurasi-peran-2026-11-13/bukti/ui_pengaturan_peran.js` dan `ui_sapuan_layar.js`) terpisah.

U3   login "Staf Penagihan Uji" membawa view_resources/hidden_views/permissions = /auth/me + daftar peran (memuat peran
     itu); `user.employee_id` = "" (akun tidak tertaut karyawan) dan /hr/employees/me memang 404.
U3b  akun seed yang tertaut karyawan hanya dari sisi HR (data acuan: `users.employee_id` kosong) → `employee_id` terisi.
U4   rincian sample membawa `caps`; untuk peran kustom tanpa acuan, `caps.pick_winner` = jawaban kebijakan server.
"""
import datetime
import os
import uuid

import bcrypt
import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
SANDI = "demo12345"


def _login(email="admin@kainnusantara.id", password=SANDI):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}


def _peran_penagihan(adm):
    r = requests.post(f"{BASE}/access/roles", headers=adm, timeout=30, json={
        "label": f"Staf Penagihan Uji BP {uuid.uuid4().hex[:4]}", "base_role": "", "description": "uji PR-T7",
        "levels": {"ar": "manage", "customer": "view", "approval": "view"}})
    assert r.status_code == 200, r.text
    return (r.json().get("role") or r.json())["id"]


def _akun(rid):
    uid = f"usr_bp_prt7_{uuid.uuid4().hex[:8]}"
    email = f"{uid}@uji.id"
    DB.users.insert_one({"id": uid, "name": f"Uji PR-T7 {rid}", "email": email, "role": rid, "status": "active",
                         "home_entity_id": "ent_ksc", "allowed_entity_ids": ["ent_ksc"],
                         "password_hash": bcrypt.hashpw(SANDI.encode(), bcrypt.gensalt()).decode(),
                         "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
    return uid, email


def _bersihkan(uid):
    DB.sessions.delete_many({"user_id": uid})
    DB.users.delete_one({"id": uid})
    DB.audit_logs.delete_many({"resource_id": uid, "action": "login"})


def test_PRT7_U3_login_konteks_izin_dan_daftar_peran():
    adm = _h(_login()["token"])
    rid = _peran_penagihan(adm)
    uid, email = _akun(rid)
    try:
        j = _login(email)
        me = requests.get(f"{BASE}/auth/me", headers=_h(j["token"]), timeout=30).json()
        assert j["view_resources"] == me["view_resources"] and j["view_resources"]
        assert j["hidden_views"] == me["hidden_views"]
        assert j["permissions"] == me["permissions"]
        roles = {x["id"]: x for x in j["roles"]}
        assert rid in roles and roles[rid]["custom"] is True and roles[rid]["base_role"] == ""
        assert j["user"]["employee_id"] == "" and me["employee_id"] == ""
        assert requests.get(f"{BASE}/hr/employees/me", headers=_h(j["token"]), timeout=30).status_code == 404
        # Endpoint kerangka yang dulu dipanggil di setiap layar memang di luar izin peran ini (layar kini tidak memanggil).
        assert requests.get(f"{BASE}/finance/posting-failures/count", headers=_h(j["token"]), timeout=30).status_code == 403
        assert requests.get(f"{BASE}/sales/keep-pending", headers=_h(j["token"]), timeout=30).status_code == 403
    finally:
        _bersihkan(uid)
        requests.delete(f"{BASE}/access/roles/{rid}", headers=adm, timeout=30)


def test_PRT7_U3b_employee_id_dari_tautan_hr():
    linked = DB.hr_employees.find_one({"user_id": {"$nin": ["", None]}}, {"_id": 0, "id": 1, "user_id": 1})
    if not linked:
        pytest.skip("data acuan tanpa karyawan tertaut akun")
    u = DB.users.find_one({"id": linked["user_id"], "status": "active"}, {"_id": 0, "email": 1})
    if not u:
        pytest.skip("akun tertaut tidak aktif")
    j = _login(u["email"])
    assert j["user"]["employee_id"] == linked["id"]
    assert requests.get(f"{BASE}/hr/employees/me", headers=_h(j["token"]), timeout=30).status_code == 200


def test_PRT7_U4_caps_rincian_sample():
    smp = DB.md_samples.find_one({"entity_id": "ent_ksc"}, {"_id": 0, "id": 1})
    if not smp:
        pytest.skip("data acuan tanpa permintaan sample di ent_ksc")
    adm = _h(_login()["token"])
    caps = requests.get(f"{BASE}/rnd/samples/{smp['id']}", headers=adm, timeout=30).json()["caps"]
    assert set(caps) == {"pick_winner", "approve_spec"}
    r = requests.post(f"{BASE}/access/roles", headers=adm, timeout=30, json={
        "label": f"TA Putus Sample BP {uuid.uuid4().hex[:4]}", "base_role": "", "description": "uji PR-T7",
        "permissions": {"rnd": ["view", "decide"]}})
    assert r.status_code == 200, r.text
    rid = (r.json().get("role") or r.json())["id"]
    uid, email = _akun(rid)
    try:
        j = _login(email)
        caps = requests.get(f"{BASE}/rnd/samples/{smp['id']}", headers=_h(j["token"]), timeout=30).json()["caps"]
        pol = requests.get(f"{BASE}/config/explain", headers=adm, timeout=30,
                           params={"key": "rnd.sample_decision_roles", "entity_id": "ent_ksc"}).json().get("value")
        allowed = pol if isinstance(pol, list) else [x.strip() for x in str(pol or "").split(",") if x.strip()]
        assert caps["pick_winner"] is (not allowed or rid in allowed)
    finally:
        _bersihkan(uid)
        requests.delete(f"{BASE}/access/roles/{rid}", headers=adm, timeout=30)
