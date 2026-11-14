"""PK-19 U15–U16 — di MongoDB ASLI (lingkungan A): dua permintaan bersamaan atas kwitansi yang sama.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); fixture disisipkan langsung ke database uji
lokal (`MONGO_URL`/`DB_NAME`). Tidak untuk database berisi data nyata.

Persiapan (fixture): pelanggan uji, pesanan A1 Rp 1.000.000 (terkirim) milik `ent_ksc`, rekening Kas Kecil uji
`rek_bp19_k` milik `ent_ksc`; toleransi selisih `ent_ksc` dibuat 0 lewat Pusat Pengaturan (lapisan PT dicabut sesudahnya).

  U15  kwitansi tunai Rp 1.200.000 ke A1 (lebih 200.000 → deposit) → dua batal bersamaan → satu 200, satu 409;
       deposit turun 200.000 tepat sekali; satu set baris pembalik (Σ baris A1 = 1.000.000 − 1.000.000 = 0).
  U16  kwitansi Rp 990.000 ke A1 (kurang 10.000) → dua "hapus sisa" bersamaan → satu 200, satu 409; satu baris
       `hapus_sisa` 10.000; satu jurnal Dr 6-9100 10.000 / Cr 1-1200 10.000.
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
JT = 1_000_000
KSC = "ent_ksc"
TOL = "payment.variance_tolerance_rupiah"


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": KSC}


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture(scope="module")
def h():
    hh = _login()
    r = requests.put(f"{BASE}/config/values", headers=hh, timeout=30, json={"items": [
        {"key": TOL, "value": 0, "scope_type": "entity", "scope_id": KSC, "reason": "uji PK-19 lapis A"}]})
    assert r.status_code == 200, r.text
    if not DB.bank_accounts.find_one({"id": "rek_bp19_k"}):
        DB.bank_accounts.insert_one({"id": "rek_bp19_k", "name": "Kas Kecil Uji BP19", "entity_id": KSC,
                                     "account_type": "cash", "cash_type": "kas_kecil", "is_active": True,
                                     "opening_balance": 0})
    yield hh
    requests.post(f"{BASE}/config/values/clear", headers=hh, timeout=30, json={
        "key": TOL, "scope_type": "entity", "scope_id": KSC, "reason": "uji PK-19 lapis A kembalikan"})


def _dunia():
    tag = uuid.uuid4().hex[:8]
    cus, so = f"cus_bp19_{tag}", f"so_bp19_{tag}"
    DB.customers.insert_one({"id": cus, "name": f"Toko BP19 {tag}", "entity_id": KSC, "status": "active",
                             "deposit_balance": 0.0, "created_at": _now()})
    DB.sales_orders.insert_one({"id": so, "number": f"SO-BP19-{tag}", "entity_id": KSC, "customer_id": cus,
                                "customer_name": f"Toko BP19 {tag}", "status": "shipped", "grand_total": float(JT),
                                "payments": [], "paid_total": 0.0, "payment_status": "unpaid", "items": [],
                                "payment_term_code": "NET30", "created_at": _now()})
    return cus, so


def _kwitansi(hh, cus, so, amount, alloc, method="tunai"):
    r = requests.post(f"{BASE}/ar-receipts", headers=hh, timeout=60, json={
        "customer_id": cus, "amount": amount, "method": method, "entity_id": KSC, "account_id": "rek_bp19_k",
        "allocations": [{"order_id": so, "amount": alloc}]})
    assert r.status_code == 200, r.text
    return r.json()


def _bersamaan(fn):
    with ThreadPoolExecutor(2) as ex:
        return sorted(ex.map(fn, [0, 1]))


def test_PK19_U15_dua_batal_bersamaan(h):
    for _ in range(3):   # beberapa putaran: balapan tidak selalu muncul di satu percobaan
        cus, so = _dunia()
        k1 = _kwitansi(h, cus, so, 1_200_000, JT)
        assert DB.customers.find_one({"id": cus})["deposit_balance"] == 200_000
        codes = _bersamaan(lambda _i: requests.post(f"{BASE}/ar-receipts/{k1['id']}/void", headers=h,
                                                    params={"reason": "uji U15"}, timeout=60).status_code)
        assert codes == [200, 409], codes
        assert DB.customers.find_one({"id": cus})["deposit_balance"] == 0     # turun 200.000 sekali
        rows = DB.sales_orders.find_one({"id": so})["payments"]
        assert sorted(p["amount"] for p in rows) == [-JT, JT] and sum(p["amount"] for p in rows) == 0
        rc = DB.ar_receipts.find_one({"id": k1["id"]})
        assert rc["status"] == "void" and "saga_lock" not in rc and rc["void_intent"]["status"] == "done"


def test_PK19_U16_dua_hapus_sisa_bersamaan(h):
    for _ in range(3):
        cus, so = _dunia()
        k3 = _kwitansi(h, cus, so, 990_000, 990_000, method="tunai")
        body = {"kind": "writeoff", "reason_code": "uncollectible_small", "note": "uji U16"}
        codes = _bersamaan(lambda _i: requests.post(f"{BASE}/payment-variances/receipt/{k3['id']}/decide",
                                                    headers=h, json=body, timeout=60).status_code)
        assert codes == [200, 409], codes
        rows = [p for p in DB.sales_orders.find_one({"id": so})["payments"] if p.get("kind") == "hapus_sisa"]
        assert [p["amount"] for p in rows] == [10_000]
        decs = list(DB.payment_variance_decisions.find({"receipt_id": k3["id"]}))
        assert len(decs) == 1 and decs[0]["status"] == "done"
        jes = list(DB.journal_entries.find({"source_type": "payment_variance_writeoff", "source_id": decs[0]["id"],
                                            "status": {"$ne": "void"}}))
        assert len(jes) == 1 and jes[0]["total_debit"] == 10_000
