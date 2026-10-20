"""Keputusan owner 2026-10-21 (#6) — aturan peran di backend mengenali PERAN ACUAN peran kustom (role_in).

Peran kustom & akun uji dibuat lewat API resmi lalu dihapus. Sebelum penyelarasan, peran kustom turunan
Sales lolos dari pagar "hanya data miliknya" (melihat semua pelanggan/pesanan), ditolak Tanya KN, dan
turunan Manager mendapat 404 di Meja Saya.
Jalankan: cd /app/backend && python -m pytest tests/test_role_in_alignment.py -p no:randomly -n 0 -q
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
PW = "Uji-Role-12345"
MADE = {"roles": [], "users": []}


def _login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id", "demo12345")


def _actor(admin, label, base, levels):
    r = requests.post(f"{BASE}/access/roles", json={"label": f"{label} {TAG}", "base_role": base, "levels": levels}, headers=admin)
    assert r.status_code in (200, 201), r.text
    rid = r.json()["id"]
    MADE["roles"].append(rid)
    email = f"uji.rolein.{len(MADE['users'])}.{TAG}@kainnusantara.id"
    u = requests.post(f"{BASE}/users", json={"name": f"Uji {label} {TAG}", "email": email, "role": rid, "password": PW,
                                             "home_entity_id": ENT, "allowed_entity_ids": [ENT]}, headers=admin)
    assert u.status_code in (200, 201), u.text
    MADE["users"].append(u.json().get("id") or DB.users.find_one({"email": email}, {"id": 1})["id"])
    return _login(email, PW)


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    DB.users.delete_many({"id": {"$in": MADE["users"]}})
    DB.sessions.delete_many({"user_id": {"$in": MADE["users"]}})
    adm = _login("admin@kainnusantara.id", "demo12345")
    for rid in MADE["roles"]:
        requests.delete(f"{BASE}/access/roles/{rid}", headers=adm)


def _items(r):
    body = r.json()
    return body if isinstance(body, list) else body.get("items", [])


def test_turunan_sales_kena_pagar_data_milik_sendiri(admin):
    assert len(_items(requests.get(f"{BASE}/sales-orders", headers=admin))) > 0           # data acuan ada pesanan
    h = _actor(admin, "UJI Sales Senior", "sales", {"penjualan": "manage", "customer": "manage"})
    r = requests.get(f"{BASE}/sales-orders", headers=h)
    assert r.status_code == 200, r.text
    assert _items(r) == [], "turunan Sales hanya melihat pesanan miliknya (akun baru = tidak ada)"
    c = requests.get(f"{BASE}/customers", headers=h)
    assert c.status_code == 200 and _items(c) == [], "turunan Sales hanya melihat pelanggan miliknya"


def test_turunan_sales_boleh_tanya_kn(admin):
    h = _actor(admin, "UJI Sales Tanya", "sales", {"penjualan": "view"})
    assert requests.get(f"{BASE}/ai/catalog", headers=h).status_code == 200


def test_turunan_manager_mendapat_meja_manager(admin):
    h = _actor(admin, "UJI Manager Area", "manager", {"penjualan": "view"})
    r = requests.get(f"{BASE}/desks/me", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "manager"
