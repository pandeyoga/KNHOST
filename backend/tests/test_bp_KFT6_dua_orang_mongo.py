"""KF-T6 U12–U14 — di MongoDB ASLI (lingkungan A): buka kembali tutup buku dan jurnal manual dengan aturan dua orang.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`) di atas data acuan (`scripts/dev_restore_demo.sh`).
Backend harus sudah dinyalakan ulang sesudah KF-T6 (kunci `kontrol.*`, rute `/api/gl/journal-proposals`). Aturan diubah
lewat `PUT /api/config/values` pada lapisan PT `ent_ksc` dan dicabut lagi di akhir (`/values/clear`).

Akun: `admin@` (adm), `manager@` (mgr), `manager.printing@` (mgr2, manajer kedua di ent_ksc). Admin kedua (adm2) TIDAK
ada di data acuan: uji menyisipkan akun + sesi sementara langsung ke database uji dan menghapusnya di akhir. Periode
tertutup untuk U12 disisipkan langsung (2019-03, tanpa jurnal penutup) lalu dihapus. Jurnal yang lahir di U13/U14
dibalik lewat API di akhir. Tidak untuk database berisi data nyata.
"""
import datetime
import os
import uuid

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"


def pesan(label):
    return (f"{label} harus diputuskan orang lain: Anda yang mengajukannya. Minta rekan yang berwenang. "
            "Admin dapat mengubah aturan ini di Pengaturan › Persetujuan › Kontrol dua orang.")


def _login(email):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


def _atur(h, key, value):
    r = requests.put(f"{BASE}/config/values", headers=h, timeout=30, json={"items": [
        {"key": key, "value": value, "scope_type": "entity", "scope_id": ENT, "reason": "uji KF-T6 lapis A"}]})
    assert r.status_code == 200, r.text


def _cabut(h, key):
    requests.post(f"{BASE}/config/values/clear", headers=h, timeout=30,
                  json={"key": key, "scope_type": "entity", "scope_id": ENT, "reason": "uji KF-T6 lapis A"})


def _saldo(h, kode):
    r = requests.get(f"{BASE}/gl/accounts/{kode}/ledger", headers=h, params={"entity_id": ENT}, timeout=60)
    assert r.status_code == 200, r.text
    return float(r.json().get("balance") or 0)


def _jurnal(nilai, ket):
    return {"date": datetime.date.today().isoformat(), "description": ket, "entity_id": ENT,
            "lines": [{"account_code": "1-1100", "debit": nilai, "credit": 0, "description": ket},
                      {"account_code": "3-1000", "debit": 0, "credit": nilai, "description": ket}]}


@pytest.fixture(scope="module")
def akun():
    if not DB.users.find_one({"email": "manager.printing@kainnusantara.id"}):
        pytest.skip("data acuan belum dipulihkan (scripts/dev_restore_demo.sh)")
    adm = DB.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0})
    uid, tok = f"usr_kft6_{uuid.uuid4().hex[:8]}", "tok_kft6_" + uuid.uuid4().hex
    now = datetime.datetime.now(datetime.timezone.utc)
    DB.users.insert_one({**{k: v for k, v in adm.items() if k not in ("id", "email", "name")},
                         "id": uid, "email": f"{uid}@uji.id", "name": "Admin Kedua Uji", "status": "active"})
    DB.sessions.insert_one({"token": tok, "user_id": uid, "created_at": now,
                            "expires_at": now + datetime.timedelta(hours=2)})
    try:
        yield {"adm": _login("admin@kainnusantara.id"), "mgr": _login("manager@kainnusantara.id"),
               "mgr2": _login("manager.printing@kainnusantara.id"),
               "adm2": {"Authorization": f"Bearer {tok}", "X-Entity-Id": ENT}, "adm_nama": adm["name"]}
    finally:
        DB.sessions.delete_one({"token": tok})
        DB.users.delete_one({"id": uid})


def test_U12_buka_kembali_dua_admin(akun):
    h = akun["adm"]
    cid = f"pc_kft6_{uuid.uuid4().hex[:8]}"
    DB.period_closings.insert_one({"id": cid, "entity_id": ENT, "period_type": "month", "period_key": "2019-03",
                                   "period_label": "Maret 2019 (uji KF-T6)", "start_date": "2019-03-01",
                                   "end_date": "2019-03-31", "status": "closed", "net_income": 0.0,
                                   "journal_entry_id": None, "closed_by": "uji", "closed_at": "2019-04-01T00:00:00Z"})
    _atur(h, "kontrol.buka_kembali_tutup_buku.min_orang", "2")
    try:
        url = f"{BASE}/finance/closing/{cid}/reopen"
        r = requests.post(url, headers=h, timeout=30)
        assert r.status_code == 202, r.text
        assert r.json() == {"status": "menunggu_orang_kedua", "requested_by": akun["adm_nama"]}
        assert DB.period_closings.find_one({"id": cid})["status"] == "closed"
        r = requests.post(url, headers=h, timeout=30)
        assert (r.status_code, r.json().get("detail")) == (403, pesan("Buka kembali tutup buku")), r.text
        r = requests.post(url, headers=akun["adm2"], timeout=30)
        assert r.status_code == 200, r.text
        rec = DB.period_closings.find_one({"id": cid})
        assert rec["status"] == "reopened" and "reopen_request" not in rec
    finally:
        _cabut(h, "kontrol.buka_kembali_tutup_buku.min_orang")
        DB.period_closings.delete_one({"id": cid})


def test_U13_U14_jurnal_manual(akun):
    h = akun["adm"]
    lahir = []
    _atur(h, "kontrol.jurnal_manual.min_orang", "2")
    try:
        je0 = DB.journal_entries.count_documents({})
        kas0, modal0 = _saldo(h, "1-1100"), _saldo(h, "3-1000")
        r = requests.post(f"{BASE}/gl/journal", headers=akun["mgr"], json=_jurnal(1000000, "uji KF-T6 U13"), timeout=60)
        assert r.status_code == 202, r.text
        pid = r.json()["proposal_id"]
        assert DB.journal_entries.count_documents({}) == je0
        assert (_saldo(h, "1-1100"), _saldo(h, "3-1000")) == (kas0, modal0)
        r = requests.post(f"{BASE}/gl/journal-proposals/{pid}/approve", headers={**akun["mgr"],
                          "Idempotency-Key": uuid.uuid4().hex}, timeout=60)
        assert (r.status_code, r.json().get("detail")) == (403, pesan("Jurnal manual")), r.text
        r = requests.post(f"{BASE}/gl/journal-proposals/{pid}/approve", headers={**akun["mgr2"],
                          "Idempotency-Key": uuid.uuid4().hex}, timeout=60)
        assert r.status_code == 200, r.text
        je = DB.journal_entries.find_one({"id": r.json()["journal_id"]}, {"_id": 0})
        lahir.append(je["id"])
        assert (je["status"], je["created_by"], je["approved_by"]) == ("posted", "Dewi Rahayu", "Fajar Nugroho")
        assert _saldo(h, "1-1100") - kas0 == 1000000
        assert abs(_saldo(h, "3-1000") - modal0) == 1000000
    finally:
        _cabut(h, "kontrol.jurnal_manual.min_orang")
    _atur(h, "kontrol.jurnal_manual.batas_nominal", 10000000)
    try:
        r = requests.post(f"{BASE}/gl/journal", headers={**akun["mgr"], "Idempotency-Key": uuid.uuid4().hex},
                          json=_jurnal(5000000, "uji KF-T6 U14 kecil"), timeout=60)
        assert r.status_code == 200 and r.json()["status"] == "posted", r.text
        lahir.append(r.json()["id"])
        r = requests.post(f"{BASE}/gl/journal", headers={**akun["mgr"], "Idempotency-Key": uuid.uuid4().hex},
                          json=_jurnal(15000000, "uji KF-T6 U14 besar"), timeout=60)
        assert r.status_code == 202 and r.json()["proposal_id"].startswith("jprop_"), r.text
        requests.post(f"{BASE}/gl/journal-proposals/{r.json()['proposal_id']}/reject",
                      headers={**h, "Idempotency-Key": uuid.uuid4().hex}, json={"reason": "bersihkan uji"}, timeout=30)
    finally:
        _cabut(h, "kontrol.jurnal_manual.batas_nominal")
        for jid in lahir:   # bersihkan: jurnal pembalik (jurnal asli tetap, sesuai P7)
            requests.post(f"{BASE}/gl/journal/{jid}/reverse", headers={**h, "Idempotency-Key": uuid.uuid4().hex},
                          json={"date": datetime.date.today().isoformat(), "reason": "bersihkan uji KF-T6"}, timeout=60)
