"""Iteration 143 — MAKLOON reservation protection + PO variance seed.

Covers:
 - Stok Makloon Aman: block / backorder / approve modes via /api/sales-orders + /api/config/values
 - Roll-mode (purchase_mode=roll) blocked identically
 - approve pending → /api/sales-orders/{id}/approve blocked by APPROVAL_PENDING
 - Cleanup: cancel+delete TEST SOs, delete TEST material_reservations, reset config back to 'block'
"""
import os
import time
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN = {"email": "admin@kainnusantara.id", "password": "demo12345"}
ENT = "ent_ksc"
PRODUCT_ID = "prod_batik_mega"
CUST_ID = "cust_textile_medan"
ADDR_ID = "addr_005"
MRES_ID = f"mres_TEST_{uuid.uuid4().hex[:8]}"
TEST_PR_REF = f"TEST_PR_{uuid.uuid4().hex[:6]}"


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    r.raise_for_status()
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers():
    tok = _login(ADMIN)
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": ENT, "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL)
    db = cli[DB_NAME]
    yield db
    cli.close()


@pytest.fixture(scope="module")
def free_qty(admin_headers):
    r = requests.get(f"{BASE_URL}/api/inventory/balances?product_id={PRODUCT_ID}", headers=admin_headers, timeout=30)
    r.raise_for_status()
    rows = r.json()
    rows = [x for x in rows if x.get("owner_entity_id") == ENT]
    assert rows, "no balance row for product+entity"
    # pick highest available
    avail = max(float(x.get("available_qty") or 0) for x in rows)
    assert avail > 20, f"not enough free stock to test (available={avail})"
    return avail


@pytest.fixture(scope="module", autouse=True)
def seed_reservation(mongo, free_qty):
    """Insert a material reservation taking most of free stock, then clean up at module teardown."""
    # Reserve ~ (free_qty - 50) so free available after reservation ≈ 50 (room for small test)
    reserve_qty = max(free_qty - 50.0, 1.0)
    doc = {
        "id": MRES_ID,
        "product_id": PRODUCT_ID,
        "owner_entity_id": ENT,
        "ref_type": "purchase_requisition",
        "ref_id": TEST_PR_REF,
        "pr_id": TEST_PR_REF,
        "pr_line_no": 1,
        "qty": float(reserve_qty),
        "status": "active",
        "note": "TEST iter143 makloon reservation",
    }
    mongo.material_reservations.insert_one(doc)
    print(f"[seed] inserted {MRES_ID} qty={reserve_qty} (free_qty_before={free_qty})")
    yield reserve_qty
    # teardown
    mongo.material_reservations.delete_many({"id": MRES_ID})
    mongo.material_reservations.delete_many({"ref_id": TEST_PR_REF})
    print("[teardown] removed TEST material_reservations")


# ------ created SO tracking so we can cancel/delete at end ------
_created_so_ids: list[str] = []


@pytest.fixture(scope="module", autouse=True)
def cleanup_sos(admin_headers, mongo):
    yield
    for so_id in _created_so_ids:
        try:
            requests.post(f"{BASE_URL}/api/sales-orders/{so_id}/cancel",
                          headers=admin_headers,
                          json={"reason": "TEST cleanup"}, timeout=20)
        except Exception as e:
            print(f"cancel {so_id} fail: {e}")
        try:
            mongo.sales_orders.delete_one({"id": so_id})
        except Exception as e:
            print(f"delete {so_id} fail: {e}")
    # reset config back to default (block)
    requests.put(f"{BASE_URL}/api/config/values",
                 headers=admin_headers,
                 json={"items": [{"key": "allocation.makloon_reserve_mode", "value": "block",
                                   "scope_type": "global", "reason": "TEST cleanup iter143"}]},
                 timeout=20)
    print("[teardown] reset allocation.makloon_reserve_mode=block")


def _set_mode(admin_headers, mode: str):
    r = requests.put(f"{BASE_URL}/api/config/values",
                     headers=admin_headers,
                     json={"items": [{"key": "allocation.makloon_reserve_mode", "value": mode,
                                       "scope_type": "global", "reason": f"TEST iter143 {mode}"}]},
                     timeout=20)
    assert r.status_code == 200, f"set mode {mode} → {r.status_code} {r.text[:200]}"


def _so_payload(qty, *, allow_backorder=False, confirm=False, purchase_mode="qty", roll_lines=None):
    item = {
        "product_id": PRODUCT_ID,
        "quantity": float(qty),
        "unit": "yard",
        "purchase_mode": purchase_mode,
    }
    if roll_lines is not None:
        item["roll_lines"] = roll_lines
    return {
        "customer_id": CUST_ID,
        "shipping_address_id": ADDR_ID,
        "items": [item],
        "allow_backorder": allow_backorder,
        "confirm_makloon_override": confirm,
    }


# ============================================================
# MODE: block (default)
# ============================================================

def test_01_small_qty_within_free_succeeds_block(admin_headers):
    """Note: with the 250yd reservation seeded, free is very small. Use allow_backorder for sanity: order shape works."""
    _set_mode(admin_headers, "block")
    r = requests.post(f"{BASE_URL}/api/sales-orders", headers=admin_headers,
                      json=_so_payload(2, allow_backorder=True), timeout=30)
    assert r.status_code == 200, f"basic SO shape expected 200, got {r.status_code}: {r.text[:300]}"
    so = r.json()
    assert so.get("id")
    _created_so_ids.append(so["id"])


def test_02_block_mode_returns_409_MAKLOON_RESERVED(admin_headers, free_qty, seed_reservation):
    """qty beyond free stock → 409 MAKLOON_RESERVED"""
    big = free_qty  # entire free (bigger than the ~10 remaining)
    r = requests.post(f"{BASE_URL}/api/sales-orders", headers=admin_headers,
                      json=_so_payload(big), timeout=30)
    assert r.status_code == 409, f"expected 409, got {r.status_code}: {r.text[:300]}"
    detail = r.json().get("detail", {})
    assert detail.get("code") == "MAKLOON_RESERVED", f"detail={detail}"
    assert "dicadangkan" in (detail.get("message") or "").lower() or "makloon" in (detail.get("message") or "").lower()


def test_03_block_mode_allow_backorder_200(admin_headers, free_qty):
    """allow_backorder:true → 200 with reserved_qty capped and backorder"""
    big = free_qty
    r = requests.post(f"{BASE_URL}/api/sales-orders", headers=admin_headers,
                      json=_so_payload(big, allow_backorder=True), timeout=30)
    assert r.status_code == 200, f"backorder expected 200, got {r.status_code}: {r.text[:300]}"
    so = r.json()
    _created_so_ids.append(so["id"])
    items = so.get("items", [])
    assert items
    reserved = sum(float(x.get("reserved_qty") or 0) for x in items)
    backorder = sum(float(x.get("backorder_qty") or 0) for x in items)
    assert reserved < big + 0.5, f"reserved should cap below requested; reserved={reserved}, req={big}"
    assert backorder > 0, f"expected some backorder qty; items={items}"


# ============================================================
# MODE: approve
# ============================================================

def test_04_approve_mode_returns_409_approval(admin_headers, free_qty):
    _set_mode(admin_headers, "approve")
    big = free_qty
    r = requests.post(f"{BASE_URL}/api/sales-orders", headers=admin_headers,
                      json=_so_payload(big), timeout=30)
    assert r.status_code == 409, f"approve mode expected 409, got {r.status_code}: {r.text[:300]}"
    detail = r.json().get("detail", {})
    assert detail.get("code") == "MAKLOON_RESERVED_APPROVAL", f"detail={detail}"


def test_05_approve_with_confirm_override_succeeds_with_pending_approval(admin_headers, free_qty):
    # Use qty > free remaining (~50) but within physical available; add allow_backorder in case
    big = min(free_qty - 10.0, free_qty)  # within available
    r = requests.post(f"{BASE_URL}/api/sales-orders", headers=admin_headers,
                      json=_so_payload(big, confirm=True, allow_backorder=True), timeout=30)
    assert r.status_code == 200, f"confirm override expected 200, got {r.status_code}: {r.text[:300]}"
    so = r.json()
    _created_so_ids.append(so["id"])
    pending = so.get("pending_approvals") or []
    types = [p.get("type") for p in pending]
    assert "makloon" in types, f"expected pending_approvals type 'makloon'; got {pending}"
    makloon = next(p for p in pending if p.get("type") == "makloon")
    assert makloon.get("required_role") == "manager" or "manager" in str(makloon.get("required_roles", [])), \
        f"required_role not manager; approval={makloon}"


def test_06_approve_blocked_while_makloon_pending(admin_headers):
    """POST /api/sales-orders/{id}/approve → 409 APPROVAL_PENDING while makloon pending"""
    assert _created_so_ids, "need prior SO"
    # Use the most recent SO with pending makloon
    so_id = _created_so_ids[-1]
    r = requests.post(f"{BASE_URL}/api/sales-orders/{so_id}/approve",
                      headers=admin_headers, json={}, timeout=20)
    assert r.status_code == 409, f"expected 409 APPROVAL_PENDING, got {r.status_code}: {r.text[:300]}"
    detail = r.json().get("detail", {})
    code = detail.get("code") if isinstance(detail, dict) else ""
    assert code == "APPROVAL_PENDING", f"expected APPROVAL_PENDING; detail={detail}"


# ============================================================
# Roll-mode blocked same way (block mode)
# ============================================================

def test_07_roll_mode_blocked_in_block_mode(admin_headers, free_qty):
    _set_mode(admin_headers, "block")
    # fetch available rolls for product
    r = requests.get(f"{BASE_URL}/api/inventory/rolls/available?product_id={PRODUCT_ID}",
                     headers=admin_headers, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"rolls/available not accessible: {r.status_code}")
    rolls = r.json()
    if isinstance(rolls, dict):
        rolls = rolls.get("items") or rolls.get("rolls") or []
    rolls = [x for x in rolls if x.get("owner_entity_id") == ENT]
    if len(rolls) < 2:
        pytest.skip(f"not enough rolls to assemble a big roll-mode cart ({len(rolls)})")
    # Pick rolls summing to > remaining free_after_reservation (~10)
    chosen = []
    total = 0.0
    for rl in rolls:
        q = float(rl.get("length_yard") or rl.get("quantity") or rl.get("remaining_qty") or 0)
        if q <= 0:
            continue
        chosen.append({"roll_id": rl.get("id") or rl.get("roll_id"), "mode": "whole", "quantity": q})
        total += q
        if total > 50:
            break
    if total <= 10:
        pytest.skip(f"could not reach qty>10 with rolls (total={total})")
    r = requests.post(f"{BASE_URL}/api/sales-orders", headers=admin_headers,
                      json=_so_payload(total, purchase_mode="roll", roll_lines=chosen), timeout=30)
    # Expect 409 MAKLOON_RESERVED (same block as qty mode)
    if r.status_code == 200:
        so = r.json()
        _created_so_ids.append(so["id"])
        pytest.fail(f"roll mode expected block, got 200: items={so.get('items')}")
    assert r.status_code == 409, f"roll mode expected 409, got {r.status_code}: {r.text[:300]}"
    code = (r.json().get("detail") or {}).get("code")
    assert code in ("MAKLOON_RESERVED", "MAKLOON_RESERVED_APPROVAL"), f"unexpected code {code}"
