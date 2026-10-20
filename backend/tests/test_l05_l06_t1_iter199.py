"""T1 iter 199 — Verify fixes for issues reported in iter198.

Scope:
1. Cutting receive: CUTTING_DEST_OTHER_OWNER, same/shared warehouse OK, idempotent, 409 for missing roll.
2. Cutting desk rows include roll_owner_entity_id; locations include sharing_mode/entity_ids.
3. sample_admin has sample_order.create (catalogue preview, soft, sample SO).
4. sample_admin cannot create a regular SO (403 on order.create).
5. POST /api/sales-orders with catalogue.soft_product_id='' => 400 "Pilih satu warna soft".
6. GET /api/sample-orders/stats/summary paid_value excludes cancelled.
7. Logistics dashboard active[] rows include qc_status.
8. Notification label for so_qc_requested goes to qc@ with link="inspections".
9. GET /api/sample-orders/catalogue/templates returns only templates with free stock for the entity.
"""
import os
import time

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ENT_KSC = "ent_ksc"
ENT_KANDA = "ent_kanda"
CUST, ADDR, PROD = "cust_butik_bali", "addr_002", "prod_batik_mega"

TAG = "T1I199"


def _login(email, pw="demo12345"):
    DB.login_attempts.delete_many({})
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT_KSC}


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def sampleadmin():
    return _login("sampleadmin@kainnusantara.id")


@pytest.fixture(scope="module")
def finance():
    return _login("finance@kainnusantara.id")


@pytest.fixture(scope="module")
def created_sos(admin):
    ids = []
    yield ids
    for sid in ids:
        try:
            requests.post(f"{BASE}/sales-orders/{sid}/cancel", json={"reason": f"{TAG} cleanup"},
                          headers=admin, timeout=60)
        except Exception:
            pass
        DB.notifications.delete_many({"ref": {"$regex": f"^so_qc:{sid}"}})
        DB.wms_tasks.delete_many({"order_id": sid, "task_subtype": "sample_cut"})


# ────────────────────────────────────────────────────────────────────────
# 2 + 7: locations / desk shape / deliveries qc_status
# ────────────────────────────────────────────────────────────────────────
def test_cutting_locations_include_sharing(admin):
    r = requests.get(f"{BASE}/cutting/locations", headers=admin, timeout=30)
    assert r.status_code == 200
    rows = r.json()
    assert rows
    sample = [x for x in rows if x.get("sharing_mode") == "dedicated"]
    assert sample, "no dedicated warehouses in cutting locations list"
    assert all("sharing_mode" in x and "entity_ids" in x for x in rows)


def test_cutting_desk_rows_have_roll_owner(sampleadmin):
    r = requests.get(f"{BASE}/cutting/desk", headers=sampleadmin, timeout=30)
    assert r.status_code == 200, r.text[:200]
    queues = r.json()["queues"]
    assert [q["key"] for q in queues] == ["awaiting_internal", "to_cut", "to_receive", "ready"]
    for q in queues:
        for row in q["rows"]:
            assert "roll_owner_entity_id" in row, f"missing roll_owner_entity_id in queue {q['key']}"


def test_logistics_dashboard_active_rows_have_qc_status(admin):
    r = requests.get(f"{BASE}/logistics/dashboard", headers=admin, timeout=30)
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    assert "active" in body
    # qc_status key must be present on every active row (empty string allowed)
    for row in body["active"]:
        assert "qc_status" in row, f"missing qc_status: {row.get('id')}"
        assert row["qc_status"] in ("", "required", "passed", "failed")


# ────────────────────────────────────────────────────────────────────────
# 3 + 4: sample_admin permissions
# ────────────────────────────────────────────────────────────────────────
def test_sampleadmin_catalogue_preview_allowed(sampleadmin):
    # Pick any template id to just exercise permission layer; 404/409/400 all mean we passed authz.
    r = requests.get(f"{BASE}/sample-orders/catalogue/preview",
                     params={"template_id": "ptpl_nope"}, headers=sampleadmin, timeout=30)
    assert r.status_code != 403, r.text[:200]


def test_sampleadmin_catalogue_templates_allowed(sampleadmin):
    r = requests.get(f"{BASE}/sample-orders/catalogue/templates",
                     params={"entity_id": ENT_KSC}, headers=sampleadmin, timeout=30)
    assert r.status_code == 200, r.text[:200]
    assert isinstance(r.json(), list)


def test_sampleadmin_cannot_create_regular_so(sampleadmin):
    r = requests.post(f"{BASE}/sales-orders", headers=sampleadmin, timeout=60, json={
        "customer_id": CUST, "shipping_address_id": ADDR, "entity_id": ENT_KSC,
        "items": [{"product_id": PROD, "quantity": 1.0, "unit": "yard", "base_quantity": 1.0}]})
    assert r.status_code == 403, r.text[:200]


def test_sampleadmin_can_create_sample_so(sampleadmin, admin, created_sos):
    r = requests.post(f"{BASE}/sales-orders", headers=sampleadmin, timeout=60, json={
        "customer_id": CUST, "shipping_address_id": ADDR, "entity_id": ENT_KSC,
        "order_type": "sample", "sample_billing": "free",
        "items": [{"product_id": PROD, "quantity": 1.0, "unit": "yard", "base_quantity": 1.0,
                   "is_sample": True, "sample_kind": "standard"}]})
    assert r.status_code == 200, r.text[:300]
    created_sos.append(r.json()["id"])


# ────────────────────────────────────────────────────────────────────────
# 5: catalogue empty soft rejected
# ────────────────────────────────────────────────────────────────────────
def test_catalogue_requires_soft(admin, created_sos):
    r = requests.post(f"{BASE}/sales-orders", headers=admin, timeout=60, json={
        "customer_id": CUST, "shipping_address_id": ADDR, "entity_id": ENT_KSC,
        "order_type": "sample", "sample_billing": "paid",
        "catalogue": {"template_id": "ptpl_anything", "soft_product_id": ""},
        "items": []})
    assert r.status_code == 400, r.text[:200]
    assert "warna soft" in r.text.lower(), r.text[:200]


# ────────────────────────────────────────────────────────────────────────
# 6: sample stats paid_value excludes cancelled
# ────────────────────────────────────────────────────────────────────────
def test_sample_stats_paid_value_excludes_cancelled(admin):
    r = requests.get(f"{BASE}/sample-orders/stats/summary", headers=admin, timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert "paid_value" in body
    # Sum manually
    q = {"order_type": "sample", "sample_billing": "paid", "status": {"$ne": "cancelled"}}
    expected = round(sum(float(d.get("grand_total") or 0) for d in DB.sales_orders.find(q, {"grand_total": 1})), 2)
    assert abs(float(body["paid_value"]) - expected) < 0.01, (body["paid_value"], expected)
    # Make sure cancelled ones are excluded: check there is at least one paid-cancelled SO; if so
    # paid_value < sum including cancelled.
    inc_cancel = round(sum(float(d.get("grand_total") or 0) for d in DB.sales_orders.find(
        {"order_type": "sample", "sample_billing": "paid"}, {"grand_total": 1})), 2)
    if inc_cancel > expected + 0.01:
        assert body["paid_value"] < inc_cancel


# ────────────────────────────────────────────────────────────────────────
# 8: qc notification visible to qc user with "inspections" link
# ────────────────────────────────────────────────────────────────────────
def test_qc_notification_to_qc_user(admin, created_sos):
    r = requests.post(f"{BASE}/sales-orders", headers=admin, timeout=60, json={
        "customer_id": CUST, "shipping_address_id": ADDR, "entity_id": ENT_KSC,
        "qc_request": "full",
        "items": [{"product_id": PROD, "quantity": 2.0, "unit": "yard", "base_quantity": 2.0}]})
    assert r.status_code == 200, r.text[:300]
    so = r.json()
    created_sos.append(so["id"])
    time.sleep(0.5)
    qc = _login("qc@kainnusantara.id")
    notes = requests.get(f"{BASE}/notifications", headers=qc, timeout=30).json()
    mine = [n for n in notes if n.get("type") == "so_qc_requested" and so["number"] in n.get("title", "")]
    assert mine, [n.get("title") for n in notes[:5]]
    assert mine[0].get("link") == "inspections"


# ────────────────────────────────────────────────────────────────────────
# 9: catalogue/templates filters by entity ownership + yard-stock
# ────────────────────────────────────────────────────────────────────────
def test_catalogue_templates_filters_by_entity(admin):
    r_ksc = requests.get(f"{BASE}/sample-orders/catalogue/templates",
                        params={"entity_id": ENT_KSC}, headers=admin, timeout=30)
    r_kda = requests.get(f"{BASE}/sample-orders/catalogue/templates",
                        params={"entity_id": ENT_KANDA}, headers=admin, timeout=30)
    assert r_ksc.status_code == 200 and r_kda.status_code == 200, (r_ksc.text, r_kda.text)
    ksc_tids = {t["id"] for t in r_ksc.json()}
    kda_tids = {t["id"] for t in r_kda.json()}
    # Templates can overlap only if same template has yard-stock available for both entities.
    # Each returned template must have at least one product belonging to an owner-roll.
    # Spot-check: templates listed for KSC must map to products with ≥1 available yd roll owned by ksc.
    for tid in list(ksc_tids)[:3]:
        pids = [p["id"] for p in DB.products.find({"template_id": tid}, {"id": 1})]
        assert pids
        found = DB.inventory_rolls.find_one({
            "product_id": {"$in": pids}, "owner_entity_id": ENT_KSC, "status": "available"})
        assert found, f"template {tid} returned for ksc but no ksc-owned available roll"
    # KSC and Kanda should not have identical complete lists (if they did, filter is a no-op)
    if ksc_tids and kda_tids:
        assert ksc_tids != kda_tids or len(ksc_tids) == 0, "ksc/kanda template lists are identical"


# ────────────────────────────────────────────────────────────────────────
# 1: cutting receive edge cases — using a synthetic sample_cut task
# ────────────────────────────────────────────────────────────────────────
@pytest.fixture
def synthetic_cut_task():
    """Create a fake sample_cut task referencing a real ent_ksc roll, so cutting/tasks/{id}/receive
    can be exercised without running the full sample order flow."""
    roll = DB.inventory_rolls.find_one({"owner_entity_id": "ent_ksc", "status": "available",
                                        "length_remaining": {"$gt": 1}, "warehouse_id": "wh_jakarta"})
    if not roll:
        pytest.skip("no ent_ksc roll in wh_jakarta available for synthetic cut task")
    tid = f"wt_{TAG}_cut_test"
    DB.wms_tasks.delete_one({"id": tid})
    DB.wms_tasks.insert_one({
        "id": tid, "task_subtype": "sample_cut", "entity_id": "ent_ksc",
        "order_id": f"so_{TAG}_synthetic", "order_number": f"{TAG}/SO-TEST",
        "warehouse_id": roll["warehouse_id"], "roll_id": roll["id"],
        "product_id": roll["product_id"], "unit": "yard",
        "child_roll_no": "TESTCHILD", "parent_roll_no": roll.get("roll_no", ""),
        "quantity": 1.0, "status": "picked", "created_at": "2026-01-01T00:00:00+00:00",
        "customer_name": "TEST", "product_name": "test"})
    yield tid, roll
    DB.wms_tasks.delete_one({"id": tid})


def test_receive_rejects_other_owner_warehouse(admin, synthetic_cut_task):
    tid, roll = synthetic_cut_task
    # KSC roll → send to Kanda dedicated warehouse → should be 400 CUTTING_DEST_OTHER_OWNER
    r = requests.post(f"{BASE}/cutting/tasks/{tid}/receive",
                     json={"to_warehouse_id": DB.warehouses.find_one({"code": "GU-KANDA"})["id"]}, headers=admin, timeout=30)
    assert r.status_code == 400, r.text[:200]
    detail = r.json().get("detail", {})
    code = detail.get("code") if isinstance(detail, dict) else ""
    assert code == "CUTTING_DEST_OTHER_OWNER", r.text[:300]


def test_receive_same_warehouse_ok_and_idempotent(admin, synthetic_cut_task):
    tid, roll = synthetic_cut_task
    r1 = requests.post(f"{BASE}/cutting/tasks/{tid}/receive",
                      json={"to_warehouse_id": roll["warehouse_id"]}, headers=admin, timeout=60)
    assert r1.status_code == 200, r1.text[:300]
    body1 = r1.json()
    assert (body1.get("cutting_handoff") or {}).get("received_at"), "handoff not recorded"
    # second call is idempotent
    r2 = requests.post(f"{BASE}/cutting/tasks/{tid}/receive",
                      json={"to_warehouse_id": roll["warehouse_id"]}, headers=admin, timeout=60)
    assert r2.status_code == 200, r2.text[:300]


def test_receive_missing_roll_409(admin):
    tid = f"wt_{TAG}_missing_roll"
    DB.wms_tasks.delete_one({"id": tid})
    DB.wms_tasks.insert_one({
        "id": tid, "task_subtype": "sample_cut", "entity_id": "ent_ksc",
        "order_id": f"so_{TAG}_missing", "warehouse_id": "wh_jakarta",
        "roll_id": "roll_does_not_exist_xxx", "product_id": PROD, "unit": "yard",
        "status": "picked", "created_at": "2026-01-01T00:00:00+00:00"})
    try:
        r = requests.post(f"{BASE}/cutting/tasks/{tid}/receive",
                         json={"to_warehouse_id": "wh_jakarta"}, headers=admin, timeout=30)
        assert r.status_code == 409, r.text[:200]
    finally:
        DB.wms_tasks.delete_one({"id": tid})


def test_receive_shared_warehouse_ok(admin):
    """A shared warehouse (sharing_mode='shared', entity_ids=[]) should always be a valid dest."""
    roll = DB.inventory_rolls.find_one({"owner_entity_id": "ent_ksc", "status": "available",
                                        "length_remaining": {"$gt": 1}, "warehouse_id": "wh_jakarta"})
    if not roll:
        pytest.skip("no ksc roll available")
    tid = f"wt_{TAG}_shared_test"
    DB.wms_tasks.delete_one({"id": tid})
    DB.wms_tasks.insert_one({
        "id": tid, "task_subtype": "sample_cut", "entity_id": "ent_ksc",
        "order_id": f"so_{TAG}_shared", "warehouse_id": roll["warehouse_id"],
        "roll_id": roll["id"], "product_id": roll["product_id"], "unit": "yard",
        "child_roll_no": "SHAREDCHILD", "quantity": 1.0, "status": "picked",
        "created_at": "2026-01-01T00:00:00+00:00"})
    try:
        # wh_bf256327b163 is sharing_mode='shared' with empty entity_ids
        r = requests.post(f"{BASE}/cutting/tasks/{tid}/receive",
                         json={"to_warehouse_id": DB.warehouses.find_one({"code": "RCM-WOVEN"})["id"]}, headers=admin, timeout=60)
        assert r.status_code == 200, r.text[:300]
        # Need to move roll back and clear movements
        DB.inventory_rolls.update_one({"id": roll["id"]},
                                      {"$set": {"warehouse_id": roll["warehouse_id"]}})
        DB.inventory_movements.delete_many({"id": {"$in": [f"mov_cho_{tid}", f"mov_chi_{tid}"]}})
    finally:
        DB.wms_tasks.delete_one({"id": tid})


def test_receive_unknown_task_404(admin):
    r = requests.post(f"{BASE}/cutting/tasks/wt_does_not_exist/receive",
                     json={"to_warehouse_id": "wh_jakarta"}, headers=admin, timeout=30)
    assert r.status_code == 404
