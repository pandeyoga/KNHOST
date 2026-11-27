"""PK-14 U1–U11 — indeks unik keuangan wajib di MongoDB ASLI (lingkungan A).

Prasyarat: backend versi PK-14 sudah pernah dinyalakan pada database ini (`REACT_APP_BACKEND_URL`, untuk U7–U10) dan
`MONGO_URL`/`DB_NAME` menunjuk database uji lokal. U3–U6 menyalakan backend SENDIRI di port 8011 (folder `backend/`
checkout ini) untuk melihat proses awal gagal/berhasil; backend utama tidak disentuh. Tidak untuk data nyata.
Semua data uji dihapus di akhir; indeks yang sengaja dihapus dipasang kembali oleh U5/U6.
"""
import datetime
import os
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymongo
import pytest
import requests
from pymongo.errors import DuplicateKeyError

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
from indexes import REQUIRED_UNIQUE_INDEXES, diff_required  # noqa: E402

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
PORT = 8011
TAG = uuid.uuid4().hex[:8]
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()


def _info():
    return {c: DB[c].index_information() for c in {it["collection"] for it in REQUIRED_UNIQUE_INDEXES}}


_NYALA = {"n": 0}


def _nyalakan(mode=None, batas=150):
    """Nyalakan backend checkout ini di PORT. Kembalikan (hidup, log). Proses dihentikan sebelum kembali."""
    env = dict(os.environ)
    env.pop("KN_REQUIRED_INDEX_MODE", None)
    if mode:
        env["KN_REQUIRED_INDEX_MODE"] = mode
    _NYALA["n"] += 1
    log = Path(f"/tmp/pk14_be_{TAG}_{_NYALA['n']}_{mode or 'enforce'}.log")
    with open(log, "w") as fh:
        p = subprocess.Popen([sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", str(PORT)],
                             cwd=str(BACKEND), env=env, stdout=fh, stderr=subprocess.STDOUT)
    hidup = False
    t0 = time.time()
    try:
        while time.time() - t0 < batas:
            if p.poll() is not None:
                break
            try:
                if requests.get(f"http://127.0.0.1:{PORT}/api/auth/context", timeout=3).status_code in (200, 401, 403):
                    hidup = True
                    break
            except requests.RequestException:
                pass
            time.sleep(2)
    finally:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                p.kill()
    return hidup, log.read_text(errors="ignore")


def _periksa():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_required_indexes.py")], capture_output=True,
                       text=True, env=dict(os.environ), timeout=120)
    return r.returncode, r.stdout


def _login():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _serentak(fn, n=2):
    with ThreadPoolExecutor(n) as ex:
        return [f.result() for f in [ex.submit(fn) for _ in range(n)]]


@pytest.fixture(scope="module", autouse=True)
def bersih():
    yield
    DB.penalties.delete_many({"doc_id": {"$regex": f"^so_pk14_{TAG}"}})
    DB.payment_plans.delete_many({"doc_id": {"$regex": f"^so_pk14_{TAG}"}})
    DB.sales_orders.delete_many({"id": {"$regex": f"^so_pk14_{TAG}"}})
    DB.finance_cases.delete_many({"source.id": f"rcp_pk14_{TAG}"})
    DB.journal_entries.delete_many({"source_id": {"$regex": f"^pnl_pk14_{TAG}"}})
    for c in ("interco_transactions", "interco_settlements", "interco_returns", "interco_loans"):
        DB[c].delete_many({"number": f"PK14-{TAG}"})


def test_U01_delapan_indeks_persis():
    assert diff_required(_info()) == []
    for it in REQUIRED_UNIQUE_INDEXES:
        i = DB[it["collection"]].index_information()[it["name"]]
        assert i.get("unique") is True and [(k, int(d)) for k, d in i["key"]] == list(it["keys"])


def test_U02_pemeriksa_hijau():
    kode, out = _periksa()
    assert kode == 0, out
    # KP-T5 menambah `doc_number_formats.uq_kind_entity` (8 → 9); PK-40 menambah 5 indeks wajib (faktur pajak aktif &
    # NSFP keluaran/masukan, kunci masa pajak): 9 + 5; KP-T6 menambah `pdf_templates.uq_doctype_entity`: + 1;
    # PM-T1 menambah `bank_accounts.uq_default_receiving`: + 1. CR-T1 menambah `customer_credit_profiles.uq_customer_entity`
    # dan `credit_profile_requests.uq_open_request`: + 2. PK-31 menambah `intercompany_eliminations.uq_pair_period`: + 1.
    # PM-T2 menambah `payment_codes.uq_pay_code` dan `payment_codes.uq_pay_code_line`: + 2.
    # PK-39 menambah `budgets.uq_budget_key` (satu pagu per PT, tahun, bulan, dimensi, kunci): + 1.
    # AG-T3 menambah `ai_action_proposals.uq_pending_session` (satu kartu asisten menunggu per percakapan): + 1.
    # KM-T1 menambah `sales_targets.uq_target_pt_sales_periode`, `incentive_components.uq_component_code`,
    # `incentive_definitions.uq_definition_version`: + 3.
    # PY-T1 menambah `hr_pay_components.uq_entity_code`, `hr_pay_inputs.uq_source_key` dan
    # `hr_payroll_runs.uq_active_key`: + 3.
    # PY-T2 menambah `hr_compensation_history.uq_employee_effective_approved` dan
    # `hr_employee_assignments.uq_employee_effective_approved` (satu baris sah per karyawan per tanggal berlaku): + 2.
    # CR-T2 menambah `payment_plans.uq_plan_live_doc` dan `customer_balances.uq_customer_entity`: + 2.
    # PM-T4 menambah `cash_holdings.uq_holding_receipt` (satu titipan tunai per kwitansi): + 1.
    # PY-T3 menambah `hr_holidays.uq_entity_date` dan `hr_tax_opening_balances.uq_entity_employee_year`: + 2.
    # KM-T3 menambah `incentive_sheets.uq_isheet_active_key` (satu baris lembar insentif berlaku per sales, komponen,
    # periode dasar): + 1.
    # KM-T4 menambah `interco_charges.uq_charge_run_to` (satu tagihan insentif antar-PT per proses gaji dan PT
    # tertagih): + 1.
    # KA-2 menambah `incentive_rates.uq_incentive_rate_key` (satu tarif insentif per PT dan kunci tarif): + 1.
    # KA-6 menambah `commission_period_rules.uq_commission_period` (satu potret aturan komisi per PT dan bulan): + 1.
    # BTP-5 menambah `commission_carry_balances.uq_commission_carry` (satu saldo potongan komisi per PT, sales, bulan):
    # + 1.
    # LB-T4 menambah `ar_receipts.uq_payment_report` (satu kwitansi hidup per laporan bayar): + 1.
    # F1-T1 menambah `ar_receipts.uq_bank_line_receipt` (satu kwitansi per mutasi bank): + 1 (angka di sini belum ikut).
    # Kas & Bank 2 (C6) menambah `cash_out_requests.uq_cor_idem_key` (satu pengajuan kas keluar manual per PT dan kunci
    # kiriman): + 1.
    assert out.count(": terpasang · 0 kelompok kembar") == len(REQUIRED_UNIQUE_INDEXES) == 44


def test_U03_U04_U05_indeks_tak_terpasang_menolak_mulai():
    DB.penalties.drop_index("uq_penalty_line_period")
    dasar = {"doc_type": "sales_order", "doc_id": f"so_pk14_{TAG}_u3", "plan_id": "", "line_seq": 1,
             "period_key": "2026-10-01|2026-11", "status": "draft", "entity_id": "ent_ksc", "amount": 1000.0}
    DB.penalties.insert_many([{**dasar, "id": f"pnl_pk14_{TAG}_a", "number": f"DN-PK14-{TAG}-A"},
                              {**dasar, "id": f"pnl_pk14_{TAG}_b", "number": f"DN-PK14-{TAG}-B"}])
    # U3 — mode bawaan: proses awal gagal
    hidup, log = _nyalakan()
    assert not hidup, log[-2000:]
    assert "INDEKS WAJIB BELUM TERPASANG" in log and "penalties.uq_penalty_line_period" in log
    assert "db.penalties.aggregate" in log
    kode, out = _periksa()
    assert kode == 1 and "penalties.uq_penalty_line_period" in out and "1 kelompok kembar" in out, out
    # U4 — mode warn: mulai, pesan tertulis
    hidup, log = _nyalakan("warn")
    assert hidup, log[-2000:]
    assert "INDEKS WAJIB BELUM TERPASANG" in log
    # U5 — kembar dibereskan (data uji saja): mulai, indeks terpasang lagi
    DB.penalties.delete_one({"id": f"pnl_pk14_{TAG}_b"})
    hidup, log = _nyalakan()
    assert hidup, log[-2000:]
    assert "uq_penalty_line_period" in DB.penalties.index_information()


def test_U06_indeks_hilang_tanpa_kembar_dipasang_lagi():
    DB.payment_plans.drop_index("uq_plan_active_doc")
    hidup, log = _nyalakan()
    assert hidup, log[-2000:]
    assert "uq_plan_active_doc" in DB.payment_plans.index_information()


def _pesanan(sufiks, total=3_000_000):
    sid = f"so_pk14_{TAG}_{sufiks}"
    cus = DB.customers.find_one({"entity_id": {"$in": ["ent_ksc", "all", None]}}, {"_id": 0, "id": 1, "name": 1}) or {}
    DB.sales_orders.insert_one({"id": sid, "number": f"SO-PK14-{TAG}-{sufiks}", "entity_id": "ent_ksc",
                                "customer_id": cus.get("id", ""), "customer_name": cus.get("name", ""),
                                "grand_total": total, "status": "confirmed", "payments": [],
                                "created_at": "2026-08-01T03:00:00+00:00"})
    return sid


def test_U07_rencana_bersamaan_satu_aktif():
    h = _login()
    sid = _pesanan("u7")
    body = {"doc_type": "sales_order", "doc_id": sid, "mode": "net", "net_days": 30}
    hasil = _serentak(lambda: requests.post(f"{BASE}/payment-plans", headers=h, json=body, timeout=60))
    assert all(r.status_code in (200, 400) for r in hasil), [r.text for r in hasil]
    for r in hasil:
        if r.status_code == 400:
            assert "Dokumen ini sudah punya rencana pembayaran aktif" in r.text, r.text
    assert DB.payment_plans.count_documents({"doc_id": sid, "status": "active"}) == 1


def test_U08_akrual_bersamaan_satu_nota():
    h = _login()
    sid = _pesanan("u8")
    r = requests.post(f"{BASE}/payment-plans", headers=h, timeout=60, json={
        "doc_type": "sales_order", "doc_id": sid, "mode": "custom",
        "lines": [{"kind": "installment", "basis": "percent", "percent": 100, "due_rule": "fixed_date",
                   "due_date": "2026-09-01", "label": "Pelunasan"}],
        "penalty": {"mode": "draft", "grace_days": 0}})
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    hasil = _serentak(lambda: requests.post(f"{BASE}/payment-plans/{pid}/accrue", headers=h, timeout=60))
    assert [x.status_code for x in hasil] == [200, 200], [x.text for x in hasil]
    keys = [p["period_key"] for p in DB.penalties.find({"plan_id": pid, "line_seq": 1})]
    assert keys and len(keys) == len(set(keys)), keys


def test_U09_kasus_bersamaan_satu_terbuka():
    h = _login()
    body = {"case_type": "bayar_dobel", "entity_id": "ent_ksc", "amount": 10_000,
            "source": {"kind": "ar_receipt", "id": f"rcp_pk14_{TAG}"}}
    hasil = _serentak(lambda: requests.post(f"{BASE}/finance-cases", headers=h, json=body, timeout=60))
    kode = sorted(r.status_code for r in hasil)
    assert kode == [200, 400], [r.text for r in hasil]
    assert "sudah punya kasus" in [r for r in hasil if r.status_code == 400][0].text
    assert DB.finance_cases.count_documents({"source.id": f"rcp_pk14_{TAG}",
                                             "status": {"$in": ["open", "in_progress"]}}) == 1


def test_U10_terbitkan_denda_bersamaan_satu_jurnal():
    h = _login()
    nid = f"pnl_pk14_{TAG}_u10"
    DB.penalties.insert_one({
        "id": nid, "number": f"DN-PK14-{TAG}-U10", "entity_id": "ent_ksc", "doc_type": "sales_order",
        "doc_id": f"so_pk14_{TAG}_u10", "doc_number": "SO-PK14-U10", "plan_id": "", "line_seq": 0,
        "due_date": "2026-09-01", "period_key": f"2026-09-01|{TAG}", "customer_id": "", "customer_name": "Uji",
        "base_amount": 1_000_000, "base": "installment", "amount": 20_000.0, "original_amount": 20_000.0,
        "days_late": 30, "billable_days": 30, "rate_pct_per_month": 2.0, "grace_days": 0, "cap_pct": 0,
        "status": "draft", "status_label": "Usulan", "paid_amount": 0.0, "je_id": "", "explain": [],
        "created_by": "uji", "created_at": NOW, "updated_at": NOW, "refs": []})
    hasil = _serentak(lambda: requests.post(f"{BASE}/penalties/{nid}/issue", headers=h, timeout=60))
    assert all(r.status_code < 500 for r in hasil), [r.text for r in hasil]
    assert DB.journal_entries.count_documents({"source_type": "penalty", "source_id": nid,
                                               "status": {"$ne": "void"}}) == 1


def test_U11_nomor_antar_pt_unik():
    for c in ("interco_transactions", "interco_settlements", "interco_returns", "interco_loans"):
        DB[c].insert_one({"id": f"pk14_{TAG}_{c}_1", "number": f"PK14-{TAG}"})
        with pytest.raises(DuplicateKeyError):
            DB[c].insert_one({"id": f"pk14_{TAG}_{c}_2", "number": f"PK14-{TAG}"})
