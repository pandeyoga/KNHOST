"""Iter105 — Scenario: PR (source=special_order) tanpa product_id → convert-to-po
   mengisi SKU R&D & menandai produk eksklusif.
Seeds DB directly, calls API, cleans up.
"""
import os, uuid, asyncio, pytest, requests
from datetime import datetime, timezone

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") + "/api"
CREDS = {"email": "admin@kainnusantara.id", "password": "demo12345"}


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "X-Entity-Id": "ent_ksc"})
    r = s.post(f"{BASE}/auth/login", json=CREDS, timeout=30)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


@pytest.fixture(scope="module")
def dbc():
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from pymongo import MongoClient
    c = MongoClient(os.environ["MONGO_URL"])
    return c[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def scenario_ids():
    return {"so_id": "", "pr_id": "", "prod_id": "", "po_id": ""}


def test_seed_so_product_pr(dbc, scenario_ids):
    tag = uuid.uuid4().hex[:8]
    prod_id = f"TEST_prod_{tag}"
    so_id = f"TEST_so_{tag}"
    pr_id = f"TEST_pr_{tag}"
    spec_id = f"TEST_spec_{tag}"

    dbc.products.insert_one({
        "id": prod_id, "sku": f"TEST-SKU-{tag}", "name": "TEST R&D Result",
        "base_unit": "meter", "special_order_id": so_id,
        "entity_id": "ent_ksc", "lifecycle": "produksi",
        "created_at": _now(), "updated_at": _now(),
    })
    dbc.special_orders.insert_one({
        "id": so_id, "number": f"TEST-SO-{tag}", "customer_id": "cust_test",
        "customer_name": "TEST Customer", "linked_product_id": prod_id,
        "spec_id": spec_id, "entity_id": "ent_ksc",
        "created_at": _now(),
    })
    dbc.purchase_requisitions.insert_one({
        "id": pr_id, "number": f"TEST-PR-{tag}",
        "status": "approved",
        "source": "special_order", "source_ref_id": so_id,
        "items": [{
            "line_no": 1, "product_id": "", "sku": "", "product_name": "",
            "quantity": 10, "unit": "meter", "unit_price": 100000,
            "line_total": 1000000,
        }],
        "total_est_amount": 1000000,
        "entity_id": "ent_ksc",
        "preferred_supplier_id": "sup_5ffaf80582d0",
        "created_at": _now(), "updated_at": _now(),
    })
    scenario_ids.update({"so_id": so_id, "pr_id": pr_id, "prod_id": prod_id, "spec_id": spec_id})


def test_get_pr_repairs_lines(client, scenario_ids):
    pr_id = scenario_ids["pr_id"]
    r = client.get(f"{BASE}/purchase-requisitions/{pr_id}")
    assert r.status_code == 200, r.text
    doc = r.json()
    # After repair_pr_lines the product_id is filled
    it = doc["items"][0]
    assert it["product_id"] == scenario_ids["prod_id"], it
    assert it.get("sku")


def test_convert_pr_to_po(client, scenario_ids):
    pr_id = scenario_ids["pr_id"]
    r = client.post(f"{BASE}/purchase-requisitions/{pr_id}/convert-to-po",
                    json={"supplier_id": "sup_5ffaf80582d0", "warehouse_id": "wh_bandung"})
    assert r.status_code == 200, r.text
    result = r.json()
    assert result.get("po"), result
    scenario_ids["po_id"] = result["po"].get("id") or ""


def test_product_marked_exclusive(dbc, scenario_ids):
    p = dbc.products.find_one({"id": scenario_ids["prod_id"]}, {"_id": 0})
    assert p, "product missing"
    assert p.get("exclusive_customer_id") == "cust_test", p
    assert p.get("catalog_scope") == "customer", p
    assert p.get("special_order_id") == scenario_ids["so_id"]


def test_zzz_cleanup(dbc, scenario_ids):
    dbc.products.delete_one({"id": scenario_ids["prod_id"]})
    dbc.special_orders.delete_one({"id": scenario_ids["so_id"]})
    dbc.purchase_requisitions.delete_one({"id": scenario_ids["pr_id"]})
    if scenario_ids.get("po_id"):
        dbc.purchase_orders.delete_one({"id": scenario_ids["po_id"]})
