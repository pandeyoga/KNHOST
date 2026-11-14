"""CR-T1 U16 — di MongoDB ASLI (lingkungan A): dua pengajuan perubahan kredit bersamaan untuk satu pelanggan di satu PT →
tepat satu 200 dan satu 409, satu dokumen `diajukan` (indeks unik parsial `credit_profile_requests.uq_open_request`).

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`) di atas data acuan (`scripts/dev_restore_demo.sh`).
Backend harus sudah dinyalakan ulang sesudah CR-T1 (indeks wajib `uq_open_request`, `uq_customer_entity`; rute
`/api/customers/{id}/credit-profile-requests`). Pelanggan uji dibuat lewat API lalu dihapus bersama pengajuannya di akhir.
Tidak untuk database berisi data nyata.
"""
import os
import threading
import uuid

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"


def _login(email="manager@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


def test_indeks_wajib_terpasang():
    p = DB.customer_credit_profiles.index_information().get("uq_customer_entity")
    assert p and p.get("unique"), p
    r = DB.credit_profile_requests.index_information().get("uq_open_request")
    assert r and r.get("unique"), r
    assert r.get("partialFilterExpression") == {"status": "diajukan"}


def test_U16_dua_pengajuan_bersamaan_satu_terbuka():
    h = _login()
    adm = _login("admin@kainnusantara.id")
    sales = DB.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0, "id": 1})
    tanda = uuid.uuid4().hex[:6]
    r = requests.post(f"{BASE}/customers", headers=adm, timeout=30, json={
        "name": f"Toko Uji CRT1 {tanda}", "pic_name": "Andi", "phone": "081234567816", "city": "Bandung",
        "address": "Jl. Uji Kredit No. 16", "entity_id": ENT, "assigned_sales_id": sales["id"]})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    try:
        for putaran in range(5):   # ulangi supaya benturan benar-benar terjadi
            hasil = []

            def _ajukan(i):
                x = requests.post(f"{BASE}/customers/{cid}/credit-profile-requests", headers=h, timeout=60,
                                  json={"changes": {"credit_limit": 1_000_000 * (i + 1)}, "reason": "Uji bersamaan"})
                hasil.append(x.status_code)

            ts = [threading.Thread(target=_ajukan, args=(i,)) for i in range(2)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
            assert sorted(hasil) == [200, 409], (putaran, hasil)
            assert DB.credit_profile_requests.count_documents({"customer_id": cid, "status": "diajukan"}) == 1
            DB.credit_profile_requests.update_many({"customer_id": cid, "status": "diajukan"},
                                                   {"$set": {"status": "dibatalkan"}})
    finally:
        DB.credit_profile_requests.delete_many({"customer_id": cid})
        DB.customer_credit_profiles.delete_many({"customer_id": cid})
        DB.customers.delete_one({"id": cid})
