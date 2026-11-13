"""PK-08 U14 — di MongoDB ASLI (lingkungan A): dua bayar denda BERSAMAAN dengan kunci berbeda atas nota 100.000.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); fixture disisipkan langsung ke database uji
lokal (`MONGO_URL`/`DB_NAME`). Tidak untuk database berisi data nyata.
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _rekening():
    acc = DB.bank_accounts.find_one({"entity_id": "ent_ksc", "is_active": {"$ne": False},
                                     "status": {"$ne": "inactive"}})
    if not acc:
        pytest.skip("tidak ada rekening aktif ent_ksc di database uji")
    return acc["id"]


def test_U14_bayar_denda_bersamaan_kunci_berbeda():
    h, rek = _login(), _rekening()
    for putaran in range(3):
        nid = f"pnl_bp08_{uuid.uuid4().hex[:8]}"
        DB.penalties.insert_one({
            "id": nid, "number": nid.upper(), "entity_id": "ent_ksc", "doc_type": "sales_order", "doc_id": "so_bp08",
            "plan_id": "", "line_seq": 0, "due_date": "2026-10-01", "period_key": f"2026-10-01|{nid}",
            "customer_name": "Uji BP08", "amount": 100000.0, "original_amount": 100000.0, "paid_amount": 0.0,
            "status": "draft", "created_at": "2026-11-13T00:00:00+00:00"})
        r = requests.post(f"{BASE}/penalties/{nid}/issue", headers=h, timeout=60)
        assert r.status_code == 200, r.text

        def bayar(key):
            return requests.post(f"{BASE}/penalties/{nid}/pay", json={"amount": 60000, "account_id": rek},
                                 headers={**h, "Idempotency-Key": key}, timeout=60).status_code
        with ThreadPoolExecutor(2) as ex:
            codes = sorted(ex.map(bayar, [f"bp08-{putaran}-a", f"bp08-{putaran}-b"]))
        assert codes[0] == 200 and codes[1] in (400, 409), codes
        p = DB.penalties.find_one({"id": nid})
        assert p["paid_amount"] == 60000
        assert DB.cash_transactions.count_documents({"ref_type": "penalty", "ref_id": nid}) == 1
