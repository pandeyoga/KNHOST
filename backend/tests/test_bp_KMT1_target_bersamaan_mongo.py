"""KM-T1 U17 — di MongoDB ASLI (lingkungan A): dua `PUT /api/incentive/targets` bersamaan dengan kunci sama (PT, sales,
jenis periode, periode) → keduanya 200 dan tepat SATU dokumen target (indeks unik wajib `uq_target_pt_sales_periode`;
yang kalah balapan mengulang sebagai pembaruan, `services/incentive_targets.save_target`).

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`) di atas data acuan (`scripts/dev_restore_demo.sh`).
Backend harus sudah dinyalakan ulang sesudah KM-T1 (indeks wajib terpasang; rute `/api/incentive/*`). Target uji memakai
periode jauh (`2099-…`) dan dihapus di akhir. Tidak untuk database berisi data nyata.
"""
import os
import threading

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
    t = DB.sales_targets.index_information().get("uq_target_pt_sales_periode")
    assert t and t.get("unique"), t
    assert [k for k, _ in t["key"]] == ["entity_id", "sales_id", "period_type", "period"]
    c = DB.incentive_components.index_information().get("uq_component_code")
    assert c and c.get("unique"), c
    d = DB.incentive_definitions.index_information().get("uq_definition_version")
    assert d and d.get("unique"), d


def test_U17_dua_simpan_bersamaan_satu_dokumen():
    h = _login()
    sales = DB.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0, "id": 1})
    assert sales, "akun sales@ data acuan tidak ada"
    try:
        for putaran in range(5):   # ulangi supaya benturan benar-benar terjadi
            period = f"2099-{putaran + 1:02d}"
            hasil = []

            def _simpan(i, period=period):
                x = requests.put(f"{BASE}/incentive/targets", headers=h, timeout=60, json={
                    "sales_id": sales["id"], "period_type": "month", "period": period,
                    "target_sales_amount": 1_000_000 * (i + 1), "target_collection_amount": 500_000})
                hasil.append(x.status_code)

            ts = [threading.Thread(target=_simpan, args=(i,)) for i in range(2)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
            assert hasil == [200, 200], (putaran, hasil)
            n = DB.sales_targets.count_documents({"entity_id": ENT, "sales_id": sales["id"], "period_type": "month",
                                                  "period": period})
            assert n == 1, (putaran, n)
    finally:
        DB.sales_targets.delete_many({"entity_id": ENT, "sales_id": sales["id"], "period": {"$regex": "^2099-"}})
