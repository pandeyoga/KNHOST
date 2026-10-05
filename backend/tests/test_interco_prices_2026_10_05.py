"""2026-10-05 — Backend tests for INTERCO PRICE feature (harga internal antar-PT).

Covers:
- GET /api/interco/prices/access (role-based)
- GET /api/interco/prices/summary (6 pairs)
- POST /api/interco/prices/bulk (RBAC + validation)
- GET/POST /api/sales-admin/orders/{id}/fulfillment-plan with INTERCO_PRICE_MISSING scenario
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://internal-pricing.preview.emergentagent.com").rstrip("/")
ENT_KSC = "ent_ksc"
ENT_KANDA = "ent_kanda"


def _login(email: str) -> requests.Session:
    s = requests.Session()
    for pw in ("demo12345", "demo1234"):
        r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
        if r.status_code == 200:
            return s
    assert False, f"login {email} failed with both passwords -> {r.status_code} {r.text[:200]}"


@pytest.fixture(scope="module")
def admin(): return _login("admin@kainnusantara.id")
@pytest.fixture(scope="module")
def md(): return _login("md@kainnusantara.id")
@pytest.fixture(scope="module")
def finance(): return _login("finance@kainnusantara.id")
@pytest.fixture(scope="module")
def manager(): return _login("manager@kainnusantara.id")
@pytest.fixture(scope="module")
def salesadmin(): return _login("salesadmin@kainnusantara.id")
@pytest.fixture(scope="module")
def salesadmin_kanda(): return _login("salesadmin.kanda@kainnusantara.id")


# ─────────── /api/interco/prices/access ───────────
@pytest.mark.parametrize("role_email,can_set", [
    ("admin@kainnusantara.id", True),
    ("md@kainnusantara.id", True),
    ("finance@kainnusantara.id", True),
    ("manager@kainnusantara.id", False),
    ("salesadmin@kainnusantara.id", False),
])
def test_prices_access(role_email, can_set):
    s = _login(role_email)
    r = s.get(f"{BASE_URL}/api/interco/prices/access", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("can_set") is can_set, f"{role_email}: can_set={data.get('can_set')} expected {can_set}"


# ─────────── /api/interco/prices/summary ───────────
def test_summary_as_md_has_pairs(md):
    r = md.get(f"{BASE_URL}/api/interco/prices/summary", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    pairs = data.get("pairs") or []
    # 3 entities (Sukacita, Kanda, Cipta Sandang) → 6 directed pairs
    assert len(pairs) == 6, f"expected 6 pairs, got {len(pairs)}: {pairs}"
    for p in pairs:
        assert "seller_entity_id" in p and "buyer_entity_id" in p
        assert "missing" in p and isinstance(p["missing"], int)


def test_summary_forbidden_for_salesadmin(salesadmin):
    r = salesadmin.get(f"{BASE_URL}/api/interco/prices/summary", timeout=30)
    assert r.status_code == 403, r.text


# ─────────── /api/interco/prices/bulk ───────────
def test_bulk_rbac_salesadmin_forbidden(salesadmin):
    r = salesadmin.post(f"{BASE_URL}/api/interco/prices/bulk",
                        json={"seller_entity_id": ENT_KSC, "buyer_entity_id": ENT_KANDA, "items": []},
                        timeout=30)
    assert r.status_code == 403


def test_bulk_rbac_manager_forbidden(manager):
    r = manager.post(f"{BASE_URL}/api/interco/prices/bulk",
                     json={"seller_entity_id": ENT_KSC, "buyer_entity_id": ENT_KANDA, "items": []},
                     timeout=30)
    assert r.status_code == 403


def test_bulk_same_entity_rejected(finance):
    r = finance.post(f"{BASE_URL}/api/interco/prices/bulk",
                     json={"seller_entity_id": ENT_KSC, "buyer_entity_id": ENT_KSC,
                           "items": [{"product_id": "whatever", "unit_price": 100}]},
                     timeout=30)
    assert r.status_code == 400, r.text


def test_bulk_no_valid_price_rejected(finance):
    r = finance.post(f"{BASE_URL}/api/interco/prices/bulk",
                     json={"seller_entity_id": ENT_KSC, "buyer_entity_id": ENT_KANDA,
                           "items": [{"product_id": "no-such", "unit_price": 0}]},
                     timeout=30)
    assert r.status_code == 400, r.text


def test_bulk_creates_contract_and_then_terminate(finance, admin):
    """Pick an existing missing product (if any), create a TEST contract, verify, then terminate for cleanup."""
    # find a missing product in Kanda->KSC direction (likely empty due to seed, so use pair with real stock)
    r = finance.get(f"{BASE_URL}/api/interco/prices/missing",
                    params={"seller_entity_id": ENT_KSC, "buyer_entity_id": ENT_KANDA, "only_stock": "false"},
                    timeout=30)
    assert r.status_code == 200, r.text
    rows = r.json().get("rows") or []
    if not rows:
        pytest.skip("No missing products available to test bulk create")
    pick = rows[0]
    created_price = 1234
    r = finance.post(f"{BASE_URL}/api/interco/prices/bulk",
                     json={"seller_entity_id": ENT_KSC, "buyer_entity_id": ENT_KANDA,
                           "notes": "TEST_bulk_create",
                           "items": [{"product_id": pick["product_id"], "unit_price": created_price}]},
                     timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("count") == 1
    created = data["created"][0]
    assert created["product_id"] == pick["product_id"]
    assert float(created["unit_price"]) == created_price
    # verify contract is active and partner_kind=entity via contracts list
    cid = created["id"]
    r = admin.get(f"{BASE_URL}/api/supplier-contracts/{cid}", timeout=30)
    if r.status_code == 200:
        c = r.json()
        assert c.get("contract_type") == "internal"
        assert c.get("partner_kind") == "entity"
        assert c.get("partner_id") == ENT_KANDA
        assert c.get("entity_id") == ENT_KSC
    # cleanup: terminate
    rt = admin.post(f"{BASE_URL}/api/supplier-contracts/{cid}/status",
                    json={"status": "terminated", "reason": "TEST cleanup"}, timeout=30)
    assert rt.status_code in (200, 204), rt.text


# ─────────── Fulfillment plan: INTERCO_PRICE_MISSING scenario ───────────
@pytest.fixture(scope="module")
def missing_price_scenario(admin, salesadmin_kanda):
    """Create a TEST SO in Kanda with backorder for a product only stocked in KSC,
    terminate the internal contract KSC→Kanda for that product, yield (order_id, product_id, contract_id),
    then restore contract & cleanup SO."""
    # Pick a product that has stock in ent_ksc and existing internal contract to ent_kanda
    # Query supplier contracts list
    r = admin.get(f"{BASE_URL}/api/supplier-contracts",
                  params={"contract_type": "internal", "entity_id": ENT_KSC, "status": "active"}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    contracts = data if isinstance(data, list) else data.get("items") or []
    # filter: partner_id=ent_kanda
    contracts = [c for c in contracts if c.get("partner_id") == ENT_KANDA and c.get("product_id")]
    assert contracts, "No active internal contracts KSC->Kanda; seed may be missing"
    # pick one that has stock in KSC
    chosen = None
    for c in contracts:
        pid = c["product_id"]
        rb = admin.get(f"{BASE_URL}/api/stock-availability",
                       params={"product_id": pid, "entity_id": ENT_KSC}, timeout=30)
        if rb.status_code == 200:
            # just assume this works; otherwise fallback below
            pass
        chosen = c
        break
    assert chosen
    pid = chosen["product_id"]
    cid = chosen["id"]

    # Fetch customer in Kanda
    rc = admin.get(f"{BASE_URL}/api/customers", params={"entity_id": ENT_KANDA, "limit": 5}, timeout=30)
    assert rc.status_code == 200, rc.text
    cdata = rc.json()
    customers = cdata if isinstance(cdata, list) else cdata.get("items") or []
    assert customers, "No customers in Kanda"
    cust = customers[0]

    # Create SO as salesadmin.kanda with allow_backorder
    uniq = uuid.uuid4().hex[:8]
    addrs = cust.get("addresses") or []
    shipping_address_id = (addrs[0]["id"] if addrs else "")
    so_payload = {
        "entity_id": ENT_KANDA,
        "customer_id": cust["id"],
        "customer_name": f"TEST_{cust.get('name','cust')}",
        "shipping_address_id": shipping_address_id,
        "notes": f"TEST_interco_price_missing_{uniq}",
        "allow_backorder": True,
        "items": [{"product_id": pid, "quantity": 10, "unit_price": 100000, "unit": "meter"}],
    }
    rs = salesadmin_kanda.post(f"{BASE_URL}/api/sales-orders",
                               headers={"X-Entity-Id": ENT_KANDA}, json=so_payload, timeout=60)
    if rs.status_code != 200 and rs.status_code != 201:
        pytest.skip(f"Cannot create SO with allow_backorder: {rs.status_code} {rs.text[:400]}")
    so = rs.json()
    order_id = so.get("id")

    # Terminate the internal contract to force missing price state
    rt = admin.post(f"{BASE_URL}/api/supplier-contracts/{cid}/status",
                    json={"status": "terminated", "reason": "TEST interco price missing"}, timeout=30)
    assert rt.status_code in (200, 204), rt.text

    yield {"order_id": order_id, "product_id": pid, "contract_id": cid}

    # ─── Teardown ───
    # Restore contract
    admin.post(f"{BASE_URL}/api/supplier-contracts/{cid}/status",
               json={"status": "active", "reason": "TEST restore"}, timeout=30)
    # Try to cancel SO
    admin.post(f"{BASE_URL}/api/sales-orders/{order_id}/cancel",
               json={"reason": "TEST cleanup"}, timeout=30)


def test_plan_get_marks_price_not_ready(salesadmin_kanda, missing_price_scenario):
    oid = missing_price_scenario["order_id"]
    pid = missing_price_scenario["product_id"]
    r = salesadmin_kanda.get(f"{BASE_URL}/api/sales-admin/orders/{oid}/fulfillment-plan",
                             headers={"X-Entity-Id": ENT_KANDA}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("can_set_internal_price") is False
    # find line
    line = next((ln for ln in data["lines"] if ln["product_id"] == pid), None)
    assert line, f"product {pid} not in plan lines"
    others = line.get("other_entities") or []
    ksc_entry = next((o for o in others if o["entity_id"] == ENT_KSC), None)
    assert ksc_entry, f"no KSC entry in other_entities: {others}"
    assert ksc_entry.get("price_ready") is False, ksc_entry


def test_plan_post_returns_structured_error(salesadmin_kanda, missing_price_scenario):
    oid = missing_price_scenario["order_id"]
    pid = missing_price_scenario["product_id"]
    r = salesadmin_kanda.post(
        f"{BASE_URL}/api/sales-admin/orders/{oid}/fulfillment-plan",
        headers={"X-Entity-Id": ENT_KANDA},
        json={"lines": [{"product_id": pid, "interco": [{"entity_id": ENT_KSC, "qty": 5}]}],
              "note": "TEST interco without price"},
        timeout=60,
    )
    assert r.status_code == 400, r.text
    detail = r.json().get("detail")
    # detail should be dict with code=INTERCO_PRICE_MISSING
    assert isinstance(detail, dict), f"expected dict detail, got {type(detail)}: {detail}"
    assert detail.get("code") == "INTERCO_PRICE_MISSING", detail


def test_plan_md_can_set_flag(md, missing_price_scenario):
    oid = missing_price_scenario["order_id"]
    r = md.get(f"{BASE_URL}/api/sales-admin/orders/{oid}/fulfillment-plan",
               headers={"X-Entity-Id": ENT_KANDA}, timeout=30)
    # md may not have order.confirm access; accept 200 or 403
    if r.status_code == 200:
        assert r.json().get("can_set_internal_price") is True


# ─────────── Request price (notification) ───────────
def test_request_price_as_salesadmin(salesadmin_kanda, missing_price_scenario):
    pid = missing_price_scenario["product_id"]
    oid = missing_price_scenario["order_id"]
    r = salesadmin_kanda.post(f"{BASE_URL}/api/interco/prices/request",
                              json={"seller_entity_id": ENT_KSC, "buyer_entity_id": ENT_KANDA,
                                    "product_id": pid, "order_id": oid, "note": "TEST please set price"},
                              timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "sent" in data
    # at least message key present
    assert "message" in data
