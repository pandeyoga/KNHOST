"""Pelatihan 18 Nov — S4 Koreksi & pembatalan (uji jalan `uji/situasi/S4_koreksi_pembatalan.js`).

1. Anulir jurnal manual menyimpan ALASAN (standar N5 "pembatalan meminta alasan") di jurnal + kolom alasan jejak audit;
   klien lama tanpa isi permintaan tetap diterima.
2. Reklasifikasi Akun Sementara (1-9999) bisa bertanggal di bulan saldo itu terjadi: dulu jurnal reklas selalu bertanggal
   hari ini, jadi saldo suspense Oktober yang dibersihkan awal November tetap tercatat di saldo per 31 Oktober → gerbang
   tutup buku Oktober (K-15) tetap terblokir. Tanggal masa depan / periode tertutup ditolak.
3. Riwayat tagihan pemasok menulis cara bayar & NAMA rekening ("… · transfer dari Kas Toko …"), bukan "via transfer
   (kas_kecil)".
"""
import pytest

from core_utils import now_iso
from pembantu import tutup_periode
from services import gl_service as gl
from services.book_date import tanggal_buku

pytestmark = pytest.mark.anyio
KSC = "ent_ksc"
HARI_INI = tanggal_buku()


def _jurnal(tanggal, ket, baris):
    return {"date": tanggal, "description": ket, "lines": [
        {"account_code": a, "debit": d, "credit": c} for a, d, c in baris]}


async def test_anulir_jurnal_manual_menyimpan_alasan(klien, db, kepala_admin):
    r = await klien.post("/api/gl/journal", headers=kepala_admin,
                         json=_jurnal(HARI_INI, "uji S4 salah akun", [("6-3000", 125_000, 0), ("2-1900", 0, 125_000)]))
    assert r.status_code == 200, r.text
    jid = r.json()["id"]
    r = await klien.post(f"/api/gl/journal/{jid}/void", headers=kepala_admin,
                         json={"reason": "Salah akun: seharusnya beban sewa"})
    assert r.status_code == 200, r.text
    je = await db.journal_entries.find_one({"id": jid}, {"_id": 0})
    assert je["status"] == "void" and je["void_reason"] == "Salah akun: seharusnya beban sewa", je
    a = await db.audit_logs.find_one({"action": "journal_entry_voided", "entity_id": jid}, {"_id": 0})
    assert a and a["reason"] == "Salah akun: seharusnya beban sewa", a


async def test_anulir_jurnal_tanpa_isi_tetap_diterima(klien, db, kepala_admin):
    r = await klien.post("/api/gl/journal", headers=kepala_admin,
                         json=_jurnal(HARI_INI, "uji S4 klien lama", [("6-3000", 1_000, 0), ("2-1900", 0, 1_000)]))
    jid = r.json()["id"]
    r = await klien.post(f"/api/gl/journal/{jid}/void", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert (await db.journal_entries.find_one({"id": jid}))["status"] == "void"


async def test_reklas_suspense_bertanggal_bulan_saldonya(klien, db, kepala_admin):
    """Saldo suspense Oktober direklas bertanggal 31 Okt → saldo per 31 Okt nol (tutup buku Oktober tidak terblokir)."""
    tgl = "2026-10-20"
    if tgl >= HARI_INI:   # uji dijalankan sebelum 21 Okt 2026: pakai tanggal kemarin
        import datetime
        tgl = (datetime.date.fromisoformat(HARI_INI) - datetime.timedelta(days=1)).isoformat()
    akhir = tgl[:8] + "28"
    sebelum = await gl.suspense_balance(KSC, as_of=akhir)
    r = await klien.post("/api/gl/journal", headers=kepala_admin,
                         json=_jurnal(tgl, "uji S4 kas tak dikenal", [("1-1100", 77_000, 0), ("1-9999", 0, 77_000)]))
    assert r.status_code == 200, r.text
    assert round(await gl.suspense_balance(KSC, as_of=akhir) - sebelum, 2) == -77_000

    # Tanpa tanggal (perilaku lama) → bertanggal hari ini: saldo bulan itu tidak berubah bila hari ini di bulan lain.
    r = await klien.post("/api/gl/suspense/reclass", headers=kepala_admin, json={
        "amount": 1_000, "side": "credit", "target_account": "4-9000", "note": "uji tanpa tanggal", "entity_id": KSC})
    assert r.status_code == 200, r.text
    assert r.json()["date"][:10] == HARI_INI

    r = await klien.post("/api/gl/suspense/reclass", headers=kepala_admin, json={
        "amount": 76_000, "side": "credit", "target_account": "4-9000", "note": "uji bertanggal", "entity_id": KSC,
        "date": akhir})
    assert r.status_code == 200, r.text
    assert r.json()["date"][:10] == akhir
    selisih = round(await gl.suspense_balance(KSC, as_of=akhir) - sebelum, 2)
    assert selisih == (-1_000 if HARI_INI > akhir else 0), selisih
    a = await db.audit_logs.find_one({"action": "suspense_reclass", "entity_id": r.json()["id"]}, {"_id": 0})
    assert a["after"]["date"][:10] == akhir


async def test_reklas_suspense_tanggal_maju_dan_periode_tertutup_ditolak(klien, db, kepala_admin):
    r = await klien.post("/api/gl/suspense/reclass", headers=kepala_admin, json={
        "amount": 1_000, "side": "credit", "target_account": "4-9000", "entity_id": KSC, "date": "2099-01-31"})
    assert r.status_code == 400 and "masa depan" in r.json()["detail"], r.text
    r = await klien.post("/api/gl/suspense/reclass", headers=kepala_admin, json={
        "amount": 1_000, "side": "credit", "target_account": "4-9000", "entity_id": KSC, "date": "31-01-2026"})
    assert r.status_code == 400, r.text
    await tutup_periode(KSC, "2025-12")
    n = await db.journal_entries.count_documents({"source_type": "suspense_reclass"})
    r = await klien.post("/api/gl/suspense/reclass", headers=kepala_admin, json={
        "amount": 1_000, "side": "credit", "target_account": "4-9000", "entity_id": KSC, "date": "2025-12-31"})
    assert r.status_code == 409, r.text
    assert await db.journal_entries.count_documents({"source_type": "suspense_reclass"}) == n


async def test_riwayat_tagihan_menyebut_rekening(klien, db, kepala_admin):
    await db.bank_accounts.insert_one({"id": "rek_s4_toko", "name": "Kas Toko S4", "entity_id": KSC, "account_type": "cash",
                                       "cash_type": "kas_kecil", "is_active": True, "opening_balance": 0})
    await db.vendor_bills.insert_one({
        "id": "vb_s4", "bill_number": "VB-S4", "entity_id": KSC, "supplier_id": "sup_s4", "supplier_name": "Pemasok S4",
        "status": "posted", "grand_total": 500_000.0, "subtotal": 500_000.0, "amount_paid": 0.0, "payments": [],
        "timeline": [], "po_id": None, "bill_date": "2026-11-01", "created_at": now_iso()})
    r = await klien.post("/api/vendor-bills/vb_s4/pay", headers={**kepala_admin, "Idempotency-Key": "s4-riwayat"},
                         json={"amount": 500_000, "paid_at": HARI_INI, "bank_account_id": "rek_s4_toko"})
    assert r.status_code == 200, r.text
    tl = next(t for t in r.json()["timeline"] if t.get("label") == "Pembayaran dicatat")
    assert "dari Kas Toko S4" in tl["note"] and "kas_kecil" not in tl["note"], tl
    assert "Rp 500.000" in tl["note"] and "kas KSC/CASH-" in tl["note"], tl
