"""PREP-D1 — gate U300 V2: kebijakan alarm (K-RFID-09), sesi dokumen bertahap (K-RFID-10), klaim tanpa bocor,
lintasan kosong/mundur, luapan, protokol per perangkat, auto-cocok, alert kesehatan, parameter gate berversi,
simulator tiap skenario, kontrak 2.1. HTTP nyata (device key + sesi pengguna + izin) ke backend yang berjalan.

Data uji sendiri bertanda TEST_D1_<tag> (gudang, perangkat, SO/SJ, roll, tag, MKO, perbaikan) — dibersihkan di akhir.
Jalankan TERPISAH dari test_iter117/118 (motor loop):
  cd /app/backend && python -m pytest -q -p no:cacheprovider -n0 tests/test_prep_d1_gate_v2.py
"""
import copy
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import rfid_v2_envelope as env  # noqa: E402
from services import rfid_v2_ingest as ingest  # noqa: E402
from services import rfid_v2_sessions as sessions  # noqa: E402
from services.rfid_ingest_service import hash_device_key  # noqa: E402

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
WH = f"wh_TEST_D1_{TAG}"
ENT = "ent_ksc"
FIXTURE = json.loads((Path(__file__).parent / "fixtures/u300_contract.json").read_text())["DeviceConfig"]
V2 = f"{BASE}/api/rfid/v2"
_N = {"n": 0}
DEVICES = []


def _nx():
    _N["n"] += 1
    return _N["n"]


def _login(email):
    for pw in ("demo12345", "demo1234"):
        r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
        if r.status_code == 200:
            return {"Authorization": "Bearer " + r.json()["token"]}
    pytest.skip(f"login {email} gagal")


@pytest.fixture(scope="module", autouse=True)
def seed():
    try:
        requests.get(f"{BASE}/api/health", timeout=10)
    except requests.RequestException:
        pytest.skip("backend tidak berjalan")
    DB.warehouses.insert_one({"id": WH, "name": f"Gudang Uji D1 {TAG}", "code": f"D1{TAG[:4]}", "roles": ["storage"],
                              "sharing_mode": "shared", "active": True})
    yield
    devs = [d["id"] for d in DEVICES]
    pids = [p["_id"] for p in DB.rfid_v2_passages.find({"device_id": {"$in": devs}}, {"_id": 1})]
    for name in ("rfid_v2_events", "rfid_v2_summaries", "rfid_v2_edges", "rfid_v2_overflow", "rfid_v2_crossings"):
        DB[name].delete_many({"passage": {"$in": pids}})
    DB.rfid_v2_crossings.delete_many({"device_id": {"$in": devs}})
    for name in ("rfid_v2_passages", "rfid_v2_bindings", "rfid_v2_gate_latches", "rfid_v2_health", "rfid_v2_configs"):
        DB[name].delete_many({"device_id": {"$in": devs}})
    DB.rfid_v2_doc_sessions.delete_many({"warehouse_id": WH})
    DB.rfid_v2_event_ids.delete_many({"passage": {"$in": pids}})
    DB.notifications.delete_many({"ref": {"$regex": f"TEST_D1_{TAG}"}})
    for coll in ("inventory_rolls", "shipments", "repair_orders"):
        DB[coll].delete_many({"warehouse_id": WH})
    DB.rfid_tags.delete_many({"epc": {"$regex": f"^E2D1{TAG.upper()}"}})
    DB.sales_orders.delete_many({"id": {"$regex": f"^so_TEST_D1_{TAG}"}})
    DB.makloon_orders.delete_many({"id": {"$regex": f"^mko_TEST_D1_{TAG}"}})
    for name in ("rfid_reads", "rfid_passages", "rfid_observations", "rfid_incidents"):
        DB[name].delete_many({"device_id": {"$in": devs}})
    DB.rfid_devices.delete_many({"id": {"$in": devs}})
    DB.warehouses.delete_one({"id": WH})


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id")


@pytest.fixture(scope="module")
def whadmin():
    return _login("wh.admin@kainnusantara.id")


def _epc():
    return f"E2D1{TAG.upper()}{_nx():012X}"


def make_device(admin, direction="out", publish=True, enabled=True):
    n = _nx()
    key = f"dk_TEST_D1_{TAG}_{n}"
    dev = {"id": f"dev_TEST_D1_{TAG}_{n}", "code": f"D1-{TAG}-{n}", "name": f"Gate Uji D1 {n}", "type": "gate",
           "direction": direction, "warehouse_id": WH, "enabled": enabled, "status": "offline",
           "api_key_hash": hash_device_key(key)}
    DB.rfid_devices.insert_one(dict(dev))
    dev["key"] = key
    DEVICES.append(dev)
    if publish:
        publish_config(admin, dev, "d1-v1")
    return dev


def publish_config(admin, dev, version, params=None):
    cfg = copy.deepcopy(FIXTURE)
    cfg.update(device_id=dev["id"], warehouse_id=WH, site_id="site-d1", config_version=version)
    g = cfg["logical_gates"][0]
    g.update(logical_gate_id="G1", warehouse_id=WH, site_id="site-d1", direction=dev["direction"],
             antenna_ids=["1", "2", "3"], completion_basis="document_session")
    if params is not None:
        g["passage_parameters"] = params
    r = requests.put(f"{V2}/ops/devices/{dev['id']}/config", headers=admin, json=cfg, timeout=30)
    assert r.status_code == 200, r.text


def roll(status="available", **extra):
    rid, epc = f"roll_TEST_D1_{TAG}_{_nx()}", _epc()
    DB.inventory_rolls.insert_one({"id": rid, "roll_no": rid[-8:], "warehouse_id": WH, "status": status,
                                   "owner_entity_id": ENT, **extra})
    DB.rfid_tags.insert_one({"id": f"tag_{rid}", "epc": epc, "roll_id": rid, "status": "active"})
    return rid, epc


def shipment(n):
    so, sid = f"so_TEST_D1_{TAG}_{_nx()}", f"shp_TEST_D1_{TAG}_{_nx()}"
    DB.sales_orders.insert_one({"id": so, "number": so, "status": "in_progress", "entity_id": ENT})
    rolls = [roll("in_transit_sales", reserved_ref={"type": "sales_order", "id": so}) for _ in range(n)]
    DB.shipments.insert_one({"id": sid, "shipment_no": f"SJ-D1-{_nx()}", "order_id": so, "warehouse_id": WH,
                             "status": "dispatched", "entity_id": ENT, "created_at": datetime.now(timezone.utc).isoformat(),
                             "rolls": [{"roll_id": r} for r, _ in rolls]})
    return sid, [r for r, _ in rolls], [e for _, e in rolls]


def device_cfg(dev):
    r = requests.get(f"{V2}/device/config", headers={"X-Device-Key": dev["key"]}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def build(dev, scenario, doc=(), extra=(), background=()):
    cfg = device_cfg(dev)
    g = cfg["logical_gates"][0]
    return env.build_passage(scenario=scenario, gate_id=g["logical_gate_id"], config_version=cfg["config_version"],
                             hardware_profile_id=cfg["hardware_profile_id"], direction=g["direction"],
                             antennas=g["antenna_ids"], doc_epcs=doc, extra_strong=extra, background_epcs=background)


def send(dev, built, close_patch=None):
    for body in built["batches"]:
        r = requests.post(f"{V2}/events", headers={"X-Device-Key": dev["key"]}, json=body, timeout=30)
        assert r.status_code == 200, r.text
    close = {**built["close"], **(close_patch or {})}
    r = requests.post(f"{V2}/passages/{built['passage_id']}/close", json=close, timeout=60,
                      headers={"X-Device-Key": dev["key"], "Idempotency-Key": "c-" + built["passage_id"]})
    assert r.status_code == 200, r.text
    return r.json()


def gate_state(dev):
    r = requests.get(f"{V2}/device/gate-state", headers={"X-Device-Key": dev["key"]}, params={"logical_gate_id": "G1"})
    assert r.status_code == 200, r.text
    return r.json()


def session_of(admin, sid, direction="out"):
    r = requests.get(f"{V2}/ops/doc-sessions/shipment/{sid}", headers=admin, params={"direction": direction})
    assert r.status_code == 200, r.text
    return r.json()


# ── 1. galat terstruktur & izin (AUD-MW-06) ────────────────────────────────────────────────
def test_structured_device_errors(admin):
    assert requests.get(f"{V2}/device/config").json()["detail"]["code"] == "AUTH_REQUIRED"
    assert requests.get(f"{V2}/device/config", headers={"X-Device-Key": "x"}).json()["detail"]["code"] == "AUTH_INVALID"
    off = make_device(admin, publish=False, enabled=False)
    r = requests.get(f"{V2}/device/config", headers={"X-Device-Key": off["key"]})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "ADMIN_DISABLED" and r.json()["detail"]["retryable"]
    fresh = make_device(admin, publish=False)
    r = requests.get(f"{V2}/device/config", headers={"X-Device-Key": fresh["key"]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "CONFIG_REQUIRED" and r.json()["detail"]["retryable"]


def test_ops_require_user_session_and_permission(admin, whadmin):
    dev = make_device(admin)
    assert requests.get(f"{V2}/ops/devices/{dev['id']}", headers={"X-Device-Key": dev["key"]}).status_code == 401
    assert requests.get(f"{V2}/ops/devices/{dev['id']}", headers=whadmin).status_code == 200
    for path, body in (("simulate", {"scenario": "empty"}), ("gate-parameters", {"parameters": {}})):
        assert requests.post(f"{V2}/ops/devices/{dev['id']}/{path}", headers=whadmin, json=body).status_code == 403
    assert requests.put(f"{V2}/ops/devices/{dev['id']}/protocol", headers=whadmin, json={"protocol": "legacy"}).status_code == 403


# ── 2. hijau auto-cocok + sesi dokumen bertahap (K-RFID-10, AUD-MW-15) ─────────────────────
def test_full_load_green_auto_match(admin):
    dev = make_device(admin)
    sid, _, epcs = shipment(3)
    d = send(dev, build(dev, "full_load", epcs))
    assert d["verdict"] == "GREEN" and d["binding_mode"] == "auto" and d["indicator"] == "GREEN"
    assert d["counts"]["matched"] == 3 and d["counts"]["pending"] == 0 and not d["latched"]
    assert d["reason_codes"][0] == "MANIFEST_MATCH" and d["sources"][0]["source_id"] == sid


def test_partial_trips_and_session_status(admin):
    dev = make_device(admin)
    sid, rolls, epcs = shipment(4)
    d1 = send(dev, build(dev, "partial_trip", epcs[:2]))
    assert d1["verdict"] == "GREEN" and d1["counts"]["pending"] == 2 and d1["allow_live_signal"]
    st = session_of(admin, sid)
    assert (st["passed"], st["remaining"], st["status"]) == (2, 2, "open")
    assert {r["roll_id"] for r in st["rolls"] if r["passed"]} == set(rolls[:2])
    assert all(r["local_passage_id"] == d1["local_passage_id"] for r in st["rolls"] if r["passed"])
    d2 = send(dev, build(dev, "partial_trip", epcs[2:]))
    assert d2["verdict"] == "GREEN" and d2["counts"]["pending"] == 0
    assert session_of(admin, sid)["status"] == "complete"


def test_close_session_rolls_missing_is_review(admin, whadmin):
    dev = make_device(admin)
    sid, _, epcs = shipment(3)
    send(dev, build(dev, "partial_trip", epcs[:2]))
    url = f"{V2}/ops/doc-sessions/shipment/{sid}/close"
    r = requests.post(url, headers=whadmin, json={"direction": "out", "note": "dokumen dikirim"})
    assert r.status_code == 200, r.text
    close = r.json()["close"]
    assert close["verdict"] == "REVIEW" and close["reason_codes"] == ["ROLLS_MISSING"] and close["missing_count"] == 1
    again = requests.post(url, headers=whadmin, json={"direction": "out"}).json()["close"]
    assert again["at"] == close["at"]          # idempoten, tidak menimpa


# ── 3. lintasan kosong / mundur (AUD-MW-02 sisi server) ───────────────────────────────────
def test_empty_and_reversed_passages(admin):
    dev = make_device(admin)
    sid, _, epcs = shipment(2)
    for scenario, doc in (("empty", []), ("reversed", epcs)):
        d = send(dev, build(dev, scenario, doc))
        assert d["verdict"] == "CANCELLED" and not d["latched"] and d["indicator"] == "OFF", (scenario, d["reason_codes"])
    d = send(dev, build(dev, "reversed_with_rolls", epcs))
    assert d["verdict"] == "REVIEW" and "REVERSED_WITH_ROLLS" in d["reason_codes"] and not d["latched"]
    assert session_of(admin, sid)["passed"] == 0 and not gate_state(dev)["latched"]   # mundur = tidak diklaim lewat
    zero = send(dev, {"passage_id": f"zero-{TAG}", "batches": [], "close": {
        **build(dev, "empty")["close"], "observed_edge_count": 0, "observed_summary_count": 0}})
    assert zero["verdict"] == "CANCELLED"     # 0 bukti sama sekali (pola agent 0.4) tanpa alarm


# ── 4. satu kunci per gate + reason_codes (K-RFID-09 / AUD-MW-03) ──────────────────────────
def test_red_single_latch_per_gate(admin, whadmin):
    dev = make_device(admin)
    _, _, a = shipment(2)
    _, foreign = roll("available")
    red = send(dev, build(dev, "foreign_roll", a, extra=[foreign]))
    assert red["verdict"] == "RED" and red["latched"] and "NO_DOCUMENT" in red["reason_codes"] and red["latch_id"]
    st = gate_state(dev)
    assert st["latched"] and st["latch_id"] == red["latch_id"]
    _, _, b = shipment(2)
    green = send(dev, build(dev, "full_load", b))
    assert green["verdict"] == "GREEN" and "GATE_LATCHED" not in green["reason_codes"]   # tidak dipaksa terkunci
    _, q = roll("quarantine")
    red2 = send(dev, build(dev, "quarantine_roll", [], extra=[q]))
    assert red2["verdict"] == "RED" and red2["latch_id"] == red["latch_id"]          # kunci yang sama, bukan berantai
    st = gate_state(dev)
    assert st["latch_passage_count"] == 2 and "QUARANTINE" in st["latch_reason_codes"]
    ack = {"device_id": dev["id"], "note": "sudah dicek fisik", "latch_id": st["latch_id"]}
    assert requests.post(f"{V2}/ops/devices/{dev['id']}/gate-latch/acknowledge", headers={"X-Device-Key": dev["key"]},
                         json=ack).status_code == 401
    r = requests.post(f"{V2}/ops/devices/{dev['id']}/gate-latch/acknowledge", headers=whadmin, json=ack)
    assert r.status_code == 200 and r.json()["latch_released"] and not r.json()["latched"], r.text
    assert not gate_state(dev)["latched"]
    stale = requests.post(f"{V2}/ops/devices/{dev['id']}/gate-latch/acknowledge", headers=whadmin, json=ack)
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "STALE_ACKNOWLEDGE"
    row = DB.rfid_v2_passages.find_one({"device_id": dev["id"], "local_passage_id": red["local_passage_id"]})
    assert row["decision"]["verdict"] == "RED"                                          # verdict tidak berubah


def test_reason_codes_keep_violation_and_review(admin):
    dev = make_device(admin)
    _, q = roll("quarantine")
    late = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    d = send(dev, build(dev, "quarantine_roll", [], extra=[q]), close_patch={"closing_captured_at": late})
    assert d["verdict"] == "RED" and d["reason_code"] == "QUARANTINE"
    assert {"QUARANTINE", "TIME_UNVERIFIED"} <= set(d["reason_codes"])
    assert d["reason_codes"].index("QUARANTINE") < d["reason_codes"].index("TIME_UNVERIFIED")
    levels = {i["code"]: i["level"] for i in d["reasons"]}
    assert levels["QUARANTINE"] == "RED" and levels["TIME_UNVERIFIED"] == "REVIEW"


def test_review_only_does_not_latch(admin):
    dev = make_device(admin)
    _, _, epcs = shipment(2)
    d = send(dev, build(dev, "full_load", epcs), close_patch={"capture_complete": False})
    assert d["verdict"] == "REVIEW" and not d["latched"] and d["indicator"] == "YELLOW"
    assert not gate_state(dev)["latched"]


# ── 5. klaim crossing tidak bocor (AUD-MW-08) ─────────────────────────────────────────────
def test_claims_do_not_leak_on_conflict(admin):
    dev = make_device(admin)
    sid, rolls, epcs = shipment(2)
    assert send(dev, build(dev, "partial_trip", epcs[:1]))["verdict"] == "GREEN"
    both = send(dev, build(dev, "full_load", epcs))
    assert both["verdict"] == "RED" and "REPLAY_EXIT" in both["reason_codes"]
    assert session_of(admin, sid)["passed"] == 1              # roll kedua TIDAK ikut terklaim oleh lintasan merah
    assert send(dev, build(dev, "partial_trip", epcs[1:]))["verdict"] == "GREEN"
    ref = {"source_type": "shipment", "source_id": f"race-{TAG}"}
    DB.rfid_v2_crossings.insert_one({"_id": sessions.claim_id("shipment", ref["source_id"], "out", "rA"),
                                     "passage": "lain", "roll_id": "rA", "device_id": dev["id"]})
    ok, conflicts = run(sessions.insert_claims("mine", "out", [("rA", ref), ("rB", ref)], {"device_id": dev["id"]}))
    assert not ok and conflicts == ["rA"]
    assert not DB.rfid_v2_crossings.find_one({"_id": sessions.claim_id("shipment", ref["source_id"], "out", "rB")})


# ── 6. luapan → ACK quarantined durable + REVIEW (AUD-MW-01c) ────────────────────────────
def test_overflow_quarantined_ack_and_review(admin):
    dev = make_device(admin)
    _, _, epcs = shipment(2)
    built = build(dev, "overflow", epcs)
    device = DB.rfid_devices.find_one({"id": dev["id"]}, {"_id": 0})
    acks = run(ingest.events(device, built["batches"][0], capacity_override={"summary": 1}))
    sums = acks["summary_acks"]
    assert all(a["durable"] for a in sums) and {a["status"] for a in sums} == {"quarantined"}
    assert sums[0]["error"]["code"] == "CAPTURE_OVERFLOW"
    r = requests.post(f"{V2}/passages/{built['passage_id']}/close", json=built["close"],
                      headers={"X-Device-Key": dev["key"], "Idempotency-Key": "c-" + built["passage_id"]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["verdict"] == "REVIEW" and "CAPTURE_OVERFLOW" in d["reason_codes"] and not d["latched"]
    assert d["counts"]["overflow"] == len(sums)


# ── 7. protokol per perangkat (AUD-MW-09) ─────────────────────────────────────────────────
def test_protocol_flag_closes_legacy_ingest(admin):
    dev = make_device(admin)
    _, epc = roll("available")
    r = requests.post(f"{BASE}/api/rfid/ingest", headers={"X-Device-Key": dev["key"]}, json={"epcs": [epc]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "PROTOCOL_V2_DEVICE"
    legacy = make_device(admin, publish=False)
    assert requests.post(f"{BASE}/api/rfid/ingest", headers={"X-Device-Key": legacy["key"]}, json={"epcs": [epc]}).status_code == 200
    assert requests.put(f"{V2}/ops/devices/{dev['id']}/protocol", headers=admin, json={"protocol": "legacy"}).status_code == 200
    assert requests.post(f"{BASE}/api/rfid/ingest", headers={"X-Device-Key": dev["key"]}, json={"epcs": [epc]}).status_code == 200
    assert requests.put(f"{V2}/ops/devices/{dev['id']}/protocol", headers=admin, json={"protocol": "v2"}).status_code == 200
    assert DB.rfid_devices.find_one({"id": dev["id"]})["protocol"] == "v2"


# ── 8. parameter gate berversi + auto-cocok bisa dimatikan + binding manual ──────────────
def test_gate_parameters_auto_match_and_manual_binding(admin, whadmin):
    dev = make_device(admin)
    url = f"{V2}/ops/devices/{dev['id']}/gate-parameters"
    bad = requests.post(url, headers=admin, json={"config_version": "d1-bad", "parameters": {"tail_ms": -1}})
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "INVALID_GATE_PARAMETERS"
    assert requests.post(url, headers=admin, json={"config_version": "d1-v2", "parameters": {"auto_match": False}}).status_code == 200
    ov = requests.get(f"{V2}/ops/devices/{dev['id']}", headers=whadmin).json()
    assert ov["config_version"] == "d1-v2" and ov["gate_parameters"]["auto_match"] is False
    assert ov["gate_parameters"]["note"].startswith("titik awal kalibrasi")
    sid, _, epcs = shipment(2)
    d = send(dev, build(dev, "full_load", epcs))
    assert d["verdict"] == "REVIEW" and "NO_MANIFEST" in d["reason_codes"] and session_of(admin, sid)["passed"] == 0
    r = requests.post(f"{V2}/ops/devices/{dev['id']}/manifest", headers=whadmin, json={
        "logical_gate_id": "G1", "direction": "out", "sources": [{"source_type": "shipment", "source_id": sid}]})
    assert r.status_code == 200, r.text
    time.sleep(6.5)   # bacaan contoh envelope mundur 6 dtk; binding harus lebih dulu dari bacaan (MANIFEST_BOUND_AFTER_CAPTURE)
    d = send(dev, build(dev, "full_load", epcs))
    assert d["verdict"] == "GREEN" and d["binding_mode"] == "manual", d["reason_codes"]
    rel = requests.delete(f"{V2}/ops/devices/{dev['id']}/manifest", headers=whadmin, params={"logical_gate_id": "G1"})
    assert rel.status_code == 200 and rel.json()["released"]
    assert requests.post(url, headers=admin, json={"config_version": "d1-v3", "parameters": {"rssi_default_strong_dbm": -40}}).status_code == 200
    _, _, weak = shipment(1)
    d = send(dev, build(dev, "full_load", weak))
    assert d["verdict"] == "CANCELLED" and d["counts"]["weak"] == 1     # −48 dBm kini lemah → diabaikan, tanpa alarm


# ── 9. sumber P18: Perbaikan & Order Makloon (auto-cocok) ─────────────────────────────────
def test_repair_and_makloon_sources(admin):
    dev = make_device(admin)
    ro = f"ro_TEST_D1_{TAG}_{_nx()}"
    rolls = [roll("wip", repair_open=ro) for _ in range(2)]
    DB.repair_orders.insert_one({"id": ro, "number": f"RPR-D1-{_nx()}", "status": "sent", "entity_id": ENT,
                                 "warehouse_id": WH, "lines": [{"roll_id": r, "warehouse_id": WH} for r, _ in rolls]})
    d = send(dev, build(dev, "full_load", [e for _, e in rolls]))
    assert d["verdict"] == "GREEN" and d["sources"][0]["source_type"] == "repair_order", d["reason_codes"]
    mko = f"mko_TEST_D1_{TAG}_{_nx()}"
    issue = f"{mko}:1"
    br = {"type": "subcon", "id": issue, "mko_id": mko, "step": 1}
    mrolls = [roll("subcon", bucket_ref=br) for _ in range(2)]
    DB.makloon_orders.insert_one({"id": mko, "mko_number": f"MKO-D1-{_nx()}", "status": "in_progress", "entity_id": ENT,
                                  "steps": [{"seq": 1, "issue_ref": issue, "status": "issued", "from_warehouse_id": WH}]})
    d = send(dev, build(dev, "full_load", [e for _, e in mrolls]))
    assert d["verdict"] == "GREEN" and d["sources"][0]["source_type"] == "makloon_order", d["reason_codes"]
    assert d["sources"][0]["doc_id"] == mko


# ── 10. alert kesehatan reader (AUD-MW-17) ────────────────────────────────────────────────
def test_health_alert_on_reader_stopped(admin, whadmin):
    dev = make_device(admin)
    tel = {"event_id": uuid.uuid4().hex, "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
           "config_version": "d1-v1", "app_build": "test", "sdk_version": "20251103", "radio_state": "stopped",
           "printer_state": "not_applicable", "erp_transport": "online", "pending_event_count": 5000,
           "pending_bytes": 1, "oldest_pending_at": None, "free_storage_bytes": 1, "uptime_seconds": 1,
           "time_quality": "synced", "last_error": None}
    assert requests.post(f"{V2}/device/telemetry", headers={"X-Device-Key": dev["key"]}, json=tel).status_code == 200
    notes = list(DB.notifications.find({"type": "rfid_reader_health", "ref": {"$regex": dev["id"]}}))
    assert any("READER_STOPPED" in n["ref"] for n in notes) and any("QUEUE_RISING" in n["ref"] for n in notes)
    assert all(n["recipient_role"] in ("warehouse_admin", "manager") for n in notes)
    rules = {r["rule"]: r for r in requests.get(f"{V2}/ops/devices/{dev['id']}/health", headers=whadmin).json()["rules"]}
    assert rules["READER_STOPPED"]["active"] and not rules["TELEMETRY_STALE"]["active"]
    tel.update(event_id=uuid.uuid4().hex, radio_state="ready", pending_event_count=0)
    requests.post(f"{V2}/device/telemetry", headers={"X-Device-Key": dev["key"]}, json=tel)
    old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    DB.rfid_devices.update_one({"id": dev["id"]}, {"$set": {"v2_telemetry_at": old}})
    rules = {r["rule"]: r for r in requests.get(f"{V2}/ops/devices/{dev['id']}/health", headers=whadmin).json()["rules"]}
    assert not rules["READER_STOPPED"]["active"] and rules["TELEMETRY_STALE"]["active"]


# ── 11. simulator lintasan tiap skenario (endpoint admin) ─────────────────────────────────
def test_simulator_every_scenario(admin):
    dev = make_device(admin)
    for _ in range(9):
        shipment(4)
    roll("available")
    roll("quarantine")
    for scenario in env.SCENARIOS:
        r = requests.post(f"{V2}/ops/devices/{dev['id']}/simulate", headers=admin, json={"scenario": scenario}, timeout=120)
        assert r.status_code == 200, (scenario, r.text)
        res = r.json()
        verdicts = [p["decision"]["verdict"] for p in res["passages"]]
        assert res["as_expected"], (scenario, verdicts, [p["decision"]["reason_codes"] for p in res["passages"]])
        assert all(p["decision"]["simulated"] and p["local_passage_id"].startswith("sim-") for p in res["passages"])
    assert requests.post(f"{V2}/ops/devices/{dev['id']}/simulate", headers=admin, json={"scenario": "x"}).status_code == 400


# ── 12. kontrak 2.1 ────────────────────────────────────────────────────────────────────────
def test_contract_21_identical_and_valid():
    root = Path(__file__).resolve().parents[2]
    a = (root / "backend/contracts/rfid_v2.json").read_bytes()
    b = (root / "middleware/u300-agent/contracts/OPENAPI_RFID_V2.json").read_bytes()
    assert a == b and json.loads(a)["info"]["version"] == "2.1.0"
    from services import rfid_v2_core as core
    built = env.build_passage(scenario="full_load", gate_id="G", config_version="v", hardware_profile_id="h",
                              direction="out", antennas=["1"], doc_epcs=["E2" + "A" * 22])
    core.validate("EventsRequest", built["batches"][0])
    core.validate("PassageClose", built["close"])
    spec = json.loads(a)
    for path in ("/api/rfid/v2/ops/devices/{device_id}", "/api/rfid/v2/ops/doc-sessions/{source_type}/{source_id}",
                 "/api/rfid/v2/ops/devices/{device_id}/simulate"):
        assert path in spec["paths"]
    assert spec["components"]["schemas"]["GateAcknowledge"]["required"] == ["device_id", "note"]
    assert "CANCELLED" in spec["components"]["schemas"]["GateDecision"]["properties"]["verdict"]["enum"]


def test_decision_matches_contract(admin):
    dev = make_device(admin)
    _, _, epcs = shipment(1)
    d = send(dev, build(dev, "full_load", epcs))
    from services import rfid_v2_core as core
    core.validate("GateDecision", d)
    st = gate_state(dev)
    core.validate("GateState", st)
