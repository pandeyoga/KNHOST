"""COMM-04 campaign vendor bills — edge cases (iteration 191): generic vendor-bill endpoint bypass, concurrency."""
import os
import concurrent.futures as cf

import pytest
import requests
from pymongo import MongoClient

B = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]


def _h(email, pw="demo12345"):
    t = requests.post(f"{B}/auth/login", json={"email": email, "password": pw}, timeout=30).json()["token"]
    return {"Authorization": f"Bearer {t}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture(scope="module")
def ctx():
    h = {"a": _h("admin@kainnusantara.id", "demo12345"), "f": _h("finance@kainnusantara.id"),
         "m": _h("manager@kainnusantara.id"), "sa": _h("salesadmin@kainnusantara.id")}
    c = requests.post(f"{B}/marketing/campaigns", json={"name": "TEST_COMM04E", "budget": 1000000}, headers=h["m"]).json()
    h["c"] = c
    h["v"] = requests.get(f"{B}/marketing/vendor-options", headers=h["m"]).json()
    yield h
    bills = [b["id"] for b in DB.vendor_bills.find({"campaign_id": c["id"]})]
    cash = [x["id"] for x in DB.cash_transactions.find({"ref_id": {"$in": bills}})]
    DB.journal_entries.delete_many({"source_id": {"$in": bills + cash}})
    DB.cash_transactions.delete_many({"id": {"$in": cash}})
    DB.vendor_bills.delete_many({"id": {"$in": bills}})
    DB.notifications.delete_many({"ref": {"$in": [f"mkt_bill:{b}" for b in bills]}})
    DB.mkt_campaigns.delete_one({"id": c["id"]})


def _mk(ctx, inv, amount=100000):
    r = requests.post(f"{B}/marketing/campaigns/{ctx['c']['id']}/vendor-bills", headers=ctx["m"], json={
        "supplier_id": ctx["v"][0]["id"], "supplier_invoice_no": inv, "description": "Iklan TEST",
        "amount": amount, "ppn_amount": 0})
    assert r.status_code == 200, r.text
    return r.json()


# SoD/role: sales_admin must not approve campaign bill through generic /vendor-bills/{id}/approve
def test_generic_approve_by_sales_admin_blocked(ctx):
    b = _mk(ctx, "TEST-E-1")
    r = requests.post(f"{B}/vendor-bills/{b['id']}/approve", headers=ctx["sa"])
    print("generic approve by sales_admin:", r.status_code, r.text[:200])
    assert r.status_code == 403


# Generic reject should not bypass min-5 reason rule / role
def test_generic_reject_by_sales_admin_blocked(ctx):
    b = _mk(ctx, "TEST-E-2")
    r = requests.post(f"{B}/vendor-bills/{b['id']}/reject", headers=ctx["sa"], json={"notes": ""})
    print("generic reject by sales_admin:", r.status_code, r.text[:200])
    assert r.status_code == 403


# Concurrency: two approvals at once → exactly one JE
def test_concurrent_approve_single_journal(ctx):
    b = _mk(ctx, "TEST-E-3")
    url = f"{B}/marketing/campaigns/{ctx['c']['id']}/vendor-bills/{b['id']}/approve"
    with cf.ThreadPoolExecutor(4) as ex:
        codes = [f.result().status_code for f in [ex.submit(requests.post, url, headers=ctx[k]) for k in ("f", "a", "f", "a")]]
    print("concurrent codes", codes)
    je = DB.journal_entries.count_documents({"source_type": "vendor_bill", "source_id": b["id"]})
    assert je == 1, f"journals={je} codes={codes}"
    assert codes.count(200) == 1


# Unknown campaign → 404; bill of other campaign → 404
def test_not_found(ctx):
    r = requests.post(f"{B}/marketing/campaigns/nope/vendor-bills/x/approve", headers=ctx["f"])
    assert r.status_code == 404
