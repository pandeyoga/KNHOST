"""PK-12 — kunci idempotensi di semua jalur uang (docs/blueprint/unit/PK-12.md), sisi server U1–U10.

Admin, `X-Entity-Id: ent_ksc`. "Kirim dua kali" = dua permintaan identik berurutan dengan `Idempotency-Key` sama.
"""
from __future__ import annotations

import datetime
import itertools

import pytest

from idempotency import IDEMPOTENT_PREFIXES
from services import gl_service as gl

pytestmark = pytest.mark.anyio
E1 = "ent_ksc"
HARI_INI = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
_n = itertools.count(1)


def _k(h, key):
    return {**h, "Idempotency-Key": key}


def _jurnal(nominal=250_000, kredit=None):
    return {"date": HARI_INI, "description": "uji PK-12", "lines": [
        {"account_code": "1-1100", "debit": nominal, "credit": 0},
        {"account_code": "4-9000", "debit": 0, "credit": nominal if kredit is None else kredit}]}


async def _dua_kali(klien, url, h, key, body=None):
    r1 = await klien.post(url, headers=_k(h, key), json=body)
    r2 = await klien.post(url, headers=_k(h, key), json=body)
    return r1, r2


async def _saldo(db, akun="1-1100") -> float:
    d = k = 0.0
    async for je in db.journal_entries.find({"entity_id": E1, "status": {"$ne": "void"}}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") == akun:
                d += float(ln.get("debit") or 0)
                k += float(ln.get("credit") or 0)
    return round(d - k, 2)


@pytest.fixture(scope="module")
async def rek(db):
    await db.bank_accounts.insert_many([
        {"id": f"ba_pk12_{i}", "name": f"Kas PK12 {i}", "account_type": "cash", "cash_type": "kas_besar",
         "entity_id": E1, "is_active": True, "status": "active", "opening_balance": 0} for i in (1, 2)])
    return "ba_pk12_1"


async def test_U01_jurnal_dua_kali_satu_dokumen(klien, db, kepala_admin):
    n = await db.journal_entries.count_documents({"entity_id": E1})
    r1, r2 = await _dua_kali(klien, "/api/gl/journal", kepala_admin, "k-je-1", _jurnal())
    assert r1.status_code == 200 and r2.status_code == 200, (r1.text, r2.text)
    assert r1.json()["id"] == r2.json()["id"] and r1.json()["number"] == r2.json()["number"]
    assert r2.headers.get("X-Idempotent-Replay") == "true"
    assert await db.journal_entries.count_documents({"entity_id": E1}) == n + 1


async def test_U02_kas_dua_kali_satu_mutasi(klien, db, kepala_admin, rek):
    r = await klien.post("/api/cash-transactions", headers=kepala_admin, json={
        "cash_type": "kas_besar", "direction": "in", "amount": 1_000_000, "category": "lain-lain",
        "description": "modal uji PK-12", "account_id": rek})
    assert r.status_code == 200, r.text
    n = await db.cash_transactions.count_documents({})
    nj = await db.journal_entries.count_documents({"source_type": "cash_transaction"})
    s0 = await _saldo(db)
    r1, r2 = await _dua_kali(klien, "/api/cash-transactions", kepala_admin, "k-kas-1", {
        "cash_type": "kas_besar", "direction": "out", "amount": 75_000, "category": "lain-lain",
        "description": "uji PK-12 kas keluar", "account_id": rek})
    assert r1.status_code == 200 and r2.status_code == 200, (r1.text, r2.text)
    assert r1.json()["id"] == r2.json()["id"]
    assert await db.cash_transactions.count_documents({}) == n + 1
    assert await db.journal_entries.count_documents({"source_type": "cash_transaction"}) == nj + 1
    assert await _saldo(db) == s0 - 75_000


async def test_U03_reklas_suspense_dua_kali(klien, db, kepala_admin):
    await klien.post("/api/gl/journal", headers=kepala_admin, json={
        "date": HARI_INI, "description": "uji PK-12 isi suspense",
        "lines": [{"account_code": "1-9999", "debit": 40_000, "credit": 0},
                  {"account_code": "4-9000", "debit": 0, "credit": 40_000}]})
    n = await db.journal_entries.count_documents({"source_type": "suspense_reclass"})
    r1, r2 = await _dua_kali(klien, "/api/gl/suspense/reclass", kepala_admin, "k-reklas-1", {
        "amount": 40_000, "side": "debit", "target_account": "6-2000", "note": "uji PK-12"})
    assert r1.status_code == 200 and r2.status_code == 200, (r1.text, r2.text)
    assert await db.journal_entries.count_documents({"source_type": "suspense_reclass"}) == n + 1


@pytest.mark.parametrize("url,koleksi,isi", [
    ("/api/cash-advances", "cash_advances", {
        "entity_id": E1, "divisi": "Gudang", "kegiatan": "uji PK-12", "payment_method": "tunai",
        "lines": [{"description": "bensin", "qty": 1, "satuan": "unit", "unit_price": 50_000}]}),
    ("/api/finance-cases", "finance_cases", {"case_type": "selisih_biaya_bank", "entity_id": E1, "amount": 1000,
                                             "title": "uji PK-12"}),
    ("/api/tax/pph-records", "tax_pph_records", {"entity_id": E1, "period": "2026-10", "code": "pph23",
                                                 "rate": 2.0, "dpp": 1_000_000}),
    ("/api/fixed-assets", "fin_fixed_assets", {"name": "Mesin uji PK-12", "acquisition_cost": 12_000_000,
                                           "acquisition_date": "2026-10-01", "useful_life_months": 48,
                                           "entity_id": E1}),
])
async def test_U04_jalur_lain_dua_kali(klien, db, kepala_admin, url, koleksi, isi):
    n = await db[koleksi].count_documents({})
    r1, r2 = await _dua_kali(klien, url, kepala_admin, f"k-u4-{koleksi}", isi)
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200 and r2.json() == r1.json(), r2.text
    assert await db[koleksi].count_documents({}) == n + 1


async def test_U05_terbitkan_denda_dua_kali_lalu_tanpa_kunci(klien, db, kepala_admin):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await db.penalties.insert_one({
        "id": "pnl_pk12", "number": "DN-DENDA-PK12", "entity_id": E1, "doc_type": "sales_order",
        "doc_id": "so_pk12", "doc_number": "SO-PK12", "plan_id": "", "line_seq": 0, "due_date": "2026-10-01",
        "period_key": "2026-10-01|2026-11", "customer_id": "cus_pk12", "customer_name": "Toko PK12",
        "base_amount": 5_000_000, "base": "installment", "amount": 100_000.0, "original_amount": 100_000.0,
        "days_late": 30, "billable_days": 30, "rate_pct_per_month": 2.0, "grace_days": 0, "cap_pct": 0,
        "status": "draft", "status_label": "Usulan", "paid_amount": 0.0, "je_id": "", "explain": [],
        "created_by": "uji", "created_at": now, "updated_at": now, "refs": []})
    r1, r2 = await _dua_kali(klien, "/api/penalties/pnl_pk12/issue", kepala_admin, "k-denda-1")
    assert r1.status_code == 200 and r2.status_code == 200, (r1.text, r2.text)
    assert r1.json() == r2.json()
    assert await db.journal_entries.count_documents({"source_type": "penalty", "source_id": "pnl_pk12"}) == 1
    r3 = await klien.post("/api/penalties/pnl_pk12/issue", headers=kepala_admin)
    assert r3.status_code == 400 and "sudah berstatus" in r3.text, r3.text


JALUR_LAYAR = [
    "/api/gl/journal", "/api/gl/journal/je_x/reverse", "/api/gl/journal/je_x/void", "/api/gl/suspense/reclass",
    "/api/cash-transactions", "/api/cash-transactions/cash_x/void",
    "/api/vendor-bills", "/api/vendor-bills/vb_x/submit", "/api/vendor-bills/vb_x/approve",
    "/api/vendor-bills/vb_x/reject", "/api/vendor-bills/vb_x/cancel", "/api/vendor-bills/vb_x/payments",
    "/api/vendor-bills/vb_x/payments/pay_x/void",
    "/api/contra-bons", "/api/contra-bons/cb_x/deductions", "/api/contra-bons/cb_x/pay",
    "/api/contra-bons/cb_x/decision", "/api/contra-bons/cb_x/schedule", "/api/contra-bons/cb_x/dispute",
    "/api/contra-bons/cb_x/cancel", "/api/contra-bons/cb_x/pay-from-bank-line",
    "/api/interco/transactions", "/api/interco/settlements", "/api/interco/returns",
    "/api/interco/transactions/ic_x/confirm", "/api/interco/transactions/ic_x/cancel", "/api/interco/loans",
    "/api/interco/loans/ln_x/repay", "/api/interco/tax-invoices/ic_x",
    "/api/fixed-assets", "/api/fixed-assets/depreciation/run", "/api/fixed-assets/fa_x/dispose",
    "/api/fixed-assets/fa_x/transfer", "/api/fixed-assets/transfers/tr_x/settle",
    "/api/cash-advances", "/api/cash-advances/ca_x/approve", "/api/cash-advances/ca_x/disburse",
    "/api/cash-advance-settlements", "/api/cash-advance-settlements/st_x/approve",
    "/api/cash-advance-settlements/st_x/pay-reimburse",
    "/api/payment-plans", "/api/payment-plans/pp_x", "/api/payment-plans/pp_x/void",
    "/api/penalties/pnl_x/issue", "/api/penalties/pnl_x/waive", "/api/penalties/pnl_x/adjust",
    "/api/penalties/pnl_x/pay",
    "/api/payment-variances/assess", "/api/payment-variances/pv_x/decide", "/api/payment-variances/pv_x/reverse",
    "/api/finance-cases", "/api/finance-cases/fc_x/resolve", "/api/finance-cases/fc_x/reject",
    "/api/tax/pph-records", "/api/tax/pph-records/pph_x",
    "/api/input-tax-invoices", "/api/input-tax-invoices/it_x/cancel",
    "/api/tax-invoices/ti_x/nsfp", "/api/tax-invoices/ti_x/replace", "/api/tax-invoices/ti_x/cancel",
    "/api/bank-reconciliation/lines/bl_x/book-fee", "/api/bank-reconciliation/lines/bl_x/hold",
    "/api/bank-reconciliation/lines/bl_x/allocate-holding", "/api/bank-reconciliation/lines/bl_x/match",
]


def test_U06_semua_jalur_layar_tercakup():
    luput = [p for p in JALUR_LAYAR if not p.startswith(IDEMPOTENT_PREFIXES)]
    assert luput == []


async def test_U07_kunci_sama_isi_beda_409(klien, db, kepala_admin):
    n = await db.journal_entries.count_documents({"entity_id": E1})
    r = await klien.post("/api/gl/journal", headers=_k(kepala_admin, "k-je-1"), json=_jurnal(300_000))
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert await db.journal_entries.count_documents({"entity_id": E1}) == n


async def test_U08_kunci_terikat_akun_dan_pt(klien, db, kepala_admin, sesi):
    manajer = await sesi("manager@kainnusantara.id")
    n = await db.journal_entries.count_documents({})
    r1 = await klien.post("/api/gl/journal", headers=_k(manajer, "k-je-1"), json=_jurnal())
    r2 = await klien.post("/api/gl/journal", headers=_k({**kepala_admin, "X-Entity-Id": "ent_kanda"}, "k-je-1"),
                          json=_jurnal())
    assert r1.status_code == 200 and r2.status_code == 200, (r1.text, r2.text)
    assert "X-Idempotent-Replay" not in r1.headers and "X-Idempotent-Replay" not in r2.headers
    assert await db.journal_entries.count_documents({}) == n + 2


async def test_U09_jawaban_5xx_tidak_disimpan(klien, db, kepala_admin, monkeypatch):
    asli = gl.create_manual_entry
    sisa = {"n": 1}

    async def _sekali_gagal(*a, **kw):
        if sisa["n"]:
            sisa["n"] -= 1
            raise RuntimeError("uji: galat tak tertangani")
        return await asli(*a, **kw)
    monkeypatch.setattr(gl, "create_manual_entry", _sekali_gagal)
    n = await db.journal_entries.count_documents({"entity_id": E1})
    body = _jurnal(123_000)
    r1 = await klien.post("/api/gl/journal", headers=_k(kepala_admin, "k-je-2"), json=body)
    assert r1.status_code == 500
    r2 = await klien.post("/api/gl/journal", headers=_k(kepala_admin, "k-je-2"), json=body)
    assert r2.status_code == 200, r2.text
    assert "X-Idempotent-Replay" not in r2.headers
    assert await db.journal_entries.count_documents({"entity_id": E1}) == n + 1


async def test_U10_jawaban_4xx_diputar_ulang(klien, db, kepala_admin):
    n = await db.journal_entries.count_documents({"entity_id": E1})
    r1, r2 = await _dua_kali(klien, "/api/gl/journal", kepala_admin, "k-je-3", _jurnal(250_000, kredit=240_000))
    assert r1.status_code == 400 and r2.status_code == 400, (r1.text, r2.text)
    assert r1.json() == r2.json()
    assert r2.headers.get("X-Idempotent-Replay") == "true"
    assert await db.journal_entries.count_documents({"entity_id": E1}) == n
