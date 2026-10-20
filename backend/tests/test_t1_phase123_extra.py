"""T1 extra regression (public URL): LN-090 Ganti Roll grade lock, LN-033 T08 cancel guards, LN-012 grey, LN-102 desk cards."""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
T = uuid.uuid4().hex[:6]


def _login(email, pw="demo12345"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture(scope="module")
def H():
    return {"admin": _login("admin@kainnusantara.id", "demo12345"), "sales": _login("sales@kainnusantara.id"),
            "manager": _login("manager@kainnusantara.id"), "warehouse": _login("warehouse@kainnusantara.id")}


# --- LN-090: Ganti Roll candidates + reallocate reject other grade on replacement line
@pytest.fixture(scope="module")
def repl_so():
    src = DB.sales_orders.find_one({"number": "KSC/SO-00003"}, {"_id": 0})
    so = f"so_TEST_T1G_{T}"
    roll = f"roll_TEST_T1G_{T}"
    DB.inventory_rolls.insert_one({"id": roll, "roll_no": f"TEST_R{T}", "product_id": "prod_batik_mega", "owner_entity_id": "ent_ksc",
                                   "warehouse_id": "wh_jakarta", "status": "available", "grade": "B", "length_remaining": 30.0,
                                   "length_initial": 30.0, "unit": "yard", "created_at": "2026-10-19T00:00:00+00:00"})
    DB.sales_orders.insert_one({**{k: src[k] for k in ("customer_id", "customer_name", "shipping_address_id", "entity_id")},
                                "id": so, "number": f"TEST_SO-T1G-{T}", "status": "reserved",
                                "items": [{"product_id": "prod_batik_mega", "quantity": 5, "base_quantity": 5, "unit": "yard",
                                           "base_unit": "yard", "required_grade": "A"}]})
    yield so, roll
    DB.sales_orders.delete_many({"id": so})
    DB.inventory_rolls.delete_many({"id": roll})


def test_candidates_mark_other_grade_ineligible(H, repl_so):
    so, roll = repl_so
    r = requests.get(f"{BASE}/sales-orders/{so}/items/prod_batik_mega/roll-candidates", headers=H["admin"], timeout=30)
    assert r.status_code == 200, r.text
    row = next(x for x in r.json()["items"] if x["id"] == roll)
    assert row["eligible"] is False
    assert any("Pengganti retur wajib grade A" in m for m in row["reasons"]), row["reasons"]
    others = [x for x in r.json()["items"] if x["grade"] == "A" and x["status"] == "available"]
    assert all(not any("Pengganti retur" in m for m in x["reasons"]) for x in others)


def test_reallocate_other_grade_409(H, repl_so):
    so, roll = repl_so
    r = requests.post(f"{BASE}/sales-orders/{so}/items/prod_batik_mega/reallocate", headers=H["admin"], timeout=30,
                      json={"roll_lines": [{"roll_id": roll, "take_qty": 5}], "reason": "TEST ganti roll grade lain"})
    assert r.status_code == 409, r.text
    assert "Pengganti retur wajib grade A" in r.text


# --- LN-012-T04: greige always hidden for sales
def test_sales_never_sees_grey(H):
    r = requests.get(f"{BASE}/products?paginate=true&stage=grey&limit=50", headers=H["sales"], timeout=30)
    assert r.status_code == 200
    d = r.json()
    items = d.get("items") if isinstance(d, dict) else d
    assert all(str(p.get("stage")).lower() != "grey" for p in items)



def test_sales_so_grey_403_even_when_setting_excludes_grey(H):
    import time
    cfg = lambda v, why: requests.put(f"{BASE}/config/values", headers=H["admin"], timeout=30,  # noqa: E731
                                      json={"items": [{"key": "catalog.sales_hidden_stages", "value": v, "scope_type": "global", "reason": why}]})
    assert cfg(["yarn"], "TEST_T1 grey selalu").status_code in (200, 201)
    try:
        time.sleep(16)
        r = requests.post(f"{BASE}/sales-orders", headers=H["sales"], timeout=30, json={
            "customer_id": "cust_toko_kain", "shipping_address_id": "addr_001", "notes": "TEST_T1_grey",
            "items": [{"product_id": "prod_5ceb7db913eb", "quantity": 1, "unit_price": 10000, "unit": "m"}]})
        if r.status_code < 300:
            requests.post(f"{BASE}/sales-orders/{r.json().get('id')}/cancel", headers=H["admin"], json={"reason": "TEST cleanup"})
        assert r.status_code == 403, f"{r.status_code} {r.text[:200]}"
    finally:
        cfg(["grey", "yarn"], "restore")


def test_admin_sees_grey(H):
    r = requests.get(f"{BASE}/products?paginate=true&stage=grey&limit=50", headers=H["admin"], timeout=30)
    d = r.json()
    items = d.get("items") if isinstance(d, dict) else d
    assert any(str(p.get("stage")).lower() == "grey" for p in items)


# --- LN-102-T02: desk cards count == len(rows), no dupes, wms rows carry flow_type/po_id
@pytest.mark.parametrize("who", ["admin", "manager", "sales", "warehouse"])
def test_desk_cards_consistent(H, who):
    r = requests.get(f"{BASE}/desks/me", headers=H[who], timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    queues = d.get("queues") or [q for g in d.get("desks", []) for q in g.get("queues", [])]
    assert queues, d.keys()
    for q in queues:
        rows = q.get("rows") or []
        if "count" in q:
            assert q["count"] == len(rows), (q["id"], q["count"], len(rows))
        keys = [(x.get("ref_type"), x.get("ref_id")) for x in rows]
        assert len(keys) == len(set(keys)), f"dupe in {q['id']}"
        if q.get("id") == "tugas_wms":
            for x in rows:
                assert "flow_type" in x and "po_id" in x
