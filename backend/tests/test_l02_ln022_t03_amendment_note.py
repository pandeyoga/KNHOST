"""L02 LN-022-T03 — koreksi setelah pendapatan terjurnal lewat nota + jurnal, bukan edit histori/posting dobel."""
import os

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
SID, JE = "so_TEST_l022t03", "je_TEST_l022t03"


def _h(email, pwd, ent):
    t = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pwd}).json()["token"]
    return {"Authorization": f"Bearer {t}", "X-Entity-Id": ent}


@pytest.fixture(scope="module")
def ctx():
    DB.sales_orders.delete_one({"id": SID})   # sisa run yang crash (uq_number)
    DB.journal_entries.delete_many({"id": JE})
    src = DB.sales_orders.find_one({"status": "done", "items.0": {"$exists": True}}, {"_id": 0})
    so = {**src, "id": SID, "number": "TEST/SO-L022T03", "status": "confirmed", "payments": [], "paid_total": 0,
          "payment_status": "pending", "amendment_count": 0, "timeline": [], "notes": "TEST_L022T03"}
    DB.sales_orders.insert_one(so)
    DB.journal_entries.insert_one({"id": JE, "source_type": "shipment_revenue", "source_id": "shp_TEST_l022t03",
                                   "ref": {"order_id": SID}, "status": "posted", "entity_id": so["entity_id"],
                                   "lines": [], "description": "TEST_L022T03 fixture"})
    yield {"so": so, "admin": _h("admin@kainnusantara.id", "demo12345", so["entity_id"]),
           "manager": _h("manager@kainnusantara.id", "demo12345", so["entity_id"])}
    notes = [n["id"] for n in DB.credit_notes.find({"order_id": SID}, {"id": 1})]
    amds = [a["id"] for a in DB.doc_amendments.find({"doc_id": SID}, {"id": 1})]
    DB.notifications.delete_many({"$or": [{"ref": {"$in": amds}}, {"action_id": {"$in": amds}}]})
    DB.journal_entries.delete_many({"$or": [{"id": JE}, {"source_id": {"$in": notes}}]})
    DB.store_credit_ledger.delete_many({"ref_id": {"$in": notes}})
    DB.credit_notes.delete_many({"order_id": SID})
    DB.doc_amendments.delete_many({"doc_id": SID})
    DB.doc_refs.delete_many({"$or": [{"from_id": SID}, {"to_id": SID}, {"from_id": {"$in": notes}}]})
    DB.sales_orders.delete_one({"id": SID})


def _propose(c, field, to):
    it = c["so"]["items"][0]
    body = {"doc_type": "sales_order", "doc_id": SID, "reason_code": "price_correction", "note": "TEST_L022T03",
            "changes": [{"product_id": it["product_id"], "field": field, "to": to}]}
    r = requests.post(f"{BASE}/amendments", headers=c["admin"], json=body)
    assert r.status_code == 200, r.text[:400]
    amd = r.json()
    if amd["status"] == "pending_approval":
        r = requests.post(f"{BASE}/amendments/{amd['id']}/decision", headers=c["manager"], json={"action": "approve"})
        assert r.status_code == 200, r.text[:400]
        amd = r.json()
    return amd


def test_credit_note_posts_journal_and_reduces_ar_without_editing_order(ctx):
    it = ctx["so"]["items"][0]
    amd = _propose(ctx, "price", round(float(it["price"]) * 0.9, 2))
    assert amd["method"] == "credit_note", amd["method"]
    so = DB.sales_orders.find_one({"id": SID}, {"_id": 0})
    assert so["grand_total"] == ctx["so"]["grand_total"] and so["items"][0]["price"] == it["price"]
    cn = DB.credit_notes.find_one({"amendment_id": amd["id"]}, {"_id": 0})
    assert cn["status"] == "posted" and cn["ar_applied"] == cn["gross_amount"] and cn["journal_entry_id"]
    je = DB.journal_entries.find_one({"id": cn["journal_entry_id"]}, {"_id": 0})
    dr = round(sum(l["debit"] for l in je["lines"]), 2)
    assert dr == round(sum(l["credit"] for l in je["lines"]), 2) == cn["gross_amount"]
    pays = [p for p in so["payments"] if p.get("receipt_id") == cn["id"]]
    assert len(pays) == 1 and pays[0]["amount"] == cn["gross_amount"]
    # retry keputusan tidak menerbitkan nota/jurnal kedua
    r = requests.post(f"{BASE}/amendments/{amd['id']}/decision", headers=ctx["manager"], json={"action": "approve"})
    assert r.status_code == 400
    assert DB.credit_notes.count_documents({"amendment_id": amd["id"]}) == 1
    assert DB.journal_entries.count_documents({"source_type": "amendment_credit_note", "source_id": cn["id"]}) == 1


def test_debit_note_recorded_waits_for_billing_rule(ctx):
    it = ctx["so"]["items"][0]
    amd = _propose(ctx, "price", round(float(it["price"]) * 1.2, 2))
    assert amd["method"] == "debit_note"
    dn = DB.credit_notes.find_one({"amendment_id": amd["id"]}, {"_id": 0})
    assert dn["kind"] == "debit_note" and dn["billing_status"] == "awaiting_billing_rule"
    assert DB.journal_entries.count_documents({"source_id": dn["id"]}) == 0
