"""KF-T1 — izin kelola dan lihat pengaturan benar-benar berfungsi (docs/blueprint/unit/KF-T1.md).

Peran uji: "Tanpa Acuan" (izin rinci), "Manajer Kosong", Sopir (`driver`); akun `mgr` (manager seed), `adm` (admin seed),
akun berperan `md`. PT `ent_ksc`. Satu database per modul; nilai yang diubah dicatat per uji.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import bootstrap
import config_registry as registry
from access_modules import VIEW_RESOURCE_OVERRIDES
from services import config_resolver as resolver

pytestmark = pytest.mark.anyio

B1 = "Anda belum punya akses untuk melihat pengaturan. Minta Admin menambahkan akses 'Pengaturan, Pengguna & Hak Akses'."
KUNCI_TERBUKA = ["finance.default_payment_term_code", "inventory.min_cut_qty", "sales.allow_item_discount",
                 "sales.allow_order_discount", "tax.ppn_rate", "tax.ppn_mode", "tax.dpp_nilai_lain",
                 "allocation.roll_pick_sales", "purchasing.allow_item_discount", "purchasing.allow_order_discount",
                 "purchasing.bill_price_tolerance_percent", "purchasing.bill_qty_tolerance_percent",
                 "ui.show_coming_soon", "ui.coming_soon_collapsed"]


def _put(key, value, scope_type="entity", scope_id="ent_ksc"):
    return {"items": [{"key": key, "value": value, "scope_type": scope_type, "scope_id": scope_id,
                       "reason": "uji KF-T1"}]}


def _detail(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


async def _orang(akun, sesi, peran):
    u = await akun(peran)
    return u, await sesi(u)


async def test_U01_pemegang_kelola_pengaturan_menyimpan_lapisan_pt(klien, akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"settings": ["view", "manage"]}, label="Kelola Pengaturan")
    _, h = await _orang(akun, sesi, rid)
    r = await klien.put("/api/config/values", headers=h, json=_put("sales.allow_partial_shipment", False))
    assert r.status_code == 200, r.text
    assert await resolver.value_of("sales.allow_partial_shipment", {"entity_id": "ent_ksc"}) is False


async def test_U02_bisa_ubah_232_kunci(klien, akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"settings": ["view", "manage"]}, label="Kelola Pengaturan 2")
    _, h = await _orang(akun, sesi, rid)
    r = await klien.get("/api/config/effective", headers=h)
    assert r.status_code == 200, r.text
    # PR-T2 — 232 kunci aktif berizin `settings.manage` saat KF-T1; tiga kunci `ai.*_roles` kini tidak dipakai
    # (diatur di Peran & Hak Akses) → 232 − 3 = 229.
    assert sum(1 for it in r.json()["items"] if it["can_edit"]) == 229


async def test_U03_lapisan_grup_tetap_untuk_lintas_pt(klien, akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"settings": ["view", "manage"]}, label="Kelola Pengaturan 3")
    _, h = await _orang(akun, sesi, rid)
    r = await klien.put("/api/config/values", headers=h, json=_put("sales.allow_partial_shipment", False, "global", ""))
    assert r.status_code == 403, r.text
    assert "hanya dapat diubah peran lintas badan usaha" in _detail(r)


async def test_U04_lihat_saja_tidak_bisa_ubah(klien, akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"settings": ["view"]}, label="Lihat Pengaturan")
    _, h = await _orang(akun, sesi, rid)
    r = await klien.put("/api/config/values", headers=h, json=_put("sales.allow_partial_shipment", True))
    assert r.status_code == 403, r.text
    assert "'Pengaturan, Pengguna & Hak Akses'" in _detail(r)
    assert "settings.manage" not in _detail(r)
    r = await klien.get("/api/config/registry", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 310 + 5   # PK-46 menambah lima kunci PPh 21 bertanggal (hr.ptkp_table sudah ada)


async def test_U05_manajer_kosong_tidak_lagi_lewat_nama_peran(klien, akun, sesi, peran_manajer_kosong):
    sebelum = await resolver.value_of("lot.require_dye_lot", {"entity_id": "ent_ksc"})
    _, h = await _orang(akun, sesi, await peran_manajer_kosong())
    r = await klien.put("/api/config/values", headers=h, json=_put("lot.require_dye_lot", not sebelum))
    assert r.status_code == 403, r.text
    r = await klien.get("/api/config/registry", headers=h)
    assert r.status_code == 403, r.text
    assert await resolver.value_of("lot.require_dye_lot", {"entity_id": "ent_ksc"}) == sebelum


async def test_U06_manajer_bawaan_tetap_berwenang(klien, sesi):
    h = await sesi("manager@kainnusantara.id")
    r = await klien.put("/api/config/values", headers=h, json=_put("lot.require_dye_lot", False, "global", ""))
    assert r.status_code == 200, r.text
    n = await resolver.value_of("rnd.max_rounds", {})
    r = await klien.put("/api/config/values", headers=h, json=_put("rnd.max_rounds", int(n) + 1, "global", ""))
    assert r.status_code == 200, r.text


async def test_U07_izin_konfigurasi_stok_hanya_kunci_lot(klien, akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"inventory": ["view", "configure"]}, label="Atur Stok")
    _, h = await _orang(akun, sesi, rid)
    r = await klien.put("/api/config/values", headers=h, json=_put("lot.require_dye_lot", True))
    assert r.status_code == 200, r.text
    r = await klien.put("/api/config/values", headers=h, json=_put("makloon.auto_claim", False))
    assert r.status_code == 403, r.text
    r = await klien.get("/api/config/registry", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 8
    assert all(e["key"].startswith("lot.") for e in r.json()["entries"])
    r = await klien.get("/api/config/effective", headers=h, params={"group": "pajak"})
    assert r.status_code == 403, r.text
    assert _detail(r).startswith("Anda belum punya akses untuk melihat pengaturan “Pajak”")


async def test_U08_migrasi_peran_beracuan_manajer_sekali_jalan(klien, kepala_admin, db):
    rid = "cr_manajer_lama_kft1"
    await db.custom_roles.insert_one({"id": rid, "label": "Manajer Lama KF", "description": "uji", "base_role": "manager",
                                      "levels": {}, "created_at": "2026-01-01", "updated_at": "2026-01-01"})
    await db.permission_settings.update_one({"id": "default"}, {"$set": {f"matrix.{rid}": {}}})
    await db.system_settings.update_one({"scope": "__migrations__"}, {"$unset": {"kft1_izin_pengaturan": ""}})
    migrasi = getattr(bootstrap, "migrate_kft1_settings_permissions")
    await migrasi()
    m1 = (await db.permission_settings.find_one({"id": "default"}))["matrix"][rid]
    for res, act in (("rnd", "manage"), ("inventory", "configure"), ("goods_receipt", "configure"),
                     ("makloon", "configure")):
        assert act in (m1.get(res) or []), (res, m1)
    assert "view" not in (m1.get("inventory") or [])
    doc1 = await db.permission_settings.find_one({"id": "default"}, {"_id": 0})
    await migrasi()
    assert await db.permission_settings.find_one({"id": "default"}, {"_id": 0}) == doc1
    perms = {k: list(v) for k, v in m1.items() if k != "inventory"}
    r = await klien.patch(f"/api/access/roles/{rid}", headers=kepala_admin, json={"permissions": perms})
    assert r.status_code == 200, r.text
    await migrasi()
    m3 = (await db.permission_settings.find_one({"id": "default"}))["matrix"][rid]
    assert "configure" not in (m3.get("inventory") or [])


async def test_U09_sopir_tidak_membaca_pusat_pengaturan(klien, akun, sesi, peran_sopir):
    _, h = await _orang(akun, sesi, peran_sopir)
    for path, params in (("/api/config/registry", {}), ("/api/config/effective", {}),
                         ("/api/config/explain", {"key": "tax.ppn_rate"}), ("/api/config/history", {}),
                         ("/api/config/simulators", {}), ("/api/config/health", {})):
        r = await klien.get(path, headers=h, params=params)
        assert r.status_code == 403, (path, r.text)
        if path != "/api/config/health":
            assert _detail(r).startswith("Anda belum punya akses untuk melihat pengaturan"), (path, r.text)


async def test_U10_md_tetap_32_kunci_rnd(klien, akun, sesi):
    _, h = await _orang(akun, sesi, "md")
    r = await klien.get("/api/config/registry", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 32
    n = await resolver.value_of("rnd.max_rounds", {"entity_id": "ent_ksc"})
    r = await klien.put("/api/config/values", headers=h, json=_put("rnd.max_rounds", int(n) + 1))
    assert r.status_code == 200, r.text
    r = await klien.get("/api/config/explain", headers=h, params={"key": "bank.auto_match_min_score"})
    assert r.status_code == 403, r.text


async def test_U11_pengaturan_efektif_disaring_untuk_pembaca_biasa(klien, kepala_admin, akun, sesi, peran_sopir):
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json=_put("bank.auto_match_min_score", 85, "global", ""))
    assert r.status_code == 200, r.text
    _, h = await _orang(akun, sesi, peran_sopir)
    s = (await klien.get("/api/settings/effective", headers=h)).json()
    assert "show_coming_soon" in s.get("ui", {})
    assert "ppn_rate" in s.get("tax", {}) and "is_pkp" in s.get("tax", {})
    assert "default_payment_term_code" in s.get("finance", {})
    for atas in ("bank", "commission", "approval", "ar", "role_home"):
        assert atas not in s, atas
    a = (await klien.get("/api/settings/effective", headers=kepala_admin)).json()
    assert a["bank"]["auto_match_min_score"] == 85
    assert "commission" in a


async def test_U12_baca_pengaturan_mentah_butuh_izin_lihat(klien, akun, sesi, peran_sopir):
    _, h = await _orang(akun, sesi, peran_sopir)
    r = await klien.get("/api/settings", headers=h)
    assert r.status_code == 403, r.text
    assert _detail(r) == B1
    r = await klien.get("/api/settings", headers=await sesi("manager@kainnusantara.id"))
    assert r.status_code == 200, r.text


async def test_U13_registry_tanpa_nama_peran():
    for e in registry.all_entries():
        assert "roles" not in e and "owner_role" not in e, e["key"]
    for k in KUNCI_TERBUKA:
        assert registry.get(k)["sensitif_baca"] is False, k
    with pytest.raises(TypeError):
        registry.E("x.y", group="tampilan", label="a", help="b", impact="c", roles=("manager",))


def _kelompok_layar() -> dict:
    js = (Path(__file__).resolve().parents[2] / "frontend/src/features/settings/config/configGroupViews.js").read_text()
    out = {}
    for view, groups in re.findall(r'"(settings-cfg-[a-z]+)":\s*\{[^}]*?groups:\s*\[([^\]]*)\]', js, re.S):
        out[view] = re.findall(r'"([a-z-]+)"', groups)
    return out


def test_U14_tab_pengaturan_mengikuti_izin_kuncinya():
    hitung = {"settings-config": {"settings"}}
    for view, groups in _kelompok_layar().items():
        res = {"settings"}
        for g in groups:
            res |= {e["permission"][0] for e in registry.by_group(g) if not e["key"].startswith("commission.")}
        hitung[view] = res
    assert len(hitung) == 11
    for view, res in hitung.items():
        assert set(VIEW_RESOURCE_OVERRIDES.get(view, [])) == res, view
