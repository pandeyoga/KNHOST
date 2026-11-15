"""KM-T1 serah-terima (b) — jalur yang ada dialihkan: harga pembanding & potret pemilik angka di `create_order`,
`analytics_facts.build_rows` membaca potret, serah-terima pelanggan mengganti PIC tim, `POST /api/sales-targets` lama
diteruskan ke penyimpan target baru (KM-T5: jalur lama dihapus; U14 memakai `PUT /api/incentive/targets`), dua skrip data
lama. Spesifikasi `docs/blueprint/unit/KM-T1.md` U9, U10, U14
(lingkungan B); U17 (dua simpan bersamaan) = lapis A `backend/tests/test_bp_KMT1_target_bersamaan_mongo.py`.

Fixture (DISISIP langsung): produk `prd_kmt1b_*` (harga umum per yard, tanpa stok → baris jadi backorder), pelanggan
`cus_kmt1b_*` di `ent_ksc` dengan tim sales PIC S1, harga daftar PT (`entity_prices`) dan harga langganan
(`customer_prices`) untuk U10. Pesanan dibuat lewat API (`POST /api/sales-orders`, Admin seed); serah-terima lewat API
(`POST /api/customers/{id}/reassign`); target lewat API (`PUT /api/incentive/targets`).

Hitung tangan U10: harga langganan 48.000 menang (`price` 48.000, `price_source` customer); pembanding = harga daftar PT
55.000 (`list_price_source` entity); harga umum 60.000. Satuan jual = satuan dasar (yard) → faktor 1.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
REPO = Path(__file__).resolve().parents[2]
BAG: dict = {}


def _produk(pid: str, harga: float) -> dict:
    return {"id": pid, "sku": pid.upper(), "name": f"Kain Uji {pid}", "category": "Kain", "base_unit": "yard",
            "price": harga, "status": "active", "is_active": True, "lifecycle": "produksi", "created_at": now_iso()}


def _pelanggan(cid: str, s1: dict, entity_id: str = KSC) -> dict:
    return {"id": cid, "code": cid.upper(), "name": f"Toko {cid}", "entity_id": entity_id, "status": "active",
            "credit_limit": 0, "pic_name": "Bu Rina", "phone": "6281200000000",
            "assigned_sales_id": s1["id"], "assigned_sales_name": s1["name"],
            "sales_team": [{"sales_id": s1["id"], "name": s1["name"], "role": "pic", "split_pct": 100.0}],
            "addresses": [{"id": f"addr_{cid}", "label": "Toko", "recipient_name": "Bu Rina", "phone": "6281200000000",
                           "city": "Bandung", "address": "Jl. Uji No. 1", "is_primary": True}],
            "created_at": now_iso()}


@pytest.fixture(scope="module")
async def uji(db, akun, kepala_admin):
    s1 = await akun("sales", entitas=(KSC,))
    s2 = await akun("sales", entitas=(KSC,))
    luar = await akun("sales", entitas=(KANDA,))   # sales yang tidak ditugaskan di PT pelanggan
    await db.products.insert_many([_produk("prd_kmt1b_a", 60_000), _produk("prd_kmt1b_b", 60_000)])
    await db.customers.insert_many([_pelanggan("cus_kmt1b_c1", s1), _pelanggan("cus_kmt1b_c2", s1)])
    await db.entity_prices.insert_one({"id": "ep_kmt1b_a", "entity_id": KSC, "product_id": "prd_kmt1b_a",
                                       "sell_price": 55_000, "status": "active", "is_listed": True,
                                       "valid_from": "2026-01-01", "created_at": now_iso()})
    await db.customer_prices.insert_one({"id": "cp_kmt1b_a", "entity_id": KSC, "customer_id": "cus_kmt1b_c2",
                                         "product_id": "prd_kmt1b_a", "sell_price": 48_000, "status": "active",
                                         "valid_from": "2026-01-01", "created_at": now_iso()})
    return {"s1": s1, "s2": s2, "luar": luar, "adm": kepala_admin}


async def _pesan(klien, h, customer: str, pid: str = "prd_kmt1b_a", qty: float = 10):
    r = await klien.post("/api/sales-orders", headers={**h, "X-Entity-Id": KSC}, json={
        "customer_id": customer, "shipping_address_id": "", "entity_id": KSC, "allow_backorder": True,
        "items": [{"product_id": pid, "quantity": qty, "unit": "yard"}]})
    assert r.status_code == 200, r.text
    return r.json()


# ═══ U10 — harga pembanding dipotret di tiap baris ═════════════════════════════════════════════════════════════════
async def test_KMT1_U10_harga_pembanding_dipotret(klien, db, uji):
    so = await _pesan(klien, uji["adm"], "cus_kmt1b_c2")
    it = (await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0}))["items"][0]
    assert (it["price"], it["price_source"]) == (48_000, "customer"), it
    assert (it["list_price"], it["list_price_source"], it["global_price"]) == (55_000, "entity", 60_000), it
    assert "floor_price" in it and "floor_from" in it
    # produk tanpa harga PT → pembanding = harga umum
    so2 = await _pesan(klien, uji["adm"], "cus_kmt1b_c2", pid="prd_kmt1b_b")
    it2 = (await db.sales_orders.find_one({"id": so2["id"]}, {"_id": 0}))["items"][0]
    assert (it2["price"], it2["list_price"], it2["list_price_source"], it2["global_price"]) == (
        60_000, 60_000, "global", 60_000), it2


# ═══ U9 — serah-terima pelanggan: pesanan baru milik sales baru, pesanan lama tetap ═════════════════════════════════
async def test_KMT1_U9_serah_terima_pelanggan(klien, db, uji):
    s1, s2 = uji["s1"]["id"], uji["s2"]["id"]
    lama = await _pesan(klien, uji["adm"], "cus_kmt1b_c1")
    assert (await db.sales_orders.find_one({"id": lama["id"]}))["sales_attribution"] == [{"sales_id": s1, "split": 1.0}]
    r = await klien.post("/api/customers/cus_kmt1b_c1/reassign", headers=uji["adm"],
                         json={"assigned_sales_id": s2, "reason": "uji KM-T1 serah-terima"})
    assert r.status_code == 200, r.text
    c = await db.customers.find_one({"id": "cus_kmt1b_c1"}, {"_id": 0})
    assert c["assigned_sales_id"] == s2
    assert [(m["sales_id"], m["role"], m["split_pct"]) for m in c["sales_team"]] == [(s2, "pic", 100.0)], c["sales_team"]
    baru = await _pesan(klien, uji["adm"], "cus_kmt1b_c1")
    doc = await db.sales_orders.find_one({"id": baru["id"]}, {"_id": 0})
    assert doc["sales_attribution"] == [{"sales_id": s2, "split": 1.0}], doc.get("sales_attribution")
    assert [m["sales_id"] for m in doc["sales_team"]] == [s2]
    assert (await db.sales_orders.find_one({"id": lama["id"]}))["sales_attribution"] == [{"sales_id": s1, "split": 1.0}]
    BAG.update(lama=lama["id"], baru=baru["id"])


async def test_KMT1_b_serah_terima_hanya_ke_sales_pt_pelanggan(klien, uji):
    r = await klien.post("/api/customers/cus_kmt1b_c2/reassign", headers=uji["adm"],
                         json={"assigned_sales_id": uji["luar"]["id"], "reason": "uji KM-T1 PT lain"})
    assert (r.status_code, r.json()["detail"]) == (400, "Salesperson tujuan tidak valid"), r.text


async def test_KMT1_b_fakta_analitik_membaca_potret(db, uji):
    """`analytics_facts.build_rows` memakai `sales_attribution` (potret) — dulu tim pesanan → serah-terima tim
    pelanggan sesudahnya ikut memindahkan pesanan yang dibangun ulang (KM-03, KM-06)."""
    from services import analytics_facts
    s1, s2 = uji["s1"]["id"], uji["s2"]["id"]
    so = {"id": "so_kmt1b_af", "number": "SO-AF", "entity_id": KSC, "grand_total": 1_000_000, "ppn_amount": 0,
          "status": "confirmed", "created_at": now_iso(),
          "items": [{"product_id": "prd_kmt1b_a", "quantity": 10, "price": 100_000, "line_total": 1_000_000}],
          "sales_team": [{"sales_id": s1, "role": "pic", "split_pct": 100}],
          "sales_attribution": [{"sales_id": s2, "split": 1.0}]}
    rows = analytics_facts.build_rows(so, {"assigned_sales_id": s1}, {}, {})
    assert {r["sales_id"] for r in rows} == {s2} and rows[0]["net_alloc"] == 1_000_000, rows
    rows = analytics_facts.build_rows(so, {"assigned_sales_id": s1}, {}, {}, mode="customer_owner")
    assert {r["sales_id"] for r in rows} == {s1}   # mode pemilik pelanggan kini: tidak memakai potret
    tanpa = {**so, "sales_attribution": None}
    assert {r["sales_id"] for r in analytics_facts.build_rows(tanpa, {}, {}, {})} == {s1}   # pesanan lama: aturan tim


# ═══ U14 — target untuk akun berperan kustom beracuan sales ════════════════════════════════════════════════════════
async def test_KMT1_U14_target_peran_kustom_acuan_sales(klien, db, akun, uji):
    r = await klien.post("/api/access/roles", headers=uji["adm"], json={
        "label": "Sales Senior", "base_role": "sales", "description": "peran uji KM-T1"})
    assert r.status_code == 200, r.text
    rid = (r.json().get("role") or r.json())["id"]
    senior = await akun(rid, entitas=(KSC, KANDA))
    h = {**uji["adm"], "X-Entity-Id": KANDA}
    r = await klien.put("/api/incentive/targets", headers=h, json={
        "sales_id": senior["id"], "period_type": "month", "period": "2026-12", "target_sales_amount": 150_000_000})
    assert r.status_code == 200, r.text
    assert (r.json()["entity_id"], r.json()["sales_name"]) == (KANDA, senior["name"])
    # KM-T5 — jalur lama `POST /api/sales-targets` (layar "Set Target") DIHAPUS; sifat yang dulu diuji lewat jalur itu
    # (PT = PT konteks, kunci per PT, periode salah 400, "Semua PT" 409) kini diuji lewat penyimpan yang sama
    # (`PUT /api/incentive/targets`).
    r = await klien.put("/api/incentive/targets", headers=h, json={
        "sales_id": senior["id"], "period_type": "month", "period": "2026-12", "target_sales_amount": 175_000_000,
        "target_collection_amount": 90_000_000})
    assert r.status_code == 200, r.text
    assert (r.json()["entity_id"], r.json()["period_type"], r.json()["target_sales_amount"]) == (
        KANDA, "month", 175_000_000), r.json()
    docs = await db.sales_targets.find({"sales_id": senior["id"], "period": "2026-12"}, {"_id": 0}).to_list(None)
    assert [(d["entity_id"], d["target_sales_amount"]) for d in docs] == [(KANDA, 175_000_000)], docs
    r = await klien.put("/api/incentive/targets", headers={**uji["adm"], "X-Entity-Id": KSC}, json={
        "sales_id": senior["id"], "period_type": "month", "period": "2026-12", "target_sales_amount": 10_000_000})
    assert r.status_code == 200 and r.json()["entity_id"] == KSC
    assert await db.sales_targets.count_documents({"sales_id": senior["id"], "period": "2026-12"}) == 2   # per PT
    r = await klien.put("/api/incentive/targets", headers={**uji["adm"], "X-Entity-Id": KSC}, json={
        "sales_id": senior["id"], "period_type": "month", "period": "2026-Q4", "target_sales_amount": 1})
    assert r.status_code == 400 and r.json()["detail"].startswith("Periode tidak sesuai jenisnya")
    r = await klien.put("/api/incentive/targets", headers={**uji["adm"], "X-Entity-Id": "all"}, json={
        "sales_id": senior["id"], "period_type": "month", "period": "2026-12", "target_sales_amount": 1})
    assert r.status_code == 409, r.text
    r = await klien.post("/api/sales-targets", headers=h, json={"sales_id": senior["id"], "period": "2026-12"})
    assert r.status_code in (404, 405), r.text


# ═══ Skrip data lama (dijalankan di database tiruan; data nyata = H3) ══════════════════════════════════════════════
def _skrip(nama: str):
    sys.path.insert(0, str(REPO / "scripts"))
    return importlib.import_module(nama)


async def test_KMT1_b_skrip_migrasi_target(db, uji, capsys):
    skrip = _skrip("migrate_sales_targets_km_t1")
    s1 = uji["s1"]
    await db.sales_targets.delete_many({"id": {"$regex": "^starg_kmt1b_"}})
    await db.sales_targets.insert_many([
        {"id": "starg_kmt1b_1", "sales_id": s1["id"], "period": "2025-03", "target_sales_amount": 1},
        {"id": "starg_kmt1b_2", "sales_id": s1["id"], "period": "2025-04", "period_type": "month",
         "entity_id": KSC, "target_sales_amount": 2},
        {"id": "starg_kmt1b_3", "sales_id": s1["id"], "period": "2025-Q2", "entity_id": KSC}])
    assert await skrip.jalankan([]) == 0
    keluar = capsys.readouterr().out
    assert "Target starg_kmt1b_1: isi period_type = month, entity_id = ent_ksc" in keluar, keluar
    assert "Dilewati starg_kmt1b_3: periode bukan YYYY-MM" in keluar
    assert "Mode baca-saja" in keluar
    assert (await db.sales_targets.find_one({"id": "starg_kmt1b_1"})).get("period_type") is None   # baca-saja
    assert await skrip.jalankan(["--apply"]) == 0
    t = await db.sales_targets.find_one({"id": "starg_kmt1b_1"})
    assert (t["period_type"], t["entity_id"]) == ("month", KSC)
    assert await skrip.jalankan(["--apply"]) == 0
    assert "Tanpa perubahan." in capsys.readouterr().out
    # kunci kembar sesudah pengisian → dilaporkan (H6), keluar 3, tidak digabung
    await db.sales_targets.insert_one({"id": "starg_kmt1b_4", "sales_id": s1["id"], "period": "2025-04"})
    assert await skrip.jalankan([]) == 3
    keluar = capsys.readouterr().out
    assert "KUNCI KEMBAR (H6)" in keluar and "starg_kmt1b_2" in keluar and "starg_kmt1b_4" in keluar, keluar
    await db.sales_targets.delete_many({"id": {"$regex": "^starg_kmt1b_"}})


async def test_KMT1_b_skrip_isi_harga_pembanding(db, capsys):
    skrip = _skrip("backfill_order_price_refs")
    await db.sales_orders.insert_one({"id": "so_kmt1b_lama", "number": "SO-LAMA", "entity_id": KSC, "items": [
        {"product_id": "p1", "price": 50_000, "price_source": "entity"},
        {"product_id": "p2", "price": 60_000, "price_source": "global"},
        {"product_id": "p3", "price": 45_000, "price_source": "customer"},
        {"product_id": "p4", "price": 40_000, "price_source": "special_approval"}], "created_at": now_iso()})
    assert await skrip.jalankan([]) == 0
    keluar = capsys.readouterr().out
    assert "dibiarkan — sumber harga customer: 1 baris" in keluar and "special_approval: 1 baris" in keluar, keluar
    assert "list_price" not in (await db.sales_orders.find_one({"id": "so_kmt1b_lama"}))["items"][0]   # baca-saja
    assert await skrip.jalankan(["--apply"]) == 0
    items = (await db.sales_orders.find_one({"id": "so_kmt1b_lama"}))["items"]
    assert [(i.get("list_price"), i.get("list_price_source"), i.get("global_price")) for i in items] == [
        (50_000, "entity", None), (60_000, "global", 60_000), (None, None, None), (None, None, None)]
    assert await skrip.jalankan(["--apply"]) == 0
    assert "Tanpa perubahan." in capsys.readouterr().out
