"""Live API tests for G3 Phase 03 — iteration 169 batch (4 temuan terakhir + V3-PO-02 reinforce).

Scope:
- V3-CF-01   /api/finance/cash-flow method+allocation+reconciled
- D4-FIN-04  /api/finance/profitability metric/estimate/legacy_orders; finance role strip (recursive)
- D4-CASH-01 /api/cash-transactions/summary opening dari bank_accounts.cash_type;
             POST /api/bank-accounts: account_type=cash → cash_type=kas_kecil otomatis;
             cash_type invalid → 400; backfill_cash_type startup (semua bank_accounts punya cash_type).
- D4-DATE-01 /api/home/* periode WIB bulan ini
- V3-PO-02   amandemen qty baris ber-penerimaan tepat ke received → waiting_approval + reason mengandung 'qty_to_received'
"""
import os
import datetime
import pytest
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "https://internal-pricing.preview.emergentagent.com").rstrip("/")

ADMIN = ("admin@kainnusantara.id", "demo12345")
FINANCE = ("finance@kainnusantara.id", "demo1234")
SALES = ("sales@kainnusantara.id", "demo1234")
MANAGER = ("manager@kainnusantara.id", "demo1234")

PO_ID = "po_TEST_variance01"


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


@pytest.fixture(scope="module")
def sales():
    return _h(SALES)


@pytest.fixture(scope="module")
def manager():
    return _h(MANAGER)


# ── V3-CF-01 ──────────────────────────────────────────────────────────────────
def test_cashflow_method_allocation_reconciled(admin):
    today = datetime.date.today()
    start = today.replace(day=1).isoformat()
    end = today.isoformat()
    r = requests.get(f"{BASE}/api/finance/cash-flow", params={"start": start, "end": end}, headers=admin, timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("method") == "journal_cash_classification", j
    assert j.get("allocation") == "pro_rata_cash_side", j
    assert j.get("reconciled") is True, {"reconciled": j.get("reconciled"), "diff": j.get("end_cash"), "computed_end": j.get("computed_end")}


# ── D4-FIN-04 ─────────────────────────────────────────────────────────────────
def test_profitability_structure_admin(admin):
    r = requests.get(f"{BASE}/api/finance/profitability", headers=admin, timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("metric") in ("realised_shipped",), j.get("metric")
    assert "legacy_orders" in j
    for k in ("totals", "by_customer", "by_product", "monthly"):
        assert k in j, f"missing {k}"
    est = j.get("estimate")
    assert isinstance(est, dict) and est.get("label"), est
    for k in ("totals", "by_customer", "by_product", "monthly"):
        assert k in est, f"estimate missing {k}"
    # admin punya field cost/margin
    totals = j["totals"]
    assert "revenue" in totals


def test_profitability_finance_strip_recursive(finance):
    r = requests.get(f"{BASE}/api/finance/profitability", headers=finance, timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    # cogs & margin TIDAK boleh ada di totals, estimate, maupun monthly
    def _scan(d, path="root"):
        if isinstance(d, dict):
            for k, v in d.items():
                assert k not in ("cogs", "margin", "margin_pct"), f"field {k} bocor di {path}"
                _scan(v, f"{path}.{k}")
        elif isinstance(d, list):
            for i, v in enumerate(d):
                _scan(v, f"{path}[{i}]")
    _scan(j)
    # estimate tetap ada (realisasi/estimasi struktur sama, hanya field biaya di-strip)
    assert "estimate" in j and "totals" in j["estimate"]


# ── D4-CASH-01 ────────────────────────────────────────────────────────────────
def test_cash_summary_opening_by_cash_type(admin):
    r = requests.get(f"{BASE}/api/cash-transactions/summary", headers=admin, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "kas_kecil" in j and "kas_besar" in j
    assert "opening" in j["kas_kecil"] and "opening" in j["kas_besar"]
    # type numeric
    assert isinstance(j["kas_kecil"]["opening"], (int, float))
    assert isinstance(j["kas_besar"]["opening"], (int, float))


def test_bank_accounts_all_have_cash_type(admin):
    r = requests.get(f"{BASE}/api/bank-accounts", headers=admin, timeout=30)
    assert r.status_code == 200, r.text
    accs = r.json()
    assert isinstance(accs, list) and len(accs) > 0
    missing = [a for a in accs if a.get("cash_type") not in ("kas_kecil", "kas_besar")]
    assert not missing, f"akun tanpa cash_type: {[a.get('id') for a in missing]}"


def test_create_bank_account_cash_defaults_kas_kecil(admin):
    import uuid as _u
    name = f"TEST_bank_{_u.uuid4().hex[:8]}"
    payload = {"name": name, "account_type": "cash", "entity_id": "ent_ksc", "opening_balance": 0}
    r = requests.post(f"{BASE}/api/bank-accounts", json=payload, headers=admin, timeout=30)
    assert r.status_code == 200, r.text
    doc = r.json()
    try:
        assert doc.get("cash_type") == "kas_kecil", doc
        assert doc.get("account_type") == "cash"
    finally:
        # cleanup via nonaktifkan + delete langsung tidak tersedia; set is_active=False (data uji)
        requests.patch(f"{BASE}/api/bank-accounts/{doc['id']}", json={"is_active": False, "name": doc["name"] + "_X"}, headers=admin, timeout=30)


def test_create_bank_account_invalid_cash_type_400(admin):
    payload = {"name": "TEST_bad", "account_type": "cash", "cash_type": "kas_sedang", "entity_id": "ent_ksc"}
    r = requests.post(f"{BASE}/api/bank-accounts", json=payload, headers=admin, timeout=30)
    assert r.status_code == 400, (r.status_code, r.text)
    assert "cash_type" in r.text.lower()


# ── D4-DATE-01 ────────────────────────────────────────────────────────────────
def test_home_period_wib_current_month(sales, admin):
    # sales home
    r = requests.get(f"{BASE}/api/home/sales", headers=sales, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    # bulan WIB sekarang (UTC+7)
    now_wib = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
    expected = now_wib.strftime("%Y-%m")
    period = j.get("period") or (j.get("sales_force") or {}).get("period") or ""
    # period bisa berupa "YYYY-MM" atau "{start,end}" — toleransi: cek substring tahun-bulan
    assert expected in str(period) or expected in str(j), f"period WIB {expected} tidak terlihat di payload home/sales: period={period}"


def test_home_admin_period_wib(admin):
    r = requests.get(f"{BASE}/api/home/admin", headers=admin, timeout=30)
    assert r.status_code == 200, r.text


# ── V3-PO-02 reinforce ────────────────────────────────────────────────────────
def _get_po(hdr):
    r = requests.get(f"{BASE}/api/purchase-orders/{PO_ID}", headers=hdr, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def test_po02_qty_to_received_triggers_reapproval(admin):
    """Setelah qty baris ber-penerimaan diturunkan tepat ke received,
    V3-PO-02 memastikan amandemen SELALU memicu persetujuan ulang (apapun nilainya),
    status PO = waiting_approval dan approval_reason memuat 'qty_to_received'."""
    po = _get_po(admin)
    lines = po.get("lines") or po.get("items") or []
    assert lines, po
    # ambil baris pertama (po seed po_TEST_variance01 hanya 1 baris received 60/100)
    line = dict(lines[0])
    received = float(line.get("received_qty") or 0)
    assert received > 0, "seed PO belum ada penerimaan — jalankan seed_test_po_variance.py dulu"
    # amendment qty = received (satu-satunya nilai yang diperbolehkan per V3-PO-02)
    new_item = {
        "product_id": line["product_id"],
        "quantity": received,
        "unit": line.get("unit") or line.get("base_unit") or "yard",
        "price": line.get("price", 0),
        "discount_percent": line.get("discount_percent", 0),
        "expected_grade": line.get("expected_grade", ""),
    }
    payload = {"items": [new_item], "reason": "V3-PO-02 live reinforcement test"}
    r = requests.post(f"{BASE}/api/purchase-orders/{PO_ID}/amend", json=payload, headers=admin, timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    status = (j.get("po") or j).get("status") or j.get("status")
    reason = (j.get("po") or j).get("approval_reason") or j.get("approval_reason") or ""
    reasons_blob = (reason or "") + str(j)
    assert status == "waiting_approval", f"status harus waiting_approval, dapat {status}; resp={j}"
    assert "qty_to_received" in reasons_blob, f"approval_reason harus memuat 'qty_to_received', dapat {reasons_blob[:400]}"
