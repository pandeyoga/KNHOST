"""Uji adversarial pelatihan 18 Nov (agen D) — pembatalan dokumen uang BERTANGGAL MAJU.

V-09 (LAPORAN_AUDIT) memperbaiki batal-bayar tagihan supplier: jurnal pembaliknya bertanggal kas aslinya bila kas itu
masih di depan. Kelas cacat yang sama masih ada di dua pintu lain:

  * batal KWITANSI bertanggal maju (mis. 15 Des) hari ini → pembalik kas (Dr Piutang / Cr Bank) dan baris pembalik
    pembayaran pesanan bertanggal HARI INI, sebelum jurnal aslinya → bulan berjalan mendapat Dr 1-1200 / Cr 1-1100 tanpa
    jurnal asal (saldo bank turun, piutang naik sampai tanggal kwitansi), umur piutang pesanan ikut salah;
  * anulir KAS MANUAL bertanggal maju → pembalik bertanggal hari ini (cacat yang sama untuk akun kas & lawannya).

Aturan yang diuji (sama dengan `vendor_bills.void_vendor_bill_payment` dan `gl_service.reverse_entry`): pembalik
bertanggal dokumen asal bila tanggal itu masih di depan; selain itu hari ini (perilaku lama tetap).
"""
from __future__ import annotations

import uuid

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"
MAJU = "2099-12-15"


def _id(awal: str) -> str:
    return f"{awal}_advmaju_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
async def dunia(db):
    await db.bank_accounts.insert_one({"id": "rek_advmaju", "name": "BCA KSC Uji Maju", "entity_id": KSC,
                                       "account_type": "bank", "cash_type": "kas_besar", "is_active": True,
                                       "opening_balance": 0})
    cus = _id("cus")
    await db.customers.insert_one({"id": cus, "name": "Toko Uji Maju", "entity_id": KSC, "status": "active",
                                   "deposit_balance": 0.0})
    return {"cus": cus}


async def _pesanan(db, cus, total) -> dict:
    from services import gl_service as gl
    so = {"id": _id("so"), "number": f"SO-ADV-{uuid.uuid4().hex[:4]}", "entity_id": KSC, "customer_id": cus,
          "customer_name": "Toko Uji Maju", "status": "shipped", "grand_total": float(total), "payments": [],
          "paid_total": 0.0, "payment_status": "unpaid", "payment_term_code": "NET30", "items": [],
          "created_at": now_iso()}
    await db.sales_orders.insert_one(dict(so))
    await gl._insert_entry(lines=[{"account_code": "1-1200", "debit": float(total), "credit": 0.0},
                                  {"account_code": "4-1000", "debit": 0.0, "credit": float(total)}],
                           description=f"pendapatan {so['number']} (fixture)", date=now_iso(),
                           source_type="sales_order", source_id=so["id"], entity_id=KSC, created_by="uji")
    return so


async def _kwitansi(klien, h, cus, so, amount, tanggal):
    body = {"customer_id": cus, "amount": amount, "method": "transfer", "entity_id": KSC, "account_id": "rek_advmaju",
            "reference_no": f"ADV-{uuid.uuid4().hex[:6]}", "receipt_date": tanggal,
            "allocations": [{"order_id": so["id"], "amount": amount}]}
    r = await klien.post("/api/ar-receipts", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


async def test_batal_kwitansi_bertanggal_maju_dibalik_di_tanggal_aslinya(klien, kepala_admin, db, dunia):
    so = await _pesanan(db, dunia["cus"], 1_000_000)
    rc = await _kwitansi(klien, kepala_admin, dunia["cus"], so, 300_000.5, MAJU)
    kas = rc["cash_txn_id"]
    asal = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": kas})
    assert asal["date"][:10] == MAJU, asal["date"]
    r = await klien.post(f"/api/ar-receipts/{rc['id']}/void", headers=kepala_admin, params={"reason": "uji tanggal maju"})
    assert r.status_code == 200, r.text
    balik = await db.journal_entries.find_one({"source_type": "cash_transaction_void", "source_id": kas})
    assert balik is not None
    assert balik["date"][:10] == MAJU, f"pembalik bertanggal {balik['date'][:10]}, sebelum jurnal asal {MAJU}"
    # baris pembalik pembayaran pesanan juga tidak boleh mendahului baris aslinya (umur piutang / rekening koran)
    pays = (await db.sales_orders.find_one({"id": so["id"]}))["payments"]
    asli = next(p for p in pays if not p.get("reverses"))
    pembalik = next(p for p in pays if p.get("reverses") == asli["id"])
    assert str(pembalik["date"])[:10] >= str(asli["date"])[:10], (pembalik["date"], asli["date"])
    assert round(sum(float(p["amount"]) for p in pays), 2) == 0


async def test_batal_kwitansi_hari_ini_tetap_dibalik_hari_ini(klien, kepala_admin, db, dunia):
    from services.book_date import tanggal_buku
    hari_ini = tanggal_buku()
    so = await _pesanan(db, dunia["cus"], 500_000)
    rc = await _kwitansi(klien, kepala_admin, dunia["cus"], so, 200_000, hari_ini)
    r = await klien.post(f"/api/ar-receipts/{rc['id']}/void", headers=kepala_admin, params={"reason": "uji hari ini"})
    assert r.status_code == 200, r.text
    balik = await db.journal_entries.find_one({"source_type": "cash_transaction_void", "source_id": rc["cash_txn_id"]})
    assert balik and balik["date"][:10] == hari_ini


async def test_anulir_kas_manual_bertanggal_maju_dibalik_di_tanggal_aslinya(klien, kepala_admin, db, dunia):
    r = await klien.post("/api/cash-transactions", headers=kepala_admin, json={
        "cash_type": "kas_besar", "direction": "out", "amount": 12_345, "category": "operasional",
        "description": "uji kas maju", "account_id": "rek_advmaju", "entity_id": KSC, "txn_date": MAJU})
    assert r.status_code == 200, r.text
    kas = r.json()["id"]
    asal = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": kas})
    assert asal["date"][:10] == MAJU
    r = await klien.post(f"/api/cash-transactions/{kas}/void", headers=kepala_admin, json={"reason": "uji tanggal maju"})
    assert r.status_code == 200, r.text
    balik = await db.journal_entries.find_one({"source_type": "cash_transaction_void", "source_id": kas})
    assert balik and balik["date"][:10] == MAJU, balik and balik["date"]


async def test_batal_dua_kali_pesannya_berbahasa_indonesia(klien, kepala_admin, db, dunia):
    """Klik ganda / dua pengguna membatalkan kwitansi atau kas yang sama: yang kedua dulu membaca "Receipt sudah di-void"
    / "Transaksi sudah di-void" (campuran Inggris). Kini kalimat Indonesia yang menyebut dokumennya."""
    from services.book_date import tanggal_buku
    so = await _pesanan(db, dunia["cus"], 400_000)
    rc = await _kwitansi(klien, kepala_admin, dunia["cus"], so, 100_000, tanggal_buku())
    r1 = await klien.post(f"/api/ar-receipts/{rc['id']}/void", headers=kepala_admin, params={"reason": "uji 1"})
    assert r1.status_code == 200, r1.text
    r2 = await klien.post(f"/api/ar-receipts/{rc['id']}/void", headers=kepala_admin, params={"reason": "uji 2"})
    assert r2.status_code == 409 and r2.json()["detail"] == "Kwitansi ini sudah dibatalkan.", r2.text
    r = await klien.post("/api/cash-transactions", headers=kepala_admin, json={
        "cash_type": "kas_besar", "direction": "out", "amount": 1_000, "category": "operasional",
        "description": "uji batal dua kali", "account_id": "rek_advmaju", "entity_id": KSC})
    kas = r.json()["id"]
    assert (await klien.post(f"/api/cash-transactions/{kas}/void", headers=kepala_admin, json={"reason": "a"})).status_code == 200
    r2 = await klien.post(f"/api/cash-transactions/{kas}/void", headers=kepala_admin, json={"reason": "b"})
    assert r2.status_code == 409 and r2.json()["detail"] == "Transaksi kas ini sudah dibatalkan.", r2.text


async def test_batal_kwitansi_maju_dari_pemilih_tanggal_layar(klien, kepala_admin, db, dunia):
    """Pemilih tanggal layar mengirim "2099-12-15T00:00:00.000Z" (uji jalan peserta 99: KSC/AR-00073 bertanggal
    2026-12-15T00:00:00.000Z, pembaliknya KSC/JE-00476 bertanggal 2026-11-18). Pembalik = tanggal buku jurnal asal."""
    so = await _pesanan(db, dunia["cus"], 600_000)
    rc = await _kwitansi(klien, kepala_admin, dunia["cus"], so, 300_000, f"{MAJU}T00:00:00.000Z")
    asal = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": rc["cash_txn_id"]})
    r = await klien.post(f"/api/ar-receipts/{rc['id']}/void", headers=kepala_admin, params={"reason": "uji pemilih"})
    assert r.status_code == 200, r.text
    balik = await db.journal_entries.find_one({"source_type": "cash_transaction_void", "source_id": rc["cash_txn_id"]})
    assert balik["date"][:10] == asal["date"][:10] == MAJU, (asal["date"], balik["date"])
