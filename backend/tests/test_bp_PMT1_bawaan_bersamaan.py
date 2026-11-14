"""PM-T1 U14 — di MongoDB ASLI (lingkungan A): dua PATCH bersamaan menjadikan rekening A dan B bawaan `transfer`.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`) di atas data acuan (`scripts/dev_restore_demo.sh`).
Backend harus sudah dinyalakan ulang sesudah PM-T1 (indeks wajib `bank_accounts.uq_default_receiving`, rute
`/api/bank-accounts/receiving`). Harapan: tepat satu rekening bawaan `transfer` di PT itu, tidak ada jawaban 5xx.
Dua rekening uji dibuat lewat API lalu dinonaktifkan dan dihapus di akhir (rekening uji tanpa saldo awal dan mutasi).
Tidak untuk database berisi data nyata.
"""
import os
import threading
import uuid

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


def test_indeks_bawaan_terpasang():
    info = DB.bank_accounts.index_information().get("uq_default_receiving")
    assert info and info.get("unique"), info
    assert info.get("partialFilterExpression") == {"default_receiving_methods.0": {"$exists": True}}


def test_U14_dua_patch_bersamaan_satu_bawaan():
    h = _login()
    tanda = uuid.uuid4().hex[:6]
    ids = []
    bidang = ("holder_name", "purposes", "payment_method_codes", "default_receiving_methods", "show_on_documents")
    # Rekening data acuan PT ini ikut tertulis (pengisian awal & pencabutan bawaan) → dipulihkan di akhir.
    potret = {d["id"]: {f: d[f] for f in bidang if f in d}
              for d in DB.bank_accounts.find({"entity_id": ENT}, {"_id": 0, "id": 1, **{f: 1 for f in bidang}})}
    try:
        for huruf in ("A", "B"):
            r = requests.post(f"{BASE}/bank-accounts", headers=h, timeout=30, json={
                "name": f"Uji PMT1 {huruf} {tanda}", "account_type": "bank", "bank_name": "BCA",
                "account_number": f"9{tanda}{huruf}", "payment_method_codes": ["transfer"]})
            assert r.status_code == 200, r.text
            ids.append(r.json()["id"])
        hasil = {}

        def _jadikan_bawaan(acc_id):
            r = requests.patch(f"{BASE}/bank-accounts/{acc_id}", headers=h, timeout=60,
                               json={"default_receiving_methods": ["transfer"]})
            hasil[acc_id] = r.status_code

        for _ in range(5):   # ulangi supaya benturan benar-benar terjadi
            ts = [threading.Thread(target=_jadikan_bawaan, args=(i,)) for i in ids]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
            assert all(k < 500 for k in hasil.values()), hasil
            n = DB.bank_accounts.count_documents({"entity_id": ENT, "default_receiving_methods": "transfer"})
            assert n == 1, n
        r = requests.get(f"{BASE}/bank-accounts/receiving", headers=h, timeout=30,
                         params={"entity_id": ENT, "method": "transfer"})
        assert r.status_code == 200, r.text
        assert sum(1 for x in r.json() if x["is_default"]) == 1
    finally:
        DB.bank_accounts.delete_many({"id": {"$in": ids}})
        DB.bank_account_changes.delete_many({"account_id": {"$in": ids}})
        for acc_id, isi in potret.items():
            ops = {}
            if isi:
                ops["$set"] = isi
            if any(f not in isi for f in bidang):
                ops["$unset"] = {f: "" for f in bidang if f not in isi}
            if ops:
                DB.bank_accounts.update_one({"id": acc_id}, ops)
