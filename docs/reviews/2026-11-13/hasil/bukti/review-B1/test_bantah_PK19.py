"""Uji bantahan reviewer B1 — PK-19 (SL-05, SL-06, FX-05, FX-06, FX-07). Lapis B; cp ke backend/tests_mem/, -n 0 -s."""
# ruff: noqa: F811
import asyncio

import pytest

from core_utils import now_iso
from pembantu import jumlah, tutup_periode
from test_PK19_alur import (JT, KANDA, KSC, _baris, _deposit, _hari, _id, _jurnal, _kwitansi, _pesanan, _putus,
                            _saldo_deposit, _so, dunia)  # noqa: F401

pytestmark = pytest.mark.anyio


# ── SL-05 ────────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_SL05_jalur_lain_simulasi_dan_ubah_pesanan_langsung(klien, kepala_admin, db, dunia, akun, sesi):
    a1 = await _pesanan(db, dunia["A"], 1 * JT, label="S5-")
    sales = await sesi(await akun("sales"))
    for h in (kepala_admin, sales):
        r = await klien.post(f"/api/sales-orders/{a1['id']}/simulate-payment", headers=h,
                             json={"amount": 1 * JT, "method": "Transfer Simulasi"})
        assert r.status_code in (403, 410), r.text
    # pintu ubah pesanan: field pembayaran dari klien tidak boleh ikut tertulis
    for metode, url in (("patch", f"/api/sales-orders/{a1['id']}"), ("put", f"/api/sales-orders/{a1['id']}")):
        r = await getattr(klien, metode)(url, headers=kepala_admin, json={
            "payments": [{"id": "x", "amount": 1 * JT}], "paid_total": 1 * JT, "payment_status": "paid"})
        print("OBS ubah pesanan", metode, r.status_code)
    so = await _so(db, a1)
    assert so["payments"] == [] and so["paid_total"] == 0 and so["payment_status"] == "unpaid"
    assert await jumlah("invoices", {"order_id": a1["id"]}) == 0


async def test_SL05_tanpa_izin_sales_tidak_bisa_kwitansi(klien, db, dunia, akun, sesi):
    a1 = await _pesanan(db, dunia["A"], 1 * JT, label="S5b-")
    sales = await sesi(await akun("sales"))
    r = await _kwitansi(klien, sales, dunia["A"], 1 * JT, [(a1, 1 * JT)])
    from dependencies import permission_matrix
    izin = ((await permission_matrix()).get("sales") or {}).get("ar_receipt") or []
    print("OBS kwitansi oleh sales", r.status_code, "izin bawaan sales ar_receipt:", izin)
    # Bukan pintu lama: sales memang memegang ar_receipt.create (bawaan) → lewat kwitansi resmi; tanpa izin → 403.
    assert (r.status_code == 200) == ("create" in izin), r.text
    if r.status_code == 200:
        assert await jumlah("ar_receipts", {"id": r.json()["id"], "status": "posted"}) == 1


# ── SL-06 ────────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_SL06_ulang_dan_bersamaan_void_kwitansi_berdeposit(klien, kepala_admin, db, dunia):
    a1 = await _pesanan(db, dunia["A"], 1 * JT, label="S6-")
    await _deposit(db, dunia["A"], 400_000)
    r = await _kwitansi(klien, kepala_admin, dunia["A"], 600_000, [(a1, 1 * JT)], deposit=400_000)
    assert r.status_code == 200, r.text
    k = r.json()
    assert await _saldo_deposit(db, dunia["A"]) == 0
    v1, v2 = await asyncio.gather(
        klien.post(f"/api/ar-receipts/{k['id']}/void", headers=kepala_admin, params={"reason": "uji bersamaan 1"}),
        klien.post(f"/api/ar-receipts/{k['id']}/void", headers=kepala_admin, params={"reason": "uji bersamaan 2"}))
    v3 = await klien.post(f"/api/ar-receipts/{k['id']}/void", headers=kepala_admin, params={"reason": "uji ulang 3"})
    dep = await _saldo_deposit(db, dunia["A"])
    so = await _so(db, a1)
    doc = await db.ar_receipts.find_one({"id": k["id"]}, {"_id": 0})
    print("OBS void", v1.status_code, v2.status_code, v3.status_code, "deposit", dep, "status", doc["status"],
          "Σbayar", sum(p["amount"] for p in so["payments"]), "gl", doc.get("void_gl_status"), doc.get("gl_status"))
    assert dep == 400_000, f"deposit sesudah void (berulang) = {dep}, seharusnya kembali 400.000 sekali"
    assert doc["status"] == "void" and "saga_lock" not in doc
    assert sum(p["amount"] for p in so["payments"]) == 0 and so["payment_status"] == "unpaid"
    # jurnal: bersih nol di piutang untuk kwitansi ini
    net = 0.0
    async for je in db.journal_entries.find({"status": {"$ne": "void"}, "$or": [
            {"source_id": {"$regex": "^" + k["id"]}}, {"reverses_source_id": k["id"]}]}):
        net += sum(float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
                   for ln in je["lines"] if ln["account_code"] == "1-1200")
    print("OBS void Δpiutang bersih jurnal ber-sumber kwitansi:", net)


# ── FX-05 ────────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_FX05_jalur_lain_kwitansi_deposit_ke_pelanggan_dan_pt_lain(klien, kepala_admin, db, dunia):
    b1 = await _pesanan(db, dunia["B"], 800_000, label="F5B-")
    x1 = await _pesanan(db, dunia["A"], 1 * JT, ent=KANDA, label="F5X-")
    a1 = await _pesanan(db, dunia["A"], 300_000, label="F5A-")
    await _deposit(db, dunia["A"], 500_000)
    n0 = await jumlah("ar_receipts", {"customer_id": dunia["A"], "status": {"$ne": "void"}})
    for tujuan in (b1, x1):
        # satu sah (a1) + satu tidak sah: tidak boleh ada yang tertulis (validasi semua dulu)
        r = await _kwitansi(klien, kepala_admin, dunia["A"], 0, [(a1, 300_000), (tujuan, 200_000)], deposit=500_000)
        print("OBS kwitansi-deposit ke", tujuan["number"], r.status_code, r.text[:120])
        assert r.status_code in (400, 403, 409), r.text
        assert await _saldo_deposit(db, dunia["A"]) == 500_000
        assert (await _so(db, tujuan))["payments"] == [] and (await _so(db, a1))["payments"] == []
    assert await jumlah("ar_receipts", {"customer_id": dunia["A"], "status": {"$ne": "void"}}) == n0


async def test_FX05_batas_deposit_kurang_dari_alokasi(klien, kepala_admin, db, dunia):
    a1 = await _pesanan(db, dunia["A"], 300_000, label="F5c-")
    a2 = await _pesanan(db, dunia["A"], 300_000, label="F5d-")
    await _deposit(db, dunia["A"], 400_000)
    r = await _kwitansi(klien, kepala_admin, dunia["A"], 0, [(a1, 300_000), (a2, 300_000)], deposit=600_000)
    print("OBS deposit kurang", r.status_code, r.text[:140])
    assert r.status_code in (400, 409), r.text
    assert await _saldo_deposit(db, dunia["A"]) == 400_000
    assert (await _so(db, a1))["payments"] == [] and (await _so(db, a2))["payments"] == []


# ── FX-06 ────────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_FX06_bersamaan_dua_hapus_sisa(klien, kepala_admin, db, dunia):
    a1 = await _pesanan(db, dunia["A"], 1 * JT, label="F6-")
    r = await _kwitansi(klien, kepala_admin, dunia["A"], 990_000, [(a1, 990_000)])
    assert r.status_code == 200, r.text
    k = r.json()
    r1, r2 = await asyncio.gather(_putus(klien, kepala_admin, k["id"], "writeoff"),
                                  _putus(klien, kepala_admin, k["id"], "writeoff"))
    so = await _so(db, a1)
    hapus = [p for p in so["payments"] if p.get("kind") == "hapus_sisa" and p["amount"] > 0]
    n_dec = await jumlah("payment_variance_decisions", {"receipt_id": k["id"], "status": {"$nin": ["reversed", "cancelled"]}})
    did = (r1 if r1.status_code == 200 else r2).json()["id"]
    jes = await db.journal_entries.count_documents({"source_type": "payment_variance_writeoff", "status": {"$ne": "void"},
                                                    "source_id": {"$regex": "^" + did}})
    print("OBS hapus sisa bersamaan", r1.status_code, r2.status_code, "baris", len(hapus), "keputusan", n_dec, "jurnal", jes)
    assert sorted([r1.status_code, r2.status_code]) == [200, 409]
    assert len(hapus) == 1 and n_dec == 1 and jes == 1


async def test_FX06_koreksi_batal_hapus_sisa_lalu_putus_lagi(klien, kepala_admin, db, dunia):
    a1 = await _pesanan(db, dunia["A"], 1 * JT, label="F6b-")
    r = await _kwitansi(klien, kepala_admin, dunia["A"], 990_000, [(a1, 990_000)])
    k = r.json()
    r1 = await _putus(klien, kepala_admin, k["id"], "writeoff")
    assert r1.status_code == 200, r1.text
    did = r1.json()["id"]
    rv = await klien.post(f"/api/payment-variances/{did}/reverse", headers=kepala_admin, json={"reason": "uji batal hapus sisa"})
    assert rv.status_code == 200, rv.text
    rv2 = await klien.post(f"/api/payment-variances/{did}/reverse", headers=kepala_admin, json={"reason": "uji batal lagi"})
    so = await _so(db, a1)
    net = 0.0
    async for je in db.journal_entries.find({"status": {"$ne": "void"}, "source_id": {"$regex": "^" + did}}):
        net += sum(float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
                   for ln in je["lines"] if ln["account_code"] == "6-9100")
    print("OBS batal hapus sisa", rv.status_code, rv2.status_code, "Σbayar", sum(p["amount"] for p in so["payments"]),
          "Δ6-9100", net)
    # batal kedua dijawab 200 (keputusan sudah `reversed` dikembalikan apa adanya) — yang penting tanpa efek kedua
    assert rv2.status_code in (200, 400, 409), rv2.text
    assert await jumlah("journal_entries", {"source_type": "payment_variance_reversal", "source_id": {"$regex": "^" + did},
                                            "status": {"$ne": "void"}}) == 1
    assert sum(p["amount"] for p in so["payments"]) == 990_000 and round(net, 2) == 0
    r3 = await _putus(klien, kepala_admin, k["id"], "writeoff")
    so = await _so(db, a1)
    print("OBS putus lagi sesudah batal", r3.status_code, "Σbayar", sum(p["amount"] for p in so["payments"]))
    assert r3.status_code in (200, 409)
    assert sum(p["amount"] for p in so["payments"]) in (990_000, 1 * JT)


# ── FX-07 ────────────────────────────────────────────────────────────────────────────────────────────────────────
async def _faktur_tutup_sisa(klien, h, db):
    from services import gl_service as gl
    vb = _id("vb")
    await db.vendor_bills.insert_one({
        "id": vb, "bill_number": vb.upper(), "entity_id": KSC, "supplier_id": "sup_b1", "supplier_name": "Pemasok",
        "status": "posted", "grand_total": 5 * JT, "subtotal": 5 * JT, "amount_paid": 0.0, "payments": [],
        "timeline": [], "po_id": None, "bill_date": _hari(), "created_at": now_iso()})
    await gl._insert_entry(lines=[{"account_code": "5-1000", "debit": 5 * JT, "credit": 0.0},
                                  {"account_code": "2-1100", "debit": 0.0, "credit": 5 * JT}],
                           description="faktur pemasok (fixture)", date=now_iso(), source_type="vendor_bill",
                           source_id=vb, entity_id=KSC, created_by="uji")
    r = await klien.post(f"/api/vendor-bills/{vb}/pay", headers={**h, "Idempotency-Key": _id("k")}, json={
        "amount": 4_990_000, "paid_at": _hari(), "bank_account_id": "rek_pk19_b",
        "variance": {"kind": "ap_writeoff", "reason_code": "supplier_discount", "note": "uji bantah"}})
    assert r.status_code == 200, r.text
    return vb, await db.payment_variance_decisions.find_one({"bill_id": vb}, {"_id": 0})


async def test_FX07_ulang_dan_bersamaan_batal_tutup_sisa_hutang(klien, kepala_admin, db, dunia):
    vb, dec = await _faktur_tutup_sisa(klien, kepala_admin, db)
    r1, r2 = await asyncio.gather(
        klien.post(f"/api/payment-variances/{dec['id']}/reverse", headers=kepala_admin, json={"reason": "batal uji 1"}),
        klien.post(f"/api/payment-variances/{dec['id']}/reverse", headers=kepala_admin, json={"reason": "batal uji 2"}))
    r3 = await klien.post(f"/api/payment-variances/{dec['id']}/reverse", headers=kepala_admin, json={"reason": "batal uji 3"})
    rev = await _jurnal(db, "payment_variance_reversal", f"{dec['id']}")
    print("OBS batal AP", r1.status_code, r2.status_code, r3.status_code, "jurnal pembalik", len(rev), _baris(rev))
    assert len(rev) == 1 and _baris(rev) == [("2-1100", 0.0, 10_000.0), ("4-9000", 10_000.0, 0.0)]
    assert r3.status_code in (200, 400, 409)   # ulang = keputusan `reversed` dikembalikan, tanpa jurnal kedua
    bill = await db.vendor_bills.find_one({"id": vb}, {"_id": 0})
    assert bill["status"] != "paid"


async def test_FX07_periode_tertutup_batal_tutup_sisa_hutang(klien, kepala_admin, db, dunia):
    from services.vendor_bill_service import bill_financials
    vb, dec = await _faktur_tutup_sisa(klien, kepala_admin, db)
    c = await tutup_periode(KSC, now_iso()[:7])
    try:
        r = await klien.post(f"/api/payment-variances/{dec['id']}/reverse", headers=kepala_admin,
                             json={"reason": "batal saat periode tertutup"})
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
    bill = await db.vendor_bills.find_one({"id": vb}, {"_id": 0})
    d2 = await db.payment_variance_decisions.find_one({"id": dec["id"]}, {"_id": 0})
    rev = await _jurnal(db, "payment_variance_reversal", f"{dec['id']}")
    print("OBS batal AP periode tertutup", r.status_code, r.text[:160], "keputusan", d2["status"],
          d2.get("reversal_gl_status"), "faktur", bill["status"], bill_financials(bill)["outstanding"], "jurnal", len(rev))
    # Aman bila: ditolak tanpa perubahan, ATAU diterima dengan penanda gagal yang terlihat (bukan diam-diam).
    if r.status_code == 200:
        assert len(rev) == 1 or d2.get("reversal_gl_status") == "failed", "hutang hidup lagi tanpa jurnal dan tanpa penanda"
    else:
        assert d2["status"] != "reversed" and bill["status"] == "paid" and len(rev) == 0
