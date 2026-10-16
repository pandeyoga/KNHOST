"""Iter-118 P10 — Opname & financial (WM-07, WM-08, FN-14, RF-17) + gate actions + passages history.

Tests the public HTTP /api surface via REACT_APP_BACKEND_URL. Service-level invariants are already
covered by audit/iterations/2026-10-08-P10-opname-financial/repro_p10.py (21/21). This file verifies
the HTTP contract and the new UX fields (`action`, GET /rfid/passages).

All test data uses prefix TEST_iter118_ and is cleaned by test_zz_cleanup.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import Any, Dict, Optional

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
WH = "wh_jakarta"
T = f"TEST_iter118_{uuid.uuid4().hex[:6]}"


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ─── Fixtures ───────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    s.headers.update({"X-Entity-Id": ENTITY, "Content-Type": "application/json"})
    r = s.post(f"{BASE}/api/auth/login",
               json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=20)
    assert r.status_code == 200, r.text
    tok = r.json().get("token") or r.json().get("access_token")
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def warehouse():
    s = requests.Session()
    s.headers.update({"X-Entity-Id": ENTITY, "Content-Type": "application/json"})
    r = s.post(f"{BASE}/api/auth/login",
               json={"email": "warehouse@kainnusantara.id", "password": "demo12345"}, timeout=20)
    assert r.status_code == 200, r.text
    tok = r.json().get("token") or r.json().get("access_token")
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


# ─── Helpers ────────────────────────────────────────────────────────────────
async def _mk_product(n: int, **kw) -> Dict[str, Any]:
    p = {"id": f"{T}_p{n}", "sku": f"{T.upper()}-{n}", "name": f"Audit P10 {n}", "unit": "meter", **kw}
    await DB.products.insert_one(dict(p))
    return p


async def _mk_roll(pid: str, n: int, qty: float, bin_id: str = "",
                   status: str = "available", cost: float = 100.0, wh: str = WH, **kw):
    doc = {"id": f"{T}_r{n}", "roll_no": f"{T}-R{n}", "product_id": pid,
           "owner_entity_id": ENTITY, "warehouse_id": wh, "bin_id": bin_id or None,
           "status": status, "length_remaining": float(qty), "length": float(qty),
           "unit": "meter", "unit_cost": cost, "created_at": "2026-01-01T00:00:00+00:00", **kw}
    await DB.inventory_rolls.insert_one(doc)
    return doc


def _create_session(client, name: str) -> str:
    r = client.post(f"{BASE}/api/cycle-count/sessions",
                    json={"warehouse_id": WH, "name": f"{T}-{name}"}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _add_item(client, sid: str, product_id: str, bin_id: str = ""):
    return client.post(f"{BASE}/api/cycle-count/sessions/{sid}/items",
                       json={"product_id": product_id, "bin_id": bin_id,
                             "owner_entity_id": ENTITY}, timeout=20)


def _count(client, sid: str, item_id: str, qty: float):
    return client.patch(f"{BASE}/api/cycle-count/sessions/{sid}/items/{item_id}",
                        json={"actual_qty": qty}, timeout=20)


# ─── WM-07 — Stock opname per bin + validasi ────────────────────────────────
class TestWM07StockOpnameHTTP:
    def test_full_two_bin_flow(self, admin):
        p = _run(_mk_product(1))
        _run(_mk_roll(p["id"], 1, 40, "binA"))
        _run(_mk_roll(p["id"], 2, 60, "binB"))

        sid = _create_session(admin, "wm07")

        # Add binA — expected_qty = 40 (bin scope, bukan 100 gudang)
        ra = _add_item(admin, sid, p["id"], "binA")
        assert ra.status_code == 200, ra.text
        ia = ra.json()
        assert ia["expected_qty"] == 40, ia

        # Duplicate (same bin) → 409
        rdup = _add_item(admin, sid, p["id"], "binA")
        assert rdup.status_code == 409, rdup.text

        # Mix level (warehouse-level empty bin) → 409
        rmix = _add_item(admin, sid, p["id"], "")
        assert rmix.status_code == 409, rmix.text

        # Add binB
        rb = _add_item(admin, sid, p["id"], "binB")
        assert rb.status_code == 200, rb.text
        ib = rb.json()
        assert ib["expected_qty"] == 60, ib

        # actual_qty = -1 → 400
        rn = _count(admin, sid, ia["id"], -1)
        assert rn.status_code in (400, 422), (rn.status_code, rn.text)

        # actual_qty = NaN → 400 (bukan 500)
        rnan = admin.patch(f"{BASE}/api/cycle-count/sessions/{sid}/items/{ia['id']}",
                           data='{"actual_qty": NaN}',
                           headers={"Content-Type": "application/json"}, timeout=20)
        assert rnan.status_code in (400, 422), (rnan.status_code, rnan.text)

        # Count: binA 30, binB 60 → submit → 1 discrepancy
        assert _count(admin, sid, ia["id"], 30).status_code == 200
        assert _count(admin, sid, ib["id"], 60).status_code == 200
        rs = admin.post(f"{BASE}/api/cycle-count/sessions/{sid}/submit", timeout=20)
        assert rs.status_code == 200, rs.text
        s = rs.json()
        assert len(s.get("discrepancies") or []) == 1, s

        # Approve → binA 30, binB 60 (no double reduction)
        ra = admin.post(f"{BASE}/api/cycle-count/sessions/{sid}/approve",
                        json={"reason": "audit"}, timeout=20)
        assert ra.status_code == 200, ra.text
        rolls_a = _run(DB.inventory_rolls.find(
            {"product_id": p["id"], "bin_id": "binA", "status": {"$ne": "consumed"}},
            {"_id": 0, "length_remaining": 1}).to_list(10))
        rolls_b = _run(DB.inventory_rolls.find(
            {"product_id": p["id"], "bin_id": "binB"},
            {"_id": 0, "length_remaining": 1}).to_list(10))
        assert sum(r["length_remaining"] for r in rolls_a) == 30
        assert sum(r["length_remaining"] for r in rolls_b) == 60

        # FN-14: journal Dr 5-9500 1000 / Cr 1-1300 1000 untuk kurang 10@100
        je = _run(DB.journal_entries.find_one(
            {"source_type": "cycle_count_variance", "source_id": f"{sid}:{ia['id']}"},
            {"_id": 0}))
        assert je, "journal_entries not found"
        has_dr = any(ln["account_code"] == "5-9500" and abs(ln["debit"] - 1000) < 0.01
                     for ln in je["lines"])
        has_cr = any(ln["account_code"] == "1-1300" and abs(ln["credit"] - 1000) < 0.01
                     for ln in je["lines"])
        assert has_dr and has_cr, je["lines"]

        # Approve ulang → 400, jurnal tidak double
        r2 = admin.post(f"{BASE}/api/cycle-count/sessions/{sid}/approve",
                        json={"reason": "audit"}, timeout=20)
        assert r2.status_code == 400, (r2.status_code, r2.text)
        n = _run(DB.journal_entries.count_documents(
            {"source_type": "cycle_count_variance",
             "source_id": {"$regex": f"^{sid}"}}))
        assert n == 1, n


# ─── FN-14 — surplus (WAC + zero-cost reason) ───────────────────────────────
class TestFN14Surplus:
    def test_surplus_wac_and_zero_cost(self, admin):
        # Surplus roll with cost
        p = _run(_mk_product(2))
        _run(_mk_roll(p["id"], 21, 50, "", cost=80.0))
        sid = _create_session(admin, "sur")
        it = _add_item(admin, sid, p["id"]).json()
        assert _count(admin, sid, it["id"], 55).status_code == 200
        assert admin.post(f"{BASE}/api/cycle-count/sessions/{sid}/submit", timeout=20).status_code == 200
        r = admin.post(f"{BASE}/api/cycle-count/sessions/{sid}/approve",
                       json={"reason": "audit"}, timeout=20)
        assert r.status_code == 200, r.text
        new_roll = _run(DB.inventory_rolls.find_one(
            {"product_id": p["id"], "id": {"$ne": f"{T}_r21"}}, {"_id": 0}))
        assert new_roll and float(new_roll.get("unit_cost") or 0) == 80, new_roll
        je = _run(DB.journal_entries.find_one(
            {"source_type": "cycle_count_variance", "source_id": f"{sid}:{it['id']}"},
            {"_id": 0}))
        assert je and any(ln["account_code"] == "1-1300" and abs(ln["debit"] - 400) < 0.01
                          for ln in je["lines"]), je["lines"] if je else None

        # Zero-cost product (no roll/cost reference)
        p0 = _run(_mk_product(3))
        sid0 = _create_session(admin, "zero")
        it0 = _add_item(admin, sid0, p0["id"]).json()
        assert _count(admin, sid0, it0["id"], 5).status_code == 200
        assert admin.post(f"{BASE}/api/cycle-count/sessions/{sid0}/submit",
                          timeout=20).status_code == 200

        # Approve without reason → 409, no roll created, session tetap submitted & tidak ter-lock
        r409 = admin.post(f"{BASE}/api/cycle-count/sessions/{sid0}/approve",
                         json={"reason": "audit"}, timeout=20)
        assert r409.status_code == 409, (r409.status_code, r409.text)
        assert _run(DB.inventory_rolls.count_documents({"product_id": p0["id"]})) == 0
        st = _run(DB.cycle_count_sessions.find_one({"id": sid0}, {"_id": 0}))
        assert st["status"] == "submitted" and not st.get("saga_lock"), st

        # Approve with zero_cost_reason → 200, tersimpan
        rok = admin.post(f"{BASE}/api/cycle-count/sessions/{sid0}/approve",
                        json={"reason": "audit",
                              "zero_cost_reason": "Barang sampel hibah, HPP nol"},
                        timeout=20)
        assert rok.status_code == 200, rok.text
        body = rok.json()
        adj = (body.get("items") or [{}])[0].get("adjustment") or {}
        assert adj.get("zero_cost_reason"), adj


# ─── WM-08 — picked ikut + drift keluar scope ───────────────────────────────
class TestWM08PickedAndDrift:
    def test_picked_in_scope_and_drift_409(self, admin):
        p = _run(_mk_product(4))
        _run(_mk_roll(p["id"], 41, 10, "binC", "available"))
        _run(_mk_roll(p["id"], 42, 30, "binC", "picked",
                      reserved_ref={"type": "sales_order", "id": f"{T}_so"}))
        sid = _create_session(admin, "picked")
        it = _add_item(admin, sid, p["id"], "binC").json()
        assert it.get("expected_qty") == 40, it
        assert _count(admin, sid, it["id"], 0).status_code == 200
        assert admin.post(f"{BASE}/api/cycle-count/sessions/{sid}/submit",
                          timeout=20).status_code == 200
        r = admin.post(f"{BASE}/api/cycle-count/sessions/{sid}/approve",
                       json={"reason": "audit"}, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        adj = (body.get("items") or [{}])[0].get("adjustment") or {}
        assert adj.get("requested") == -40 and adj.get("applied") == -40 \
               and adj.get("unresolved") == 0, adj
        left = sum(x["length_remaining"] for x in _run(DB.inventory_rolls.find(
            {"product_id": p["id"]}, {"_id": 0, "length_remaining": 1}).to_list(10)))
        assert left == 0, left

        # Drift keluar scope setelah submit → approve 409, roll tidak berubah
        p2 = _run(_mk_product(5))
        _run(_mk_roll(p2["id"], 51, 20, "binD"))
        sid2 = _create_session(admin, "drift")
        it2 = _add_item(admin, sid2, p2["id"], "binD").json()
        assert _count(admin, sid2, it2["id"], 15).status_code == 200
        assert admin.post(f"{BASE}/api/cycle-count/sessions/{sid2}/submit",
                          timeout=20).status_code == 200
        _run(DB.inventory_rolls.update_one(
            {"id": f"{T}_r51"}, {"$set": {"status": "in_transit_sales"}}))
        r409 = admin.post(f"{BASE}/api/cycle-count/sessions/{sid2}/approve",
                         json={"reason": "audit"}, timeout=20)
        assert r409.status_code == 409, (r409.status_code, r409.text)
        roll = _run(DB.inventory_rolls.find_one({"id": f"{T}_r51"},
                                                {"_id": 0, "length_remaining": 1}))
        assert roll["length_remaining"] == 20, roll
        st = _run(DB.cycle_count_sessions.find_one({"id": sid2}, {"_id": 0, "status": 1}))
        assert st["status"] == "submitted", st


# ─── Gate actions (ACTIONS map) + passage history ───────────────────────────
class TestGateActionsAndHistory:
    def _mk_device_and_key(self, admin, name: str, warehouse_id: str = WH,
                           direction: str = "out") -> Dict[str, Any]:
        r = admin.post(f"{BASE}/api/rfid/devices",
                      json={"name": f"{T}-{name}", "type": "gate",
                            "warehouse_id": warehouse_id, "direction": direction},
                      timeout=20)
        assert r.status_code == 200, r.text
        dev = r.json()
        r2 = admin.post(f"{BASE}/api/rfid/devices/{dev['id']}/api-key", timeout=20)
        key = r2.json().get("api_key") or r2.json().get("key")
        assert key, r2.json()
        requests.post(f"{BASE}/api/rfid/heartbeat",
                     headers={"X-Device-Key": key}, timeout=20)
        return {"device": dev, "api_key": key}

    def test_simulate_contains_action(self, admin, warehouse):
        """/api/rfid/gate/simulate menghasilkan `action` sesuai code."""
        g = self._mk_device_and_key(admin, "sim-action")
        # roll available tanpa dokumen → NO_DOCUMENT
        p = _run(_mk_product(10))
        roll = _run(_mk_roll(p["id"], 110, 10, status="available"))
        # encode tag
        import sys
        sys.path.insert(0, "C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend")
        from services import rfid_service as rs
        _run(rs.encode_tag(roll["id"], [ENTITY]))

        r = warehouse.post(f"{BASE}/api/rfid/gate/simulate",
                          json={"device_id": g["device"]["id"], "roll_id": roll["id"]},
                          timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        # action should be present on top-level and reflect NO_DOCUMENT guidance
        assert "action" in body, body
        action = body.get("action") or ""
        assert "surat jalan" in action.lower() or "tahan" in action.lower(), body

    def test_ingest_action_and_passages_history(self, admin, warehouse):
        """Ingest with mixed verdict → passage persisted with reads having `action`.
        GET /api/rfid/passages returns rows + acknowledged_by/at/note + reads with action."""
        g = self._mk_device_and_key(admin, "gate-hist")

        # Two rolls — one bad (no doc) and one good (dispatched shipment)
        p = _run(_mk_product(11))
        r_bad = _run(_mk_roll(p["id"], 111, 10, status="available"))
        so_id = f"{T}_so_hist"
        _run(DB.sales_orders.insert_one({"id": so_id, "number": f"{T}-SO-H",
                                        "entity_id": ENTITY, "status": "confirmed"}))
        r_good = _run(_mk_roll(p["id"], 112, 10, status="in_transit_sales",
                              reserved_ref={"type": "sales_order", "id": so_id}))
        _run(DB.shipments.insert_one(
            {"id": f"{T}_shp_h", "order_id": so_id, "warehouse_id": WH,
             "status": "dispatched", "rolls": [{"roll_id": r_good["id"]}],
             "created_at": "2026-01-01T00:00:00+00:00"}))

        import sys
        sys.path.insert(0, "C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend")
        from services import rfid_service as rs
        epc_bad = _run(rs.encode_tag(r_bad["id"], [ENTITY]))["epc"]
        epc_good = _run(rs.encode_tag(r_good["id"], [ENTITY]))["epc"]

        r = requests.post(f"{BASE}/api/rfid/ingest",
                          headers={"X-Device-Key": g["api_key"]},
                          json={"events": [
                              {"epc": epc_bad, "event_id": f"{T}-h-b"},
                              {"epc": epc_good, "event_id": f"{T}-h-g"},
                          ]}, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        # top-level results carry action
        actions = [res.get("action") for res in body.get("results") or []]
        assert all(actions), body
        passage = body.get("passage") or {}
        assert passage.get("verdict") == "red", passage
        passage_id = passage["id"]

        # GET /api/rfid/passages?device_id=
        rp = warehouse.get(f"{BASE}/api/rfid/passages",
                          params={"device_id": g["device"]["id"], "limit": 10},
                          timeout=20)
        assert rp.status_code == 200, rp.text
        body2 = rp.json()
        assert "passages" in body2 and "next_before" in body2, body2
        rows = body2["passages"]
        assert any(p["id"] == passage_id for p in rows), rows
        row = next(p for p in rows if p["id"] == passage_id)
        # shape: verdict, red_count/green_count, reads[].action, acknowledged_* (null before ack)
        assert row["verdict"] == "red"
        assert row["red_count"] == 1 and row["green_count"] == 1
        assert isinstance(row.get("reads"), list) and len(row["reads"]) == 2
        for rd in row["reads"]:
            assert rd.get("action"), rd
            assert "result" in rd and "roll_no" in rd
        # Before ack
        assert row.get("acknowledged_by") in (None, "", False) or row["acknowledged_by"] is None
        assert row.get("acknowledge_note") in (None, "", False) or row["acknowledge_note"] is None

        # Acknowledge → kemudian history memperlihatkan pengakuan + note
        ack = warehouse.post(f"{BASE}/api/rfid/passages/{passage_id}/acknowledge",
                            json={"note": "cek fisik oleh satpam utama"}, timeout=20)
        assert ack.status_code == 200, ack.text

        rp2 = warehouse.get(f"{BASE}/api/rfid/passages",
                           params={"device_id": g["device"]["id"]}, timeout=20)
        row2 = next(p for p in rp2.json()["passages"] if p["id"] == passage_id)
        assert row2.get("acknowledged_by"), row2
        assert row2.get("acknowledged_at"), row2
        assert "satpam" in (row2.get("acknowledge_note") or ""), row2

        # Filter by warehouse_id juga works
        rp3 = warehouse.get(f"{BASE}/api/rfid/passages",
                           params={"warehouse_id": WH, "limit": 5}, timeout=20)
        assert rp3.status_code == 200
        assert isinstance(rp3.json().get("passages"), list)


# ─── RF-17 — RFID cycle count (encode WIP + metrics) ────────────────────────
class TestRF17RfidCycleCount:
    def test_encode_wip_now_allowed(self, admin):
        """Encode tag untuk roll WIP sekarang diizinkan via POST /api/rfid/tags/encode."""
        p = _run(_mk_product(20))
        _run(_mk_roll(p["id"], 220, 10, status="wip"))
        r = admin.post(f"{BASE}/api/rfid/tags/encode",
                      json={"roll_id": f"{T}_r220"}, timeout=20)
        assert r.status_code == 200, r.text
        tag = r.json()
        assert tag.get("epc") and tag.get("roll_id") == f"{T}_r220", tag

    def test_rfid_cycle_count_metrics_http(self, admin):
        """POST /api/rfid/cycle-count/start → scan via verify-sessions/{id}/scan → complete."""
        # Build a new synthetic warehouse to isolate expected set
        wh = f"{T}_wh"
        _run(DB.warehouses.insert_one({"id": wh, "name": "Audit P10 WH",
                                        "entity_id": ENTITY, "owner_entity_id": ENTITY}))
        p = _run(_mk_product(21))
        _run(_mk_roll(p["id"], 261, 10, status="available", wh=wh))
        _run(_mk_roll(p["id"], 262, 10, status="wip", wh=wh))
        _run(_mk_roll(p["id"], 263, 10, status="damaged", wh=wh))
        _run(_mk_roll(p["id"], 264, 10, status="in_transit_sales", wh=wh))
        _run(_mk_roll(p["id"], 265, 10, status="available", wh=wh))  # untagged

        import sys
        sys.path.insert(0, "C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend")
        from services import rfid_service as rs
        epcs = []
        for n in (261, 262, 264):
            tag = _run(rs.encode_tag(f"{T}_r{n}", [ENTITY]))
            epcs.append(tag["epc"])

        rstart = admin.post(f"{BASE}/api/rfid/cycle-count/start",
                           json={"warehouse_id": wh}, timeout=20)
        assert rstart.status_code == 200, rstart.text
        sess = rstart.json()
        sid = sess["id"]
        expected_roll_ids = {e["roll_id"] for e in sess.get("expected") or []}
        # WIP tagged roll (r262) must be in expected; in_transit_sales (r264) must NOT
        assert f"{T}_r262" in expected_roll_ids, expected_roll_ids
        assert f"{T}_r264" not in expected_roll_ids, expected_roll_ids

        # Scan expected EPCs + 1 foreign EPC
        foreign = rs.generate_epc()
        scan_epcs = [e["epc"] for e in sess["expected"]] + [foreign]
        rscan = admin.post(f"{BASE}/api/rfid/verify-sessions/{sid}/scan",
                          json={"epcs": scan_epcs, "source": "manual"},
                          timeout=20)
        assert rscan.status_code == 200, rscan.text

        rcomp = admin.post(f"{BASE}/api/rfid/cycle-count/{sid}/complete",
                          json={"note": "audit"}, timeout=20)
        assert rcomp.status_code == 200, rcomp.text
        cc = rcomp.json()
        # accuracy < 100 karena ada 1 EPC asing
        assert cc.get("accuracy_pct") is not None and cc["accuracy_pct"] < 100, cc
        for k in ("eligible_count", "tagged_count", "untagged_count",
                  "tag_coverage_pct", "read_recall_pct", "extra_rate_pct",
                  "unresolved_count"):
            assert k in cc, (k, cc)
        assert cc["extra_rate_pct"] > 0, cc


# ─── Cleanup ────────────────────────────────────────────────────────────────
def test_zz_cleanup():
    async def _clean():
        # Sessions + journals
        sids = [s["id"] for s in await DB.cycle_count_sessions.find(
            {"name": {"$regex": f"^{T}"}}, {"_id": 0, "id": 1}).to_list(100)]
        for sid in sids:
            await DB.journal_entries.delete_many(
                {"source_type": "cycle_count_variance",
                 "source_id": {"$regex": f"^{sid}"}})
        await DB.cycle_count_sessions.delete_many({"id": {"$in": sids}})

        # Devices + their reads/passages/incidents
        devs = await DB.rfid_devices.find(
            {"name": {"$regex": f"^{T}"}}, {"_id": 0, "id": 1}).to_list(100)
        dev_ids = [d["id"] for d in devs]
        if dev_ids:
            await DB.rfid_reads.delete_many({"device_id": {"$in": dev_ids}})
            await DB.rfid_passages.delete_many({"device_id": {"$in": dev_ids}})
            await DB.rfid_observations.delete_many({"device_id": {"$in": dev_ids}})
        await DB.rfid_devices.delete_many({"name": {"$regex": f"^{T}"}})

        # Tags / rolls / products / sales / shipments / warehouses
        rolls = await DB.inventory_rolls.find(
            {"id": {"$regex": f"^{T}"}}, {"_id": 0, "id": 1}).to_list(500)
        roll_ids = [r["id"] for r in rolls]
        if roll_ids:
            tags = await DB.rfid_tags.find(
                {"roll_id": {"$in": roll_ids}}, {"_id": 0, "epc": 1}).to_list(500)
            await DB.rfid_tags.delete_many({"roll_id": {"$in": roll_ids}})
            await DB.rfid_incidents.delete_many({"epc": {"$in": [t["epc"] for t in tags]}})

        pids = [f"{T}_p{n}" for n in range(1, 30)]
        await DB.inventory_movements.delete_many({"product_id": {"$in": pids}})
        await DB.inventory_balances.delete_many({"product_id": {"$in": pids}})
        await DB.inventory_lots.delete_many({"product_id": {"$in": pids}})
        await DB.inventory_rolls.delete_many({"id": {"$regex": f"^{T}"}})
        await DB.inventory_rolls.delete_many({"product_id": {"$in": pids}})
        await DB.products.delete_many({"id": {"$in": pids}})
        await DB.sales_orders.delete_many({"id": {"$regex": f"^{T}"}})
        await DB.shipments.delete_many({"id": {"$regex": f"^{T}"}})
        await DB.rfid_verify_sessions.delete_many({"warehouse_id": f"{T}_wh"})
        await DB.rfid_cycle_counts.delete_many({"warehouse_id": f"{T}_wh"})
        await DB.warehouses.delete_many({"id": f"{T}_wh"})
    _run(_clean())
