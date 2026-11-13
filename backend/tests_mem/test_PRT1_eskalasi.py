"""PR-T1 — tutup jalan menaikkan hak sendiri lewat kelola akun dan kelola peran (docs/blueprint/unit/PR-T1.md).

Persiapan bersama: peran kustom HR = tanpa peran acuan, tingkat `{"admin": "manage"}`; akun `hr` berperan HR;
akun `adm` = admin seed; akun `sls` berperan sales. `assignable_roles` kosong kecuali disebut.
Urutan uji penting (satu database per modul): U5 membuka daftar kelola HR untuk U5–U7; U12/U14/U16/U17 di akhir.
"""
from __future__ import annotations

import pytest

from access_modules import apply_levels

pytestmark = pytest.mark.anyio

ADMIN_EMAIL = "admin@kainnusantara.id"


@pytest.fixture(scope="module")
async def siap(klien, kepala_admin, akun, sesi, db):
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={
        "label": "HR Uji", "base_role": "", "levels": {"admin": "manage"}, "description": "peran uji PR-T1"})
    assert r.status_code == 200, r.text
    hr_role = r.json()["id"]
    hr = await akun(hr_role)
    sls = await akun("sales")
    adm = await db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 0})
    return {"hr_role": hr_role, "hr": hr, "hr_h": await sesi(hr), "sls": sls, "adm": adm,
            "adm_h": kepala_admin}


async def _jumlah_admin(db, aktif_saja: bool = False) -> int:
    q = {"role": "admin"}
    if aktif_saja:
        q["status"] = "active"
    return await db.users.count_documents(q)


def _detail(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


async def test_U01_hr_menjadikan_diri_admin_ditolak(klien, db, siap):
    r = await klien.patch(f"/api/users/{siap['hr']['id']}", headers=siap["hr_h"], json={"data": {"role": "admin"}})
    assert r.status_code == 403, r.text
    assert _detail(r) == "Peran Admin hanya bisa diberikan oleh Admin."
    assert (await db.users.find_one({"id": siap["hr"]["id"]}))["role"] == siap["hr_role"]


async def test_U02_hr_membuat_akun_admin_ditolak(klien, db, siap):
    sebelum = await _jumlah_admin(db)
    r = await klien.post("/api/users", headers=siap["hr_h"], json={
        "name": "Admin Gelap", "email": "admin.gelap@uji.id", "role": "admin", "password": "rahasia123",
        "home_entity_id": "ent_ksc", "allowed_entity_ids": ["ent_ksc"]})
    assert r.status_code == 403, r.text
    assert await _jumlah_admin(db) == sebelum
    assert not await db.users.find_one({"email": "admin.gelap@uji.id"})


async def test_U03_hr_mereset_sandi_admin_ditolak(klien, db, siap):
    sebelum = (await db.users.find_one({"id": siap["adm"]["id"]}))["password_hash"]
    sesi_sebelum = await db.sessions.count_documents({"user_id": siap["adm"]["id"]})
    assert sesi_sebelum >= 1
    r = await klien.post(f"/api/users/{siap['adm']['id']}/reset-password", headers=siap["hr_h"],
                         json={"new_password": "dibajak123"})
    assert r.status_code == 403, r.text
    assert (await db.users.find_one({"id": siap["adm"]["id"]}))["password_hash"] == sebelum
    assert await db.sessions.count_documents({"user_id": siap["adm"]["id"]}) == sesi_sebelum


async def test_U04_hr_membuat_akun_sales_ditolak_daftar_kosong(klien, db, siap):
    r = await klien.post("/api/users", headers=siap["hr_h"], json={
        "name": "Sales Satu", "email": "sales.satu@uji.id", "role": "sales", "password": "rahasia123",
        "home_entity_id": "ent_ksc", "allowed_entity_ids": ["ent_ksc"]})
    assert r.status_code == 403, r.text
    assert "belum diberi wewenang mengelola akun berperan" in _detail(r)
    assert not await db.users.find_one({"email": "sales.satu@uji.id"})


async def test_U05_daftar_kelola_dibuka_admin_lalu_hr_membuat_sales(klien, db, siap):
    r = await klien.patch(f"/api/access/roles/{siap['hr_role']}", headers=siap["adm_h"],
                          json={"assignable_roles": ["sales", "warehouse"]})
    assert r.status_code == 200, r.text
    assert r.json()["assignable_roles"] == ["sales", "warehouse"]
    assert len(r.json()["assignable_roles_labels"]) == 2
    r = await klien.post("/api/users", headers=siap["hr_h"], json={
        "name": "Sales Dua", "email": "sales.dua@uji.id", "role": "sales", "password": "rahasia123",
        "home_entity_id": "ent_ksc", "allowed_entity_ids": ["ent_ksc"]})
    assert r.status_code == 200, r.text
    assert (await db.users.find_one({"email": "sales.dua@uji.id"}))["role"] == "sales"


async def test_U05b_tanda_can_manage_di_daftar(klien, siap):
    """Tambahan (Layar §): `GET /api/users` dan `GET /api/access/roles` memuat `can_manage` per baris."""
    r = await klien.get("/api/users", headers=siap["hr_h"])
    assert r.status_code == 200, r.text
    baris = {u["id"]: u for u in r.json()}
    assert baris[siap["adm"]["id"]]["can_manage"] is False
    assert baris[siap["sls"]["id"]]["can_manage"] is True
    r = await klien.get("/api/access/roles", headers=siap["hr_h"])
    assert r.status_code == 200, r.text
    peran = {x["id"]: x for x in r.json()["roles"]}
    assert peran["manager"]["can_manage"] is False
    assert peran["admin"]["can_manage"] is False
    assert peran[siap["hr_role"]]["can_manage"] is False   # peran sendiri
    r = await klien.get("/api/access/roles", headers=siap["adm_h"])
    assert {x["id"]: x["can_manage"] for x in r.json()["roles"]}["manager"] is True


async def test_U06_hr_menaikkan_sales_ke_manajer_ditolak(klien, db, siap):
    r = await klien.patch(f"/api/users/{siap['sls']['id']}", headers=siap["hr_h"], json={"data": {"role": "manager"}})
    assert r.status_code == 403, r.text
    assert (await db.users.find_one({"id": siap["sls"]["id"]}))["role"] == "sales"


async def test_U07_hr_mereset_sandi_sales_boleh(klien, siap):
    r = await klien.post(f"/api/users/{siap['sls']['id']}/reset-password", headers=siap["hr_h"],
                         json={"new_password": "sandibaru123"})
    assert r.status_code == 200, r.text


async def test_U08_hr_mengubah_daftar_kelola_ditolak(klien, db, siap):
    r = await klien.patch(f"/api/access/roles/{siap['hr_role']}", headers=siap["hr_h"],
                          json={"assignable_roles": ["admin"]})
    assert r.status_code == 403, r.text
    rec = await db.permission_settings.find_one({"id": "default"})
    assert rec["assignable_roles"][siap["hr_role"]] == ["sales", "warehouse"]
    # Admin pun tidak bisa memasukkan `admin` ke daftar.
    r = await klien.patch(f"/api/access/roles/{siap['hr_role']}", headers=siap["adm_h"],
                          json={"assignable_roles": ["admin"]})
    assert r.status_code == 400, r.text


async def test_U09_hr_merakit_peran_dari_manajer_ditolak(klien, db, siap):
    r = await klien.post("/api/access/roles", headers=siap["hr_h"], json={"label": "X", "base_role": "manager"})
    assert r.status_code == 403, r.text
    assert "akses yang Anda sendiri tidak punya" in _detail(r)
    assert not await db.custom_roles.find_one({"id": "cr_x"})


async def test_U10_hr_mengubah_peran_manajer_ditolak(klien, db, siap):
    sebelum = (await db.permission_settings.find_one({"id": "default"}) or {}).get("matrix", {}).get("manager")
    r = await klien.patch("/api/access/roles/manager", headers=siap["hr_h"], json={"levels": {"accounting": "none"}})
    assert r.status_code == 403, r.text
    assert _detail(r).startswith("Peran Manajer memiliki akses lebih luas")
    sesudah = (await db.permission_settings.find_one({"id": "default"}) or {}).get("matrix", {}).get("manager")
    assert sesudah == sebelum


async def test_U11_hr_merakit_peran_sesuai_izinnya(klien, db, siap):
    hr = (await klien.get(f"/api/access/roles/{siap['hr_role']}", headers=siap["adm_h"])).json()["permissions"]
    hasil = apply_levels({}, {"hr": "view"})
    lebih = [(res, a) for res, acts in hasil.items() for a in acts if a not in (hr.get(res) or [])]
    r = await klien.post("/api/access/roles", headers=siap["hr_h"],
                         json={"label": "Y", "base_role": "", "levels": {"hr": "view"}})
    if lebih:
        assert r.status_code == 403, r.text
        assert not await db.custom_roles.find_one({"label": "Y"})
    else:
        assert r.status_code == 200, r.text
    # Arah sebaliknya (izin hasil ⊆ izin HR) harus lolos.
    r = await klien.post("/api/access/roles", headers=siap["hr_h"],
                         json={"label": "Y2", "base_role": "", "levels": {"admin": "view"}})
    assert r.status_code == 200, r.text


async def test_U13_hr_mengubah_peran_sendiri_tetap_ditolak(klien, siap):
    r = await klien.patch(f"/api/access/roles/{siap['hr_role']}", headers=siap["hr_h"],
                          json={"levels": {"hr": "manage"}})
    assert r.status_code == 403, r.text
    assert _detail(r).startswith("Anda tidak bisa mengubah hak akses peran Anda sendiri")


async def test_U12_admin_tidak_terpengaruh(klien, db, akun, siap):
    h = siap["adm_h"]
    # U1 — Admin menjadikan akun lain Admin, lalu dikembalikan.
    korban = await akun("sales")
    r = await klien.patch(f"/api/users/{korban['id']}", headers=h, json={"data": {"role": "admin"}})
    assert r.status_code == 200, r.text
    r = await klien.patch(f"/api/users/{korban['id']}", headers=h, json={"data": {"role": "sales"}})
    assert r.status_code == 200, r.text
    # U2 — Admin membuat akun Admin.
    r = await klien.post("/api/users", headers=h, json={
        "name": "Admin Kedua", "email": "admin.kedua@uji.id", "role": "admin", "password": "rahasia123",
        "home_entity_id": "ent_ksc", "allowed_entity_ids": ["ent_ksc"]})
    assert r.status_code == 200, r.text
    adm2 = r.json()["id"]
    # U3 — Admin mereset sandi Admin (akun kedua, supaya sesi kepala admin tetap ada).
    r = await klien.post(f"/api/users/{adm2}/reset-password", headers=h, json={"new_password": "sandibaru123"})
    assert r.status_code == 200, r.text
    r = await klien.delete(f"/api/users/{adm2}", headers=h)   # kembalikan: hanya satu admin aktif
    assert r.status_code == 200, r.text
    # U9 — Admin merakit peran dari Manajer.
    r = await klien.post("/api/access/roles", headers=h, json={"label": "X Admin", "base_role": "manager"})
    assert r.status_code == 200, r.text
    # U10 — Admin mengubah peran Manajer, lalu dikembalikan ke bawaan.
    r = await klien.patch("/api/access/roles/manager", headers=h, json={"levels": {"accounting": "none"}})
    assert r.status_code == 200, r.text
    r = await klien.post("/api/access/roles/manager/reset", headers=h)
    assert r.status_code == 200, r.text


async def test_U14_penjaga_admin_terakhir_tetap(klien, db, siap):
    r = await klien.delete(f"/api/users/{siap['sls']['id']}", headers=siap["adm_h"])
    assert r.status_code == 200, r.text
    assert await _jumlah_admin(db, aktif_saja=True) == 1
    r = await klien.delete(f"/api/users/{siap['adm']['id']}", headers=siap["adm_h"])
    assert r.status_code in (400, 409), r.text
    assert (await db.users.find_one({"id": siap["adm"]["id"]}))["status"] == "active"


async def test_U16_akun_admin_tidak_bisa_dipindah_massal(klien, db, siap):
    sebelum = await _jumlah_admin(db, aktif_saja=True)
    r = await klien.post("/api/access/roles/admin/move-users", headers=siap["adm_h"], json={"to_role": "sales"})
    assert r.status_code == 400, r.text
    assert _detail(r) == "Akun Admin tidak bisa dipindahkan massal. Ubah satu per satu di Akun & Akses."
    assert await _jumlah_admin(db, aktif_saja=True) == sebelum


async def test_U17_pindah_massal_mencabut_sesi(klien, db, akun, sesi, siap):
    a = await akun("warehouse")
    b = await akun("warehouse")
    await sesi(a)
    await sesi(b)
    assert await db.sessions.count_documents({"user_id": {"$in": [a["id"], b["id"]]}}) == 2
    r = await klien.post("/api/access/roles/warehouse/move-users", headers=siap["adm_h"], json={"to_role": "sales"})
    assert r.status_code == 200, r.text
    for u in (a, b):
        assert (await db.users.find_one({"id": u["id"]}))["role"] == "sales"
    assert await db.sessions.count_documents({"user_id": {"$in": [a["id"], b["id"]]}}) == 0
