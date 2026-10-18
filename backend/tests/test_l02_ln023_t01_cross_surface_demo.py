"""L02 LN-023-T01 — cross-surface consistency on real demo data (customer 360 credit vs AR aging detail,
GL 1-1200 sanity, sales-force KPI invariant). Read-only."""
import os

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
EPS = 0.05


def _login(email, pwd, ent):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pwd})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ent}


@pytest.fixture(scope="module")
def tok():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
    assert r.status_code == 200
    return r.json()["token"]


def _customers_with_orders():
    ids = DB.sales_orders.distinct("customer_id", {"status": {"$nin": ["cancelled", "expired", "draft"]}})
    return [c for c in DB.customers.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "entity_id": 1}) if c.get("entity_id")]


# customer 360 credit vs aging detail totals for every demo customer that has orders
def test_c360_vs_aging_detail_all_customers(tok):
    custs = _customers_with_orders()
    assert custs, "no demo customers with orders"
    mism = []
    for c in custs:
        h = {"Authorization": f"Bearer {tok}", "X-Entity-Id": c["entity_id"]}
        r1 = requests.get(f"{BASE}/customers/{c['id']}/360", headers=h)
        r2 = requests.get(f"{BASE}/ar/aging/{c['id']}", headers=h)
        assert r1.status_code == 200 and r2.status_code == 200, (c, r1.status_code, r2.status_code)
        cr = r1.json().get("credit") or {}
        t = r2.json().get("totals") or {}
        assert abs(cr["ar_ledger"] + cr["exposure"] - cr["ar_outstanding"]) < EPS, (c, cr)
        if abs(cr["ar_ledger"] - t.get("ar_ledger", 0)) > EPS or abs(cr["exposure"] - t.get("exposure", 0)) > EPS:
            mism.append((c["id"], cr["ar_ledger"], t.get("ar_ledger"), cr["exposure"], t.get("exposure")))
    print(f"checked {len(custs)} customers, mismatches: {mism}")
    assert not mism, mism


# order journey split sums to outstanding for every non-cancelled demo order
def test_journey_split_invariant_all_orders(tok):
    bad = []
    orders = list(DB.sales_orders.find({"status": {"$nin": ["draft"]}}, {"_id": 0, "id": 1, "entity_id": 1, "status": 1}).limit(60))
    for o in orders:
        h = {"Authorization": f"Bearer {tok}", "X-Entity-Id": o.get("entity_id") or "ent_ksc"}
        r = requests.get(f"{BASE}/sales-orders/{o['id']}/journey", headers=h)
        assert r.status_code == 200, (o, r.text[:200])
        j = r.json()
        if abs(j["ar_ledger"] + j["exposure"] - j["outstanding"]) > EPS or j["ar_ledger"] < 0 or j["exposure"] < 0:
            bad.append((o["id"], j["outstanding"], j["ar_ledger"], j["exposure"]))
        if o["status"] in ("cancelled", "expired") and j["exposure"] > EPS:
            bad.append(("cancelled_with_exposure", o["id"], j["exposure"]))
    print(f"checked {len(orders)} orders; bad: {bad}")
    assert not bad, bad


# sales-force KPI (sales.kanda on ent_kanda) invariant
def test_sales_kpi_kanda_invariant():
    h = _login("sales.kanda@kainnusantara.id", "demo1234", "ent_kanda")
    for path in ("/sales/kpi", "/home/sales"):
        r = requests.get(f"{BASE}{path}", headers=h)
        assert r.status_code == 200, r.text
        d = r.json()
        k = d.get("kpi", d) if path == "/home/sales" else d
        assert abs(k["ar_ledger"] + k["exposure"] - k["ar_outstanding"]) < EPS, (path, k)
        print(path, k["ar_outstanding"], k["ar_ledger"], k["exposure"])
