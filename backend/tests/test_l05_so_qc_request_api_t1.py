"""L05 LN-050-T01 (T1) — real SO create via API with qc_request + ref-docs + SPK + dispatch endpoint guard."""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ENT = "ent_ksc"
CUST, ADDR, PROD = "cust_butik_bali", "addr_002", "prod_batik_mega"


def _login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def created():
    ids = []
    yield ids
    # cleanup: cancel via API (releases reservations), then purge docs
    h = _login("admin@kainnusantara.id", "demo12345")
    for sid in ids:
        requests.post(f"{BASE}/sales-orders/{sid}/cancel", json={"reason": "TEST cleanup L05 QC"}, headers=h, timeout=60)
        for r in DB.inventory_rolls.find({"reserved_ref.id": sid}, {"_id": 0, "id": 1}):
            DB.inventory_rolls.update_one({"id": r["id"]}, {"$set": {"status": "available"}, "$unset": {"reserved_ref": ""}})
        DB.inspections.delete_many({"ref_doc_id": sid})
        DB.wms_tasks.delete_many({"order_id": sid, "_test_l05": True})
        DB.shipments.delete_many({"order_id": sid})
        DB.sales_orders.delete_one({"id": sid})


def _create(h, **extra):
    payload = {"customer_id": CUST, "shipping_address_id": ADDR, "entity_id": ENT,
               "items": [{"product_id": PROD, "quantity": 10.0, "unit": "yard", "base_quantity": 10.0}], **extra}
    return requests.post(f"{BASE}/sales-orders", json=payload, headers=h, timeout=120)


# --- create validation
def test_invalid_mode_400(admin):
    r = _create(admin, qc_request="banyak")
    assert r.status_code == 400 and "Request QC" in r.text


@pytest.mark.parametrize("pct", [0, 101])
def test_invalid_pct_422(admin, pct):
    r = _create(admin, qc_request="sampling", qc_sample_pct=pct)
    assert r.status_code == 422


def test_default_none_stored(admin, created):
    r = _create(admin)
    assert r.status_code == 200, r.text[:300]
    created.append(r.json()["id"])
    so = DB.sales_orders.find_one({"id": r.json()["id"]}, {"_id": 0, "qc_request": 1})
    assert so["qc_request"] == {"mode": "none", "status": "not_required"}


def test_sampling_stored_by_sales_admin(created):
    h = _login("salesadmin@kainnusantara.id", "demo12345")
    r = _create(h, qc_request="SAMPLING", qc_sample_pct=25)
    assert r.status_code == 200, r.text[:300]
    created.append(r.json()["id"])
    qr = DB.sales_orders.find_one({"id": r.json()["id"]})["qc_request"]
    assert qr["mode"] == "sampling" and qr["sample_pct"] == 25 and qr["status"] == "required"


def test_full_flow_ref_docs_spk_dispatch(admin, created):
    r = _create(admin, qc_request="full")
    assert r.status_code == 200, r.text[:300]
    so = r.json()
    sid = so["id"]
    created.append(sid)
    qr = DB.sales_orders.find_one({"id": sid})["qc_request"]
    assert qr["mode"] == "full" and qr["status"] == "required"
    # ref-docs list includes it, excludes 'none' SO
    opts = requests.get(f"{BASE}/inspections/meta/ref-docs", params={"kind": "sales_order"}, headers=admin, timeout=30).json()
    vals = [o["value"] for o in opts.get("items", [])]
    assert sid in vals
    assert created[0] not in vals
    reserved = list(DB.inventory_rolls.find({"reserved_ref.id": sid}, {"_id": 0, "id": 1, "status": 1}))
    print("reserved rolls:", reserved)
    # dispatch endpoint guard via fake outbound task (staging, picked)
    tid = f"wt_test_{uuid.uuid4().hex[:8]}"
    DB.wms_tasks.insert_one({"id": tid, "flow_type": "outbound", "status": "staging", "entity_id": ENT,
                             "stages": ["created", "picking", "packing", "staging", "dispatched"],
                             "order_id": sid, "order_number": so.get("order_number", ""), "product_id": PROD,
                             "warehouse_id": "wh_jakarta", "quantity": 10, "picked_qty": 10, "shipped_qty": 0,
                             "unit": "yard", "_test_l05": True})
    d = requests.post(f"{BASE}/outbound/tasks/{tid}/dispatch", headers=admin, timeout=60)
    print("outbound dispatch:", d.status_code, d.text[:200])
    assert d.status_code == 400 and "meminta QC" in d.text
    # SPK
    s = requests.post(f"{BASE}/inspections", json={"kind": "sales_order", "ref_doc_id": sid}, headers=admin, timeout=30)
    print("spk:", s.status_code, s.text[:200])
    if reserved:
        assert s.status_code == 200
        assert {ln["roll_id"] for ln in s.json()["lines"]} == {x["id"] for x in reserved if x["status"] == "reserved"}
    # bypass probe: generic advance endpoint (reported, not asserted)
    a = requests.post(f"{BASE}/wms/tasks/{tid}/advance", headers=admin, timeout=60)
    print("ADVANCE BYPASS PROBE:", a.status_code, a.text[:300])
