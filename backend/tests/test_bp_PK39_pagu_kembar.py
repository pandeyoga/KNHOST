"""PK-39 U8 — di MongoDB ASLI (lingkungan A): dua `POST /api/finance/budgets` identik dikirim bersamaan → tepat satu 200
dan satu 409, satu dokumen di `budgets` (indeks unik wajib `budgets.uq_budget_key`).

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`) di atas data acuan (`scripts/dev_restore_demo.sh`).
Backend harus sudah dinyalakan ulang sesudah PK-39 (indeks wajib `uq_budget_key` terpasang; bila data acuan memuat pagu
kembar, aplikasi tidak mulai — titik henti H6, kueri pencari di `indexes.REQUIRED_UNIQUE_INDEXES`). Pagu uji memakai
tahun 2999 (tidak bertabrakan dengan pagu nyata) dan dihapus di akhir beserta riwayatnya. Tidak untuk database berisi
data nyata.
"""
import os
import threading

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
TAHUN = 2999


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


def _bersih():
    ids = [d["id"] for d in DB.budgets.find({"entity_id": ENT, "year": TAHUN}, {"_id": 0, "id": 1})]
    DB.budgets.delete_many({"entity_id": ENT, "year": TAHUN})
    DB.budget_history.delete_many({"budget_id": {"$in": ids}})


def test_indeks_wajib_terpasang():
    i = DB.budgets.index_information().get("uq_budget_key")
    assert i and i.get("unique"), i
    assert [k for k, _ in i["key"]] == ["entity_id", "year", "month", "dimension", "key"]


def test_U8_dua_pagu_bersamaan_satu_dokumen():
    h = _login()
    _bersih()
    try:
        for putaran in range(5):   # ulangi supaya benturan benar-benar terjadi
            hasil = []
            body = {"entity_id": ENT, "year": TAHUN, "month": putaran + 1, "dimension": "account", "key": "6-2000",
                    "amount": 1_000_000, "note": "uji PK-39 U8"}

            def _kirim():
                x = requests.post(f"{BASE}/finance/budgets", headers=h, json=body, timeout=60)
                hasil.append((x.status_code, x.text))

            ts = [threading.Thread(target=_kirim) for _ in range(2)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
            kode = sorted(k for k, _ in hasil)
            assert kode == [200, 409], (putaran, hasil)
            assert "sudah ada" in next(t for k, t in hasil if k == 409)
            assert DB.budgets.count_documents({"entity_id": ENT, "year": TAHUN, "month": putaran + 1,
                                               "dimension": "account", "key": "6-2000"}) == 1
    finally:
        _bersih()
