"""Pelatihan Keuangan 18 Nov 2026 — uji adversarial O1 (tingkat tinggi, buku): PENEBUSAN SALDO KREDIT (store credit /
saldo retur) ke pesanan yang BELUM dikirim mengkredit 1-1200 Piutang Usaha langsung.

Data latihan: retur tukar barang peserta 43 → pesanan pengganti KSC/SO-00056 (status `reserved`, belum dikirim) dilunasi
penuh dengan saldo retur (KSC/SCR-…); jurnal KSC/JE-00211 Dr 2-1450 / Cr 1-1200 Rp 3.349.147,50 = persis selisih
rekonsiliasi Saldo & Umur (/ar/aging, "Selisih") dan INV-BAL-02 `ent_ksc Δ−3.349.147,50`. Piutang buku besar turun untuk
pesanan yang piutangnya belum lahir (pendapatan diakui saat surat jalan, KEB-PDPT).

Aturan yang ditiru (TIDAK ada mekanisme baru) = kwitansi kas (`gl_service._receipt_lines` + `_post_cash_transaction`):
  * alokasi ke pesanan yang melebihi piutang yang sudah lahir (`gl_service.order_ar_room`) = uang muka: Cr 2-1400, baris
    bayarnya ditandai `gl_bucket=advance` (`tag_advance_payment`);
  * pesanan yang SUDAH sebagian berpendapatan: porsi yang lahir langsung direklas ke piutang sesudah jurnal
    (`post_advance_reclass`, Dr 2-1400 / Cr 1-1200) → hasil bersihnya terpecah piutang vs uang muka;
  * surat jalan berikutnya mereklas sisanya (`post_order_revenue_and_cogs` → `post_advance_reclass`);
  * batal = pola `posting_registry.post_receipt_void`: pembalik reklas (`post_advance_reclass_reversal`) lalu pembalik
    jurnal penebusan → setiap akun kembali persis.

Hitung tangan (PT KSC, PKP 11%; pesanan 100 yd × Rp 10.000 = DPP Rp 1.000.000 + PPN Rp 110.000 = Rp 1.110.000):
  L1 belum dikirim, tebus Rp 1.110.000 → Dr 2-1450 1.110.000 / Cr 2-1400 1.110.000 (kode lama: Cr 1-1200 → selisih −1.110.000);
     surat jalan penuh: Dr 1-1200 1.110.000 (pendapatan) + reklas Dr 2-1400 / Cr 1-1200 1.110.000 → piutang 0 = pembantu;
     batal sesudah reklas → piutang 1.110.000 (pesanan kembali tertagih), uang muka 0, saldo kredit pulih.
  L2 dikirim 40 yd (piutang lahir 444.000), tebus 666.000 → bersih Cr 1-1200 444.000 · Cr 2-1400 222.000;
     surat jalan sisa 60 yd: Dr 1-1200 666.000 + reklas 222.000 → piutang 444.000 = sisa tagihan; batal → piutang
     1.110.000, uang muka 0.
  L3 batal sebelum dikirim → jurnal pembalik = cermin persis jurnal penebusan (Dr 2-1400 / Cr 2-1450).
Rekonsiliasi buku besar ↔ buku pembantu (`customer_balance_service.reconcile_gl`, angka layar Saldo & Umur) tidak
boleh berubah oleh satu pun langkah di atas.
"""
from __future__ import annotations

import uuid
from typing import Dict

import pytest

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"
DPP, PPN = 1_000_000.0, 110_000.0
GRAND = DPP + PPN
AKUN = ("1-1200", "2-1400", "2-1450")


def _id(awal: str) -> str:
    return f"{awal}_tsc_{uuid.uuid4().hex[:8]}"


async def _saldo(db) -> Dict[str, float]:
    """Saldo debit − kredit akun piutang / uang muka pelanggan / saldo kredit PT KSC (jurnal tidak-batal)."""
    out = {k: 0.0 for k in AKUN}
    async for je in db.journal_entries.find({"entity_id": KSC, "status": {"$ne": "void"},
                                             "lines.account_code": {"$in": list(AKUN)}}, {"_id": 0, "lines": 1}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") in out:
                out[ln["account_code"]] += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return {k: round(v, 2) for k, v in out.items()}


def _delta(a: Dict[str, float], b: Dict[str, float]) -> Dict[str, float]:
    return {k: round(b[k] - a[k], 2) for k in AKUN}


async def _selisih_tak_terjelaskan() -> float:
    from services import customer_balance_service as cbs
    return float((await cbs.reconcile_gl(KSC))["unexplained"])


async def _neto(db, flt: dict) -> Dict[str, float]:
    out: Dict[str, float] = {}
    async for je in db.journal_entries.find({**flt, "status": {"$ne": "void"}}, {"_id": 0, "lines": 1}):
        for ln in je.get("lines") or []:
            out[ln["account_code"]] = round(out.get(ln["account_code"], 0.0) + float(ln.get("debit") or 0)
                                            - float(ln.get("credit") or 0), 2)
    return {k: v for k, v in out.items() if abs(v) > 0.001}


@pytest.fixture(scope="module")
async def siap(db, kepala_admin):
    from services import store_credit_service as sc
    cid = _id("cus")
    await db.customers.insert_one({"id": cid, "name": "Latihan O1 · Toko Tukar Barang", "entity_id": KSC,
                                   "status": "active", "payment_profile": {}, "deposit_balance": 0.0,
                                   "assigned_sales_id": ""})
    # saldo retur (Nota Kredit retur → Cr 2-1450) — sisi jurnal terbit di luar uji ini; cukup saldo bukunya
    await sc.issue(customer_id=cid, entity_id=KSC, amount=10_000_000, ref_type="uji", ref_id=_id("ret"),
                   note="saldo retur uji O1")
    return {"h": kepala_admin, "cid": cid}


async def _pesanan(db, siap, status: str = "reserved") -> dict:
    so = {"id": _id("so"), "number": f"KSC/SO-O1-{uuid.uuid4().hex[:5]}", "entity_id": KSC, "customer_id": siap["cid"],
          "customer_name": "Latihan O1 · Toko Tukar Barang", "status": status, "grand_total": GRAND,
          "total_amount": GRAND, "subtotal": DPP, "ppn_amount": PPN, "payments": [], "paid_total": 0.0,
          "payment_status": "unpaid", "payment_term_code": "NET30", "payment_term_days": 30,
          "items": [{"product_id": "prd_o1", "quantity": 100, "unit_price": 10_000, "line_total": DPP}],
          "created_at": "2026-11-02T03:00:00+00:00", "confirmed_at": "2026-11-02T03:00:00+00:00"}
    await db.sales_orders.insert_one(dict(so))
    return so


async def _kirim(db, so: dict, qty: float, status: str) -> None:
    """Surat jalan terbit → jalur jurnal yang sama dengan layar (`post_order_revenue_and_cogs`: pendapatan pro-rata per
    surat jalan + reklas uang muka)."""
    from services import gl_service as gl
    await db.shipments.insert_one({"id": _id("shp"), "shipment_no": f"SJ-O1-{uuid.uuid4().hex[:4]}",
                                   "order_id": so["id"], "entity_id": KSC, "product_id": "prd_o1", "qty": qty,
                                   "status": "dispatched", "created_at": "2026-11-05T03:00:00+00:00"})
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"status": status}})
    await gl.post_order_revenue_and_cogs(so["id"])


async def _tebus(klien, siap, so: dict, nilai: float) -> dict:
    r = await klien.post("/api/store-credit/redeem", headers=siap["h"], json={
        "customer_id": siap["cid"], "entity_id": KSC, "amount": nilai,
        "allocations": [{"order_id": so["id"], "amount": nilai}], "note": "saldo retur untuk pesanan pengganti"})
    assert r.status_code == 200, r.text
    return r.json()


async def _batal(klien, siap, red: dict) -> None:
    r = await klien.post(f"/api/store-credit/entries/{red['ledger_entry_id']}/reverse", headers=siap["h"],
                         json={"reason": "uji O1 batal"})
    assert r.status_code == 200, r.text


async def _cermin(db, red_id: str) -> None:
    """Jurnal pembalik penebusan = cermin persis jurnal penebusan."""
    asal = await _neto(db, {"source_type": "store_credit_redeem", "source_id": red_id})
    balik = await _neto(db, {"source_type": "store_credit_redeem_reversal", "source_id": red_id})
    assert asal and balik == {k: -v for k, v in asal.items()}, (asal, balik)


async def test_O1_L1_tebus_pesanan_belum_dikirim_jadi_uang_muka_lalu_reklas_saat_kirim(klien, db, siap):
    from services import store_credit_service as sc
    so = await _pesanan(db, siap)
    s0, x0 = await _saldo(db), await _selisih_tak_terjelaskan()
    kredit0 = await sc.balance(siap["cid"], KSC)

    red = await _tebus(klien, siap, so, GRAND)
    # kode lama: {"2-1450": 1.110.000, "1-1200": −1.110.000} — piutang buku besar minus untuk pesanan belum terkirim
    assert await _neto(db, {"source_type": "store_credit_redeem", "source_id": red["id"]}) == \
        {"2-1450": GRAND, "2-1400": -GRAND}
    o = await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert [(p["amount"], p.get("gl_bucket")) for p in o["payments"]] == [(GRAND, "advance")]
    assert _delta(s0, await _saldo(db)) == {"1-1200": 0.0, "2-1400": -GRAND, "2-1450": GRAND}
    assert await _selisih_tak_terjelaskan() == x0   # kode lama: berubah −1.110.000 (= "Selisih" layar Saldo & Umur)

    # surat jalan penuh → pendapatan Dr 1-1200 + reklas uang muka Dr 2-1400 / Cr 1-1200 (pesanan sudah lunas)
    await _kirim(db, so, 100, "shipped")
    assert _delta(s0, await _saldo(db)) == {"1-1200": 0.0, "2-1400": 0.0, "2-1450": GRAND}
    assert await _selisih_tak_terjelaskan() == x0

    # batal sesudah reklas → pembalik reklas + pembalik penebusan: pesanan kembali tertagih penuh
    await _batal(klien, siap, red)
    assert _delta(s0, await _saldo(db)) == {"1-1200": GRAND, "2-1400": 0.0, "2-1450": 0.0}
    assert await _selisih_tak_terjelaskan() == x0
    assert await sc.balance(siap["cid"], KSC) == kredit0
    assert await _neto(db, {"source_type": "advance_reclass_reversal", "source_id": f"{so['id']}:{red['id']}"}) == \
        {"1-1200": GRAND, "2-1400": -GRAND}
    await _cermin(db, red["id"])


async def test_O1_L2_tebus_pesanan_dikirim_sebagian_dipecah_piutang_dan_uang_muka(klien, db, siap):
    from services import store_credit_service as sc
    so = await _pesanan(db, siap, status="confirmed")
    await _kirim(db, so, 40, "partially_shipped")          # piutang lahir 40% × 1.110.000 = 444.000
    lahir = round(GRAND * 0.4, 2)
    s0, x0 = await _saldo(db), await _selisih_tak_terjelaskan()
    kredit0 = await sc.balance(siap["cid"], KSC)

    tebus = round(GRAND * 0.6, 2)                          # 666.000 > piutang lahir 444.000
    red = await _tebus(klien, siap, so, tebus)
    # hasil bersih (jurnal penebusan + reklas seketika, pola kwitansi kas): Cr piutang sebesar yang lahir, sisanya uang muka
    assert _delta(s0, await _saldo(db)) == {"1-1200": -lahir, "2-1400": -round(tebus - lahir, 2), "2-1450": tebus}
    assert await _selisih_tak_terjelaskan() == x0          # kode lama & tanpa reklas seketika: berubah

    await _kirim(db, so, 60, "shipped")                   # surat jalan penutup: sisa uang muka direklas
    s2 = await _saldo(db)
    assert _delta(s0, s2) == {"1-1200": round(GRAND - lahir - tebus, 2), "2-1400": 0.0, "2-1450": tebus}
    assert round(s2["1-1200"] - s0["1-1200"] + lahir, 2) == round(GRAND - tebus, 2)   # piutang pesanan = sisa tagihan
    assert await _selisih_tak_terjelaskan() == x0

    await _batal(klien, siap, red)
    assert _delta(s0, await _saldo(db)) == {"1-1200": round(GRAND - lahir, 2), "2-1400": 0.0, "2-1450": 0.0}
    assert await _selisih_tak_terjelaskan() == x0
    assert await sc.balance(siap["cid"], KSC) == kredit0
    await _cermin(db, red["id"])


async def test_O1_L3_batal_sebelum_dikirim_kebalikan_persis(klien, db, siap):
    so = await _pesanan(db, siap)
    s0, x0 = await _saldo(db), await _selisih_tak_terjelaskan()
    red = await _tebus(klien, siap, so, 500_000)
    assert _delta(s0, await _saldo(db)) == {"1-1200": 0.0, "2-1400": -500_000.0, "2-1450": 500_000.0}
    await _batal(klien, siap, red)
    assert _delta(s0, await _saldo(db)) == {"1-1200": 0.0, "2-1400": 0.0, "2-1450": 0.0}
    assert await _selisih_tak_terjelaskan() == x0
    await _cermin(db, red["id"])
    o = await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert round(sum(float(p["amount"]) for p in o["payments"]), 2) == 0.0
    assert {p.get("gl_bucket") for p in o["payments"]} == {"advance"}   # baris pembalik ikut ber-bucket uang muka
