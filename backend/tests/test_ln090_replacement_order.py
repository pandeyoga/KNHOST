"""LN-090 T02/T03 — pesanan pengganti nyata (KLR-03/04/05): qty dari QC (yard), harga asal, saldo → selisih."""
import os
import subprocess
import sys
import uuid

import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
T = uuid.uuid4().hex[:6]


def _login(email, pw="demo12345"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


ADMIN = _login("admin@kainnusantara.id", "demo12345")


def _seed(status="credit_settled", rtype="penggantian", accepted=10.0):
    src = DB.sales_orders.find_one({"number": "KSC/SO-00003"}, {"_id": 0})
    pid = "prod_batik_mega"   # satuan dasar yard, stok tersedia di KSC
    so = f"so_TEST_RPL_{T}_{uuid.uuid4().hex[:4]}"
    DB.sales_orders.insert_one({**{k: src[k] for k in ("customer_id", "customer_name", "shipping_address_id", "entity_id")},
                                "id": so, "number": f"TEST_SO-{so}", "status": "shipped", "payment_term_code": "NET30",
                                "items": [{"product_id": pid, "quantity": 20, "base_quantity": 20, "line_total": 600000}],
                                "grand_total": 600000, "qc_request": {"mode": "none"}})
    rid = f"sr_TEST_RPL_{T}_{uuid.uuid4().hex[:4]}"
    DB.sales_returns.insert_one({"id": rid, "number": f"TEST_RET-RPL-{rid[-4:]}", "order_id": so, "entity_id": "ent_ksc",
                                 "customer_id": src["customer_id"], "return_type": rtype, "status": status,
                                 "items": [{"product_id": pid, "product_name": "TEST", "unit": "yard", "quantity_returned": accepted,
                                            "inspection": {"accepted_qty": accepted, "grade": "A"}}]})
    return so, rid, pid


def _issue(rid, cust, amount):
    code = ("import asyncio; from services import store_credit_service as sc; "
            f"asyncio.run(sc.issue(customer_id='{cust}', entity_id='ent_ksc', amount={amount}, "
            f"ref_type='sales_return', ref_id='{rid}', ref_number='TEST', actor='test'))")
    subprocess.run([sys.executable, "-c", code], check=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_ln090_t03_requires_store_credit_and_same_article():
    _, rid, pid = _seed(status="inspected")
    r = requests.post(f"{BASE}/sales-returns/{rid}/replacement-order", headers=ADMIN, json={"items": [{"product_id": pid, "qty_yard": 5}]})
    assert r.status_code == 400 and "Store Credit" in r.text
    _, rid2, _ = _seed()
    r = requests.post(f"{BASE}/sales-returns/{rid2}/replacement-order", headers=ADMIN, json={"items": [{"product_id": "pX", "qty_yard": 5}]})
    assert r.status_code == 400 and "artikel" in r.text


def test_ln090_t02_t03_replacement_order_original_price_and_difference():
    so, rid, pid = _seed(accepted=10.0)
    pv = requests.get(f"{BASE}/sales-returns/{rid}/replacement", headers=ADMIN).json()
    ob = pv["obligation"][0]
    assert ob["unit_price_base"] == 30000 and ob["qty_base"] == 10 and ob["qty_yard"] == 10
    cust = DB.sales_returns.find_one({"id": rid})["customer_id"]
    _issue(rid, cust, 300000)
    r = requests.post(f"{BASE}/sales-returns/{rid}/replacement-order", headers=ADMIN,
                      json={"items": [{"product_id": pid, "qty_yard": 12}]})
    assert r.status_code == 200, r.text
    out = r.json()
    new = DB.sales_orders.find_one({"id": out["order"]["id"]})
    assert new["replacement_for_return"]["return_id"] == rid
    assert abs(new["items"][0]["price"] - 30000) < 0.01           # KLR-05 — harga transaksi asal
    s = out["summary"]
    assert s["credit_applied"] == 300000 and s["to_bill"] > 0     # KLR-04 — lebih → selisih ditagih
    again = requests.post(f"{BASE}/sales-returns/{rid}/replacement-order", headers=ADMIN,
                          json={"items": [{"product_id": pid, "qty_yard": 1}]})
    assert again.status_code in (400, 409)
    appr = DB.price_approvals.find_one({"replacement_return_id": rid})
    assert appr["scope"] == "order" and appr["so_id"] == new["id"]  # harga sekali pakai


def test_ln090_replacement_same_grade_as_sold():
    so, rid, pid = _seed(accepted=5.0)
    ref = DB.inventory_rolls.find_one({"product_id": pid, "owner_entity_id": "ent_ksc", "status": "available",
                                       "grade": {"$nin": [None, "", "BS"]}}, {"_id": 0, "id": 1, "grade": 1})
    assert ref, "butuh roll available prod_batik_mega di KSC"
    DB.sales_returns.update_one({"id": rid}, {"$set": {"items.0.roll_ids": [ref["id"]]}})
    pv = requests.get(f"{BASE}/sales-returns/{rid}/replacement", headers=ADMIN).json()
    assert pv["obligation"][0]["sold_grade"] == ref["grade"]
    _issue(rid, DB.sales_returns.find_one({"id": rid})["customer_id"], 150000)
    r = requests.post(f"{BASE}/sales-returns/{rid}/replacement-order", headers=ADMIN,
                      json={"items": [{"product_id": pid, "qty_yard": 5}]})
    assert r.status_code == 200, r.text
    new = DB.sales_orders.find_one({"id": r.json()["order"]["id"]})
    assert new["items"][0]["required_grade"] == ref["grade"]
    ids = [x["roll_id"] for a in new.get("allocations") or [] for x in a.get("rolls") or []]
    grades = {g["grade"] for g in DB.inventory_rolls.find({"id": {"$in": ids}}, {"grade": 1})}
    assert grades <= {ref["grade"]}, grades

def test_ln090_cancel_replacement_restores_credit_and_allows_new():
    so, rid, pid = _seed(accepted=5.0)
    cust = DB.sales_returns.find_one({"id": rid})["customer_id"]
    _issue(rid, cust, 150000)
    r = requests.post(f"{BASE}/sales-returns/{rid}/replacement-order", headers=ADMIN, json={"items": [{"product_id": pid, "qty_yard": 5}]})
    assert r.status_code == 200, r.text
    new_id = r.json()["order"]["id"]
    c = requests.post(f"{BASE}/sales-orders/{new_id}/cancel", headers=ADMIN, json={"reason": "TEST batal pengganti"})
    assert c.status_code == 200, c.text
    ret = DB.sales_returns.find_one({"id": rid})
    assert not ret.get("replacement_order_id") and ret["replacement_history"][-1]["order_id"] == new_id
    assert DB.store_credit_redemptions.count_documents({"allocations.order_id": new_id, "status": {"$ne": "void"}}) == 0
    r2 = requests.post(f"{BASE}/sales-returns/{rid}/replacement-order", headers=ADMIN, json={"items": [{"product_id": pid, "qty_yard": 5}]})
    assert r2.status_code == 200 and r2.json()["summary"]["credit_applied"] > 0, r2.text





def teardown_module(_m):
    rets = [r["id"] for r in DB.sales_returns.find({"id": {"$regex": f"^sr_TEST_RPL_{T}"}}, {"id": 1, "replacement_order_id": 1})]
    for r in DB.sales_returns.find({"id": {"$in": rets}}, {"replacement_order_id": 1}):
        if r.get("replacement_order_id"):
            requests.post(f"{BASE}/sales-orders/{r['replacement_order_id']}/cancel", headers=ADMIN, json={"reason": "TEST cleanup"})
    DB.sales_returns.delete_many({"id": {"$in": rets}})
    DB.sales_orders.delete_many({"id": {"$regex": f"^so_TEST_RPL_{T}"}})
    DB.price_approvals.delete_many({"replacement_return_id": {"$in": rets}})
    DB.store_credit_ledger.delete_many({"ref_id": {"$in": rets}})
