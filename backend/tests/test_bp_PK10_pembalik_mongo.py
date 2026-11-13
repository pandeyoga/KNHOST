"""PK-10 U15 — di MongoDB ASLI (lingkungan A): balik jurnal manual dan batal kas BERSAMAAN → tepat satu pembalik.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); membaca database uji lokal
(`MONGO_URL`/`DB_NAME`). Tidak untuk database berisi data nyata.
"""
import datetime
import os
from concurrent.futures import ThreadPoolExecutor

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
HARI_INI = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def _login():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _saldo_kas():
    d = k = 0.0
    for je in DB.journal_entries.find({"entity_id": "ent_ksc", "status": {"$ne": "void"},
                                       "lines.account_code": "1-1100"}, {"lines": 1}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") == "1-1100":
                d += float(ln.get("debit") or 0)
                k += float(ln.get("credit") or 0)
    return round(d - k, 2)


def test_U15_balik_dan_batal_kas_bersamaan():
    h = _login()
    acc = DB.bank_accounts.find_one({"entity_id": "ent_ksc", "is_active": {"$ne": False}, "status": {"$ne": "inactive"},
                                     "cash_type": "kas_besar"})
    if not acc:
        pytest.skip("tidak ada rekening kas besar aktif ent_ksc")
    for putaran in range(3):
        s0 = _saldo_kas()
        r = requests.post(f"{BASE}/cash-transactions", headers=h, timeout=60, json={
            "cash_type": "kas_besar", "direction": "in", "amount": 1_000_000, "category": "lain-lain",
            "description": f"uji PK-10 U15 {putaran}", "account_id": acc["id"]})
        assert r.status_code == 200, r.text
        kas = r.json()
        j = DB.journal_entries.find_one({"source_type": "cash_transaction", "source_id": kas["id"]})

        def balik():
            return requests.post(f"{BASE}/gl/journal/{j['id']}/reverse", headers=h, timeout=60,
                                 json={"date": HARI_INI, "reason": "uji balik bersamaan"}).status_code

        def batal():
            return requests.post(f"{BASE}/cash-transactions/{kas['id']}/void", headers=h, timeout=60,
                                 json={"reason": "uji batal bersamaan"}).status_code
        with ThreadPoolExecutor(2) as ex:
            fa, fb = ex.submit(balik), ex.submit(batal)
            fa.result(), fb.result()
        assert DB.journal_entries.count_documents({"ref.reverses_entry_id": j["id"], "status": {"$ne": "void"}}) == 1
        assert _saldo_kas() == s0
