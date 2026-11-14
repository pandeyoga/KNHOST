"""PK-36 — akun kontrol di MongoDB ASLI (lingkungan A, data acuan): penolakan tidak menulis apa pun.

Pelengkap uji lingkungan B (`tests_mem/test_PK36_akun_kontrol.py`): kueri riwayat pemetaan (`entity_id` kosong/None/PT)
dan saringan baris jurnal berjalan di MongoDB asli. Semua permintaan di sini DITOLAK atau hanya membaca — tidak ada
jurnal, usulan, atau pengaturan yang tertulis. Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`);
membaca database uji lokal (`MONGO_URL`/`DB_NAME`). Tidak untuk database berisi data nyata.
"""
import datetime
import os
import re

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
HARI_INI = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
ENT = "ent_ksc"


def _login():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


def _kontrol(h):
    r = requests.get(f"{BASE}/gl/accounts", headers=h, params={"entity_id": ENT}, timeout=60)
    assert r.status_code == 200, r.text
    return {a["code"]: a for a in r.json() if a.get("is_control")}


def test_bp_PK36_daftar_akun_dan_jurnal_manual_ditolak():
    h = _login()
    kontrol = _kontrol(h)
    assert {"1-1200", "2-1100", "1-1300", "1-1250", "2-1250"} <= set(kontrol), sorted(kontrol)
    if not all(a["manual_allowed"] is False for a in kontrol.values()):
        pytest.skip("pengaturan PT ini 'izinkan' di data acuan — penolakan tidak diuji")
    n0 = DB.journal_entries.count_documents({})
    p0 = DB.journal_proposals.count_documents({})
    r = requests.post(f"{BASE}/gl/journal", headers=h, timeout=60, json={
        "date": HARI_INI, "description": "uji PK-36 (harus ditolak)", "lines": [
            {"account_code": "1-1200", "debit": 100000, "credit": 0},
            {"account_code": "4-9000", "debit": 0, "credit": 100000}]})
    assert r.status_code == 422, r.text
    assert "akun kontrol piutang usaha" in r.json()["detail"]
    assert DB.journal_entries.count_documents({}) == n0
    assert DB.journal_proposals.count_documents({}) == p0


def test_bp_PK36_pembalikan_manual_jurnal_otomatis_ke_akun_kontrol_ditolak():
    h = _login()
    kontrol = _kontrol(h)
    if not all(a["manual_allowed"] is False for a in kontrol.values()):
        pytest.skip("pengaturan PT ini 'izinkan' di data acuan")
    je = DB.journal_entries.find_one(
        {"entity_id": ENT, "status": "posted",
         "source_type": {"$nin": ["manual", "closing", "reversal"], "$not": re.compile(r"(_reversal|_void)$")},
         "lines.account_code": {"$in": list(kontrol)}, "reversed_by_entry_id": {"$exists": False},
         "reversed": {"$ne": True}}, {"_id": 0, "id": 1, "number": 1})
    if not je:
        pytest.skip("data acuan tanpa jurnal otomatis ke akun kontrol yang belum dibalik")
    r = requests.post(f"{BASE}/gl/journal/{je['id']}/reverse", headers=h, timeout=60,
                      json={"date": HARI_INI, "reason": "uji PK-36 (harus ditolak)"})
    assert r.status_code == 422, r.text
    assert "pembalikan manual ditolak" in r.json()["detail"]
    asal = DB.journal_entries.find_one({"id": je["id"]}, {"_id": 0, "reversed_by_entry_id": 1})
    assert "reversed_by_entry_id" not in asal
