"""PK-37 U14 — di MongoDB ASLI (lingkungan A): kas manual lewat API → jurnalnya bertanggal buku WIB 10 huruf.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); membaca database uji lokal
(`MONGO_URL`/`DB_NAME`). Tidak untuk database berisi data nyata. Kas uji dibatalkan lagi di akhir.

Tanggal harapan = tanggal WIB (UTC+7) jam dinding saat permintaan; dicatat sebelum dan sesudah kirim supaya uji yang
jatuh tepat di pergantian hari (00.00 WIB) tetap sah.
"""
import datetime
import os
import re
import uuid

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
WIB = datetime.timezone(datetime.timedelta(hours=7))


def _login():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _hari_ini_wib() -> str:
    return datetime.datetime.now(WIB).date().isoformat()


def test_U14_kas_manual_jurnal_bertanggal_wib():
    h = _login()
    acc = DB.bank_accounts.find_one({"entity_id": "ent_ksc", "is_active": {"$ne": False}, "status": {"$ne": "inactive"},
                                     "cash_type": "kas_besar"})
    if not acc:
        pytest.skip("tidak ada rekening kas besar aktif ent_ksc")
    tanda = f"uji PK-37 U14 {uuid.uuid4().hex[:8]}"
    sebelum = _hari_ini_wib()
    r = requests.post(f"{BASE}/cash-transactions", headers={**h, "Idempotency-Key": f"k-pk37-{uuid.uuid4().hex}"},
                      json={"cash_type": "kas_besar", "direction": "out", "amount": 12_500, "category": "lain-lain",
                            "description": tanda, "account_id": acc["id"]}, timeout=60)
    sesudah = _hari_ini_wib()
    assert r.status_code == 200, r.text
    kas = r.json()
    try:
        je = DB.journal_entries.find_one({"source_type": "cash_transaction", "source_id": kas["id"],
                                          "status": {"$ne": "void"}}, {"_id": 0})
        assert je, "jurnal kas tidak terbentuk"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", je["date"]), je["date"]              # 10 huruf
        assert je["date"] in (sebelum, sesudah), (je["date"], sebelum, sesudah)        # = tanggal WIB saat itu
        assert "+00:00" in je["created_at"] or je["created_at"].endswith("Z")          # stempel UTC tetap di created_at
    finally:
        requests.post(f"{BASE}/cash-transactions/{kas['id']}/void", headers=h,
                      json={"reason": "pembersihan uji PK-37 U14"}, timeout=60)
