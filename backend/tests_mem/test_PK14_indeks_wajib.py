"""PK-14 — indeks unik keuangan wajib (docs/blueprint/unit/PK-14.md), lapis B: U12 (fungsi pembanding), U13 (mode),
U14 (pemetaan `DuplicateKeyError` di empat titik sisip).

Keunikan sungguhan (U1–U11) hanya sah di MongoDB asli: `backend/tests/test_bp_PK14_indeks_wajib.py`.
"""
from __future__ import annotations

import copy
import datetime
from contextlib import contextmanager

import mongomock.collection as _mc
import pytest
from pymongo.errors import DuplicateKeyError

import indexes
from services import finance_case_service as fcs
from services import gl_service as gl
from services import payment_plan_service as pps
from services import penalty_service as pens

pytestmark = pytest.mark.anyio
E1 = "ent_ksc"
SEKARANG = datetime.datetime.now(datetime.timezone.utc).isoformat()
# PK-40 (SL-13): `uq_fkt_active`, `uq_fkt_nsfp`, `uq_fpm_active`, `uq_fpm_nsfp`, `uq_tax_period` masuk daftar wajib.
PK40_INDEKS = 5
# PM-T1: `bank_accounts.uq_default_receiving` (satu rekening bawaan per PT per cara bayar).
PMT1_INDEKS = 1
# CR-T1: `customer_credit_profiles.uq_customer_entity` (satu profil per pelanggan per PT) dan
# `credit_profile_requests.uq_open_request` (satu pengajuan terbuka per pelanggan per PT).
CRT1_INDEKS = 2
# PK-31 (IC-03): `intercompany_eliminations.uq_pair_period` (satu eliminasi otomatis per pasangan per bulan).
PK31_INDEKS = 1
# PM-T2: `payment_codes.uq_pay_code` (kode bayar unik lintas PT) + `uq_pay_code_line` (satu kode per pesanan per baris).
PMT2_INDEKS = 2
# PK-39 (FY-12) — `budgets.uq_budget_key` (satu pagu per PT, tahun, bulan, dimensi, kunci).
PK39_INDEKS = 1
# AG-T3 (D7) — `ai_action_proposals.uq_pending_session` (satu kartu tindakan asisten menunggu per percakapan).
AGT3_INDEKS = 1
# KM-T1 — `sales_targets.uq_target_pt_sales_periode` (satu target per PT, sales, jenis periode, periode),
# `incentive_components.uq_component_code` (kode komponen per PT), `incentive_definitions.uq_definition_version`.
KMT1_INDEKS = 3


def _info_lengkap() -> dict:
    out: dict = {}
    for it in indexes.REQUIRED_UNIQUE_INDEXES:
        out.setdefault(it["collection"], {})[it["name"]] = {
            "key": [(k, 1.0) for k, _ in it["keys"]], "unique": True,
            "partialFilterExpression": copy.deepcopy(it["partial"])}
    return out


def test_U12_pembanding_indeks():
    info = _info_lengkap()
    assert indexes.diff_required(info) == []
    b = _info_lengkap()
    del b["finance_cases"]["uq_case_open_source"]
    d = indexes.diff_required(b)
    assert [(x["name"], x["problem"]) for x in d] == [("uq_case_open_source", "tidak ada")] and d[0]["finder"]
    c = _info_lengkap()
    c["journal_entries"]["uq_je_source_active"]["unique"] = False
    d = indexes.diff_required(c)
    assert [(x["name"], x["problem"]) for x in d] == [("uq_je_source_active", "tidak unik")] and d[0]["finder"]
    e = _info_lengkap()
    e["payment_plans"]["uq_plan_active_doc"]["partialFilterExpression"] = {"status": "open"}
    d = indexes.diff_required(e)
    assert [(x["name"], x["problem"]) for x in d] == [("uq_plan_active_doc", "ekspresi parsial berbeda")]
    assert "payment_plans" in d[0]["finder"]
    f = _info_lengkap()
    f["penalties"]["uq_penalty_line_period"]["key"] = [("doc_id", 1), ("period_key", 1)]
    assert [x["problem"] for x in indexes.diff_required(f)] == ["kunci berbeda"]
    # KP-T5 — + `doc_number_formats.uq_kind_entity` (satu format nomor per jenis per PT/grup): 8 → 9.
    # PK-40 menambah 5 indeks wajib (faktur keluaran/masukan aktif & NSFP, kunci masa pajak): 9 + 5.
    # KP-T6 — + `pdf_templates.uq_doctype_entity` (satu lapisan template cetak per jenis per PT/grup): + 1.
    # PM-T1 — + `bank_accounts.uq_default_receiving` (satu rekening penerima bawaan per cara bayar per PT): + PMT1_INDEKS.
    # PK-31 — + `intercompany_eliminations.uq_pair_period` (satu eliminasi otomatis per pasangan per bulan): + PK31_INDEKS.
    # PM-T2 — + `payment_codes.uq_pay_code`, `uq_pay_code_line` (kode bayar unik lintas PT; satu per tagihan): + PMT2_INDEKS.
    # PK-39 — + `budgets.uq_budget_key` (satu pagu per PT, tahun, bulan, dimensi, kunci): + PK39_INDEKS.
    # AG-T3 — + `ai_action_proposals.uq_pending_session` (satu kartu asisten menunggu per percakapan): + AGT3_INDEKS.
    # KM-T1 — + target per PT, kode komponen per PT, versi definisi per PT: + KMT1_INDEKS.
    assert len(indexes.REQUIRED_UNIQUE_INDEXES) == (9 + PK40_INDEKS + 1 + PMT1_INDEKS + CRT1_INDEKS + PK31_INDEKS
                                                    + PMT2_INDEKS + PK39_INDEKS + AGT3_INDEKS + KMT1_INDEKS)


async def test_U13_mode_enforce_dan_warn(aplikasi, monkeypatch):
    satu = [{"collection": "penalties", "name": "uq_penalty_line_period", "label": "nota denda per baris per periode",
             "problem": "tidak ada", "finder": "db.penalties.aggregate([...])"}]

    async def _diffs():
        return [dict(x) for x in satu]
    monkeypatch.setattr(indexes, "required_index_diffs", _diffs)
    monkeypatch.setenv("KN_REQUIRED_INDEX_MODE", "enforce")
    with pytest.raises(indexes.RequiredIndexError) as ei:
        await indexes.assert_required_indexes()
    pesan = str(ei.value)
    assert "INDEKS WAJIB BELUM TERPASANG" in pesan and "penalties.uq_penalty_line_period" in pesan
    assert "db.penalties.aggregate" in pesan
    monkeypatch.delenv("KN_REQUIRED_INDEX_MODE")   # bawaan = enforce
    with pytest.raises(indexes.RequiredIndexError):
        await indexes.assert_required_indexes()
    monkeypatch.setenv("KN_REQUIRED_INDEX_MODE", "warn")
    await indexes.assert_required_indexes()   # tidak melempar


@contextmanager
def _kembar(koleksi: str, key_pattern: dict):
    """Sisipan ke `koleksi` dipaksa melempar DuplicateKeyError ber-keyPattern tertentu (sekali)."""
    asli = _mc.Collection.insert_one
    sisa = {"n": 1}

    def _palsu(self, doc, *a, **kw):
        if self.name == koleksi and sisa["n"]:
            sisa["n"] -= 1
            raise DuplicateKeyError("E11000 duplicate key (uji)", 11000,
                                    {"keyPattern": dict(key_pattern), "keyValue": {}})
        return asli(self, doc, *a, **kw)
    _mc.Collection.insert_one = _palsu
    try:
        yield
    finally:
        _mc.Collection.insert_one = asli


async def test_U14a_rencana_kembar_jadi_pesan(aplikasi, db):
    await db.sales_orders.insert_one({"id": "so_pk14", "number": "SO-PK14", "entity_id": E1, "customer_id": "cus_pk14",
                                      "customer_name": "Toko PK14", "grand_total": 1_000_000, "status": "confirmed",
                                      "created_at": SEKARANG})
    with _kembar("payment_plans", {"doc_type": 1, "doc_id": 1}):
        with pytest.raises(pps.PlanError, match="Dokumen ini sudah punya rencana pembayaran aktif. Muat ulang lalu ubah"):
            await pps.create_plan("sales_order", "so_pk14", {"mode": "net", "net_days": 30}, {"name": "uji"})


async def test_U14b_kasus_kembar_jadi_pesan(aplikasi):
    with _kembar("finance_cases", {"case_type": 1, "source.id": 1}):
        with pytest.raises(fcs.CaseError, match="Sumber ini sudah punya kasus yang belum selesai. Buka kasus itu"):
            await fcs.create_case({"case_type": "selisih_biaya_bank", "entity_id": E1, "amount": 1000,
                                   "source": {"kind": "ar_receipt", "id": "rcp_pk14"}}, {"name": "uji"}, None, E1)


async def test_U14c_nota_denda_kembar_kembalikan_yang_ada(aplikasi, db):
    ada = {"id": "pnl_pk14_ada", "number": "DN-DENDA-PK14", "entity_id": E1, "doc_type": "sales_order",
           "doc_id": "so_pk14", "plan_id": "pyp_pk14", "line_seq": 2, "period_key": "2026-10-01|2026-11",
           "status": "draft", "amount": 5000.0}
    await db.penalties.insert_one(dict(ada))
    plan = {"id": "pyp_pk14", "number": "RPB-PK14", "entity_id": E1, "doc_type": "sales_order", "doc_id": "so_pk14"}
    calc = {"amount": 5000.0, "days_late": 10, "billable_days": 10, "rate_pct_per_month": 2.0, "grace_days": 0,
            "cap_pct": 0, "explain": []}
    with _kembar("penalties", {"doc_id": 1, "plan_id": 1, "line_seq": 1, "period_key": 1}):
        hasil = await pens._create(plan, {"seq": 2, "label": "Cicilan 2", "due_date": "2026-10-01"}, calc,
                                   250_000, "2026-10-01|2026-11", {"base": "installment"}, "uji")
    assert hasil["id"] == "pnl_pk14_ada"
    assert await db.penalties.count_documents({"doc_id": "so_pk14", "line_seq": 2}) == 1


async def test_U14d_jurnal_kembar_kembalikan_yang_ada(aplikasi, db):
    garis = [{"account_code": "1-1100", "account_name": "Kas", "debit": 1000, "credit": 0},
             {"account_code": "4-9000", "account_name": "Lain", "debit": 0, "credit": 1000}]
    pertama = await gl._insert_entry(lines=garis, description="uji PK-14", date="2026-11-02T10:00:00",
                                     source_type="uji_pk14", source_id="src_pk14", entity_id=E1, created_by="uji")
    with _kembar("journal_entries", {"source_type": 1, "source_id": 1}):
        kedua = await gl._insert_entry(lines=garis, description="uji PK-14 ulang", date="2026-11-02T10:00:00",
                                       source_type="uji_pk14", source_id="src_pk14", entity_id=E1, created_by="uji")
    assert kedua["id"] == pertama["id"]
    with _kembar("journal_entries", {"number": 1}):   # duplikat nomor tetap dilempar
        with pytest.raises(DuplicateKeyError):
            await gl._insert_entry(lines=garis, description="uji PK-14 nomor", date="2026-11-02T10:00:00",
                                   source_type="uji_pk14", source_id="src_pk14_b", entity_id=E1, created_by="uji")
