"""Audit UI tahap 2 (UAT 24 Okt) — grup G1 Keuangan: uji lewat HTTP (butuh server backend yang memuat kode terbaru).

Dijalankan koordinator setelah restart backend:
  cd /app/backend && python -m pytest tests/test_audit2_g1_http.py -p no:randomly -n 0 -q
"""
import os

import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]


def _login(email, pw="demo12345"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


ADMIN = _login("admin@kainnusantara.id")


def test_g108_revenue_mapping_candidates_not_empty():
    """Pemetaan Akun › Pendapatan penjualan: kandidat 4-xxxx muncul (dulu kosong karena revenue vs income)."""
    r = requests.get(f"{BASE}/gl/account-mappings/penjualan.pendapatan/candidates", headers=ADMIN)
    assert r.status_code == 200, r.text
    codes = [c["code"] for c in r.json()]
    assert "4-1000" in codes, codes
    rows = {x["key"]: x for x in requests.get(f"{BASE}/gl/account-mappings", headers=ADMIN).json()["rows"]}
    assert rows["penjualan.pendapatan"]["allowed_type_labels"] == ["Pendapatan"]


def test_g120_cash_void_records_reason():
    """Anulir transaksi kas manual: alasan dikirim & tercatat di dokumen."""
    c = requests.post(f"{BASE}/cash-transactions", headers=ADMIN, json={
        "cash_type": "kas_kecil", "direction": "out", "amount": 1234, "category": "lain",
        "description": "TEST_G1 uji anulir beralasan", "entity_id": "ent_ksc"})
    assert c.status_code in (200, 201), c.text
    tid = c.json()["id"]
    v = requests.post(f"{BASE}/cash-transactions/{tid}/void", headers=ADMIN,
                      json={"reason": "TEST_G1 salah input nominal"})
    assert v.status_code == 200, v.text
    doc = DB.cash_transactions.find_one({"id": tid})
    assert doc["status"] == "void" and doc["void_reason"] == "TEST_G1 salah input nominal"


def test_g126_gl_summary_reports_void_count_and_sources():
    r = requests.get(f"{BASE}/gl/summary", headers=ADMIN)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body.get("void_count"), int)
    assert isinstance(body.get("sources"), list)
    listed = requests.get(f"{BASE}/gl/journal", headers=ADMIN, params={"page": 1, "page_size": 1}).json()
    assert listed["total"] == body["journal_count"] + body["void_count"]


def test_g102_exchange_schedules_include_group_suppliers():
    r = requests.get(f"{BASE}/contra-bons/exchange-schedules", headers=ADMIN)
    assert r.status_code == 200, r.text
    sched = r.json()
    gr = requests.get(f"{BASE}/contra-bons/unbilled-receipts", headers=ADMIN).json()
    total_sched = round(sum(x["unbilled_gr_value"] for x in sched["rows"]), 2)
    assert abs(total_sched - float(gr["total_value"])) < 0.01, (total_sched, gr["total_value"])
