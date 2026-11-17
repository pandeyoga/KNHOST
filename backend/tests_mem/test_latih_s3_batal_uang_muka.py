"""Pelatihan Keuangan 18 Nov 2026 — situasi S3 (pesanan sampai uang masuk): pesanan ber-uang muka yang DIBATALKAN.

  S3-L1  Pesanan bertermin DP yang sudah menerima uang muka (kas masuk, Cr 2-1400 Uang Muka Pelanggan) lalu dibatalkan
         sebelum dikirim: dulu uang mukanya tertinggal di pesanan mati — tidak masuk titipan pelanggan, tidak tampil di
         Laporan Uang Muka, tidak bisa dikembalikan (Kasus "Pengembalian dana" dibatasi saldo titipan) dan tidak bisa
         dipakai pesanan lain, padahal akun 2-1400 di buku besar masih memegangnya. Sekarang pembatalan memindahkannya
         menjadi titipan pelanggan: tanpa jurnal baru (uang muka pesanan dan titipan sama-sama 2-1400), baris penarikan
         di pesanan (terbayar pesanan mati = 0), saldo titipan bertambah, dan kwitansi asalnya tidak bisa lagi dibatalkan
         diam-diam (uangnya sudah dipindah).
  S3-L2  Pemindahan aman diulang (dipanggil dua kali = satu kali) dan pesanan tanpa uang muka tidak tersentuh.
  S3-L3  Termin DP 50%: membayar TEPAT uang muka yang jatuh tempo bukan "Kurang bayar" (penilaian selisih membaca jadwal
         tagihan), dan daftar tagihan terbuka form Terima pembayaran menyebut uang muka yang ditagih (`due_now`).
"""
from __future__ import annotations

import uuid

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"


def _id(awal: str) -> str:
    return f"{awal}_s3_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin):
    r = await klien.post("/api/bank-accounts", headers=kepala_admin, json={
        "account_type": "bank", "bank_name": "BCA", "purposes": ["penerimaan_pelanggan"],
        "payment_method_codes": ["transfer"], "name": "BCA Operasional S3", "account_number": "741-559-5555",
        "holder_name": "PT Kain Suka Cita", "default_receiving_methods": ["transfer"], "entity_id": KSC})
    assert r.status_code == 200, r.text
    cus = _id("cus")
    await db.customers.insert_one({"id": cus, "name": "Latihan S3 · Toko Kain", "entity_id": KSC, "status": "active",
                                   "payment_profile": {"default_method": "tempo", "term_days": 30}})
    return {"h": kepala_admin, "P": cus}


async def _pesanan_dp(db, siap, total: float) -> dict:
    so = {"id": _id("so"), "number": f"SO-S3-{uuid.uuid4().hex[:4]}", "entity_id": KSC, "customer_id": siap["P"],
          "customer_name": "Latihan S3 · Toko Kain", "status": "confirmed", "grand_total": float(total),
          "ppn_amount": 0.0, "payments": [], "paid_total": 0, "payment_status": "unpaid", "payment_term_code": "DP50",
          "items": [], "created_at": now_iso()}
    await db.sales_orders.insert_one(dict(so))
    return so


async def _saldo_akun(db, kode: str) -> float:
    tot = 0.0
    async for je in db.journal_entries.find({"entity_id": KSC, "status": {"$ne": "void"}}, {"_id": 0, "lines": 1}):
        tot += sum(float(ln.get("credit") or 0) - float(ln.get("debit") or 0)
                   for ln in je.get("lines") or [] if ln.get("account_code") == kode)
    return round(tot, 2)


async def _titipan(db, cus: str) -> float:
    c = await db.customers.find_one({"id": cus}, {"_id": 0, "deposit_balance": 1})
    return round(float((c or {}).get("deposit_balance") or 0), 2)


async def test_S3_L1_batal_pesanan_ber_uang_muka_memindah_uang_muka_ke_titipan(klien, db, siap):
    so = await _pesanan_dp(db, siap, 2_615_160)
    dp = 1_307_580.0
    r = await klien.post("/api/ar-receipts", headers=siap["h"], json={
        "customer_id": siap["P"], "amount": dp, "method": "transfer", "entity_id": KSC, "reference_no": "TRF-S3-DP",
        "allocations": [{"order_id": so["id"], "amount": dp}]})
    assert r.status_code == 200, r.text
    rc = r.json()
    o = await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert [p.get("gl_bucket") for p in o["payments"]] == ["advance"], "uang muka pesanan belum dikirim"
    um_awal = await _saldo_akun(db, "2-1400")
    titip_awal = await _titipan(db, siap["P"])
    n_je = await db.journal_entries.count_documents({})

    r = await klien.post(f"/api/sales-orders/{so['id']}/cancel", headers=siap["h"],
                         json={"reason": "Pelanggan membatalkan pesanan sebelum dikirim"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"
    assert round(float(r.json().get("advance_to_deposit") or 0), 2) == dp, r.json().get("advance_to_deposit")

    # Titipan pelanggan bertambah sebesar uang muka; terbayar pesanan mati kembali nol.
    assert await _titipan(db, siap["P"]) == round(titip_awal + dp, 2)
    o = await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert round(sum(float(p.get("amount") or 0) for p in o["payments"]), 2) == 0.0
    assert round(float(o.get("paid_total") or 0), 2) == 0.0
    tarik = [p for p in o["payments"] if float(p.get("amount") or 0) < 0]
    assert len(tarik) == 1 and tarik[0]["kind"] == "deposit" and tarik[0].get("gl_bucket") == "advance"
    # Tanpa jurnal baru: 2-1400 tetap memegang uang yang sama (kini sebagai titipan).
    assert await db.journal_entries.count_documents({}) == n_je
    assert await _saldo_akun(db, "2-1400") == um_awal
    d = (await klien.get("/api/ar-receipts/deposit", headers=siap["h"], params={"customer_id": siap["P"]})).json()
    assert round(float(d["deposit_balance"]), 2) == round(titip_awal + dp, 2)

    # Kwitansi uang muka tidak bisa dibatalkan diam-diam sesudah uangnya dipindah (titipan tidak boleh dobel).
    r = await klien.post(f"/api/ar-receipts/{rc['id']}/void", headers=siap["h"], json={"reason": "uji pembatalan"})
    assert r.status_code == 409, r.text
    assert await _titipan(db, siap["P"]) == round(titip_awal + dp, 2)


async def test_S3_L2_pemindahan_aman_diulang_dan_pesanan_tanpa_uang_muka_tidak_tersentuh(klien, db, siap):
    from services import ar_receipt_service as ar
    so = await _pesanan_dp(db, siap, 1_000_000)
    r = await klien.post("/api/ar-receipts", headers=siap["h"], json={
        "customer_id": siap["P"], "amount": 500_000, "method": "transfer", "entity_id": KSC, "reference_no": "TRF-S3-L2",
        "allocations": [{"order_id": so["id"], "amount": 500_000}]})
    assert r.status_code == 200, r.text
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"status": "cancelled"}})
    awal = await _titipan(db, siap["P"])
    assert await ar.uang_muka_pesanan_batal_ke_titipan(so["id"], {"name": "uji"}, "uji") == 500_000
    assert await ar.uang_muka_pesanan_batal_ke_titipan(so["id"], {"name": "uji"}, "uji") == 0.0
    assert await _titipan(db, siap["P"]) == round(awal + 500_000, 2)

    kosong = await _pesanan_dp(db, siap, 750_000)
    r = await klien.post(f"/api/sales-orders/{kosong['id']}/cancel", headers=siap["h"],
                         json={"reason": "Pelanggan membatalkan pesanan sebelum bayar"})
    assert r.status_code == 200, r.text
    assert float(r.json().get("advance_to_deposit") or 0) == 0.0
    o = await db.sales_orders.find_one({"id": kosong["id"]}, {"_id": 0})
    assert o["payments"] == [] and await _titipan(db, siap["P"]) == round(awal + 500_000, 2)


async def test_S3_L3_bayar_tepat_uang_muka_termin_dp_bukan_kurang_bayar(klien, db, siap):
    """S3-L3 — pesanan bertermin DP 50% yang sudah dikonfirmasi: tagihan yang jatuh tempo SEKARANG = baris uang muka
    (jadwal tagihan, "sebelum kirim"). Dulu penilaian selisih memakai jatuh tempo termin dari tanggal pesanan (belum
    jatuh tempo) sehingga harapannya = seluruh sisa pesanan: membayar tepat uang muka dinilai "Kurang bayar Rp … —
    seharusnya Rp (total)" dan Finance dipaksa memilih keputusan (bawaan "Dipotong biaya bank")."""
    if not await db.payment_terms.find_one({"code": "DP50"}):
        await db.payment_terms.insert_one({"entity_id": "all", "code": "DP50", "name": "DP 50% + Pelunasan",
                                           "dp_percent": 50, "days": 14, "active": True})
    so = await _pesanan_dp(db, siap, 2_537_016)
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"confirmed_at": now_iso()}})
    dp = 1_268_508.0
    r = await klien.post("/api/payment-variances/assess", headers=siap["h"], json={
        "customer_id": siap["P"], "amount": dp, "allocations": [{"order_id": so["id"], "amount": dp}]})
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["direction"] == "none" and a["needs_decision"] is False, (a["direction"], a["expected"], a["explain"])
    assert round(float(a["expected"]), 2) == dp
    assert a["boundary_label"] == "tagihan yang jatuh tempo"

    # Uang muka kurang Rp 10.000 tetap kurang bayar — dihitung dari uang muka, bukan dari total pesanan.
    r = await klien.post("/api/payment-variances/assess", headers=siap["h"], json={
        "customer_id": siap["P"], "amount": dp - 10_000, "allocations": [{"order_id": so["id"], "amount": dp - 10_000}]})
    a = r.json()
    assert a["direction"] == "under" and round(float(a["delta"]), 2) == -10_000.0, (a["direction"], a["delta"])

    # Daftar tagihan terbuka form "Terima pembayaran" menyebut yang ditagih sekarang (uang muka) — bahan isian bawaan.
    rows = (await klien.get("/api/ar-receipts/open-orders", headers=siap["h"],
                            params={"customer_id": siap["P"]})).json()
    row = next(x for x in rows if x["order_id"] == so["id"])
    assert round(float(row["outstanding"]), 2) == 2_537_016.0 and round(float(row.get("due_now") or 0), 2) == dp, row

    # Kwitansi uang muka tepat tersimpan tanpa keputusan selisih.
    r = await klien.post("/api/ar-receipts", headers=siap["h"], json={
        "customer_id": siap["P"], "amount": dp, "method": "transfer", "entity_id": KSC, "reference_no": "TRF-S3-L3",
        "allocations": [{"order_id": so["id"], "amount": dp}]})
    assert r.status_code == 200, r.text
    assert not (r.json().get("variance") or {}).get("decision_kind"), r.json().get("variance")
