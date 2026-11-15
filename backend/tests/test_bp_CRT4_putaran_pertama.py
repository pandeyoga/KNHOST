"""CR-T4 — di MongoDB ASLI (lingkungan A) dengan data acuan: putaran pertama job denda sesudah jadwal tagihan ikut dipindai.

RISIKO spesifikasi (`docs/blueprint/unit/CR-T4.md`): sesudah job memindai SEMUA jadwal hidup (`origin` `term` jadwal
tagihan CR-T2 maupun `manual`), jumlah nota draf bisa naik tajam pada putaran pertama. Berkas ini mengukurnya di data
acuan (`scripts/dev_restore_demo.sh`) dan mencetaknya untuk laporan (`-s`):

  1. hitung jadwal hidup per asal + nota draf sebelum;
  2. jalankan job lewat `POST /api/scheduler/jobs/penalty_accrual/run` (Admin);
  3. hitung nota draf sesudah, per asal jadwal; nota baru TIDAK berjurnal (INV-PEN-01);
  4. putaran kedua di hari yang sama tidak menambah nota (idempoten per baris per bulan).
Nota draf tanpa jurnal → aman; dipulihkan dengan `restore_demo`. Tidak untuk database berisi data nyata.
"""
import os

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _hitung():
    asal = {}
    for p in DB.payment_plans.find({"status": "active"}, {"_id": 0, "id": 1, "origin": 1}):
        o = p.get("origin") or "manual"
        a = asal.setdefault(o, {"jadwal": 0, "draf": 0})
        a["jadwal"] += 1
        a["draf"] += DB.penalties.count_documents({"plan_id": p["id"], "status": "draft"})
    return asal, DB.penalties.count_documents({"status": "draft"})


def test_CRT4_A_putaran_pertama_jumlah_nota_draf():
    h = _login()
    sebelum, draf_awal = _hitung()
    print(f"[CR-T4] sebelum: jadwal hidup per asal {sebelum}; nota draf seluruhnya {draf_awal}")
    r = requests.post(f"{BASE}/scheduler/jobs/penalty_accrual/run", headers=h, timeout=300)
    assert r.status_code == 200, r.text
    print(f"[CR-T4] hasil job: {r.json()}")
    sesudah, draf_akhir = _hitung()
    print(f"[CR-T4] sesudah: per asal {sesudah}; nota draf seluruhnya {draf_akhir} (+{draf_akhir - draf_awal})")
    baru = [p["id"] for p in DB.penalties.find({"status": "draft"}, {"_id": 0, "id": 1})]
    assert DB.journal_entries.count_documents({"source_type": "penalty", "source_id": {"$in": baru},
                                               "status": {"$ne": "void"}}) == 0   # INV-PEN-01
    r = requests.post(f"{BASE}/scheduler/jobs/penalty_accrual/run", headers=h, timeout=300)
    assert r.status_code == 200, r.text
    assert DB.penalties.count_documents({"status": "draft"}) == draf_akhir   # idempoten


def test_CRT4_A_aturan_denda_pelanggan_data_acuan():
    h = _login()
    c = DB.customers.find_one({"entity_id": "ent_ksc", "status": {"$ne": "merged"}}, {"_id": 0, "id": 1})
    assert c, "data acuan tidak punya pelanggan ent_ksc"
    r = requests.get(f"{BASE}/customers/{c['id']}/penalty-policy", headers=h, params={"entity_id": "ent_ksc"},
                     timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    print(f"[CR-T4] aturan denda {c['id']} @ ent_ksc: {j['effective']} asal {j['sources']}")
    assert set(j["effective"]) == {"mode", "rate_pct_per_month", "base", "cap_pct", "grace_days", "min_amount"}
    lapisan = DB.config_values.count_documents({"scope_type": "customer", "key": {"$in": [
        "payment.penalty_mode", "payment.penalty_base", "payment.penalty_cap_pct", "ar.denda_rate_pct_per_month",
        "ar.grace_days"]}})
    print(f"[CR-T4] baris lapisan pelanggan lima kunci denda (dipindah skrip migrate_penalty_customer_layer): {lapisan}")
