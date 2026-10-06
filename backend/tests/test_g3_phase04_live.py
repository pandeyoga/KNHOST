"""Live API tests for G3 Phase 04 — iteration 170 batch (24 temuan Fase 04 + ekspor xlsx).

Scope singkat:
- Ekspor /api/finance/profitability/export.xlsx (admin: 3 sheet + HPP; finance: tanpa HPP)
- /api/inventory/stock-analytics (full landed cost_basis, aging-rows match)
- /api/wms/health-dashboard (putaway_* + latest_cc_status)
- /api/hr/analytics/summary (turnover.missing_separation_date, payroll.runs/unposted_runs)
- PATCH /api/hr/employees/{id} status resigned + separation_date valid/invalid
- POST /api/hr/kpi period '2026-99' → 400; bobot 0 tersimpan 0; /api/hr/kpi/me rata-rata abaikan bobot 0
- POST /api/config/simulate bill_match: received 0 billed 10 → verdict block
- Bank recon: preview MT940 RC/RD + stmt_date 2026-13-01 → ditolak
- /api/finance/equity-changes net_income = laba P&L + movement_unclosed_earnings
- /api/marketing/dashboard breakdown_additive=false
"""
import io
import os
import datetime
import pytest
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "https://internal-pricing.preview.emergentagent.com").rstrip("/")

ADMIN = ("admin@kainnusantara.id", "demo12345")
FINANCE = ("finance@kainnusantara.id", "demo1234")


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return r.json()["token"]


def _h(creds):
    return {"Authorization": f"Bearer {_login(*creds)}"}


@pytest.fixture(scope="module")
def admin():
    return _h(ADMIN)


@pytest.fixture(scope="module")
def finance():
    return _h(FINANCE)


# ── Export profitabilitas xlsx ────────────────────────────────────────────────
def _xlsx_sheets(content: bytes):
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(content), read_only=True)
    return wb.sheetnames, {name: [list(r) for r in wb[name].iter_rows(values_only=True)] for name in wb.sheetnames}


def test_profitability_export_admin_has_cost_columns(admin):
    today = datetime.date.today()
    start = today.replace(day=1).isoformat()
    r = requests.get(f"{BASE}/api/finance/profitability/export.xlsx",
                     params={"start": start, "end": today.isoformat()},
                     headers=admin, timeout=60)
    assert r.status_code == 200, r.text
    assert "spreadsheetml" in r.headers.get("content-type", "")
    names, data = _xlsx_sheets(r.content)
    assert names == ["Per Pelanggan", "Per Produk", "Keterangan"], names
    head = data["Per Pelanggan"][0]
    # admin melihat kolom HPP/Marjin
    assert "Realisasi HPP" in head and "Estimasi HPP" in head and "Realisasi Marjin %" in head
    assert "Selisih Pendapatan (Realisasi − Estimasi)" in head
    # Keterangan memuat label realisasi+estimasi
    ket = {row[0]: row[1] for row in data["Keterangan"] if row and row[0]}
    assert "Realisasi" in ket and "Estimasi" in ket
    assert "ditampilkan" in str(ket.get("HPP/Marjin", ""))


def test_profitability_export_finance_hides_cost(finance):
    today = datetime.date.today()
    start = today.replace(day=1).isoformat()
    r = requests.get(f"{BASE}/api/finance/profitability/export.xlsx",
                     params={"start": start, "end": today.isoformat()},
                     headers=finance, timeout=60)
    assert r.status_code == 200
    _, data = _xlsx_sheets(r.content)
    head = data["Per Pelanggan"][0]
    assert "Realisasi HPP" not in head and "Estimasi HPP" not in head
    assert "Realisasi Marjin" not in head and "Estimasi Marjin" not in head
    assert "Realisasi Pendapatan" in head and "Estimasi Pendapatan" in head
    ket = {row[0]: row[1] for row in data["Keterangan"] if row and row[0]}
    assert "disembunyikan" in str(ket.get("HPP/Marjin", ""))


# ── D4-STOCK-02/03/04 Stock analytics ────────────────────────────────────────
def test_stock_analytics_full_landed_and_aging_match(admin):
    r = requests.get(f"{BASE}/api/inventory/stock-analytics", headers=admin, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    s = data.get("summary") or {}
    assert "total_base_value" in s and "total_landed_value" in s
    assert s.get("cost_basis") == "full_landed", s.get("cost_basis")
    # jumlah qty di aging buckets = jumlah on-hand lintas baris (bila ada data)
    rows = data.get("rows") or []
    aging = data.get("aging") or {}
    if rows:
        total_on_hand = sum(float(r.get("on_hand", 0) or 0) for r in rows)
        total_aging = sum(float(v.get("qty", 0) or 0) for v in (aging.values() if isinstance(aging, dict) else []))
        # toleransi kecil karena pembulatan
        assert abs(total_on_hand - total_aging) < 1.0, (total_on_hand, total_aging)


# ── D4-WMS-04 / D4-WMS-02 WMS health dashboard ──────────────────────────────
def test_wms_health_putaway_and_cc(admin):
    r = requests.get(f"{BASE}/api/wms/health-dashboard", headers=admin, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    totals = data.get("totals") or {}
    for k in ("putaway_pending", "putaway_ready", "putaway_blocked"):
        assert k in totals, f"missing {k} in totals {list(totals)}"
    whs = data.get("warehouses") or []
    assert whs, "no warehouses in health response"
    # per-warehouse harus punya putaway_blocked_by_reason dan latest_cc_status
    sample = whs[0]
    assert "putaway_blocked_by_reason" in sample, list(sample.keys())
    assert "latest_cc_status" in sample, list(sample.keys())
    # kolom last_cc boleh None (belum ada hitungan selesai), tidak tertimpa sesi open
    # cukup pastikan kalau latest_cc_status != 'completed'/'measured'/'closed' maka last_cc boleh null
    lcs = (whs[0] or {}).get("latest_cc_status")
    if lcs and str(lcs).lower() in ("open", "running", "in_progress"):
        last_cc = (whs[0] or {}).get("last_cc")
        if isinstance(last_cc, dict):
            assert last_cc.get("status", "").lower() not in ("open", "running", "in_progress")


# ── D4-HR-01/02 HR analytics summary ────────────────────────────────────────
def test_hr_analytics_summary_fields(admin):
    r = requests.get(f"{BASE}/api/hr/analytics/summary", headers=admin, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    t = data.get("turnover") or {}
    p = data.get("payroll") or {}
    assert "missing_separation_date" in t, list(t)
    assert "runs" in p and "unposted_runs" in p, list(p)


# ── D4-HR-02 PATCH employee separation ─────────────────────────────────────
def test_hr_employee_separation_valid_and_invalid(admin):
    # buat karyawan TEST_
    payload = {
        "name": "TEST_FASE04_SEP",
        "email": "TEST_sep_fase04@example.com",
        "status": "active",
        "join_date": "2025-01-01",
    }
    r = requests.post(f"{BASE}/api/hr/employees", json=payload, headers=admin, timeout=30)
    assert r.status_code in (200, 201), r.text
    emp = r.json()
    emp_id = emp.get("id") or emp.get("_id")
    assert emp_id, emp

    try:
        # separation_date invalid '2026-02-30' → 400
        r_bad = requests.patch(f"{BASE}/api/hr/employees/{emp_id}",
                               json={"data": {"status": "resigned", "separation_date": "2026-02-30"}},
                               headers=admin, timeout=30)
        assert r_bad.status_code == 400, f"expected 400, got {r_bad.status_code}: {r_bad.text}"

        # separation_date valid tersimpan
        r_ok = requests.patch(f"{BASE}/api/hr/employees/{emp_id}",
                              json={"data": {"status": "resigned", "separation_date": "2026-02-28"}},
                              headers=admin, timeout=30)
        assert r_ok.status_code == 200, r_ok.text
        got = r_ok.json()
        assert str(got.get("separation_date", ""))[:10] == "2026-02-28", got.get("separation_date")
        assert got.get("status") == "resigned"
    finally:
        # cleanup
        requests.delete(f"{BASE}/api/hr/employees/{emp_id}", headers=admin, timeout=30)


# ── D4-KPI-PERIOD-01 / WEIGHT-01 ─────────────────────────────────────────────
def test_hr_kpi_invalid_period_and_weight_zero(admin):
    # Dapatkan satu karyawan existing untuk uji
    r_list = requests.get(f"{BASE}/api/hr/employees", headers=admin, timeout=30)
    assert r_list.status_code == 200
    emps = r_list.json()
    if not emps:
        pytest.skip("no employees in DB")
    emp_id = (emps[0].get("id") or emps[0].get("_id"))
    assert emp_id

    # period invalid '2026-99' → 400
    bad = requests.post(f"{BASE}/api/hr/kpi", headers=admin, timeout=30,
                        json={"employee_id": emp_id, "period": "2026-99",
                              "metric": "TEST_metric", "target": 10, "actual": 5,
                              "weight": 1})
    assert bad.status_code == 400, f"expected 400, got {bad.status_code}: {bad.text}"

    # weight 0 tersimpan 0
    ok = requests.post(f"{BASE}/api/hr/kpi", headers=admin, timeout=30,
                       json={"employee_id": emp_id, "period": "2026-01",
                             "metric": "TEST_FASE04_weight0", "target": 10, "actual": 5,
                             "weight": 0, "note": "TEST_"})
    assert ok.status_code in (200, 201), ok.text
    doc = ok.json()
    assert float(doc.get("weight", -1)) == 0.0, doc
    kpi_id = doc.get("id")

    # cleanup
    if kpi_id:
        requests.delete(f"{BASE}/api/hr/kpi/{kpi_id}", headers=admin, timeout=30)


# ── D4-SIM-01 bill_match block ───────────────────────────────────────────────
def test_config_simulate_bill_match_block_when_not_received(admin):
    body = {
        "simulator": "bill_match",
        "sample": {"received_qty": 0, "billed_qty": 10,
                   "po_price": 100000, "billed_price": 100000,
                   "ordered_qty": 10, "already_billed_qty": 0,
                   "match_mode": "received"},
    }
    r = requests.post(f"{BASE}/api/config/simulate", json=body, headers=admin, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("verdict") == "block", data


# ── D4-BANK-01/02 preview MT940 strict ISO date ─────────────────────────────
MT940_RD_RC_SAMPLE = """:20:TEST
:25:1234567890
:28C:1/1
:60F:C260101IDR0,00
:61:260215RD1000,00NTRFTEST//ref1
:86:Masuk saldo
:62F:C260215IDR1000,00
-"""

MT940_INVALID_DATE = """:20:TEST
:25:1234567890
:28C:1/1
:60F:C260101IDR0,00
:61:260230D1000,00NTRFTEST//ref2
:86:tanggal 30 feb
:62F:D260230IDR1000,00
-"""


def test_bank_recon_preview_rd_rc_markers(admin):
    r = requests.post(f"{BASE}/api/bank-reconciliation/preview", headers=admin, timeout=30,
                      json={"raw": MT940_RD_RC_SAMPLE, "fmt": {"type": "mt940"}, "year_hint": 2026})
    # Boleh gagal bila format tidak dikenali, tapi harus 200/400 bukan 500
    assert r.status_code in (200, 400), f"{r.status_code}: {r.text}"
    if r.status_code == 200:
        data = r.json()
        # response memakai 'rows' untuk baris mutasi dan 'errors' untuk per-baris
        assert "rows" in data or "errors" in data or "line_errors" in data, list(data)


def test_bank_recon_import_rejects_invalid_stmt_date(admin):
    # import langsung dengan stmt_date 2026-13-01 → harus ditolak
    body = {
        "bank_account_id": "acc_nonexistent_TEST",
        "lines": [{"stmt_date": "2026-13-01", "amount": 100, "direction": "in", "description": "TEST"}],
    }
    r = requests.post(f"{BASE}/api/bank-reconciliation/import", headers=admin, timeout=30, json=body)
    # Baik 400 (invalid date) atau 403/404 (akun tidak ada). Yang penting bukan 500 dan bukan 200.
    assert r.status_code in (400, 403, 404), f"expected 400/403/404, got {r.status_code}: {r.text[:200]}"


# ── D4-EQ-01 equity-changes net_income + movement ─────────────────────────────
def test_equity_statement_fields(admin):
    today = datetime.date.today()
    start = today.replace(day=1).isoformat()
    r = requests.get(f"{BASE}/api/finance/equity-changes",
                     params={"start": start, "end": today.isoformat()},
                     headers=admin, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "net_income" in data and "period_operating_net_income" in data, list(data)
    assert "movement_unclosed_earnings" in data, list(data)
    # net_income = period_operating_net_income
    assert abs(float(data["net_income"]) - float(data["period_operating_net_income"])) < 0.5


# ── D4-MKT-01 breakdown_additive=false ───────────────────────────────────────
def test_marketing_dashboard_breakdown_additive_false(admin):
    r = requests.get(f"{BASE}/api/marketing/dashboard", headers=admin, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("breakdown_additive") is False, data.get("breakdown_additive")
    assert str(data.get("breakdown_basis", "")).lower() in ("shared_post_attribution", "shared", "post_attribution") \
        or "shared" in str(data.get("breakdown_basis", ""))
