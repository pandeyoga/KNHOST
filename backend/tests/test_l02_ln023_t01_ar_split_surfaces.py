"""L02 LN-023-T01 follow-up — Piutang ledger vs Eksposur split on every surface
(customer 360 credit, sales/admin/manager home, /sales/kpi, order journey, AR aging)."""
import os
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ENT = "ent_ksc"
CUST = "cust_TEST_ln023t01"
SO = "so_TEST_ln023t01"
JE = "je_TEST_ln023t01_shp"
SALES_ID = "user_sales_01"
GT = 10_000_000.0
EPS = 0.05


def _login(email, pwd):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pwd})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


def _cleanup():
    DB.journal_entries.delete_many({"$or": [{"id": JE}, {"ref.order_id": SO}, {"source_id": SO}]})
    DB.sales_orders.delete_many({"id": SO})
    DB.customers.delete_many({"id": CUST})
    DB.doc_refs.delete_many({"$or": [{"from_id": SO}, {"to_id": SO}]})


@pytest.fixture(scope="module")
def H():
    return {"admin": _login("admin@kainnusantara.id", "demo12345"),
            "sales": _login("sales@kainnusantara.id", "demo12345"),
            "manager": _login("manager@kainnusantara.id", "demo12345")}


def _snap(H):
    """Collect every surface's ar numbers."""
    out = {}
    r = requests.get(f"{BASE}/sales/kpi", headers=H["sales"]); assert r.status_code == 200, r.text
    out["kpi"] = r.json()
    r = requests.get(f"{BASE}/home/sales", headers=H["sales"]); assert r.status_code == 200, r.text
    out["home_sales"] = r.json()["kpi"]
    r = requests.get(f"{BASE}/home/admin", headers=H["admin"]); assert r.status_code == 200, r.text
    out["home_admin"] = r.json()["ar"]
    r = requests.get(f"{BASE}/home/manager", headers=H["manager"]); assert r.status_code == 200, r.text
    out["home_manager"] = r.json()["totals"]
    return out


@pytest.fixture(scope="module")
def baseline(H):
    _cleanup()
    snap = _snap(H)
    cust = DB.customers.find_one({"id": "cust_butik_bali"}, {"_id": 0})
    cust.update({"id": CUST, "code": "TEST_LN023T01", "name": "TEST_LN023T01 Customer", "entity_id": ENT,
                 "credit_limit": 0, "status": "active", "deposit_balance": 0, "assigned_sales_id": SALES_ID})
    DB.customers.insert_one(dict(cust))
    so = (DB.sales_orders.find_one({"id": "so_97e1a0a7a24c"}, {"_id": 0})
          or DB.sales_orders.find_one({"entity_id": ENT, "id": {"$not": {"$regex": "TEST"}}}, {"_id": 0}))
    assert so, "no template SO found in ent_ksc"
    now = datetime.now(timezone.utc).isoformat()
    so.update({"id": SO, "number": "KSC/TEST_SO-LN023T01", "customer_id": CUST, "customer_name": cust["name"],
               "status": "confirmed", "payments": [], "paid_total": 0, "payment_status": "pending",
               "grand_total": GT, "total_amount": GT, "allocations": [], "refs": [], "entity_id": ENT,
               "payment_term_code": "NET30", "created_at": now, "sales_id": SALES_ID, "created_by": SALES_ID})
    so.pop("payment_profile_method", None)
    DB.sales_orders.insert_one(dict(so))
    yield snap
    if not os.environ.get("LN023_KEEP"):
        _cleanup()


def _c360(H):
    r = requests.get(f"{BASE}/customers/{CUST}/360", headers=H["admin"])
    assert r.status_code == 200, r.text
    d = r.json()
    return d.get("credit") or d.get("customer", {}).get("credit")


def _journey(H, who="admin"):
    r = requests.get(f"{BASE}/sales-orders/{SO}/journey", headers=H[who])
    assert r.status_code == 200, r.text
    return r.json()


def _aging(H):
    r = requests.get(f"{BASE}/ar/aging/{CUST}", headers=H["admin"])
    assert r.status_code == 200, r.text
    return r.json()


def _assert_delta(H, base, ledger, exposure):
    now = _snap(H)
    for k in ("kpi", "home_sales"):
        b, n = base[k], now[k]
        assert abs((n["ar_outstanding"] - b["ar_outstanding"]) - (ledger + exposure)) < EPS, (k, b, n)
        assert abs((n["ar_ledger"] - b["ar_ledger"]) - ledger) < EPS, (k, b, n)
        assert abs((n["exposure"] - b["exposure"]) - exposure) < EPS, (k, b, n)
        assert abs(n["ar_ledger"] + n["exposure"] - n["ar_outstanding"]) < EPS, k
    a, ab = now["home_admin"], base["home_admin"]
    assert abs(a["ar_ledger"] + a["exposure"] - a["outstanding"]) < EPS, a
    assert abs((a["ar_ledger"] - ab["ar_ledger"]) - ledger) < EPS, (ab, a)
    assert abs((a["exposure"] - ab["exposure"]) - exposure) < EPS, (ab, a)
    m, mb = now["home_manager"], base["home_manager"]
    assert abs(m["ar_ledger"] + m["exposure"] - m["ar_outstanding"]) < EPS, m
    assert abs((m["ar_ledger"] - mb["ar_ledger"]) - ledger) < EPS, (mb, m)
    assert abs((m["exposure"] - mb["exposure"]) - exposure) < EPS, (mb, m)


class TestT01Surfaces:
    def test_baseline_invariants(self, baseline):
        for k in ("kpi", "home_sales"):
            v = baseline[k]
            assert {"ar_ledger", "exposure", "ar_outstanding"} <= set(v), k
            assert abs(v["ar_ledger"] + v["exposure"] - v["ar_outstanding"]) < EPS, (k, v)
        a = baseline["home_admin"]
        assert abs(a["ar_ledger"] + a["exposure"] - a["outstanding"]) < EPS, a
        m = baseline["home_manager"]
        assert abs(m["ar_ledger"] + m["exposure"] - m["ar_outstanding"]) < EPS, m

    # stage 1: confirmed, unshipped, NET30 → all exposure
    def test_stage1_customer360_journey_aging(self, H, baseline):
        c = _c360(H)
        assert c["ar_outstanding"] == GT and c["ar_ledger"] == 0 and c["exposure"] == GT, c
        j = _journey(H)
        assert j["outstanding"] == GT and j["ar_ledger"] == 0 and j["exposure"] == GT
        d = _aging(H)
        assert d["totals"]["ar_ledger"] == 0 and d["totals"]["exposure"] == GT, d["totals"]

    def test_stage1_home_kpi_deltas(self, H, baseline):
        _assert_delta(H, baseline, 0.0, GT)

    def test_stage1_sales_owner_journey(self, H, baseline):
        j = _journey(H, "sales")
        assert j["ar_ledger"] == 0 and j["exposure"] == GT

    # stage 2: shipment_revenue JE for 4jt → split moves
    def test_stage2_partial_shipment_split(self, H, baseline):
        DB.journal_entries.insert_one({
            "id": JE, "number": "KSC/TEST_JE-LN023T01", "source_type": "shipment_revenue",
            "source": "shipment_revenue", "source_id": "shp_TEST_ln023t01", "status": "posted", "entity_id": ENT,
            "description": "TEST_LN023T01 pengakuan", "ref": {"order_id": SO, "order_number": "KSC/TEST_SO-LN023T01"},
            "date": "2026-01-10T00:00:00+00:00", "created_at": "2026-01-10T00:00:00+00:00",
            "lines": [{"account_code": "1-1200", "debit": 4_000_000.0, "credit": 0.0},
                      {"account_code": "4-1000", "debit": 0.0, "credit": 4_000_000.0}],
            "total_debit": 4_000_000.0, "total_credit": 4_000_000.0})
        c = _c360(H)
        j = _journey(H)
        d = _aging(H)
        assert c["ar_ledger"] == 4_000_000.0 and c["exposure"] == 6_000_000.0, c
        assert j["ar_ledger"] == 4_000_000.0 and j["exposure"] == 6_000_000.0
        assert d["totals"]["ar_ledger"] == 4_000_000.0 and d["totals"]["exposure"] == 6_000_000.0
        assert c["ar_outstanding"] == j["outstanding"] == GT

    def test_stage2_home_kpi_deltas(self, H, baseline):
        _assert_delta(H, baseline, 4_000_000.0, 6_000_000.0)

    # stage 3: payment 1.5jt (direct DB) → ledger shrinks, exposure unchanged
    def test_stage3_payment_reduces_ledger(self, H, baseline):
        DB.sales_orders.update_one({"id": SO}, {"$set": {
            "payments": [{"amount": 1_500_000.0, "created_at": datetime.now(timezone.utc).isoformat(),
                          "method": "transfer"}], "paid_total": 1_500_000.0, "payment_status": "partial"}})
        c, j, d = _c360(H), _journey(H), _aging(H)
        for name, v in (("c360", c), ("journey", j)):
            assert v["ar_ledger"] == 2_500_000.0 and v["exposure"] == 6_000_000.0, (name, v.get("ar_ledger"), v.get("exposure"))
        assert c["ar_outstanding"] == j["outstanding"] == 8_500_000.0
        assert d["totals"]["ar_ledger"] == 2_500_000.0 and d["totals"]["exposure"] == 6_000_000.0
        _assert_delta(H, baseline, 2_500_000.0, 6_000_000.0)

    # credit gating uses full ar_outstanding by design
    def test_credit_limit_gating_uses_full_outstanding(self, H, baseline):
        DB.customers.update_one({"id": CUST}, {"$set": {"credit_limit": 9_000_000.0}})
        try:
            c = _c360(H)
            assert c["available_credit"] == 500_000.0, c
            assert c["status"] in ("warning", "blocked")
        finally:
            DB.customers.update_one({"id": CUST}, {"$set": {"credit_limit": 0}})

    # edge: cancelled / expired order → journey has no outstanding / ledger / exposure
    @pytest.mark.parametrize("status", ["cancelled", "expired"])
    def test_cancelled_order_journey_split(self, H, baseline, status):
        DB.sales_orders.update_one({"id": SO}, {"$set": {"status": status}})
        try:
            j = _journey(H)
            c = _c360(H)
            assert c["ar_outstanding"] == 0
            print(f"{status} journey:", j["outstanding"], j["ar_ledger"], j["exposure"])
            assert j["cancelled"] is True
            assert j["outstanding"] == 0 and j["ar_ledger"] == 0 and j["exposure"] == 0, j
            step = next(s for s in j["steps"] if s["key"] == "dibayar")
            assert step["done"] is False and step["state"] == "cancelled", step
            assert step["detail"] == "Pesanan dibatalkan — tidak ada tagihan", step
            assert "Sisa tagihan" not in str(j["steps"])
            assert j["current_step"] == "dibatalkan"
            js = _journey(H, "sales")
            assert js["outstanding"] == 0 and js["exposure"] == 0
        finally:
            DB.sales_orders.update_one({"id": SO}, {"$set": {"status": "confirmed"}})

    # regression: back to confirmed → split restored
    def test_after_uncancel_split_restored(self, H, baseline):
        j = _journey(H)
        assert j["cancelled"] is False
        assert j["outstanding"] == 8_500_000.0
        assert abs(j["ar_ledger"] + j["exposure"] - j["outstanding"]) < EPS
        step = next(s for s in j["steps"] if s["key"] == "dibayar")
        assert step["detail"].startswith("Sisa tagihan"), step

    # regression: shipped status (non-cancelled) → ledger+exposure == outstanding
    def test_shipped_status_split_invariant(self, H, baseline):
        DB.sales_orders.update_one({"id": SO}, {"$set": {"status": "shipped"}})
        try:
            j = _journey(H)
            assert j["outstanding"] == 8_500_000.0
            assert abs(j["ar_ledger"] + j["exposure"] - j["outstanding"]) < EPS, j
        finally:
            DB.sales_orders.update_one({"id": SO}, {"$set": {"status": "confirmed"}})
