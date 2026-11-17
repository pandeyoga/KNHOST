"""PK-41 serah-terima (b) — laporan pendukung lewat HTTP (docs/blueprint/unit/PK-41.md, U1–U16; U17 = uji jalan layar).

Satuan angka: ribu rupiah kecuali disebut (`RB` = 1.000). Termin 30 hari (`payment_term_days`). Tiap skenario memakai PT
uji sendiri (`pt_uji`) supaya total laporan, saldo akun, dan Laba-Rugi tidak tercampur; U12 memakai `ent_ksc` +
`ent_kanda` (spesifikasi) dan diukur sebagai SELISIH sebelum/sesudah fixture.

FIXTURE (disisipkan langsung): pelanggan, pesanan, dokumen surat jalan + jurnal pendapatannya (bentuk
`post_shipment_revenue`), baris `payments[]`, tagihan pemasok, retur beli, voucher biaya masuk, nota kredit, dan jurnal
(`gl_service._insert_entry` dengan `source_type` asli). ALUR (API): `GET /api/ar/aging`, `GET /api/ar/aging/{id}`,
`GET /api/vendor-bills/payables/summary`, `POST /api/vendor-bills`, `GET /api/finance/cash-flow`,
`GET /api/finance/profitability`, `GET /api/finance/tower`, `GET /api/finance/cashflow-forecast`, `PUT /api/config/values`,
`POST /api/ai/query`; `compute_customer_credit` dan `close_period` dipanggil sebagai fungsi.

Hitung tangan per uji ada di komentarnya.
"""
from __future__ import annotations

import contextlib
import datetime
import itertools
import uuid

import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI, pt_uji

pytestmark = pytest.mark.anyio

ADMIN = "admin@kainnusantara.id"
KSC, KANDA = "ent_ksc", "ent_kanda"
RB = 1000
JT = 1_000_000


def _id(awal: str) -> str:
    return f"{awal}_pk41_{uuid.uuid4().hex[:8]}"


async def _pt(kode: str) -> str:
    from services.entity_lifecycle_service import invalidate_status_cache
    eid = await pt_uji(kode)
    invalidate_status_cache()
    return eid


async def _je(eid: str, tanggal: str, baris, source_type: str, source_id: str = "", *, ref=None, label: str = ""):
    from services import gl_service as gl
    return await gl._insert_entry(lines=[{"account_code": k, "debit": d, "credit": c} for k, d, c in baris],
                                  description=f"fixture PK-41 {source_type}", date=tanggal, source_type=source_type,
                                  source_id=source_id or _id(source_type), entity_id=eid, created_by="uji",
                                  source_label=label, ref=ref)


async def _pelanggan(db, eid: str, nama: str = "Toko PK41") -> dict:
    c = {"id": _id("cus"), "name": nama, "entity_id": eid, "status": "active", "payment_profile": {},
         "deposit_balance": 0, "assigned_sales_id": ""}
    await db.customers.insert_one(dict(c))
    return c


async def _pesanan(db, cus: dict, total: float, *, payments=(), payment_status="unpaid", status="partially_shipped",
                   items=None, ppn: float = 0.0) -> dict:
    so = {"id": _id("so"), "number": f"SO-PK41-{uuid.uuid4().hex[:5]}", "entity_id": cus["entity_id"],
          "customer_id": cus["id"], "customer_name": cus["name"], "status": status, "grand_total": float(total),
          "total_amount": float(total), "ppn_amount": ppn, "payments": [dict(p) for p in payments],
          "payment_status": payment_status, "payment_term_days": 30, "payment_term_code": "NET30",
          "items": items or [], "created_at": "2026-08-25T03:00:00+00:00"}
    await db.sales_orders.insert_one(dict(so))
    return so


async def _kirim(db, so: dict, nilai: float, tanggal: str, *, nomor: str = "") -> dict:
    """Surat jalan + jurnal pendapatannya (Dr piutang / Cr pendapatan) bertanggal `tanggal` (fixture)."""
    shid = _id("sj")
    nomor = nomor or f"SJ-{shid[-6:]}"
    await db.shipments.insert_one({"id": shid, "shipment_no": nomor, "order_id": so["id"], "status": "dispatched",
                                   "created_at": f"{tanggal}T03:00:00+00:00"})
    await _je(so["entity_id"], tanggal, [("1-1200", nilai, 0), ("4-1000", 0, nilai)], "shipment_revenue", shid,
              ref={"order_id": so["id"], "order_number": so["number"]}, label=nomor)
    return {"id": shid, "shipment_no": nomor}


def _bayar(nilai: float, tanggal: str) -> dict:
    return {"id": _id("pay"), "kind": "kas", "amount": nilai, "method": "transfer", "date": tanggal,
            "created_at": tanggal}


async def _get(klien, h, url, **params):
    r = await klien.get(url, headers=h, params={k: v for k, v in params.items() if v is not None})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
async def adm(sesi):
    simpan: dict = {}

    async def _h(eid: str):
        if eid not in simpan:
            simpan[eid] = await sesi(ADMIN, entitas=eid)
        return simpan[eid]
    return _h


def _beku(monkeypatch, tanggal_wib: str, jam_wib: int = 10):
    """Bekukan "hari ini" (`services.book_date._sekarang`, satu-satunya jam hari ini WIB)."""
    from services import book_date
    d = datetime.date.fromisoformat(tanggal_wib)
    beku = datetime.datetime(d.year, d.month, d.day, jam_wib, 0, tzinfo=book_date.WIB).astimezone(datetime.timezone.utc)
    monkeypatch.setattr(book_date, "_sekarang", lambda: beku)


@contextlib.contextmanager
def _sisip_massal(koleksi):
    """Fixture massal ber-id unik buatan uji: pemeriksaan indeks unik `mongomock` (memindai seluruh koleksi untuk TIAP
    dokumen, O(n²); dipasang `mongomock_motor` per objek koleksi) dilewati selama penyisipan koleksi `koleksi`."""
    inti = koleksi._AsyncMongoMockCollection__collection
    asli = inti._ensure_uniques
    inti._ensure_uniques = lambda *_a, **_k: None
    try:
        yield
    finally:
        inti._ensure_uniques = asli


@pytest.fixture
def to_list_seperti_motor(monkeypatch):
    """`mongomock_motor` mengabaikan panjang `to_list(n)` (selalu semua baris), sedangkan Motor asli memotong di n —
    batas itulah sumber RP-01. Selama uji U5/U6 kursor tiruan memotong seperti Motor (pola PK-42 U10)."""
    import mongomock_motor

    async def _to_list(self, length=None, *_a, **_kw):
        cur = self._AsyncCursor__cursor
        return list(cur) if length is None else list(itertools.islice(cur, int(length)))
    monkeypatch.setattr(mongomock_motor.AsyncCursor, "to_list", _to_list)


# ═══ U1, U15 — umur piutang per surat jalan; pencocokan ke saldo akun piutang ═══════════════════════════════════════
@pytest.fixture(scope="module")
async def data_u1(db):
    eid = await _pt("P41U1")
    cus = await _pelanggan(db, eid)
    so = await _pesanan(db, cus, 100 * RB)
    await _kirim(db, so, 40 * RB, "2026-09-01", nomor="SJ-U1")
    return {"eid": eid, "cus": cus, "so": so}


async def test_PK41_U1_umur_piutang_per_surat_jalan(klien, adm, data_u1):
    # Jatuh tempo 2026-09-01 + 30 = 2026-10-01; per 2026-11-15 lewat 45 hari → 31–60: 40; belum dikirim 60 → current.
    # (kode lama: seluruh 100 di 31–60 — jatuh tempo surat jalan pertama untuk seluruh pesanan)
    eid = data_u1["eid"]
    j = await _get(klien, await adm(eid), "/api/ar/aging", entity_id=eid, as_of="2026-11-15")
    row = next(c for c in j["customers"] if c["customer_id"] == data_u1["cus"]["id"])
    assert (row["b31_60"], row["current"], row["outstanding"], row["overdue"]) == (40 * RB, 60 * RB, 100 * RB, 40 * RB)
    assert (row["ar_ledger"], row["exposure"], row["oldest_days"]) == (40 * RB, 60 * RB, 45)
    t = j["totals"]
    assert (t["b31_60"], t["current"], t["total"], t["overdue"], t["ar_ledger"], t["exposure"]) == (
        40 * RB, 60 * RB, 100 * RB, 40 * RB, 40 * RB, 60 * RB)
    d = await _get(klien, await adm(eid), f"/api/ar/aging/{data_u1['cus']['id']}", as_of="2026-11-15")
    (it,) = d["items"]
    assert [(ln["sumber"], ln["ref_number"], ln["jatuh_tempo"], ln["sisa"], ln["hari_lewat"], ln["bucket"])
            for ln in it["lines"]] == [("surat_jalan", "SJ-U1", "2026-10-01", 40 * RB, 45, "b31_60"),
                                       ("belum_dikirim", data_u1["so"]["number"], None, 60 * RB, 0, "current")]
    assert (it["due_date"], it["days_late"], it["bucket"], it["ar_ledger"], it["exposure"]) == (
        "2026-10-01", 45, "b31_60", 40 * RB, 60 * RB)


async def test_PK41_U15_pencocokan_saldo_akun_piutang(klien, adm, data_u1):
    # Saldo akun piutang PT = Dr 1-1200 40 (jurnal surat jalan) = piutang tercatat 40 → selisih 0.
    eid = data_u1["eid"]
    rec = (await _get(klien, await adm(eid), "/api/ar/aging", entity_id=eid, as_of="2026-11-15"))["reconciliation"]
    assert (rec["ar_ledger_total"], rec["gl_balance"], rec["difference"]) == (40 * RB, 40 * RB, 0)
    assert rec["note"].startswith("Piutang tercatat sama dengan saldo akun piutang per 15 November 2026")


# ═══ U2 — uang muka sebelum kirim ═══════════════════════════════════════════════════════════════════════════════════
async def test_PK41_U2_bayar_sebelum_kirim(klien, adm, db):
    # Bayar 30 (1 Sep) dialokasikan ke surat jalan 50 (10 Sep) → tercatat 20; belum dikirim 100 − 50 = 50; total 70.
    eid = await _pt("P41U2")
    cus = await _pelanggan(db, eid)
    so = await _pesanan(db, cus, 100 * RB, payments=[_bayar(30 * RB, "2026-09-01")], payment_status="partial")
    await _kirim(db, so, 50 * RB, "2026-09-10")
    t = (await _get(klien, await adm(eid), "/api/ar/aging", entity_id=eid, as_of="2026-09-20"))["totals"]
    assert (t["total"], t["ar_ledger"], t["exposure"], t["current"], t["overdue"]) == (
        70 * RB, 20 * RB, 50 * RB, 70 * RB, 0)


# ═══ U3 — status kredit dari baris terkirim ════════════════════════════════════════════════════════════════════════
async def test_PK41_U3_status_kredit_baris_terkirim(data_u1, monkeypatch):
    # "Hari ini" 2026-11-15: lewat tempo hanya surat jalan 40 (lewat 45 hari); bagian belum dikirim 60 tidak telat.
    from services.customer_service import compute_customer_credit
    _beku(monkeypatch, "2026-11-15")
    c = await compute_customer_credit(data_u1["cus"])
    assert (c["overdue_amount"], c["max_overdue_days"], c["ar_outstanding"], c["ar_ledger"], c["exposure"]) == (
        40 * RB, 45, 100 * RB, 40 * RB, 60 * RB)


# ═══ U4 — posisi per tanggal ═══════════════════════════════════════════════════════════════════════════════════════
async def test_PK41_U4_posisi_per_tanggal(klien, adm, db):
    # Terkirim penuh 1 Okt (jatuh tempo 31 Okt); bayar 40 (15 Okt) + 60 (5 Nov); kini lunas.
    # per 31 Okt: 100 − 40 = 60 di current (lewat 0 hari); per 10 Nov: 100 − 100 = 0.
    eid = await _pt("P41U4")
    cus = await _pelanggan(db, eid)
    so = await _pesanan(db, cus, 100 * RB, payments=[_bayar(40 * RB, "2026-10-15"), _bayar(60 * RB, "2026-11-05")],
                        payment_status="paid", status="shipped")
    await _kirim(db, so, 100 * RB, "2026-10-01")
    t = (await _get(klien, await adm(eid), "/api/ar/aging", entity_id=eid, as_of="2026-10-31"))["totals"]
    assert (t["current"], t["total"], t["overdue"]) == (60 * RB, 60 * RB, 0)
    t = (await _get(klien, await adm(eid), "/api/ar/aging", entity_id=eid, as_of="2026-11-10"))["totals"]
    assert (t["total"], t["customers"]) == (0, 0)


# ═══ U5 — ringkasan hutang tidak terpotong 2.000 tagihan ════════════════════════════════════════════════════════════
async def test_PK41_U5_hutang_tanpa_batas_2000(klien, adm, db, to_list_seperti_motor):
    # 2.000 tagihan lunas disisipkan lebih dulu, lalu tagihan ke-2.001 `posted` Rp 50.000.000 belum dibayar.
    # (kode lama: 2.000 tagihan pertama tanpa urutan = semua lunas → total 0)
    eid = await _pt("P41U5")
    with _sisip_massal(db.vendor_bills):
        await db.vendor_bills.insert_many([{
            "id": f"vb_pk41_u5_{i}", "bill_number": f"VB-U5-{i}", "entity_id": eid, "status": "paid",
            "payment_status": "paid", "grand_total": 1000.0, "amount_paid": 1000.0, "supplier_id": "sup_pk41_u5",
            "supplier_name": "Pemasok U5", "bill_date": "2026-10-01", "due_date": "2026-10-31", "created_at": now_iso()}
            for i in range(2000)])
    await db.vendor_bills.insert_one({
        "id": "vb_pk41_u5_x", "bill_number": "VB-U5-X", "entity_id": eid, "status": "posted",
        "payment_status": "unpaid", "grand_total": 50 * JT, "amount_paid": 0.0, "supplier_id": "sup_pk41_u5",
        "supplier_name": "Pemasok U5", "bill_date": "2026-11-01", "due_date": "2026-12-01", "created_at": now_iso()})
    j = await _get(klien, await adm(eid), "/api/vendor-bills/payables/summary", entity_id=eid)
    assert j["total_outstanding"] == 50 * JT
    assert [b["bill_number"] for b in j["bills"]] == ["VB-U5-X"]


# ═══ U6 — umur piutang tidak terpotong 5.000 pelanggan ══════════════════════════════════════════════════════════════
async def test_PK41_U6_piutang_tanpa_batas_5000_pelanggan(klien, adm, db, to_list_seperti_motor):
    # 5.000 pelanggan tanpa pesanan, lalu pelanggan ke-5.001 dengan pesanan terkirim Rp 7.000.000 belum dibayar.
    # (kode lama: 5.000 pelanggan pertama → total 0)
    eid = await _pt("P41U6")
    with _sisip_massal(db.customers):
        await db.customers.insert_many([{"id": f"cus_pk41_u6_{i}", "name": f"Kosong {i}", "entity_id": eid,
                                         "status": "active", "payment_profile": {}} for i in range(5000)])
    cus = await _pelanggan(db, eid, "Pelanggan 5001")
    so = await _pesanan(db, cus, 7 * JT, status="shipped")
    await _kirim(db, so, 7 * JT, "2026-11-01")
    t = (await _get(klien, await adm(eid), "/api/ar/aging", entity_id=eid))["totals"]
    assert (t["total"], t["customers"]) == (7 * JT, 1)


# ═══ U7, U8, U9 — arus kas per jenis transaksi ══════════════════════════════════════════════════════════════════════
async def test_PK41_U7_arus_kas_per_jenis_transaksi(klien, adm):
    # Kas sebelum periode 1.000 − 100 = 900. Oktober: jual tunai +300, sewa −50 → operasi 250; pelepasan aset kas 130 →
    # investasi 130 (laba 50 tidak ke operasi); pinjaman antar-PT diterima 500 → pendanaan 500; saldo awal rekening 200 →
    # kas awal (bukan arus periode): kas awal disesuaikan 900 + 200 = 1.100; perubahan 250 + 130 + 500 = 880;
    # kas akhir 1.100 + 880 = 1.980 = buku besar (900 + 300 − 50 + 130 + 500 + 200). (kode lama: 793,33 · 86,67 · 200)
    eid = await _pt("P41U7")
    for tgl, baris, st in [
        ("2026-09-30", [("1-1100", 1000, 0), ("3-1000", 0, 1000)], "manual"),
        ("2026-09-30", [("1-2100", 100, 0), ("1-1100", 0, 100)], "fixed_asset_acquisition"),
        ("2026-09-30", [("6-6000", 20, 0), ("1-2900", 0, 20)], "depreciation"),
        ("2026-10-05", [("1-1100", 300, 0), ("4-1000", 0, 300)], "sales_order"),
        ("2026-10-06", [("6-2000", 50, 0), ("1-1100", 0, 50)], "cash_transaction"),
        ("2026-10-10", [("1-1100", 130, 0), ("1-2900", 20, 0), ("1-2100", 0, 100), ("4-9100", 0, 50)],
         "fixed_asset_disposal"),
        ("2026-10-12", [("1-1100", 500, 0), ("2-1250", 0, 500)], "interco_loan"),
        ("2026-10-15", [("1-1100", 200, 0), ("3-2900", 0, 200)], "bank_opening_balance"),
    ]:
        await _je(eid, tgl, baris, st)
    j = await _get(klien, await adm(eid), "/api/finance/cash-flow", start="2026-10-01", end="2026-10-31", entity_id=eid)
    assert (j["operating"]["total"], j["investing"]["total"], j["financing"]["total"]) == (250, 130, 500)
    assert (j["opening_balance_additions"], j["begin_cash"], j["begin_cash_adjusted"]) == (200, 900, 1100)
    assert (j["net_change"], j["end_cash"], j["end_cash_actual"], j["reconciled"]) == (880, 1980, 1980, True)
    assert j["method"] == "direct_by_source"
    assert [(ln["code"], ln["amount"]) for ln in j["investing"]["lines"]] == [("1-2100", 130)]


async def test_PK41_U8_saldo_awal_bukan_pendanaan(klien, adm):
    eid = await _pt("P41U8")
    await _je(eid, "2026-10-15", [("1-1100", 500, 0), ("3-2900", 0, 500)], "bank_opening_balance")
    j = await _get(klien, await adm(eid), "/api/finance/cash-flow", start="2026-10-01", end="2026-10-31", entity_id=eid)
    assert (j["financing"]["total"], j["opening_balance_additions"], j["net_change"], j["end_cash"]) == (0, 500, 0, 500)
    assert j["reconciled"] is True


async def test_PK41_U9_akun_kas_dari_pemetaan(klien, adm, db):
    # `kas_bank.kas_besar` PT ini → 1-1101; jual tunai Dr 1-1101 300 / Cr 4-1000 300 → operasi 300; kas akhir memuat 1-1101.
    from services import gl_mapping_service as glm
    eid = await _pt("P41U9")
    if not await db.gl_accounts.find_one({"code": "1-1101"}):
        await db.gl_accounts.insert_one({
            "id": _id("gla"), "code": "1-1101", "name": "Bank Uji PK-41", "type": "asset", "normal_balance": "debit",
            "parent_code": "1-1000", "is_postable": True, "is_active": True, "entity_id": None, "created_at": now_iso()})
    await glm.set_mapping("kas_bank.kas_besar", eid, "1-1101", "uji PK-41 akun bank PT", AKTOR_UJI)
    await _je(eid, "2026-10-05", [("1-1101", 300, 0), ("4-1000", 0, 300)], "sales_order")
    j = await _get(klien, await adm(eid), "/api/finance/cash-flow", start="2026-10-01", end="2026-10-31", entity_id=eid)
    assert (j["operating"]["total"], j["end_cash"], j["end_cash_actual"]) == (300, 300, 300)
    assert "1-1101" in j["cash_accounts"]


# ═══ U10 — umur hutang: belum jatuh tempo + pencocokan ke saldo akun hutang ═════════════════════════════════════════
async def test_PK41_U10_hutang_belum_jatuh_tempo_dan_pencocokan(klien, adm, db):
    # Tagihan 100 jatuh tempo 20 hari lagi → "Belum jatuh tempo" 100, 1–30 = 0 (kode lama: "0-30" 100).
    # Akun hutang: Cr 100 (tagihan) + Cr 10 (biaya masuk diterapkan, belum dibayar) − Dr 20 (retur beli disetujui) = 90.
    # Pencocokan: 100 + 10 − 20 = 90 = saldo akun 90 → tidak terjelaskan 0.
    from services.book_date import tanggal_buku
    eid = await _pt("P41U10")
    jt = (datetime.date.fromisoformat(tanggal_buku()) + datetime.timedelta(days=20)).isoformat()
    await db.vendor_bills.insert_one({
        "id": "vb_pk41_u10", "bill_number": "VB-U10", "entity_id": eid, "status": "posted", "payment_status": "unpaid",
        "grand_total": 100 * RB, "amount_paid": 0.0, "supplier_id": "sup_pk41_u10", "supplier_name": "Pemasok U10",
        "bill_date": tanggal_buku(), "due_date": jt, "created_at": now_iso()})
    await _je(eid, tanggal_buku(), [("2-1150", 100 * RB, 0), ("2-1100", 0, 100 * RB)], "vendor_bill", "vb_pk41_u10")
    await db.purchase_returns.insert_one({
        "id": "pr_pk41_u10", "number": "PR-U10", "debit_note_number": "DN-U10", "entity_id": eid, "status": "approved",
        "supplier_outcome": "ap_credit", "ap_basis": "hutang", "supplier_id": "sup_pk41_u10", "total_amount": 20 * RB,
        "grand_total": 20 * RB, "gl_status": "posted", "created_at": now_iso()})
    await _je(eid, tanggal_buku(), [("2-1100", 20 * RB, 0), ("1-1300", 0, 20 * RB)], "purchase_return", "pr_pk41_u10")
    await db.landed_cost_vouchers.insert_one({
        "id": "lcv_pk41_u10", "voucher_number": "LC-U10", "entity_id": eid, "status": "applied", "total_cost": 10 * RB,
        "amount_paid": 0.0, "provider_name": "Ekspedisi U10", "created_at": now_iso()})
    await _je(eid, tanggal_buku(), [("1-1300", 10 * RB, 0), ("2-1100", 0, 10 * RB)], "landed_cost", "lcv_pk41_u10")
    j = await _get(klien, await adm(eid), "/api/vendor-bills/payables/summary", entity_id=eid)
    assert (j["aging"]["not_due"], j["aging"]["1-30"], j["total_outstanding"]) == (100 * RB, 0, 100 * RB)
    (b,) = j["bills"]
    assert (b["days_past_due"], b["aging_bucket"], b["aging_label"], b["due_basis"]) == (
        -20, "not_due", "Belum jatuh tempo", "due_date")
    assert j["reconciliation"] == {"bills_outstanding": 100 * RB, "landed_cost_outstanding": 10 * RB,
                                   "debit_notes_open": 20 * RB, "expected_gl": 90 * RB, "gl_balance": 90 * RB,
                                   "unexplained": 0}


async def test_PK41_U10b_buat_tagihan_isi_jatuh_tempo_dari_termin(klien, adm, db):
    # Tagihan tanpa jatuh tempo → tanggal tagihan 2026-11-02 + termin pemasok NET14 (14 hari) = 2026-11-16 (tidak ditolak).
    eid = await _pt("P41U10B")
    await db.payment_terms.insert_one({"id": _id("pt"), "code": "N14PK41", "name": "Net 14", "type": "credit",
                                       "net_days": 14, "is_active": True, "entity_id": None})
    await db.suppliers.insert_one({"id": "sup_pk41_u10b", "name": "Pemasok U10b", "payment_term_code": "N14PK41",
                                   "entity_id": eid, "status": "active"})
    from routers.vendor_bills import _due_from_supplier_term
    assert await _due_from_supplier_term({"supplier_id": "sup_pk41_u10b"}, "2026-11-02T03:00:00+00:00", eid) == \
        "2026-11-16"
    from services import report_basis as rb
    # ringkasan hutang memakai aturan yang sama untuk tagihan lama tanpa jatuh tempo (dasar `bill_date`)
    assert await rb.jatuh_tempo_tagihan({"bill_date": "2026-11-02", "supplier_id": "sup_pk41_u10b",
                                         "entity_id": eid}, {}) == ("2026-11-16", "bill_date")


# ═══ U11 — profitabilitas dikurangi nota kredit; pencocokan ke Laba-Rugi ════════════════════════════════════════════
async def test_PK41_U11_profitabilitas_nota_kredit(klien, adm, db):
    # Surat jalan: pendapatan 100, biaya roll 60. Nota kredit retur: neto 20, HPP kembali 12. Hapus buku 5-9500 12.
    # Layar: pendapatan 100 − 20 = 80; HPP 60 − 12 = 48; marjin 32; marjin % 32/80 = 40,0.
    # Laba-Rugi: pendapatan 80; beban pokok 5-1000 (60 − 12) + 5-9500 12 = 60 → laba kotor 20 = 32 − 12 + 0 + 0.
    eid = await _pt("P41U11")
    cus = await _pelanggan(db, eid)
    item = {"product_id": "prd_pk41", "product_name": "Kain PK41", "category": "Katun", "quantity": 10,
            "base_quantity": 10, "base_unit": "meter", "line_total": 100 * RB, "subtotal": 100 * RB}
    so = await _pesanan(db, cus, 100 * RB, status="shipped", items=[item])
    sj = {"id": _id("sj"), "shipment_no": "SJ-U11", "order_id": so["id"], "product_id": "prd_pk41", "qty": 10,
          "status": "dispatched", "created_at": "2026-10-05T03:00:00+00:00",
          "rolls": [{"roll_id": "roll_pk41", "length": 10, "unit_cost": 6 * RB, "extended_cost": 60 * RB}]}
    await db.shipments.insert_one(dict(sj))
    ref = {"order_id": so["id"], "order_number": so["number"]}
    await _je(eid, "2026-10-05", [("1-1200", 100 * RB, 0), ("4-1000", 0, 100 * RB)], "shipment_revenue", sj["id"], ref=ref)
    await _je(eid, "2026-10-05", [("5-1000", 60 * RB, 0), ("1-1300", 0, 60 * RB)], "shipment_cogs", sj["id"], ref=ref)
    await db.credit_notes.insert_one({
        "id": "cn_pk41_u11", "number": "CN-U11", "order_id": so["id"], "order_number": so["number"],
        "customer_id": cus["id"], "customer_name": cus["name"], "entity_id": eid, "status": "posted",
        "lines": [{"product_id": "prd_pk41", "product_name": "Kain PK41", "quantity": 2, "unit": "meter",
                   "unit_price": 10 * RB, "line_total": 20 * RB}],
        "net_amount": 20 * RB, "ppn_amount": 0.0, "gross_amount": 20 * RB, "cogs_amount": 12 * RB,
        "settlement": "ar", "created_at": "2026-10-20T03:00:00+00:00"})
    await _je(eid, "2026-10-20", [("4-1000", 20 * RB, 0), ("1-1200", 0, 20 * RB),
                                  ("1-1300", 12 * RB, 0), ("5-1000", 0, 12 * RB)], "sales_return", "cn_pk41_u11")
    await _je(eid, "2026-10-25", [("5-9500", 12 * RB, 0), ("1-1300", 0, 12 * RB)], "inventory_writeoff")
    j = await _get(klien, await adm(eid), "/api/finance/profitability", start="2026-10-01", end="2026-10-31",
                   entity_id=eid)
    t = j["totals"]
    assert (t["revenue"], t["credit_notes"], t["cogs"], t["cogs_returned"], t["margin"], t["margin_pct"]) == (
        80 * RB, 20 * RB, 48 * RB, 12 * RB, 32 * RB, 40.0)
    assert [(r["label"], r["amount"]) for r in j["reconciliation"]] == [
        ("Marjin kotor layar ini", 32 * RB),
        ("Penghapusan dan penyesuaian persediaan (akun beban pokok selain HPP)", -12 * RB),
        ("Penjualan antar-PT (tidak termasuk di layar ini)", 0),
        ("Pendapatan lain di Laba-Rugi (denda, bunga, klaim — bukan penjualan barang)", 0),   # pelatihan 18 Nov
        ("Selisih belum dijelaskan", 0),
        ("Laba kotor menurut Laba-Rugi", 20 * RB)]
    # dimensi ikut dikurangi: produk, pelanggan, PT, bulan
    (p,) = j["by_product"]
    assert (p["key"], p["revenue"], p["cogs"], p["margin"], p["qty"], p["orders"]) == ("prd_pk41", 80 * RB, 48 * RB,
                                                                                        32 * RB, 8, 1)
    assert [(r["revenue"], r["margin"]) for r in j["by_customer"]] == [(80 * RB, 32 * RB)]
    assert [(r["revenue"], r["margin"]) for r in j["by_entity"]] == [(80 * RB, 32 * RB)]
    assert [(m["month"], m["revenue"], m["cogs"]) for m in j["monthly"]] == [("2026-10", 80 * RB, 48 * RB)]


async def test_PK41_U11b_pencocokan_disembunyikan_tanpa_izin_hpp(klien, akun, sesi, peran_tanpa_acuan):
    # Pencocokan memuat marjin & laba kotor → hanya pemegang izin HPP & Margin Produk (`costing.view`).
    eid = await _pt("P41U11")
    rid = await peran_tanpa_acuan({"accounting": ["view"]}, label="PK41 akuntansi tanpa HPP")
    h = await sesi(await akun(rid, entitas=(eid,)), entitas=eid)
    j = await _get(klien, h, "/api/finance/profitability", start="2026-10-01", end="2026-10-31", entity_id=eid)
    assert "reconciliation" not in j and "cogs_returned" not in j["totals"] and "margin" not in j["totals"]
    assert (j["totals"]["revenue"], j["totals"]["credit_notes"]) == (80 * RB, 20 * RB)


# ═══ U12 — Control Tower mode gabungan ═════════════════════════════════════════════════════════════════════════════
async def test_PK41_U12_tower_gabungan_saringan_pt(klien, db, akun, sesi, peran_tanpa_acuan):
    # Pengguna ditugaskan di ent_ksc + ent_kanda. Sesudah fixture: piutang terkirim ksc 40 + pesanan belum dikirim 100;
    # PT ketiga piutang 30; kas ksc 500; hutang kanda 100 → piutang tercatat +40; belum lunas +140 (tanpa 30 PT ketiga);
    # modal kerja +(500 + 40 − 100) = +440. (kode lama: piutang +170, modal kerja +570)
    rid = await peran_tanpa_acuan({"accounting": ["view"]}, label="PK41 tower dua PT")
    h = await sesi(await akun(rid, entitas=(KSC, KANDA)), entitas=KSC)
    sebelum = await _get(klien, h, "/api/finance/tower", entity_id="all")
    cus = await _pelanggan(db, KSC, "Toko Tower")
    so1 = await _pesanan(db, cus, 40 * RB, status="shipped")
    await _kirim(db, so1, 40 * RB, "2026-11-02")
    await _pesanan(db, cus, 100 * RB, status="confirmed")
    lain = await _pt("P41U12C")
    cus3 = await _pelanggan(db, lain, "Toko PT Ketiga")
    so3 = await _pesanan(db, cus3, 30 * RB, status="shipped")
    await _kirim(db, so3, 30 * RB, "2026-11-02")
    await _je(KSC, "2026-11-03", [("1-1100", 500 * RB, 0), ("3-1000", 0, 500 * RB)], "manual")
    await db.vendor_bills.insert_one({
        "id": "vb_pk41_u12", "bill_number": "VB-U12", "entity_id": KANDA, "status": "posted", "payment_status": "unpaid",
        "grand_total": 100 * RB, "amount_paid": 0.0, "supplier_id": "sup_pk41_u12", "supplier_name": "Pemasok U12",
        "bill_date": "2026-11-01", "due_date": "2026-12-01", "created_at": now_iso()})
    sesudah = await _get(klien, h, "/api/finance/tower", entity_id="all")
    beda = lambda f: round(f(sesudah) - f(sebelum), 2)   # noqa: E731
    assert beda(lambda d: d["ar"]["ar_ledger"]) == 40 * RB
    assert beda(lambda d: d["ar"]["outstanding"]) == 140 * RB
    assert beda(lambda d: d["ar"]["exposure"]) == 100 * RB
    assert beda(lambda d: d["working_capital"]) == 440 * RB
    assert sesudah["working_capital_basis"] == "Kas + piutang tercatat − hutang"
    assert [b["label"] for b in sesudah["ar"]["bucket_labels"]][0] == "Belum jatuh tempo"


# ═══ U13 — satu penghitung hari: proyeksi kas dan umur piutang berlawanan tanda ═════════════════════════════════════
async def test_PK41_U13_proyeksi_dan_umur_berlawanan_tanda(klien, adm, db, monkeypatch):
    # Surat jalan 2026-10-21 + 30 = jatuh tempo 2026-11-20; jam 2026-11-19 20.00 WIB → hari ke jatuh tempo 1,
    # hari lewat −1. (kode lama: (due − now).days dan (now − due).days dengan jam UTC → bukan 1 dan −1)
    _beku(monkeypatch, "2026-11-19", jam_wib=20)
    eid = await _pt("P41U13")
    cus = await _pelanggan(db, eid)
    so = await _pesanan(db, cus, 100 * RB, status="shipped")
    await _kirim(db, so, 100 * RB, "2026-10-21", nomor="SJ-U13")
    from services.report_basis import hari_antara
    assert hari_antara("2026-11-19", "2026-11-20") == 1
    fc = await _get(klien, await adm(eid), "/api/finance/cashflow-forecast", entity_id=eid)
    (it,) = [i for i in fc["ar_items"] if i["number"] == so["number"]]
    assert (it["due_date"], it["days_to_due"], it["due_basis"]) == ("2026-11-20", 1, "per_sj")
    d = await _get(klien, await adm(eid), f"/api/ar/aging/{cus['id']}")
    (ln,) = d["items"][0]["lines"]
    assert (ln["jatuh_tempo"], ln["hari_lewat"]) == ("2026-11-20", -1)


# ═══ U14 — judul kolom umur dari pengaturan ════════════════════════════════════════════════════════════════════════
async def test_PK41_U14_judul_kolom_dari_pengaturan(klien, adm, kepala_admin, db):
    eid = await _pt("P41U14")
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [{
        "key": "ar.aging_buckets", "value": [15, 45, 90], "scope_type": "entity", "scope_id": eid,
        "reason": "uji PK-41 kolom umur"}]})
    assert r.status_code == 200, r.text
    j = await _get(klien, await adm(eid), "/api/ar/aging", entity_id=eid)
    assert [b["label"] for b in j["bucket_labels"]] == [
        "Belum jatuh tempo", "1–15 hari", "16–45 hari", "46–90 hari", "> 90 hari"]
    lain = await _get(klien, await adm(KSC), "/api/ar/aging", entity_id=KSC)   # PT lain tidak ikut
    assert [b["label"] for b in lain["bucket_labels"]][1] == "1–30 hari"


# ═══ U16 — penjaga lampiran kueri C.6–C.8 (pemilik perbaikan: PK-16, PK-31) ═════════════════════════════════════════
async def test_PK41_U16_C6_ekuitas_sesudah_tutup_buku():
    # Laba 100 (Juli) lalu tutup buku Juli: Laba Ditahan +100, laba berjalan 0, total ekuitas = ekuitas neraca.
    from services import closing_service as cs
    from services import financial_statement_service as fs
    from services import equity_statement_service as eq
    eid = await _pt("P41C6")
    await _je(eid, "2026-07-10", [("1-1100", 100, 0), ("4-1000", 0, 100)], "manual")
    await cs.close_period("month", "2026-07", AKTOR_UJI, eid)
    bs = await fs.balance_sheet("2026-07-31", scope={"entity_id": eid})
    ld = next((x["amount"] for x in bs["equity"]["lines"] if x["code"] == "3-2000"), 0)
    assert (ld, bs["equity"]["current_earnings"]) == (100, 0)
    e = await eq.equity_statement("2026-07-01", "2026-07-31", {"entity_id": eid})
    assert e["end_total"] == bs["equity_total"] == 100


async def test_PK41_U16_C7_antar_pt_belum_terjual(db):
    # A jual ke B 100 (HPP 60), B belum menjual: eliminasi bulan itu menghapus pendapatan 100 dan HPP 60, persediaan
    # B turun 40 → konsolidasi pendapatan 0, HPP 0, persediaan −40 (mesin PK-31).
    import test_PK31_eliminasi_periode as p31
    a, b = await _pt("P41C7A"), await _pt("P41C7B")
    pid = "pk41_c7"
    if not await db.products.find_one({"id": p31.PRD}):
        await db.products.insert_one({"id": p31.PRD, "name": "Kain PK31", "sku": "PK31", "base_unit": "meter",
                                      "status": "active"})
    await _je(a, "2026-01-02", [("1-1300", 60 * JT, 0), ("3-2900", 0, 60 * JT)], "uji")
    await db.interco_transactions.insert_many(p31.pasangan(pid, a, b, 100 * JT, nomor="P41/IC-C7", tanggal="2026-06-10"))
    await p31.jurnal_jual(pid, a, b, 100 * JT, "2026-06-10")
    await p31.jurnal_barang(pid, a, b, 100 * JT, 60 * JT, "2026-06-12")
    await p31.tugas_gudang(db, "trn_pk41_c7", pid, a, b, [("roll_pk41_c7", 1000.0)], "2026-06-12")
    await db.inventory_rolls.insert_one(p31.roll("roll_pk41_c7", b, 1000.0, 100_000,
                                                 [p31.unsur_rantai(pid, a, b, 100_000, 60_000, "2026-06-12")]))
    e = await p31.mesin().period_entry(pid, "2026-06")
    garis = p31.baris(e)
    pend = sum(d - k for c, d, k in garis if c == "4-1000")
    hpp = sum(k - d for c, d, k in garis if c == "5-1000")
    sedia = sum(d - k for c, d, k in garis if c in ("1-1300", "1-1310"))
    assert (100 * JT - pend, 60 * JT - hpp, sedia) == (0, 0, -40 * JT), garis


async def test_PK41_U16_C8_tanya_kn_tanpa_jurnal_penutup(klien, sesi):
    # Oktober 500 lalu jurnal penutup Oktober; November 200 → pendapatan diakui November = 200 (kode lama −300).
    eid = await _pt("P41C8")
    h = await sesi(ADMIN, entitas=eid)

    async def diakui(dari, sampai):
        r = await klien.post("/api/ai/query", headers=h, json={
            "metrics": ["recognized_revenue"], "group_by": [], "time_grain": None,
            "period": {"preset": "custom", "from": dari, "to": sampai}, "compare": "none", "filters": [],
            "sort": {"by": None, "direction": "desc"}, "limit": None, "include_samples": False,
            "entity_scope": "active"})
        assert r.status_code == 200, r.text
        return float(r.json()["totals"].get("recognized_revenue") or 0)

    awal = await diakui("2026-11-01", "2026-11-30")
    await _je(eid, "2026-10-10", [("1-1100", 500, 0), ("4-1000", 0, 500)], "manual")
    await _je(eid, "2026-10-31T23:59:59", [("4-1000", 500, 0), ("3-2000", 0, 500)], "closing")
    await _je(eid, "2026-11-05", [("1-1100", 200, 0), ("4-1000", 0, 200)], "manual")
    assert await diakui("2026-11-01", "2026-11-30") - awal == 200


# ═══ Invarian baca-saja INV-AR-03 (langkah kerja 8) ═════════════════════════════════════════════════════════════════
async def test_PK41_invarian_piutang_tercatat_vs_akun(db, data_u1, capsys):
    # U1: tercatat 40 = akun 40 → tidak dilaporkan. PT P41INV: jurnal manual Dr 1-1200 25 (tanpa surat jalan) → akun 25,
    # tercatat 0 → selisih (akun − tercatat) 25 − 0 = 25 DILAPORKAN (WARN), tidak menggagalkan.
    import importlib
    import re
    import sys
    from pathlib import Path
    eid = await _pt("P41INV")
    await _je(eid, "2026-11-02", [("1-1200", 25 * RB, 0), ("4-1000", 0, 25 * RB)], "manual")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    vdi = importlib.import_module("verify_data_integrity")
    await vdi.layer_gl_invariants(db)
    keluar = re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().out)
    (baris,) = [x for x in keluar.splitlines() if "INV-AR-03" in x]
    assert "[WARN]" in baris and "ent_uji_p41inv(tercatat 0 · akun 25,000 · Δ25,000)" in baris, baris
    assert "ent_uji_p41u1(" not in baris


# ═══ Skrip baca-saja daftar status kredit yang berubah (RISIKO spesifikasi) ═════════════════════════════════════════
async def test_PK41_skrip_status_kredit_berubah(db, capsys):
    # Pesanan 100: SJ-1 40 (60 hari lalu), SJ-2 60 (10 hari lalu), termin 30, bayar 40. Rumus lama: seluruh sisa 60
    # jatuh tempo SJ pertama + 30 = 30 hari lalu → telat 30 > 14 → diblokir. Rumus baru: bayar 40 melunasi SJ-1; SJ-2
    # jatuh tempo 20 hari lagi → tidak telat → aktif (plafon 0 = tanpa plafon).
    import importlib
    import re
    import sys
    from pathlib import Path
    from services.book_date import tanggal_buku
    eid = await _pt("P41SKR")
    cus = await _pelanggan(db, eid, "Toko Berubah")
    hari = datetime.date.fromisoformat(tanggal_buku())
    so = await _pesanan(db, cus, 100 * RB, payments=[_bayar(40 * RB, (hari - datetime.timedelta(days=5)).isoformat())],
                        payment_status="partial", status="shipped")
    await _kirim(db, so, 40 * RB, (hari - datetime.timedelta(days=60)).isoformat())
    await _kirim(db, so, 60 * RB, (hari - datetime.timedelta(days=10)).isoformat())
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    skrip = importlib.import_module("pk41_status_kredit_berubah")
    assert await skrip.main() == 0
    keluar = capsys.readouterr().out
    # rumus lama membulatkan jam UTC ke bawah (RP-11): telat lama 29 atau 30 hari tergantung jam uji
    assert re.search(r"Toko Berubah \[ent_uji_p41skr\]: blocked → active · lewat tempo 60,000 → 0 · telat (29|30) → 0 hari",
                     keluar), keluar
    assert await db.journal_entries.count_documents({"entity_id": eid}) == 2   # baca-saja: tidak ada tulisan baru


# ═══ Bersama PK-32 (nota kredit/debit amandemen) — piutang tidak terpotong dua kali, tagihan tambahan tidak hilang ═══
async def test_PK41_PK32_nota_tertangguh_tidak_dipotong_dua_kali(klien, adm, db):
    pytest.importorskip("services.credit_note_service")   # berlaku sesudah PK-32 (mesin nota, nilai tagihan)
    # Contoh PK-32 U5: pesanan 1.000.000; SJ-1 400.000 (40 m); koreksi harga → 800.000: dibalik 80.000 (jurnal Dr 4-1000 /
    # Cr 1-1200, baris `nota_koreksi`) + tertangguh 120.000 (baris `nota_tangguh`, tanpa jurnal).
    # Piutang tercatat = 400.000 − 80.000 = 320.000 = saldo 1-1200; belum dikirim = 1.000.000 − 400.000 − 0 − 120.000
    # = 480.000 (60 m × 8.000). Lalu SJ-2 dijurnal 480.000 (nilai efektif) → tercatat 880.000 − 80.000 = 800.000 = saldo
    # 1-1200; belum dikirim 1.000.000 − 880.000 − 120.000 = 0. (Bila nota tertangguh ikut dialokasikan ke surat jalan:
    # tercatat 200.000 lalu 680.000 — piutang terpotong dua kali.)
    eid = await _pt("P41N32")
    cus = await _pelanggan(db, eid)
    so = await _pesanan(db, cus, 1_000_000, status="partially_shipped", payments=[
        {"id": _id("pay"), "kind": "nota_kredit", "amount": 80_000, "method": "credit_note", "receipt_id": "cn_pk41",
         "gl_bucket": "nota_koreksi", "date": "2026-10-10", "created_at": "2026-10-10"},
        {"id": _id("pay"), "kind": "nota_kredit", "amount": 120_000, "method": "credit_note", "receipt_id": "cn_pk41",
         "gl_bucket": "nota_tangguh", "date": "2026-10-10", "created_at": "2026-10-10"}], payment_status="partial")
    await _kirim(db, so, 400_000, "2026-10-01", nomor="SJ-N32-1")
    await _je(eid, "2026-10-10", [("4-1000", 80_000, 0), ("1-1200", 0, 80_000)], "amendment_credit_note", "cn_pk41",
              ref={"order_id": so["id"], "order_number": so["number"]})
    j = await _get(klien, await adm(eid), "/api/ar/aging", entity_id=eid, as_of="2026-10-20")
    t, rec = j["totals"], j["reconciliation"]
    assert (t["ar_ledger"], t["exposure"], t["total"]) == (320_000, 480_000, 800_000), t
    assert (rec["ar_ledger_total"], rec["gl_balance"], rec["difference"]) == (320_000, 320_000, 0), rec
    await _kirim(db, so, 480_000, "2026-10-25", nomor="SJ-N32-2")
    j = await _get(klien, await adm(eid), "/api/ar/aging", entity_id=eid, as_of="2026-10-31")
    t, rec = j["totals"], j["reconciliation"]
    assert (t["ar_ledger"], t["exposure"], t["total"]) == (800_000, 0, 800_000), t
    assert (rec["gl_balance"], rec["difference"]) == (800_000, 0), rec


async def test_PK41_PK32_nota_debit_jadi_baris_tagihan(klien, adm, db):
    pytest.importorskip("services.credit_note_service")   # berlaku sesudah PK-32 (mesin nota, nilai tagihan)
    # Contoh PK-32 U6: terkirim penuh 1.000.000 (1 Okt); nota debit 100.000 (10 Okt) → `extra_billing_lines` gross
    # 100.000 + jurnal `amendment_debit_note` Dr 1-1200 100.000. Baris tagihan: SJ 1.000.000 (jatuh tempo 31 Okt) + nota
    # debit 100.000 (jatuh tempo 10 Okt + 30 = 9 Nov); belum dikirim 1.100.000 − 1.100.000 = 0; tercatat 1.100.000 =
    # saldo 1-1200.
    eid = await _pt("P41D32")
    cus = await _pelanggan(db, eid)
    so = await _pesanan(db, cus, 1_000_000, status="shipped")
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"extra_billing_lines": [
        {"id": _id("xbl"), "debit_note_id": "dn_pk41", "debit_note_number": "DN-PK41", "net": 100_000, "ppn": 0,
         "gross": 100_000, "due_date": "2026-11-09", "created_at": "2026-10-10T03:00:00+00:00"}]}})
    await _kirim(db, so, 1_000_000, "2026-10-01", nomor="SJ-D32")
    await _je(eid, "2026-10-10", [("1-1200", 100_000, 0), ("4-1000", 0, 100_000)], "amendment_debit_note", "dn_pk41",
              ref={"order_id": so["id"], "order_number": so["number"]}, label="DN-PK41")
    j = await _get(klien, await adm(eid), "/api/ar/aging", entity_id=eid, as_of="2026-11-15")
    t, rec = j["totals"], j["reconciliation"]
    assert (t["ar_ledger"], t["exposure"], t["total"]) == (1_100_000, 0, 1_100_000), t
    assert (rec["gl_balance"], rec["difference"]) == (1_100_000, 0), rec
    d = await _get(klien, await adm(eid), f"/api/ar/aging/{cus['id']}", as_of="2026-11-15")
    (it,) = d["items"]
    assert [(ln["sumber"], ln["ref_number"], ln["jatuh_tempo"], ln["sisa"], ln["hari_lewat"]) for ln in it["lines"]] == [
        ("surat_jalan", "SJ-D32", "2026-10-31", 1_000_000, 15), ("nota_debit", "DN-PK41", "2026-11-09", 100_000, 6)]
    assert it["grand_total"] == 1_100_000
