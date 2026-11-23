"""KA-3 — aturan murni komisi per artikel: indeks tarif, aturan PT, potret, pengali harga, hitung baris.

Rancangan `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md`. Fungsi murni diuji tanpa DB; indeks tarif
dan simulator lewat database tiruan. Angka harapan = hitung tangan (komentar di tiap uji).
"""
from __future__ import annotations

import pytest

from services.commission_rules import (ALASAN_LABEL, ACUAN_FIELD, faktor_diskon, hitung_baris, label_alasan,
                                       muat_indeks_tarif, periksa_nilai, pengali_harga, pilih_jenjang, pilih_pita,
                                       pilih_tarif, potret, sumber_harga)

pytestmark = pytest.mark.anyio

PITA = [{"sampai_pct": 3, "pengali": 0.8}, {"sampai_pct": 10, "pengali": 0.5}, {"sampai_pct": None, "pengali": 0.0}]
SUMBER_BAWAAN = [{"sumber": s, "cara": "ikut_pita", "pengali": 1.0} for s in ("special_approval", "customer", "special_order")]


def _tarif(nilai, tingkat, lingkup, **extra):
    return {"id": f"{tingkat}_{nilai}", "per_unit_amount": nilai, "_lingkup": lingkup, **extra}


def _indeks(*pasangan):
    return {k: _tarif(n, k.split(":")[0], l) for k, n, l in pasangan}


IDX_KSC = _indeks(("kategori:Batik", 3000, "semua_pt"), ("artikel:tpl_ka_mega", 3500, "pt"),
                  ("varian:prd_ka_mega_bru", 4000, "pt"))
IDX_KANDA = _indeks(("kategori:Batik", 3000, "semua_pt"), ("artikel:tpl_ka_mega", 3200, "semua_pt"))


def _asal(t):
    return (t["per_unit_amount"], t["asal_tingkat"], t["asal_lingkup"])


def _aturan(basis="pricelist", acuan="daftar_pt", pita=PITA, sumber=None, tarif=3500, margin_cap=50, **diskon):
    """Aturan berbentuk potret (`items[].commission_rule`): isian diskon & batas margin ada di dalam `tarif`."""
    t = {"per_unit_amount": tarif, "margin_cap_pct": margin_cap, "discount_threshold_type": "pct",
         "discount_threshold": 10, "discount_mechanic": "tier_factor", "discount_factor": 0.5, "discount_potong_rp": 0}
    t.update(diskon)
    return {"price_basis": basis, "price_bands": pita, "price_source_rules": sumber or SUMBER_BAWAAN, "acuan": acuan,
            "tarif": t}


def _baris(bersih, qty=100, **lain):
    b = {"quantity": qty, "base_quantity": qty, "price": 50_000, "line_total": bersih * qty, "price_source": "global"}
    b.update(lain)
    return b


def test_KA3_U1_urutan_tarif():
    k = dict(template_id="tpl_ka_mega", category="Batik")
    assert _asal(pilih_tarif(IDX_KSC, product_id="prd_ka_mega_mrh", **k)) == (3500, "artikel", "pt")
    assert _asal(pilih_tarif(IDX_KSC, product_id="prd_ka_mega_bru", **k)) == (4000, "varian", "pt")
    assert _asal(pilih_tarif(IDX_KSC, product_id="prd_x", template_id="tpl_x", category="Batik")) == (3000, "kategori", "semua_pt")
    assert _asal(pilih_tarif(IDX_KANDA, product_id="prd_ka_mega_mrh", **k)) == (3200, "artikel", "semua_pt")
    assert pilih_tarif(IDX_KSC, product_id="p", template_id="", category="Lurik") is None
    # salinan: dokumen indeks tidak berubah
    assert "asal_tingkat" not in IDX_KSC["artikel:tpl_ka_mega"]


# Acuan daftar_pt = list_price 50.000. 49.000 → selisih 2% (≤3 → 0,8) · 48.500 → 3% tepat (batas termasuk → 0,8) ·
# 47.500 → 5% (≤10 → 0,5) · 44.000 → 12% (sisa → 0) · 51.000 → -2% → harga penuh.
@pytest.mark.parametrize("bersih,harap", [(50_000, (1.0, "harga_penuh")), (51_000, (1.0, "harga_penuh")),
                                          (49_000, (0.8, "pita")), (48_500, (0.8, "pita")),
                                          (47_500, (0.5, "pita")), (44_000, (0.0, "pita"))])
def test_KA3_U2_pita(bersih, harap):
    _, f, alasan, _ = pengali_harga(_aturan(), _baris(bersih, list_price=50_000))
    assert (f, alasan) == harap


def test_KA3_U2b_selisih_dibulatkan_dan_label():
    _, f, alasan, sel = pengali_harga(_aturan(), _baris(47_500, list_price=50_000))
    assert sel == 5.0
    assert label_alasan("pita", 2) == "2% di bawah harga acuan"
    assert label_alasan("pita", 2.5) == "2,5% di bawah harga acuan"
    assert label_alasan("pita", 2.456) == "2,46% di bawah harga acuan"
    assert label_alasan("harga_penuh", None) == ALASAN_LABEL["harga_penuh"]
    assert "{" not in label_alasan("pita", None)


def test_KA3_U3_sumber_tetap():
    sumber = [{"sumber": "special_approval", "cara": "pengali_tetap", "pengali": 0.5},
              {"sumber": "customer", "cara": "ikut_pita", "pengali": 1.0},
              {"sumber": "special_order", "cara": "pengali_tetap", "pengali": 0.7}]
    a = _aturan(sumber=sumber)
    # harga = acuan, tetap 0,5 karena asal harga persetujuan khusus
    assert pengali_harga(a, _baris(50_000, list_price=50_000, price_source="special_approval")) == (
        3500, 0.5, "sumber_tetap:special_approval", None)
    # special_order_price menang atas price_source global
    b = _baris(50_000, list_price=50_000, special_order_price=40_000)
    assert sumber_harga(b) == "special_order"
    assert pengali_harga(a, b)[1:3] == (0.7, "sumber_tetap:special_order")
    # 'customer' ikut pita: 49.000 → 0,8
    assert pengali_harga(a, _baris(49_000, list_price=50_000, price_source="customer"))[1:3] == (0.8, "pita")
    assert sumber_harga({"price_source": ""}) == "global" and sumber_harga({}) == "global"


def test_KA3_U4_tanpa_pembanding():
    assert pengali_harga(_aturan(), _baris(49_000, list_price=None)) == (3500, 1.0, "tanpa_pembanding", None)
    assert pengali_harga(_aturan(), _baris(49_000, list_price=0))[2] == "tanpa_pembanding"
    # R4: melewati ambang diskon → jalur diskon lama
    t, f, alasan, sel = pengali_harga(_aturan(), _baris(40_000, list_price=0, discount_percent=15))
    assert (t, f, alasan, sel) == (3500, 0.5, "diskon_lewat_ambang", None)


def test_KA3_U5_acuan_batas_bawah():
    assert ACUAN_FIELD == {"daftar_pt": "list_price", "umum": "global_price", "batas_bawah": "floor_price"}
    # floor 45.000, bersih 44.100 → selisih 2% → 0,8
    _, f, alasan, sel = pengali_harga(_aturan(acuan="batas_bawah"), _baris(44_100, floor_price=45_000, list_price=99_999))
    assert (f, alasan, sel) == (0.8, "pita", 2.0)
    assert pengali_harga(_aturan(acuan="umum"), _baris(49_000, global_price=50_000))[1] == 0.8


def test_KA3_U6_diskon_baris_sama_dengan_lama():
    cfg = {"discount_threshold_type": "pct", "discount_threshold": 10, "discount_mechanic": "tier_factor",
           "discount_factor": 0.5, "discount_potong_rp": 0}
    line = _baris(42_500, discount_percent=15)
    assert faktor_diskon(cfg, line, 3500) == (3500, 0.5)
    from services.sales_force_service import _discount_factor
    assert _discount_factor(cfg, line, 3500) == (3500, 0.5)
    a = _aturan(basis="diskon_baris")
    assert pengali_harga(a, line) == (3500, 0.5, "diskon_lewat_ambang", None)
    assert pengali_harga(a, _baris(50_000, discount_percent=5)) == (3500, 1.0, "diskon_baris", None)
    # potong_rp mengubah tarif efektif
    a2 = _aturan(basis="diskon_baris", discount_mechanic="potong_rp", discount_potong_rp=500)
    assert pengali_harga(a2, line) == (3000, 1.0, "diskon_lewat_ambang", None)


def test_KA3_U7_hitung_baris():
    # dasar 100, fraksi 0,5 → qty 50; tarif 3.500; pita 0,8 (49.000 vs 50.000); capaian 1,1; biaya 35.000 → margin 14.000/dasar.
    # kotor = 50 × 3.500 × 0,8 × 1,1 = 154.000; batas 50% × 50 × 14.000 = 350.000 → 154.000 tanpa batas.
    line = _baris(49_000, list_price=50_000)
    kw = dict(fraksi=0.5, bobot=1.0, biaya=35_000, biaya_diketahui=True, pengali_capaian=1.1)
    h = hitung_baris(_aturan(), line, **kw)
    assert (h["komisi"], h["dibatasi"]) == (154_000, False)
    assert (h["tarif"], h["pengali_harga"], h["alasan_harga"], h["pengali_capaian"]) == (3500, 0.8, "pita", 1.1)
    assert h["qty_dasar_terbayar"] == 50 and h["komisi_penuh"] == 308_000
    # batas 10% × 50 × 14.000 = 70.000 → dibatasi
    a10 = _aturan(margin_cap=10)
    h10 = hitung_baris(a10, line, **kw)
    assert (h10["komisi"], h10["dibatasi"]) == (70_000, True)
    # komisi_penuh = fraksi 1 → batas 140.000, kotor 308.000
    assert h10["komisi_penuh"] == 140_000
    # bobot 0,5 → separuh; biaya tak diketahui → tanpa batas walau batas 10%
    h2 = hitung_baris(a10, line, **{**kw, "bobot": 0.5, "biaya_diketahui": False})
    assert (h2["komisi"], h2["dibatasi"]) == (77_000, False)


def test_KA3_U8_pilih_jenjang():
    j = [{"capaian_min_pct": 0, "pengali": 0.5}, {"capaian_min_pct": 80, "pengali": 1.0}, {"capaian_min_pct": 100, "pengali": 1.2}]
    assert [pilih_jenjang(j, p) for p in (0, 79.9, 80, 99.9, 100, 250)] == [0.5, 0.5, 1.0, 1.0, 1.2, 1.2]


def test_KA3_U8b_pilih_pita_sisa():
    assert [pilih_pita(PITA, s) for s in (0.5, 3, 3.01, 10, 10.01, 90)] == [0.8, 0.8, 0.5, 0.5, 0.0, 0.0]


def test_KA3_U10_potret_bentuk_v1():
    pt = {"price_basis": "pricelist", "acuan": "daftar_pt", "price_bands": PITA, "price_source_rules": SUMBER_BAWAAN,
          "discount_threshold_type": "pct", "discount_threshold": 10, "discount_mechanic": "tier_factor",
          "discount_factor": 0.5, "discount_potong_rp": 0, "default_margin_cap_pct": 50}
    tarif = {"id": "ir1", "per_unit_amount": 3500, "margin_cap_pct": None, "discount_threshold": None,
             "asal_tingkat": "artikel", "asal_lingkup": "pt", "price_bands": [{"sampai_pct": None, "pengali": 1.0}],
             "price_source_rules": None}
    p = potret(tarif, pt, artikel={"id": "tpl_ka_mega", "nama": "Batik Mega", "kode": "BTK-MEGA"},
               sumber="pesanan", waktu="2026-11-23T00:00:00+00:00")
    assert (p["v"], p["sumber"], p["dipotret_pada"]) == (1, "pesanan", "2026-11-23T00:00:00+00:00")
    assert p["artikel"]["kode"] == "BTK-MEGA"
    # kosong → nilai PT; pita artikel (bukan None) menggantikan PT; aturan sumber None → PT
    assert p["tarif"]["margin_cap_pct"] == 50 and p["tarif"]["discount_threshold"] == 10
    assert p["tarif"]["asal_tingkat"] == "artikel" and p["tarif"]["id"] == "ir1"
    assert p["price_bands"] == [{"sampai_pct": None, "pengali": 1.0}] and p["price_source_rules"] == SUMBER_BAWAAN
    assert (p["price_basis"], p["acuan"]) == ("pricelist", "daftar_pt")
    kosong = potret(None, pt, artikel=None, sumber="saat_hitung", waktu="x")
    assert kosong["tarif"] is None and kosong["artikel"] is None


async def test_KA3_U11_indeks_tarif(klien, kepala_admin, db):
    from core_utils import now_iso
    baris = [("all", "kategori:KA3Kat", 3000, {"category": "KA3Kat"}),
             ("ent_ksc", "artikel:tpl_ka3", 3500, {"template_id": "tpl_ka3", "category": "KA3Kat"}),
             ("all", "artikel:tpl_ka3", 3200, {"template_id": "tpl_ka3", "category": "KA3Kat"}),
             ("ent_kanda", "kategori:KA3Kat", 2900, {"category": "KA3Kat"})]
    for i, (ent, rk, n, extra) in enumerate(baris):
        await db.incentive_rates.insert_one({"id": f"irate_ka3_{i}", "entity_id": ent, "rate_key": rk, "per_unit_amount": n,
                                             "status": "active", "created_at": now_iso(), **extra})
    await db.incentive_rates.insert_one({"id": "irate_ka3_off", "entity_id": "ent_ksc", "rate_key": "kategori:KA3Mati",
                                         "category": "KA3Mati", "per_unit_amount": 1, "status": "inactive"})
    await db.incentive_rates.insert_one({"id": "irate_ka3_lama", "entity_id": "all", "category": "KA3Lama",
                                         "per_unit_amount": 777, "status": "active"})   # tanpa rate_key
    ksc = await muat_indeks_tarif("ent_ksc")
    assert (ksc["artikel:tpl_ka3"]["per_unit_amount"], ksc["artikel:tpl_ka3"]["_lingkup"]) == (3500, "pt")
    assert (ksc["kategori:KA3Kat"]["per_unit_amount"], ksc["kategori:KA3Kat"]["_lingkup"]) == (3000, "semua_pt")
    assert "kategori:KA3Mati" not in ksc and ksc["kategori:KA3Lama"]["per_unit_amount"] == 777
    semua = await muat_indeks_tarif("all")
    assert semua["artikel:tpl_ka3"]["per_unit_amount"] == 3200
    assert semua["kategori:KA3Kat"]["per_unit_amount"] == 3000 and (await muat_indeks_tarif(None)) == semua


async def test_KA3_U12_aturan_pt_ada_semua_kunci(klien, kepala_admin):
    from services.commission_rules import aturan_pt
    a = await aturan_pt("ent_ksc", {"commission.price_basis": "pricelist"})
    assert a["price_basis"] == "pricelist" and a["default_margin_cap_pct"] is not None


async def test_KA3_U9_simulator(klien, kepala_admin):
    ov = {"commission.price_basis": "pricelist", "commission.price_bands": PITA}
    r = await klien.post("/api/config/simulate", headers=kepala_admin,
                         json={"key": "commission.price_bands", "ctx": {"entity_id": "ent_ksc"}, "overrides": ov,
                               "sample": {"list_price": 50_000, "net_price": 49_000, "per_unit": 3500, "quantity": 100}})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["simulator"] == "commission_price"
    # selisih 2% → pengali 0,8 → 100 × 3.500 × 0,8 = 280.000
    assert any("0,8" in s["value"] for s in j["steps"]), j
    assert "280.000" in j["result"], j
    r = await klien.post("/api/config/simulate", headers=kepala_admin,
                         json={"key": "commission.achievement_tiers",
                               "overrides": {"commission.achievement_tiers": [
                                   {"capaian_min_pct": 0, "pengali": 0.5}, {"capaian_min_pct": 80, "pengali": 1.0}]},
                               "sample": {"achievement": 85, "commission": 1_000_000}})
    assert r.status_code == 200, r.text
    assert r.json()["simulator"] == "commission_achievement" and "1.000.000" in r.json()["result"]


def test_KA3_U13_angka_tak_hingga_ditolak():
    for buruk in ("nan", "inf", "-inf", float("nan"), float("inf")):
        with pytest.raises(ValueError):
            periksa_nilai("commission.price_bands", [{"sampai_pct": None, "pengali": buruk}])


def test_KA3_U14_pesan_sumber_tak_dikenal_tanpa_kode_mentah():
    with pytest.raises(ValueError) as e:
        periksa_nilai("commission.price_source_rules", [{"sumber": "entity", "cara": "ikut_pita", "pengali": 1}])
    msg = str(e.value)
    assert "entity" not in msg and "Harga khusus, Harga pelanggan, Pesanan khusus" in msg
    assert "special_approval" not in msg


@pytest.mark.parametrize("kosong", [None, ""])
async def test_KA3_U15_pita_terbuka_tersimpan_dinormalisasi(klien, kepala_admin, kosong):
    nilai = [{"sampai_pct": "5", "pengali": "0.9"}, {"sampai_pct": kosong, "pengali": 0}]
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json={"items": [{"key": "commission.price_bands", "value": nilai, "scope_type": "global",
                                         "reason": "uji KA-3"}]})
    assert r.status_code == 200, r.text
    from services.config_resolver import value_of
    assert await value_of("commission.price_bands", {}) == [{"sampai_pct": 5.0, "pengali": 0.9},
                                                            {"sampai_pct": None, "pengali": 0.0}]
    await klien.put("/api/config/values", headers=kepala_admin,
                    json={"items": [{"key": "commission.price_bands", "value": [{"sampai_pct": None, "pengali": 1.0}],
                                     "scope_type": "global", "reason": "pulihkan"}]})
