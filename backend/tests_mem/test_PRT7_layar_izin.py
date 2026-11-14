"""PR-T7 — tombol dan panggilan data di layar mengikuti izin (docs/blueprint/unit/PR-T7.md), bagian server.

U3  `POST /api/auth/login` membawa konteks izin lengkap (sama dengan `GET /api/auth/me`) + daftar peran, supaya layar
    pertama tidak digambar dengan konteks kosong (PR-UX-41). Ditambah `user.employee_id` (tautan karyawan dari sisi HR,
    sumber yang sama dengan `GET /api/hr/employees/me`) — layar Profil Saya tidak memanggil `/hr/employees/me` bila kosong.
U4  `GET /api/rnd/samples/{id}` membawa `caps.pick_winner` / `caps.approve_spec` yang dihitung pemeriksa kebijakan server
    (`rnd_spec_service._assert_role`), bukan layar dari daftar peran pengaturan.

Peran uji: "Staf Penagihan Uji" = peran kustom tanpa peran dasar, levels {ar: manage, customer: view, approval: view}
(peran yang dipakai `docs/audit/konfigurasi-peran-2026-11-13/bukti/ui_pengaturan_peran.js`). "Tanpa Acuan" dan Sopir
= peran uji baku `02_STANDAR.md` §6. Fixture: akun & sample disisipkan langsung ke database; peran dibuat lewat API.
Di kode lama: login tanpa `view_resources`/`hidden_views`/`roles`/`employee_id`; rincian sample tanpa `caps`.
"""
from __future__ import annotations

import pytest

from core_utils import hash_password

pytestmark = pytest.mark.anyio

SANDI = "SandiUjiPRT7-123"
SAMPLE_ID = "smp_uji_prt7"


async def _peran_penagihan(klien, kepala_admin) -> str:
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={
        "label": "Staf Penagihan Uji", "base_role": "", "description": "Menagih piutang; uji PR-T7",
        "levels": {"ar": "manage", "customer": "view", "approval": "view"}})
    assert r.status_code == 200, r.text
    j = r.json()
    return (j.get("role") or j)["id"]


async def _akun_bersandi(akun, db, peran: str) -> dict:
    u = await akun(peran)
    await db.users.update_one({"id": u["id"]}, {"$set": {"password_hash": hash_password(SANDI)}})
    return u


async def test_PRT7_U3_login_membawa_konteks_izin_dan_daftar_peran(klien, akun, db, kepala_admin):
    rid = await _peran_penagihan(klien, kepala_admin)
    u = await _akun_bersandi(akun, db, rid)
    r = await klien.post("/api/auth/login", json={"email": u["email"], "password": SANDI})
    assert r.status_code == 200, r.text
    j = r.json()
    # Konteks izin = bentuk GET /api/auth/me (view_resources + hidden_views) …
    me = (await klien.get("/api/auth/me", headers={"Authorization": f"Bearer {j['token']}"})).json()
    assert isinstance(j.get("view_resources"), dict) and j["view_resources"], "login tanpa view_resources"
    assert j["view_resources"] == me["view_resources"]
    assert isinstance(j.get("hidden_views"), list) and j["hidden_views"] == me["hidden_views"]
    assert j["permissions"] == me["permissions"]
    assert j["permissions"].get("customer") == ["view"] and "view" in j["permissions"].get("approval", [])
    # … dan daftar peran berbentuk GET /api/roles yang memuat peran kustom itu (beranda & menu sejak layar pertama).
    roles = {x["id"]: x for x in (j.get("roles") or [])}
    assert rid in roles, "daftar peran di jawaban login tidak memuat peran kustom akun ini"
    assert roles[rid]["custom"] is True and roles[rid]["base_role"] == ""
    assert roles[rid]["home_view"] == "hr-my-profile"
    daftar_api = (await klien.get("/api/roles", headers={"Authorization": f"Bearer {j['token']}"})).json()["roles"]
    assert [x["id"] for x in j["roles"]] == [x["id"] for x in daftar_api]


async def test_PRT7_U3b_employee_id_mengikuti_tautan_karyawan(klien, akun, db, kepala_admin):
    """Akun tanpa karyawan → `employee_id` "" (layar tidak memanggil /hr/employees/me, yang pasti 404).
    Akun tertaut lewat sisi HR saja (`hr_employees.user_id`, bentuk data acuan: 14 dari 17 akun tanpa
    `users.employee_id`) → `employee_id` terisi dan /hr/employees/me 200."""
    u = await _akun_bersandi(akun, db, "sales")
    j = (await klien.post("/api/auth/login", json={"email": u["email"], "password": SANDI})).json()
    assert j["user"].get("employee_id") == ""
    h = {"Authorization": f"Bearer {j['token']}"}
    assert (await klien.get("/api/hr/employees/me", headers=h)).status_code == 404
    assert (await klien.get("/api/auth/me", headers=h)).json().get("employee_id") == ""
    await db.hr_employees.insert_one({"id": "emp_uji_prt7", "code": "EMP-PRT7", "name": u["name"], "user_id": u["id"],
                                      "entity_id": "ent_ksc", "status": "active", "allowances": []})
    j2 = (await klien.post("/api/auth/login", json={"email": u["email"], "password": SANDI})).json()
    assert j2["user"].get("employee_id") == "emp_uji_prt7"
    h2 = {"Authorization": f"Bearer {j2['token']}"}
    assert (await klien.get("/api/auth/me", headers=h2)).json().get("employee_id") == "emp_uji_prt7"
    assert (await klien.get("/api/hr/employees/me", headers=h2)).status_code == 200


async def _siapkan_sample(db, klien, kepala_admin) -> None:
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [{
        "key": "rnd.sample_decision_roles", "value": ["manager"], "scope_type": "global", "scope_id": "",
        "reason": "uji PR-T7 U4: hanya manajer memutus pemenang"}]})
    assert r.status_code == 200, r.text
    if not await db.md_samples.find_one({"id": SAMPLE_ID}):
        await db.md_samples.insert_one({
            "id": SAMPLE_ID, "number": "SMP/UJI/PRT7", "title": "Sample uji PR-T7", "entity_id": "ent_ksc",
            "status": "in_progress", "purpose": "", "sample_types": ["labdip"], "rounds": [], "participants": [],
            "timeline": [], "line_code": "", "created_by": "uji"})


async def test_PRT7_U4_bendera_pick_winner_dari_pemeriksa_server(klien, akun, sesi, db, kepala_admin,
                                                                peran_tanpa_acuan, peran_sopir):
    from services import rnd_spec_service as specs
    from services.rnd_sample_service import RndError

    await _siapkan_sample(db, klien, kepala_admin)

    async def jawaban_pemeriksa(peran: str) -> bool:
        try:
            await specs._assert_role({"role": peran}, "sample_decision_roles", "ent_ksc", "memutus pemenang sample")
            return True
        except RndError:
            return False

    mgr = await sesi("manager@kainnusantara.id")
    r = await klien.get(f"/api/rnd/samples/{SAMPLE_ID}", headers=mgr)
    assert r.status_code == 200, r.text
    assert r.json()["caps"]["pick_winner"] is True

    ta_id = await peran_tanpa_acuan({"rnd": ["view", "decide"]}, label="TA Putus Sample")
    ta = await sesi(await akun(ta_id))
    r = await klien.get(f"/api/rnd/samples/{SAMPLE_ID}", headers=ta)
    assert r.status_code == 200, r.text
    assert r.json()["caps"]["pick_winner"] is await jawaban_pemeriksa(ta_id)
    assert r.json()["caps"]["pick_winner"] is False   # kebijakan ["manager"] — id peran kustom tidak tercantum

    sopir = await sesi(await akun(peran_sopir))
    assert (await klien.get(f"/api/rnd/samples/{SAMPLE_ID}", headers=sopir)).status_code == 403


async def test_PRT7_U4b_approve_spec_dan_uji_ulang(klien, sesi, db, kepala_admin):
    """`caps.approve_spec` = kebijakan `rnd.spec_approval_roles` (bawaan manajer & admin); sample uji ulang selalu boleh
    memilih (server melewati kebijakan peran untuk hasil teknis uji ulang — `decide_sample`)."""
    from services import rnd_spec_service as specs

    await _siapkan_sample(db, klien, kepala_admin)
    adm = kepala_admin
    caps = (await klien.get(f"/api/rnd/samples/{SAMPLE_ID}", headers=adm)).json()["caps"]
    allowed = await specs._policy_roles("spec_approval_roles", "ent_ksc")
    assert caps["approve_spec"] is (not allowed or "admin" in allowed)
    assert caps["pick_winner"] is False   # admin tidak tercantum di ["manager"]
    await db.md_samples.update_one({"id": SAMPLE_ID}, {"$set": {"purpose": "revalidation",
                                                                 "revalidation": {"supplier_id": "sup_x"}}})
    try:
        caps = (await klien.get(f"/api/rnd/samples/{SAMPLE_ID}", headers=adm)).json()["caps"]
        assert caps["pick_winner"] is True
    finally:
        await db.md_samples.update_one({"id": SAMPLE_ID}, {"$set": {"purpose": ""}, "$unset": {"revalidation": ""}})
