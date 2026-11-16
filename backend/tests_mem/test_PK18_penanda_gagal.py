"""PK-18 — penanda gagal (`gl_status`) dan panel Posting Gagal untuk semua jenis dokumen yang menjurnal.

Lihat docs/blueprint/unit/PK-18.md. Persiapan bersama: PT `ent_ksc`, admin seed. "Paksa gagal" = fixture
`paksa_jurnal_gagal("akun", …)` (menonaktifkan akun lawan untuk PT itu lewat `gl_service.update_account`, tanpa
penolak pemakaian — penolak hanya dipasang di endpoint PATCH) sebelum aksi; akun aktif lagi sebelum ulang.
Faktur contoh: neto Rp 10.000.000 + PPN Rp 1.100.000 = Rp 11.100.000.

Dokumen sumber = fixture yang disisipkan langsung (isi secukupnya untuk lolos pemeriksaan yang ada); aksinya dan ulang
posting dijalankan lewat API (alur). U13 (dua ulang bersamaan) di MongoDB asli: backend/tests/test_bp_PK18_ulang_bersamaan_mongo.py.
"""
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from core_utils import now_iso
from pembantu import jurnal, jumlah, saldo_akun, tutup_periode
from services import gl_service as gl
from services.book_date import periode_buku, tanggal_buku

KSC = "ent_ksc"
JT = 1_000_000
PENGAJU = "usr_pengaju_pk18"   # pembuat dokumen ≠ admin penyetuju (kontrol dua orang KF-T6)
ROOT = Path(__file__).resolve().parents[2]
PANEL = "/api/finance/posting-failures"


def uid(awalan: str) -> str:
    return f"{awalan}_pk18_{uuid.uuid4().hex[:8]}"


async def panel(klien, h, **q):
    r = await klien.get(PANEL, headers=h, params=q)
    assert r.status_code == 200, r.text
    return r.json()


async def ulang(klien, h, kind, doc_id):
    return await klien.post(f"{PANEL}/{kind}/{doc_id}/retry", headers=h)


async def jurnal_aktif(source_type: str, source_id: str):
    from db import db
    return await db.journal_entries.find(
        {"source_type": source_type, "source_id": source_id, "status": {"$ne": "void"}}, {"_id": 0}).to_list(10)


def baris(je):
    """{akun: (debit, kredit)} — satu jurnal."""
    out = {}
    for ln in je["lines"]:
        d, c = out.get(ln["account_code"], (0.0, 0.0))
        out[ln["account_code"]] = (round(d + float(ln.get("debit") or 0), 2), round(c + float(ln.get("credit") or 0), 2))
    return out


# ── Fixture dokumen ──────────────────────────────────────────────────────────────────────────────────────────────────
async def _faktur(db, status: str, **lain) -> str:
    bid = uid("vb")
    await db.vendor_bills.insert_one({
        "id": bid, "bill_number": f"VB/PK18/{bid[-8:]}", "entity_id": KSC, "status": status, "po_id": "",
        "supplier_id": "sup_pk18", "supplier_name": "Pemasok Uji PK-18", "items": [], "subtotal": 10 * JT,
        "ppn_amount": 1.1 * JT, "tax_amount": 1.1 * JT, "grand_total": 11.1 * JT, "total_amount": 11.1 * JT,
        "amount_paid": 0.0, "payments": [], "created_by": "Pengaju", "created_by_id": PENGAJU,
        "approval_status": "pending" if status == "pending_approval" else "not_required", "timeline": [],
        "bill_date": "2026-10-15", "created_at": now_iso(), **lain})
    return bid


async def _produk_gudang(db, *, harga: float) -> tuple:
    pid, wid = uid("prd"), uid("wh")
    await db.products.insert_one({"id": pid, "name": "Kain Uji PK-18", "sku": f"SKU-{pid}", "base_unit": "meter",
                                  "harga_pokok": harga, "is_active": True})
    await db.warehouses.insert_one({"id": wid, "name": "Gudang Uji PK-18", "entity_id": KSC, "is_active": True})
    return pid, wid


async def _roll(db, pid, wid, *, panjang: float, harga: float, **lain) -> str:
    rid = uid("roll")
    await db.inventory_rolls.insert_one({
        "id": rid, "roll_no": f"R-{rid[-6:]}", "product_id": pid, "warehouse_id": wid, "owner_entity_id": KSC,
        "entity_id": KSC, "unit": "meter", "status": "available", "length_initial": panjang,
        "length_remaining": panjang, "unit_cost": harga, "base_unit_cost": harga, "grade": "A", "lot": "LOT-PK18",
        "created_at": now_iso(), **lain})
    from services.roll_service import rebuild_balance
    await rebuild_balance(pid, wid, KSC)
    return rid


# ── U1 — periode tertutup: ditolak sebelum tulisan apa pun ───────────────────────────────────────────────────────────
async def test_PK18_U1_periode_tertutup_faktur_ditolak_tanpa_tulisan(klien, kepala_admin, db):
    """Jurnal faktur bertanggal `posted_at` = hari ini (tanggal yang dipakai fungsi posting), jadi periode yang ditutup =
    bulan buku berjalan (laporan: koreksi U1). Faktur menunggu persetujuan → Setujui."""
    bid = await _faktur(db, "pending_approval")
    je0 = await jumlah("journal_entries", {})
    c = await tutup_periode(KSC, periode_buku())
    try:
        r = await klien.post(f"/api/vendor-bills/{bid}/approve", headers=kepala_admin)
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
    assert r.status_code == 409 and "sudah ditutup" in r.json()["detail"], r.text
    doc = await db.vendor_bills.find_one({"id": bid})
    assert doc["status"] == "pending_approval" and "gl_status" not in doc and doc.get("approval_status") == "pending"
    assert await jumlah("journal_entries", {}) == je0


# ── U2/U3 — faktur pemasok: jurnal gagal tercatat, ulang tepat sekali ───────────────────────────────────────────────
@pytest.fixture(scope="module")
async def faktur_gagal(klien, kepala_admin, db):
    return {"id": await _faktur(db, "pending_approval")}


async def test_PK18_U2_faktur_akun_nonaktif_jurnal_gagal_terlihat_di_panel(klien, kepala_admin, db, faktur_gagal,
                                                                            paksa_jurnal_gagal):
    bid = faktur_gagal["id"]
    async with paksa_jurnal_gagal("akun", entity_id=KSC, kode_akun="2-1100"):
        r = await klien.post(f"/api/vendor-bills/{bid}/approve", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert r.json()["gl_status"] == "failed" and "2-1100 nonaktif" in r.json()["gl_error"]
    doc = await db.vendor_bills.find_one({"id": bid})
    assert doc["status"] == "posted" and doc["gl_status"] == "failed" and "2-1100 nonaktif" in doc["gl_error"]
    assert doc.get("gl_failed_at")
    assert await jurnal_aktif("vendor_bill", bid) == []
    p = await panel(klien, kepala_admin, kind="vendor_bill")
    assert p["total"] == 1 and p["counts"]["vendor_bill"] == 1
    assert p["items"][0]["number"] == doc["bill_number"] and p["items"][0]["amount"] == 11_100_000
    assert p["items"][0]["link"]["focus_id"] == bid and p["labels"]["vendor_bill"] == "Faktur Pemasok"


async def test_PK18_U3_ulang_dua_kali_tepat_satu_jurnal(klien, kepala_admin, db, faktur_gagal):
    bid = faktur_gagal["id"]
    h0 = await saldo_akun("2-1100", KSC)
    r1 = await ulang(klien, kepala_admin, "vendor_bill", bid)
    r2 = await ulang(klien, kepala_admin, "vendor_bill", bid)
    assert r1.status_code == 200 and r1.json()["gl_status"] == "posted", r1.text
    assert r2.status_code == 404, r2.text
    jes = await jurnal_aktif("vendor_bill", bid)
    assert len(jes) == 1 and r1.json()["journal_entry_id"] == jes[0]["id"]
    # Hitungan tangan: neto 11.100.000 − 1.100.000 = 10.000.000 → Dr 2-1150 GR/IR; PPN 1.100.000 → Dr 1-1500;
    # Cr 2-1100 Hutang = grand total 11.100.000.
    assert baris(jes[0]) == {"2-1150": (10 * JT, 0.0), "1-1500": (1.1 * JT, 0.0), "2-1100": (0.0, 11.1 * JT)}
    doc = await db.vendor_bills.find_one({"id": bid})
    # Saldo 2-1100 (normal kredit) naik 11.100.000 = sisa hutang faktur (11.100.000 − 0).
    assert round(await saldo_akun("2-1100", KSC) - h0, 2) == round(doc["grand_total"] - doc["amount_paid"], 2) == 11.1 * JT
    assert doc["gl_status"] == "posted" and doc["gl_error"] == "" and doc["journal_entry_id"] == jes[0]["id"]


# ── U4 — landed cost ─────────────────────────────────────────────────────────────────────────────────────────────────
async def test_PK18_U4_landed_cost_gagal_lalu_diulang(klien, kepala_admin, db, paksa_jurnal_gagal):
    pid, wid = await _produk_gudang(db, harga=50_000)
    po = uid("po")
    await _roll(db, pid, wid, panjang=100, harga=50_000, acquired={"via": "po", "ref_id": po})
    vid = uid("lcv")
    await db.landed_cost_vouchers.insert_one({
        "id": vid, "voucher_number": f"LC/PK18/{vid[-6:]}", "entity_id": KSC, "status": "pending_approval",
        "po_ids": [po], "total_cost": 3 * JT, "amount_paid": 0, "basis": "value", "provider_name": "Ekspedisi Uji",
        "created_by": "Pengaju", "created_by_id": PENGAJU, "timeline": [], "payments": []})
    async with paksa_jurnal_gagal("akun", entity_id=KSC, kode_akun="1-1300"):
        r = await klien.post(f"/api/landed-costs/{vid}/approve", headers=kepala_admin)
    assert r.status_code == 200, r.text
    v = await db.landed_cost_vouchers.find_one({"id": vid})
    assert v["status"] == "applied" and v["allocated_total"] == 3 * JT and v["gl_status"] == "failed"
    assert r.json()["gl_status"] == "failed"
    r2 = await ulang(klien, kepala_admin, "landed_cost", vid)
    assert r2.status_code == 200 and r2.json()["gl_status"] == "posted", r2.text
    jes = await jurnal_aktif("landed_cost", vid)
    assert len(jes) == 1 and baris(jes[0]) == {"1-1300": (3 * JT, 0.0), "2-1100": (0.0, 3 * JT)}


# ── U5 — langkah makloon ─────────────────────────────────────────────────────────────────────────────────────────────
async def test_PK18_U5_kirim_bahan_makloon_maju_walau_jurnal_gagal(klien, kepala_admin, db, paksa_jurnal_gagal):
    pid, wid = await _produk_gudang(db, harga=50_000)
    await _roll(db, pid, wid, panjang=50, harga=50_000)        # bahan 50 m × 50.000 = 2.500.000
    mko = uid("mko")
    await db.makloon_orders.insert_one({
        "id": mko, "mko_number": f"MKO/PK18/{mko[-6:]}", "entity_id": KSC, "status": "draft",
        "from_warehouse_id": wid, "timeline": [], "steps": [{
            "seq": 1, "status": "pending", "material_flow": "moves", "input_product_id": pid, "input_name": "Kain",
            "input_qty": 50, "input_unit": "meter", "output_product_id": pid, "process_type": "celup",
            "stage_label": "Celup", "makloon_id": "mitra_pk18", "makloon_name": "Mitra Uji",
            "issue_ref": f"{mko}:1", "expected_output_qty": 50}]})
    async with paksa_jurnal_gagal("akun", entity_id=KSC, kode_akun="1-1350"):
        r = await klien.post(f"/api/makloon-orders/{mko}/issue", headers=kepala_admin, json={"step_seq": 1})
    assert r.status_code == 200, r.text
    o = await db.makloon_orders.find_one({"id": mko})
    st = o["steps"][0]
    assert st["status"] == "issued" and st["gl_status"] == "failed" and "1-1350 nonaktif" in st["gl_error"]
    assert not o.get("saga_lock")
    p = await panel(klien, kepala_admin, kind="makloon_step")
    row = next(i for i in p["items"] if i["id"] == f"{mko}:1")
    assert row["amount"] == 2.5 * JT
    r2 = await ulang(klien, kepala_admin, "makloon_step", f"{mko}:1")
    assert r2.status_code == 200 and r2.json()["gl_status"] == "posted", r2.text
    jes = await jurnal_aktif("subcon_issue", f"{mko}:1")
    assert len(jes) == 1 and baris(jes[0]) == {"1-1350": (2.5 * JT, 0.0), "1-1300": (0.0, 2.5 * JT)}
    assert (await db.makloon_orders.find_one({"id": mko}))["steps"][0]["gl_status"] == "posted"


async def test_PK18_U5b_catat_jasa_makloon_gagal_lalu_diulang(klien, kepala_admin, db, paksa_jurnal_gagal):
    """Tambahan (bukan baris spesifikasi): langkah jasa murni — tagihan jasa lahir, langkah `received` walau jurnal
    jasa gagal; ulang menerbitkannya sekali dari nilai tagihan yang tersimpan. K-82 (MP-T4b): bawaan semua PT "saat
    faktur" → jurnal jasa Dr 1-1350 / Cr GR/IR 2-1150 (hutang 2-1100 baru lahir saat faktur mitra dicocokkan)."""
    pid, wid = await _produk_gudang(db, harga=50_000)
    mko = uid("mko")
    await db.makloon_orders.insert_one({
        "id": mko, "mko_number": f"MKO/PK18/{mko[-6:]}", "entity_id": KSC, "status": "in_progress",
        "from_warehouse_id": wid, "timeline": [], "steps": [{
            "seq": 1, "status": "pending", "material_flow": "service_only", "input_product_id": pid,
            "input_name": "Kain", "input_qty": 10, "input_unit": "meter", "output_product_id": pid,
            "process_type": "screen", "stage_label": "Screen", "makloon_id": "mitra_pk18", "makloon_name": "Mitra Uji",
            "issue_ref": f"{mko}:1", "expected_output_qty": 10}]})
    async with paksa_jurnal_gagal("akun", entity_id=KSC, kode_akun="2-1150"):
        r = await klien.post(f"/api/makloon-orders/{mko}/record-service", headers=kepala_admin,
                             json={"step_seq": 1, "tariff": 300_000})
    assert r.status_code == 200, r.text
    st = (await db.makloon_orders.find_one({"id": mko}))["steps"][0]
    assert st["status"] == "received" and st["gl_status"] == "failed" and st["service_bill_id"]
    assert await jurnal_aktif("subcon_service", st["service_bill_id"]) == []
    r2 = await ulang(klien, kepala_admin, "makloon_step", f"{mko}:1")
    assert r2.status_code == 200 and r2.json()["gl_status"] == "posted", r2.text
    jes = await jurnal_aktif("subcon_service", st["service_bill_id"])
    assert len(jes) == 1 and baris(jes[0]) == {"1-1350": (300_000.0, 0.0), "2-1150": (0.0, 300_000.0)}


# ── U6 — susut potong ────────────────────────────────────────────────────────────────────────────────────────────────
async def test_PK18_U6_susut_potong_gagal_lalu_diulang(klien, kepala_admin, db, paksa_jurnal_gagal):
    pid, wid = await _produk_gudang(db, harga=20_000)
    rid = await _roll(db, pid, wid, panjang=50, harga=20_000, length_reserved=10, length_reservations=[
        {"id": "rsv_pk18", "qty": 10, "ref": {"type": "manual", "id": "ref_pk18"}, "status": "reserved"}])
    async with paksa_jurnal_gagal("akun", entity_id=KSC, kode_akun="5-9500"):
        r = await klien.post(f"/api/inventory/rolls/{rid}/reservations/rsv_pk18/cut", headers=kepala_admin,
                             json={"actual_length": 10, "waste": 2, "waste_reason": "susut uji PK-18 di ujung roll"})
    assert r.status_code == 200, r.text
    mv = await db.inventory_movements.find_one({"id": "mov_cutw_rsv_pk18"})
    assert mv["movement_type"] == "cut_waste" and mv["gl_status"] == "failed" and mv["gl_amount"] == 40_000
    r2 = await ulang(klien, kepala_admin, "cut_waste", "mov_cutw_rsv_pk18")
    assert r2.status_code == 200 and r2.json()["gl_status"] == "posted", r2.text
    # Hitungan tangan: susut 2 m × biaya roll 20.000 = 40.000.
    jes = await jurnal_aktif("inventory_writeoff", "cutw:rsv_pk18")
    assert len(jes) == 1 and baris(jes[0]) == {"5-9500": (40_000.0, 0.0), "1-1300": (0.0, 40_000.0)}


# ── U7 — batal kwitansi ──────────────────────────────────────────────────────────────────────────────────────────────
async def test_PK18_U7_batal_kwitansi_pembalik_gagal_lalu_diulang(klien, kepala_admin, db, paksa_jurnal_gagal):
    rcp, kas = uid("rcp"), uid("cash")
    await db.ar_receipts.insert_one({
        "id": rcp, "number": f"KW/PK18/{rcp[-6:]}", "entity_id": KSC, "status": "posted", "customer_id": "cus_pk18",
        "customer_name": "Pelanggan Uji", "amount": 500_000, "method": "tunai", "allocations": [], "applied_total": 500_000,
        "used_deposit": 0, "unapplied_amount": 0, "deposit_delta": 0, "cash_txn_id": kas, "receipt_date": tanggal_buku(),
        "gl_status": "posted", "created_at": now_iso()})
    txn = {"id": kas, "number": f"KAS/{kas[-6:]}", "entity_id": KSC, "direction": "in", "amount": 500_000,
           "cash_type": "kas_kecil", "category": "Penerimaan Piutang", "ref_type": "ar_receipt", "ref_id": rcp,
           "txn_date": tanggal_buku(), "status": "posted", "created_at": now_iso()}
    await db.cash_transactions.insert_one(dict(txn))
    await gl.post_cash_durable(txn)          # fixture: kwitansi tunai terposting (Dr 1-1110 / Cr 1-1200)
    assert len(await jurnal_aktif("cash_transaction", kas)) == 1
    async with paksa_jurnal_gagal("akun", entity_id=KSC, kode_akun="1-1110"):
        r = await klien.post(f"/api/ar-receipts/{rcp}/void", headers=kepala_admin, params={"reason": "uji PK-18"})
    assert r.status_code == 200, r.text
    doc = await db.ar_receipts.find_one({"id": rcp})
    assert doc["status"] == "void" and doc["void_gl_status"] == "failed" and "1-1110 nonaktif" in doc["void_gl_error"]
    r2 = await ulang(klien, kepala_admin, "ar_receipt_void", rcp)
    assert r2.status_code == 200 and r2.json()["gl_status"] == "posted", r2.text
    assert (await db.ar_receipts.find_one({"id": rcp}))["void_gl_status"] == "posted"
    assert len(await jurnal_aktif("cash_transaction_void", kas)) == 1


# ── U8 — surat jalan tanpa jurnal → not_required (GL-12) ────────────────────────────────────────────────────────────
async def test_PK18_U8_surat_jalan_nominal_nol_tidak_ditulis_posted(klien, kepala_admin, db):
    so, shp = uid("so"), uid("shp")
    await db.sales_orders.insert_one({"id": so, "number": f"SO/PK18/{so[-6:]}", "entity_id": KSC, "status": "shipped",
                                      "customer_id": "cus_pk18", "items": [], "grand_total": 0, "payments": []})
    await db.shipments.insert_one({"id": shp, "shipment_no": f"SJ/PK18/{shp[-6:]}", "entity_id": KSC, "order_id": so,
                                   "status": "dispatched", "rolls": [], "qty": 0, "gl_status": "failed",
                                   "gl_error": "uji: jurnal dipaksa gagal", "created_at": now_iso()})
    r = await ulang(klien, kepala_admin, "shipment", shp)
    assert r.status_code == 200, r.text
    assert r.json()["gl_status"] == "not_required"
    assert (await db.shipments.find_one({"id": shp}))["gl_status"] == "not_required"


# ── U9 — aset tetap ──────────────────────────────────────────────────────────────────────────────────────────────────
async def test_PK18_U9_aset_tetap_tersimpan_jurnal_gagal_lalu_diulang(klien, kepala_admin, db, paksa_jurnal_gagal):
    # PK-23 — sumber dana wajib (kas: rekening fixture) dan akun aset nonaktif kini ditolak PERIKSA sebelum tulisan
    # (400, PK-23 U6); kegagalan jurnal dipaksa di pintu sisip.
    if not await db.bank_accounts.find_one({"id": "rek_pk18_u9"}):
        await db.bank_accounts.insert_one({"id": "rek_pk18_u9", "name": "BCA PK18", "entity_id": KSC,
                                           "account_type": "bank", "cash_type": "kas_besar", "is_active": True,
                                           "opening_balance": 0})
    async with paksa_jurnal_gagal("sisip", entity_id=KSC, source_type="fixed_asset_acquisition"):
        r = await klien.post("/api/fixed-assets", headers=kepala_admin, json={
            "name": "Mesin potong PK-18", "category": "Peralatan & Mesin", "acquisition_cost": 12 * JT,
            "acquisition_date": tanggal_buku(), "useful_life_months": 48, "entity_id": KSC,
            "funding_source": "kas", "account_id": "rek_pk18_u9"})
    assert r.status_code == 200, r.text
    aid = r.json()["id"]
    a = await db.fin_fixed_assets.find_one({"id": aid})
    assert a["gl_status"] == "failed" and r.json()["gl_status"] == "failed"
    r2 = await ulang(klien, kepala_admin, "fixed_asset", aid)
    assert r2.status_code == 200 and r2.json()["gl_status"] == "posted", r2.text
    jes = await jurnal_aktif("fixed_asset_acquisition", aid)
    assert len(jes) == 1 and jes[0]["total_debit"] == 12 * JT
    assert (await db.fin_fixed_assets.find_one({"id": aid}))["acquisition_je"] == jes[0]["number"]


# ── U10/U11 — akun dipakai pemetaan / bersaldo tidak bisa dinonaktifkan ─────────────────────────────────────────────
async def test_PK18_U10_akun_dipakai_pemetaan_tidak_bisa_dinonaktifkan(klien, kepala_admin, db):
    r = await klien.patch("/api/gl/accounts/2-1100", headers=kepala_admin, json={"is_active": False})
    assert r.status_code == 409, r.text
    assert "masih dipakai pemetaan akun" in r.json()["detail"] and "Pemetaan Akun" in r.json()["detail"]
    acc = await db.gl_accounts.find_one({"code": "2-1100", "entity_id": {"$in": [None, ""]}})
    assert acc.get("is_active") is not False


async def test_PK18_U11_akun_bersaldo_tidak_bisa_dinonaktifkan_sampai_dibalik(klien, kepala_admin, db):
    r = await klien.post("/api/gl/accounts", headers=kepala_admin,
                         json={"code": "6-4999", "name": "Beban Uji PK-18", "type": "expense"})
    assert r.status_code == 200, r.text
    je = await jurnal(KSC, tanggal_buku(), [("6-4999", 1_000, 0), ("1-1100", 0, 1_000)], "uji saldo PK-18",
                      "pk18_u11")
    r = await klien.patch("/api/gl/accounts/6-4999", headers=kepala_admin, json={"is_active": False})
    assert r.status_code == 409 and "masih bersaldo Rp 1.000" in r.json()["detail"], r.text
    await gl.reverse_entry(je["id"], tanggal_buku(), "uji PK-18: saldo dipindahkan", {"name": "Uji", "id": "u"})
    r = await klien.patch("/api/gl/accounts/6-4999", headers=kepala_admin, json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False, r.text


# ── U12 — izin ulang ─────────────────────────────────────────────────────────────────────────────────────────────────
async def test_PK18_U12_ulang_butuh_accounting_manage(klien, db, akun, sesi, peran_tanpa_acuan):
    kas = uid("cash")
    await db.cash_transactions.insert_one({
        "id": kas, "number": f"KAS/{kas[-6:]}", "entity_id": KSC, "direction": "out", "amount": 250_000,
        "cash_type": "kas_besar", "category": "Beban Operasional", "txn_date": tanggal_buku(), "status": "posted",
        "gl_status": "failed", "gl_error": "uji: jurnal dipaksa gagal", "created_at": now_iso()})
    lihat = await sesi(await akun(await peran_tanpa_acuan({"accounting": ["view"]})))
    kelola = await sesi(await akun(await peran_tanpa_acuan({"accounting": ["view", "manage"]})))
    r = await ulang(klien, lihat, "cash_transaction", kas)
    assert r.status_code == 403, r.text
    assert (await klien.get(PANEL, headers=lihat)).status_code == 200
    r = await ulang(klien, kelola, "cash_transaction", kas)
    assert r.status_code == 200 and r.json()["gl_status"] == "posted", r.text
    assert len(await jurnal_aktif("cash_transaction", kas)) == 1


# ── U14 — penjaga statik ─────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("arg", [[], ["--self-test"]])
def test_PK18_U14_penjaga_cakupan_posting(arg):
    p = subprocess.run([sys.executable, "scripts/guardrails/verify_posting_coverage.py", *arg], cwd=ROOT,
                       capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stdout[-3000:] + p.stderr[-2000:]


# ── Inti (a) — pintu tahan-gagal dan panel berhalaman ────────────────────────────────────────────────────────────────
async def test_PK18_inti_post_durable_posted_failed_not_required(db):
    vid = uid("pd")
    await db.cash_transactions.insert_one({"id": vid, "steps": [{"seq": 1}, {"seq": 2}]})
    st_id = uid("src")

    async def gagal():
        raise RuntimeError("uji: akun nonaktif")

    r = await gl.post_durable("cash_transactions", vid, gagal, source_type="uji", source_id=st_id)
    d = await db.cash_transactions.find_one({"id": vid})
    assert r["gl_status"] == d["gl_status"] == "failed" and d["gl_error"] == "uji: akun nonaktif" and d["gl_failed_at"]
    with pytest.raises(RuntimeError):
        await gl.post_durable("cash_transactions", vid, gagal, source_type="uji", source_id=st_id, raise_on_fail=True)

    async def kosong():
        return None

    r = await gl.post_durable("cash_transactions", vid, kosong, source_type="uji", source_id=st_id)
    d = await db.cash_transactions.find_one({"id": vid})
    assert r["gl_status"] == d["gl_status"] == "not_required" and d["gl_error"] == ""

    async def terbit():
        return await jurnal(KSC, tanggal_buku(), [("6-1000", 5_000, 0), ("1-1100", 0, 5_000)], "uji PK-18", st_id)

    r = await gl.post_durable("cash_transactions", vid, terbit, source_type="uji", source_id=st_id,
                              field="steps.$.gl_status", match={"steps.seq": 2})
    d = await db.cash_transactions.find_one({"id": vid})
    assert r["gl_status"] == "posted" and d["steps"][1]["gl_status"] == "posted"
    assert d["steps"][1]["journal_entry_id"] == r["journal_entry_id"] and "gl_status" not in d["steps"][0]
    # Ulang: jurnal sudah ada, fungsi posting tidak menerbitkan lagi (None) → tetap `posted` dari pencarian jurnal.
    r = await gl.post_durable("cash_transactions", vid, kosong, source_type="uji", source_id=st_id)
    assert r["gl_status"] == "posted" and r["journal_entry_id"] == d["steps"][1]["journal_entry_id"]
    await db.cash_transactions.delete_one({"id": vid})


async def test_PK18_inti_panel_berhalaman_hitungan_dari_kueri(klien, kepala_admin, db):
    ids = []
    for i in range(5):
        kas = f"cash_pk18_hal_{i}"
        ids.append(kas)
        await db.cash_transactions.insert_one({
            "id": kas, "number": f"KAS/HAL/{i}", "entity_id": KSC, "direction": "out", "amount": 1_000 + i,
            "status": "posted", "gl_status": "failed", "gl_error": "uji", "gl_failed_at": f"2026-11-0{i + 1}T00:00:00+00:00"})
    await db.cash_transactions.insert_one({"id": "cash_pk18_hal_kanda", "number": "KAS/HAL/K", "entity_id": "ent_kanda",
                                           "direction": "out", "amount": 9, "status": "posted", "gl_status": "failed"})
    semua = await panel(klien, kepala_admin)
    p1 = await panel(klien, kepala_admin, kind="cash_transaction", page=1, page_size=2)
    p3 = await panel(klien, kepala_admin, kind="cash_transaction", page=3, page_size=2)
    n = p1["counts"]["cash_transaction"]
    assert n >= 5 and p1["total"] == n and p1["page"] == 1 and p1["page_size"] == 2
    assert [i["id"] for i in p1["items"]] == ["cash_pk18_hal_4", "cash_pk18_hal_3"]   # terbaru gagal dulu
    assert p3["total"] == n and len(p3["items"]) == min(2, max(0, n - 4))
    assert "cash_pk18_hal_kanda" not in [i["id"] for i in semua["items"]]            # cakupan PT pengguna
    assert semua["total"] == sum(semua["counts"].values()) and len(semua["items"]) <= 50
    assert set(semua["labels"]) == set(semua["counts"])
    cnt = (await klien.get(f"{PANEL}/count", headers=kepala_admin)).json()
    assert cnt["total"] == semua["total"]
    r = await klien.get(PANEL, headers=kepala_admin, params={"kind": "tidak_ada"})
    assert r.status_code == 400 and r.json()["detail"] == "Jenis dokumen tidak dikenal"
    r = await ulang(klien, kepala_admin, "tidak_ada", "x")
    assert r.status_code == 400 and r.json()["detail"] == "Jenis dokumen tidak dikenal"
    r = await ulang(klien, kepala_admin, "cash_transaction", "cash_pk18_hal_kanda")
    assert r.status_code == 404 and "tidak ditemukan" in r.json()["detail"]
    await db.cash_transactions.delete_many({"id": {"$in": ids + ["cash_pk18_hal_kanda"]}})
