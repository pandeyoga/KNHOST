"""PREP-F — ujung-ke-ujung TANPA perangkat: ERP sungguhan (HTTP) ↔ connector PC gudang (`middleware/printer-connector`)
↔ simulator printer ZPL (TCP). Skenario RACC-22/24/25/26/27 sejauh bisa dibuktikan tanpa CP30EN fisik.

Simulator BUKAN bukti perilaku CP30EN — hanya membuktikan logika ERP + connector (ledger, start barrier, hasil per
label, pemulihan) terhadap printer yang berperilaku seperti bahasa ZPL Zebra.
  cd /app/backend && python -m pytest -q -p no:cacheprovider -n0 tests/test_prep_f_connector_e2e.py
"""
import hashlib
import os
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest
import requests
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
CONN = ROOT / "middleware" / "printer-connector"
if not CONN.exists():
    pytest.skip("middleware/printer-connector tidak ada", allow_module_level=True)
sys.path.insert(0, str(CONN))
sys.path.insert(0, str(CONN / "simulator"))
from kn_printer_connector.config import ConnectorConfig, PrinterConfig  # noqa: E402
from kn_printer_connector.erp import ErpClient, ErpUnavailable  # noqa: E402
from kn_printer_connector.worker import PrinterWorker  # noqa: E402
from zpl_printer_sim import SimPrinter  # noqa: E402

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
WH = f"wh_TEST_PFE_{TAG}"
DEVICES, STATE = [], {}
FAST = {"outcome_timeout_s": 3, "pause_wait_s": 6, "status_probe_timeout_s": 0.6, "poll_interval_s": 0.05,
        "telemetry_interval_s": 1, "renew_before_s": 30}


def _login(email):
    for pw in ("demo12345", "demo1234"):
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
        if r.status_code == 200:
            return r.json()["token"]
    pytest.skip(f"login {email} gagal")


@pytest.fixture(scope="module", autouse=True)
def seed():
    try:
        requests.get(f"{API}/health", timeout=10)
    except requests.RequestException:
        pytest.skip("backend tidak berjalan")
    STATE["product_id"] = DB.products.find_one({"sku": {"$exists": True}}, {"id": 1})["id"]
    STATE["ent"] = DB.inventory_rolls.find_one({"status": "available"}, {"owner_entity_id": 1})["owner_entity_id"]
    DB.warehouses.insert_one({"id": WH, "name": f"Gudang Uji PFE {TAG}", "code": f"PE{TAG[:5]}", "roles": ["storage"],
                              "sharing_mode": "shared", "active": True})
    STATE["h"] = {"Authorization": f"Bearer {_login('admin@kainnusantara.id')}", "X-Entity-Id": STATE["ent"]}
    yield
    rolls = [r["id"] for r in DB.inventory_rolls.find({"warehouse_id": WH}, {"id": 1})]
    jobs = [j["id"] for j in DB.rfid_print_jobs.find({"warehouse_id": WH}, {"id": 1})]
    DB.rfid_verify_sessions.delete_many({"print_job_id": {"$in": jobs}})
    DB.rfid_print_jobs.delete_many({"id": {"$in": jobs}})
    for c in ("rfid_tags", "rfid_tag_events", "roll_label_prints"):
        DB[c].delete_many({"roll_id": {"$in": rolls}})
    DB.inventory_rolls.delete_many({"id": {"$in": rolls}})
    DB.rfid_devices.delete_many({"id": {"$in": DEVICES}})
    DB.warehouses.delete_one({"id": WH})


@pytest.fixture
def sim():
    s = SimPrinter(print_delay_s=0.05).start()
    yield s
    s.release_hang()
    s.stop()


def printer_device():
    n = len(DEVICES) + 1
    key = f"dk_TEST_PFE_{TAG}_{n}"
    did = f"rdev_TEST_PFE_{TAG}_{n}"
    DB.rfid_devices.insert_one({"id": did, "code": f"PFE-{TAG}-{n}", "name": f"CP30EN sim {n}", "type": "printer",
                                "warehouse_id": WH, "enabled": True, "status": "offline",
                                "api_key_hash": hashlib.sha256(key.encode()).hexdigest()})
    DEVICES.append(did)
    return did, key


def create_job(n):
    rolls = []
    for _ in range(n):
        rid = f"roll_TEST_PFE_{TAG}_{uuid.uuid4().hex[:6]}"
        DB.inventory_rolls.insert_one({"id": rid, "roll_no": f"PE-{rid[-6:]}".upper(), "warehouse_id": WH,
                                       "status": "available", "owner_entity_id": STATE["ent"],
                                       "product_id": STATE["product_id"], "length_remaining": 30.0, "unit": "yard",
                                       "lot": "LOT-E2E", "grade": "A"})
        rolls.append(rid)
    r = requests.post(f"{API}/rfid/print-jobs", headers=STATE["h"], json={"roll_ids": rolls}, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


def worker(tmp_path, sim, key, name="P1", hooks=None, erp=None):
    pc = PrinterConfig(name=name, host="127.0.0.1", port=sim.port, device_key=key, connect_timeout_s=1, io_timeout_s=1)
    cc = ConnectorConfig(erp_url=API, data_dir=str(tmp_path), printers=[pc], http_timeout_s=30)
    w = PrinterWorker(pc, cc, hooks=hooks, erp=erp)
    w._load_config()
    w.policies.update(FAST)
    return w


def job_doc(job_id):
    return DB.rfid_print_jobs.find_one({"id": job_id}, {"_id": 0, "items.zpl": 0})


def drain(w, job_id, steps=250, final=("printed", "partial", "failed", "needs_review", "verified")):
    for _ in range(steps):
        try:
            w.step()
        except ErpUnavailable:
            time.sleep(0.05)
        j = job_doc(job_id)
        if j["status"] in final and not w.ledger.pending_results() and not w.ledger.active_job():
            return j
    raise AssertionError(f"job tidak tuntas: {job_doc(job_id)['status']} {job_doc(job_id).get('counts')}")


def clear_queue():
    DB.rfid_print_jobs.update_many({"warehouse_id": WH, "status": {"$in": ["queued", "printing"]}},
                                   {"$set": {"status": "failed"}, "$unset": {"lease": ""}})


def test_partial_batch_10_labels_end_to_end(tmp_path, sim):
    """RACC-25 — 7 terkonfirmasi, 2 gagal encode (VOID), 1 tidak pasti (printer macet) — hanya yang terbukti aktif."""
    clear_queue()
    did, key = printer_device()
    sim.set_fault(encode_fail={4, 7}, hang={10})
    job = create_job(10)
    w = worker(tmp_path, sim, key)
    j = drain(w, job["id"], steps=400)
    c = j["counts"]
    assert (c["confirmed"], c["failed"], c["unknown"]) == (7, 2, 1), c
    assert j["status"] == "needs_review" and j["review_open"] == 3
    st = [i["status"] for i in j["items"]]
    assert st[3] == st[6] == "failed" and st[9] == "unknown"
    active = {t["epc"] for t in DB.rfid_tags.find({"roll_id": {"$in": [i["roll_id"] for i in j["items"]]},
                                                   "status": "active"}, {"epc": 1})}
    assert active == {i["epc"] for i in j["items"] if i["status"] == "confirmed"}
    assert sim.received == 10                                  # tiap label dikirim tepat sekali
    assert set(sim.printed_epcs()) == active                    # chip yang tertulis = tag yang aktif
    ev = j["items"][0]["evidence"]
    assert ev["source"] == "printer_readback" and ev["readback_epc"] == j["items"][0]["epc"]
    dev = DB.rfid_devices.find_one({"id": did})
    assert dev["connector_health"]["instance_id"] == w.instance_id and dev["printer_health"]["state"]
    fu = requests.get(f"{API}/rfid/printers/follow-up", headers=STATE["h"], params={"warehouse_id": WH}, timeout=60).json()
    assert len([x for x in fu["items"] if x["job_id"] == job["id"]]) == 3
    w.close()


def test_crash_after_send_restart_reports_unknown_no_blind_reprint(tmp_path, sim):
    """RACC-26 — crash sesudah label ke-2 terkirim; connector hidup lagi → label ke-2 'tidak pasti', TIDAK dicetak ulang."""
    clear_queue()
    _, key = printer_device()
    job = create_job(3)
    n = {"sent": 0}

    class Crash(Exception):
        pass

    def after_sent(_j, _iid):
        n["sent"] += 1
        if n["sent"] == 2:
            raise Crash()

    w = worker(tmp_path, sim, key, hooks={"after_sent": after_sent})
    with pytest.raises(Crash):
        for _ in range(60):
            w.step()
    w.close()
    time.sleep(0.4)
    w2 = worker(tmp_path, sim, key)
    w2.ledger.recover_after_crash()
    j = drain(w2, job["id"])
    assert [i["status"] for i in j["items"]] == ["confirmed", "unknown", "confirmed"]
    assert j["items"][1]["evidence"]["source"] == "connector_recovery"
    assert sim.received == 3
    assert j["print_attempts"] == 1                              # attempt yang sama dipakai sesudah restart
    w2.close()


def test_lost_result_ack_retries_same_event_without_reprint(tmp_path, sim):
    clear_queue()
    _, key = printer_device()
    job = create_job(2)
    real = ErpClient(API, key, "inst-lost-ack", timeout_s=30)
    drops = {"n": 1}

    class LossyErp:
        def __getattr__(self, name):
            return getattr(real, name)

        def results(self, job_id, attempt_id, rows):
            out = real.results(job_id, attempt_id, rows)
            if drops["n"] > 0:
                drops["n"] -= 1
                raise ErpUnavailable("respons hilang")
            return out

    w = worker(tmp_path, sim, key, erp=LossyErp())
    j = drain(w, job["id"])
    assert [i["status"] for i in j["items"]] == ["confirmed", "confirmed"]
    full = DB.rfid_print_jobs.find_one({"id": job["id"]})
    assert all(len(i["results"]) == 1 for i in full["items"])
    assert sim.received == 2
    w.close()


def test_two_printers_same_warehouse_never_print_same_job(tmp_path, sim):
    """RACC-22 — dua connector/printer satu gudang menarik bersamaan: tiap job dicetak tepat satu printer, tiap EPC sekali."""
    clear_queue()
    sim2 = SimPrinter(print_delay_s=0.05).start()
    try:
        (_, k1), (_, k2) = printer_device(), printer_device()
        jobs = [create_job(2) for _ in range(4)]
        w1 = worker(tmp_path / "a", sim, k1, "PA")
        w2 = worker(tmp_path / "b", sim2, k2, "PB")
        stop = threading.Event()

        def loop(w):
            while not stop.is_set():
                try:
                    w.step()
                except ErpUnavailable:
                    pass
                time.sleep(0.02)

        ts = [threading.Thread(target=loop, args=(w,), daemon=True) for w in (w1, w2)]
        for t in ts:
            t.start()
        deadline = time.time() + 90
        while time.time() < deadline and not all(job_doc(j["id"])["status"] == "printed" for j in jobs):
            time.sleep(0.3)
        stop.set()
        for t in ts:
            t.join(10)
        assert all(job_doc(j["id"])["status"] == "printed" for j in jobs)
        all_epcs = [i["epc"] for j in jobs for i in j["items"]]
        printed = sim.printed_epcs() + sim2.printed_epcs()
        assert sorted(printed) == sorted(all_epcs)                 # tidak ada EPC tercetak dua kali
        assert all(job_doc(j["id"])["print_attempts"] == 1 for j in jobs)
        w1.close()
        w2.close()
    finally:
        sim2.stop()


def test_offline_erp_holds_then_resumes_and_verify_after_print(tmp_path, sim):
    """Internet putus: tidak ada label baru dimulai; hasil tertahan lalu terkirim. Sesudah cetak, verifikasi C72 (RACC-24)."""
    clear_queue()
    _, key = printer_device()
    job = create_job(3)
    real = ErpClient(API, key, "inst-offline", timeout_s=30)
    flag = {"down": False}

    class FlakyErp:
        def __getattr__(self, name):
            attr = getattr(real, name)

            def call(*a, **k):
                if flag["down"]:
                    raise ErpUnavailable("internet gudang putus (simulasi)")
                return attr(*a, **k)
            return call

    w = worker(tmp_path, sim, key, erp=FlakyErp())
    w.step()       # klaim
    w.step()       # label 1
    flag["down"] = True
    held = sim.received
    for _ in range(6):
        try:
            w.step()
        except ErpUnavailable:
            pass
    assert sim.received <= held + 1
    stuck = sim.received
    for _ in range(3):
        try:
            w.step()
        except ErpUnavailable:
            pass
    assert sim.received == stuck
    flag["down"] = False
    j = drain(w, job["id"])
    assert j["status"] == "printed" and sim.received == 3
    w.close()
    # tercetak ≠ terverifikasi: verifikasi handheld memakai EPC yang benar-benar tertulis di chip simulator
    s = requests.post(f"{API}/rfid/print-jobs/{job['id']}/verify/start", headers=STATE["h"], timeout=60).json()
    requests.post(f"{API}/rfid/verify-sessions/{s['id']}/scan", headers=STATE["h"], json={"epcs": sim.printed_epcs()},
                  timeout=60)
    c = requests.post(f"{API}/rfid/verify-sessions/{s['id']}/complete", headers=STATE["h"], timeout=60).json()
    assert c["result"] == "clean" and job_doc(job["id"])["status"] == "verified"
