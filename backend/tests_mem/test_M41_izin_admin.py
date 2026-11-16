"""M41 (masukan pemilik 16 Nov) — "Saya admin tapi tidak punya akses" ke Pusat Export.

Akar: garis dasar pertama `permission_settings.defaults_applied` dulu dibuat dari SELURUH izin bawaan kode, bukan dari
matriks tersimpan. Instalasi lama yang melompat ke versi bergaris dasar sekaligus menerima modul baru (`data_export`)
menandai modul itu "sudah diterapkan" tanpa pernah memasukkannya ke matriks → Admin (dan peran lain) ditolak 403.

U1 tiruan instalasi lama (matriks tanpa `data_export`, tanpa garis dasar) → sesudah start, semua peran bawaan yang
   seharusnya memegang `data_export` memegangnya dan Admin bisa membuka Pusat Export.
U2 garis dasar sudah rusak (modul ditandai diterapkan, tidak ada di matriks) → Admin (terkunci) dipulihkan tiap start;
   peran lain tidak disentuh (bisa jadi dicabut Admin) — dilaporkan skrip diagnosa.
U3 start biasa tanpa yang hilang tidak menulis apa pun.
"""
from __future__ import annotations

import pytest

import bootstrap
from permissions_config import DEFAULT_PERMISSIONS

pytestmark = pytest.mark.anyio


async def _cabut_data_export(db, *, garis_dasar: str) -> None:
    rec = await db.permission_settings.find_one({"id": "default"}, {"_id": 0})
    matrix = rec["matrix"]
    for perms in matrix.values():
        if isinstance(perms, dict):
            perms.pop("data_export", None)
    upd = {"$set": {"matrix": matrix}}
    if garis_dasar == "kosong":
        upd["$unset"] = {"defaults_applied": ""}
    await db.permission_settings.update_one({"id": "default"}, upd)


async def test_U1_instalasi_lama_tanpa_garis_dasar(klien, kepala_admin, db):
    await _cabut_data_export(db, garis_dasar="kosong")
    r = await klien.get("/api/export-center/datasets", headers=kepala_admin)
    assert r.status_code == 403   # keadaan di lapangan (foto 34)
    await bootstrap.run_bootstrap()
    rec = await db.permission_settings.find_one({"id": "default"}, {"_id": 0})
    for role, mods in DEFAULT_PERMISSIONS.items():
        if "data_export" in mods:
            assert set(mods["data_export"]) <= set(rec["matrix"][role].get("data_export") or []), role
    r = await klien.get("/api/export-center/datasets", headers=kepala_admin)
    assert r.status_code == 200, r.text


async def test_U2_garis_dasar_rusak_admin_dipulihkan_peran_lain_tidak(klien, kepala_admin, db):
    await _cabut_data_export(db, garis_dasar="tetap")   # `defaults_applied` tetap menandai data_export "diterapkan"
    await bootstrap.run_bootstrap()
    rec = await db.permission_settings.find_one({"id": "default"}, {"_id": 0})
    assert rec["matrix"]["admin"]["data_export"] == ["view", "export"]
    assert "data_export" not in rec["matrix"]["finance"]   # bisa jadi keputusan Admin → tidak dihidupkan diam-diam
    r = await klien.get("/api/export-center/datasets", headers=kepala_admin)
    assert r.status_code == 200, r.text
    jejak = await db.audit_logs.find_one({"action": "locked_role_defaults_restored"}, {"_id": 0})
    assert jejak and "data_export" in str(jejak)


async def test_U3_start_biasa_tidak_menulis(db):
    sebelum = await db.permission_settings.find_one({"id": "default"}, {"_id": 0, "updated_at": 1})
    hasil = await bootstrap.ensure_locked_role_defaults()
    assert hasil == {}
    sesudah = await db.permission_settings.find_one({"id": "default"}, {"_id": 0, "updated_at": 1})
    assert sebelum == sesudah
