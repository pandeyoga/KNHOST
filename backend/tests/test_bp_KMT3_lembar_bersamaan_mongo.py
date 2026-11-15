"""KM-T3 U16 — di MongoDB ASLI (lingkungan A): Lembar Insentif bersamaan.

  (1) dua `POST /api/incentive/sheets/{id}/approve` bersamaan atas lembar `submitted` → satu 200 dan satu 409 (pembaruan
      bersyarat status lama + revisi, `services/incentive_sheet_service._simpan`);
  (2) dua `POST /api/incentive/sheets` bersamaan → dua nomor `LIN-` berbeda (deret atomik `next_doc_number`);
  (3) dua lembar bersamaan dengan baris (sales, komponen, periode dasar) yang sama → satu 200 dan satu 409 (indeks unik wajib
      `uq_isheet_active_key`).

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`) di atas data acuan (`scripts/dev_restore_demo.sh`).
Backend harus sudah dinyalakan ulang sesudah KM-T3 (indeks wajib terpasang; rute `/api/incentive/sheets*`). Lembar uji
memakai periode bayar jauh (`2099-…`), komponen uji `KMT3UJI` dan periode dasar `2099-…`; semuanya dihapus di akhir. Tidak
untuk database berisi data nyata.
"""
import os
import threading

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"


def _login(email):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


def _bersamaan(fn, n=2):
    hasil = []
    ts = [threading.Thread(target=lambda i=i: hasil.append(fn(i))) for i in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return hasil


def _komponen(h):
    r = requests.get(f"{BASE}/incentive/components", headers=h, timeout=30)
    ada = next((c for c in r.json().get("items", []) if c.get("code") == "KMT3UJI"), None)
    if ada:
        return ada
    r = requests.post(f"{BASE}/incentive/components", headers=h, timeout=30, json={
        "code": "KMT3UJI", "name": "Insentif Uji KM-T3", "basis_period_type": "month", "columns": ["omzet"]})
    assert r.status_code == 200, r.text
    return r.json()


def test_indeks_wajib_terpasang():
    i = DB.incentive_sheets.index_information()
    a = i.get("uq_isheet_active_key")
    assert a and a.get("unique"), a
    assert [k for k, _ in a["key"]] == ["entity_id", "active_keys"]
    n = next((v for v in i.values() if [k for k, _ in v["key"]] == ["number"]), None)
    assert n and n.get("unique"), i


def test_U16_bersamaan():
    mgr = _login("manager@kainnusantara.id")
    adm = _login("admin@kainnusantara.id")
    sales = DB.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0, "id": 1})
    assert sales, "akun sales@ data acuan tidak ada"
    komp = _komponen(adm)
    try:
        # (2) dua lembar kosong bersamaan → dua nomor berbeda
        hasil = _bersamaan(lambda i: requests.post(f"{BASE}/incentive/sheets", headers=mgr, timeout=60,
                                                   json={"pay_period": "2099-01", "title": f"uji KM-T3 {i}"}))
        assert [r.status_code for r in hasil] == [200, 200], [r.text for r in hasil]
        nomor = {r.json()["number"] for r in hasil}
        assert len(nomor) == 2, nomor
        # (1) dua pengesahan bersamaan → satu 200 dan satu 409
        for putaran in range(3):
            baris = {"sales_id": sales["id"], "component_id": komp["id"], "basis_period_type": "month",
                     "basis_period": f"2099-{putaran + 1:02d}"}
            r = requests.post(f"{BASE}/incentive/sheets", headers=mgr, timeout=60,
                              json={"pay_period": "2099-02", "lines": [baris]})
            assert r.status_code == 200, r.text
            s = r.json()
            r = requests.patch(f"{BASE}/incentive/sheets/{s['id']}/lines/{s['lines'][0]['id']}", headers=mgr,
                               timeout=60, json={"amount": 1_000_000})
            assert r.status_code == 200, r.text
            assert requests.post(f"{BASE}/incentive/sheets/{s['id']}/submit", headers=mgr, timeout=60).status_code == 200
            hasil = _bersamaan(lambda i, sid=s["id"]: requests.post(
                f"{BASE}/incentive/sheets/{sid}/approve", headers=adm if i else mgr, timeout=60, json={}))
            assert sorted(r.status_code for r in hasil) == [200, 409], (putaran, [r.text for r in hasil])
            assert DB.incentive_sheets.find_one({"id": s["id"]})["status"] == "approved"
        # (3) dua lembar dengan baris yang sama bersamaan → satu 200 dan satu 409
        for putaran in range(3):
            baris = {"sales_id": sales["id"], "component_id": komp["id"], "basis_period_type": "month",
                     "basis_period": f"2099-{putaran + 6:02d}"}
            hasil = _bersamaan(lambda i, b=baris: requests.post(f"{BASE}/incentive/sheets", headers=mgr, timeout=60,
                                                                json={"pay_period": "2099-03", "lines": [b]}))
            assert sorted(r.status_code for r in hasil) == [200, 409], (putaran, [r.text for r in hasil])
            kunci = f"{sales['id']}|{komp['id']}|{baris['basis_period']}"
            assert DB.incentive_sheets.count_documents({"entity_id": ENT, "active_keys": kunci}) == 1
    finally:
        DB.incentive_sheets.delete_many({"entity_id": ENT, "pay_period": {"$regex": "^2099-"}})
        DB.incentive_components.delete_many({"entity_id": ENT, "code": "KMT3UJI"})
