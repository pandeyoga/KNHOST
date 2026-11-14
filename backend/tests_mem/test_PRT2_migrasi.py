"""PR-T2 — izin pengganti gerbang nama peran: katalog & migrasi sekali jalan (docs/blueprint/unit/PR-T2.md).

Serah-terima (a): hijau SEBELUM gerbang lama dialihkan (U11, U14) dan sesudahnya.
"Nyalakan ulang" = `bootstrap.run_bootstrap()` + `custom_role_service.sync_registry()` (urutan `server.lifespan`).
"Instalasi lama" = fixture: semua pasangan bawaan PR-T2 dibuang dari `matrix` dan `defaults_applied`, id migrasi
dihapus — keadaan basis data yang dibuat kode sebelum PR-T2.
"""
from __future__ import annotations

import pytest

import bootstrap
from permissions_config import AI_TEMPLATE_IDS, DEFAULT_PERMISSIONS, PRT2_ACTIONS, PRT2_RESOURCES

pytestmark = pytest.mark.anyio

ID = "prt2:gerbang-peran"
SIMPAN: dict = {}


async def _nyalakan_ulang() -> None:
    from services.custom_role_service import sync_registry
    await bootstrap.run_bootstrap()
    await sync_registry()


def _pasangan_prt2() -> dict:
    out = {res: None for res in [*PRT2_RESOURCES, "ai_template"]}   # None = seluruh sumber daya
    for (res, act) in PRT2_ACTIONS:
        out.setdefault(res, [])
        if out[res] is not None:
            out[res].append(act)
    return out


async def _tiru_instalasi_lama(db) -> None:
    rec = await db.permission_settings.find_one({"id": "default"})
    for kunci in ("matrix", "defaults_applied"):
        for perms in (rec.get(kunci) or {}).values():
            for res, acts in _pasangan_prt2().items():
                if acts is None:
                    perms.pop(res, None)
                elif res in perms:
                    perms[res] = [a for a in perms[res] if a not in acts or (res, a) == ("goods_receipt", "configure")]
    rec["migrations_applied"] = [m for m in rec.get("migrations_applied") or [] if m != ID]
    await db.permission_settings.replace_one({"id": "default"}, rec)


async def _peran(klien, h, rid: str) -> dict:
    r = await klien.get(f"/api/access/roles/{rid}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _himpunan(perms: dict) -> dict:
    return {k: set(v) for k, v in (perms or {}).items() if v}


async def test_katalog_enam_modul_dan_label(klien, kepala_admin):
    r = await klien.get("/api/access/modules", headers=kepala_admin)
    assert r.status_code == 200, r.text
    j = r.json()
    mods = {m["id"]: m for m in j["modules"]}
    for mid, res in {"sales_force": ["sales_force", "credit_override"], "costing": ["costing"],
                     "manager_home": ["manager_home"], "system_tools": ["system_tools"], "devices": ["rfid_device"],
                     # AG-T2 — modul Asisten Tanya KN juga memuat Asisten Keuangan (`ai_finance`).
                     "assistant": ["ai", "ai_template", "ai_finance"]}.items():
        assert mods[mid]["resources"] == res, mid
        for x in res:
            assert j["resource_labels"].get(x), x
    assert mods["costing"].get("sensitive") and mods["system_tools"].get("sensitive") and mods["devices"].get("sensitive")
    assert sorted(mods["assistant"]["actions"]["ai_template"]) == sorted(AI_TEMPLATE_IDS)
    assert j["action_labels"]["ai_template.daily_brief"] == "Laporan hari ini"
    for kunci in ("sales_force.post", "revoke", "view_margin", "view_stock_value", "extend_rounds", "retire",
                  "treat_cutloss"):
        assert j["action_labels"].get(kunci), kunci


async def test_bawaan_baru_tercatat_sekali(klien, kepala_admin, db):
    rec = await db.permission_settings.find_one({"id": "default"})
    assert rec["migrations_applied"].count(ID) == 1
    m = await _peran(klien, kepala_admin, "manager")
    assert m["permissions"]["costing"] == ["view"]
    assert set(m["permissions"]["sales_force"]) == {"view", "update", "delete", "post", "assign"}
    assert m["modified"] is False   # basis data baru: matriks = bawaan
    w = await _peran(klien, kepala_admin, "warehouse")
    assert "ai" not in w["permissions"] and "ai_template" not in w["permissions"]   # tidak bisa membuka asisten
    assert await db.audit_logs.count_documents({"action": "role_gates_migrated"}) == 1


async def test_U11_peran_kustom_lama_menerima_baris_N(klien, kepala_admin, db, akun, sesi):
    # Fixture sisip (bukan lewat API): dua peran kustom yang dibuat sebelum PR-T2, matriks kosong.
    for rid, label, base in (("cr_manajer_lama", "Manajer Lama", "manager"),
                             ("cr_gudang_lama", "Gudang Lama", "warehouse_admin")):
        await db.custom_roles.insert_one({"id": rid, "label": label, "description": "uji PR-T2", "base_role": base,
                                          "levels": {}, "created_at": "2026-01-01T00:00:00+00:00",
                                          "updated_at": "2026-01-01T00:00:00+00:00"})
        await db.permission_settings.update_one({"id": "default"}, {"$set": {f"matrix.{rid}": {}}})
    await _tiru_instalasi_lama(db)
    await _nyalakan_ulang()
    ml = await _peran(klien, kepala_admin, "cr_manajer_lama")
    # Baris N berperan manager: Tim Sales (5), pengecualian kredit, HPP, beranda manajer, kebersihan data (lihat/ubah),
    # pemakaian asisten (`ai.manage`, tabel "Endpoint"), dan `ai.view` (manager ada di `ai.enabled_roles`).
    # Tidak ada baris P+N (matriks kosong → tidak memegang P), tidak ada `ai.view_margin`/templat (nama persis).
    assert _himpunan(ml["permissions"]) == {
        "sales_force": {"view", "update", "delete", "post", "assign"}, "credit_override": {"approve"},
        "costing": {"view"}, "manager_home": {"view"}, "system_tools": {"view", "update"}, "ai": {"view", "manage"}}
    assert ml["levels"]["costing"]["level"] == "view"
    u = await akun("cr_manajer_lama")
    r = await klien.get("/api/costing/wac", headers=await sesi(u))
    assert r.status_code == 200, r.text
    gl = await _peran(klien, kepala_admin, "cr_gudang_lama")
    # Koreksi blueprint (laporan PR-T2): selain `rfid_device.revoke`, Admin Gudang ada di `ai.enabled_roles` bawaan —
    # hari ini peran kustom beracuan Admin Gudang lolos `_ai_user`, jadi menerima `ai.view` juga.
    assert _himpunan(gl["permissions"]) == {"rfid_device": {"revoke"}, "ai": {"view"}}


async def test_migrasi_tidak_jalan_dua_kali_dan_pencabutan_bertahan(klien, kepala_admin, db):
    m = await _peran(klien, kepala_admin, "manager")
    perms = {k: list(v) for k, v in m["permissions"].items()}
    perms.pop("costing")
    r = await klien.patch("/api/access/roles/manager", headers=kepala_admin, json={"permissions": perms})
    assert r.status_code == 200, r.text
    await _nyalakan_ulang()
    m = await _peran(klien, kepala_admin, "manager")
    assert "costing" not in m["permissions"]
    rec = await db.permission_settings.find_one({"id": "default"})
    assert rec["migrations_applied"].count(ID) == 1
    assert "view" in rec["defaults_applied"]["manager"]["costing"]
    r = await klien.post("/api/access/roles/manager/reset", headers=kepala_admin)
    assert r.status_code == 200, r.text


async def test_U14_migrasi_membaca_nilai_pengaturan_ai(klien, db, sesi):
    # Fixture: nilai `ai.enabled_roles` diubah SEBELUM migrasi (baris `config_values` disisip langsung).
    await db.config_values.insert_one({
        "id": "cfgv_uji_prt2", "key": "ai.enabled_roles", "scope_type": "global", "scope_id": "",
        "value": ["admin", "manager"], "effective_from": "2026-01-01T00:00:00+00:00", "effective_to": "",
        "reason": "uji PR-T2", "changed_by": "uji", "changed_at": "2026-01-01T00:00:00+00:00",
        "created_at": "2026-01-01T00:00:00+00:00", "applied_at": "2026-01-01T00:00:00+00:00"})
    await _tiru_instalasi_lama(db)
    await _nyalakan_ulang()
    rec = await db.permission_settings.find_one({"id": "default"})
    assert "ai" not in rec["matrix"]["sales"] and "ai_template" not in rec["matrix"]["sales"]
    assert "view" in rec["defaults_applied"]["sales"]["ai"]   # tidak diberikan lagi oleh sync_permission_modules
    assert rec["matrix"]["manager"]["ai"]
    r = await klien.get("/api/ai/status", headers=await sesi("sales@kainnusantara.id"))
    assert r.status_code == 403, r.text
    await db.config_values.delete_one({"id": "cfgv_uji_prt2"})
    await _nyalakan_ulang()   # start biasa: tidak ada yang berubah lagi
    rec2 = await db.permission_settings.find_one({"id": "default"})
    assert "ai" not in rec2["matrix"]["sales"]
    assert rec2["migrations_applied"].count(ID) == 1
    assert DEFAULT_PERMISSIONS["sales"]["ai"] == ["view"]
