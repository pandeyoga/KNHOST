"""KM-T4 U16 — di MongoDB ASLI (lingkungan A): dua pengesahan Lembar Insentif bersamaan di PT bermode Lembar Insentif.

Dua `POST /api/incentive/sheets/{id}/approve` bersamaan atas lembar `submitted` (PT bermode `sheet`) → satu 200 dan satu
409 (NIAT `submitted → approving` bersyarat revisi, `services/incentive_payroll.sahkan_tertaut`); hasilnya tepat satu
jurnal `incentive_sheet` dan satu masukan gaji per baris (kunci unik `hr_pay_inputs.source_key`). Diulang tiga kali.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`) di atas data acuan (`scripts/dev_restore_demo.sh`).
Backend harus sudah dinyalakan ulang sesudah KM-T4. Uji MENGUBAH pengaturan `hr.payroll_commission_mode` lapisan PT
`ent_ksc` menjadi `sheet` (beralasan) lalu MENCABUTNYA di akhir; lembar uji memakai periode bayar & periode dasar jauh
(`2099-…`) dan komponen uji `KMT4UJI`; lembar, masukan gaji, dan jurnalnya dihapus di akhir. Tidak untuk database berisi
data nyata (titik henti H5: sakelar PT nyata diubah pemilik).
"""
import os
import threading

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
KUNCI = "hr.payroll_commission_mode"


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
    ada = next((c for c in r.json().get("items", []) if c.get("code") == "KMT4UJI"), None)
    if ada:
        return ada
    r = requests.post(f"{BASE}/incentive/components", headers=h, timeout=30, json={
        "code": "KMT4UJI", "name": "Insentif Uji KM-T4", "basis_period_type": "month", "columns": ["omzet"]})
    assert r.status_code == 200, r.text
    return r.json()


def _mode(h, nilai):
    item = {"key": KUNCI, "scope_type": "entity", "scope_id": ENT, "reason": "uji bersamaan KM-T4 (data acuan)"}
    if nilai is None:
        # Cek integrator (lingkungan A): `/config/values/clear` menerima SATU butir (`ConfigValueIn`), bukan `{"items": …}` —
        # bentuk lama → 422, pembersihan berhenti dan lembar uji tertinggal (putaran berikut 409 "sudah ada di lembar").
        r = requests.post(f"{BASE}/config/values/clear", headers=h, timeout=30, json=item)
    else:
        r = requests.put(f"{BASE}/config/values", headers=h, timeout=30, json={"items": [{**item, "value": nilai}]})
    assert r.status_code == 200, r.text


def test_indeks_wajib_terpasang():
    i = DB.interco_charges.index_information()
    a = i.get("uq_charge_run_to")
    assert a and a.get("unique"), a
    assert [k for k, _ in a["key"]] == ["source.run_id", "to_entity_id"]
    assert DB.hr_pay_inputs.index_information().get("uq_source_key", {}).get("unique"), "uq_source_key"


def test_U16_dua_pengesahan_bersamaan():
    mgr = _login("manager@kainnusantara.id")
    adm = _login("admin@kainnusantara.id")
    sales = DB.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0, "id": 1})
    assert sales, "akun sales@ data acuan tidak ada"
    assert DB.hr_employees.find_one({"user_id": sales["id"], "status": "active"}), "sales@ belum tertaut karyawan"
    komp = _komponen(adm)
    lembar = []
    _mode(adm, "sheet")
    try:
        for putaran in range(3):
            baris = {"sales_id": sales["id"], "component_id": komp["id"], "basis_period_type": "month",
                     "basis_period": f"2099-{putaran + 1:02d}"}
            r = requests.post(f"{BASE}/incentive/sheets", headers=mgr, timeout=60,
                              json={"pay_period": "2099-04", "lines": [baris]})
            assert r.status_code == 200, r.text
            s = r.json()
            lembar.append(s["id"])
            r = requests.patch(f"{BASE}/incentive/sheets/{s['id']}/lines/{s['lines'][0]['id']}", headers=mgr,
                               timeout=60, json={"amount": 1_000_000})
            assert r.status_code == 200, r.text
            assert requests.post(f"{BASE}/incentive/sheets/{s['id']}/submit", headers=mgr, timeout=60).status_code == 200
            hasil = _bersamaan(lambda i, sid=s["id"]: requests.post(
                f"{BASE}/incentive/sheets/{sid}/approve", headers=adm if i else mgr, timeout=60, json={}))
            assert sorted(r.status_code for r in hasil) == [200, 409], (putaran, [r.text for r in hasil])
            doc = DB.incentive_sheets.find_one({"id": s["id"]})
            assert (doc["status"], doc["payroll_linked"], doc["gl_status"]) == ("approved", True, "posted"), doc
            assert DB.journal_entries.count_documents({"source_type": "incentive_sheet", "source_id": s["id"],
                                                       "status": {"$ne": "void"}}) == 1
            assert DB.hr_pay_inputs.count_documents({"source_type": "incentive_sheet",
                                                     "source_ref.sheet_id": s["id"]}) == 1
    finally:
        _mode(adm, None)
        DB.hr_pay_inputs.delete_many({"source_type": "incentive_sheet", "source_ref.sheet_id": {"$in": lembar}})
        DB.journal_entries.delete_many({"source_type": "incentive_sheet", "source_id": {"$in": lembar}})
        DB.incentive_sheets.delete_many({"entity_id": ENT, "pay_period": {"$regex": "^2099-"}})
        DB.incentive_components.delete_many({"entity_id": ENT, "code": "KMT4UJI"})
