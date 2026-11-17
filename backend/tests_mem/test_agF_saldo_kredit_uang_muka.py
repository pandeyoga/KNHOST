"""INV-BAL-02 di data latihan 18 Nov: `ent_ksc Δ−3.349.147,50` = KSC/SO-00056 (`reserved`, belum dikirim) dilunasi
penuh dengan SALDO KREDIT (KSC/SCR-00002). Jurnal penebusan selalu Dr 2-1450 / Cr 1-1200 Piutang, padahal pendapatan
pesanan itu belum lahir: piutang buku besar jadi minus untuk pesanan yang belum terkirim (piutang dokumen = 0). Kwitansi
kas dan deposit benar sejak KEB-PDPT (`gl_service._receipt_lines` / `post_deposit_only_receipt`: alokasi ke pesanan
yang belum berpendapatan = uang muka 2-1400, ditandai `gl_bucket=advance`, direklas ke piutang saat surat jalan).
Penebusan saldo kredit melewati aturan itu.

Langkah ulang (layar): Keuangan › Titipan & Saldo Kredit › [Pakai Saldo] ke pesanan yang belum dikirim → Buku Besar
1-1200 PT itu turun sebesar penebusan; INV-BAL-02 merah tanpa sebab yang dikenal.

Hitung tangan (PT `ent_kanda`, non-PKP): saldo kredit Rp 500.000; pesanan Rp 1.000.000 belum dikirim; tebus Rp 300.000
  → Dr 2-1450 300.000 / Cr 2-1400 300.000 (BUKAN Cr 1-1200); piutang buku besar pesanan = 0; baris bayar ber-`advance`.
  Surat jalan penuh Rp 1.000.000 (Dr 1-1200) + reklas uang muka (Dr 2-1400 / Cr 1-1200 300.000) → piutang 700.000,
  uang muka 0 — sama dengan pelunasan kas.
  Batal penebusan sesudah reklas → piutang kembali 1.000.000, uang muka 0, saldo kredit kembali 500.000.
Pesanan yang SUDAH dikirim tetap Cr 1-1200 (perilaku lama, tidak berubah).
"""
from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.anyio

KANDA = "ent_kanda"


def _id(awal: str) -> str:
    return f"{awal}_agfsc_{uuid.uuid4().hex[:8]}"


async def _saldo(kode: str, sumber: str = "") -> float:
    """Saldo (debit − kredit) akun di PT uji; `sumber` = hanya jurnal ber-source_id/ref pesanan itu (bila diisi)."""
    from db import db
    tot = 0.0
    async for je in db.journal_entries.find({"entity_id": KANDA, "status": {"$ne": "void"},
                                             "lines.account_code": kode}, {"_id": 0}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") == kode:
                tot += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return round(tot, 2)


async def _pelanggan_dan_pesanan(db, nilai: float, status: str = "confirmed") -> dict:
    from services import store_credit_service as sc
    cid = _id("cus")
    await db.customers.insert_one({"id": cid, "name": "Toko Uji Saldo Kredit", "entity_id": KANDA, "status": "active",
                                   "payment_profile": {}, "deposit_balance": 0.0, "assigned_sales_id": ""})
    await sc.issue(customer_id=cid, entity_id=KANDA, amount=500_000, ref_type="uji", ref_id=_id("ret"),
                   note="saldo kredit uji")
    so = {"id": _id("so"), "number": f"SO-AGFSC-{uuid.uuid4().hex[:5]}", "entity_id": KANDA, "customer_id": cid,
          "customer_name": "Toko Uji Saldo Kredit", "status": status, "grand_total": float(nilai),
          "total_amount": float(nilai), "ppn_amount": 0.0, "payments": [], "paid_total": 0.0,
          "payment_status": "unpaid", "payment_term_code": "NET30", "payment_term_days": 30, "items": [],
          "created_at": "2026-11-02T03:00:00+00:00", "confirmed_at": "2026-11-02T03:00:00+00:00"}
    await db.sales_orders.insert_one(dict(so))
    return so


async def _kirim(db, so: dict, nilai: float) -> None:
    from services import gl_service as gl
    shid = _id("shp")
    await db.shipments.insert_one({"id": shid, "shipment_no": "SJ-AGFSC", "order_id": so["id"], "entity_id": KANDA,
                                   "status": "dispatched", "created_at": "2026-11-05T03:00:00+00:00"})
    await gl._insert_entry(lines=[{"account_code": "1-1200", "debit": float(nilai), "credit": 0.0},
                                  {"account_code": "4-1000", "debit": 0.0, "credit": float(nilai)}],
                           description=f"Pengakuan penjualan {so['number']}", date="2026-11-05T03:00:00+00:00",
                           source_type="shipment_revenue", source_id=shid, entity_id=KANDA, created_by="system",
                           source_label="SJ-AGFSC", ref={"order_id": so["id"], "order_number": so["number"]})
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"status": "shipped"}})


async def _jurnal_tebus(db, red_id: str) -> dict:
    je = await db.journal_entries.find_one({"source_type": "store_credit_redeem", "source_id": red_id,
                                            "status": {"$ne": "void"}}, {"_id": 0})
    out: dict = {}
    for ln in je["lines"]:
        out[ln["account_code"]] = round(out.get(ln["account_code"], 0) + float(ln.get("debit") or 0)
                                        - float(ln.get("credit") or 0), 2)
    return out


async def test_tebus_saldo_kredit_pesanan_belum_dikirim_jadi_uang_muka(db):
    from services import customer_balance_service as cbs
    from services import gl_service as gl
    from services import store_credit_service as sc
    awal = await cbs.reconcile_gl(KANDA)
    ar0, um0, sk0 = await _saldo("1-1200"), await _saldo("2-1400"), await _saldo("2-1450")
    so = await _pelanggan_dan_pesanan(db, 1_000_000)
    red = await sc.redeem(customer_id=so["customer_id"], entity_id=KANDA, amount=300_000,
                          allocations=[{"order_id": so["id"], "amount": 300_000}], actor={"name": "Uji"})
    # kode lama: {"2-1450": 300000, "1-1200": -300000} → piutang buku besar minus untuk pesanan belum terkirim
    assert await _jurnal_tebus(db, red["id"]) == {"2-1450": 300_000, "2-1400": -300_000}
    o = await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert [(p["kind"], p["amount"], p.get("gl_bucket")) for p in o["payments"]] == \
        [("saldo_kredit", 300_000, "advance")]
    assert await _saldo("1-1200") == ar0
    rec = await cbs.reconcile_gl(KANDA)
    assert rec["unexplained"] == awal["unexplained"], rec       # kode lama: Δ −300.000 tak terjelaskan

    # surat jalan penuh → reklas uang muka ke piutang (jalur yang sama dengan kwitansi kas)
    await _kirim(db, so, 1_000_000)
    o = await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    await gl.post_advance_reclass(o)
    assert await _saldo("1-1200") == round(ar0 + 700_000, 2)
    assert await _saldo("2-1400") == um0
    assert (await cbs.reconcile_gl(KANDA))["unexplained"] == awal["unexplained"]

    # batal penebusan sesudah reklas → piutang kembali penuh, uang muka nol, saldo kredit kembali
    await sc.reverse_redemption(red["id"], reason="uji batal", actor={"name": "Uji"})
    assert await _saldo("1-1200") == round(ar0 + 1_000_000, 2)
    assert await _saldo("2-1400") == um0
    assert await _saldo("2-1450") == sk0
    assert await sc.balance(so["customer_id"], KANDA) == 500_000
    assert (await cbs.reconcile_gl(KANDA))["unexplained"] == awal["unexplained"]


async def test_tebus_batal_sebelum_dikirim_uang_muka_kembali_nol(db):
    from services import store_credit_service as sc
    um0, ar0 = await _saldo("2-1400"), await _saldo("1-1200")
    so = await _pelanggan_dan_pesanan(db, 1_000_000)
    red = await sc.redeem(customer_id=so["customer_id"], entity_id=KANDA, amount=200_000,
                          allocations=[{"order_id": so["id"], "amount": 200_000}], actor={"name": "Uji"})
    assert await _saldo("2-1400") == round(um0 - 200_000, 2)
    await sc.reverse_redemption(red["id"], reason="uji batal", actor={"name": "Uji"})
    assert (await _saldo("2-1400"), await _saldo("1-1200")) == (um0, ar0)


async def test_tebus_pesanan_sudah_dikirim_tetap_kredit_piutang(db):
    from services import store_credit_service as sc
    so = await _pelanggan_dan_pesanan(db, 1_000_000)
    await _kirim(db, so, 1_000_000)
    red = await sc.redeem(customer_id=so["customer_id"], entity_id=KANDA, amount=250_000,
                          allocations=[{"order_id": so["id"], "amount": 250_000}], actor={"name": "Uji"})
    assert await _jurnal_tebus(db, red["id"]) == {"2-1450": 250_000, "1-1200": -250_000}
    o = await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert [p.get("gl_bucket") for p in o["payments"]] == [None]
