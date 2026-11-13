"""PK-11 U13 — di MongoDB ASLI (lingkungan A): dua tutup buku bulan lalu BERSAMAAN → tepat satu berhasil.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); membaca database uji lokal
(`MONGO_URL`/`DB_NAME`). Tidak untuk database berisi data nyata. Penutupan yang terbentuk dibuka kembali di akhir.
"""
import datetime
import os
from concurrent.futures import ThreadPoolExecutor

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"


def _bulan_lalu() -> str:
    hari_ini = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).date()
    akhir_bulan_lalu = hari_ini.replace(day=1) - datetime.timedelta(days=1)
    return akhir_bulan_lalu.strftime("%Y-%m")


def _login():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


def test_U13_tutup_bersamaan_satu_berhasil():
    h = _login()
    kunci = _bulan_lalu()
    if DB.period_closings.find_one({"entity_id": ENT, "status": "closed", "start_date": {"$lte": f"{kunci}-28"},
                                    "end_date": {"$gte": f"{kunci}-01"}}):
        pytest.skip(f"periode {kunci} {ENT} sudah tertutup di database ini")
    sebelum = DB.journal_entries.count_documents({"entity_id": ENT, "source_type": "closing"})
    badan = {"period_type": "month", "period_key": kunci, "entity_id": ENT,
             # data acuan bisa bersaldo suspense; admin menembus dengan alasan (K-15) supaya yang diuji kuncinya
             "suspense_override_reason": "uji PK-11 U13 tutup bersamaan"}

    def tutup():
        return requests.post(f"{BASE}/finance/closing/close", headers=h, json=badan, timeout=120)
    with ThreadPoolExecutor(2) as ex:
        hasil = [f.result() for f in [ex.submit(tutup), ex.submit(tutup)]]
    kode = sorted(r.status_code for r in hasil)
    try:
        assert kode == [200, 400], [r.text for r in hasil]
        recs = list(DB.period_closings.find({"entity_id": ENT, "period_key": kunci, "status": "closed"}))
        assert len(recs) == 1
        assert DB.period_closings.count_documents({"entity_id": ENT, "status": "closing"}) == 0
        jp = DB.journal_entries.count_documents({"entity_id": ENT, "source_type": "closing",
                                                 "status": {"$ne": "void"}, "source_id": recs[0]["id"]})
        assert jp == (1 if recs[0].get("journal_entry_id") else 0)
        assert DB.journal_entries.count_documents({"entity_id": ENT, "source_type": "closing"}) - sebelum == jp
    finally:
        for r in hasil:
            if r.status_code == 200:
                requests.post(f"{BASE}/finance/closing/{r.json()['id']}/reopen", headers=h, timeout=60)
