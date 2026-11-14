"""MN-T1 — di MongoDB ASLI (lingkungan A, data acuan): izin bawaan Finance (K-09, K-17), endpoint utama tiap view menu
keuangan & SDM yang dipindah, dan `hidden_views` berisi id grup `kas-aset` yang dihapus.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); peran uji dibuat lewat API, akun uji disisipkan
langsung ke database uji lokal (`MONGO_URL`/`DB_NAME`) dengan sandi data acuan, lalu dihapus lagi. Tidak untuk database
berisi data nyata. Padanan lapis B: `backend/tests_mem/test_MNT1_menu_keuangan.py` (U4, U11, U12, U13). Uji jalan layar
U16/U17 (peramban, satu tangkapan sidebar per peran) terpisah.

U4   tiap baris tabel bantu `view_main_permission.json`: peran Tanpa Acuan berizin tepat satu pasangan → GET tidak 403.
U13  akun seed finance@ → GET /vendor-bills 200, GET /contra-bons 200; pencairan PD berstatus disetujui bukan 403
     (PD fixture disisipkan, dibersihkan sesudahnya bersama transaksi kas & jurnalnya).
U12  peran kustom dengan `hidden_views` [finance-cases, kas-aset] (ditulis langsung) → dimuat tanpa `kas-aset`.
"""
import datetime
import json
import os
import uuid
from pathlib import Path

import bcrypt
import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
SANDI = "demo12345"
TABEL = json.loads((Path(__file__).resolve().parents[2] / "frontend" / "src" / "config" / "__tests__" / "fixtures"
                    / "view_main_permission.json").read_text(encoding="utf-8"))["views"]


def _login(email="admin@kainnusantara.id", password=SANDI):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture(scope="module")
def adm():
    return _h(_login()["token"])


def _akun(rid):
    uid = f"usr_bp_mnt1_{uuid.uuid4().hex[:8]}"
    email = f"{uid}@uji.id"
    DB.users.insert_one({"id": uid, "name": f"Uji MN-T1 {rid}", "email": email, "role": rid, "status": "active",
                         "home_entity_id": "ent_ksc", "allowed_entity_ids": ["ent_ksc"],
                         "password_hash": bcrypt.hashpw(SANDI.encode(), bcrypt.gensalt()).decode(),
                         "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
    return uid, email


def _bersihkan(uid=None, rid=None, adm=None):
    if uid:
        DB.sessions.delete_many({"user_id": uid})
        DB.users.delete_one({"id": uid})
        DB.audit_logs.delete_many({"resource_id": uid, "action": "login"})
    if rid and adm:
        requests.delete(f"{BASE}/access/roles/{rid}", headers=adm, timeout=30)


def test_MNT1_U13_finance_hutang_dan_pencairan(adm):
    fin = _h(_login("finance@kainnusantara.id")["token"])
    for ep in ("/vendor-bills", "/contra-bons"):
        r = requests.get(f"{BASE}{ep}", headers=fin, timeout=60)
        assert r.status_code == 200, (ep, r.status_code, r.text[:200])
    ca_id = f"ca_bp_mnt1_{uuid.uuid4().hex[:6]}"
    DB.cash_advances.insert_one({"id": ca_id, "number": f"PD-MNT1-{uuid.uuid4().hex[:5]}", "entity_id": "ent_ksc",
                                 "status": "approved", "lines": [{"description": "uji", "amount": 1000}],
                                 "total_amount": 1000, "approvals": [], "kegiatan": "uji MN-T1", "created_by": "uji",
                                 "created_by_id": "uji", "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
    try:
        r = requests.post(f"{BASE}/cash-advances/{ca_id}/disburse", headers=fin, timeout=60,
                          json={"cash_type": "kas_kecil", "note": "uji MN-T1"})
        assert r.status_code != 403, r.text
    finally:
        txn = [t["id"] for t in DB.cash_transactions.find({"ref_type": "cash_advance", "ref_id": ca_id}, {"id": 1})]
        DB.journal_entries.delete_many({"source_type": "cash_transaction", "source_id": {"$in": txn}})
        DB.cash_transactions.delete_many({"id": {"$in": txn}})
        DB.cash_advances.delete_one({"id": ca_id})


def test_MNT1_U04_satu_pasangan_izin_tidak_403(adm):
    ditolak, dibuat = [], []
    try:
        for view, t in sorted(TABEL.items()):
            for res, act in t["izin"]:
                ep = (t.get("endpoint_per_izin") or {}).get(f"{res}.{act}", t["endpoint"])
                r = requests.post(f"{BASE}/access/roles", headers=adm, timeout=30, json={
                    "label": f"TA BP {res[:14]}.{act[:12]} {uuid.uuid4().hex[:4]}", "base_role": "",
                    "description": "uji MN-T1", "permissions": {res: [act]}})
                assert r.status_code == 200, r.text
                rid = (r.json().get("role") or r.json())["id"]
                uid, email = _akun(rid)
                dibuat.append((uid, rid))
                h = _h(_login(email)["token"])
                code = requests.get(f"{BASE}{ep.removeprefix('/api')}", headers=h, timeout=60).status_code
                if code == 403:
                    ditolak.append(f"{view} · {res}.{act} · {ep}")
    finally:
        for uid, rid in dibuat:
            _bersihkan(uid, rid, adm)
    assert ditolak == []


def test_MNT1_U12_hidden_views_kas_aset_dibuang(adm):
    r = requests.post(f"{BASE}/access/roles", headers=adm, timeout=30, json={
        "label": f"Penyembunyi Kas & Aset BP {uuid.uuid4().hex[:4]}", "base_role": "finance", "description": "uji MN-T1"})
    assert r.status_code == 200, r.text
    rid = (r.json().get("role") or r.json())["id"]
    try:
        DB.permission_settings.update_one({"id": "default"}, {"$set": {f"hidden_views.{rid}": ["finance-cases", "kas-aset"]}})
        r = requests.get(f"{BASE}/access/roles/{rid}", headers=adm, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["hidden_views"] == ["finance-cases"]
    finally:
        _bersihkan(rid=rid, adm=adm)
