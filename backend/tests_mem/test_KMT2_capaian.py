"""KM-T2 — layar Capaian: cari, telusur, dan jumlahkan angka dasar insentif per sales (lingkungan B).

Spesifikasi `docs/blueprint/unit/KM-T2.md`, uji penerimaan U1–U15 (U16 = uji komponen jest
`features/__tests__/kmt2Capaian.test.js`; U17 = uji jalan peramban oleh integrator).

Fixture **F2** (rancangan `05` §4.2) di `ent_kanda` (non-PKP, tahun buku kalender) — DISISIPKAN langsung (pesanan,
surat jalan, retur & nota kredit), jurnal pendapatan diterbitkan `gl_service.post_order_revenue_and_cogs` /
`post_sales_return`, kwitansi lewat fungsi kwitansi asli `ar_receipt_service.create_receipt`, target lewat
`incentive_targets.save_target`, lalu fakta dibangun ulang (`incentive_facts.rebuild`, `analytics_facts.rebuild_facts`).
Semua harga jual Rp 50.000/yd, biaya Rp 35.000/yd.

Hitung tangan (masukan → langkah → hasil):
  OA0 Andi 52.000 yd × 50.000 = 2.600.000.000; list 56.800 → acuan 2.600 jt × 56.800/50.000 = 2.953.600.000;
      dibuat 3 Agu, terkirim penuh 14 Agu.
  OA1 Andi 20.000 yd × 50.000 = 1.000.000.000; list 58.000 → acuan 1.000 jt × 58/50 = 1.160.000.000; biaya
      20.000 × 35.000 = 700.000.000; dibuat 28 Sep, terkirim penuh 12 Okt.
  OB0 Budi 400 yd = 20.000.000 (list 50.000), terkirim 20 Sep. OB1 Budi 10.000 yd = 500.000.000 (list 50.000), 9 Okt.
  Kwitansi: RA0 10 Sep 2.300 jt → OA0 · RA1 20 Okt 700 jt → OA1 · RB1 15 Okt 500 jt → OB1 · RB0 16 Okt 20 jt → OB0.
  Target: Andi 2026-10 800 jt / 750 jt · Andi 2026-Q3 2.400 jt / 2.250 jt · Budi 2026-10 500 jt / 450 jt.

  U1 Andi Okt: omzet 1.000 jt; % = 1.000/800 = 125,0; uang masuk 700 jt; % = 700/750 = 93,33 → 93,3.
  U2 Andi Okt: realisasi 1.000/1.160 = 86,21 → 86,2; potongan 100 − 86,21 = 13,79 → 13,8; di bawah acuan 100,0
      (net 1.000 jt < acuan 1.160 jt); margin (1.000 − 700)/1.000 = 30,0.
  U3 Budi Okt: omzet 500 jt; % 100,0; uang masuk 500 + 20 = 520 jt; % 520/450 = 115,56 → 115,6; realisasi 100,0;
      di bawah acuan 0,0 (net = acuan, bukan di bawah).
  U4 Andi 2026-Q3 (1 Jul–30 Sep): target triwulan 2.400 jt (angka tersendiri); omzet OA0 2.600 jt → 108,33 → 108,3;
      uang masuk RA0 2.300 jt → 2.300/2.250 = 102,22 → 102,2; realisasi 2.600/2.953,6 = 88,03 → 88,0.
  U7 Budi pembanding September: OB0 20 jt (omzet bersih).
  U8 dasar omzet "pesanan": Andi Okt 0 (OA1 dibuat 28 Sep, OA0 3 Agu); Sep 1.000 jt.
  U9 retur 50 jt atas OA1 25 Okt: omzet bersih 1.000 − 50 = 950 jt; % 950/800 = 118,75 → 118,8.
  U10 kumulatif Okt (1 Jan–31 Okt): omzet 2.600 + 1.000 = 3.600 jt; target = Σ target BULANAN dalam rentang = 800 jt
      (target triwulan Q3 bukan target bulanan).
"""
from __future__ import annotations

import io
import re
from typing import Any, Dict

import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI

pytestmark = pytest.mark.anyio

KANDA = "ent_kanda"
PRD = "prd_kmt2_kain"
CA, CB, CS = "cus_kmt2_andi", "cus_kmt2_budi", "cus_kmt2_senior"
OA0, OA1, OB0, OB1, OS1 = "so_kmt2_oa0", "so_kmt2_oa1", "so_kmt2_ob0", "so_kmt2_ob1", "so_kmt2_os1"
REK = "rek_kmt2_b"
OKT = {"period_type": "month", "period": "2026-10"}


def _iso(tgl: str, jam: str = "03:00:00") -> str:
    return f"{tgl}T{jam}+00:00"


def _item(qty: int, list_price: float) -> Dict[str, Any]:
    return {"product_id": PRD, "sku": "KMT2-01", "product_name": "Kain Uji KM-T2", "quantity": qty, "base_quantity": qty,
            "unit": "yard", "base_unit": "yard", "price": 50_000, "line_total": qty * 50_000, "list_price": list_price,
            "list_price_source": "entity", "global_price": 60_000, "floor_price": 45_000, "unit_cost": 35_000,
            "price_source": "entity", "category": "Katun", "line_code": "woven"}


async def _pesanan_terkirim(db, gl, so_id: str, cust: str, sales_id: str, qty: int, list_price: float,
                            dibuat: str, dikirim: str) -> None:
    """Pesanan satu baris, terkirim penuh dengan satu surat jalan; jurnal pendapatan lewat fungsi posting asli."""
    nomor = f"SO/KMT2/{so_id[-3:].upper()}"
    await db.sales_orders.insert_one({
        "id": so_id, "number": nomor, "entity_id": KANDA, "customer_id": cust, "customer_name": f"Toko {cust[-5:]}",
        "status": "shipped", "payment_term_code": "NET30", "items": [_item(qty, list_price)], "subtotal": qty * 50_000,
        "grand_total": qty * 50_000, "ppn_amount": 0, "payments": [], "paid_total": 0.0, "payment_status": "unpaid",
        "sales_team": [{"sales_id": sales_id, "role": "pic", "split_pct": 100.0}],
        "created_at": _iso(dibuat), "updated_at": now_iso()})
    await db.shipments.insert_one({"id": f"shp_{so_id}", "shipment_no": f"SJ/KMT2/{so_id[-3:].upper()}",
                                   "entity_id": KANDA, "order_id": so_id, "order_number": nomor, "product_id": PRD,
                                   "qty": qty, "unit": "yard", "status": "dispatched", "created_at": _iso(dikirim)})
    await gl.post_order_revenue_and_cogs(so_id)


async def _bangun_ulang() -> None:
    from services import analytics_facts, incentive_facts
    await incentive_facts.rebuild()
    await analytics_facts.rebuild_facts()


@pytest.fixture(scope="module")
async def f2(db, akun):
    from services import ar_receipt_service as ars
    from services import config_resolver as resolver
    from services import gl_service as gl
    from services import incentive_targets as itg
    await resolver.set_value("payment.variance_tolerance_rupiah", 0, scope_type="entity", scope_id=KANDA, actor="uji",
                             reason="uji KM-T2")
    await db.bank_accounts.insert_one({"id": REK, "name": "BCA Kanda KM-T2", "entity_id": KANDA, "account_type": "bank",
                                       "cash_type": "kas_besar", "is_active": True, "opening_balance": 0})
    andi = await akun("sales", entitas=(KANDA,))
    budi = await akun("sales", entitas=(KANDA,))
    for u, nama in ((andi, "Andi KMT2"), (budi, "Budi KMT2")):
        await db.users.update_one({"id": u["id"]}, {"$set": {"name": nama}})
        u["name"] = nama
    await db.products.insert_one({"id": PRD, "name": "Kain Uji KM-T2", "sku": "KMT2-01", "base_unit": "yard",
                                  "price": 60_000, "category": "Katun", "line_code": "woven", "is_active": True})
    await db.customers.insert_many([
        {"id": CA, "name": "Toko Andi KM-T2", "entity_id": KANDA, "status": "active", "deposit_balance": 0.0,
         "assigned_sales_id": andi["id"], "created_at": _iso("2026-01-05"),
         "sales_team": [{"sales_id": andi["id"], "role": "pic", "split_pct": 100.0}]},
        {"id": CB, "name": "Toko Budi KM-T2", "entity_id": KANDA, "status": "active", "deposit_balance": 0.0,
         "assigned_sales_id": budi["id"], "created_at": _iso("2026-10-02"),
         "sales_team": [{"sales_id": budi["id"], "role": "pic", "split_pct": 100.0}]}])
    await _pesanan_terkirim(db, gl, OA0, CA, andi["id"], 52_000, 56_800, "2026-08-03", "2026-08-14")
    await _pesanan_terkirim(db, gl, OA1, CA, andi["id"], 20_000, 58_000, "2026-09-28", "2026-10-12")
    await _pesanan_terkirim(db, gl, OB0, CB, budi["id"], 400, 50_000, "2026-09-15", "2026-09-20")
    await _pesanan_terkirim(db, gl, OB1, CB, budi["id"], 10_000, 50_000, "2026-10-05", "2026-10-09")
    rc: Dict[str, str] = {}
    for nama, cust, so, nilai, tgl in (("RA0", CA, OA0, 2_300_000_000, "2026-09-10"),
                                       ("RA1", CA, OA1, 700_000_000, "2026-10-20"),
                                       ("RB1", CB, OB1, 500_000_000, "2026-10-15"),
                                       ("RB0", CB, OB0, 20_000_000, "2026-10-16")):
        r = await ars.create_receipt({"customer_id": cust, "entity_id": KANDA, "amount": nilai, "method": "transfer",
                                      "account_id": REK, "allocations": [{"order_id": so, "amount": nilai}],
                                      "receipt_date": tgl}, AKTOR_UJI)
        rc[nama] = r["id"]
    for sid, pt, p, omzet, cair in ((andi["id"], "month", "2026-10", 800e6, 750e6),
                                    (andi["id"], "quarter", "2026-Q3", 2_400e6, 2_250e6),
                                    (budi["id"], "month", "2026-10", 500e6, 450e6)):
        await itg.save_target(KANDA, {"sales_id": sid, "period_type": pt, "period": p, "target_sales_amount": omzet,
                                      "target_collection_amount": cair}, AKTOR_UJI)
    await _bangun_ulang()
    return {"andi": andi, "budi": budi, **rc}


async def _capaian(klien, h, **params):
    r = await klien.get("/api/incentive/achievement", headers={**h, "X-Entity-Id": KANDA}, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _baris(j: Dict[str, Any], sales_id: str) -> Dict[str, Any]:
    rows = [r for r in j["rows"] if r.get("sales_id") == sales_id]
    assert len(rows) == 1, j["rows"]
    return rows[0]


# ═══ U1–U3 — Oktober per sales ══════════════════════════════════════════════════════════════════════════════════════
async def test_KMT2_U1_andi_oktober(klien, kepala_admin, f2):
    j = await _capaian(klien, kepala_admin, **OKT)
    a = _baris(j, f2["andi"]["id"])
    assert (a["target_sales"], a["omzet"], a["retur"], a["omzet_bersih"], a["pct_omzet"]) == (
        800_000_000, 1_000_000_000, 0, 1_000_000_000, 125.0), a
    assert (a["target_collection"], a["uang_masuk"], a["pct_pencairan"]) == (750_000_000, 700_000_000, 93.3), a
    assert a["name"] == "Andi KMT2" and a["jumlah_pesanan"] == 1
    # piutang per 31 Okt (PK-41, per surat jalan, NET30): OA0 2.600 − 2.300 = 300 jt jatuh tempo 13 Sep (lewat);
    # OA1 1.000 − 700 = 300 jt jatuh tempo 11 Nov (belum) → sisa 600 jt, lewat tempo 300 jt
    assert (a["sisa_piutang"], a["lewat_tempo"], j["piutang_as_of"]) == (600_000_000, 300_000_000, "2026-10-31"), a
    assert (j["entity_id"], j["period"]["date_from"], j["period"]["date_to"], j["period"]["type"]) == (
        KANDA, "2026-10-01", "2026-10-31", "month")
    d = j["definition"]
    assert (d["dasar_omzet"], d["isi_pencairan"], d["pemilik_angka"], d["harga_acuan"]) == (
        "terkirim", "uang_masuk", "sales_pesanan", "daftar_pt"), d
    assert d["version"] >= 1 and d["labels"] and j["facts_as_of"]
    # angka per sales tercocokkan dengan pembukuan (jurnal & kas fixture diterbitkan fungsi asli)
    assert j["reconciliation"] == {"omzet_ok": True, "omzet_diff": 0, "pencairan_ok": True, "pencairan_diff": 0}, \
        j["reconciliation"]
    # D5 — total = Σ baris (uang dalam rupiah bulat)
    for k in ("omzet", "retur", "omzet_bersih", "uang_masuk", "target_sales", "target_collection"):
        assert j["totals"][k] == sum(r[k] for r in j["rows"] if r.get(k) is not None), k


async def test_KMT2_U2_kualitas_harga_andi(klien, kepala_admin, f2):
    a = _baris(await _capaian(klien, kepala_admin, **OKT), f2["andi"]["id"])
    assert (a["realisasi_harga_pct"], a["rata_potongan_pct"], a["porsi_bawah_acuan_pct"], a["margin_pct"]) == (
        86.2, 13.8, 100.0, 30.0), a


async def test_KMT2_U3_budi_oktober(klien, kepala_admin, f2):
    b = _baris(await _capaian(klien, kepala_admin, **OKT), f2["budi"]["id"])
    assert (b["omzet"], b["pct_omzet"], b["uang_masuk"], b["pct_pencairan"]) == (
        500_000_000, 100.0, 520_000_000, 115.6), b
    assert (b["realisasi_harga_pct"], b["porsi_bawah_acuan_pct"]) == (100.0, 0.0), b
    assert (b["pelanggan_baru"], b["jumlah_pesanan"]) == (1, 1), b   # Toko Budi dibuat 2 Okt


# ═══ U4 — triwulan: target tersendiri ═══════════════════════════════════════════════════════════════════════════════
async def test_KMT2_U4_triwulan_andi(klien, kepala_admin, f2):
    j = await _capaian(klien, kepala_admin, period_type="quarter", period="2026-Q3")
    a = _baris(j, f2["andi"]["id"])
    assert (a["target_sales"], a["omzet"], a["pct_omzet"]) == (2_400_000_000, 2_600_000_000, 108.3), a
    assert (a["uang_masuk"], a["pct_pencairan"], a["realisasi_harga_pct"]) == (2_300_000_000, 102.2, 88.0), a
    assert (j["period"]["date_from"], j["period"]["date_to"]) == ("2026-07-01", "2026-09-30")


# ═══ U5–U6 — telusur sampai dokumen ═════════════════════════════════════════════════════════════════════════════════
async def _sumber(klien, h, **params):
    r = await klien.get("/api/incentive/achievement/sources", headers={**h, "X-Entity-Id": KANDA}, params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def test_KMT2_U5_telusur_uang_masuk_budi(klien, kepala_admin, f2):
    j = await _sumber(klien, kepala_admin, **OKT, metric="uang_masuk", sales_id=f2["budi"]["id"])
    assert (j["total"], j["sum"]) == (2, 520_000_000), j
    assert sorted(i["doc_id"] for i in j["items"]) == sorted([f2["RB1"], f2["RB0"]])
    assert {i["doc_type"] for i in j["items"]} == {"ar_receipt"}
    assert sorted(i["amount"] for i in j["items"]) == [20_000_000, 500_000_000]
    assert all(i["link"]["view"] and i["link"]["focus_id"] for i in j["items"]), j["items"]
    b = _baris(await _capaian(klien, kepala_admin, **OKT), f2["budi"]["id"])
    assert j["sum"] == b["uang_masuk"]   # D4 — jumlah daftar = angka sel yang dibuka
    # halaman: satu baris per halaman, jumlah total tetap
    j1 = await _sumber(klien, kepala_admin, **OKT, metric="uang_masuk", sales_id=f2["budi"]["id"], page=2, page_size=1)
    assert (j1["total"], j1["sum"], len(j1["items"])) == (2, 520_000_000, 1)


async def test_KMT2_U6_telusur_omzet_andi(klien, kepala_admin, f2):
    j = await _sumber(klien, kepala_admin, **OKT, metric="omzet", sales_id=f2["andi"]["id"])
    assert (j["total"], j["sum"]) == (1, 1_000_000_000), j
    it = j["items"][0]
    assert (it["doc_type"], it["doc_id"], it["amount"], it["so_id"], it["date_wib"]) == (
        "shipment", f"shp_{OA1}", 1_000_000_000, OA1, "2026-10-12"), it
    assert it["link"]["focus_id"] == OA1 and it["doc_number"] == "SJ/KMT2/OA1"   # surat jalan dibuka lewat pesanannya
    r = await klien.get("/api/incentive/achievement/sources", headers={**kepala_admin, "X-Entity-Id": KANDA},
                        params={**OKT, "metric": "margin", "sales_id": f2["andi"]["id"]})
    assert r.status_code == 400, r.text


# ═══ U7 — pembanding periode sebelumnya ═════════════════════════════════════════════════════════════════════════════
async def test_KMT2_U7_bandingkan_bulan_sebelumnya(klien, kepala_admin, f2):
    j = await _capaian(klien, kepala_admin, **OKT, compare="prev")
    budi = f2["budi"]["id"]
    assert j["compare"]["by_key"][budi]["omzet_bersih"] == 20_000_000, j["compare"]
    assert j["compare"]["by_key"][budi]["uang_masuk"] == 0
    assert j["compare"]["label"] == "Sep 2026" and j["compare"]["date_from"] == "2026-09-01"
    j2 = await _capaian(klien, kepala_admin, **OKT, compare="yoy")
    assert j2["compare"]["date_from"] == "2025-10-01" and j2["compare"]["by_key"].get(budi, {}).get("omzet_bersih", 0) == 0


# ═══ U8 — definisi omzet "saat pesanan dibuat" ══════════════════════════════════════════════════════════════════════
async def test_KMT2_U8_dasar_omzet_pesanan(klien, kepala_admin, f2):
    from services import config_resolver as resolver
    v0 = (await _capaian(klien, kepala_admin, **OKT))["definition"]["version"]
    await resolver.set_value("insentif.dasar_omzet", "pesanan", scope_type="entity", scope_id=KANDA, actor="uji",
                             reason="uji KM-T2 U8")
    try:
        okt = await _capaian(klien, kepala_admin, **OKT)
        sep = await _capaian(klien, kepala_admin, period_type="month", period="2026-09")
        andi = f2["andi"]["id"]
        assert _baris(okt, andi)["omzet"] == 0, _baris(okt, andi)
        assert _baris(sep, andi)["omzet"] == 1_000_000_000, _baris(sep, andi)
        assert (okt["definition"]["version"], okt["definition"]["dasar_omzet"]) == (v0 + 1, "pesanan")
        s = await _sumber(klien, kepala_admin, period_type="month", period="2026-09", metric="omzet", sales_id=andi)
        assert [(i["doc_type"], i["doc_id"], i["amount"]) for i in s["items"]] == [("sales_order", OA1, 1_000_000_000)]
    finally:
        await resolver.clear_layer("insentif.dasar_omzet", scope_type="entity", scope_id=KANDA, actor="uji",
                                   reason="uji KM-T2 U8 selesai")
    assert _baris(await _capaian(klien, kepala_admin, **OKT), f2["andi"]["id"])["omzet"] == 1_000_000_000


# ═══ U9 — retur mengurangi omzet bersih ═════════════════════════════════════════════════════════════════════════════
async def test_KMT2_U9_retur_oktober(klien, kepala_admin, db, f2):
    from services import gl_service as gl
    from services import incentive_facts
    ret = {"id": "sr_kmt2_1", "number": "RJ/KMT2/1", "entity_id": KANDA, "order_id": OA1, "order_number": "SO/KMT2/OA1",
           "customer_id": CA, "status": "settled", "approved_at": _iso("2026-10-25"), "items": [],
           "credit_note_id": "cn_kmt2_1", "created_at": _iso("2026-10-24")}
    await db.sales_returns.insert_one(dict(ret))
    await db.credit_notes.insert_one({
        "id": "cn_kmt2_1", "number": "CN/KMT2/1", "return_id": ret["id"], "order_id": OA1,
        "order_number": "SO/KMT2/OA1", "customer_id": CA, "entity_id": KANDA,
        "lines": [{"product_id": PRD, "quantity": 1000, "unit": "yard", "unit_price": 50_000, "line_total": 50_000_000}],
        "net_amount": 50_000_000, "ppn_amount": 0, "gross_amount": 50_000_000, "cogs_amount": 35_000_000,
        "settlement": "ar", "status": "posted", "created_at": _iso("2026-10-25", "04:00:00")})
    await gl.post_sales_return(ret, return_net=50_000_000, return_ppn=0, return_cogs=35_000_000,
                               credit_note_number="CN/KMT2/1")
    await incentive_facts.rebuild()
    j = await _capaian(klien, kepala_admin, **OKT)
    a = _baris(j, f2["andi"]["id"])
    assert (a["retur"], a["omzet_bersih"], a["pct_omzet"]) == (50_000_000, 950_000_000, 118.8), a
    assert j["reconciliation"]["omzet_ok"] is True, j["reconciliation"]
    s = await _sumber(klien, kepala_admin, **OKT, metric="retur", sales_id=f2["andi"]["id"])
    assert [(i["doc_type"], i["doc_id"], i["amount"]) for i in s["items"]] == [("credit_note", "cn_kmt2_1", 50_000_000)]
    assert s["sum"] == a["retur"]


# ═══ U10 — kumulatif tahun berjalan ═════════════════════════════════════════════════════════════════════════════════
async def test_KMT2_U10_kumulatif(klien, kepala_admin, f2):
    j = await _capaian(klien, kepala_admin, **OKT, cumulative="true")
    a = _baris(j, f2["andi"]["id"])
    assert (a["omzet"], a["target_sales"]) == (3_600_000_000, 800_000_000), a
    assert (j["period"]["date_from"], j["period"]["date_to"], j["period"]["cumulative"]) == (
        "2026-01-01", "2026-10-31", True)
    r = await klien.get("/api/incentive/achievement", headers={**kepala_admin, "X-Entity-Id": KANDA},
                        params={"period_type": "quarter", "period": "2026-Q3", "cumulative": "true"})
    assert r.status_code == 400, r.text


# ═══ U11–U13 — izin, margin, Semua PT, galat ════════════════════════════════════════════════════════════════════════
async def test_KMT2_U11_tanpa_izin_margin(klien, akun, sesi, peran_tanpa_acuan, f2):
    u = await akun(await peran_tanpa_acuan({"incentive": ["view"]}, label="Lihat Capaian"), entitas=(KANDA,))
    h = await sesi(u, entitas=KANDA)
    j = await _capaian(klien, h, **OKT)
    assert j["rows"] and not [r for r in j["rows"] if "margin_pct" in r], j["rows"]
    assert "margin_pct" not in j["totals"]
    r = await klien.get("/api/incentive/achievement/export", headers=h, params=OKT)
    assert r.status_code == 200, r.text
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(r.content))
    kepala = [c.value for c in wb["Capaian"][2]]
    assert "Margin" not in kepala, kepala


async def test_KMT2_U12_tanpa_izin_ditolak(klien, akun, sesi, peran_manajer_kosong, peran_sopir, f2):
    for peran in (await peran_manajer_kosong(), peran_sopir):
        h = await sesi(await akun(peran, entitas=(KANDA,)), entitas=KANDA)
        for ep, extra in (("/api/incentive/achievement", {}),
                          ("/api/incentive/achievement/sources", {"metric": "omzet", "sales_id": f2["andi"]["id"]}),
                          ("/api/incentive/achievement/export", {})):
            r = await klien.get(ep, headers=h, params={**OKT, **extra})
            assert r.status_code == 403, (peran, ep, r.text)
            d = r.json()["detail"]
            assert d.startswith("Anda belum punya akses untuk") and "'Kinerja & Insentif'" in d, d
            assert not re.search(r"incentive\.|[a-z]+_[a-z]+", d), d


async def test_KMT2_U13_semua_pt_dan_galat_periode(klien, kepala_admin, f2):
    h = {**kepala_admin, "X-Entity-Id": "all"}
    for ep in ("/api/incentive/achievement", "/api/incentive/achievement/export"):
        r = await klien.get(ep, headers=h, params=OKT)
        assert (r.status_code, r.json()["detail"]) == (
            400, "Pilih satu PT untuk melihat Capaian. Definisi angka berbeda di tiap PT."), r.text
    hk = {**kepala_admin, "X-Entity-Id": KANDA}
    r = await klien.get("/api/incentive/achievement", headers=hk, params={"period_type": "quarter", "period": "2026-10"})
    assert (r.status_code, r.json()["detail"]) == (400, "Periode tidak sesuai jenisnya. Contoh: 2026-10, 2026-Q4, atau 2026.")
    r = await klien.get("/api/incentive/achievement", headers=hk,
                        params={"period_type": "range", "date_from": "2026-01-01", "date_to": "2027-01-05"})
    assert (r.status_code, r.json()["detail"]) == (400, "Rentang tanggal paling panjang 366 hari.")
    r = await klien.get("/api/incentive/achievement", headers=hk,
                        params={"period_type": "range", "date_from": "2026-10-01", "date_to": "2026-10-31"})
    assert r.status_code == 200, r.text
    assert _baris(r.json(), f2["budi"]["id"])["omzet"] == 500_000_000
    assert _baris(r.json(), f2["budi"]["id"])["target_sales"] == 500_000_000   # bulan penuh dalam rentang


# ═══ U14 — ekspor Excel tiga lembar ═════════════════════════════════════════════════════════════════════════════════
async def test_KMT2_U14_ekspor_excel(klien, kepala_admin, f2):
    from openpyxl import load_workbook
    r = await klien.get("/api/incentive/achievement/export", headers={**kepala_admin, "X-Entity-Id": KANDA}, params=OKT)
    assert r.status_code == 200, r.text
    assert re.search(r'filename="capaian-[^"]+-2026-10\.xlsx"', r.headers["content-disposition"]), r.headers
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Definisi", "Capaian", "Dokumen"]
    definisi = [c for row in wb["Definisi"].iter_rows(values_only=True) for c in row if c is not None]
    teks = " ".join(str(c) for c in definisi)
    assert "terkirim" in teks and "Versi definisi" in teks, teks
    versi = (await _capaian(klien, kepala_admin, **OKT))["definition"]["version"]
    assert versi in definisi, definisi
    ws = wb["Capaian"]
    kepala = [c.value for c in ws[2]]
    kol_omzet = kepala.index("Omzet")
    andi = next(row for row in ws.iter_rows(min_row=3, values_only=True) if row[0] == f2["andi"]["name"])
    assert andi[kol_omzet] == 1_000_000_000, (kepala, andi)
    assert "Margin" in kepala   # admin memegang incentive.view_margin
    dok = list(wb["Dokumen"].iter_rows(values_only=True))
    nomor = {row[4] for row in dok[1:]}
    assert {"SJ/KMT2/OA1", "CN/KMT2/1"} <= nomor, nomor
    # isi berkas = daftar yang sedang dilihat: cari "budi" → hanya baris Budi (+ Total), dokumen hanya milik Budi
    r = await klien.get("/api/incentive/achievement/export", headers={**kepala_admin, "X-Entity-Id": KANDA},
                        params={**OKT, "q": "budi", "only_numbers": "true"})
    wb = load_workbook(io.BytesIO(r.content))
    nama = [row[0] for row in wb["Capaian"].iter_rows(min_row=3, values_only=True)]
    assert nama == [f2["budi"]["name"], "Total"], nama
    nomor = {row[4] for row in list(wb["Dokumen"].iter_rows(values_only=True))[1:]}
    assert "SJ/KMT2/OA1" not in nomor and "SJ/KMT2/OB1" in nomor, nomor


# ═══ U15 — peran kustom beracuan sales ══════════════════════════════════════════════════════════════════════════════
async def test_KMT2_U15_peran_kustom_beracuan_sales(klien, kepala_admin, db, akun, f2):
    from services import gl_service as gl
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={
        "label": "Sales Senior KMT2", "base_role": "sales", "description": "peran uji KM-T2"})
    assert r.status_code == 200, r.text
    rid = (r.json().get("role") or r.json())["id"]
    senior = await akun(rid, entitas=(KANDA,))
    tanpa_angka = await akun(rid, entitas=(KANDA,))
    await db.customers.insert_one({"id": CS, "name": "Toko Senior KM-T2", "entity_id": KANDA, "status": "active",
                                   "assigned_sales_id": senior["id"], "created_at": _iso("2026-01-05")})
    await _pesanan_terkirim(db, gl, OS1, CS, senior["id"], 100, 50_000, "2026-10-01", "2026-10-03")
    await _bangun_ulang()
    j = await _capaian(klien, kepala_admin, **OKT)
    s = _baris(j, senior["id"])
    assert (s["name"], s["omzet"]) == (senior["name"], 5_000_000), s
    assert _baris(j, tanpa_angka["id"])["omzet"] == 0   # akun aktif berperan (acuan) sales tetap terdaftar


# ═══ Pelengkap — pengelompokan, saringan, pemilik pelanggan ═════════════════════════════════════════════════════════
async def test_KMT2_kelompok_dan_saringan(klien, kepala_admin, f2):
    j = await _capaian(klien, kepala_admin, **OKT, group_by="customer")
    per = {r["key"]: r for r in j["rows"]}
    assert per[CB]["omzet"] == 500_000_000 and per[CB]["uang_masuk"] == 520_000_000, per
    assert all("target_sales" not in r and "sisa_piutang" not in r and "pelanggan_baru" not in r for r in j["rows"])
    j = await _capaian(klien, kepala_admin, **OKT, group_by="price_source")
    assert [(r["name"], r["omzet"]) for r in j["rows"] if r["omzet"]] == [("Harga PT", 1_505_000_000)], j["rows"]
    assert all(r.get("uang_masuk") is None for r in j["rows"]) and j["notes"], j
    j = await _capaian(klien, kepala_admin, **OKT, **{"sales_id[]": [f2["budi"]["id"]]})
    assert [r["sales_id"] for r in j["rows"]] == [f2["budi"]["id"]], j["rows"]


async def test_KMT2_pemilik_pelanggan(klien, kepala_admin, db, f2):
    from services import config_resolver as resolver
    andi, budi = f2["andi"]["id"], f2["budi"]["id"]
    await db.customers.update_one({"id": CB}, {"$set": {"assigned_sales_id": andi}})   # Toko Budi kini dipegang Andi
    await resolver.set_value("insentif.pemilik_angka", "pemilik_pelanggan", scope_type="entity", scope_id=KANDA,
                             actor="uji", reason="uji KM-T2 pemilik pelanggan")
    try:
        j = await _capaian(klien, kepala_admin, period_type="month", period="2026-09")
        assert _baris(j, andi)["omzet"] == 20_000_000 and _baris(j, budi)["omzet"] == 0   # OB0 kini milik Andi
    finally:
        await resolver.clear_layer("insentif.pemilik_angka", scope_type="entity", scope_id=KANDA, actor="uji",
                                   reason="uji KM-T2 selesai")
        await db.customers.update_one({"id": CB}, {"$set": {"assigned_sales_id": budi}})
    j = await _capaian(klien, kepala_admin, period_type="month", period="2026-09")
    assert _baris(j, budi)["omzet"] == 20_000_000


async def test_KMT2_izin_margin_bawaan_dan_katalog():
    import access_modules as am
    from permissions_config import DEFAULT_PERMISSIONS
    assert "view_margin" in DEFAULT_PERMISSIONS["admin"]["incentive"]
    assert "view_margin" in DEFAULT_PERMISSIONS["manager"]["incentive"]
    assert "view_margin" not in (DEFAULT_PERMISSIONS["finance"].get("incentive") or [])
    assert am.ACTION_LABEL["incentive.view_margin"] == "Lihat margin"
    assert "incentive-capaian" in am.MODULE_BY_ID["incentive"]["nav"]
