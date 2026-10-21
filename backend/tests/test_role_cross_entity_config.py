"""Keputusan owner 2026-10-21 — akses lintas badan usaha DAPAT DIKONFIGURASI per peran (bawaan & kustom).

Dulu hanya Admin & Manager bawaan yang membuka semua badan usaha; peran kustom turunan Manager terkunci
pada badan usaha yang ditugaskan. Kini: pengaturan per peran di layar "Peran & Hak Akses"
(`PATCH /roles/{id}` `cross_entity`), bawaan peran kustom = peran acuannya, Admin dikunci selalu lintas PT.
Diuji lewat API dengan akun sementara (hash sandi disalin dari akun seed, dibuang di akhir).
Jalankan: cd /app/backend && python -m pytest tests/test_role_cross_entity_config.py -p no:randomly -n 0 -q
"""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
TAG = uuid.uuid4().hex[:6]
HOME = "ent_ksc"
ACTIVE = sorted(e["id"] for e in DB.business_entities.find({"status": "active"}, {"_id": 0, "id": 1}))
TEMP_USERS, TEMP_ROLES = [], []


def _login(email, pw="demo12345", entity=HOME):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": entity}


def _user(role):
    """Akun sementara peran `role`, ditugaskan HANYA ke KSC; sandi = hash akun seed finance@."""
    src = DB.users.find_one({"email": "finance@kainnusantara.id"}, {"_id": 0, "password_hash": 1})
    uid = f"user_TEST_CROSS_{TAG}_{len(TEMP_USERS)}"
    email = f"test.cross.{TAG}.{len(TEMP_USERS)}@kainnusantara.id"
    DB.users.insert_one({"id": uid, "name": f"Uji Lintas PT {len(TEMP_USERS)}", "email": email, "role": role,
                         "password_hash": src["password_hash"], "home_entity_id": HOME, "allowed_entity_ids": [HOME],
                         "status": "active", "must_change_password": False, "created_at": "2026-10-21T00:00:00"})
    TEMP_USERS.append(uid)
    return email


def _ctx(email, entity=HOME):
    r = requests.get(f"{BASE}/auth/me", headers=_login(email, entity=entity))
    assert r.status_code == 200, r.text
    return r.json()["entity_context"]


@pytest.fixture(scope="module")
def adm():
    h = _login("admin@kainnusantara.id")
    yield h
    DB.users.delete_many({"id": {"$in": TEMP_USERS}})
    for rid in TEMP_ROLES:
        requests.delete(f"{BASE}/access/roles/{rid}", headers=h)
    requests.patch(f"{BASE}/access/roles/finance", headers=h, json={"cross_entity": False})   # kembali ke bawaan


def test_peran_kustom_turunan_manager_ikut_lintas_pt_dan_bisa_dimatikan(adm):
    assert len(ACTIVE) > 1, "butuh >1 badan usaha aktif di data acuan"
    r = requests.post(f"{BASE}/access/roles", headers=adm, json={"label": f"TEST Manajer Cabang {TAG}", "base_role": "manager"})
    assert r.status_code == 200, r.text
    role = r.json()
    TEMP_ROLES.append(role["id"])
    assert role["cross_entity"] is True and role["cross_entity_default"] is True     # ikut peran acuan (Manager)
    email = _user(role["id"])
    ctx = _ctx(email)
    assert ctx["is_cross_entity"] is True and sorted(ctx["allowed_entity_ids"]) == ACTIVE
    other = next(e for e in ACTIVE if e != HOME)
    assert _ctx(email, entity=other)["active_entity_id"] == other                      # boleh pindah ke PT lain
    p = requests.patch(f"{BASE}/access/roles/{role['id']}", headers=adm, json={"cross_entity": False})
    assert p.status_code == 200 and p.json()["cross_entity"] is False and p.json()["cross_entity_overridden"] is True
    ctx = _ctx(email)
    assert ctx["is_cross_entity"] is False and ctx["allowed_entity_ids"] == [HOME]
    denied = requests.get(f"{BASE}/auth/me", headers=_login(email, entity=other))      # PT lain tidak lagi bisa dibuka
    assert denied.status_code == 403 and "tidak ditugaskan" in denied.text, denied.text[:200]


def test_peran_bawaan_lain_bisa_dinyalakan_admin_dikunci(adm):
    email = _user("finance")
    assert _ctx(email)["allowed_entity_ids"] == [HOME]                                 # bawaan Finance: tidak lintas PT
    p = requests.patch(f"{BASE}/access/roles/finance", headers=adm, json={"cross_entity": True})
    assert p.status_code == 200, p.text
    assert p.json()["cross_entity"] is True and p.json()["cross_entity_default"] is False
    assert sorted(_ctx(email)["allowed_entity_ids"]) == ACTIVE
    roles = {r["id"]: r for r in requests.get(f"{BASE}/access/roles", headers=adm).json()["roles"]}
    assert roles["finance"]["cross_entity"] is True and roles["manager"]["cross_entity"] is True
    back = requests.patch(f"{BASE}/access/roles/finance", headers=adm, json={"cross_entity": False})
    assert back.status_code == 200 and back.json()["cross_entity_overridden"] is False   # sama dengan bawaan → ikut bawaan
    assert _ctx(email)["allowed_entity_ids"] == [HOME]
    assert requests.patch(f"{BASE}/access/roles/admin", headers=adm, json={"cross_entity": False}).status_code == 403


def test_hanya_pemegang_izin_peran_yang_boleh_mengubah(adm):
    sales = _login("sales@kainnusantara.id")
    assert requests.patch(f"{BASE}/access/roles/finance", headers=sales, json={"cross_entity": True}).status_code == 403
    assert requests.get(f"{BASE}/access/roles", headers=adm).json()["roles"]
