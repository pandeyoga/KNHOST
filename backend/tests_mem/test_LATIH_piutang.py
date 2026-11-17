"""Pelatihan Keuangan 18 Nov 2026 — bagian A (Piutang): perbaikan yang ditemukan saat uji jalan skenario F02–F06.

  L1  Kwitansi baru menyimpan `journal_entry_id` jurnal kasnya (label "Jurnal Terbit" di Riwayat Pembayaran AR bisa
      dibuka). Kwitansi lama tanpa id: daftar (`GET /api/ar-receipts`, berhalaman & tidak) mengisinya dari transaksi kas.
  L2  Selisih bayar pesanan yang BELUM jatuh tempo tidak lagi ditulis "tagihan yang jatuh tempo" (pesanan bertempo 30
      hari, bayar 40 %: batasnya = sisa tagihan pesanan tujuan, belum jatuh tempo).

Persiapan (FIXTURE): rekening penerimaan bawaan transfer `ent_ksc` lewat API; pelanggan + pesanan terbuka disisip
langsung (bentuk sama dengan `test_PMT3_kwitansi_rekening.py`).
"""
from __future__ import annotations

import uuid

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"


def _id(awal: str) -> str:
    return f"{awal}_latih_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin):
    r = await klien.post("/api/bank-accounts", headers=kepala_admin, json={
        "account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
        "payment_method_codes": ["transfer"], "name": "BCA Operasional Latihan", "account_number": "741-559-5554",
        "holder_name": "PT Kain Suka Cita", "default_receiving_methods": ["transfer"], "entity_id": KSC})
    assert r.status_code == 200, r.text
    cus = _id("cus")
    await db.customers.insert_one({"id": cus, "name": "Latihan Uji · Toko Kain", "entity_id": KSC, "status": "active",
                                   "payment_profile": {"default_method": "tempo", "term_days": 30}})
    return {"h": kepala_admin, "P": cus, "rek": r.json()["id"]}


async def _pesanan(db, siap, total: float) -> dict:
    so = {"id": _id("so"), "number": f"SO-LATIH-{uuid.uuid4().hex[:4]}", "entity_id": KSC, "customer_id": siap["P"],
          "customer_name": "Latihan Uji · Toko Kain", "status": "confirmed", "grand_total": float(total), "payments": [],
          "paid_total": 0, "payment_status": "unpaid", "payment_term_code": "NET30", "created_at": now_iso()}
    await db.sales_orders.insert_one(dict(so))
    return so


async def test_LATIH_L1_kwitansi_menyimpan_id_jurnal_dan_daftar_mengisi_yang_lama(klien, db, siap):
    so = await _pesanan(db, siap, 3_440_167.5)          # nilai bertengah rupiah seperti SO latihan
    r = await klien.post("/api/ar-receipts", headers=siap["h"], json={
        "customer_id": siap["P"], "amount": 3_440_167.5, "method": "transfer", "entity_id": KSC,
        "allocations": [{"order_id": so["id"], "amount": 3_440_167.5}]})
    assert r.status_code == 200, r.text
    rc = r.json()
    kas = await db.cash_transactions.find_one({"id": rc["cash_txn_id"]}, {"_id": 0})
    assert kas["journal_entry_id"], "kas kwitansi belum berjurnal"
    assert rc["gl_status"] == "posted" and rc["journal_entry_id"] == kas["journal_entry_id"]
    je = await db.journal_entries.find_one({"id": rc["journal_entry_id"]}, {"_id": 0})
    # Pesanan fixture belum dikirim → sisi kredit = Uang Muka Pelanggan (2-1400); yang diuji: jurnal kas kwitansi ini.
    assert [(ln["account_code"], ln["debit"]) for ln in je["lines"] if ln["debit"]] == [("1-1100", 3_440_167.5)]
    assert sum(ln["credit"] for ln in je["lines"]) == 3_440_167.5 and je["source_id"] == rc["cash_txn_id"]

    # Kwitansi lama (sebelum perbaikan): id jurnal kosong → daftar mengisinya dari transaksi kas, tanpa menulis.
    await db.ar_receipts.update_one({"id": rc["id"]}, {"$set": {"journal_entry_id": ""}})
    for params in ({"customer_id": siap["P"], "page": 1, "page_size": 10}, {"customer_id": siap["P"]}):
        d = (await klien.get("/api/ar-receipts", headers=siap["h"], params=params)).json()
        rows = d["items"] if isinstance(d, dict) else d
        row = next(x for x in rows if x["id"] == rc["id"])
        assert row["journal_entry_id"] == kas["journal_entry_id"], params
    assert (await db.ar_receipts.find_one({"id": rc["id"]}, {"_id": 0}))["journal_entry_id"] == ""


async def test_LATIH_L2_selisih_pesanan_belum_jatuh_tempo_tidak_disebut_jatuh_tempo(klien, db, siap):
    so = await _pesanan(db, siap, 3_484_012.5)
    r = await klien.post("/api/payment-variances/assess", headers=siap["h"], json={
        "customer_id": siap["P"], "amount": 1_393_605, "allocations": [{"order_id": so["id"], "amount": 1_393_605}]})
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["direction"] == "under" and a["needs_decision"] is True
    assert a["boundary"] == 3_484_012.5
    assert "jatuh tempo" not in a["boundary_label"].replace("belum jatuh tempo", "")
    assert a["boundary_label"] == "sisa tagihan pesanan tujuan, belum jatuh tempo"
    assert all("Tagihan yang jatuh tempo" not in s for s in a["explain"])
