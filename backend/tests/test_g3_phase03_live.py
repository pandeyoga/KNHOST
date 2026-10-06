"""Live API tests for G3 Phase 03 (iteration 167).
Covers:
- D4-FIN-01: /api/finance/tower entity header vs query parity
- D4-COMM-BOUNDS-01: supplier-contracts tariff_rate < 0 and supplier-items last_price < 0 => 422
- D4-BUD-EDIT-01: budget duplicate month and invalid year => 400
- Regressi: sales/manager home load; financial statements multi/single entity; profitability; cashflow-forecast; AR aging
- Regresi fulfillment plan duplicate product => 400
"""
import os
import pytest
import requests
import uuid

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "https://internal-pricing.preview.emergentagent.com").rstrip("/")

ADMIN = ("admin@kainnusantara.id", "demo12345")
SALES = ("sales@kainnusantara.id", "demo1234")
FINANCE = ("finance@kainnusantara.id", "demo1234")
MANAGER = ("manager@kainnusantara.id", "demo1234")
SALESADMIN = ("salesadmin@kainnusantara.id", "demo1234")


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_hdr():
    tok = _login(*ADMIN)
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def finance_hdr():
    tok = _login(*FINANCE)
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def sales_hdr():
    tok = _login(*SALES)
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def manager_hdr():
    tok = _login(*MANAGER)
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def salesadmin_hdr():
    tok = _login(*SALESADMIN)
    return {"Authorization": f"Bearer {tok}"}


# --- D4-FIN-01 ---
def test_fin_tower_entity_header_matches_query(admin_hdr):
    h_with_ent = {**admin_hdr, "X-Entity-Id": "ent_ksc"}
    r_hdr = requests.get(f"{BASE}/api/finance/tower", headers=h_with_ent, timeout=60)
    assert r_hdr.status_code == 200, r_hdr.text
    r_q = requests.get(f"{BASE}/api/finance/tower?entity_id=ent_ksc", headers=admin_hdr, timeout=60)
    assert r_q.status_code == 200, r_q.text
    r_all = requests.get(f"{BASE}/api/finance/tower?entity_id=all", headers=admin_hdr, timeout=60)
    assert r_all.status_code == 200, r_all.text

    hdr = r_hdr.json()
    q = r_q.json()
    all_ = r_all.json()
    # ignore volatile fields
    for d in (hdr, q, all_):
        d.pop("generated_at", None)
    assert hdr == q, "finance tower header vs ?entity_id=ent_ksc should match exactly"
    assert all_ != q, "finance tower ?entity_id=all should differ from single entity"


# --- D4-COMM-BOUNDS-01 ---
def _pick_supplier_contract_id(admin_hdr):
    for url in ("/api/supplier-contracts", "/api/supplier-contracts?limit=1"):
        r = requests.get(f"{BASE}{url}", headers=admin_hdr, timeout=30)
        if r.status_code == 200:
            data = r.json()
            items = data if isinstance(data, list) else data.get("items") or data.get("data") or []
            if items:
                it = items[0]
                return it.get("id") or it.get("_id") or it.get("contract_id")
    return None


def test_supplier_contract_negative_tariff_rejected(admin_hdr):
    cid = _pick_supplier_contract_id(admin_hdr)
    if not cid:
        pytest.skip("no supplier contract available")
    r = requests.patch(
        f"{BASE}/api/supplier-contracts/{cid}",
        headers=admin_hdr,
        json={"tariff_rate": -5},
        timeout=30,
    )
    assert r.status_code == 422, f"expected 422 got {r.status_code}: {r.text}"


def _pick_supplier_item_id(admin_hdr):
    r = requests.get(f"{BASE}/api/supplier-items", headers=admin_hdr, timeout=30)
    if r.status_code != 200:
        return None
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("data") or []
    if not items:
        return None
    it = items[0]
    return it.get("id") or it.get("_id")


def test_supplier_item_negative_last_price_rejected(admin_hdr):
    # 422 by Pydantic validation triggers before id lookup
    r = requests.patch(
        f"{BASE}/api/supplier-items/nonexistent_TEST_id",
        headers=admin_hdr,
        json={"last_price": -1},
        timeout=30,
    )
    assert r.status_code == 422, f"expected 422 got {r.status_code}: {r.text}"


# --- D4-BUD-EDIT-01 ---
def test_budget_duplicate_month_and_invalid_year(admin_hdr, finance_hdr, manager_hdr):
    # Try admin first, fall back to finance
    created_ids = []
    tag = f"TEST_{uuid.uuid4().hex[:8]}"
    base_payload_common = {
        "entity_id": "ent_ksc",
        "year": 2099,
        "account_code": "4-1000",
        "amount": 1000,
        "note": tag,
    }
    hdrs_to_try = [admin_hdr, finance_hdr, manager_hdr]
    used_hdr = None
    for h in hdrs_to_try:
        p1 = {**base_payload_common, "month": 1}
        r = requests.post(f"{BASE}/api/finance/budgets", headers=h, json=p1, timeout=30)
        if r.status_code in (200, 201):
            used_hdr = h
            created_ids.append(r.json().get("id") or r.json().get("_id"))
            break
    if not used_hdr:
        pytest.skip(f"cannot create budget via POST /api/finance/budgets (last: {r.status_code} {r.text[:200]})")

    try:
        # create second budget month=2 same key
        p2 = {**base_payload_common, "month": 2}
        r2 = requests.post(f"{BASE}/api/finance/budgets", headers=used_hdr, json=p2, timeout=30)
        assert r2.status_code in (200, 201), r2.text
        bid2 = r2.json().get("id") or r2.json().get("_id")
        created_ids.append(bid2)

        # PATCH -> month=1 should 400 (duplicate)
        rp = requests.patch(f"{BASE}/api/finance/budgets/{bid2}", headers=used_hdr, json={"month": 1}, timeout=30)
        assert rp.status_code == 400, f"expected 400 dup month got {rp.status_code}: {rp.text}"

        # PATCH -> year=1900 should 400
        ry = requests.patch(f"{BASE}/api/finance/budgets/{bid2}", headers=used_hdr, json={"year": 1900}, timeout=30)
        assert ry.status_code == 400, f"expected 400 invalid year got {ry.status_code}: {ry.text}"
    finally:
        for bid in created_ids:
            if bid:
                requests.delete(f"{BASE}/api/finance/budgets/{bid}", headers=used_hdr, timeout=30)


# --- Regresi: home sales & manager ---
def test_sales_home_loads(sales_hdr):
    r = requests.get(f"{BASE}/api/home/sales", headers=sales_hdr, timeout=60)
    assert r.status_code == 200, r.text


def test_manager_home_loads(manager_hdr):
    r = requests.get(f"{BASE}/api/home/manager", headers=manager_hdr, timeout=60)
    assert r.status_code == 200, r.text


# --- Regresi: finance reports ---
@pytest.mark.parametrize("ent", ["all", "ent_ksc"])
@pytest.mark.parametrize("endpoint", [
    "/api/finance/balance-sheet",
    "/api/finance/income-statement",
    "/api/finance/cash-flow",
])
def test_financial_statements(admin_hdr, endpoint, ent):
    r = requests.get(f"{BASE}{endpoint}?entity_id={ent}", headers=admin_hdr, timeout=60)
    assert r.status_code == 200, f"{endpoint} ent={ent}: {r.status_code} {r.text[:200]}"


def test_profitability_loads(admin_hdr):
    r = requests.get(f"{BASE}/api/finance/profitability?entity_id=ent_ksc", headers=admin_hdr, timeout=60)
    assert r.status_code == 200, r.text


def test_cashflow_forecast_loads(admin_hdr):
    r = requests.get(f"{BASE}/api/finance/cashflow-forecast?entity_id=ent_ksc", headers=admin_hdr, timeout=60)
    assert r.status_code == 200, r.text


def test_ar_aging_loads(admin_hdr):
    r = requests.get(f"{BASE}/api/ar/aging?entity_id=ent_ksc", headers=admin_hdr, timeout=60)
    assert r.status_code == 200, r.text


# --- Regresi: fulfillment plan duplicate product -> 400 ---
def test_fulfillment_plan_duplicate_product_rejected(salesadmin_hdr, admin_hdr):
    # Need a SO id; try to pick first open SO
    r = requests.get(f"{BASE}/api/sales-orders?entity_id=ent_ksc&limit=5", headers=admin_hdr, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"cannot list SO: {r.status_code}")
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("data") or []
    if not items:
        pytest.skip("no SO available")
    so = items[0]
    so_id = so.get("id") or so.get("_id")
    # fetch SO lines for a product id
    lines = so.get("lines") or so.get("items_list") or []
    if not lines:
        rso = requests.get(f"{BASE}/api/sales-orders/{so_id}", headers=admin_hdr, timeout=30)
        if rso.status_code == 200:
            lines = rso.json().get("lines") or rso.json().get("items") or []
    if not lines:
        pytest.skip("SO has no lines to test")
    product_id = lines[0].get("product_id") or lines[0].get("product", {}).get("id") if isinstance(lines[0], dict) else None
    if not product_id:
        pytest.skip("cannot find product_id")

    payload = {
        "lines": [
            {"product_id": product_id, "stock_qty": 1},
            {"product_id": product_id, "stock_qty": 1},
        ],
        "note": "TEST_dup_guard",
    }
    r = requests.post(
        f"{BASE}/api/sales-admin/orders/{so_id}/fulfillment-plan",
        headers=salesadmin_hdr,
        json=payload,
        timeout=30,
    )
    assert r.status_code == 400, f"expected 400 dup product got {r.status_code}: {r.text[:400]}"
