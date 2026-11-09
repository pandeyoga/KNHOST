"""PREP-D2 — gate V2 → transaksi gudang + antrean periksa (K-GDG-02/03, K-RFID-09/10, K-OPN-03, AUD-MW-08/10).

Skenario tanpa perangkat (envelope simulator D1 lewat endpoint DEVICE sungguhan + sesi pengguna):
PA dari GRN (draf otomatis → terbit → kirim) → gate IN 2 trip → tiba bertahap → sisa handheld → PA selesai & sesi
GREEN · transfer ke gedung bergate diterima per trip · SJ keluar 2 trip → sesi ditutup saat berangkat → roll kurang
kuning → admin terima / tolak · area beku → kuning tanpa transaksi → diterima setelah beku dilepas · gedung handheld →
hanya bukti · merah terkunci → akui kunci (izin approve) · koreksi klaim beraudit · izin, idempoten, audit, kios.
Residu: dokumen baru dibuang (sidik `_id`), saldo & nomor urut dipulihkan. Jalankan TERPISAH dari iter117/118:
  cd /app/backend && python -m pytest -q -p no:cacheprovider -n0 tests/test_prep_d2_gate_txn.py
"""
import copy
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402
from services import rfid_v2_envelope as env  # noqa: E402
from services.rfid_ingest_service import hash_device_key  # noqa: E402

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
API, V2 = f"{BASE}/api", f"{BASE}/api/rfid/v2"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
ENT = "ent_ksc"
SITE = f"site_TEST_D2_{TAG}"
WH_SRC, WH_GATE, WH_HH = (f"wh_TEST_D2_{TAG}_{k}" for k in ("tr", "gate", "hh"))
DEV = {k: f"dev_TEST_D2_{TAG}_{k}" for k in ("in", "out", "hh")}
KEYS = {k: f"dk_TEST_D2_{TAG}_{k}" for k in DEV}
FIXTURE = json.loads((Path(__file__).parent / "fixtures/u300_contract.json").read_text())["DeviceConfig"]
_N = {"n": 0}


def _nx():
    _N["n"] += 1
    return _N["n"]


def _login(email):
    for pw in ("demo12345", "demo1234"):
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
        if r.status_code == 200:
            return {"Authorization": "Bearer " + r.json()["token"], "X-Entity-Id": ENT}
    pytest.skip(f"login {email} gagal")


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id")


@pytest.fixture(scope="module")
def whadmin():
    return _login("wh.admin@kainnusantara.id")


@pytest.fixture(scope="module")
def staff():
    return _login("warehouse@kainnusantara.id")


@pytest.fixture(scope="module", autouse=True)
def seed(admin):
    try:
        requests.get(f"{API}/health", timeout=10)
    except requests.RequestException:
        pytest.skip("backend tidak berjalan")
    stock = snapshot_stock(["inventory_balances", "number_sequences"])
    assert stock.get("__enabled__"), "restore harus aktif (DB uji)"
    names = [c for c in DB.list_collection_names() if c.startswith("rfid_v2")] + [
        "inventory_rolls", "inventory_movements", "inventory_lots", "audit_logs", "notifications", "rfid_tags",
        "rfid_devices", "putaway_orders", "warehouses", "warehouse_transfers", "shipments", "sales_orders",
        "cycle_count_sessions", "doc_refs", "wms_tasks", "rfid_v2_reviews", "rfid_v2_gate_txn",
        "rfid_v2_claim_corrections"]
    ids = snapshot_new_ids(sorted(set(names)))
    gate_cfg = {"has_gate": True, "physical_gate": True, "confirm_mode": "gate",
                "pairs": [{"in_device_id": DEV["in"], "out_device_id": DEV["out"], "layout": "terpisah"}]}
    for wid, code, roles, gc in ((WH_SRC, f"D2T{TAG}", ["transit", "receiving"], None),
                                 (WH_GATE, f"D2G{TAG}", ["storage"], gate_cfg), (WH_HH, f"D2H{TAG}", ["storage"], None)):
        DB.warehouses.insert_one({"id": wid, "name": f"Uji D2 {code}", "code": code, "roles": roles, "site_id": SITE,
                                  "sharing_mode": "shared", "active": True, "gate_config": gc or {"has_gate": False}})
    for k, wh in (("in", WH_GATE), ("out", WH_GATE), ("hh", WH_HH)):
        DB.rfid_devices.insert_one({"id": DEV[k], "code": f"D2-{k}-{TAG}", "name": f"Gate Uji D2 {k}", "type": "gate",
                                    "direction": "out" if k == "out" else "in", "warehouse_id": wh, "enabled": True,
                                    "status": "online", "api_key_hash": hash_device_key(KEYS[k])})
        publish(admin, k)
    yield
    purge_new_ids(ids, verbose=False)
    restore_stock(stock)


def publish(admin, k):
    cfg = copy.deepcopy(FIXTURE)
    wh = WH_HH if k == "hh" else WH_GATE
    cfg.update(device_id=DEV[k], warehouse_id=wh, site_id=SITE, config_version="d2-v1")
    g = cfg["logical_gates"][0]
    g.update(logical_gate_id="G1", warehouse_id=wh, site_id=SITE, direction="out" if k == "out" else "in",
             antenna_ids=["1", "2", "3"], completion_basis="document_session")
    r = requests.put(f"{V2}/ops/devices/{DEV[k]}/config", headers=admin, json=cfg, timeout=30)
    assert r.status_code == 200, r.text


def product():
    p = DB.products.find_one({"status": {"$ne": "inactive"}, "base_unit": "meter"}, {"_id": 0, "id": 1})
    assert p, "data acuan tanpa produk meter"
    return p["id"]


def rolls(n, wh=WH_SRC, status="available", **extra):
    pid, out = product(), []
    for _ in range(n):
        i = _nx()
        rid, tid, epc = f"roll_TEST_D2_{TAG}_{i}", f"tag_TEST_D2_{TAG}_{i}", f"E2D2{TAG.upper()}{i:012X}"
        DB.rfid_tags.insert_one({"id": tid, "epc": epc, "roll_id": rid, "status": "active", "warehouse_id": wh,
                                 "created_at": "2026-11-01T00:00:00+00:00"})
        DB.inventory_rolls.insert_one({
            "id": rid, "roll_no": f"D2{TAG}{i}", "product_id": pid, "warehouse_id": wh, "owner_entity_id": ENT,
            "status": status, "length_remaining": 30.0, "length_initial": 30.0, "unit": "meter", "grade": "A",
            "lot": "L-D2", "rfid_tag_id": tid, "bin_id": None, "active_movement": None, "length_reserved": 0,
            "length_reservations": [], "journey": {"stage": "tag_verified", "verified_tag_id": tid, "routing": "store",
                                                   "updated_at": "2026-11-02T00:00:00+00:00"}, **extra})
        out.append({"id": rid, "epc": epc, "roll_no": f"D2{TAG}{i}"})
    return out


def send(k, scenario, doc=(), extra=(), close_patch=None, resend=False):
    cfg = requests.get(f"{V2}/device/config", headers={"X-Device-Key": KEYS[k]}, timeout=30).json()
    g = cfg["logical_gates"][0]
    built = env.build_passage(scenario=scenario, gate_id="G1", config_version=cfg["config_version"],
                              hardware_profile_id=cfg["hardware_profile_id"], direction=g["direction"],
                              antennas=g["antenna_ids"], doc_epcs=doc, extra_strong=extra)
    for body in built["batches"]:
        r = requests.post(f"{V2}/events", headers={"X-Device-Key": KEYS[k]}, json=body, timeout=30)
        assert r.status_code == 200, r.text
    close = {**built["close"], **(close_patch or {})}
    hdr = {"X-Device-Key": KEYS[k], "Idempotency-Key": "c-" + built["passage_id"]}
    r = requests.post(f"{V2}/passages/{built['passage_id']}/close", json=close, timeout=90, headers=hdr)
    assert r.status_code == 200, r.text
    if resend:   # close ulang (retry agent) — keputusan & transaksi tidak boleh berlipat
        again = requests.post(f"{V2}/passages/{built['passage_id']}/close", json=close, timeout=90, headers=hdr)
        assert again.status_code == 200 and again.json()["decision_id"] == r.json()["decision_id"]
    wait_txn(k, r.json())
    return r.json()


def wait_txn(k, d, timeout=60):
    """PREP-H — transaksi gate kini di pekerja latar (close tidak menunggu): tunggu lintasan tuntas sebelum memeriksa
    efeknya (tiba PA, terima transfer, bukti trip, kasus antrean)."""
    import time
    pid = pid_of(k, d)
    end = time.time() + timeout
    while time.time() < end:
        row = DB.rfid_v2_passages.find_one({"_id": pid}, {"gate_txn_state": 1, "gate_txn_input": 1})
        if row and (row.get("gate_txn_state") in ("done", "error") or not row.get("gate_txn_input")):
            return row.get("gate_txn_state")
        time.sleep(0.05)
    raise AssertionError(f"transaksi gate lintasan {pid} belum tuntas dalam {timeout} dtk")


def pid_of(k, d):
    from services.rfid_v2_common import digest
    return digest([DEV[k], d["local_passage_id"]])


def published_pa(admin, n):
    from services import inbound_qc_common as iqc
    rs = rolls(n)
    out = run(iqc.auto_draft_after_release([r["id"] for r in rs], {"type": "test_d2", "id": f"{TAG}-{_nx()}"}, "Penguji"))
    drafts = [d for d in out["drafts"] if d["to_warehouse_name"] == f"Uji D2 D2G{TAG}"]
    assert len(drafts) == 1, out
    pa_id = drafts[0]["id"]
    r = requests.post(f"{API}/putaway-orders/{pa_id}/publish", headers=admin, json={}, timeout=60)
    assert r.status_code == 200, r.text
    assert requests.post(f"{API}/putaway-orders/{pa_id}/dispatch", headers=admin, timeout=60).status_code == 200
    return pa_id, rs


def pa(pa_id):
    return DB.putaway_orders.find_one({"id": pa_id}, {"_id": 0})


def shipment(n, wh=WH_GATE):
    so, sid = f"so_TEST_D2_{TAG}_{_nx()}", f"shp_TEST_D2_{TAG}_{_nx()}"
    DB.sales_orders.insert_one({"id": so, "number": so, "status": "in_progress", "entity_id": ENT})
    rs = rolls(n, wh=wh, status="in_transit_sales", reserved_ref={"type": "sales_order", "id": so})
    DB.shipments.insert_one({"id": sid, "shipment_no": f"SJ-D2-{_nx()}", "order_id": so, "warehouse_id": wh,
                             "status": "dispatched", "entity_id": ENT, "created_at": datetime.now(timezone.utc).isoformat(),
                             "rolls": [{"roll_id": r["id"]} for r in rs]})
    return sid, rs


def case(cid, hdr):
    r = requests.get(f"{V2}/ops/reviews/{cid}", headers=hdr, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def session(hdr, typ, sid, direction):
    r = requests.get(f"{V2}/ops/doc-sessions/{typ}/{sid}", headers=hdr, params={"direction": direction}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


# ── 1. PA dari GRN → gate IN 2 trip → sisa handheld → PA selesai (K-GDG-02/10, K-RFID-10) ───────────
def test_putaway_gate_in_two_trips_then_handheld(admin):
    pa_id, rs = published_pa(admin, 5)
    e = [r["epc"] for r in rs]
    d1 = send("in", "partial_trip", e[:2])
    assert d1["verdict"] == "GREEN" and d1["counts"]["pending"] == 3, d1["reason_codes"]
    doc = pa(pa_id)
    assert doc["status"] == "partially_received" and doc["arrived_count"] == 2 and doc.get("btg_number")
    trip = doc["arrival_trips"][0]
    assert trip["source"]["type"] == "gate" and trip["source"]["passage_id"] == pid_of("in", d1)
    d2 = send("in", "partial_trip", e[2:4], resend=True)          # trip 2 + close diulang (idempoten)
    assert d2["verdict"] == "GREEN" and d2["counts"]["pending"] == 1
    doc = pa(pa_id)
    assert (doc["status"], doc["arrived_count"], len(doc["arrival_trips"])) == ("partially_received", 4, 2)
    assert {i["arrived_via"] for i in doc["items"] if i["status"] == "arrived"} == {"gate"}
    led = list(DB.rfid_v2_gate_txn.find({"source_ref.source_id": pa_id}))
    assert len(led) == 2 and {x["state"] for x in led} == {"done"} and all(x["attempts"] == 1 for x in led)
    r = requests.post(f"{API}/putaway-orders/{pa_id}/arrival-trips", headers=admin,
                      json={"epcs": [e[4]], "client_trip_id": f"HH-{TAG}"}, timeout=60)
    assert r.status_code == 200, r.text
    assert pa(pa_id)["status"] == "completed"
    st = session(admin, "putaway", pa_id, "in")
    assert st["status"] == "closed" and st["close"]["verdict"] == "GREEN" and st["close"]["trigger"] == "putaway_closed"
    assert st["close"]["completed_count"] == 1 and st["close"]["completed"][0]["via"] == "handheld"
    assert not DB.rfid_v2_reviews.find_one({"kind": "rolls_missing", "sources.source_id": pa_id})


# ── 2. transfer ke gedung bergate: terima per trip lewat layanan terima transfer ─────────────────────
def test_transfer_received_per_gate_trip(admin):
    tid = f"trf_TEST_D2_{TAG}_{_nx()}"
    rs = rolls(3, status="in_transit_transfer", reserved_ref={"type": "wh_transfer", "id": tid})
    DB.warehouse_transfers.insert_one({
        "id": tid, "code": f"TRF-D2-{_nx()}", "status": "dispatched", "transfer_kind": "warehouse",
        "source_warehouse_id": WH_SRC, "dest_warehouse_id": WH_GATE, "owner_entity_id": ENT, "entity_id": ENT,
        "items": [{"product_id": product(), "unit": "meter",
                   "rolls": [{"roll_id": r["id"], "roll_no": r["roll_no"], "length": 30.0} for r in rs]}],
        "created_at": datetime.now(timezone.utc).isoformat()})
    d1 = send("in", "partial_trip", [rs[0]["epc"], rs[1]["epc"]], resend=True)
    assert d1["verdict"] == "GREEN"
    t = DB.warehouse_transfers.find_one({"id": tid})
    assert t["status"] == "partially_received" and len(t["receipt_events"]) == 1
    assert DB.inventory_rolls.count_documents({"id": {"$in": [rs[0]["id"], rs[1]["id"]]}, "warehouse_id": WH_GATE}) == 2
    assert send("in", "partial_trip", [rs[2]["epc"]])["verdict"] == "GREEN"
    assert DB.warehouse_transfers.find_one({"id": tid})["status"] == "completed"
    st = session(admin, "wh_transfer", tid, "in")
    assert st["status"] == "closed" and st["close"]["verdict"] == "GREEN" and st["close"]["trigger"] == "transfer_completed"


# ── 3. SJ keluar 2 trip → bukti per trip → SJ berangkat → roll kurang kuning → admin terima / tolak ──
def test_shipment_out_trips_missing_roll_accept(whadmin, staff):
    from services import logistics_service as lgs
    sid, rs = shipment(4)
    d1 = send("out", "partial_trip", [r["epc"] for r in rs[:2]])
    d2 = send("out", "partial_trip", [rs[2]["epc"]])
    assert (d1["verdict"], d2["verdict"]) == ("GREEN", "GREEN")
    exits = DB.shipments.find_one({"id": sid})["gate_exits"]
    assert [(x["trip_no"], x["count"], x["txn"]) for x in exits] == [(1, 2, True), (2, 1, True)]
    run(lgs._close_gate_sessions({"shipment_ids": [sid]}, "shipment_departed"))   # kait logistik "berangkat"
    st = session(whadmin, "shipment", sid, "out")
    assert st["close"]["verdict"] == "REVIEW" and st["close"]["missing"][0]["roll_id"] == rs[3]["id"]
    c = DB.rfid_v2_reviews.find_one({"kind": "rolls_missing", "sources.source_id": sid})
    assert c and c["rolls"][0]["state"] == "open" and c["txn_mode"] == "gate"
    assert DB.notifications.find_one({"ref": f"rfid_review:{c['_id']}:warehouse_admin", "type": "rfid_gate_review"})
    url = f"{V2}/ops/reviews/{c['_id']}/rolls/accept"
    body = {"roll_keys": [rs[3]["id"]], "reason": "Dicek fisik di truk, roll ada"}
    assert requests.post(url, headers=staff, json=body, timeout=30).status_code == 403   # wms.scan tanpa approve
    r = requests.post(url, headers=whadmin, json=body, timeout=60)
    assert r.status_code == 200, r.text
    assert r.json()["case"]["status"] == "resolved" and r.json()["case"]["rolls"][0]["state"] == "accepted"
    again = requests.post(url, headers=whadmin, json=body, timeout=60)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "REVIEW_CLOSED"   # idempoten: tidak dobel
    assert session(whadmin, "shipment", sid, "out")["passed"] == 4
    assert DB.shipments.find_one({"id": sid})["gate_exits"][-1]["via"] == "review"
    assert DB.audit_logs.find_one({"action": "rfid_v2_review_accept", "entity_id": c["_id"]})


def test_shipment_missing_roll_reject_and_review_passage(whadmin):
    from services import gate_txn_service as gt
    sid, rs = shipment(2)
    d = send("out", "full_load", [rs[0]["epc"]], close_patch={"capture_complete": False})
    assert d["verdict"] == "REVIEW" and not d["latched"]                                # kuning: barang jalan
    pc = case(DB.rfid_v2_reviews.find_one({"passage": pid_of("out", d)})["_id"], whadmin)
    assert pc["manual_close"] and pc["rolls"][0]["state"] == "recorded"                # roll cocok tetap dicatat
    assert any(x["code"] == "CAPTURE_INCOMPLETE" for x in pc["reasons"])
    r = requests.post(f"{V2}/ops/reviews/{pc['case_id']}/dismiss", headers=whadmin, json={"reason": "bukti lengkap di CCTV"})
    assert r.status_code == 200 and r.json()["case"]["status"] == "resolved"
    st = run(gt.close_document_session("shipment", sid, "out", "manual", {"id": "u", "name": "Uji"}, "tutup"))
    assert st["closed_now"] and st["close"]["missing_count"] == 1
    cid = DB.rfid_v2_reviews.find_one({"kind": "rolls_missing", "sources.source_id": sid})["_id"]
    r = requests.post(f"{V2}/ops/reviews/{cid}/rolls/reject", headers=whadmin,
                      json={"roll_keys": [rs[1]["id"]], "reason": "roll tertinggal di gudang", "mode": "reject"})
    assert r.status_code == 200 and r.json()["case"]["rolls"][0]["state"] == "rejected"
    assert r.json()["case"]["status"] == "resolved"


# ── 4. area beku pendaftaran awal → kuning AREA_FROZEN tanpa transaksi → diterima setelah beku dilepas ─
def test_frozen_area_review_without_transaction(admin, whadmin):
    pa_id, rs = published_pa(admin, 2)
    sess = f"cc_TEST_D2_{TAG}_{_nx()}"
    DB.cycle_count_sessions.insert_one({"id": sess, "name": "Uji D2 beku", "mode": "registration", "warehouse_id": WH_GATE,
                                        "warehouse_name": "Uji D2", "freeze": {"active": True, "mode": "warehouse", "bin_ids": []}})
    try:
        d = send("in", "full_load", [r["epc"] for r in rs])
        assert d["verdict"] == "REVIEW" and d["reason_code"] == "AREA_FROZEN" and not d["latched"]
        doc = pa(pa_id)
        assert doc["status"] == "in_transit" and not doc.get("arrival_trips") and doc["gate_arrivals"][0]["txn"] is False
        assert DB.rfid_v2_gate_txn.find_one({"passage": pid_of("in", d)})["state"] == "frozen"
        kio = requests.get(f"{V2}/ops/devices/{DEV['in']}/kiosk", headers=whadmin, timeout=30).json()
        assert kio["passage"]["verdict"] == "yellow" and not kio["latched"]
        c = case(DB.rfid_v2_reviews.find_one({"passage": pid_of("in", d)})["_id"], whadmin)
        keys = [i["key"] for i in c["rolls"]]
        assert {i["state"] for i in c["rolls"]} == {"open"} and all("AREA_FROZEN" in i["codes"] for i in c["rolls"])
        assert all(i["evidence"] and i["evidence"]["peak_rssi"] for i in c["rolls"])            # bukti per roll
        r = requests.post(f"{V2}/ops/reviews/{c['case_id']}/rolls/accept", headers=whadmin,
                          json={"roll_keys": keys, "reason": "coba saat beku"})
        assert r.status_code == 409 and r.json()["detail"]["code"] == "REGISTRATION_FREEZE"
        assert {i["state"] for i in case(c["case_id"], whadmin)["rolls"]} == {"open"}           # dikembalikan
    finally:
        DB.cycle_count_sessions.update_one({"id": sess}, {"$set": {"freeze.active": False}})
    r = requests.post(f"{V2}/ops/reviews/{c['case_id']}/rolls/accept", headers=whadmin,
                      json={"roll_keys": keys, "reason": "beku sudah dilepas, fisik dicek"})
    assert r.status_code == 200, r.text
    assert pa(pa_id)["status"] == "completed" and r.json()["case"]["status"] == "resolved"


# ── 5. gedung bermode handheld: gate hanya bukti, alur handheld lama tetap ──────────────────────────
def test_handheld_warehouse_gate_records_evidence_only(admin):
    rs = rolls(2)
    r = requests.post(f"{API}/putaway-orders", headers=admin, timeout=60,
                      json={"from_warehouse_id": WH_SRC, "to_warehouse_id": WH_HH, "roll_ids": [x["id"] for x in rs]})
    assert r.status_code == 200, r.text
    pa_id = r.json()["id"]
    assert requests.post(f"{API}/putaway-orders/{pa_id}/dispatch", headers=admin, timeout=60).status_code == 200
    d = send("hh", "full_load", [x["epc"] for x in rs])
    assert d["verdict"] == "GREEN" and "HANDHELD_MODE" in d["reason_codes"]
    doc = pa(pa_id)
    assert doc["status"] == "in_transit" and not doc.get("arrival_trips")
    assert doc["gate_arrivals"][0]["txn"] is False and doc["gate_arrivals"][0]["count"] == 2
    assert DB.rfid_v2_gate_txn.find_one({"passage": pid_of("hh", d)})["state"] == "evidence"
    r = requests.post(f"{API}/putaway-orders/{pa_id}/arrival-trips", headers=admin,
                      json={"epcs": [x["epc"] for x in rs], "client_trip_id": f"HH2-{TAG}"}, timeout=60)
    assert r.status_code == 200 and pa(pa_id)["status"] == "completed"


def _simulate(admin, pa_id):
    r = requests.post(f"{V2}/ops/devices/{DEV['in']}/simulate", headers=admin, timeout=120,
                      json={"scenario": "partial_trip", "source_type": "putaway", "source_id": pa_id})
    assert r.status_code == 200, r.text
    return [p["decision"] for p in r.json()["passages"]]


def test_ops_simulator_respects_rfid_simulation_mode(admin):
    """Simulator ops D1 di gedung bergate: transaksi HANYA bila Mode simulasi RFID PT dokumen menyala (UAT);
    bila mati → hanya bukti, stok tidak berubah (simulator tidak boleh mengubah stok produksi)."""
    q = {"key": "wms.rfid_simulation", "scope_type": "entity", "scope_id": ENT}
    old = [r["value"] for r in DB.config_values.find(q, {"_id": 0, "value": 1})]
    try:
        DB.config_values.update_many(q, {"$set": {"value": False}})
        pa_id, _ = published_pa(admin, 2)
        ds = _simulate(admin, pa_id)
        assert [d["verdict"] for d in ds] == ["GREEN", "GREEN"] and all("SIMULATED_EVIDENCE" in d["reason_codes"] for d in ds)
        doc = pa(pa_id)
        assert doc["status"] == "in_transit" and not doc.get("arrival_trips")
        assert [(x["trip_no"], x["txn"], x["simulated"]) for x in doc["gate_arrivals"]] == [(1, False, True), (2, False, True)]
        if not old:
            DB.config_values.insert_one({**q, "id": f"cfgv_TEST_D2_{TAG}", "value": True, "effective_from": "2026-01-01",
                                         "effective_to": "", "created_at": "2026-01-01"})
        DB.config_values.update_many(q, {"$set": {"value": True}})
        pa2, _ = published_pa(admin, 2)
        ds = _simulate(admin, pa2)
        assert [d["verdict"] for d in ds] == ["GREEN", "GREEN"] and not any("SIMULATED_EVIDENCE" in d["reason_codes"] for d in ds)
        doc = pa(pa2)
        assert doc["status"] == "completed" and len(doc["arrival_trips"]) == 2   # simulator D1 → tiba bertahap 2 trip
    finally:
        if old:
            DB.config_values.update_many(q, {"$set": {"value": old[0]}})
        DB.config_values.delete_many({"id": f"cfgv_TEST_D2_{TAG}"})


# ── 6. merah terkunci → akui kunci gate (izin approve, terpisah dari wms.scan) ───────────────────────
def test_red_latch_acknowledge_needs_approve(whadmin, staff):
    _, rs = shipment(1)
    stray = rolls(1, wh=WH_GATE)[0]
    d = send("out", "foreign_roll", [rs[0]["epc"]], extra=[stray["epc"]])
    assert d["verdict"] == "RED" and d["latched"]
    assert not DB.rfid_v2_gate_txn.find_one({"passage": pid_of("out", d), "state": {"$ne": "skipped"}})   # merah: nihil
    c = DB.rfid_v2_reviews.find_one({"passage": pid_of("out", d)})
    assert c and c["latch_open"] and c["verdict"] == "RED"
    url = f"{V2}/ops/reviews/{c['_id']}/acknowledge-latch"
    assert requests.post(url, headers=staff, json={"note": "dicek satpam"}).status_code == 403
    assert requests.post(f"{V2}/ops/devices/{DEV['out']}/gate-latch/acknowledge", headers=staff,
                         json={"latch_id": d["latch_id"], "note": "dicek satpam"}).status_code == 403
    r = requests.post(url, headers=whadmin, json={"note": "roll asing dikembalikan ke rak"})
    assert r.status_code == 200 and r.json()["latch_released"], r.text
    kio = requests.get(f"{V2}/ops/devices/{DEV['out']}/kiosk", headers=whadmin, timeout=30).json()
    assert not kio["latched"]
    stray_item = next(i for i in r.json()["case"]["rolls"] if i["roll_id"] == stray["id"])
    assert "NOT_IN_DOCUMENT" in stray_item["codes"] or "NO_DOCUMENT" in stray_item["codes"]
    r = requests.post(f"{V2}/ops/reviews/{c['_id']}/rolls/accept", headers=whadmin,
                      json={"roll_keys": [stray_item["key"]], "reason": "coba terima tanpa dokumen"})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "NO_DOCUMENT_FOR_ROLL"


# ── 7. koreksi klaim crossing beraudit (AUD-MW-08) ──────────────────────────────────────────────────
def test_claim_release_and_move_audited(whadmin, staff):
    sid, rs = shipment(1)
    assert send("out", "full_load", [rs[0]["epc"]])["verdict"] == "GREEN"
    src = {"source_type": "shipment", "source_id": sid}
    other = f"shp_TEST_D2_{TAG}_{_nx()}"
    so = DB.shipments.find_one({"id": sid})["order_id"]
    DB.shipments.insert_one({"id": other, "shipment_no": f"SJ-D2-{_nx()}", "order_id": so, "warehouse_id": WH_GATE,
                             "status": "dispatched", "entity_id": ENT, "rolls": [{"roll_id": rs[0]["id"]}]})
    body = {"source": src, "target": {"source_type": "shipment", "source_id": other}, "direction": "out",
            "roll_id": rs[0]["id"], "reason": "roll dimuat untuk SJ lain"}
    assert requests.post(f"{V2}/ops/crossings/move", headers=staff, json=body).status_code == 403
    short = requests.post(f"{V2}/ops/crossings/move", headers=whadmin, json={**body, "reason": "salah"})
    assert short.status_code == 400 and short.json()["detail"]["code"] == "REASON_REQUIRED"
    r = requests.post(f"{V2}/ops/crossings/move", headers=whadmin, json=body)
    assert r.status_code == 200 and r.json()["moved"], r.text
    assert session(whadmin, "shipment", sid, "out")["passed"] == 0
    assert session(whadmin, "shipment", other, "out")["passed"] == 1
    rel = {"source": {"source_type": "shipment", "source_id": other}, "direction": "out", "roll_id": rs[0]["id"],
           "reason": "klaim keliru, roll belum keluar"}
    r = requests.post(f"{V2}/ops/crossings/release", headers=whadmin, json=rel)
    assert r.status_code == 200 and r.json()["released"]
    assert requests.post(f"{V2}/ops/crossings/release", headers=whadmin, json=rel).status_code == 404   # idempoten
    hist = requests.get(f"{V2}/ops/crossings", headers=whadmin,
                        params={"source_type": "shipment", "source_id": other, "direction": "out"}).json()
    assert {c["action"] for c in hist["corrections"]} == {"move", "release"} and not hist["claims"]
    assert DB.audit_logs.find_one({"action": "rfid_v2_claim_moved", "entity_id": sid})


# ── 8. cek muat handheld di gedung bergate = cadangan (K-GDG-02/03) ─────────────────────────────────
def test_loading_check_required_policy_satisfied_by_gate():
    from fastapi import HTTPException
    from services import loading_check_service as lcs
    so = f"so_TEST_D2_{TAG}_{_nx()}"
    DB.sales_orders.insert_one({"id": so, "number": so, "status": "in_progress", "entity_id": ENT})
    DB.warehouses.update_many({"id": {"$in": [WH_GATE, WH_HH]}}, {"$set": {"loading_check_policy": "required"}})
    run(lcs.dispatch_guard(so, WH_GATE))                     # gate OUT tertaut → tidak wajib cek muat handheld
    with pytest.raises(HTTPException) as e:
        run(lcs.dispatch_guard(so, WH_HH))                   # gedung handheld → aturan lama tetap
    assert "mewajibkan Final Loading Check" in str(e.value.detail)
    assert run(lcs.status_for_order(so, WH_GATE))["gate_out_primary"] is True


def test_review_list_filters_and_permissions(whadmin):
    r = requests.get(f"{V2}/ops/reviews", headers=whadmin, params={"warehouse_id": WH_GATE, "status": "all"})
    assert r.status_code == 200 and all(x["warehouse_id"] == WH_GATE for x in r.json()["reviews"])
    assert r.json()["reviews"] and "_id" not in r.json()["reviews"][0]
    assert requests.get(f"{V2}/ops/reviews", headers=whadmin, params={"status": "x"}).status_code == 400
    assert requests.get(f"{V2}/ops/reviews").status_code == 401
    s = requests.get(f"{V2}/ops/reviews/summary", headers=whadmin, params={"warehouse_id": WH_GATE}).json()
    assert set(s) >= {"open", "red", "review"}
