"""PK-12 U16 — di MongoDB ASLI (lingkungan A): dua catat kas identik BERSAMAAN dengan Idempotency-Key sama → satu kas.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); membaca database uji lokal
(`MONGO_URL`/`DB_NAME`). Tidak untuk database berisi data nyata.
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]


def _login():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def test_U16_kas_bersamaan_kunci_sama():
    h = _login()
    acc = DB.bank_accounts.find_one({"entity_id": "ent_ksc", "is_active": {"$ne": False}, "status": {"$ne": "inactive"},
                                     "cash_type": "kas_besar"})
    if not acc:
        pytest.skip("tidak ada rekening kas besar aktif ent_ksc")
    for putaran in range(3):
        tanda = f"uji PK-12 U16 {uuid.uuid4().hex[:8]}"
        body = {"cash_type": "kas_besar", "direction": "in", "amount": 125_000, "category": "lain-lain",
                "description": tanda, "account_id": acc["id"]}
        hk = {**h, "Idempotency-Key": f"k-u16-{uuid.uuid4().hex}"}

        def kirim():
            return requests.post(f"{BASE}/cash-transactions", headers=hk, json=body, timeout=60)
        with ThreadPoolExecutor(2) as ex:
            hasil = [f.result() for f in [ex.submit(kirim), ex.submit(kirim)]]
        kode = sorted(r.status_code for r in hasil)
        assert kode in ([200, 200], [200, 409]), [r.text for r in hasil]
        for r in hasil:
            if r.status_code == 409:
                assert r.json()["detail"]["code"] == "IDEMPOTENT_IN_PROGRESS"
        if kode == [200, 200]:
            assert hasil[0].json()["id"] == hasil[1].json()["id"]
        assert DB.cash_transactions.count_documents({"description": tanda}) == 1, putaran
