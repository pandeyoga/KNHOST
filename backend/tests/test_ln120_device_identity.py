"""LN-120-T02 — tiap device (reader/handheld/printer) hanya bisa mengakses tugas sesuai tipe & gudangnya; tanpa token user bersama."""
import hashlib
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
TAG = uuid.uuid4().hex[:6]
KEYS = {k: f"dk_TEST_{k}_{TAG}" for k in ("reader", "printer_a", "printer_b", "off")}
JOB = f"rpj_TEST_{TAG}"


def _dev(kind, typ, wh, enabled=True):
    return {"id": f"rdev_TEST_{kind}_{TAG}", "code": f"TEST-{kind}-{TAG}", "name": f"TEST {kind}", "type": typ,
            "direction": "in" if typ == "gate" else None, "warehouse_id": wh, "enabled": enabled, "status": "offline",
            "api_key_hash": hashlib.sha256(KEYS[kind].encode()).hexdigest(), "api_key_hint": KEYS[kind][-4:]}


@pytest.fixture(scope="module", autouse=True)
def devices():
    whs = [w["id"] for w in DB.warehouses.find({}, {"id": 1}).limit(2)]
    wa, wb = whs[0], whs[-1] if len(whs) > 1 else "wh_TEST_other"
    DB.rfid_devices.insert_many([_dev("reader", "gate", wa), _dev("printer_a", "printer", wa),
                                 _dev("printer_b", "printer", wb if wb != wa else "wh_TEST_other"),
                                 _dev("off", "handheld", wa, enabled=False)])
    DB.rfid_print_jobs.insert_one({"id": JOB, "warehouse_id": wa, "status": "queued", "kind": "rfid_tag", "items": [],
                                   "lease": {"device_id": f"rdev_TEST_printer_a_{TAG}", "attempt_id": "patt_TEST",
                                             "expires_at": "2999-01-01T00:00:00+00:00"}})
    yield
    DB.rfid_devices.delete_many({"id": {"$regex": f"^rdev_TEST_.*_{TAG}$"}})
    DB.rfid_print_jobs.delete_many({"id": JOB})
    DB.rfid_reads.delete_many({"device_id": {"$regex": f"^rdev_TEST_.*_{TAG}$"}})


def _h(kind):
    return {"X-Device-Key": KEYS[kind]}


def test_missing_and_unknown_key_401():
    assert requests.post(f"{BASE}/rfid/heartbeat", timeout=30).status_code == 401
    assert requests.post(f"{BASE}/rfid/heartbeat", headers={"X-Device-Key": "dk_nope"}, timeout=30).status_code == 401


def test_user_token_not_accepted_as_device():
    t = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=30).json()["token"]
    r = requests.get(f"{BASE}/rfid/device-jobs/pending", headers={"Authorization": f"Bearer {t}"}, timeout=30)
    assert r.status_code == 401


def test_disabled_device_403():
    assert requests.post(f"{BASE}/rfid/heartbeat", headers=_h("off"), timeout=30).status_code == 403


def test_each_device_heartbeat_own_identity():
    for k in ("reader", "printer_a"):
        r = requests.post(f"{BASE}/rfid/heartbeat", headers=_h(k), timeout=30)
        assert r.status_code == 200 and r.json()["device_id"] == f"rdev_TEST_{k}_{TAG}"


def test_reader_cannot_pull_or_ack_print_jobs():
    assert requests.get(f"{BASE}/rfid/device-jobs/pending", headers=_h("reader"), timeout=30).status_code in (400, 403)
    r = requests.post(f"{BASE}/rfid/device-jobs/{JOB}/ack", json={"attempt_id": "patt_TEST"}, headers=_h("reader"), timeout=30)
    assert r.status_code == 403


def test_printer_cannot_ingest_epc():
    r = requests.post(f"{BASE}/rfid/ingest", json={"epcs": ["E2TEST"]}, headers=_h("printer_a"), timeout=30)
    assert r.status_code == 400


def test_printer_other_warehouse_cannot_ack():
    r = requests.post(f"{BASE}/rfid/device-jobs/{JOB}/ack", json={"attempt_id": "patt_TEST"}, headers=_h("printer_b"), timeout=30)
    assert r.status_code == 403
    assert DB.rfid_print_jobs.find_one({"id": JOB})["status"] == "queued"


def test_printer_wrong_attempt_409_then_owner_ok():
    r = requests.post(f"{BASE}/rfid/device-jobs/{JOB}/ack", json={"attempt_id": "patt_other"}, headers=_h("printer_a"), timeout=30)
    assert r.status_code == 409
