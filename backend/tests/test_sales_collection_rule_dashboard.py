"""Aturan tagihan sales (pelanggan milik + pesanan buatannya), status kredit saat checkout, dasbor pesanan HP."""
import os

import pytest
import requests
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _h(email, pw="demo12345"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def ayu():
    return _h("sales@kainnusantara.id")


def _own_unassigned_order(shipped=False):
    """`shipped=True` — F-16 (keputusan owner Q-05a): hanya pesanan yang sudah ber-Surat Jalan punya jatuh tempo
    dan masuk daftar tagih; pesanan belum dikirim sengaja tidak muncul."""
    u = DB.users.find_one({"email": "sales@kainnusantara.id"})
    for o in DB.sales_orders.find({"sales_id": u["id"], "status": {"$nin": ["cancelled", "draft", "rejected"]}}):
        if shipped and (o.get("payment_status") == "paid" or not DB.shipments.find_one({"order_id": o["id"]}, {"_id": 1})):
            continue
        c = DB.customers.find_one({"id": o["customer_id"]}) or {}
        if c.get("assigned_sales_id") != u["id"]:
            return u, o, c
    pytest.skip("tidak ada pesanan Ayu untuk pelanggan sales lain")


def test_worklist_includes_own_orders_for_other_customers(ayu):
    u, o, c = _own_unassigned_order(shipped=True)
    rows = requests.get(f"{BASE}/collection-reminders", params={"days_ahead": 60}, headers=ayu, timeout=30).json()
    if o.get("payment_status") == "paid":
        pytest.skip("pesanan sudah lunas")
    mine = [r for r in rows if r["order_id"] == o["id"]]
    assert mine and mine[0]["via_own_order"] is True


def test_worklist_excludes_other_sales_orders(ayu):
    u = DB.users.find_one({"email": "sales@kainnusantara.id"})
    rows = requests.get(f"{BASE}/collection-reminders", params={"days_ahead": 60}, headers=ayu, timeout=30).json()
    for r in rows:
        o = DB.sales_orders.find_one({"id": r["order_id"]})
        c = DB.customers.find_one({"id": r["customer_id"]}) or {}
        assert o.get("sales_id") == u["id"] or c.get("assigned_sales_id") == u["id"]


def test_followup_allowed_for_own_order_customer(ayu):
    u, o, c = _own_unassigned_order()
    r = requests.post(f"{BASE}/customers/{c['id']}/followups", json={"customer_id": c["id"], "order_id": o["id"], "note": "TEST_ follow-up", "outcome": "contacted"},
                      headers=ayu, timeout=30)
    assert r.status_code == 200, r.text
    DB.collection_followups.delete_many({"note": "TEST_ follow-up"})


def test_followup_denied_for_unrelated_customer(ayu):
    u = DB.users.find_one({"email": "sales@kainnusantara.id"})
    ordered = DB.sales_orders.distinct("customer_id", {"sales_id": u["id"]})
    c = DB.customers.find_one({"entity_id": "ent_ksc", "assigned_sales_id": {"$ne": u["id"]}, "id": {"$nin": ordered}})
    if not c:
        pytest.skip("tak ada pelanggan lain")
    r = requests.post(f"{BASE}/customers/{c['id']}/followups", json={"customer_id": c["id"], "note": "TEST_ x", "outcome": "contacted"}, headers=ayu, timeout=30)
    assert r.status_code == 403


def test_credit_status_same_entity_ok_cross_entity_denied(ayu):
    c = DB.customers.find_one({"entity_id": "ent_ksc"})
    assert requests.get(f"{BASE}/customers/{c['id']}/credit-status", params={"amount": 1000}, headers=ayu, timeout=30).status_code == 200
    k = DB.customers.find_one({"entity_id": "ent_kanda"})
    if k:
        assert requests.get(f"{BASE}/customers/{k['id']}/credit-status", headers=ayu, timeout=30).status_code == 403


def test_order_dashboard_shape_and_scope(ayu):
    r = requests.get(f"{BASE}/sales/order-dashboard", params={"sales_id": "user_other"}, headers=ayu, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert len(d["weekly"]) == 8 and [s["key"] for s in d["status_counts"]] == ["waiting", "processing", "shipped", "done"]
    u = DB.users.find_one({"email": "sales@kainnusantara.id"})
    total = sum(s["count"] for s in d["status_counts"])
    # UAT 24 Okt (audit UI HP) — kepemilikan = aturan "Pesanan Saya" (pembuat / sales_id / anggota tim) dan semua status
    # hidup ikut terhitung (menunggu stok, dikemas, dalam perjalanan dulu hilang dari kartu status).
    from services.sales_order_dashboard import BUCKETS
    live_status = sorted(set().union(*BUCKETS.values()))
    live = DB.sales_orders.count_documents({"$or": [{"created_by": u["id"]}, {"sales_id": u["id"]}, {"sales_team.sales_id": u["id"]}],
                                            "status": {"$in": live_status}})
    assert total == live
    assert len(d["top_customers"]) <= 5


def test_order_dashboard_manager_can_pick_sales():
    m = _h("manager@kainnusantara.id")
    u = DB.users.find_one({"email": "sales.kanda@kainnusantara.id"})
    assert requests.get(f"{BASE}/sales/order-dashboard", params={"sales_id": u["id"]}, headers=m, timeout=30).status_code == 200
