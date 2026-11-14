"""KM-T1 serah-terima (a) — data insentif: fakta omzet terkirim & pencairan, target per PT, definisi angka.

Spesifikasi `docs/blueprint/unit/KM-T1.md`, uji penerimaan U1–U8, U11–U13, U15, U16, U18 (lingkungan B). U9, U10, U14
(jalur yang ada) = `test_KMT1_pengalihan.py`; U17 (dua simpan bersamaan, indeks unik) = lapis A
`backend/tests/test_bp_KMT1_target_bersamaan_mongo.py`.

Fixture **F1** di `ent_kanda` (non-PKP, tanpa PPN), DISISIPKAN langsung (pesanan, surat jalan, retur & nota kredit, satu
baris hapus sisa lewat `ar_allocation_service.allocate`); jurnal pendapatan diterbitkan `gl_service.post_order_revenue_and_cogs`
(SJ1 saat pesanan `partially_shipped`, SJ2 sesudah `shipped`) dan `gl_service.post_sales_return`; kwitansi R1–R3 lewat
fungsi kwitansi asli `ar_receipt_service.create_receipt` (kas lewat pembuat kas PK-20, rekening fixture).

Hitung tangan:
  O1 milik S1 (tim PIC 100 %): 1.000 yd × Rp 50.000 = Rp 50.000.000; list_price 55.000; unit_cost 30.000.
  SJ1 10 Okt 600 yd → 50 jt × 600/1.000 = 30.000.000; list 30 jt × 55/50 = 33.000.000; biaya 600 × 30.000 = 18.000.000.
  SJ2  3 Nov 400 yd → pesanan `shipped` → SISA 50 jt − 30 jt = 20.000.000.
  CN1 12 Nov retur Rp 5.000.000 → `retur` −5.000.000. November Σ = 20 jt − 5 jt = 15.000.000.
  Buku: Okt Cr 4-1000 30.000.000 (shipment_revenue SJ1); Nov Cr 4-1000 20.000.000 (SJ2) − Dr 4-1000 5.000.000 (retur) = 15 jt.
  R1 15 Okt transfer 20.000.000 → O1 `kas` 20.000.000. R2 20 Okt tunai 12.000.000, O1 10.000.000 → `kas` 10.000.000,
  sisa 2.000.000 jadi deposit (belum dialokasikan). Okt: dialokasikan 30 jt + belum 2 jt = kwitansi 32 jt = kas 32 jt.
  R3 5 Nov deposit 2.000.000 → `deposit`; hapus sisa 6 Nov 500.000 → `hapus_sisa` (bukan kas).
  U7 batal R1 8 Nov → Okt tetap +20 jt; Nov pembalik −20 jt. Nov: A −20 jt + B 0 − C (0 − 20 jt) = 0; C − D = −20 − (−20) = 0.
  U8 O2 tim S1 60 % · S2 40 %, nilai bersih 1.000.001 → sen 100.000.100 × 0,6 = 60.000.060 → 600.000,60; sisa 400.000,40.
"""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI

pytestmark = pytest.mark.anyio

KANDA, KSC = "ent_kanda", "ent_ksc"
REPO = Path(__file__).resolve().parents[2]
O1, O2 = "so_kmt1_o1", "so_kmt1_o2"
PRD = "prd_kmt1_kain"
CUS = "cus_kmt1_c1"
BAG: Dict[str, Any] = {}


def _iso(tgl: str, jam: str = "03:00:00") -> str:
    return f"{tgl}T{jam}+00:00"


async def _rebuild():
    from services import incentive_facts
    return await incentive_facts.rebuild()


async def _fakta(db, koleksi: str, period: str, **saring) -> List[Dict[str, Any]]:
    return await db[koleksi].find({"entity_id": KANDA, "period": period, **saring}).to_list(None)


@pytest.fixture(scope="module")
async def f1(db, akun):
    """F1 — lihat docstring modul. Mengembalikan id akun S1, S2 dan kwitansi R1–R3."""
    from services import ar_allocation_service as aas
    from services import ar_receipt_service as ars
    from services import config_resolver as resolver
    from services import gl_service as gl
    for key in ("payment.variance_tolerance_rupiah",):
        await resolver.set_value(key, 0, scope_type="entity", scope_id=KANDA, actor="uji", reason="uji KM-T1")
    await db.bank_accounts.insert_many([
        {"id": "rek_kmt1_b", "name": "BCA Kanda KM-T1", "entity_id": KANDA, "account_type": "bank",
         "cash_type": "kas_besar", "is_active": True, "opening_balance": 0},
        {"id": "rek_kmt1_k", "name": "Kas Kecil Kanda KM-T1", "entity_id": KANDA, "account_type": "cash",
         "cash_type": "kas_kecil", "is_active": True, "opening_balance": 0}])
    s1 = await akun("sales", entitas=(KANDA, KSC))
    s2 = await akun("sales", entitas=(KANDA,))
    await db.customers.insert_one({"id": CUS, "name": "Toko Uji KM-T1", "entity_id": KANDA, "status": "active",
                                   "deposit_balance": 0.0, "assigned_sales_id": s1["id"],
                                   "sales_team": [{"sales_id": s1["id"], "role": "pic", "split_pct": 100.0}]})
    await db.products.insert_one({"id": PRD, "name": "Kain Uji KM-T1", "sku": "KMT1-01", "base_unit": "yard",
                                  "price": 60_000, "category": "Katun", "line_code": "woven", "is_active": True})
    item = {"product_id": PRD, "sku": "KMT1-01", "product_name": "Kain Uji KM-T1", "quantity": 1000,
            "base_quantity": 1000, "unit": "yard", "base_unit": "yard", "price": 50_000, "line_total": 50_000_000,
            "list_price": 55_000, "list_price_source": "entity", "global_price": 60_000, "unit_cost": 30_000,
            "price_source": "entity", "category": "Katun", "line_code": "woven"}
    await db.sales_orders.insert_one({
        "id": O1, "number": "SO/KMT1/O1", "entity_id": KANDA, "customer_id": CUS, "customer_name": "Toko Uji KM-T1",
        "status": "partially_shipped", "payment_term_code": "NET30", "items": [item], "subtotal": 50_000_000,
        "grand_total": 50_000_000, "ppn_amount": 0, "payments": [], "paid_total": 0.0, "payment_status": "unpaid",
        "sales_team": [{"sales_id": s1["id"], "role": "pic", "split_pct": 100.0}],
        "created_at": _iso("2026-10-01"), "updated_at": now_iso()})
    base_sj = {"entity_id": KANDA, "order_id": O1, "order_number": "SO/KMT1/O1", "product_id": PRD, "unit": "yard",
               "status": "dispatched"}
    await db.shipments.insert_one({**base_sj, "id": "shp_kmt1_1", "shipment_no": "SJ/KMT1/1", "qty": 600,
                                   "created_at": _iso("2026-10-10")})
    await gl.post_order_revenue_and_cogs(O1)
    await db.shipments.insert_one({**base_sj, "id": "shp_kmt1_2", "shipment_no": "SJ/KMT1/2", "qty": 400,
                                   "created_at": _iso("2026-11-03")})
    await db.sales_orders.update_one({"id": O1}, {"$set": {"status": "shipped", "updated_at": now_iso()}})
    await gl.post_order_revenue_and_cogs(O1)
    rc = {}
    for name, body in (
            ("R1", {"amount": 20_000_000, "method": "transfer", "account_id": "rek_kmt1_b",
                    "allocations": [{"order_id": O1, "amount": 20_000_000}], "receipt_date": "2026-10-15"}),
            ("R2", {"amount": 12_000_000, "method": "tunai", "account_id": "rek_kmt1_k",
                    "allocations": [{"order_id": O1, "amount": 10_000_000}], "receipt_date": "2026-10-20"}),
            ("R3", {"amount": 0, "use_deposit_amount": 2_000_000, "method": "deposit",
                    "allocations": [{"order_id": O1, "amount": 2_000_000}], "receipt_date": "2026-11-05"})):
        r = await ars.create_receipt({"customer_id": CUS, "entity_id": KANDA, **body}, AKTOR_UJI)
        rc[name] = r["id"]
    await aas.allocate(kind="hapus_sisa", order_id=O1, amount=500_000, source_id="pvd_kmt1_hs",
                       source_number="HS/KMT1/1", customer_id=CUS, entity_id=KANDA, date="2026-11-06",
                       actor=AKTOR_UJI, method="writeoff")
    ret = {"id": "sr_kmt1_1", "number": "RJ/KMT1/1", "entity_id": KANDA, "order_id": O1, "order_number": "SO/KMT1/O1",
           "customer_id": CUS, "status": "settled", "approved_at": _iso("2026-11-12"), "items": [],
           "credit_note_id": "cn_kmt1_1", "created_at": _iso("2026-11-11")}
    await db.sales_returns.insert_one(dict(ret))
    await db.credit_notes.insert_one({
        "id": "cn_kmt1_1", "number": "CN/KMT1/1", "return_id": ret["id"], "order_id": O1,
        "order_number": "SO/KMT1/O1", "customer_id": CUS, "entity_id": KANDA,
        "lines": [{"product_id": PRD, "quantity": 100, "unit": "yard", "unit_price": 50_000, "line_total": 5_000_000}],
        "net_amount": 5_000_000, "ppn_amount": 0, "gross_amount": 5_000_000, "cogs_amount": 3_000_000,
        "settlement": "ar", "status": "posted", "created_at": _iso("2026-11-12", "04:00:00")})
    await gl.post_sales_return(ret, return_net=5_000_000, return_ppn=0, return_cogs=3_000_000,
                               credit_note_number="CN/KMT1/1")
    return {"s1": s1, "s2": s2, **rc}


# ═══ U1–U3 — omzet terkirim (fakta) = buku besar ════════════════════════════════════════════════════════════════════
async def test_KMT1_U1_fakta_kirim_oktober(db, f1):
    res = await _rebuild()
    assert res["rows_shipment"] >= 3 and res["rows_collection"] >= 4, res
    rows = await _fakta(db, "fact_shipment_sales", "2026-10")
    assert len(rows) == 1, rows
    r = rows[0]
    assert (r["source_kind"], r["source_id"], r["sales_id"], r["split"]) == ("kirim", "shp_kmt1_1", f1["s1"]["id"], 1.0)
    assert (r["net"], r["list_value"], r["cost"], r["cost_known"]) == (30_000_000, 33_000_000, 18_000_000, True), r
    assert (r["global_value"], r["floor_value"], r["qty_base"]) == (36_000_000, None, 600), r   # 30 jt × 60/50
    assert (r["so_id"], r["line_idx"], r["date_wib"], r["product_id"], r["price_source"]) == (
        O1, 0, "2026-10-10", PRD, "entity")
    assert r["_id"] == f"kirim:shp_kmt1_1:0:{f1['s1']['id']}"


async def test_KMT1_U2_fakta_november_sisa_dan_retur(db, f1):
    rows = await _fakta(db, "fact_shipment_sales", "2026-11")
    per = {r["source_kind"]: r for r in rows}
    assert sorted(per) == ["kirim", "retur"] and len(rows) == 2, rows
    assert per["kirim"]["net"] == 20_000_000 and per["kirim"]["source_id"] == "shp_kmt1_2"
    assert (per["retur"]["net"], per["retur"]["cost"], per["retur"]["line_idx"]) == (-5_000_000, -3_000_000, None)
    assert per["retur"]["source_id"] == "cn_kmt1_1" and per["retur"]["date_wib"] == "2026-11-12"
    assert round(sum(r["net"] for r in rows), 2) == 15_000_000


async def test_KMT1_U3_pencocokan_omzet_dengan_buku(klien, kepala_admin, f1):
    h = {**kepala_admin, "X-Entity-Id": KANDA}
    for period, nilai in (("2026-10", 30_000_000), ("2026-11", 15_000_000)):
        r = await klien.get("/api/incentive/reconciliation", headers=h, params={"period": period})
        assert r.status_code == 200, r.text
        om = r.json()["omzet"]
        assert (om["fakta"], om["buku"], om["selisih"], om["ok"]) == (nilai, nilai, 0, True), om
        assert om["penyebab"] == []
    assert (await klien.get("/api/incentive/reconciliation", headers=h,
                            params={"period": "2026-13"})).status_code == 400


# ═══ U4–U7 — pencairan per jenis sumber dana ════════════════════════════════════════════════════════════════════════
async def test_KMT1_U4_pencairan_oktober_kas(db, f1):
    rows = await _fakta(db, "fact_collections", "2026-10")
    per = {r["receipt_id"]: r for r in rows}
    assert {k: (v["source_kind"], v["amount"]) for k, v in per.items()} == {
        f1["R1"]: ("kas", 20_000_000), f1["R2"]: ("kas", 10_000_000)}, rows
    assert sum(r["amount"] for r in rows if r["source_kind"] == "kas") == 30_000_000
    assert all(r["sales_id"] == f1["s1"]["id"] and not r["is_reversal"] for r in rows)
    assert per[f1["R2"]]["method"] == "cash" and per[f1["R2"]]["giro_uncleared"] is False


async def test_KMT1_U5_pencocokan_pencairan_oktober(klien, kepala_admin, f1):
    r = await klien.get("/api/incentive/reconciliation", headers={**kepala_admin, "X-Entity-Id": KANDA},
                        params={"period": "2026-10"})
    assert r.status_code == 200, r.text
    p = r.json()["pencairan"]
    assert (p["dialokasikan"], p["belum_dialokasikan"], p["kwitansi"], p["kas"], p["ok"]) == (
        30_000_000, 2_000_000, 32_000_000, 32_000_000, True), p


async def test_KMT1_U6_pencairan_november_deposit_dan_hapus_sisa(db, f1):
    rows = await _fakta(db, "fact_collections", "2026-11")
    assert sorted((r["source_kind"], r["amount"]) for r in rows) == [("deposit", 2_000_000), ("hapus_sisa", 500_000)]
    assert not [r for r in rows if r["source_kind"] == "kas"]
    hs = next(r for r in rows if r["source_kind"] == "hapus_sisa")
    assert hs["method"] == "writeoff" and hs["date_wib"] == "2026-11-06"


async def test_KMT1_U7_batal_kwitansi_pembalik_di_periode_batal(klien, kepala_admin, db, f1, monkeypatch):
    from services import ar_receipt_service as ars
    from services import incentive_facts
    monkeypatch.setattr(ars, "now_iso", lambda: _iso("2026-11-08"))   # "hari ini" pembatalan = 8 Nov 2026
    await ars.void_receipt(f1["R1"], AKTOR_UJI, reason="uji KM-T1 batal R1")
    monkeypatch.undo()
    await incentive_facts.sync()
    okt = await _fakta(db, "fact_collections", "2026-10", receipt_id=f1["R1"])
    nov = await _fakta(db, "fact_collections", "2026-11", receipt_id=f1["R1"])
    assert [(r["amount"], r["is_reversal"]) for r in okt] == [(20_000_000, False)], okt
    assert [(r["amount"], r["is_reversal"], r["date_wib"]) for r in nov] == [(-20_000_000, True, "2026-11-08")], nov
    h = {**kepala_admin, "X-Entity-Id": KANDA}
    for period in ("2026-10", "2026-11"):
        j = (await klien.get("/api/incentive/reconciliation", headers=h, params={"period": period})).json()
        assert j["omzet"]["ok"] and j["pencairan"]["ok"], (period, j)
    nov_p = (await klien.get("/api/incentive/reconciliation", headers=h, params={"period": "2026-11"})).json()
    assert (nov_p["pencairan"]["dialokasikan"], nov_p["pencairan"]["kwitansi"], nov_p["pencairan"]["kas"]) == (
        -20_000_000, -20_000_000, -20_000_000), nov_p["pencairan"]


# ═══ U8 — pembagian tim sampai sen ══════════════════════════════════════════════════════════════════════════════════
async def test_KMT1_U8_pembagian_tim_sampai_sen(db, f1):
    from services import gl_service as gl
    from services import incentive_facts
    s1, s2 = f1["s1"]["id"], f1["s2"]["id"]
    await db.sales_orders.insert_one({
        "id": O2, "number": "SO/KMT1/O2", "entity_id": KANDA, "customer_id": CUS, "customer_name": "Toko Uji KM-T1",
        "status": "shipped", "payment_term_code": "NET30", "grand_total": 1_000_001, "ppn_amount": 0, "payments": [],
        "items": [{"product_id": PRD, "sku": "KMT1-01", "quantity": 100, "base_quantity": 100, "unit": "yard",
                   "price": 10_000.01, "line_total": 1_000_001, "unit_cost": 6_000}],
        "sales_team": [{"sales_id": s1, "role": "pic", "split_pct": 60}, {"sales_id": s2, "role": "co", "split_pct": 40}],
        "created_at": _iso("2026-09-15"), "updated_at": now_iso()})
    await db.shipments.insert_one({"id": "shp_kmt1_o2", "shipment_no": "SJ/KMT1/O2", "entity_id": KANDA,
                                   "order_id": O2, "product_id": PRD, "qty": 100, "unit": "yard", "status": "dispatched",
                                   "created_at": _iso("2026-09-20")})
    await gl.post_order_revenue_and_cogs(O2)
    await incentive_facts.rebuild()
    rows = await db.fact_shipment_sales.find({"so_id": O2}, {"_id": 0}).to_list(None)
    per = {r["sales_id"]: r for r in rows}
    assert (per[s1]["net"], per[s2]["net"]) == (600_000.60, 400_000.40), rows
    assert (per[s1]["split"], per[s2]["split"]) == (0.6, 0.4)
    assert round(sum(r["net"] for r in rows), 2) == 1_000_001.00
    assert round(per[s1]["cost"] + per[s2]["cost"], 2) == 600_000


# ═══ U11–U13 — target per PT, triwulan tersendiri, tahun buku ═══════════════════════════════════════════════════════
async def _put(klien, h, **isi):
    return await klien.put("/api/incentive/targets", headers=h, json=isi)


async def test_KMT1_U11_target_per_pt(klien, kepala_admin, db, f1):
    s1 = f1["s1"]["id"]
    for ent, nilai in ((KSC, 100_000_000), (KANDA, 80_000_000)):
        r = await _put(klien, {**kepala_admin, "X-Entity-Id": ent}, sales_id=s1, period_type="month", period="2026-10",
                       target_sales_amount=nilai, target_collection_amount=nilai / 2)
        assert r.status_code == 200, r.text
        assert (r.json()["entity_id"], r.json()["target_sales_amount"]) == (ent, nilai)
    docs = await db.sales_targets.find({"sales_id": s1, "period_type": "month", "period": "2026-10"},
                                       {"_id": 0}).to_list(None)
    assert sorted(d["entity_id"] for d in docs) == [KANDA, KSC]
    for ent, nilai in ((KSC, 100_000_000), (KANDA, 80_000_000)):
        j = (await klien.get("/api/incentive/targets", headers={**kepala_admin, "X-Entity-Id": ent},
                             params={"period_type": "month", "period": "2026-10"})).json()
        assert [(t["entity_id"], t["target_sales_amount"]) for t in j["items"]] == [(ent, nilai)], j
        assert s1 in {x["id"] for x in j["roster"]}
    # simpan ulang = memperbarui dokumen yang sama
    r = await _put(klien, {**kepala_admin, "X-Entity-Id": KSC}, sales_id=s1, period_type="month", period="2026-10",
                   target_sales_amount=110_000_000, target_collection_amount=0)
    assert r.status_code == 200 and await db.sales_targets.count_documents(
        {"sales_id": s1, "entity_id": KSC, "period": "2026-10"}) == 1
    # galat isian (pesan spesifikasi)
    h = {**kepala_admin, "X-Entity-Id": KSC}
    r = await _put(klien, h, sales_id=s1, period_type="quarter", period="2026-10", target_sales_amount=1)
    assert (r.status_code, r.json()["detail"]) == (400, "Periode tidak sesuai jenisnya. Contoh: 2026-10, 2026-Q4, atau 2026.")
    r = await _put(klien, h, sales_id=f1["s2"]["id"], period_type="month", period="2026-10", target_sales_amount=1)
    assert (r.status_code, r.json()["detail"]) == (400, "Akun ini tidak ditugaskan di PT yang sedang dibuka.")
    r = await _put(klien, h, sales_id=s1, period_type="month", period="2026-10", target_sales_amount=-1)
    assert r.status_code == 400
    r = await _put(klien, {**kepala_admin, "X-Entity-Id": "all"}, sales_id=s1, period_type="month", period="2026-10",
                   target_sales_amount=1)
    assert r.status_code == 409, r.text


async def test_KMT1_U12_target_triwulan_angka_tersendiri(klien, kepala_admin, f1):
    h = {**kepala_admin, "X-Entity-Id": KSC}
    s1 = f1["s1"]["id"]
    for bulan, nilai in (("2026-07", 100e6), ("2026-08", 200e6), ("2026-09", 300e6)):
        assert (await _put(klien, h, sales_id=s1, period_type="month", period=bulan,
                           target_sales_amount=nilai)).status_code == 200
    r = await _put(klien, h, sales_id=s1, period_type="quarter", period="2026-Q3", target_sales_amount=700e6,
                   target_collection_amount=500e6)
    assert r.status_code == 200, r.text
    j = (await klien.get("/api/incentive/targets", headers=h, params={"period_type": "quarter",
                                                                      "period": "2026-Q3"})).json()
    assert [t["target_sales_amount"] for t in j["items"]] == [700_000_000], j   # bukan 100 + 200 + 300 = 600 jt
    assert (j["bounds"], j["previous_period"], j["period_label"]) == (
        {"start": "2026-07-01", "end": "2026-09-30"}, "2026-Q2", "Triwulan III 2026")
    # salin ke triwulan berikut: yang belum ada disalin, yang sudah ada dilewati
    r = await klien.post("/api/incentive/targets/copy", headers=h,
                         json={"period_type": "quarter", "from_period": "2026-Q3", "to_period": "2026-Q4"})
    assert r.json() == {"copied": 1, "skipped": 0}, r.text
    r = await klien.post("/api/incentive/targets/copy", headers=h,
                         json={"period_type": "quarter", "from_period": "2026-Q3", "to_period": "2026-Q4"})
    assert r.json() == {"copied": 0, "skipped": 1}, r.text


async def test_KMT1_U13_triwulan_mengikuti_tahun_buku(f1):
    from services import config_resolver as resolver
    from services import incentive_periods as ip
    await resolver.set_value("finance.fiscal_year_end_month", 3, scope_type="entity", scope_id=KANDA, actor="uji",
                             reason="uji KM-T1 U13")
    try:
        assert await ip.period_bounds("quarter", "2027-Q1", KANDA) == ("2026-04-01", "2026-06-30")
        assert await ip.period_bounds("year", "2027", KANDA) == ("2026-04-01", "2027-03-31")
        assert await ip.period_bounds("quarter", "2027-Q1", KSC) == ("2027-01-01", "2027-03-31")   # PT lain tetap
        assert ip.current_period_with("quarter", "2026-11-14", 3) == "2027-Q3"
    finally:
        await resolver.clear_layer("finance.fiscal_year_end_month", scope_type="entity", scope_id=KANDA, actor="uji",
                                   reason="uji KM-T1 U13 selesai")
    assert await ip.period_bounds("quarter", "2027-Q1", KANDA) == ("2027-01-01", "2027-03-31")


# ═══ U15 — izin (peran uji baku) ════════════════════════════════════════════════════════════════════════════════════
async def test_KMT1_U15_izin_peran_uji_baku(klien, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong, peran_sopir):
    h = await sesi(await akun(await peran_tanpa_acuan({"incentive": ["view"]}, label="Lihat Insentif")))
    for ep in ("/api/incentive/targets", "/api/incentive/components", "/api/incentive/definitions/current",
               "/api/incentive/reconciliation"):
        r = await klien.get(ep, headers=h)
        assert r.status_code == 200, (ep, r.text)
    r = await _put(klien, h, sales_id="x", period_type="month", period="2026-10")
    assert r.status_code == 403 and "Kinerja & Insentif" in r.json()["detail"], r.text
    for peran in (await peran_manajer_kosong(), peran_sopir):
        r = await klien.get("/api/incentive/targets", headers=await sesi(await akun(peran)))
        assert r.status_code == 403, (peran, r.text)
        d = r.json()["detail"]
        assert d.startswith("Anda belum punya akses untuk") and "'Kinerja & Insentif'" in d, d
        assert not re.search(r"incentive\.|[a-z]+_[a-z]+", d), d
    # Tanpa Acuan + configure: bisa mengatur
    h2 = await sesi(await akun(await peran_tanpa_acuan({"incentive": ["view", "configure"]}, label="Atur Insentif")))
    r = await klien.post("/api/incentive/components", headers=h2, json={
        "code": "ib", "name": "Insentif Bulanan", "basis_period_type": "month", "columns": ["omzet", "pencairan"]})
    assert r.status_code == 200, r.text


# ═══ U16 — empat kunci insentif.* (putaran t1_config) + versi definisi ══════════════════════════════════════════════
KUNCI = ("insentif.dasar_omzet", "insentif.isi_pencairan", "insentif.pemilik_angka", "insentif.harga_acuan")


@pytest.mark.parametrize("kunci", KUNCI)
async def test_KMT1_U16_putaran_t1_config(kunci, klien, kepala_admin):
    import config_registry as registry
    from test_KFT8_putaran_pengaturan import putaran
    e = registry.require(kunci)
    assert (e["type"], e["scopes"], e["permission"], e["risk"], e["requires_reason"]) == (
        "enum", ["global", "entity"], ["incentive", "configure"], "high", True)
    assert (e["group"], e["section"]) == ("penjualan", "komisi")
    assert e["consumers"] == ["services/incentive_definitions.py:current_definition"]
    gagal = await putaran(klien, kepala_admin, kunci)
    assert not gagal, "\n".join(gagal)
    r = await klien.put("/api/config/values", headers=kepala_admin, json={
        "key": kunci, "value": "tidak_ada", "scope_type": "global", "scope_id": "", "reason": "uji nilai tak sah"})
    assert r.status_code == 400, r.text


async def test_KMT1_U16_versi_definisi_bertambah(klien, kepala_admin):
    from services import config_resolver as resolver
    from services import incentive_definitions as idef
    h = {**kepala_admin, "X-Entity-Id": KANDA}
    j = (await klien.get("/api/incentive/definitions/current", headers=h)).json()
    v0 = j["version"]
    assert {i["field"]: i["value"] for i in j["items"]} == {
        "dasar_omzet": "terkirim", "isi_pencairan": "uang_masuk", "pemilik_angka": "sales_pesanan",
        "harga_acuan": "daftar_pt"}, j
    assert {i["field"]: i["value_label"] for i in j["items"]}["dasar_omzet"] == "Saat barang dikirim"
    assert (await klien.get("/api/incentive/definitions/current", headers=h)).json()["version"] == v0   # tanpa ubah
    ksc0 = (await idef.current_definition(KSC))["version"]
    await resolver.set_value("insentif.dasar_omzet", "pesanan", scope_type="entity", scope_id=KANDA, actor="uji",
                             reason="uji KM-T1 U16")
    try:
        j2 = (await klien.get("/api/incentive/definitions/current", headers=h)).json()
        assert j2["version"] == v0 + 1, j2
        assert {i["field"]: i["value"] for i in j2["items"]}["dasar_omzet"] == "pesanan"
        assert (await idef.current_definition(KSC))["version"] == ksc0   # PT lain tidak ikut berubah
    finally:
        await resolver.clear_layer("insentif.dasar_omzet", scope_type="entity", scope_id=KANDA, actor="uji",
                                   reason="uji KM-T1 U16 selesai")
    assert (await idef.current_definition(KANDA))["version"] == v0 + 2   # kembali ke bawaan = versi baru


# ═══ U18 — INV-KM-3: bangun ulang penuh = isi koleksi ═══════════════════════════════════════════════════════════════
async def test_KMT1_U18_inv_km3_hapus_lalu_bangun_ulang(klien, kepala_admin, db, f1, capsys):
    from services import incentive_facts
    await incentive_facts.rebuild()
    assert await incentive_facts.rebuild_diff() == []
    n_ship, n_coll = await db.fact_shipment_sales.count_documents({}), await db.fact_collections.count_documents({})
    ids = sorted(r["_id"] for r in await db.fact_shipment_sales.find({}, {"_id": 1}).to_list(None))[:2]
    ids += [(await db.fact_collections.find_one({"receipt_id": f1["R2"], "source_kind": "kas"}))["_id"]]
    await db.fact_shipment_sales.delete_many({"_id": {"$in": ids[:2]}})
    await db.fact_collections.delete_many({"_id": {"$in": ids[2:]}})
    beda = await incentive_facts.rebuild_diff()
    assert beda and sum(d["rows_expected"] - d["rows_actual"] for d in beda) == 3, beda
    r = await klien.post("/api/incentive/facts/rebuild", headers={**kepala_admin, "X-Entity-Id": KANDA}, json={})
    assert r.status_code == 200, r.text
    assert set(r.json()) >= {"rows_shipment", "rows_collection"}
    assert await incentive_facts.rebuild_diff() == []
    assert (await db.fact_shipment_sales.count_documents({}), await db.fact_collections.count_documents({})) == (
        n_ship, n_coll)
    # penjaga data (`verify_data_integrity.py` lapisan insentif): INV-KM-1/2 per PT per bulan + INV-KM-3 lulus
    sys.path.insert(0, str(REPO / "scripts"))
    vdi = importlib.import_module("verify_data_integrity")
    awal_fail = vdi.results["fail"]
    await vdi.layer_incentive_invariants(db)
    keluar = capsys.readouterr().out
    assert vdi.results["fail"] == awal_fail, keluar
    assert "INV-KM-1" in keluar and "INV-KM-2" in keluar and "INV-KM-3" in keluar, keluar
    # bukti-merah penjaga: hapus satu baris pencairan kas Oktober → INV-KM-3 (dan INV-KM-2: kas tidak lagi cocok) FAIL
    await db.fact_collections.delete_one({"_id": ids[2]})
    await vdi.layer_incentive_invariants(db)
    keluar = capsys.readouterr().out
    assert vdi.results["fail"] == awal_fail + 2, keluar
    assert re.search(r"FAIL.*INV-KM-3", keluar) and re.search(r"FAIL.*INV-KM-2", keluar), keluar
    await incentive_facts.rebuild()


# ═══ Pelengkap (a) — komponen, definisi, rekonsiliasi "Semua PT", tugas terjadwal ═══════════════════════════════════
async def test_KMT1_a_komponen_per_pt(klien, kepala_admin):
    h = {**kepala_admin, "X-Entity-Id": KANDA}
    isi = {"code": "it3", "name": "Insentif Triwulan", "basis_period_type": "quarter", "columns": ["omzet", "harga"]}
    r = await klien.post("/api/incentive/components", headers=h, json=isi)
    assert r.status_code == 200, r.text
    c = r.json()
    assert (c["code"], c["entity_id"], c["taxable"], c["is_active"], c["basis_label"]) == (
        "IT3", KANDA, True, True, "Triwulanan")
    r = await klien.post("/api/incentive/components", headers=h, json=isi)
    assert (r.status_code, r.json()["detail"]) == (409, "Kode komponen sudah dipakai di PT ini.")
    assert (await klien.post("/api/incentive/components", headers={**kepala_admin, "X-Entity-Id": KSC},
                             json=isi)).status_code == 200   # PT lain boleh memakai kode yang sama
    r = await klien.post("/api/incentive/components", headers=h, json={**isi, "code": "X Y"})
    assert r.status_code == 400
    r = await klien.post("/api/incentive/components", headers=h, json={**isi, "code": "IT4", "columns": []})
    assert r.status_code == 400
    r = await klien.patch(f"/api/incentive/components/{c['id']}", headers=h, json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False, r.text
    r = await klien.patch(f"/api/incentive/components/{c['id']}", headers={**kepala_admin, "X-Entity-Id": KSC},
                          json={"is_active": True})
    assert r.status_code in (403, 404), r.text   # komponen PT lain
    j = (await klien.get("/api/incentive/components", headers=h)).json()
    assert [x["code"] for x in j["items"]] == ["IT3"] and j["items"][0]["entity_id"] == KANDA


async def test_KMT1_a_semua_pt_hanya_baca(klien, kepala_admin):
    h = {**kepala_admin, "X-Entity-Id": "all"}
    assert (await klien.get("/api/incentive/reconciliation", headers=h)).json()["all_pt"] is True
    assert (await klien.post("/api/incentive/facts/rebuild", headers=h, json={})).status_code == 409
    assert (await klien.post("/api/incentive/components", headers=h, json={
        "code": "Z1", "name": "Z", "basis_period_type": "free", "columns": ["omzet"]})).status_code == 409


async def test_KMT1_a_tugas_terjadwal_dan_indeks():
    import indexes
    from services import incentive_facts
    from services.scheduler_service import JOB_MAP
    assert JOB_MAP["incentive_fact_sync"]["kind"] == "interval" and JOB_MAP["incentive_fact_sync"]["interval_minutes"] == 5
    assert (JOB_MAP["incentive_fact_nightly"]["hour"], JOB_MAP["incentive_fact_nightly"]["minute"]) == (2, 30)
    assert JOB_MAP["incentive_fact_sync"]["fn"] is incentive_facts.job_incentive_fact_sync
    nama = {(it["collection"], it["name"]): it for it in indexes.REQUIRED_UNIQUE_INDEXES}
    assert nama[("sales_targets", "uq_target_pt_sales_periode")]["keys"] == [
        ("entity_id", 1), ("sales_id", 1), ("period_type", 1), ("period", 1)]
    assert ("incentive_components", "uq_component_code") in nama
    assert ("incentive_definitions", "uq_definition_version") in nama
    res = await incentive_facts.job_incentive_fact_nightly()
    assert "Bangun ulang 90 hari" in res["detail"]
