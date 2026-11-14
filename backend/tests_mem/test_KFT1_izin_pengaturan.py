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

# PR-T5 — modul gabungan "Pengaturan, Pengguna & Hak Akses" dipecah; pemilik `settings` = modul "Pusat Pengaturan".
B1 = "Anda belum punya akses untuk melihat pengaturan. Minta Admin menambahkan akses 'Pusat Pengaturan'."
KUNCI_TERBUKA = ["finance.default_payment_term_code", "inventory.min_cut_qty", "sales.allow_item_discount",
                 "sales.allow_order_discount", "tax.ppn_rate", "tax.ppn_mode", "tax.dpp_nilai_lain",
                 "allocation.roll_pick_sales", "purchasing.allow_item_discount", "purchasing.allow_order_discount",
                 "purchasing.bill_price_tolerance_percent", "purchasing.bill_qty_tolerance_percent",
                 "ui.show_coming_soon", "ui.coming_soon_collapsed"]
# KF-T6 — 57 kunci `kontrol.*` (izin `settings.manage`) didaftarkan sesudah KF-T1: ikut terhitung di U02/U04. Sakelar
# lama `amendment.dual_control` (izin `settings.manage`) menjadi `not_used` → tidak bisa diubah siapa pun (−1 di U02).
KFT6_KUNCI = 57
KFT6_TIDAK_DIPAKAI = 1
# PR-T4 — empat kunci `role_home.*` (izin `settings.manage`) kini `not_used`: halaman awal diatur per peran di Peran &
# Hak Akses › Sifat peran → tidak bisa diubah siapa pun di Pusat Pengaturan (−4 di U02).
PRT4_TIDAK_DIPAKAI = 4
# KF-T2 — 11 kunci baru (`returns.*` ber-izin `sales_return.policy`, `interco_payment.*` ber-izin `entity.update`): ikut
# terhitung di katalog (U04) tetapi tidak bisa diubah pemegang `settings.manage` saja (U02 tetap). Empat kunci ber-izin
# `settings.manage` menjadi `not_used` (`contra_bon.qty_tolerance_percent`, `bank.holding/charge/interest_account_code`) →
# −4 di U02; `lot.number_format` (izin `inventory.configure`) tidak terhitung di U02.
KFT2_KUNCI = 11
KFT2_TIDAK_DIPAKAI = 4
# KP-T4 — 17 kunci persetujuan pindah ke Aturan Persetujuan (`not_used`); 10 di antaranya berizin `settings.manage`
# (approval.extra_levels, amendment.{approver_role, admin_approval_above}, antar_entitas.{approval_role,
# high_value_approval_role, approval_threshold_rupiah}, contra_bon.{tiga kunci yang sama},
# payment.variance_writeoff_approver_role); 7 lainnya berizin domain (rnd.manage / makloon.configure).
KPT4_TIDAK_DIPAKAI = 10
# KF-T3 — `tax.efaktur_enabled` (izin `settings.manage`) menjadi `not_used`: e-Faktur mengikuti status PKP di profil PT →
# tidak bisa diubah siapa pun (−1 di U02). Tidak ada kunci baru (U04 tetap).
KFT3_TIDAK_DIPAKAI = 1
# KP-T7 — 19 kunci pengingat & penjadwal baru berizin `scheduler.configure` (bawaan hanya Admin): ikut terhitung di katalog
# (U04) tetapi tidak bisa diubah pemegang `settings.manage` saja (U02 tetap). Tab "notifikasi", "keuangan-dasar",
# "persetujuan", dan "rnd" kini juga terbuka bagi pemegang izin `scheduler` (U14, `VIEW_RESOURCE_OVERRIDES`).
KPT7_KUNCI = 19
# PK-36 — satu kunci baru `gl.jurnal_manual_akun_kontrol` berizin `accounting.manage` (kelompok "keuangan-dasar"): ikut
# terhitung di katalog (U04) tetapi tidak bisa diubah pemegang `settings.manage` saja (U02 tetap). Tab "keuangan-dasar"
# kini juga terbuka bagi pemegang izin `accounting` (U14, `VIEW_RESOURCE_OVERRIDES`).
PK36_KUNCI = 1
# KF-T7 — 26 kunci baru (nilai bisnis yang dulu ditulis mati), semuanya berizin `settings.manage` dan aktif: ikut
# terhitung di U02 (bisa diubah pemegang `settings.manage`) dan di katalog (U04). Kelompok baru `keamanan` tinggal di
# layar `settings-cfg-system` bersama `sistem` (izin kuncinya `settings` → U14 tetap).
KFT7_KUNCI = 26
# PK-37 — satu kunci baru `periode.kunci_dokumen` berizin `accounting.manage`: ikut terhitung di katalog (U04) tetapi
# tidak bisa diubah pemegang `settings.manage` saja (U02 tetap). Tab "Keuangan" Pusat Pengaturan kini juga terbuka bagi
# pemegang izin `accounting` (U14, `VIEW_RESOURCE_OVERRIDES["settings-cfg-finance"]`).
PK37_KUNCI = 1
# PK-38 — aksi kontrol dua orang baru `bayar_hutang` (K-17): dua kunci `kontrol.bayar_hutang.{min_orang,batas_nominal}`
# berizin `settings.manage` → ikut terhitung di U02 dan U04. Batas pengurang piutang sudah ada sejak KF-T6 (hanya
# bawaannya yang berubah); `payment.variance_writeoff_max_amount` tetap aktif.
PK38_KUNCI = 2
# KP-T8 — dua kunci baru `integrations.anthropic.{enabled,model}` berizin `integration.manage` (bawaan Admin): ikut
# terhitung di katalog (U04) tetapi tidak bisa diubah pemegang `settings.manage` saja (U02 tetap). Tab "AI & Tampilan"
# (`settings-cfg-system`) kini juga terbuka bagi pemegang izin `integration` (U14, `VIEW_RESOURCE_OVERRIDES`).
KPT8_KUNCI = 2
# PK-30 — satu kunci baru `antar_entitas.selisih_panjang` berizin `accounting.manage` (kelompok "pajak-pembukuan"): ikut
# terhitung di katalog (U04) tetapi tidak bisa diubah pemegang `settings.manage` saja (U02 tetap).
PK30_KUNCI = 1
# PM-T1 — aksi kontrol dua orang baru `ubah_rekening` (tanpa nominal): satu kunci `kontrol.ubah_rekening.min_orang`
# berizin `settings.manage` → ikut terhitung di U02 dan U04.
PMT1_KUNCI = 1
# CR-T1 — aksi kontrol dua orang baru `ubah_profil_kredit` (bernominal): dua kunci `kontrol.ubah_profil_kredit.*` berizin
# `settings.manage` → ikut terhitung di U02 dan U04. Kunci ketiga `ar.default_credit_limit` berizin
# `credit_profile.approve` (bukan `settings.manage`): hanya terhitung di katalog (U04).
CRT1_KUNCI_KONTROL = 2
CRT1_KUNCI = 3
# AG-T1 — satu kunci baru `ai.kartu_masa_berlaku_jam` (masa berlaku kartu tindakan asisten, berlapis PT) berizin
# `settings.manage` dan aktif → ikut terhitung di U02 (bisa diubah pemegang `settings.manage`) dan di katalog (U04).
AGT1_KUNCI = 1
# PM-T2 — dua kunci baru `payment.wajib_cara_bayar_di_pesanan`, `payment.kode_bayar_awalan` berizin `cash.configure`
# (kelola rekening & cara bayar): ikut terhitung di katalog (U04) tetapi tidak bisa diubah pemegang `settings.manage` saja
# (U02 tetap).
PMT2_KUNCI = 2
# TX-T1 — tujuh kunci pajak baru (faktor DPP nilai lain, pembulatan, kode transaksi faktur) berizin `accounting.manage`
# (kelompok "pajak-pembukuan"): ikut terhitung di katalog (U04) tetapi tidak bisa diubah pemegang `settings.manage` saja
# (U02 tetap). Tab Pajak Pusat Pengaturan sudah terbuka bagi pemegang izin `accounting` sejak PK-36/PK-37.
TXT1_KUNCI = 7
# PK-39 — kunci `budget.mode` (mode pemeriksaan anggaran, dulu `fin_budget_rules.mode`) berizin `budget.configure`:
# ikut terhitung di katalog (U04) tetapi tidak bisa diubah pemegang `settings.manage` saja (U02 tetap).
PK39_KUNCI = 1
# PK-26 — satu kunci baru `inventory.landed_cost_porsi_terjual` berizin `accounting.manage` (kelompok "pembelian"): ikut
# terhitung di katalog (U04) tetapi tidak bisa diubah pemegang `settings.manage` saja (U02 tetap). Tab "Aturan Pembelian
# & Makloon" (`settings-cfg-purchasing`) kini juga terbuka bagi pemegang izin `accounting` (U14, `VIEW_RESOURCE_OVERRIDES`).
PK26_KUNCI = 1
# AG-T2 — satu kunci baru `ai.samarkan_nama` (samarkan nama pihak ke penyedia model, berlapis PT) berizin `ai.configure`:
# ikut terhitung di katalog (U04) tetapi tidak bisa diubah pemegang `settings.manage` saja (U02 tetap).
AGT2_KUNCI = 1
# PK-24 — dua kunci `kontrol.cairkan_uang_muka.*` berizin `settings.manage` (ikut U02 dan U04) + satu kunci
# `finance.lpj_wajib_lampiran` berizin `accounting.manage` (ikut katalog U04, tidak bisa diubah `settings.manage` saja).
PK24_KUNCI_KONTROL = 2
PK24_KUNCI = 3
# PK-29 — satu kunci baru `inventory.trueup_hanya_saldo_awal` (true-up persediaan hanya untuk saldo awal, K-06) berizin
# `accounting.manage` (kelompok "pajak-pembukuan"): ikut terhitung di katalog (U04) tetapi tidak bisa diubah pemegang
# `settings.manage` saja (U02 tetap).
PK29_KUNCI = 1
# PK-22 — satu kunci baru `gl.tanggal_jurnal_periodik` (tanggal jurnal gaji, penyusutan, insentif) berizin
# `accounting.manage` (kelompok "pajak-pembukuan"): ikut terhitung di katalog (U04) tetapi tidak bisa diubah pemegang
# `settings.manage` saja (U02 tetap).
PK22_KUNCI = 1


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
    # (diatur di Peran & Hak Akses) → 232 − 3 = 229. KF-T6 menambah kunci `kontrol.*` (KFT6_KUNCI) dan mematikan
    # sakelar lama (KFT6_TIDAK_DIPAKAI). PR-T4 mematikan empat kunci halaman awal (PRT4_TIDAK_DIPAKAI); KF-T2 empat kunci
    # lain (KFT2_TIDAK_DIPAKAI); KP-T4 10 kunci persetujuan berizin settings.manage (KPT4_TIDAK_DIPAKAI); KF-T3 satu kunci
    # e-Faktur (KFT3_TIDAK_DIPAKAI). Tidak tumpang tindih: kunci contra_bon milik KF-T2 (`qty_tolerance_percent`) bukan
    # salah satu dari tiga kunci persetujuan KP-T4.
    assert sum(1 for it in r.json()["items"] if it["can_edit"]) == \
        229 + KFT6_KUNCI - KFT6_TIDAK_DIPAKAI - PRT4_TIDAK_DIPAKAI - KFT2_TIDAK_DIPAKAI - KPT4_TIDAK_DIPAKAI \
        - KFT3_TIDAK_DIPAKAI + KFT7_KUNCI + PK38_KUNCI + PMT1_KUNCI + CRT1_KUNCI_KONTROL + AGT1_KUNCI \
        + PK24_KUNCI_KONTROL


async def test_U03_lapisan_grup_tetap_untuk_lintas_pt(klien, akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"settings": ["view", "manage"]}, label="Kelola Pengaturan 3")
    _, h = await _orang(akun, sesi, rid)
    r = await klien.put("/api/config/values", headers=h, json=_put("sales.allow_partial_shipment", False, "global", ""))
    assert r.status_code == 403, r.text
    # KF-T4 — glosarium: "badan usaha" → "PT" (pesan: "Aturan grup '…' hanya dapat diubah peran lintas PT.").
    assert "hanya dapat diubah peran lintas PT" in _detail(r)


async def test_U04_lihat_saja_tidak_bisa_ubah(klien, akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"settings": ["view"]}, label="Lihat Pengaturan")
    _, h = await _orang(akun, sesi, rid)
    r = await klien.put("/api/config/values", headers=h, json=_put("sales.allow_partial_shipment", True))
    assert r.status_code == 403, r.text
    assert "'Pusat Pengaturan'" in _detail(r)   # PR-T5 — modul pemilik `settings` (dulu modul gabungan)
    assert "settings.manage" not in _detail(r)
    r = await klien.get("/api/config/registry", headers=h)
    assert r.status_code == 200, r.text
    # PK-46 menambah lima kunci PPh 21 bertanggal; KF-T6 kunci kontrol.*; KF-T2 kunci retur & jadwal bayar antar-PT;
    # KP-T7 kunci pengingat & penjadwal; PK-36 kunci akun kontrol; KF-T7 nilai yang dulu ditulis mati; PK-37 kunci
    # periode tertutup mengunci dokumen; PK-38 kontrol dua orang bayar hutang; KP-T8 hidup/mati & model pengenal gambar;
    # PK-30 selisih panjang roll antar-PT; PM-T1 kontrol dua orang ubah rekening; AG-T1 masa berlaku kartu asisten;
    # TX-T1 tujuh kunci pajak (faktor, pembulatan, kode transaksi); PK-39 mode pemeriksaan anggaran; PK-26 porsi biaya
    # masuk roll yang sudah terjual; AG-T2 penyamaran nama pihak ke penyedia model; PK-24 kontrol dua orang
    # cairkan uang muka dan LPJ wajib berlampiran; PK-29 true-up persediaan hanya untuk saldo awal; PK-22
    # tanggal jurnal periodik.
    assert r.json()["total"] == 310 + 5 + KFT6_KUNCI + KFT2_KUNCI + KPT7_KUNCI + PK36_KUNCI + KFT7_KUNCI + PK37_KUNCI \
        + PK38_KUNCI + KPT8_KUNCI + PK30_KUNCI + PMT1_KUNCI + CRT1_KUNCI + AGT1_KUNCI + PMT2_KUNCI + TXT1_KUNCI \
        + PK39_KUNCI + PK26_KUNCI + AGT2_KUNCI + PK24_KUNCI + PK29_KUNCI + PK22_KUNCI


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
    # KF-T4 — id kelompok lama `pajak` kini alias kelompok "Pajak, pembukuan & antar-PT" (`GROUP_ALIASES`).
    assert _detail(r).startswith("Anda belum punya akses untuk melihat pengaturan “Pajak, pembukuan & antar-PT”")


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
    # KF-T4 — delapan layar kelompok (+ Semua pengaturan); `settings-cfg-documents` / `settings-cfg-notify` jadi alias.
    assert len(hitung) == 9
    for view, res in hitung.items():
        assert set(VIEW_RESOURCE_OVERRIDES.get(view, [])) == res, view
