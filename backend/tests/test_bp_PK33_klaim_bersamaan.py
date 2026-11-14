"""PK-33 U8 — di MongoDB ASLI (lingkungan A): dua permintaan BERSAMAAN ke endpoint yang diberi klaim oleh PK-33.

Harapan per endpoint golongan 4: tepat satu 200; yang lain 409 (`SAGA_IN_PROGRESS`/`STATE_CHANGED`, kalah klaim) atau
400 (datang sesudah yang pertama selesai: tidak ada lagi yang menunggu / tanggal bertabrakan); tidak ada dokumen turunan
ganda; tidak ada `saga_lock` tertinggal.

* `POST /api/sales-returns/{id}/roll-settlement/back-shipment` — hitungan: 2 roll `back_pending` → 1 surat jalan
  `return_back` berisi 2 roll; roll tidak lagi `back_pending`.
* `POST /api/hr/leave-requests` — hitungan: Senin–Selasa 2 hari kerja → 1 pengajuan; `pending` saldo tahun itu = 2.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); retur, roll, dan karyawan uji disisipkan
langsung ke database uji lokal (`MONGO_URL`/`DB_NAME`) sebagai FIXTURE, lalu dihapus. Tidak untuk data nyata.
"""
import datetime
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
PUTARAN = 3   # balapan tidak selalu muncul di satu percobaan


def _login():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _bersamaan(fn, n=2):
    with ThreadPoolExecutor(max_workers=n) as ex:
        return list(ex.map(fn, range(n)))


@pytest.fixture()
def bersih():
    made = {"ret": [], "roll": [], "emp": []}
    yield made
    DB.shipments.delete_many({"return_id": {"$in": made["ret"]}})
    DB.sales_returns.delete_many({"id": {"$in": made["ret"]}})
    DB.inventory_rolls.delete_many({"id": {"$in": made["roll"]}})
    DB.hr_leave_requests.delete_many({"employee_id": {"$in": made["emp"]}})
    DB.hr_leave_balances.delete_many({"employee_id": {"$in": made["emp"]}})
    DB.hr_employees.delete_many({"id": {"$in": made["emp"]}})


def test_PK33_U8_kirim_balik_bersamaan_satu_surat_jalan(bersih):
    h = _login()
    for i in range(PUTARAN):
        ret_id = f"sret_bp33_{TAG}_{i}"
        rolls = [f"roll_bp33_{TAG}_{i}_{k}" for k in range(2)]
        for r in rolls:
            DB.inventory_rolls.insert_one({"id": r, "roll_no": f"BP33-{TAG}-{i}-{r[-1]}", "unit": "yard",
                                           "product_id": "prod_bp33", "status": "returned", "owner_entity_id": "ent_ksc",
                                           "created_at": NOW})
        DB.sales_returns.insert_one({
            "id": ret_id, "number": f"RET-BP33-{TAG}-{i}", "entity_id": "ent_ksc", "order_id": f"so_bp33_{TAG}",
            "order_number": "SO-BP33", "customer_id": "cust_bp33", "customer_name": "Pelanggan Uji PK-33",
            "status": "inspected", "return_type": "cutloss", "created_at": NOW,
            "roll_outcomes": {r: {"outcome": "discount", "back_pending": True, "qty_back": 5.0} for r in rolls}})
        bersih["ret"].append(ret_id)
        bersih["roll"] += rolls

        def kirim(_):
            return requests.post(f"{BASE}/sales-returns/{ret_id}/roll-settlement/back-shipment", headers=h,
                                 json={"roll_ids": rolls}, timeout=60)

        hasil = _bersamaan(kirim)
        kode = sorted(r.status_code for r in hasil)
        assert kode.count(200) == 1, [(r.status_code, r.text[:200]) for r in hasil]
        assert all(k in (200, 400, 409) for k in kode), kode
        assert DB.shipments.count_documents({"return_id": ret_id}) == 1
        doc = DB.sales_returns.find_one({"id": ret_id})
        assert "saga_lock" not in doc, doc.get("saga_lock")
        assert all(doc["roll_outcomes"][r]["back_pending"] is False for r in rolls)


def test_PK33_U8_cuti_bersamaan_satu_pengajuan(bersih):
    h = _login()
    for i in range(PUTARAN):
        emp_id = f"emp_bp33_{TAG}_{i}"
        DB.hr_employees.insert_one({"id": emp_id, "name": f"Karyawan Uji BP33 {TAG} {i}", "entity_id": "ent_ksc",
                                    "status": "active", "created_at": NOW})
        bersih["emp"].append(emp_id)
        body = {"employee_id": emp_id, "leave_type": "cuti_tahunan", "date_from": "2027-03-01",
                "date_to": "2027-03-02", "reason": f"uji PK-33 U8 {TAG}"}

        def ajukan(_):
            return requests.post(f"{BASE}/hr/leave-requests", headers=h, json=body, timeout=60)

        hasil = _bersamaan(ajukan)
        kode = sorted(r.status_code for r in hasil)
        assert kode.count(200) == 1, [(r.status_code, r.text[:200]) for r in hasil]
        assert all(k in (200, 400, 409) for k in kode), kode
        assert DB.hr_leave_requests.count_documents({"employee_id": emp_id}) == 1
        bal = DB.hr_leave_balances.find_one({"employee_id": emp_id, "year": 2027})
        assert bal and int(bal["pending"]) == 2, bal
        assert "saga_lock" not in DB.hr_employees.find_one({"id": emp_id})
