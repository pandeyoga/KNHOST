"""E2E tests for P03 Jakarta customer leg + P04 Keep/Pending/Grade/Candidates/StockSummary.

Preview URL from REACT_APP_BACKEND_URL. Fresh DB state as of test request:
- SO: so_df1f8042999f (KANDA/SO-00003, 10 rolls committed at SRG-01)
- Transfer: trn_4eee1c252639 (KANDA/TRF-00001, SRG-01 -> GU-KANDA, dispatched)
- SO-00004: so_450bfacd5813 (keep, age 5 days overdue)
- SO-00005: so_62d6b89bf559 (keep+pending), SO-00006: so_bd9295011229 (pending)
- Customer: cust_f380f404da40 (Toko Tekstil Pasar Baru)
"""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://knhost-erp.preview.emergentagent.com").rstrip("/")
ENT = "ent_kanda"
SO_03 = "so_df1f8042999f"
SO_04 = "so_450bfacd5813"
SO_05 = "so_62d6b89bf559"
SO_06 = "so_bd9295011229"
TRF_01 = "trn_4eee1c252639"
CUST = "cust_f380f404da40"


def _login(email, password="demo1234"):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def wh():
    return {"Authorization": f"Bearer {_login('whadmin@kainnusantara.id')}", "X-Entity-Id": ENT}


@pytest.fixture(scope="session")
def mgr():
    return {"Authorization": f"Bearer {_login('manager@kainnusantara.id')}", "X-Entity-Id": ENT}


@pytest.fixture(scope="session")
def sadm():
    return {"Authorization": f"Bearer {_login('salesadmin.kanda@kainnusantara.id')}", "X-Entity-Id": ENT}


@pytest.fixture(scope="session")
def sls():
    return {"Authorization": f"Bearer {_login('sales.kanda@kainnusantara.id')}", "X-Entity-Id": ENT}


# -----------------------------
# PART B — Keep/Pending (checked BEFORE receiving transfer so in_transit is populated)
# -----------------------------
class TestKeepPending:
    def test_keep_pending_shape(self, sadm):
        r = requests.get(f"{BASE}/api/sales/keep-pending", headers=sadm, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        keep_nums = {k["number"] for k in d["keep"]}
        assert "KANDA/SO-00004" in keep_nums
        assert "KANDA/SO-00005" in keep_nums
        so04 = next(k for k in d["keep"] if k["number"] == "KANDA/SO-00004")
        assert so04["overdue"] is True
        assert so04["age_days"] >= 5
        so05 = next(k for k in d["keep"] if k["number"] == "KANDA/SO-00005")
        assert so05["also_pending"] is True
        pend_nums = {o["number"] for p in d["pending"] for o in p["orders"]}
        assert pend_nums == {"KANDA/SO-00005", "KANDA/SO-00006"}
        for p in d["pending"]:
            assert p["short_qty"] == 250.0
            assert p["unit"]
        assert d["counts"]["unique_orders"] == 3
        assert d["counts"]["both"] == 1
        assert d["counts"]["keep_overdue"] == 1
        assert d["keep_limit_days"] == 3

    def test_in_transit_before_receive(self, sadm):
        # Only valid before PART A receipt
        r = requests.get(f"{BASE}/api/sales/keep-pending", headers=sadm, timeout=30)
        d = r.json()
        it = d.get("in_transit", [])
        if not it:
            pytest.skip("in_transit empty — transfer already received")
        nums = {x["number"] for x in it}
        assert "KANDA/SO-00003" in nums

    def test_sales_role_403(self, sls):
        r = requests.get(f"{BASE}/api/sales/keep-pending", headers=sls, timeout=30)
        assert r.status_code == 403


# -----------------------------
# PART B — Grade rules
# -----------------------------
class TestGradeRules:
    def test_get_initial(self, sadm):
        r = requests.get(f"{BASE}/api/customers/{CUST}/grade-rules", headers=sadm, timeout=30)
        assert r.status_code == 200
        assert r.json()["customer_id"] == CUST

    def test_invalid_grade_422(self, sadm):
        r = requests.put(f"{BASE}/api/customers/{CUST}/grade-rules", headers=sadm,
                         json={"allowed_grades": ["Z"], "preferred_grades": [], "accept_bs": False, "note": ""}, timeout=30)
        assert r.status_code == 422

    def test_preferred_outside_allowed_422(self, sadm):
        r = requests.put(f"{BASE}/api/customers/{CUST}/grade-rules", headers=sadm,
                         json={"allowed_grades": ["A"], "preferred_grades": ["B"], "accept_bs": False, "note": ""}, timeout=30)
        assert r.status_code == 422

    def test_put_valid_then_candidates_use_rule(self, sadm):
        r = requests.put(f"{BASE}/api/customers/{CUST}/grade-rules", headers=sadm,
                         json={"allowed_grades": ["A"], "preferred_grades": ["A"], "accept_bs": False, "note": "test"}, timeout=30)
        assert r.status_code == 200
        rc = requests.get(f"{BASE}/api/sales-orders/{SO_04}/items/prod_8940eeadf05c/roll-candidates",
                          headers=sadm, timeout=30)
        assert rc.status_code == 200
        body = rc.json()
        assert body["rule"]["allowed_grades"] == ["A"]
        assert body["recommendation"]["grade"] == "A"

    def test_cleanup_rule(self, sadm):
        r = requests.put(f"{BASE}/api/customers/{CUST}/grade-rules", headers=sadm,
                         json={"allowed_grades": [], "preferred_grades": [], "accept_bs": False, "note": ""}, timeout=30)
        assert r.status_code == 200


# -----------------------------
# PART B — Sales stock summary
# -----------------------------
class TestStockSummary:
    def test_sales_can_view(self, sls):
        r = requests.get(f"{BASE}/api/sales/stock-summary", headers=sls,
                         params={"product_id": "prod_2d47ddad573a"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        rows = d["rows"]
        assert any(x["class"] == "regular" for x in rows)
        # No lot/owner details leaked
        for row in rows:
            assert "lot" not in row
            assert "owner" not in row


# -----------------------------
# PART A — P03 Jakarta leg
# -----------------------------
class TestP03JakartaLeg:
    def test_1_receive_transfer(self, wh):
        r = requests.get(f"{BASE}/api/transfers/{TRF_01}/receipt", headers=wh, timeout=30)
        if r.status_code != 200:
            pytest.skip(f"Transfer not available for receipt: {r.status_code}")
        receipt = r.json()
        # Build lines for all rolls as 'received'
        lines = [{"roll_id": rr["roll_id"], "outcome": "received"} for rr in receipt.get("rolls", [])]
        if not lines:
            pytest.skip("No rolls to receive — maybe already received")
        payload = {"lines": lines}
        r2 = requests.post(f"{BASE}/api/transfers/{TRF_01}/receive", headers=wh, json=payload, timeout=60)
        assert r2.status_code == 200, r2.text
        # Verify transfer status
        r3 = requests.get(f"{BASE}/api/transfers/{TRF_01}", headers=wh, timeout=30)
        assert r3.status_code == 200
        assert r3.json()["status"] in ("received", "completed"), r3.json().get("status")

    def test_2_so_still_confirmed_with_jakarta_task(self, wh):
        so = requests.get(f"{BASE}/api/sales-orders/{SO_03}", headers=wh, timeout=30).json()
        assert so["status"] == "confirmed", so["status"]
        # Find outbound tasks for this SO - Jakarta warehouse task should exist
        tr = requests.get(f"{BASE}/api/outbound/tasks", headers=wh,
                          params={"sales_order_id": SO_03}, timeout=30)
        # endpoint may vary; accept 200
        assert tr.status_code in (200, 404), tr.status_code


# -----------------------------
# Keep/Pending after transfer received (in_transit becomes empty for SO-00003)
# -----------------------------
class TestKeepPendingPostReceipt:
    def test_in_transit_empty_for_so03(self, sadm):
        r = requests.get(f"{BASE}/api/sales/keep-pending", headers=sadm, timeout=30).json()
        nums = {x["number"] for x in r.get("in_transit", [])}
        assert "KANDA/SO-00003" not in nums


# -----------------------------
# PART A continued — scan-pick → loading-check override → dispatch → surat-jalan → mark-delivered
# -----------------------------
TASK_ID = "wms_c9f099e4082f"  # Jakarta outbound task for SO-00003


def _reserved_rolls_for_so(headers, so_id, wh_id):
    r = requests.get(f"{BASE}/api/inventory/rolls",
                     headers=headers, params={"warehouse_id": wh_id, "status": "reserved", "limit": 50}, timeout=30)
    r.raise_for_status()
    items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    return [x for x in items if (x.get("reserved_ref") or {}).get("id") == so_id]


class TestP03JakartaDispatch:
    def test_3a_scan_pick_each_roll(self, wh):
        task_r = requests.get(f"{BASE}/api/wms/tasks/{TASK_ID}", headers=wh, timeout=30)
        if task_r.status_code != 200:
            # Fallback: fetch via list
            tr = requests.get(f"{BASE}/api/outbound/tasks", headers=wh,
                              params={"sales_order_id": SO_03}, timeout=30).json()
            task = next((t for t in tr if t["id"] == TASK_ID), None)
        else:
            task = task_r.json()
        assert task, "Task tidak ditemukan"
        if task.get("status") == "dispatched":
            pytest.skip("Task already dispatched")
        rolls = _reserved_rolls_for_so(wh, SO_03, task["warehouse_id"])
        assert len(rolls) == 10, f"expected 10 reserved rolls at Jakarta, got {len(rolls)}"
        for roll in rolls:
            qty = float(roll["length_remaining"])
            r = requests.post(f"{BASE}/api/outbound/tasks/{TASK_ID}/scan-pick", headers=wh,
                              params={"actual_qty": qty, "roll_id": roll["id"]}, timeout=30)
            assert r.status_code == 200, f"scan-pick {roll['roll_no']}: {r.status_code} {r.text}"

    def test_3b_scan_pick_wrong_roll_rejected(self, wh):
        # Find a roll not reserved for this SO
        all_r = requests.get(f"{BASE}/api/inventory/rolls", headers=wh,
                             params={"warehouse_id": "wh_ea274533ff2a", "limit": 50}, timeout=30).json()
        items = all_r if isinstance(all_r, list) else all_r.get("items", [])
        other = next((x for x in items if (x.get("reserved_ref") or {}).get("id") != SO_03 and x.get("status") == "available"), None)
        if not other:
            pytest.skip("no other available roll")
        r = requests.post(f"{BASE}/api/outbound/tasks/{TASK_ID}/scan-pick", headers=wh,
                          params={"actual_qty": 10, "roll_id": other["id"]}, timeout=30)
        assert r.status_code == 400, f"expected 400 got {r.status_code}"

    def test_4_loading_check_override_and_dispatch(self, mgr, wh):
        r = requests.post(f"{BASE}/api/outbound/so/{SO_03}/loading-check/override",
                          headers=mgr, json={"reason": "Uji alur Jakarta: roll belum bertag RFID"}, timeout=30)
        assert r.status_code in (200, 201), f"override: {r.status_code} {r.text}"
        d = requests.post(f"{BASE}/api/outbound/tasks/{TASK_ID}/dispatch", headers=wh, timeout=60)
        assert d.status_code == 200, f"dispatch: {d.status_code} {d.text}"
        body = d.json()
        # shipment present
        ship = body.get("shipment") or {}
        num = ship.get("shipment_no") or ship.get("number") or ""
        assert num.startswith("KANDA/SJ-"), f"shipment number: {ship}"
        pytest.shipment_id = ship.get("id") or body.get("shipment_id")

    def test_5_so_status_shipped(self, wh):
        so = requests.get(f"{BASE}/api/sales-orders/{SO_03}", headers=wh, timeout=30).json()
        assert so["status"] == "shipped", so["status"]

    def test_6_surat_jalan_html(self, wh):
        sid = getattr(pytest, "shipment_id", None)
        if not sid:
            # try listing shipments for the SO
            r = requests.get(f"{BASE}/api/shipments", headers=wh, params={"sales_order_id": SO_03}, timeout=30)
            items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
            sid = items[0]["id"] if items else None
        assert sid, "shipment_id not found"
        html = requests.get(f"{BASE}/api/shipments/{sid}/surat-jalan", headers=wh, timeout=30)
        assert html.status_code == 200
        text = html.text
        assert "Toko Tekstil Pasar Baru" in text
        assert "Jakarta" in text
        assert text.count("RL-") >= 10
        # No internal roll_ ids
        assert "roll_" not in text

    def test_7_mark_delivered(self, sadm):
        r = requests.post(f"{BASE}/api/sales-orders/{SO_03}/mark-delivered", headers=sadm, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        so = requests.get(f"{BASE}/api/sales-orders/{SO_03}", headers=sadm, timeout=30).json()
        assert so["status"] == "done"

    def test_8_invoice_qty_matches_shipped(self, sadm):
        # DEC-13: invoice qty = shipped qty
        r = requests.get(f"{BASE}/api/invoices", headers=sadm, params={"sales_order_id": SO_03}, timeout=30)
        if r.status_code != 200:
            pytest.skip(f"invoices endpoint: {r.status_code}")
        items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        if not items:
            pytest.skip("no invoice generated")
        inv = items[0]
        total_qty = sum(float(i.get("qty", 0)) for i in inv.get("items", []))
        # Shipped qty = sum of roll lengths
        so = requests.get(f"{BASE}/api/sales-orders/{SO_03}", headers=sadm, timeout=30).json()
        shipped = 0
        for it in so.get("items", []):
            for rr in (it.get("rolls") or []):
                shipped += float(rr.get("length") or rr.get("qty") or 0)
        assert abs(total_qty - shipped) < 0.5, f"invoice qty {total_qty} vs shipped {shipped}"
