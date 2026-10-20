"""FE-04 / FE-05 (review 2026-10-20) — aksi mengikuti izin efektif & scope sah, server tetap penegak.

Peran kustom & akun uji dibuat lewat API resmi lalu dihapus. Butuh data acuan
(`bash scripts/dev_restore_demo.sh`).
Jalankan: cd /app/backend && python -m pytest tests/test_fe04_fe05_access.py -p no:randomly -n 0 -q
"""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
TAG = uuid.uuid4().hex[:6]
PW = "Uji-FE04-12345"
CREATED = {"roles": [], "users": []}


def _login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id", "demo12345")


def _role(admin, label, levels, base=""):
    r = requests.post(f"{BASE}/access/roles", json={"label": f"{label} {TAG}", "base_role": base, "levels": levels}, headers=admin)
    assert r.status_code in (200, 201), r.text
    rid = r.json()["id"]
    CREATED["roles"].append(rid)
    return rid


def _user(admin, role, ents=(ENT,)):
    email = f"uji.{role}.{len(CREATED['users'])}.{TAG}@kainnusantara.id".lower()
    r = requests.post(f"{BASE}/users", json={"name": f"Uji {role} {TAG}", "email": email, "role": role, "password": PW,
                                             "home_entity_id": ents[0], "allowed_entity_ids": list(ents)}, headers=admin)
    assert r.status_code in (200, 201), r.text
    uid = r.json().get("id") or DB.users.find_one({"email": email}, {"id": 1})["id"]
    CREATED["users"].append(uid)
    return uid, email


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    DB.users.delete_many({"id": {"$in": CREATED["users"]}})
    DB.sessions.delete_many({"user_id": {"$in": CREATED["users"]}})
    adm = _login("admin@kainnusantara.id", "demo12345")
    for rid in CREATED["roles"]:
        requests.delete(f"{BASE}/access/roles/{rid}", headers=adm)


# ─── Petugas inspeksi: kemampuan + scope, termasuk peran kustom ────────────────
def test_petugas_inspeksi_ikut_kemampuan_dan_scope(admin):
    qc_role = _role(admin, "UJI QC", {"qc": "manage", "warehouse_ops": "view"})
    qc_uid, _ = _user(admin, qc_role)
    other_uid, _ = _user(admin, qc_role, ents=("ent_kanda",))          # berkemampuan, tapi bukan di KSC
    meta = requests.get(f"{BASE}/inspections/meta", params={"entity_id": ENT}, headers=admin).json()
    ids = {o["value"] for o in meta["officers"]}
    assert qc_uid in ids, "peran kustom berizin qc.inspect wajib muncul sebagai petugas"
    assert other_uid not in ids, "akun tanpa penugasan di badan usaha ini tidak boleh muncul"
    fin = DB.users.find_one({"role": "finance", "status": "active"}, {"id": 1})["id"]
    assert fin not in ids, "Finance tidak punya kemampuan inspect"


def test_penugasan_petugas_tak_berwenang_ditolak_server(admin):
    ins = DB.inspections.find_one({"status": {"$in": ["draft", "assigned", "open", "new"]}}, {"id": 1, "entity_id": 1})
    if not ins:
        pytest.skip("data acuan tidak punya SPK inspeksi terbuka")
    fin = DB.users.find_one({"role": "finance", "status": "active"}, {"id": 1})["id"]
    h = {**admin, "X-Entity-Id": ins.get("entity_id") or ENT}
    r = requests.post(f"{BASE}/inspections/{ins['id']}/assign", json={"assigned_to": fin}, headers=h)
    assert r.status_code == 400 and "tidak berwenang" in r.text, r.text


# ─── FE-05: Data Gudang memakai scope sah, scope=all tetap dijaga ───────────────
def test_admin_gudang_dapat_daftar_sesuai_scope_tanpa_scope_all():
    h = _login("whadmin@kainnusantara.id", "demo1234")
    r = requests.get(f"{BASE}/warehouses", headers=h)
    assert r.status_code == 200 and len(r.json()) > 0
    assert requests.get(f"{BASE}/warehouses", params={"scope": "all"}, headers=h).status_code == 403   # manipulasi tetap ditolak


def test_turunan_manager_boleh_scope_all(admin):
    rid = _role(admin, "UJI Manager Gudang", {"warehouse_ops": "manage", "inventory": "manage"}, base="manager")
    _uid, email = _user(admin, rid)
    r = requests.get(f"{BASE}/warehouses", params={"scope": "all"}, headers=_login(email, PW))
    assert r.status_code == 200, r.text


# ─── Kunci harga OD: peran pengunci (peran acuan dikenali) + order.update ───────
def test_kunci_harga_peran_acuan_dikenali_dan_finance_ditolak(admin):
    rid = _role(admin, "UJI Sales Senior", {"penjualan": "manage"}, base="sales")
    _uid, email = _user(admin, rid)
    h = _login(email, PW)
    r = requests.post(f"{BASE}/special-orders/sord_tidak_ada/lock-price", json={"auto_po": False}, headers=h)
    assert r.status_code == 404, r.text          # lolos gerbang peran → baru 404 dokumen tidak ada
    hf = _login("finance@kainnusantara.id", "demo1234")
    r = requests.post(f"{BASE}/special-orders/sord_tidak_ada/lock-price", json={"auto_po": False}, headers=hf)
    assert r.status_code == 403, r.text


# ─── Izin efektif dikirim server (sumber tombol UI) & pencabutan tercermin ──────
def test_izin_efektif_dan_pencabutan(admin):
    rid = _role(admin, "UJI Receiving", {"warehouse_ops": "manage"})
    _uid, email = _user(admin, rid)
    h = _login(email, PW)
    perms = requests.get(f"{BASE}/auth/me", headers=h).json()["permissions"]
    assert "create" in perms.get("goods_receipt", []) and "approve" not in perms.get("transfer", [])
    r = requests.patch(f"{BASE}/access/roles/{rid}", json={"levels": {"warehouse_ops": "view"}}, headers=admin)
    assert r.status_code == 200, r.text
    perms = requests.get(f"{BASE}/auth/me", headers=h).json()["permissions"]
    assert perms.get("goods_receipt") == ["view"], perms.get("goods_receipt")
    body = {"partner_type": "supplier", "partner_id": "sup_x", "warehouse_id": "wh_x"}
    assert requests.post(f"{BASE}/goods-receipts", json=body, headers=h).status_code == 403   # server menolak
