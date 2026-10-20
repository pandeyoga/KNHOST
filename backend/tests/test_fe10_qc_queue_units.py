"""FE-10 (review 2026-10-20) — antrean QC kedatangan mengirim satuan SUMBER karantina (yard/kg) per tugas,
dengan rincian per satuan; kg dan yard tidak dijumlahkan, tidak ada konversi.

Fixture sementara (dibersihkan): 3 tugas inbound `qc_pending` + roll karantina yard / kg / campuran.
Jalankan: cd /app/backend && python -m pytest tests/test_fe10_qc_queue_units.py -p no:randomly -n 0 -q
"""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
TAG = uuid.uuid4().hex[:6]
CASES = {"yard": [("yard", 60.5), ("yard", 40)], "kg": [("kg", 22.25)], "mix": [("yard", 10), ("kg", 5)]}


@pytest.fixture(scope="module")
def tasks():
    wh = DB.warehouses.find_one({"entity_ids": ENT}, {"_id": 0, "id": 1})["id"]
    ids = {}
    for key, rolls in CASES.items():
        tid = f"tsk_TEST_FE10_{TAG}_{key}"
        ids[key] = tid
        DB.wms_tasks.insert_one({"id": tid, "flow_type": "inbound", "status": "qc_pending", "entity_id": ENT,
                                 "warehouse_id": wh, "unit": rolls[0][0], "product_name": f"TEST FE10 {key}",
                                 "updated_at": "2099-01-01T00:00:00", "created_at": "2099-01-01T00:00:00"})
        DB.inventory_rolls.insert_many([{"id": f"roll_TEST_FE10_{TAG}_{key}_{i}", "qc_task_id": tid, "status": "quarantine",
                                         "unit": u, "length_remaining": q, "owner_entity_id": ENT, "warehouse_id": wh}
                                        for i, (u, q) in enumerate(rolls)])
    yield ids
    DB.wms_tasks.delete_many({"id": {"$in": list(ids.values())}})
    DB.inventory_rolls.delete_many({"qc_task_id": {"$in": list(ids.values())}})


def test_satuan_sumber_per_tugas(tasks):
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
    h = {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}
    q = requests.get(f"{BASE}/inbound/qc/queue", headers=h)
    assert q.status_code == 200, q.text
    rows = {t["id"]: t for t in q.json() if t["id"] in tasks.values()}
    y, k, m = rows[tasks["yard"]], rows[tasks["kg"]], rows[tasks["mix"]]
    assert (y["quarantine_unit"], y["quarantine_qty"], y["quarantine_by_unit"]) == ("yard", 100.5, {"yard": 100.5})
    assert (k["quarantine_unit"], k["quarantine_by_unit"], k["quarantine_unit_mixed"]) == ("kg", {"kg": 22.25}, False)
    # campuran: dirinci per satuan, tidak ada satu satuan tunggal yang menyesatkan
    assert m["quarantine_unit"] == "" and m["quarantine_unit_mixed"] is True and m["quarantine_by_unit"] == {"yard": 10, "kg": 5}
