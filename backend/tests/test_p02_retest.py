"""P02 retest — items from iteration_175 review:
1. W01-L2 single_sku (Rak W01 Level 2) blocks other SKU; same SKU accepted; suggest excludes.
2. W01-L3 grade A only (Rak W01 Level 3) blocks grade B/BS; accepts grade A.
3. Warehouse combined storage_rules on WH-JKT -> POST /api/transfers to WH-JKT with violating roll -> 400 + reservation released.
4. PA dedicated: pr.warehouse_violations on dedicated warehouse for other entity -> non-empty.
5. Capacity race: cap=1 bin, 2 concurrent putaway -> exactly one 200, other 409.
6. fix-location valid reason -> location_corrections +1; restore.
7. in_transit_transfer & consumed status -> POST /api/inventory/putaway rejected 400.

All mutations are restored in finalizer/fixture.
"""
import os
import sys
import time
import asyncio
import threading
from pathlib import Path

import pytest
import requests

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://knhost.preview.emergentagent.com").rstrip("/")

ADMIN = ("admin@kainnusantara.id", "demo12345")
WHADMIN = ("whadmin@kainnusantara.id", "demo1234")

WH_JKT = "wh_jakarta"
WH_TGR_DEDICATED_KANDA = "wh_tangerang"  # dedicated to ent_kanda


def _login(email, pwd):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return r.json()["token"]


def _h(tok, entity=None):
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    if entity:
        h["X-Entity-Id"] = entity
    return h


@pytest.fixture(scope="module")
def admin_tok():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def whadmin_tok():
    return _login(*WHADMIN)


def _mongo():
    from pymongo import MongoClient
    cli = MongoClient(os.environ.get("MONGO_URL") or "mongodb://localhost:27017",
                      serverSelectionTimeoutMS=3000)
    return cli, cli[os.environ.get("DB_NAME") or "test_database"]


# ================= 1. Level-2 single_sku =================
class TestLevel2SingleSKU:
    def test_single_sku_blocks_other_and_suggest_excludes(self, admin_tok):
        """Put roll A (SKU X) into W01-L2-01, then try to place roll B (SKU Y) -> blocked.
        Same SKU as roll A should be accepted. Suggest for roll B should not include W01-L2-01."""
        bin_code = "W01-L2-01"
        # pick two available rolls with different product_ids
        rolls = requests.get(f"{BASE_URL}/api/inventory/rolls?warehouse_id=wh_jakarta&status=available&limit=200",
                             headers=_h(admin_tok), timeout=20).json()
        rolls = [r for r in rolls if r.get("grade") == "A" and r.get("product_id") and r.get("bin_id")]
        by_prod = {}
        for r in rolls:
            by_prod.setdefault(r["product_id"], []).append(r)
        prod_ids = [pid for pid in by_prod if len(by_prod[pid]) >= 1]
        if len(prod_ids) < 2:
            pytest.skip("need rolls of 2 different SKUs")
        roll_x = by_prod[prod_ids[0]][0]
        roll_y = by_prod[prod_ids[1]][0]
        snap = [(roll_x["id"], roll_x.get("bin_id")), (roll_y["id"], roll_y.get("bin_id"))]
        try:
            # place roll_x into W01-L2-01
            r1 = requests.post(f"{BASE_URL}/api/inventory/putaway", headers=_h(admin_tok),
                               json={"roll_id": roll_x["id"], "bin_id": bin_code}, timeout=20)
            assert r1.status_code == 200, r1.text

            # evaluate roll_y into same bin -> blocked by single_sku
            ev = requests.get(f"{BASE_URL}/api/inventory/putaway/evaluate",
                              params={"roll_id": roll_y["id"], "bin": bin_code},
                              headers=_h(admin_tok), timeout=15).json()
            assert ev["ok"] is False, f"expected block, got {ev}"
            assert any("satu SKU" in b or "khusus" in b.lower() for b in ev["blocks"]), ev["blocks"]

            # actual putaway -> 400
            rp = requests.post(f"{BASE_URL}/api/inventory/putaway", headers=_h(admin_tok),
                               json={"roll_id": roll_y["id"], "bin_id": bin_code}, timeout=20)
            assert rp.status_code == 400, rp.text

            # another roll SAME SKU as roll_x (different id) should be accepted
            same_sku_candidates = [r for r in by_prod[prod_ids[0]] if r["id"] != roll_x["id"]]
            if same_sku_candidates:
                roll_x2 = same_sku_candidates[0]
                snap.append((roll_x2["id"], roll_x2.get("bin_id")))
                ev2 = requests.get(f"{BASE_URL}/api/inventory/putaway/evaluate",
                                   params={"roll_id": roll_x2["id"], "bin": bin_code},
                                   headers=_h(admin_tok), timeout=15).json()
                assert ev2["ok"] is True, f"same-SKU should be allowed: {ev2}"

            # suggest for roll_y -> should NOT include W01-L2-01
            sg = requests.get(f"{BASE_URL}/api/inventory/putaway/suggest",
                              params={"roll_id": roll_y["id"]},
                              headers=_h(admin_tok), timeout=15).json()
            codes = [s["bin_code"] for s in sg.get("suggestions", [])]
            assert bin_code not in codes, f"single_sku bin leaked into suggestions: {codes}"
        finally:
            for rid, bid in snap:
                requests.post(f"{BASE_URL}/api/inventory/putaway", headers=_h(admin_tok),
                              json={"roll_id": rid, "bin_id": bid or ""}, timeout=15)


# ================= 2. Level-3 grade A only =================
class TestLevel3GradeA:
    def test_grade_a_only(self, admin_tok):
        """W01-L3 rules grades=[A]. Grade B/BS rejected; grade A accepted."""
        bin_code = "W01-L3-01"
        rolls = requests.get(f"{BASE_URL}/api/inventory/rolls?warehouse_id=wh_jakarta&status=available&limit=50",
                             headers=_h(admin_tok), timeout=15).json()
        a_roll = next((r for r in rolls if r.get("grade") == "A"), None)
        if not a_roll:
            pytest.skip("no grade A roll")
        rid = a_roll["id"]
        cli, db = _mongo()
        try:
            orig = db.inventory_rolls.find_one({"id": rid}, {"_id": 0, "grade": 1})
            orig_grade = (orig or {}).get("grade", "A")
            # grade BS -> blocked
            db.inventory_rolls.update_one({"id": rid}, {"$set": {"grade": "BS"}})
            ev = requests.get(f"{BASE_URL}/api/inventory/putaway/evaluate",
                              params={"roll_id": rid, "bin": bin_code},
                              headers=_h(admin_tok), timeout=15).json()
            assert ev["ok"] is False, ev
            assert any("Grade" in b or "grade" in b for b in ev["blocks"]), ev["blocks"]
            rp = requests.post(f"{BASE_URL}/api/inventory/putaway", headers=_h(admin_tok),
                               json={"roll_id": rid, "bin_id": bin_code}, timeout=15)
            assert rp.status_code == 400, rp.text

            # suggest for BS -> no W01-L3-* bins
            sg = requests.get(f"{BASE_URL}/api/inventory/putaway/suggest",
                              params={"roll_id": rid}, headers=_h(admin_tok), timeout=15).json()
            l3 = [s["bin_code"] for s in sg.get("suggestions", []) if s["bin_code"].startswith("W01-L3")]
            assert not l3, f"L3 bins leaked for grade BS: {l3}"

            # grade A -> ok
            db.inventory_rolls.update_one({"id": rid}, {"$set": {"grade": "A"}})
            ev2 = requests.get(f"{BASE_URL}/api/inventory/putaway/evaluate",
                               params={"roll_id": rid, "bin": bin_code},
                               headers=_h(admin_tok), timeout=15).json()
            assert ev2["ok"] is True, ev2
        finally:
            db.inventory_rolls.update_one({"id": rid}, {"$set": {"grade": orig_grade}})
            cli.close()


# ================= 3. Warehouse combined storage_rules via PUT profile =================
class TestWarehouseCombinedStorageRules:
    def test_transfer_rejected_and_reservation_released(self, admin_tok):
        """PATCH wh_tangerang storage_rules to require grade=['A']; create transfer with grade-B roll -> 400;
        rolls remain available (reservation released)."""
        wh_id = WH_JKT  # we use JKT because we have rolls here
        # snapshot current storage_rules
        wh = requests.get(f"{BASE_URL}/api/warehouses/{wh_id}", headers=_h(admin_tok), timeout=15).json()
        orig_sr = wh.get("storage_rules") or {"mode": "none", "categories": [], "grades": []}

        # find a grade-B roll in another warehouse (so we can transfer INTO wh_id)
        # Actually transfers.create requires source != dest, so pick wh_bandung as source if has rolls.
        # Simpler: patch storage_rules on wh_bandung (not JKT), transfer FROM JKT -> BDG.
        wh_id = "wh_bandung"
        wh = requests.get(f"{BASE_URL}/api/warehouses/{wh_id}", headers=_h(admin_tok), timeout=15).json()
        orig_sr = wh.get("storage_rules") or {"mode": "none", "categories": [], "grades": []}

        # find a roll in Jakarta with grade B (or set one)
        rolls = requests.get(f"{BASE_URL}/api/inventory/rolls?warehouse_id=wh_jakarta&status=available&limit=100",
                             headers=_h(admin_tok), timeout=20).json()
        pick = next((r for r in rolls if r.get("grade") == "A" and r.get("product_id")), None)
        if not pick:
            pytest.skip("no suitable roll")

        cli, db = _mongo()
        orig_grade = pick.get("grade", "A")
        try:
            # Temporarily set roll to grade B
            db.inventory_rolls.update_one({"id": pick["id"]}, {"$set": {"grade": "B"}})

            # Apply storage_rules combined grades=['A'] on BDG
            put1 = requests.patch(f"{BASE_URL}/api/warehouses/{wh_id}", headers=_h(admin_tok),
                                  json={"data": {"storage_rules": {"mode": "combined", "grades": ["A"],
                                                                   "categories": [], "fabric_types": []}}},
                                  timeout=15)
            assert put1.status_code == 200, put1.text

            # Create transfer JKT -> BDG with the grade-B roll
            payload = {
                "source_warehouse_id": "wh_jakarta",
                "dest_warehouse_id": wh_id,
                "items": [{"product_id": pick["product_id"], "qty": 1, "unit": "yard",
                           "roll_ids": [pick["id"]]}],
                "notes": "TEST_combined_rules",
            }
            r = requests.post(f"{BASE_URL}/api/transfers", headers=_h(admin_tok, entity="ent_ksc"),
                              json=payload, timeout=20)
            assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
            assert "grade" in r.text.lower() or "Grade" in r.text, r.text

            # Verify roll still available (reservation released)
            after = db.inventory_rolls.find_one({"id": pick["id"]}, {"_id": 0, "status": 1, "reserved_for": 1})
            assert after.get("status") == "available", f"roll not released: {after}"
        finally:
            # restore storage_rules
            requests.patch(f"{BASE_URL}/api/warehouses/{wh_id}", headers=_h(admin_tok),
                           json={"data": {"storage_rules": orig_sr}}, timeout=15)
            db.inventory_rolls.update_one({"id": pick["id"]}, {"$set": {"grade": orig_grade}})
            cli.close()


# ================= 4. PA dedicated: warehouse_violations =================
class TestPaDedicatedViolations:
    def test_dedicated_wh_rejects_other_entity_owner(self):
        """pr.warehouse_violations on wh_tangerang (dedicated to ent_kanda) with roll owned by ent_ksc."""
        import os as _os
        _os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
        from db import db as _db
        from services import placement_rules as pr

        async def run():
            wh = await _db.warehouses.find_one({"id": WH_TGR_DEDICATED_KANDA}, {"_id": 0})
            assert wh and wh.get("sharing_mode") == "dedicated"
            viol = await pr.warehouse_violations(
                wh, {"owner_entity_id": "ent_ksc", "grade": "A", "roll_no": "TEST"}, {"category": "Kain"})
            return viol

        viol = asyncio.get_event_loop().run_until_complete(run()) if not asyncio.get_event_loop().is_closed() else asyncio.run(run())
        assert viol, "expected violations for cross-entity dedicated warehouse"
        assert any("dedicated" in v.lower() or "khusus" in v.lower() or "lain" in v.lower() for v in viol), viol


# ================= 5. Capacity race =================
class TestCapacityRace:
    def test_concurrent_putaway_capacity_one(self, admin_tok):
        """Set a W01 bin's capacity_rolls=1 (empty) via PUT structure, then concurrent putaway for 2 rolls."""
        # Snapshot wh FROM DB (API response may strip fields)
        cli0, db0 = _mongo()
        try:
            whdoc = db0.warehouses.find_one({"id": WH_JKT}, {"_id": 0})
        finally:
            cli0.close()
        import copy
        orig_zones = copy.deepcopy(whdoc.get("zones") or [])
        zones = copy.deepcopy(orig_zones)

        # Find an empty W01-L4-* bin (level 4 usually unused) OR use an unused W01-L1 bin
        # pick an empty bin to modify capacity
        locs = requests.get(f"{BASE_URL}/api/warehouses/{WH_JKT}/locations",
                            headers=_h(admin_tok), timeout=15).json()
        empty_w01 = [b for b in locs["bins"]
                     if b["code"].startswith("W01-L4") and b.get("roll_count", 0) == 0]
        if not empty_w01:
            empty_w01 = [b for b in locs["bins"]
                         if b["code"].startswith("W01-") and b.get("roll_count", 0) == 0
                         and not b["code"].startswith("W01-L2") and not b["code"].startswith("W01-L3")]
        if not empty_w01:
            pytest.skip("no empty W01 bin found")
        target_bin = empty_w01[0]
        target_code = target_bin["code"]
        target_id = target_bin["bin_id"]

        # Mutate zones: set capacity_rolls=1 on target bin
        orig_cap = None
        for z in zones:
            for rk in z.get("racks") or []:
                for lv in rk.get("levels") or []:
                    for b in lv.get("bins") or []:
                        if b.get("id") == target_id:
                            orig_cap = b.get("capacity_rolls")
                            b["capacity_rolls"] = 1
        pt = requests.put(f"{BASE_URL}/api/warehouses/{WH_JKT}/structure",
                          headers=_h(admin_tok), json={"zones": zones}, timeout=15)
        assert pt.status_code == 200, pt.text

        # Pick 2 available rolls (different ids)
        rolls = requests.get(f"{BASE_URL}/api/inventory/rolls?warehouse_id=wh_jakarta&status=available&limit=20",
                             headers=_h(admin_tok), timeout=15).json()
        pool = [r for r in rolls if r.get("grade") == "A"][:2]
        if len(pool) < 2:
            # restore
            requests.put(f"{BASE_URL}/api/warehouses/{WH_JKT}/structure",
                         headers=_h(admin_tok), json={"zones": orig_zones}, timeout=15)
            pytest.skip("need 2 rolls")
        r1, r2 = pool[0], pool[1]
        snap = [(r1["id"], r1.get("bin_id")), (r2["id"], r2.get("bin_id"))]

        results = {}
        def _put(rid, key):
            try:
                rr = requests.post(f"{BASE_URL}/api/inventory/putaway", headers=_h(admin_tok),
                                   json={"roll_id": rid, "bin_id": target_code}, timeout=20)
                results[key] = (rr.status_code, rr.text[:200])
            except Exception as e:
                results[key] = (0, str(e))

        try:
            t1 = threading.Thread(target=_put, args=(r1["id"], "a"))
            t2 = threading.Thread(target=_put, args=(r2["id"], "b"))
            t1.start(); t2.start(); t1.join(); t2.join()
            codes = sorted([results["a"][0], results["b"][0]])
            # Expect exactly one 200 and the other 409 (or 400 full)
            assert 200 in codes, f"neither succeeded: {results}"
            assert any(c in (409, 400) for c in codes if c != 200), f"both succeeded: {results}"
        finally:
            # restore rolls
            for rid, bid in snap:
                requests.post(f"{BASE_URL}/api/inventory/putaway", headers=_h(admin_tok),
                              json={"roll_id": rid, "bin_id": bid or ""}, timeout=15)
            # restore capacity
            requests.put(f"{BASE_URL}/api/warehouses/{WH_JKT}/structure",
                         headers=_h(admin_tok), json={"zones": orig_zones}, timeout=15)


# ================= 6. fix-location increments corrections =================
class TestFixLocationIncrement:
    def test_valid_reason_increments_corrections(self, admin_tok):
        """fix-location with valid reason increments db.location_corrections count by 1."""
        orph = requests.get(f"{BASE_URL}/api/warehouses/{WH_JKT}/orphans",
                            headers=_h(admin_tok), timeout=15).json()
        rolls = orph if isinstance(orph, list) else (orph.get("rolls") or orph.get("items") or [])
        if not rolls:
            pytest.skip("no orphan rolls")
        roll = rolls[0]
        rid = roll["id"]
        orig_bin = roll.get("bin_id")

        cli, db = _mongo()
        try:
            before = db.location_corrections.count_documents({})
            # pick a valid empty bin in Jakarta
            locs = requests.get(f"{BASE_URL}/api/warehouses/{WH_JKT}/locations",
                                headers=_h(admin_tok), timeout=15).json()
            valid_bin = next((b for b in locs["bins"]
                              if b["code"].startswith("A1-") and b.get("roll_count", 0) == 0), None)
            if not valid_bin:
                valid_bin = next((b for b in locs["bins"] if b.get("roll_count", 0) == 0), None)
            assert valid_bin, "no empty bin"
            new_bin = valid_bin["code"]

            r = requests.post(f"{BASE_URL}/api/inventory/rolls/{rid}/fix-location",
                              headers=_h(admin_tok),
                              json={"bin_id": new_bin, "reason": "TEST_fix_orphan_valid"},
                              timeout=15)
            assert r.status_code == 200, r.text
            after = db.location_corrections.count_documents({})
            assert after == before + 1, f"corrections: before={before} after={after}"
        finally:
            # Restore roll back to orphan bin_id (direct DB update)
            db.inventory_rolls.update_one({"id": rid},
                                          {"$set": {"bin_id": orig_bin, "bin_code": ""}})
            cli.close()


# ================= 7. in_transit_transfer & consumed status =================
class TestStatusRejected:
    def test_in_transit_and_consumed_rejected(self, admin_tok):
        rolls = requests.get(f"{BASE_URL}/api/inventory/rolls?warehouse_id=wh_jakarta&status=available&limit=5",
                             headers=_h(admin_tok), timeout=15).json()
        if not rolls:
            pytest.skip("no rolls")
        rid = rolls[0]["id"]
        cli, db = _mongo()
        try:
            orig = db.inventory_rolls.find_one({"id": rid}, {"_id": 0, "status": 1})
            orig_status = orig.get("status", "available")
            for bad_status in ("in_transit_transfer", "consumed"):
                db.inventory_rolls.update_one({"id": rid}, {"$set": {"status": bad_status}})
                r = requests.post(f"{BASE_URL}/api/inventory/putaway", headers=_h(admin_tok),
                                  json={"roll_id": rid, "bin_id": "W01-L1-01"}, timeout=15)
                assert r.status_code == 400, f"[{bad_status}] expected 400, got {r.status_code}: {r.text}"
        finally:
            db.inventory_rolls.update_one({"id": rid}, {"$set": {"status": orig_status}})
            cli.close()
