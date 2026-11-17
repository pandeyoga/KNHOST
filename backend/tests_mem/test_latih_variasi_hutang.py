"""Pelatihan 18 Nov — uji variasi isian bayar tagihan supplier (V5): pesan lebih bayar berupiah dan toleransi selisih
bayar supplier ikut di rincian tagihan (dipakai form Bayar pemasok untuk menyebut kurang bayar receh sebelum simpan)."""
import pytest

from core_utils import now_iso

KSC = "ent_ksc"


@pytest.fixture(scope="module")
async def data(db):
    await db.bank_accounts.insert_one({"id": "rek_v5", "name": "Kas Besar KSC", "entity_id": KSC, "account_type": "bank",
                                       "cash_type": "kas_besar", "is_active": True, "opening_balance": 0})
    await db.vendor_bills.insert_one({
        "id": "vb_v5", "bill_number": "VB-V5", "entity_id": KSC, "supplier_id": "sup_v5", "supplier_name": "Pemasok V5",
        "status": "posted", "grand_total": 1_864_800.0, "subtotal": 1_864_800.0, "amount_paid": 0.0, "payments": [],
        "timeline": [], "po_id": None, "bill_date": "2026-11-01", "created_at": now_iso()})
    return True


async def test_lebih_bayar_ditolak_dengan_rupiah(klien, kepala_admin, db, data):
    r = await klien.post("/api/vendor-bills/vb_v5/pay", headers=kepala_admin,
                         json={"amount": 2_000_000, "paid_at": "2026-11-17", "bank_account_id": "rek_v5"})
    assert r.status_code == 400, r.text
    assert r.json()["detail"].startswith("Pembayaran Rp 2.000.000 melebihi sisa hutang Rp 1.864.800."), r.text
    assert (await db.vendor_bills.find_one({"id": "vb_v5"}))["amount_paid"] == 0


async def test_rincian_tagihan_membawa_toleransi(klien, kepala_admin, data):
    r = await klien.get("/api/vendor-bills/vb_v5", headers=kepala_admin)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["payment_tolerance"] == 5000.0          # bawaan `payment.variance_ap_tolerance_rupiah`
    assert d["financials"]["outstanding"] == 1_864_800.0


async def test_batal_bayar_tanggal_maju_dibalik_di_tanggal_aslinya(klien, kepala_admin, db, data):
    """Pembayaran bertanggal maju yang dibatalkan: jurnal pembalik bertanggal kas aslinya (bukan hari ini), sehingga
    bulan berjalan tidak mendapat Dr Bank / Cr Hutang tanpa jurnal asal."""
    r = await klien.post("/api/vendor-bills/vb_v5/pay", headers={**kepala_admin, "Idempotency-Key": "v5-maju"},
                         json={"amount": 100_000, "paid_at": "2099-12-15", "bank_account_id": "rek_v5"})
    assert r.status_code == 200, r.text
    pay = next(p for p in r.json()["payments"] if not p.get("voided"))
    asal = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": pay["cash_txn_id"]})
    assert asal["date"][:10] == "2099-12-15"
    r = await klien.post(f"/api/vendor-bills/vb_v5/payments/{pay['id']}/void", headers=kepala_admin,
                         json={"notes": "uji tanggal maju"})
    assert r.status_code == 200, r.text
    balik = await db.journal_entries.find_one({"source_type": "cash_transaction_void", "source_id": pay["cash_txn_id"]})
    assert balik and balik["date"][:10] == "2099-12-15", balik
    assert r.json()["amount_paid"] == 0


async def test_batal_bayar_hari_ini_tetap_dibalik_hari_ini(klien, kepala_admin, db, data):
    from services.book_date import tanggal_buku
    hari_ini = tanggal_buku()
    r = await klien.post("/api/vendor-bills/vb_v5/pay", headers={**kepala_admin, "Idempotency-Key": "v5-kini"},
                         json={"amount": 100_000, "paid_at": hari_ini, "bank_account_id": "rek_v5"})
    assert r.status_code == 200, r.text
    pay = next(p for p in r.json()["payments"] if not p.get("voided"))
    r = await klien.post(f"/api/vendor-bills/vb_v5/payments/{pay['id']}/void", headers=kepala_admin,
                         json={"notes": "uji tanggal kini"})
    assert r.status_code == 200, r.text
    balik = await db.journal_entries.find_one({"source_type": "cash_transaction_void", "source_id": pay["cash_txn_id"]})
    assert balik and balik["date"][:10] == hari_ini


async def test_laporan_rentang_terbalik_dan_tanggal_salah_ditolak(klien, kepala_admin):
    """V8 — Laba-Rugi / Arus Kas / Perubahan Ekuitas: rentang terbalik & tanggal tak dikenal → 400 berbahasa Indonesia
    (dulu laporan Rp 0 semua tanpa pesan); rentang satu hari & kosong tetap jalan."""
    for path in ("income-statement", "cash-flow", "equity-changes"):
        r = await klien.get(f"/api/finance/{path}", headers=kepala_admin, params={"start": "2026-12-01", "end": "2026-11-17"})
        assert r.status_code == 400 and r.json()["detail"] == "Tanggal awal tidak boleh sesudah tanggal akhir.", r.text
        r = await klien.get(f"/api/finance/{path}", headers=kepala_admin, params={"start": "abc", "end": "2026-11-17"})
        assert r.status_code == 400 and r.json()["detail"] == "Tanggal awal harus berbentuk TTTT-BB-HH.", r.text
        r = await klien.get(f"/api/finance/{path}", headers=kepala_admin, params={"start": "2026-11-17", "end": "2026-11-17"})
        assert r.status_code == 200, r.text
        r = await klien.get(f"/api/finance/{path}", headers=kepala_admin)
        assert r.status_code == 200, r.text
