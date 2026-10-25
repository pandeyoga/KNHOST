"""Keputusan pemilik 26 Okt (audit UI tahap 2) — D1 Keuangan: uji lewat HTTP (butuh server backend dengan kode terbaru).

Dijalankan koordinator setelah restart backend (data acuan `scripts/dev_restore_demo.sh`):
  cd /app/backend && python -m pytest tests/test_decisions_d1_http.py -p no:randomly -n 0 -q

* K-01 — `/home/admin` & `/home/manager` piutang = `/ar/aging` (semua pelanggan, lewat tempo sama).
* K-02 — `/bank-accounts/position` = Posisi Kas Dasbor Keuangan = Kas Saat Ini Proyeksi Arus Kas (buku besar).
* K-03 — Pusat Dokumen: `amount` = total termasuk PPN, `amount_dpp` + PPN = total; Meja Saya berlabel.
* K-07 — `/interco/summary` membawa posisi bersih dua arah (≤ bruto) + `net_pairs`.
* K-15 — tutup buku dengan Suspense ≠ 0: 409 tanpa alasan, 403 non-admin, 400 alasan < 5 huruf, 200 admin + jejak audit.
"""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
TAG = uuid.uuid4().hex[:6]


def _login(email, pw="demo12345"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


ADMIN = _login("admin@kainnusantara.id")
MANAGER = _login("manager@kainnusantara.id")


def _get(path, h=ADMIN, **params):
    r = requests.get(f"{BASE}{path}", headers=h, params=params or None, timeout=60)
    assert r.status_code == 200, (path, r.status_code, r.text[:300])
    return r.json()


# ─── K-01 ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_k01_control_tower_and_manager_ar_equal_ar_aging():
    aging = _get("/ar/aging")["totals"]
    home = _get("/home/admin")["ar"]
    assert abs(home["outstanding"] - aging["total"]) < 1, (home, aging["total"])
    assert abs(home["overdue"] - aging["overdue"]) < 1, (home, aging["overdue"])
    assert home["scope"] == "semua pelanggan" and "outside_board" not in home
    mgr = _get("/home/manager", MANAGER)
    assert abs(mgr["ar_all"]["outstanding"] - aging["total"]) < 1
    ar_row = next(r for r in mgr["late_today"]["all_rows"] if r["key"] == "ar")
    assert abs(ar_row["amount"] - aging["overdue"]) < 1


def test_k01_overdue_board_includes_customers_without_sales():
    aging = _get("/ar/aging")
    no_sales_overdue = round(sum(c["overdue"] for c in aging["customers"] if not c.get("assigned_sales_id")), 2)
    home = _get("/home/admin")
    rows = {r["sales_id"]: r for r in home["top_overdue"]}
    if no_sales_overdue > 0.01:   # data acuan: Toko Kain Sejahtera Rp 1.193.250 tanpa sales
        assert "" in rows and rows[""]["sales_name"] == "Tanpa sales", rows
        assert abs(rows[""]["overdue_amount"] - no_sales_overdue) < 1


def test_k04_control_tower_low_stock_equals_single_definition():
    """Permintaan D2 (K-04): KPI "Stok Rendah" Control Tower = `/inventory/low-stock-summary` (definisi tunggal);
    saran reorder (ROP) tetap ada sebagai `reorder`."""
    home = _get("/home/admin")
    low = _get("/inventory/low-stock-summary", limit=0)
    assert home["low_stock"]["count"] == low["count"], (home["low_stock"]["count"], low["count"])
    assert home["low_stock"]["threshold"] == low["threshold"]
    assert "reorder" in home and "count" in home["reorder"]


# ─── K-14 (permintaan D3) — alasan minimum 5 huruf di endpoint keuangan ─────────────────────────────────────
def test_k14_finance_reason_min_five_letters():
    r = requests.post(f"{BASE}/payment-variances/pv_TEST_D1_nope/reverse", headers=ADMIN, json={"reason": "abcd"})
    assert r.status_code == 422, r.text
    r = requests.post(f"{BASE}/payment-plans/pp_TEST_D1_nope/void", headers=ADMIN, json={"reason": "abcd"})
    assert r.status_code == 422, r.text


# ─── K-02 ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_k02_cash_position_equals_finance_tower_and_forecast():
    pos = _get("/bank-accounts/position")
    tower = _get("/finance/tower")
    fc = _get("/finance/cashflow-forecast")
    assert abs(pos["gl_total"] - tower["cash"]["total"]) < 1, (pos["gl_total"], tower["cash"]["total"])
    assert abs(pos["gl_total"] - fc["cash_now"]) < 1
    assert set(pos["unlinked"]) == {"count", "inflow", "outflow", "net"}


# ─── K-03 ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_k03_document_center_total_includes_ppn():
    docs = _get("/pdf/documents/sales_order")["documents"]
    so = {d["source_id"]: d for d in docs}
    raw = {o["id"]: o for o in DB.sales_orders.find({"id": {"$in": list(so)}}, {"_id": 0, "id": 1, "grand_total": 1,
                                                                                   "ppn_amount": 1})}
    checked = 0
    for sid, d in so.items():
        o = raw.get(sid) or {}
        if float(o.get("ppn_amount") or 0) > 0 and o.get("grand_total"):
            assert abs(float(d["amount"]) - float(o["grand_total"])) < 0.01, (d, o)
            assert abs(float(d["amount_dpp"]) + float(d["ppn_amount"]) - float(d["amount"])) < 0.02, d
            assert d["amount_includes_ppn"] is True
            checked += 1
    assert checked > 0, "data acuan tidak memuat SO ber-PPN"


def test_k03_my_desk_money_columns_labelled():
    desk = _get("/desks/me", MANAGER)
    qs = {q["id"]: q for q in desk.get("queues") or []}
    for qid in ("so_acc", "po_acc"):
        if qid in qs:
            assert qs[qid]["value_label"] == "Total (termasuk PPN)", qs[qid]


# ─── K-07 ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_k07_interco_summary_has_net_position():
    s = _get("/interco/summary", entity_id=ENT)
    for k in ("net_payable", "net_receivable", "net_pairs", "total_payable", "total_receivable"):
        assert k in s, s.keys()
    assert s["net_payable"] <= s["total_payable"] + 0.01
    assert s["net_receivable"] <= s["total_receivable"] + 0.01
    for p in s["net_pairs"]:
        assert abs(p["net"] - abs(p["gross_debtor_owes"] - p["gross_creditor_owes"])) < 0.01, p


# ─── K-15 ─────────────────────────────────────────────────────────────────────────────────────────────────────
PERIOD = "2018-02"


def test_k15_close_blocked_by_suspense_admin_override_audited():
    if DB.period_closings.find_one({"entity_id": ENT, "status": "closed",
                                    "period_key": {"$in": [PERIOD, PERIOD[:4]]}}):
        pytest.skip("periode uji 2018-02/2018 sudah tertutup di DB ini")
    je_id = f"je_TEST_D1K15_{TAG}"
    DB.journal_entries.insert_one({
        "id": je_id, "number": f"TEST/JE-D1K15-{TAG}", "entity_id": ENT, "status": "posted", "source_type": "manual",
        "date": f"{PERIOD}-10T00:00:00", "description": "TEST_D1 suspense",
        "lines": [{"account_code": "1-9999", "debit": 12345.0, "credit": 0.0},
                  {"account_code": "1-1100", "debit": 0.0, "credit": 12345.0}]})
    body = {"period_type": "month", "period_key": PERIOD, "entity_id": ENT}
    rec_id = None
    try:
        pv = _get("/finance/closing/preview", period_type="month", period_key=PERIOD, entity_id=ENT)
        assert pv["suspense_blocks_close"] is True and abs(pv["suspense_balance"]) > 0
        r = requests.post(f"{BASE}/finance/closing/close", headers=MANAGER, json=body)
        assert r.status_code == 409 and "Suspense" in r.text, r.text
        r = requests.post(f"{BASE}/finance/closing/close", headers=MANAGER,
                          json={**body, "suspense_override_reason": "manajer coba tembus"})
        assert r.status_code == 403, r.text
        r = requests.post(f"{BASE}/finance/closing/close", headers=ADMIN, json=body)
        assert r.status_code == 409, r.text
        r = requests.post(f"{BASE}/finance/closing/close", headers=ADMIN, json={**body, "suspense_override_reason": "abc"})
        assert r.status_code == 400, r.text
        assert DB.period_closings.count_documents({"entity_id": ENT, "period_key": PERIOD, "status": "closed"}) == 0
        r = requests.post(f"{BASE}/finance/closing/close", headers=ADMIN,
                          json={**body, "suspense_override_reason": "TEST_D1 mutasi bank belum dikenali"})
        assert r.status_code == 200, r.text
        rec = r.json()
        rec_id = rec["id"]
        assert rec["suspense_override"]["reason"] == "TEST_D1 mutasi bank belum dikenali"
        log = DB.audit_logs.find_one({"action": "period_close_suspense_override", "entity_id": rec_id}, {"_id": 0})
        assert log and log.get("reason") == "TEST_D1 mutasi bank belum dikenali", log
    finally:
        if rec_id:
            DB.period_closings.delete_one({"id": rec_id})
            DB.journal_entries.delete_many({"source_type": "closing", "source_id": rec_id})
        DB.journal_entries.delete_one({"id": je_id})
        DB.period_close_locks.delete_many({"_id": ENT})
