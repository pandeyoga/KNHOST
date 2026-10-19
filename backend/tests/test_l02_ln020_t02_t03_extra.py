"""L02 LN-020-T02 (keep-pending sales scoping) + LN-021-T01 round_down edge (FEFO order) — testing agent extra."""
import os

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ENT = "ent_ksc"
PID = "prod_TEST_l021b"


def _tok(email, pwd):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pwd})
    assert r.status_code == 200, r.text[:200]
    return r.json()["token"]


def _h(email, pwd="demo1234", ent=None):
    h = {"Authorization": f"Bearer {_tok(email, pwd)}"}
    if ent:
        h["X-Entity-Id"] = ent
    return h


# ── LN-020-T02 keep-pending scoping ──
class TestKeepPendingScope:
    def test_sales_can_read_and_is_scoped(self):
        uid = DB.users.find_one({"email": "sales.kanda@kainnusantara.id"}, {"_id": 0, "id": 1})["id"]
        r = requests.get(f"{BASE}/sales/keep-pending", headers=_h("sales.kanda@kainnusantara.id", ent="ent_kanda"))
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        ids = {k["order_id"] for k in d["keep"]} | {o["order_id"] for p in d["pending"] for o in p["orders"]} \
            | {t["order_id"] for t in d["in_transit"]}
        for so in DB.sales_orders.find({"id": {"$in": list(ids)}}, {"_id": 0}):
            own = so.get("created_by") == uid or so.get("sales_id") == uid or any(
                m.get("sales_id") == uid for m in so.get("sales_team") or [])
            assert own, f"sales sees foreign SO {so.get('number')}"
        print("sales counts", d["counts"], "ids", len(ids))

    def test_sales_admin_sees_entity_superset(self):
        s = requests.get(f"{BASE}/sales/keep-pending", headers=_h("sales.kanda@kainnusantara.id", ent="ent_kanda")).json()
        a = requests.get(f"{BASE}/sales/keep-pending",
                         headers=_h("salesadmin.kanda@kainnusantara.id", ent="ent_kanda")).json()
        assert a["counts"]["unique_orders"] >= s["counts"]["unique_orders"]
        assert a["counts"]["pending_orders"] >= s["counts"]["pending_orders"]
        print("admin counts", a["counts"])

    def test_pending_no_supplier_or_owner_names(self):
        d = requests.get(f"{BASE}/sales/keep-pending", headers=_h("sales.kanda@kainnusantara.id", ent="ent_kanda")).json()
        txt = str(d["pending"]).lower()
        for k in ("supplier_name", "owner_entity", "vendor", "'supplier'"):
            assert k not in txt, k

    def test_unauth_401(self):
        assert requests.get(f"{BASE}/sales/keep-pending").status_code in (401, 403)


# ── LN-021-T01 round_down when long roll is FIRST in FEFO ──
@pytest.fixture(scope="module")
def H():
    tpl_roll = DB.inventory_rolls.find_one({"owner_entity_id": ENT, "status": "available", "unit": "yard"}, {"_id": 0})
    tpl_prod = DB.products.find_one({"id": tpl_roll["product_id"]}, {"_id": 0})
    DB.products.insert_one({**tpl_prod, "id": PID, "sku": "TEST-L021B", "name": "TEST_L021B KAIN", "variant_key": f"TEST_{PID}"})
    for i, ln in enumerate([105] + [100] * 9):
        roll = {k: v for k, v in tpl_roll.items() if k not in (
            "reserved_ref", "reserved_for_order", "length_reservations", "length_reserved", "active_movement",
            "epc", "tag_epc", "rfid_epc", "barcode")}
        DB.inventory_rolls.insert_one({**roll, "id": f"roll_TEST_l021b_{i}", "roll_no": f"TEST-L021B-{i:02d}",
                                       "product_id": PID, "length_remaining": float(ln), "length_original": float(ln),
                                       "status": "available", "grade": "A",
                                       "created_at": f"2026-01-01T00:00:{i:02d}+00:00"})
    yield {"Authorization": f"Bearer {_tok('admin@kainnusantara.id', 'demo12345')}", "X-Entity-Id": ENT}
    DB.inventory_rolls.delete_many({"product_id": PID})
    DB.products.delete_one({"id": PID})


def _preview(h, target):
    r = requests.post(f"{BASE}/sales-orders/preview-roll-reconcile", headers=h,
                      json={"entity_id": ENT, "items": [{"product_id": PID, "quantity": target, "unit": "yard"}]})
    assert r.status_code == 200, r.text[:300]
    return r.json()[0]["options"]


def test_round_down_long_roll_first(H):
    o = _preview(H, 1000)
    print({k: (v["total_qty"], v["roll_count"]) for k, v in o.items()})
    assert o["round_up"]["total_qty"] == 1005
    assert (o["round_down"]["total_qty"], o["round_down"]["roll_count"]) == (905, 9)
    assert o["exact_cut"]["total_qty"] == 1000


def test_exact_target_no_round(H):
    o = _preview(H, 905)
    print({k: (v["total_qty"], v["roll_count"]) for k, v in o.items()})
    assert o["round_up"]["total_qty"] == 905
    assert "exact_whole" in o


def test_infeasible_take_all(H):
    o = _preview(H, 2000)
    assert "take_all" in o and o["take_all"]["backorder_qty"] == 995


def test_stock_summary_shape(H):
    r = requests.get(f"{BASE}/sales/stock-summary", headers=H, params={"product_id": PID, "entity_id": ENT})
    d = r.json()
    assert r.status_code == 200 and isinstance(d["atp_horizon_days"], int)
    row = d["rows"][0]
    for k in ("physical", "free", "reserved", "incoming", "pending_demand", "atp"):
        assert k in row


def test_foreign_so_hidden_from_sales_visible_to_admin():
    """Synthetic TEST_ SO owned by admin in ent_kanda: sales.kanda must NOT see it, salesadmin.kanda must."""
    adm = DB.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0, "id": 1})["id"]
    sid = "so_TEST_kp_foreign"
    DB.sales_orders.insert_one({"id": sid, "number": "KANDA/TEST_KP-1", "entity_id": "ent_kanda", "status": "reserved",
                                "created_by": adm, "sales_id": adm, "customer_name": "TEST_CUST",
                                "created_at": "2026-01-01T00:00:00+00:00", "items": [], "grand_total": 0})
    try:
        s = requests.get(f"{BASE}/sales/keep-pending",
                         headers=_h("sales.kanda@kainnusantara.id", ent="ent_kanda")).json()
        a = requests.get(f"{BASE}/sales/keep-pending",
                         headers=_h("salesadmin.kanda@kainnusantara.id", ent="ent_kanda")).json()
        assert sid not in {k["order_id"] for k in s["keep"]}
        assert sid in {k["order_id"] for k in a["keep"]}
    finally:
        DB.sales_orders.delete_one({"id": sid})
