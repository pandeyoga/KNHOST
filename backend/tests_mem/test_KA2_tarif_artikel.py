"""KA-2 — tarif komisi per artikel dan pengecualian per varian (data + API `incentive_rates`).

Spesifikasi: docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md. Fixture DISISIP langsung: artikel
`tpl_ka_mega` ("Batik Mega", `sku_prefix` BTK-MEGA, kategori Batik) dengan dua varian `prd_ka_mega_mrh` / `prd_ka_mega_bru`.
Kunci tarif: `kategori:<kategori>` · `artikel:<id artikel>` · `varian:<id varian>`; unik per (PT, kunci).
"""
from __future__ import annotations

import pytest

import bootstrap
from core_utils import now_iso
from indexes import REQUIRED_UNIQUE_INDEXES

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"


@pytest.fixture(scope="module")
async def uji(db):
    await db.product_templates.insert_one({
        "id": "tpl_ka_mega", "name": "Batik Mega", "category": "Batik", "sku_prefix": "BTK-MEGA", "status": "active",
        "created_at": now_iso()})
    await db.products.insert_many([
        {"id": pid, "sku": sku, "name": nama, "category": "Batik", "template_id": "tpl_ka_mega", "base_unit": "meter",
         "status": "active", "created_at": now_iso()}
        for pid, sku, nama in (("prd_ka_mega_mrh", "BTK-MEGA-MRH", "Batik Mega Merah"),
                               ("prd_ka_mega_bru", "BTK-MEGA-BRU", "Batik Mega Biru"))])
    return True


async def test_KA2_U1_tarif_artikel(klien, kepala_admin, uji):
    r = await klien.post("/api/incentive-rates", headers=kepala_admin,
                         json={"entity_id": KSC, "template_id": "tpl_ka_mega", "category": "salah", "per_unit_amount": 3500})
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["rate_key"], j["category"], j["target_name"], j["target_code"]) == (
        "artikel:tpl_ka_mega", "Batik", "Batik Mega", "BTK-MEGA")
    assert j["price_bands"] is None and j["price_source_rules"] is None


async def test_KA2_U2_kembar_409_dan_dua_kunci_400(klien, kepala_admin, uji):
    r = await klien.post("/api/incentive-rates", headers=kepala_admin,
                         json={"entity_id": KSC, "template_id": "tpl_ka_mega", "per_unit_amount": 1})
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "Tarif untuk Batik Mega di PT ini sudah ada."
    r = await klien.post("/api/incentive-rates", headers=kepala_admin,
                         json={"entity_id": KSC, "template_id": "tpl_ka_mega", "product_id": "prd_ka_mega_mrh"})
    assert (r.status_code, r.json()["detail"]) == (400, "Pilih artikel atau varian, bukan keduanya.")
    r = await klien.post("/api/incentive-rates", headers=kepala_admin, json={"entity_id": KSC, "template_id": "tpl_tak_ada"})
    assert (r.status_code, r.json()["detail"]) == (400, "Artikel tidak ditemukan.")
    r = await klien.post("/api/incentive-rates", headers=kepala_admin, json={"entity_id": KSC, "product_id": "prd_tak_ada"})
    assert (r.status_code, r.json()["detail"]) == (400, "Varian tidak ditemukan.")
    r = await klien.post("/api/incentive-rates", headers=kepala_admin, json={"entity_id": KSC})
    assert (r.status_code, r.json()["detail"]) == (400, "Kategori wajib diisi")
    # baris kategori tetap jalan; kembar kategori → 409 dengan nama kategori
    r = await klien.post("/api/incentive-rates", headers=kepala_admin,
                         json={"entity_id": KSC, "category": "KA2Kat", "per_unit_amount": 100})
    assert r.status_code == 200 and r.json()["rate_key"] == "kategori:KA2Kat", r.text
    r = await klien.post("/api/incentive-rates", headers=kepala_admin, json={"entity_id": KSC, "category": "KA2Kat"})
    assert (r.status_code, r.json()["detail"]) == (409, "Tarif untuk KA2Kat di PT ini sudah ada.")


async def test_KA2_U3_pengecualian_varian(klien, kepala_admin, db, uji):
    r = await klien.post("/api/incentive-rates", headers=kepala_admin,
                         json={"entity_id": KSC, "product_id": "prd_ka_mega_bru", "category": "x", "per_unit_amount": 0})
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["rate_key"], j["category"], j["target_name"], j["target_code"]) == (
        "varian:prd_ka_mega_bru", "Batik", "Batik Mega Biru", "BTK-MEGA-BRU")
    # PATCH ganti varian → kunci & nama potret dihitung ulang
    r = await klien.patch(f"/api/incentive-rates/{j['id']}", headers=kepala_admin,
                          json={"data": {"product_id": "prd_ka_mega_mrh"}})
    assert r.status_code == 200, r.text
    assert (r.json()["rate_key"], r.json()["target_name"]) == ("varian:prd_ka_mega_mrh", "Batik Mega Merah")
    # PATCH ke kunci yang sudah dipakai → 409
    r2 = await klien.post("/api/incentive-rates", headers=kepala_admin,
                          json={"entity_id": KSC, "product_id": "prd_ka_mega_bru"})
    assert r2.status_code == 200, r2.text
    r = await klien.patch(f"/api/incentive-rates/{r2.json()['id']}", headers=kepala_admin,
                          json={"data": {"product_id": "prd_ka_mega_mrh"}})
    assert r.status_code == 409, r.text


async def test_KA2_U4_pita_khusus_artikel_divalidasi(klien, kepala_admin, uji):
    r = await klien.post("/api/incentive-rates", headers=kepala_admin,
                         json={"entity_id": "all", "template_id": "tpl_ka_mega", "price_bands": []})
    assert r.status_code == 400, r.text
    ok = [{"sampai_pct": 5, "pengali": 1}, {"sampai_pct": None, "pengali": 0.5}]
    r = await klien.post("/api/incentive-rates", headers=kepala_admin,
                         json={"entity_id": "all", "template_id": "tpl_ka_mega", "price_bands": ok})
    assert r.status_code == 200, r.text
    assert r.json()["price_bands"] == ok
    rid = r.json()["id"]
    r = await klien.patch(f"/api/incentive-rates/{rid}", headers=kepala_admin, json={"data": {"price_bands": []}})
    assert r.status_code == 400, r.text
    r = await klien.patch(f"/api/incentive-rates/{rid}", headers=kepala_admin, json={"data": {"price_bands": None}})
    assert r.status_code == 200 and r.json()["price_bands"] is None, r.text


async def test_KA2_U5_isi_awal_rate_key(db):
    await db.incentive_rates.insert_one({"id": "irate_ka_lama", "entity_id": "all", "category": "TenunLama",
                                         "per_unit_amount": 2500, "status": "active"})
    await bootstrap.backfill_incentive_rate_key()
    assert (await db.incentive_rates.find_one({"id": "irate_ka_lama"}))["rate_key"] == "kategori:TenunLama"
    await bootstrap.backfill_incentive_rate_key()   # idempoten
    assert (await db.incentive_rates.find_one({"id": "irate_ka_lama"}))["rate_key"] == "kategori:TenunLama"


def test_KA2_U6_indeks_wajib_terdaftar():
    assert any(i["name"] == "uq_incentive_rate_key" and i["collection"] == "incentive_rates"
               for i in REQUIRED_UNIQUE_INDEXES)


async def test_KA2_U7_mesin_lama_tidak_tertimpa_tarif_artikel(db):
    """Tarif kategori 500 + tarif artikel 900 (kategori potret sama): pembaca mesin tetap 500 untuk kategori itu."""
    from services import sales_force_service as sfs
    ent = "ent_ka2_mesin"
    await db.incentive_rates.insert_many([
        {"id": "irate_ka2m_kat", "entity_id": ent, "category": "KA2Mesin", "per_unit_amount": 500, "status": "active"},
        {"id": "irate_ka2m_art", "entity_id": ent, "category": "KA2Mesin", "template_id": "tpl_ka_mega",
         "per_unit_amount": 900, "status": "active"},
        {"id": "irate_ka2m_var", "entity_id": ent, "category": "KA2Mesin", "product_id": "prd_ka_mega_mrh",
         "per_unit_amount": 700, "status": "active"}])
    for urut in (1, 2):   # urutan baris tidak boleh berpengaruh
        if urut == 2:
            await db.incentive_rates.delete_one({"id": "irate_ka2m_kat"})
            await db.incentive_rates.insert_one({"id": "irate_ka2m_kat", "entity_id": ent, "category": "KA2Mesin",
                                                 "per_unit_amount": 500, "status": "active"})
        rates = await sfs._load_incentive_rates(ent)
        assert rates["KA2Mesin"]["per_unit_amount"] == 500, rates


async def test_KA2_U8_kategori_bawaan_seed_ditolak_kembar(klien, kepala_admin, db):
    from bootstrap import seed_incentive_rates
    await db.incentive_rates.delete_many({})
    await db.products.update_one({"id": "prd_ka_mega_mrh"}, {"$set": {"category": "Batik"}})
    await seed_incentive_rates()
    seed = await db.incentive_rates.find_one({"entity_id": "all", "category": "Batik"}, {"_id": 0})
    assert seed and seed["rate_key"] == "kategori:Batik", seed
    r = await klien.post("/api/incentive-rates", headers=kepala_admin, json={"entity_id": "all", "category": "Batik"})
    assert (r.status_code, r.json()["detail"]) == (409, "Tarif untuk Batik di PT ini sudah ada."), r.text
