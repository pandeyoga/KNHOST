"""Iter-115 P07b — GN-11 saga locks (admin), RF-04 warehouse policy + dispatch guard,
RF-06 manifest drift blocks dispatch, CX-12 OD done gating.

Tests go through the public preview URL for API routes, and use direct Mongo
inserts (TEST_* prefix) only for synthetic saga locks + CX-12 service-level calls.
All test fixtures are torn down in `test_zz_cleanup`.
"""
from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone, timedelta

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

def _base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            with open("C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/frontend/.env") as f:
                for ln in f:
                    if ln.startswith("REACT_APP_BACKEND_URL="):
                        v = ln.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except FileNotFoundError:
            pass
    assert v, "REACT_APP_BACKEND_URL not set"
    return v.rstrip("/")


BASE = _base()
MONGO = AsyncIOMotorClient("mongodb://127.0.0.1:27919")
DB = MONGO["knhost_data_audit_latest_pytest"]

CREDS = {
    "admin": ("admin@kainnusantara.id", "demo12345"),
    "manager": ("manager@kainnusantara.id", "demo12345"),
    "sales": ("sales@kainnusantara.id", "demo12345"),
    "finance": ("finance@kainnusantara.id", "demo12345"),
    "warehouse": ("warehouse@kainnusantara.id", "demo12345"),
}


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ─── auth helpers ───────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def tokens():
    out = {}
    for k, (email, pw) in CREDS.items():
        r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=15)
        assert r.status_code == 200, f"login {k}: {r.status_code} {r.text}"
        out[k] = r.json()["token"]
    return out


def _hdr(tok: str):
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc",
            "Content-Type": "application/json"}


# ─── synthetic fixtures ─────────────────────────────────────────────────────
TEST_TASK_STALE = "TEST_iter115_task_stale"
TEST_TASK_FRESH = "TEST_iter115_task_fresh"
TEST_TASK_EFFECT = "TEST_iter115_task_effect"
TEST_SHIP = "TEST_iter115_ship_effect"
TEST_SO_RF06 = "TEST_iter115_so_rf06"
TEST_OD_CX12 = "TEST_iter115_od"
TEST_SO_CX12 = "TEST_iter115_so_cx12"
TEST_SHIP_CX12_A = "TEST_iter115_ship_cx12_a"
TEST_SHIP_CX12_B = "TEST_iter115_ship_cx12_b"
TEST_DELI_CX12_A = "TEST_iter115_deli_cx12_a"
TEST_DELI_CX12_B = "TEST_iter115_deli_cx12_b"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@pytest.fixture(scope="module", autouse=True)
def seed_module():
    async def go():
        now = datetime.now(timezone.utc)
        # 30-min-old stale lock (no failed_at) — release should succeed
        await DB.wms_tasks.insert_one({
            "id": TEST_TASK_STALE, "entity_id": "ent_ksc", "flow_type": "outbound",
            "status": "picking", "task_number": "TEST_iter115/STALE",
            "saga_lock": {"action": "TEST_action", "by": "iter115",
                          "started_at": _iso(now - timedelta(minutes=30)),
                          "token": "TEST_tok_stale"}})
        # Fresh (<5 min) with no failed_at — release should 409
        await DB.wms_tasks.insert_one({
            "id": TEST_TASK_FRESH, "entity_id": "ent_ksc", "flow_type": "outbound",
            "status": "picking", "task_number": "TEST_iter115/FRESH",
            "saga_lock": {"action": "TEST_action", "by": "iter115",
                          "started_at": _iso(now - timedelta(minutes=1)),
                          "token": "TEST_tok_fresh"}})
        # Stale lock + downstream shipment created after lock.started_at
        locked_at = now - timedelta(minutes=30)
        await DB.wms_tasks.insert_one({
            "id": TEST_TASK_EFFECT, "entity_id": "ent_ksc", "flow_type": "outbound",
            "status": "picking", "task_number": "TEST_iter115/EFFECT",
            "saga_lock": {"action": "TEST_action", "by": "iter115",
                          "started_at": _iso(locked_at),
                          "token": "TEST_tok_effect"}})
        await DB.shipments.insert_one({
            "id": TEST_SHIP, "entity_id": "ent_ksc", "task_id": TEST_TASK_EFFECT,
            "order_id": "TEST_iter115_so", "shipment_no": "TEST_iter115/SH-01",
            "created_at": _iso(locked_at + timedelta(seconds=30))})
    _run(go())
    yield


# ─── GN-11 saga locks ───────────────────────────────────────────────────────
class TestGN11SagaLocks:
    def test_rbac_non_admin_forbidden(self, tokens):
        r = requests.get(f"{BASE}/api/saga-locks/wms_tasks/{TEST_TASK_STALE}/inspect",
                         headers=_hdr(tokens["manager"]), timeout=15)
        assert r.status_code == 403, r.text
        r2 = requests.post(f"{BASE}/api/saga-locks/wms_tasks/{TEST_TASK_STALE}/release",
                           headers=_hdr(tokens["manager"]),
                           json={"reason": "iter115 cuma coba lepas"}, timeout=15)
        assert r2.status_code == 403, r2.text

    def test_inspect_shape(self, tokens):
        r = requests.get(f"{BASE}/api/saga-locks/wms_tasks/{TEST_TASK_STALE}/inspect",
                         headers=_hdr(tokens["admin"]), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "lock" in d and "active" in d and "effects" in d
        assert d["active"] is False
        assert isinstance(d["effects"], list)

    def test_inspect_detects_effects(self, tokens):
        r = requests.get(f"{BASE}/api/saga-locks/wms_tasks/{TEST_TASK_EFFECT}/inspect",
                         headers=_hdr(tokens["admin"]), timeout=15)
        assert r.status_code == 200
        d = r.json()
        colls = {e["collection"] for e in d["effects"]}
        assert "shipments" in colls, f"expected shipments effect, got {d['effects']}"

    def test_release_reason_too_short(self, tokens):
        r = requests.post(f"{BASE}/api/saga-locks/wms_tasks/{TEST_TASK_STALE}/release",
                          headers=_hdr(tokens["admin"]), json={"reason": "short"}, timeout=15)
        assert r.status_code == 400, r.text

    def test_release_fresh_lock_conflict(self, tokens):
        r = requests.post(f"{BASE}/api/saga-locks/wms_tasks/{TEST_TASK_FRESH}/release",
                          headers=_hdr(tokens["admin"]),
                          json={"reason": "iter115 coba lepas kunci masih muda"}, timeout=15)
        assert r.status_code == 409, r.text
        assert "aktif" in str(r.json().get("detail", ""))

    def test_release_effects_require_acknowledge(self, tokens):
        r = requests.post(f"{BASE}/api/saga-locks/wms_tasks/{TEST_TASK_EFFECT}/release",
                          headers=_hdr(tokens["admin"]),
                          json={"reason": "iter115 effects tanpa ack"}, timeout=15)
        assert r.status_code == 409, r.text
        detail = r.json().get("detail")
        assert isinstance(detail, dict) and detail.get("code") == "SAGA_EFFECTS_PRESENT"
        assert detail.get("effects")

    def test_release_wrong_token_conflict(self, tokens):
        r = requests.post(f"{BASE}/api/saga-locks/wms_tasks/{TEST_TASK_STALE}/release",
                          headers=_hdr(tokens["admin"]),
                          json={"reason": "iter115 token salah token test",
                                "lock_token": "WRONG_TOKEN_XYZ"}, timeout=15)
        assert r.status_code == 409, r.text

    def test_release_success_and_audit(self, tokens):
        # STALE: no effects → success without ack
        r = requests.post(f"{BASE}/api/saga-locks/wms_tasks/{TEST_TASK_STALE}/release",
                          headers=_hdr(tokens["admin"]),
                          json={"reason": "iter115 release stale lock OK",
                                "lock_token": "TEST_tok_stale"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("released") is True

        async def verify():
            doc = await DB.wms_tasks.find_one({"id": TEST_TASK_STALE})
            assert "saga_lock" not in doc, "lock should be removed"
            # audit entry
            audit = await DB.audit_logs.find_one(
                {"action": "saga_lock_released", "entity_id": TEST_TASK_STALE},
                sort=[("timestamp", -1)])
            assert audit is not None
            payload = audit.get("payload") or audit.get("meta") or {}
            # audit stamp should contain lock + effects
            assert "lock" in payload or "effects" in payload or audit.get("reason")
        _run(verify())

    def test_release_with_acknowledge_effects(self, tokens):
        r = requests.post(f"{BASE}/api/saga-locks/wms_tasks/{TEST_TASK_EFFECT}/release",
                          headers=_hdr(tokens["admin"]),
                          json={"reason": "iter115 ack effects release",
                                "acknowledge_effects": True,
                                "lock_token": "TEST_tok_effect"}, timeout=15)
        assert r.status_code == 200, r.text


# ─── RF-04 warehouse loading-check policy ──────────────────────────────────
class TestRF04WarehousePolicy:
    WH = "wh_jakarta"
    SO = "so_003"  # has confirmed status, outbound tasks exist

    @pytest.fixture(autouse=True)
    def _ensure_restore(self):
        yield
        _run(DB.warehouses.update_one({"id": self.WH},
                                      {"$set": {"loading_check_policy": "optional"}}))

    def test_patch_policy_invalid(self, tokens):
        r = requests.patch(f"{BASE}/api/warehouses/{self.WH}",
                           headers=_hdr(tokens["admin"]),
                           json={"data": {"loading_check_policy": "bogus"}}, timeout=15)
        assert r.status_code == 400, r.text

    def test_patch_policy_valid(self, tokens):
        r = requests.patch(f"{BASE}/api/warehouses/{self.WH}",
                           headers=_hdr(tokens["admin"]),
                           json={"data": {"loading_check_policy": "required"}}, timeout=15)
        assert r.status_code == 200, r.text

        async def check():
            w = await DB.warehouses.find_one({"id": self.WH})
            assert w["loading_check_policy"] == "required"
        _run(check())

    def test_dispatch_blocked_when_required_and_no_lc(self, tokens):
        # Enable required
        requests.patch(f"{BASE}/api/warehouses/{self.WH}",
                       headers=_hdr(tokens["admin"]),
                       json={"data": {"loading_check_policy": "required"}}, timeout=15)
        # Clear any pre-existing loading_check on SO
        _run(DB.sales_orders.update_one({"id": self.SO}, {"$unset": {"loading_check": ""}}))
        # Pick a task for SO at this warehouse
        task = _run(DB.wms_tasks.find_one(
            {"order_id": self.SO, "warehouse_id": self.WH, "flow_type": "outbound",
             "status": {"$nin": ["dispatched", "cancelled", "completed"]}},
            {"_id": 0, "id": 1}))
        assert task, "no dispatchable task for SO-0003/wh_jakarta"
        r = requests.post(f"{BASE}/api/outbound/tasks/{task['id']}/dispatch",
                          headers=_hdr(tokens["admin"]), json={}, timeout=20)
        assert r.status_code == 400, r.text
        assert "mewajibkan Final Loading Check" in r.text

    def test_override_reason_too_short(self, tokens):
        r = requests.post(f"{BASE}/api/outbound/so/{self.SO}/loading-check/override",
                          headers=_hdr(tokens["admin"]), json={"reason": "no"}, timeout=15)
        assert r.status_code == 400, r.text

    def test_override_rbac_sales_forbidden(self, tokens):
        r = requests.post(f"{BASE}/api/outbound/so/{self.SO}/loading-check/override",
                          headers=_hdr(tokens["sales"]),
                          json={"reason": "iter115 sales mencoba override"}, timeout=15)
        assert r.status_code == 403, r.text

    def test_override_rbac_finance_forbidden(self, tokens):
        r = requests.post(f"{BASE}/api/outbound/so/{self.SO}/loading-check/override",
                          headers=_hdr(tokens["finance"]),
                          json={"reason": "iter115 finance mencoba override"}, timeout=15)
        assert r.status_code == 403, r.text

    def test_override_rbac_manager_ok_and_dispatch_passes(self, tokens):
        requests.patch(f"{BASE}/api/warehouses/{self.WH}",
                       headers=_hdr(tokens["admin"]),
                       json={"data": {"loading_check_policy": "required"}}, timeout=15)
        _run(DB.sales_orders.update_one({"id": self.SO}, {"$unset": {"loading_check": ""}}))
        # Ensure no open LC session
        _run(DB.rfid_verify_sessions.delete_many({"order_id": self.SO, "kind": "loading_check", "status": "open"}))
        r = requests.post(f"{BASE}/api/outbound/so/{self.SO}/loading-check/override",
                          headers=_hdr(tokens["manager"]),
                          json={"reason": "iter115 manager override OK"}, timeout=15)
        assert r.status_code == 200, r.text
        lc = r.json()
        assert lc.get("result") == "override"
        assert "manifest" in lc

        async def verify_persist():
            so = await DB.sales_orders.find_one({"id": self.SO})
            assert so["loading_check"]["result"] == "override"
            assert isinstance(so["loading_check"].get("manifest"), list)
        _run(verify_persist())


# ─── RF-06 — manifest drift blocks dispatch (service-level) ─────────────────
class TestRF06ManifestDrift:
    """Direct service-level test for dispatch_guard RF-06 branch."""

    def test_manifest_change_blocks_dispatch(self):
        async def go():
            from services import loading_check_service as lc
            # Create synthetic SO + 2 rolls
            now_dt = datetime.now(timezone.utc).isoformat()
            await DB.sales_orders.insert_one({
                "id": TEST_SO_RF06, "number": "TEST_iter115/SO-RF06",
                "entity_id": "ent_ksc", "status": "confirmed",
                "loading_check": {
                    "session_id": "TEST_sess", "result": "clean",
                    "matched": 1, "expected": 1, "missing": [], "extra": [],
                    "untagged_unresolved": [],
                    "manifest": [{"roll_id": "TEST_iter115_roll_A", "length": 100.0}],
                    "checked_at": now_dt}})
            # Case A: roll length changed — should block
            await DB.inventory_rolls.insert_many([
                {"id": "TEST_iter115_roll_A", "entity_id": "ent_ksc",
                 "reserved_ref": {"type": "sales_order", "id": TEST_SO_RF06},
                 "status": "committed", "length_remaining": 90.0,  # changed from 100
                 "roll_no": "TEST_RA", "product_id": "TEST_p"},
            ])
            raised = False
            try:
                await lc.dispatch_guard(TEST_SO_RF06, warehouse_id=None)
            except Exception as e:
                raised = True
                assert "Alokasi/roll berubah sesudah Final Loading Check" in str(e), str(e)
            assert raised, "dispatch_guard should raise on length drift"

            # Case B: restore length to 100 and add NEW reserved roll — should also block
            await DB.inventory_rolls.update_one(
                {"id": "TEST_iter115_roll_A"}, {"$set": {"length_remaining": 100.0}})
            await DB.inventory_rolls.insert_one({
                "id": "TEST_iter115_roll_B", "entity_id": "ent_ksc",
                "reserved_ref": {"type": "sales_order", "id": TEST_SO_RF06},
                "status": "reserved", "length_remaining": 50.0,
                "roll_no": "TEST_RB", "product_id": "TEST_p"})
            raised = False
            try:
                await lc.dispatch_guard(TEST_SO_RF06, warehouse_id=None)
            except Exception as e:
                raised = True
                assert "Alokasi/roll berubah" in str(e), str(e)
            assert raised, "dispatch_guard should raise on new reserved roll"

            # Case C: already-shipped rolls (status in_transit_sales) should NOT count
            await DB.inventory_rolls.update_one(
                {"id": "TEST_iter115_roll_B"},
                {"$set": {"status": "in_transit_sales"}})
            # Now only roll_A is in EXPECTED_STATUSES, with length 100 == manifest → should pass
            await lc.dispatch_guard(TEST_SO_RF06, warehouse_id=None)
        _run(go())


# ─── CX-12 — special order done when all shipments delivered ───────────────
class TestCX12FulfillmentComplete:
    def test_on_delivered_gates_until_all_shipments_delivered(self):
        async def go():
            from services import special_order_phase2 as p2
            now_dt = datetime.now(timezone.utc).isoformat()
            # Create SO + 2 shipments + OD linked to SO
            await DB.sales_orders.insert_one({
                "id": TEST_SO_CX12, "number": "TEST_iter115/SO-CX12",
                "entity_id": "ent_ksc", "status": "shipped"})
            await DB.shipments.insert_many([
                {"id": TEST_SHIP_CX12_A, "order_id": TEST_SO_CX12,
                 "entity_id": "ent_ksc", "status": "dispatched",
                 "shipment_no": "TEST_iter115/SH-A", "created_at": now_dt},
                {"id": TEST_SHIP_CX12_B, "order_id": TEST_SO_CX12,
                 "entity_id": "ent_ksc", "status": "dispatched",
                 "shipment_no": "TEST_iter115/SH-B", "created_at": now_dt},
            ])
            await DB.special_orders.insert_one({
                "id": TEST_OD_CX12, "number": "TEST_iter115/OD-01",
                "entity_id": "ent_ksc", "status": "shipped",
                "linked_sales_order_id": TEST_SO_CX12,
                "status_history": []})

            # Case A: no deliveries → fulfillment_complete False, on_delivered no-op
            assert await p2.fulfillment_complete(TEST_SO_CX12) is False
            await p2.on_delivered(TEST_SO_CX12)
            od = await DB.special_orders.find_one({"id": TEST_OD_CX12})
            assert od["status"] == "shipped"

            # Case B: only first shipment delivered → still False
            await DB.logistics_deliveries.insert_one({
                "id": TEST_DELI_CX12_A, "order_id": TEST_SO_CX12,
                "entity_id": "ent_ksc", "status": "delivered",
                "shipment_ids": [TEST_SHIP_CX12_A],
                "created_at": now_dt})
            assert await p2.fulfillment_complete(TEST_SO_CX12) is False
            await p2.on_delivered(TEST_SO_CX12)
            od = await DB.special_orders.find_one({"id": TEST_OD_CX12})
            assert od["status"] == "shipped", "should stay shipped until all delivered"

            # Case C: second shipment delivered via another delivery (e.g. pickup handover) → True → done
            await DB.logistics_deliveries.insert_one({
                "id": TEST_DELI_CX12_B, "order_id": TEST_SO_CX12,
                "entity_id": "ent_ksc", "status": "completed",
                "shipment_ids": [TEST_SHIP_CX12_B],
                "created_at": now_dt})
            assert await p2.fulfillment_complete(TEST_SO_CX12) is True
            await p2.on_delivered(TEST_SO_CX12)
            od = await DB.special_orders.find_one({"id": TEST_OD_CX12})
            assert od["status"] == "done", f"expected done, got {od['status']}"
        _run(go())


# ─── cleanup ────────────────────────────────────────────────────────────────
def test_zz_cleanup():
    async def go():
        await DB.wms_tasks.delete_many({"id": {"$in": [TEST_TASK_STALE, TEST_TASK_FRESH, TEST_TASK_EFFECT]}})
        await DB.shipments.delete_many({"id": {"$in": [TEST_SHIP, TEST_SHIP_CX12_A, TEST_SHIP_CX12_B]}})
        await DB.inventory_rolls.delete_many({"id": {"$regex": "^TEST_iter115"}})
        await DB.sales_orders.delete_many({"id": {"$in": [TEST_SO_RF06, TEST_SO_CX12]}})
        await DB.special_orders.delete_many({"id": TEST_OD_CX12})
        await DB.logistics_deliveries.delete_many({"id": {"$in": [TEST_DELI_CX12_A, TEST_DELI_CX12_B]}})
        # Clean override we may have left on SO-0003
        await DB.sales_orders.update_one({"id": "so_003"}, {"$unset": {"loading_check": ""}})
        # Restore warehouse policy
        await DB.warehouses.update_one({"id": "wh_jakarta"},
                                       {"$set": {"loading_check_policy": "optional"}})
        # Prune audit entries created by this iteration
        await DB.audit_logs.delete_many({"action": "saga_lock_released",
                                         "entity_id": {"$in": [TEST_TASK_STALE, TEST_TASK_EFFECT]}})
        await DB.audit_logs.delete_many({"action": "loading_check_override",
                                         "reason": {"$regex": "iter115"}})
    _run(go())
