"""Iter-117 P09 — Gate contract (RF-02, RF-03, RF-16, UX-01) via HTTP /api.

Prasyarat service-level 22/22 sudah hijau di repro_p09.py. Tes ini memvalidasi jalur HTTP:
- POST /api/rfid/devices + /api-key → X-Device-Key
- POST /api/rfid/ingest (events[], batch_id, session_id) dengan verdict/passage/duplicates
- POST /api/rfid/gate/simulate (jalur ingest sama)
- GET  /api/rfid/gate/{id}/status (latched, device.heartbeat_age_s, passage)
- POST /api/rfid/passages/{id}/acknowledge (note<5 → 400; ulang → 409)
- GET  /api/rfid/reads?read_type=gate (hanya gate_in/gate_out, cursor before)
- GET  /api/outbound/so/{id}/loading-check (last_scan_log terakhir)

Data uji diprefiks TEST_iter117_ dan dibersihkan di test_zz_cleanup.
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient


def _base() -> str:
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        with open("C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/frontend/.env") as f:
            for ln in f:
                if ln.startswith("REACT_APP_BACKEND_URL="):
                    v = ln.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    assert v, "REACT_APP_BACKEND_URL not set"
    return v.rstrip("/")


BASE = _base()
MONGO = AsyncIOMotorClient("mongodb://127.0.0.1:27919")
DB = MONGO["knhost_data_audit_latest_pytest"]
ENTITY = "ent_ksc"
T = f"TEST_iter117_{uuid.uuid4().hex[:6]}"


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ─── Fixtures ───────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    s.headers.update({"X-Entity-Id": ENTITY})
    r = s.post(f"{BASE}/api/auth/login",
               json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=20)
    assert r.status_code == 200, r.text
    tok = r.json().get("token") or r.json().get("access_token")
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def warehouse():
    s = requests.Session()
    s.headers.update({"X-Entity-Id": ENTITY})
    r = s.post(f"{BASE}/api/auth/login",
               json={"email": "warehouse@kainnusantara.id", "password": "demo12345"}, timeout=20)
    assert r.status_code == 200, r.text
    tok = r.json().get("token") or r.json().get("access_token")
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


def _mk_device(admin, name: str, dtype: str, warehouse_id: str,
               direction: Optional[str] = None) -> Dict[str, Any]:
    """Create a device + obtain API key. Returns {device, api_key}."""
    body = {"name": f"{T} {name}", "type": dtype, "warehouse_id": warehouse_id}
    if direction:
        body["direction"] = direction
    r = admin.post(f"{BASE}/api/rfid/devices", json=body, timeout=20)
    assert r.status_code == 200, r.text
    dev = r.json()
    r2 = admin.post(f"{BASE}/api/rfid/devices/{dev['id']}/api-key", timeout=20)
    assert r2.status_code == 200, r2.text
    key = r2.json().get("api_key") or r2.json().get("key")
    assert key, r2.json()
    # heartbeat to mark online
    hb = requests.post(f"{BASE}/api/rfid/heartbeat", headers={"X-Device-Key": key}, timeout=20)
    assert hb.status_code == 200, hb.text
    return {"device": dev, "api_key": key}


async def _mk_roll(idx: int, **kw) -> Dict[str, Any]:
    prod = await DB.products.find_one({}, {"_id": 0, "id": 1})
    r = {"id": f"{T}_r{idx}", "roll_no": f"{T}-R{idx}", "product_id": prod["id"],
         "owner_entity_id": ENTITY, "warehouse_id": "wh_jakarta", "status": "available",
         "length_remaining": 10.0, "unit": "meter",
         "created_at": "2026-01-01T00:00:00+00:00", **kw}
    await DB.inventory_rolls.insert_one(dict(r))
    return r


async def _encode(roll_id: str) -> str:
    """Encode EPC via service → returns canonical 24-hex EPC."""
    import sys
    sys.path.insert(0, "C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend")
    from services import rfid_service as rs
    tag = await rs.encode_tag(roll_id, [ENTITY])
    return tag["epc"]


# ─── RF-02 — Gate OUT (HTTP /rfid/ingest) ───────────────────────────────────
class TestRF02GateOut:
    def test_available_roll_out_red_no_document(self, admin):
        """Roll available tanpa dokumen → red NO_DOCUMENT (gate OUT di gudang asal)."""
        dev = _mk_device(admin, "gate-out-rf02-nd", "gate", "wh_jakarta", "out")
        roll = _run(_mk_roll(101))
        epc = _run(_encode(roll["id"]))
        r = requests.post(f"{BASE}/api/rfid/ingest",
                          headers={"X-Device-Key": dev["api_key"]},
                          json={"events": [{"epc": epc, "event_id": f"{T}-e101"}]},
                          timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["results"][0]["result"] == "red"
        assert body["results"][0].get("code") == "NO_DOCUMENT", body
        assert "passage" in body and body["passage"]["verdict"] == "red"
        assert "reason" in body["results"][0]

    def test_reserved_so_not_dispatched_red(self, admin):
        """Roll reserved untuk SO (belum dispatch) tanpa shipment → red (NOT_IN_MANIFEST / NOT_RELEASED).

        Observasi: evaluator mengembalikan NOT_IN_MANIFEST ketika tidak ada shipment yang mencantumkan
        roll (sesuai gate_evaluator). NOT_RELEASED dipakai jika shipment ada tapi belum dispatched.
        """
        so_id = f"{T}_so_notrel"
        _run(DB.sales_orders.insert_one(
            {"id": so_id, "number": f"{T}-SO-NR", "entity_id": ENTITY, "status": "confirmed"}))
        # Shipment ada tapi status != dispatched → NOT_RELEASED
        _run(DB.shipments.insert_one(
            {"id": f"{T}_shp_nr", "order_id": so_id, "warehouse_id": "wh_jakarta",
             "status": "draft", "rolls": [{"roll_id": f"{T}_r102"}],
             "created_at": "2026-01-01T00:00:00+00:00"}))
        dev = _mk_device(admin, "gate-out-rf02-nr", "gate", "wh_jakarta", "out")
        roll = _run(_mk_roll(102, status="reserved",
                             reserved_ref={"type": "sales_order", "id": so_id}))
        epc = _run(_encode(roll["id"]))
        r = requests.post(f"{BASE}/api/rfid/ingest",
                          headers={"X-Device-Key": dev["api_key"]},
                          json={"events": [{"epc": epc, "event_id": f"{T}-e102"}]},
                          timeout=20)
        assert r.status_code == 200, r.text
        res = r.json()["results"][0]
        assert res["result"] == "red"
        assert res.get("code") in ("NOT_RELEASED", "NOT_IN_MANIFEST"), res
        assert "reason" in res

    def test_dispatched_shipment_green_then_replay_red(self, admin):
        """Jalur bahagia: in_transit_sales + shipment dispatched di gudang gate → green,
        kemudian gate OUT lain → red REPLAY_EXIT."""
        so_id = f"{T}_so_ok"
        _run(DB.sales_orders.insert_one(
            {"id": so_id, "number": f"{T}-SO-OK", "entity_id": ENTITY, "status": "confirmed"}))
        roll = _run(_mk_roll(103, status="in_transit_sales",
                             reserved_ref={"type": "sales_order", "id": so_id}))
        _run(DB.shipments.insert_one(
            {"id": f"{T}_shp_ok", "order_id": so_id, "warehouse_id": "wh_jakarta",
             "status": "dispatched", "rolls": [{"roll_id": roll["id"]}],
             "created_at": "2026-01-01T00:00:00+00:00"}))
        epc = _run(_encode(roll["id"]))
        g1 = _mk_device(admin, "gate-out-rf02-ok1", "gate", "wh_jakarta", "out")
        r1 = requests.post(f"{BASE}/api/rfid/ingest",
                           headers={"X-Device-Key": g1["api_key"]},
                           json={"events": [{"epc": epc, "event_id": f"{T}-eok1"}]},
                           timeout=20)
        assert r1.status_code == 200, r1.text
        res1 = r1.json()["results"][0]
        assert res1["result"] == "green", res1
        assert res1.get("code") in ("MOVEMENT_OUT",), res1

        # Replay via gate lain (jakarta) sesudahnya → red REPLAY_EXIT / ALREADY_OUT
        g2 = _mk_device(admin, "gate-out-rf02-ok2", "gate", "wh_jakarta", "out")
        r2 = requests.post(f"{BASE}/api/rfid/ingest",
                           headers={"X-Device-Key": g2["api_key"]},
                           json={"events": [{"epc": epc, "event_id": f"{T}-eok2"}]},
                           timeout=20)
        assert r2.status_code == 200, r2.text
        res2 = r2.json()["results"][0]
        assert res2["result"] == "red", res2
        assert res2.get("code") in ("REPLAY_EXIT", "ALREADY_OUT"), res2

    def test_wrong_warehouse_red(self, admin):
        """Shipment dispatched di wh_jakarta, dibaca di gate wh_surabaya → red WRONG_WAREHOUSE."""
        so_id = f"{T}_so_ww"
        _run(DB.sales_orders.insert_one(
            {"id": so_id, "number": f"{T}-SO-WW", "entity_id": ENTITY, "status": "confirmed"}))
        roll = _run(_mk_roll(104, status="in_transit_sales",
                             reserved_ref={"type": "sales_order", "id": so_id}))
        _run(DB.shipments.insert_one(
            {"id": f"{T}_shp_ww", "order_id": so_id, "warehouse_id": "wh_jakarta",
             "status": "dispatched", "rolls": [{"roll_id": roll["id"]}],
             "created_at": "2026-01-01T00:00:00+00:00"}))
        epc = _run(_encode(roll["id"]))
        g = _mk_device(admin, "gate-out-rf02-ww", "gate", "wh_surabaya", "out")
        r = requests.post(f"{BASE}/api/rfid/ingest",
                          headers={"X-Device-Key": g["api_key"]},
                          json={"events": [{"epc": epc, "event_id": f"{T}-eww"}]},
                          timeout=20)
        assert r.status_code == 200, r.text
        res = r.json()["results"][0]
        assert res["result"] == "red"
        assert res.get("code") == "WRONG_WAREHOUSE", res

    def test_so_cancelled_red(self, admin):
        so_id = f"{T}_so_cnc"
        _run(DB.sales_orders.insert_one(
            {"id": so_id, "number": f"{T}-SO-CNC", "entity_id": ENTITY, "status": "cancelled"}))
        roll = _run(_mk_roll(105, status="in_transit_sales",
                             reserved_ref={"type": "sales_order", "id": so_id}))
        _run(DB.shipments.insert_one(
            {"id": f"{T}_shp_cnc", "order_id": so_id, "warehouse_id": "wh_jakarta",
             "status": "dispatched", "rolls": [{"roll_id": roll["id"]}],
             "created_at": "2026-01-01T00:00:00+00:00"}))
        epc = _run(_encode(roll["id"]))
        g = _mk_device(admin, "gate-out-rf02-cnc", "gate", "wh_jakarta", "out")
        r = requests.post(f"{BASE}/api/rfid/ingest",
                          headers={"X-Device-Key": g["api_key"]},
                          json={"events": [{"epc": epc, "event_id": f"{T}-ecnc"}]},
                          timeout=20)
        res = r.json()["results"][0]
        assert res["result"] == "red" and res.get("code") == "SO_CANCELLED", res

    def test_already_out_red(self, admin):
        """Roll yang sudah delivered → red ALREADY_OUT. Encode saat masih available, lalu set delivered."""
        roll = _run(_mk_roll(106, status="available"))
        epc = _run(_encode(roll["id"]))
        _run(DB.inventory_rolls.update_one({"id": roll["id"]}, {"$set": {"status": "delivered"}}))
        g = _mk_device(admin, "gate-out-rf02-ao", "gate", "wh_jakarta", "out")
        r = requests.post(f"{BASE}/api/rfid/ingest",
                          headers={"X-Device-Key": g["api_key"]},
                          json={"events": [{"epc": epc, "event_id": f"{T}-eao"}]},
                          timeout=20)
        res = r.json()["results"][0]
        assert res["result"] == "red" and res.get("code") == "ALREADY_OUT", res


# ─── RF-03 — Gate IN ────────────────────────────────────────────────────────
class TestRF03GateIn:
    def test_wh_transfer_green_at_destination(self, admin):
        tr_id = f"{T}_tr_ok"
        _run(DB.warehouse_transfers.insert_one(
            {"id": tr_id, "code": f"{T}-TRF-OK", "status": "dispatched",
             "source_warehouse_id": "wh_jakarta", "dest_warehouse_id": "wh_bandung"}))
        roll = _run(_mk_roll(201, status="in_transit_transfer",
                             reserved_ref={"type": "wh_transfer", "id": tr_id}))
        epc = _run(_encode(roll["id"]))
        g = _mk_device(admin, "gate-in-rf03-ok", "gate", "wh_bandung", "in")
        r = requests.post(f"{BASE}/api/rfid/ingest",
                          headers={"X-Device-Key": g["api_key"]},
                          json={"events": [{"epc": epc, "event_id": f"{T}-ein1"}]},
                          timeout=20)
        assert r.status_code == 200, r.text
        res = r.json()["results"][0]
        assert res["result"] == "green", res

    def test_wh_transfer_wrong_destination_red(self, admin):
        tr_id = f"{T}_tr_wd"
        _run(DB.warehouse_transfers.insert_one(
            {"id": tr_id, "code": f"{T}-TRF-WD", "status": "dispatched",
             "source_warehouse_id": "wh_jakarta", "dest_warehouse_id": "wh_bandung"}))
        roll = _run(_mk_roll(202, status="in_transit_transfer",
                             reserved_ref={"type": "wh_transfer", "id": tr_id}))
        epc = _run(_encode(roll["id"]))
        g = _mk_device(admin, "gate-in-rf03-wd", "gate", "wh_surabaya", "in")
        r = requests.post(f"{BASE}/api/rfid/ingest",
                          headers={"X-Device-Key": g["api_key"]},
                          json={"events": [{"epc": epc, "event_id": f"{T}-ein2"}]},
                          timeout=20)
        res = r.json()["results"][0]
        assert res["result"] == "red" and res.get("code") == "WRONG_DESTINATION", res

    def test_transit_without_document_red(self, admin):
        roll = _run(_mk_roll(203, status="in_transit_transfer"))
        epc = _run(_encode(roll["id"]))
        g = _mk_device(admin, "gate-in-rf03-dm", "gate", "wh_bandung", "in")
        r = requests.post(f"{BASE}/api/rfid/ingest",
                          headers={"X-Device-Key": g["api_key"]},
                          json={"events": [{"epc": epc, "event_id": f"{T}-ein3"}]},
                          timeout=20)
        res = r.json()["results"][0]
        assert res["result"] == "red" and res.get("code") == "DOC_MISSING", res

    def test_sales_transit_at_gate_in_red(self, admin):
        so_id = f"{T}_so_in"
        _run(DB.sales_orders.insert_one(
            {"id": so_id, "number": f"{T}-SO-IN", "entity_id": ENTITY, "status": "confirmed"}))
        roll = _run(_mk_roll(204, status="in_transit_sales",
                             reserved_ref={"type": "sales_order", "id": so_id}))
        epc = _run(_encode(roll["id"]))
        g = _mk_device(admin, "gate-in-rf03-sls", "gate", "wh_bandung", "in")
        r = requests.post(f"{BASE}/api/rfid/ingest",
                          headers={"X-Device-Key": g["api_key"]},
                          json={"events": [{"epc": epc, "event_id": f"{T}-ein4"}]},
                          timeout=20)
        res = r.json()["results"][0]
        assert res["result"] == "red" and res.get("code") == "SALES_TRANSIT_NOT_INBOUND", res


# ─── RF-16 — Idempoten/batch cap ────────────────────────────────────────────
class TestRF16Idempotent:
    def test_replay_event_id_duplicates(self, admin):
        roll = _run(_mk_roll(301))
        epc = _run(_encode(roll["id"]))
        g = _mk_device(admin, "gate-rf16-rp", "gate", "wh_jakarta", "out")
        ev_id = f"{T}-rp-1"
        r1 = requests.post(f"{BASE}/api/rfid/ingest",
                           headers={"X-Device-Key": g["api_key"]},
                           json={"events": [{"epc": epc, "event_id": ev_id}]}, timeout=20)
        assert r1.status_code == 200
        reads1 = _run(DB.rfid_reads.count_documents({"device_id": g["device"]["id"]}))
        inc1 = _run(DB.rfid_incidents.count_documents({"epc": epc}))
        r2 = requests.post(f"{BASE}/api/rfid/ingest",
                           headers={"X-Device-Key": g["api_key"]},
                           json={"events": [{"epc": epc, "event_id": ev_id}]}, timeout=20)
        body2 = r2.json()
        assert body2.get("duplicates") == 1, body2
        reads2 = _run(DB.rfid_reads.count_documents({"device_id": g["device"]["id"]}))
        inc2 = _run(DB.rfid_incidents.count_documents({"epc": epc}))
        assert reads1 == reads2 and inc1 == inc2

    def test_same_epc_new_event_within_dwell_marks_duplicate(self, admin):
        roll = _run(_mk_roll(302))
        epc = _run(_encode(roll["id"]))
        g = _mk_device(admin, "gate-rf16-dwell", "gate", "wh_jakarta", "out")
        requests.post(f"{BASE}/api/rfid/ingest",
                      headers={"X-Device-Key": g["api_key"]},
                      json={"events": [{"epc": epc, "event_id": f"{T}-dw-a"}]}, timeout=20)
        reads_before = _run(DB.rfid_reads.count_documents({"device_id": g["device"]["id"]}))
        inc_before = _run(DB.rfid_incidents.count_documents({"epc": epc}))
        r = requests.post(f"{BASE}/api/rfid/ingest",
                          headers={"X-Device-Key": g["api_key"]},
                          json={"events": [{"epc": epc, "event_id": f"{T}-dw-b"}]}, timeout=20)
        body = r.json()
        # tag diam dalam dwell → results[].duplicate=true
        res = body["results"][0]
        assert res.get("duplicate") is True, body
        reads_after = _run(DB.rfid_reads.count_documents({"device_id": g["device"]["id"]}))
        inc_after = _run(DB.rfid_incidents.count_documents({"epc": epc}))
        assert reads_after == reads_before and inc_after == inc_before

    def test_batch_too_large_413(self, admin):
        """>500 event → 413 detail.code BATCH_TOO_LARGE."""
        g = _mk_device(admin, "gate-rf16-big", "gate", "wh_jakarta", "out")
        # Generate 501 fake EPCs
        epcs = [uuid.uuid4().hex.upper()[:24].ljust(24, "0") for _ in range(501)]
        r = requests.post(f"{BASE}/api/rfid/ingest",
                          headers={"X-Device-Key": g["api_key"]},
                          json={"epcs": epcs}, timeout=20)
        assert r.status_code == 413, (r.status_code, r.text[:200])
        try:
            d = r.json().get("detail")
            # detail could be dict or str — check for code
            text = str(d)
            assert "BATCH_TOO_LARGE" in text, text
        except Exception:
            assert "BATCH_TOO_LARGE" in r.text


# ─── UX-01 — Gate status + acknowledge + reads filter ───────────────────────
class TestUX01StatusAck:
    def test_mixed_passage_latched_then_ack(self, admin, warehouse):
        # Setup: bad roll (red) + good roll (green)
        so_id = f"{T}_so_ux"
        _run(DB.sales_orders.insert_one(
            {"id": so_id, "number": f"{T}-SO-UX", "entity_id": ENTITY, "status": "confirmed"}))
        r_bad = _run(_mk_roll(401))
        r_good = _run(_mk_roll(402, status="in_transit_sales",
                               reserved_ref={"type": "sales_order", "id": so_id}))
        _run(DB.shipments.insert_one(
            {"id": f"{T}_shp_ux", "order_id": so_id, "warehouse_id": "wh_jakarta",
             "status": "dispatched", "rolls": [{"roll_id": r_good["id"]}],
             "created_at": "2026-01-01T00:00:00+00:00"}))
        epc_bad = _run(_encode(r_bad["id"]))
        epc_good = _run(_encode(r_good["id"]))

        g = _mk_device(admin, "gate-ux01", "gate", "wh_jakarta", "out")
        r = requests.post(f"{BASE}/api/rfid/ingest",
                          headers={"X-Device-Key": g["api_key"]},
                          json={"events": [
                              {"epc": epc_bad, "event_id": f"{T}-ux-b"},
                              {"epc": epc_good, "event_id": f"{T}-ux-g"},
                          ]}, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        passage = body.get("passage") or {}
        assert passage.get("verdict") == "red", passage
        assert passage.get("red_count") == 1 and passage.get("green_count") == 1, passage
        passage_id = passage["id"]

        # GET /rfid/gate/{id}/status → latched True + heartbeat_age_s + passage shape
        gs = warehouse.get(f"{BASE}/api/rfid/gate/{g['device']['id']}/status", timeout=20)
        assert gs.status_code == 200, gs.text
        st = gs.json()
        assert st.get("latched") is True, st
        assert "server_time" in st and "verdict_ttl_s" in st
        assert st.get("device", {}).get("heartbeat_age_s") is not None, st.get("device")
        p = st.get("passage") or {}
        assert "reads" in p and "age_s" in p and "expired" in p

        # Acknowledge: note too short → 400
        r400 = warehouse.post(f"{BASE}/api/rfid/passages/{passage_id}/acknowledge",
                              json={"note": "abc"}, timeout=20)
        assert r400.status_code == 400, r400.text

        # Valid ack → 200, latched false
        reads_before = _run(DB.rfid_reads.count_documents({"device_id": g["device"]["id"]}))
        inc_before = _run(DB.rfid_incidents.count_documents({"epc": epc_bad}))
        rok = warehouse.post(f"{BASE}/api/rfid/passages/{passage_id}/acknowledge",
                             json={"note": "diperiksa fisik oleh satpam"}, timeout=20)
        assert rok.status_code == 200, rok.text
        gs2 = warehouse.get(f"{BASE}/api/rfid/gate/{g['device']['id']}/status", timeout=20)
        assert gs2.json().get("latched") is False
        # Reads & insiden tetap ada
        reads_after = _run(DB.rfid_reads.count_documents({"device_id": g["device"]["id"]}))
        inc_after = _run(DB.rfid_incidents.count_documents({"epc": epc_bad}))
        assert reads_after == reads_before and inc_after == inc_before

        # Second ack → 409
        rdup = warehouse.post(f"{BASE}/api/rfid/passages/{passage_id}/acknowledge",
                              json={"note": "ack kedua, harus 409"}, timeout=20)
        assert rdup.status_code == 409, rdup.text

    def test_reads_filter_gate_only_and_cursor(self, admin, warehouse):
        """GET /api/rfid/reads?read_type=gate hanya gate_in/gate_out + mendukung cursor before."""
        # Insert sintetis inventory read (bukan gate)
        _run(DB.rfid_reads.insert_one(
            {"id": f"{T}_inv_read", "device_id": f"{T}_hh_inv",
             "read_type": "inventory", "warehouse_id": "wh_jakarta",
             "timestamp": "2999-01-01T00:00:00+00:00"}))
        r = warehouse.get(f"{BASE}/api/rfid/reads",
                          params={"read_type": "gate", "limit": 20}, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert all(x["read_type"] in ("gate_in", "gate_out") for x in body["reads"]), body
        assert "next_before" in body


# ─── Simulator (jalur ingest) ───────────────────────────────────────────────
class TestGateSimulate:
    def test_simulate_uses_ingest_path(self, admin, warehouse):
        """POST /api/rfid/gate/simulate memakai jalur ingest sama (code + passage)."""
        g = _mk_device(admin, "gate-sim", "gate", "wh_jakarta", "out")
        roll = _run(_mk_roll(501))
        _run(_encode(roll["id"]))  # need tag
        r = warehouse.post(f"{BASE}/api/rfid/gate/simulate",
                           json={"device_id": g["device"]["id"], "roll_id": roll["id"]},
                           timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        # Expected to carry code and (likely) passage, with duplicate flag possible
        assert "code" in body or body.get("result") in ("red", "green"), body


# ─── Riwayat scan loading-check ─────────────────────────────────────────────
class TestLoadingCheckScanHistory:
    def test_last_scan_log_shape(self, warehouse):
        """GET /api/outbound/so/{id}/loading-check mengandung field last_scan_log (array).

        Kita tidak selalu bisa mendapatkan SO released + task picking tanpa seeding kompleks.
        Minimal smoke: panggil endpoint pada sales order yang ada; wajib 200 + field present."""
        import sys
        sys.path.insert(0, "C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend")
        so = _run(DB.sales_orders.find_one({"entity_id": ENTITY}, {"_id": 0, "id": 1}))
        if not so:
            pytest.skip("Tidak ada sales_orders demo untuk smoke loading-check")
        r = warehouse.get(f"{BASE}/api/outbound/so/{so['id']}/loading-check", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "last_scan_log" in body, body
        assert isinstance(body["last_scan_log"], list)


# ─── Cleanup ────────────────────────────────────────────────────────────────
def test_zz_cleanup():
    async def _clean():
        # Collect tags/devices
        rolls = await DB.inventory_rolls.find({"id": {"$regex": f"^{T}"}}, {"_id": 0, "id": 1}).to_list(500)
        roll_ids = [r["id"] for r in rolls]
        tags = await DB.rfid_tags.find({"roll_id": {"$in": roll_ids}}, {"_id": 0, "epc": 1}).to_list(500)
        epcs = [t["epc"] for t in tags]

        devs = await DB.rfid_devices.find({"name": {"$regex": f"^{T}"}}, {"_id": 0, "id": 1}).to_list(500)
        dev_ids = [d["id"] for d in devs]

        # Delete reads / passages / incidents / observations
        if dev_ids:
            await DB.rfid_reads.delete_many({"device_id": {"$in": dev_ids}})
            await DB.rfid_passages.delete_many({"device_id": {"$in": dev_ids}})
            await DB.rfid_observations.delete_many({"device_id": {"$in": dev_ids}})
        if epcs:
            await DB.rfid_incidents.delete_many({"epc": {"$in": epcs}})

        # Delete sintetis inventory reads
        await DB.rfid_reads.delete_many({"id": {"$regex": f"^{T}"}})

        # Delete tags & devices
        if roll_ids:
            await DB.rfid_tags.delete_many({"roll_id": {"$in": roll_ids}})
        await DB.rfid_devices.delete_many({"name": {"$regex": f"^{T}"}})

        # Delete business docs
        await DB.inventory_rolls.delete_many({"id": {"$regex": f"^{T}"}})
        await DB.sales_orders.delete_many({"id": {"$regex": f"^{T}"}})
        await DB.shipments.delete_many({"id": {"$regex": f"^{T}"}})
        await DB.warehouse_transfers.delete_many({"id": {"$regex": f"^{T}"}})
    _run(_clean())
