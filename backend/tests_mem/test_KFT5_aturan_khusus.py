"""KF-T5 — aturan khusus per pelanggan dan per barang punya layar (docs/blueprint/unit/KF-T5.md, U1–U13).

Fixture (DISISIP langsung ke database): pelanggan `C1`, `C2` (PT `ent_ksc`) dan `C3` (PT `ent_kanda`); barang `P1`, `P2`;
roll `R1` (barang `P1`) dan `R2` (barang `P2`), sisa masing-masing 4. Nilai PT dan grup = bawaan registry
(`payment.variance_overpay_default` "deposit" · `payment.variance_tolerance_rupiah` Rp5.000 · `payment.penalty_mode`
"draft" · `cutting.waste_limit_pct` 3 % · `cutting.remnant_threshold` 2).

CR-T4 — lima kunci denda (`ar.denda_rate_pct_per_month`, `ar.grace_days`, `payment.penalty_mode`/`_base`/`_cap_pct`)
tidak lagi berlapis pelanggan (aturan denda satu pelanggan = profil kredit, `test_CRT4_denda_berlapis.py`): U1, U2, U4,
U9, U11, U12 yang dulu memakai `ar.grace_days`/`payment.penalty_mode` kini memakai kunci selisih bayar yang tetap
berlapis pelanggan, dan U1/U4 menegaskan lapisan pelanggan kunci denda ditolak 400. Penulisan aturan khusus dijalankan lewat API
(`PUT /api/config/values`, `POST /api/config/values/clear`) sebagai Admin seed; pembacaan mesin lewat fungsi pemakainya.
Satu database per modul: uji berjalan berurutan (U2 memakai hasil U1, U12 mengulang U1).
"""
from __future__ import annotations

import pytest

import config_registry as registry
from pembantu import jumlah
from services.ar_aging_service import get_ar_config
from services.config_service import get_allocation_policy
from services.payment_variance_service import variance_policy
from services.penalty_service import penalty_policy
from services.roll_service import apply_remnant_rule, cut_waste_limit_pct

pytestmark = pytest.mark.anyio

C1, C2, C3 = "cus_kft5_c1", "cus_kft5_c2", "cus_kft5_c3"
P1, P2 = "prd_kft5_p1", "prd_kft5_p2"
R1, R2 = "roll_kft5_r1", "roll_kft5_r2"
NAMA = {C1: "Toko Aturan Satu", C2: "Toko Aturan Dua", C3: "Toko Kanda Tiga", P1: "Kain Aturan P1", P2: "Kain Aturan P2"}
KUNCI_PELANGGAN = {"payment.variance_tolerance_rupiah", "payment.variance_underpay_default",
                   "payment.variance_overpay_default"}
#: CR-T4 — kunci denda tanpa lapisan pelanggan (aturan satu pelanggan di profil kreditnya).
KUNCI_DENDA = {"ar.denda_rate_pct_per_month", "ar.grace_days", "payment.penalty_mode", "payment.penalty_base",
               "payment.penalty_cap_pct"}
KUNCI_BARANG = {"cutting.remnant_threshold", "cutting.remnant_grade", "cutting.waste_limit_pct"}
# PR-T5 — modul gabungan "Pengaturan, Pengguna & Hak Akses" dipecah; pemilik `settings` = modul "Pusat Pengaturan".
B1 = "Anda belum punya akses untuk melihat pengaturan. Minta Admin menambahkan akses 'Pusat Pengaturan'."
PESAN_U_GRACE = ("Anda belum punya akses untuk mengubah pengaturan “Masa tenggang sebelum denda”. Minta Admin "
                 "menambahkan akses 'Pusat Pengaturan'.")


@pytest.fixture(scope="module", autouse=True)
async def uji(db):
    await db.customers.insert_many([
        {"id": C1, "code": "KFT5-C1", "name": NAMA[C1], "entity_id": "ent_ksc", "status": "active"},
        {"id": C2, "code": "KFT5-C2", "name": NAMA[C2], "entity_id": "ent_ksc", "status": "active"},
        {"id": C3, "code": "KFT5-C3", "name": NAMA[C3], "entity_id": "ent_kanda", "status": "active"}])
    await db.products.insert_many([
        {"id": P1, "sku": "KFT5-P1", "name": NAMA[P1], "base_unit": "meter", "status": "active"},
        {"id": P2, "sku": "KFT5-P2", "name": NAMA[P2], "base_unit": "meter", "status": "active"}])
    await db.inventory_rolls.insert_many([
        {"id": R1, "product_id": P1, "owner_entity_id": "ent_ksc", "length_remaining": 4.0, "grade": "A",
         "is_remnant": False, "status": "available"},
        {"id": R2, "product_id": P2, "owner_entity_id": "ent_ksc", "length_remaining": 4.0, "grade": "A",
         "is_remnant": False, "status": "available"}])


def _isi(key, value, scope_type, scope_id, reason="uji KF-T5"):
    return {"items": [{"key": key, "value": value, "scope_type": scope_type, "scope_id": scope_id, "reason": reason}]}


def _detail(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


async def _baris_cfg() -> int:
    return await jumlah("config_values", {})


async def test_KFT5_U1_aturan_khusus_pelanggan_terbaca_mesin(klien, kepala_admin):
    # Masukan: perlakuan lebih bayar C1 = "refund" (lapisan pelanggan). Langkah: variance_policy per pelanggan.
    # Hasil: C1 → refund (lapisan pelanggan menang); C2 → deposit (bawaan registry, tanpa lapisan pelanggan).
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json=_isi("payment.variance_overpay_default", "refund", "customer", C1))
    assert r.status_code == 200, r.text
    assert (await variance_policy("ent_ksc", C1))["overpay_default"] == "refund"
    assert (await variance_policy("ent_ksc", C2))["overpay_default"] == "deposit"
    # CR-T4 — masa tenggang denda per pelanggan tidak lagi lewat Pusat Pengaturan (profil kredit): 400, mesin tetap 0.
    sebelum = await _baris_cfg()
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi("ar.grace_days", 10, "customer", C1))
    assert r.status_code == 400, r.text
    assert _detail(r) == "“Masa tenggang sebelum denda” tidak bisa dibedakan per pelanggan."
    assert await _baris_cfg() == sebelum
    assert (await get_ar_config("ent_ksc", C1))["grace_days"] == 0
    assert (await penalty_policy("ent_ksc", C1))["grace_days"] == 0


async def test_KFT5_U2_kembali_ikut_aturan_pt(klien, kepala_admin):
    r = await klien.post("/api/config/values/clear", headers=kepala_admin,
                         json={"key": "payment.variance_overpay_default", "scope_type": "customer", "scope_id": C1,
                               "reason": "uji KF-T5"})
    assert r.status_code == 200, r.text
    assert (await variance_policy("ent_ksc", C1))["overpay_default"] == "deposit"


async def test_KFT5_U3_toleransi_selisih_bayar_per_pelanggan(klien, kepala_admin):
    # Masukan: toleransi C1 = Rp20.000; bawaan Rp5.000. C3 di ent_kanda tanpa lapisan pelanggan → tetap Rp5.000.
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json=_isi("payment.variance_tolerance_rupiah", 20000, "customer", C1))
    assert r.status_code == 200, r.text
    assert (await variance_policy("ent_ksc", C1))["tolerance"] == 20000.0
    assert (await variance_policy("ent_ksc", C2))["tolerance"] == 5000.0
    assert (await variance_policy("ent_kanda", C3))["tolerance"] == 5000.0


async def test_KFT5_U4_perlakuan_denda_per_pelanggan(klien, kepala_admin):
    # CR-T4 — perlakuan denda per pelanggan pindah ke profil kredit (bebas denda beralasan & bertanggal); lapisan
    # pelanggan Pusat Pengaturan ditolak dan mesin tetap memakai aturan PT.
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi("payment.penalty_mode", "off", "customer", C1))
    assert r.status_code == 400, r.text
    assert _detail(r) == "“Denda telat: usulan atau langsung terbit” tidak bisa dibedakan per pelanggan."
    assert (await penalty_policy("ent_ksc", C1))["mode"] == "draft"
    assert (await penalty_policy("ent_ksc", C2))["mode"] == "draft"


async def test_KFT5_U5_batas_susut_potong_per_barang(klien, kepala_admin):
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi("cutting.waste_limit_pct", 7, "product", P1))
    assert r.status_code == 200, r.text
    assert await cut_waste_limit_pct(P1, "ent_ksc") == 7.0
    assert await cut_waste_limit_pct(P2, "ent_ksc") == 3.0


async def test_KFT5_U6_ambang_sisa_potong_per_barang(klien, kepala_admin):
    # Masukan: ambang P1 = 5, P2 = bawaan 2; sisa R1 = R2 = 4. Hasil: R1 4 < 5 → sisa; R2 4 ≥ 2 → bukan sisa.
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi("cutting.remnant_threshold", 5, "product", P1))
    assert r.status_code == 200, r.text
    assert (await apply_remnant_rule(R1, P1, "ent_ksc"))["is_remnant"] is True
    assert (await apply_remnant_rule(R2, P2, "ent_ksc"))["is_remnant"] is False


async def test_KFT5_U7_kebijakan_lot_tidak_lagi_per_pelanggan(klien, kepala_admin):
    sebelum = await _baris_cfg()
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json=_isi("allocation.lot_mode", "strict_single", "customer", C1))
    assert r.status_code == 400, r.text
    assert _detail(r) == "“Kebijakan campur lot” tidak bisa dibedakan per pelanggan."
    assert await _baris_cfg() == sebelum
    # Isian kartu pelanggan (Kebijakan lot) tetap menang.
    pol = await get_allocation_policy("ent_ksc", {"id": C1, "lot_policy": "strict_single"})
    assert pol["lot_mode"] == "strict_single"


async def test_KFT5_U8_sasaran_harus_ada(klien, kepala_admin):
    sebelum = await _baris_cfg()
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json=_isi("payment.variance_tolerance_rupiah", 5000, "customer", "tidak_ada"))
    assert r.status_code == 404, r.text
    assert _detail(r) == "Pelanggan tidak ditemukan."
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json=_isi("cutting.waste_limit_pct", 5, "product", "tidak_ada"))
    assert r.status_code == 404, r.text
    assert _detail(r) == "Barang tidak ditemukan."
    assert await _baris_cfg() == sebelum


async def test_KFT5_U9_pelanggan_pt_lain_di_luar_cakupan(klien, akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"settings": ["view", "manage"]}, label="Kelola Pengaturan KF-T5")
    u = await akun(rid, entitas=("ent_ksc",))
    h = await sesi(u)
    sebelum = await _baris_cfg()
    r = await klien.put("/api/config/values", headers=h,
                        json=_isi("payment.variance_overpay_default", "refund", "customer", C3))
    assert r.status_code == 403, r.text
    assert _detail(r) == "Tidak berwenang atas entitas ini"
    assert await _baris_cfg() == sebelum
    # Pembanding: pelanggan PT sendiri boleh (lalu dicabut lagi supaya uji lain tetap memakai bawaan).
    r = await klien.put("/api/config/values", headers=h,
                        json=_isi("payment.variance_overpay_default", "refund", "customer", C2))
    assert r.status_code == 200, r.text
    r = await klien.post("/api/config/values/clear", headers=h,
                         json={"key": "payment.variance_overpay_default", "scope_type": "customer", "scope_id": C2,
                               "reason": "uji"})
    assert r.status_code == 200, r.text


async def test_KFT5_U10_izin_pelanggan_saja_tidak_cukup(klien, akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"customer": ["view", "update"]}, label="Ubah Pelanggan KF-T5")
    h = await sesi(await akun(rid, entitas=("ent_ksc",)))
    r = await klien.put("/api/config/values", headers=h, json=_isi("ar.grace_days", 5, "customer", C1))
    assert r.status_code == 403, r.text
    assert _detail(r) == PESAN_U_GRACE
    r = await klien.get("/api/config/effective", headers=h, params={"scope": "customer", "customer_id": C1})
    assert r.status_code == 403, r.text
    assert _detail(r) == B1


async def test_KFT5_U11_nilai_efektif_per_lapisan(klien, kepala_admin):
    r = await klien.get("/api/config/effective", headers=kepala_admin,
                        params={"scope": "customer", "customer_id": C1, "entity_id": "ent_ksc"})
    assert r.status_code == 200, r.text
    items = {it["key"]: it for it in r.json()["items"]}
    assert len(items) == 3 and set(items) == KUNCI_PELANGGAN
    assert all("layer_value" in it and "inherited_value" in it for it in items.values())
    # U2 mencabut perlakuan lebih bayar C1 → tidak punya nilai sendiri; U3 mengisi toleransi C1 = 20.000 (PT: 5.000).
    assert items["payment.variance_overpay_default"]["layer_value"] is None
    assert items["payment.variance_overpay_default"]["inherited_value"] == "deposit"
    assert items["payment.variance_tolerance_rupiah"]["layer_value"] == 20000
    assert items["payment.variance_tolerance_rupiah"]["inherited_value"] == 5000
    r = await klien.get("/api/config/effective", headers=kepala_admin, params={"scope": "product", "product_id": P1})
    assert r.status_code == 200, r.text
    items = {it["key"]: it for it in r.json()["items"]}
    assert len(items) == 3 and set(items) == KUNCI_BARANG
    assert all("layer_value" in it and "inherited_value" in it for it in items.values())
    assert items["cutting.waste_limit_pct"]["layer_value"] == 7 and items["cutting.waste_limit_pct"]["inherited_value"] == 3.0


async def test_KFT5_U12_daftar_pelanggan_beraturan_khusus(klien, kepala_admin):
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json=_isi("payment.variance_overpay_default", "allocate", "customer", C1))
    assert r.status_code == 200, r.text
    r = await klien.get("/api/config/layers", headers=kepala_admin,
                        params={"key": "payment.variance_overpay_default", "scope_type": "customer"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["total"] == 1, j
    assert j["rows"][0]["scope_id"] == C1
    assert j["rows"][0]["scope_label"] == NAMA[C1]
    assert j["rows"][0]["value"] == "allocate"


async def test_KFT5_U13_registry_lapisan_pelanggan_dan_barang():
    pel = {e["key"] for e in registry.all_entries() if "customer" in e["scopes"]}
    brg = {e["key"] for e in registry.all_entries() if "product" in e["scopes"]}
    assert pel == KUNCI_PELANGGAN
    assert brg == KUNCI_BARANG
    assert not [e["key"] for e in registry.all_entries() if {"supplier", "document"} & set(e["scopes"])]
    # Teks bantuan: kunci berlapis menyebut kartu tempat mengaturnya; dua kunci lot menunjuk isian kartu pelanggan.
    for k in KUNCI_PELANGGAN:
        assert "Bisa dibedakan per pelanggan dari kartu pelanggan." in registry.require(k)["help"], k
    for k in KUNCI_DENDA:   # CR-T4 — global → PT; aturan satu pelanggan di kartu pelanggan › Kredit › Aturan denda
        assert registry.require(k)["scopes"] == ["global", "entity"], k
        assert "Untuk pelanggan tertentu, atur di kartu pelanggan (Aturan denda)." in registry.require(k)["help"], k
    for k in KUNCI_BARANG:
        h = registry.require(k)["help"]
        assert "Bisa dibedakan per barang dari kartu barang." in h, k
        assert "lapisan" not in h and "kategori" not in h, k
    for k in ("allocation.lot_mode", "allocation.dye_lot_strict"):
        assert registry.require(k)["scopes"] == ["global", "entity"], k
        assert "Untuk pelanggan tertentu, atur di kartu pelanggan (Kebijakan lot)." in registry.require(k)["help"], k


# ── Tambahan (bukan baris spesifikasi): batas jalur baru ────────────────────────
async def test_KFT5_tambahan_lapisan_pemasok_dokumen_belum_tersedia(klien, kepala_admin):
    sebelum = await _baris_cfg()
    for lapisan in ("supplier", "document"):
        r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi("ar.grace_days", 5, lapisan, "x"))
        assert r.status_code == 400, r.text
        assert _detail(r) == "Aturan khusus per pemasok atau per dokumen belum tersedia."
    r = await klien.get("/api/config/layers", headers=kepala_admin, params={"key": "ar.grace_days", "scope_type": "supplier"})
    assert r.status_code == 400, r.text
    assert await _baris_cfg() == sebelum


async def test_KFT5_tambahan_daftar_tidak_menghitung_nisan(klien, kepala_admin):
    # P1 punya batas susut 7 (U5). Sesudah dicabut, daftar barang beraturan khusus untuk kunci itu kosong.
    r = await klien.get("/api/config/layers", headers=kepala_admin,
                        params={"key": "cutting.waste_limit_pct", "scope_type": "product"})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 1 and r.json()["rows"][0]["scope_label"] == NAMA[P1]
    r = await klien.post("/api/config/values/clear", headers=kepala_admin,
                         json={"key": "cutting.waste_limit_pct", "scope_type": "product", "scope_id": P1, "reason": "uji"})
    assert r.status_code == 200, r.text
    r = await klien.get("/api/config/layers", headers=kepala_admin,
                        params={"key": "cutting.waste_limit_pct", "scope_type": "product"})
    assert r.status_code == 200, r.text
    assert r.json() == {"rows": [], "total": 0}
    r = await klien.get("/api/config/layers", headers=kepala_admin, params={"key": "tidak.ada", "scope_type": "product"})
    assert r.status_code == 404, r.text


async def test_KFT5_tambahan_baca_pelanggan_pt_lain_ditolak(klien, akun, sesi, peran_tanpa_acuan, kepala_admin):
    rid = await peran_tanpa_acuan({"settings": ["view"]}, label="Lihat Pengaturan KF-T5")
    h = await sesi(await akun(rid, entitas=("ent_ksc",)))
    r = await klien.get("/api/config/effective", headers=h, params={"scope": "customer", "customer_id": C3})
    assert r.status_code == 403, r.text
    r = await klien.get("/api/config/effective", headers=h, params={"scope": "customer", "customer_id": C1})
    assert r.status_code == 200, r.text
    items = {it["key"]: it for it in r.json()["items"]}
    assert items["payment.variance_tolerance_rupiah"]["layer_value"] == 20000
    # Tanpa `entity_id`: aturan PT = aturan PT pelanggan itu (ent_ksc) → bawaan 5.000.
    assert items["payment.variance_tolerance_rupiah"]["inherited_value"] == 5000
    assert r.json()["context"]["entity_id"] == "ent_ksc"
    assert all(it["can_edit"] is False for it in items.values())
    # Daftar Pusat Pengaturan: pelanggan PT di luar cakupan pembaca tidak ikut terhitung.
    key = "payment.variance_tolerance_rupiah"
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi(key, 15000, "customer", C3))
    assert r.status_code == 200, r.text
    try:
        r = await klien.get("/api/config/layers", headers=kepala_admin, params={"key": key, "scope_type": "customer"})
        assert sorted(x["scope_id"] for x in r.json()["rows"]) == sorted([C1, C3])
        r = await klien.get("/api/config/layers", headers=h, params={"key": key, "scope_type": "customer"})
        assert r.status_code == 200, r.text
        assert [x["scope_id"] for x in r.json()["rows"]] == [C1] and r.json()["total"] == 1
    finally:
        await klien.post("/api/config/values/clear", headers=kepala_admin,
                         json={"key": key, "scope_type": "customer", "scope_id": C3, "reason": "uji"})


async def test_KFT5_tambahan_riwayat_menyebut_nama_bukan_id(klien, kepala_admin):
    r = await klien.get("/api/config/history", headers=kepala_admin, params={"key": "payment.variance_overpay_default"})
    assert r.status_code == 200, r.text
    baris = [x for x in r.json()["rows"] if x["scope_type"] == "customer" and x["scope_id"] == C1]
    assert baris and all(x["scope_label"] == NAMA[C1] for x in baris)
    r = await klien.get("/api/config/history", headers=kepala_admin, params={"key": "cutting.waste_limit_pct"})
    assert all(x["scope_label"] == NAMA[P1] for x in r.json()["rows"] if x["scope_type"] == "product")
