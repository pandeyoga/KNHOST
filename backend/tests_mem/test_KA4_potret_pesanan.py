"""KA-4 — potret aturan komisi per baris pesanan (`sales_orders.items[].commission_rule`) + isi awal pesanan lama.

Fixture (DISISIP langsung): artikel `tpl_ka4` ("Batik KA4", BTK-KA4) dengan varian `prd_ka4_mrh`; harga daftar PT 55.000;
tarif artikel di `ent_ksc` 3.500. Produk `prd_ka4_pol` berkategori `KA4Polos` tanpa artikel dan tanpa tarif.
Pesanan dibuat lewat API (Admin seed), pola `test_KMT1_pengalihan.py`.
"""
from __future__ import annotations

import pytest

import bootstrap
from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"
BAG: dict = {}


def _produk(pid: str, kategori: str, tpl: str = "") -> dict:
    d = {"id": pid, "sku": pid.upper(), "name": f"Kain Uji {pid}", "category": kategori, "base_unit": "yard",
         "price": 60_000, "status": "active", "is_active": True, "lifecycle": "produksi", "created_at": now_iso()}
    if tpl:
        d["template_id"] = tpl
    return d


def _pelanggan(cid: str, s1: dict) -> dict:
    return {"id": cid, "code": cid.upper(), "name": f"Toko {cid}", "entity_id": KSC, "status": "active",
            "credit_limit": 0, "pic_name": "Bu Rina", "phone": "6281200000000",
            "assigned_sales_id": s1["id"], "assigned_sales_name": s1["name"],
            "sales_team": [{"sales_id": s1["id"], "name": s1["name"], "role": "pic", "split_pct": 100.0}],
            "addresses": [{"id": f"addr_{cid}", "label": "Toko", "recipient_name": "Bu Rina", "phone": "6281200000000",
                           "city": "Bandung", "address": "Jl. Uji No. 1", "is_primary": True}],
            "created_at": now_iso()}


@pytest.fixture(scope="module")
async def uji(db, akun, kepala_admin, klien):
    s1 = await akun("sales", entitas=(KSC,))
    await db.product_templates.insert_one({"id": "tpl_ka4", "name": "Batik KA4", "category": "KA4Batik",
                                           "sku_prefix": "BTK-KA4", "status": "active", "created_at": now_iso()})
    await db.products.insert_many([_produk("prd_ka4_mrh", "KA4Batik", "tpl_ka4"), _produk("prd_ka4_pol", "KA4Polos")])
    await db.customers.insert_one(_pelanggan("cus_ka4_c1", s1))
    await db.entity_prices.insert_many([
        {"id": f"ep_{p}", "entity_id": KSC, "product_id": p, "sell_price": 55_000, "status": "active",
         "is_listed": True, "valid_from": "2026-01-01", "created_at": now_iso()} for p in ("prd_ka4_mrh", "prd_ka4_pol")])
    r = await klien.post("/api/incentive-rates", headers=kepala_admin,
                         json={"entity_id": KSC, "template_id": "tpl_ka4", "per_unit_amount": 3500})
    assert r.status_code == 200, r.text
    BAG["rate"] = r.json()["id"]
    return {"adm": kepala_admin}


async def _pesan(klien, h, pid: str, qty: float = 10):
    r = await klien.post("/api/sales-orders", headers={**h, "X-Entity-Id": KSC}, json={
        "customer_id": "cus_ka4_c1", "shipping_address_id": "", "entity_id": KSC, "allow_backorder": True,
        "items": [{"product_id": pid, "quantity": qty, "unit": "yard"}]})
    assert r.status_code == 200, r.text
    return r.json()


async def test_KA4_U1_pesanan_memotret_aturan(klien, db, uji):
    so = await _pesan(klien, uji["adm"], "prd_ka4_mrh")
    r = (await db.sales_orders.find_one({"id": so["id"]}))["items"][0]["commission_rule"]
    assert (r["v"], r["sumber"], r["price_basis"], r["acuan"]) == (1, "pesanan", "diskon_baris", "daftar_pt")
    assert (r["tarif"]["per_unit_amount"], r["tarif"]["asal_tingkat"], r["tarif"]["asal_lingkup"]) == (3500, "artikel", "pt")
    assert r["artikel"] == {"id": "tpl_ka4", "nama": "Batik KA4", "kode": "BTK-KA4"}
    BAG["so1"] = so["id"]


async def test_KA4_U2_ubah_tarif_tidak_mengubah_potret(klien, db, uji):
    r = await klien.patch(f"/api/incentive-rates/{BAG['rate']}", headers=uji["adm"], json={"data": {"per_unit_amount": 4000}})
    assert r.status_code == 200, r.text
    lama = (await db.sales_orders.find_one({"id": BAG["so1"]}))["items"][0]["commission_rule"]
    assert lama["tarif"]["per_unit_amount"] == 3500
    so = await _pesan(klien, uji["adm"], "prd_ka4_mrh")
    baru = (await db.sales_orders.find_one({"id": so["id"]}))["items"][0]["commission_rule"]
    assert baru["tarif"]["per_unit_amount"] == 4000


async def test_KA4_U3_tanpa_tarif_dipotret_kosong(klien, db, uji):
    so = await _pesan(klien, uji["adm"], "prd_ka4_pol")
    r = (await db.sales_orders.find_one({"id": so["id"]}))["items"][0]["commission_rule"]
    assert r["tarif"] is None and r["artikel"] is None and r["sumber"] == "pesanan"


async def test_KA4_U4_isi_awal_sekali(db, uji):
    await db.sales_orders.insert_one({
        "id": "so_ka4_lama", "number": "SO-KA4-LAMA", "entity_id": KSC, "status": "confirmed", "created_at": now_iso(),
        "items": [{"product_id": "prd_ka4_mrh", "quantity": 5, "price": 55_000, "line_total": 275_000, "category": "KA4Batik"},
                  {"product_id": "prd_ka4_pol", "quantity": 5, "price": 55_000, "line_total": 275_000,
                   "category": "KA4Polos"}]})
    await bootstrap.backfill_so_line_commission_rule()
    a, b = (await db.sales_orders.find_one({"id": "so_ka4_lama"}))["items"]
    assert (a["commission_rule"]["sumber"], a["commission_rule"]["tarif"]["per_unit_amount"],
            a["commission_rule"]["artikel"]["id"]) == ("isi_awal", 4000, "tpl_ka4")
    assert b["commission_rule"]["tarif"] is None
    dipotret = a["commission_rule"]["dipotret_pada"]
    await bootstrap.backfill_so_line_commission_rule()
    a2 = (await db.sales_orders.find_one({"id": "so_ka4_lama"}))["items"][0]
    assert a2["commission_rule"]["dipotret_pada"] == dipotret


async def test_KA4_U5_aturan_baris_tanpa_potret(db, uji):
    from services import commission_rules
    line = {"product_id": "prd_ka4_mrh", "category": "KA4Batik"}
    r = await commission_rules.aturan_baris(line, KSC, {})
    assert r["sumber"] == "saat_hitung" and r["tarif"]["per_unit_amount"] == 4000 and "commission_rule" not in line
    pot = {"v": 1, "sumber": "pesanan"}
    assert await commission_rules.aturan_baris({"commission_rule": pot}, KSC, {}) is pot
