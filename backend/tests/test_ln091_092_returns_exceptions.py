"""LN-091 potong tagihan dulu, LN-092 simulasi cutloss/diskon terkunci, LN-083 pengecualian + kondisi, LN-024 pengingat."""
import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
T = uuid.uuid4().hex[:6]
_OWN_LOOP = asyncio.new_event_loop()


def _loop():
    """Klien Motor global terikat ke loop PERTAMA yang memakainya; modul tes lain dalam satu sesi pytest bisa sudah
    mengikatnya — pakai loop itu (loop baru → "attached to a different loop")."""
    from db import db as _db
    lp = _db.client._io_loop
    if lp is None or lp.is_closed():
        lp = _db.client._io_loop = _OWN_LOOP
    return lp


def _CST():
    return DB.business_entities.find_one({"doc_prefix": "CST"})["id"]


def _login(email, pw="demo12345"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}, r.json()["user"]


ADMIN, ADMIN_U = _login("admin@kainnusantara.id", "demo12345")
MGR, _ = _login("manager@kainnusantara.id")


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    rets = [r["id"] for r in DB.sales_returns.find({"number": {"$regex": f"^TEST_RET-{T}"}}, {"id": 1})]
    DB.sales_returns.delete_many({"id": {"$in": rets}})
    DB.credit_notes.delete_many({"return_id": {"$in": rets}})
    DB.journal_entries.delete_many({"source_id": {"$in": rets}})
    DB.sales_orders.delete_many({"id": {"$regex": f"^so_TEST_{T}"}})
    DB.store_credit_ledger.delete_many({"ref_id": {"$in": rets}})
    DB.notifications.delete_many({"type": "interco_payment_due", "ref": {"$regex": f"TEST_{T}"}})


def _seed(open_total=20.0, credit=30.0, status="inspected", elig=None):
    so, rid = f"so_TEST_{T}_{uuid.uuid4().hex[:4]}", f"sr_TEST_{T}_{uuid.uuid4().hex[:4]}"
    DB.sales_orders.insert_one({"id": so, "number": f"TEST_SO-{so}", "entity_id": "ent_ksc", "customer_id": "cust_x",
                                "items": [{"product_id": "pX", "quantity": 1, "price": credit, "line_total": credit}],
                                "grand_total": credit + 100 - 100 + (open_total - open_total), "payments":
                                [{"amount": credit - open_total}], "status": "shipped", "ppn_rate": 0, "ppn_amount": 0})
    DB.sales_returns.insert_one({"id": rid, "number": f"TEST_RET-{T}-{rid[-4:]}", "order_id": so, "entity_id": "ent_ksc",
                                 "customer_id": "cust_x", "customer_name": "TEST cust", "status": status,
                                 "items": [{"product_id": "pX", "quantity_returned": 1}], "attachments": [
                                     {"id": f"att_{rid}", "filename": "bukti.jpg", "content_type": "image/jpeg", "is_deleted": False},
                                     {"id": f"pdf_{rid}", "filename": "x.pdf", "content_type": "application/pdf", "is_deleted": False}],
                                 "policy_eligibility": elig or {}})
    return so, rid


def test_ln091_t01_bill_first_then_saldo_or_refund():
    from services import return_service as rs

    async def run():
        out = {}
        for stype in ("store_credit", "cash"):
            so, rid = _seed()
            ret = DB.sales_returns.find_one({"id": rid}, {"_id": 0})
            cn = await rs._create_credit_note_and_post_gl(ret, items=ret["items"], post_stock=False, settlement_type=stype)
            je = DB.journal_entries.find_one({"source_type": "sales_return", "source_id": rid}, {"_id": 0, "lines": 1})
            out[stype] = (cn, je)
        return out
    res = _loop().run_until_complete(run())
    for stype, (cn, je) in res.items():
        assert cn["gross_amount"] == 30 and cn["ar_applied"] == 20 and cn["excess_amount"] == 10, (stype, cn)
        lines = je["lines"]
        assert round(sum(l["debit"] for l in lines), 2) == round(sum(l["credit"] for l in lines), 2)
        credits = {l["account_code"]: l["credit"] for l in lines if l["credit"]}
        assert credits.get("1-1200") == 20 and sum(credits.values()) == 30


def test_ln091_split_helper():
    from services.return_settlement_policy import split_credit
    assert split_credit(30, 20, True) == {"ar_part": 20, "excess": 10}
    assert split_credit(30, 50, True) == {"ar_part": 30, "excess": 0}
    assert split_credit(30, 20, False) == {"ar_part": 0, "excess": 30}


def test_ln092_cutloss_simulation_final_rule():
    r = requests.post(f"{BASE}/sales-returns/cutloss/simulate", headers=ADMIN,
                      json={"roll_length": 120, "defect_from": 46, "defect_to": 60, "unit_price": 1000}).json()
    assert r["customer_pieces"] == [45, 60] and r["compensation_qty"] == 15 and r["compensation_value"] == 15000
    assert r["reconciles"] and r["final"]
    d = requests.post(f"{BASE}/sales-returns/discount/simulate", headers=ADMIN, json={"qty_affected": 15, "amount": 25000}).json()
    assert d["discount_value"] == 25000 and d["stock_movement"] == 0


def test_ln083_klr08_condition_is_warning_finance_note_required():
    _, rid = _seed(elig={"decision": "eligible", "pending_decisions": []})
    DB.sales_returns.update_one({"id": rid}, {"$set": {"condition_flags": {"hangtag_missing": True, "cut_by_customer": False}}})
    bad = requests.post(f"{BASE}/sales-returns/{rid}/exceptions", headers=ADMIN,
                        json={"kind": "condition", "reason": "Hangtag hilang dari pabrik", "attachment_ids": [f"att_{rid}"]})
    assert bad.status_code == 400 and "KLR-08" in bad.text
    s = requests.post(f"{BASE}/sales-returns/{rid}/settle", headers=ADMIN, json={"outcome": "refund"})
    assert s.status_code == 400 and "catatan keputusan Finance" in s.text


FIN, _ = _login("finance@kainnusantara.id")


def test_ln092_cutloss_recorded_by_md_valued_by_finance_and_settled_as_nego():
    so, rid = _seed(elig={"decision": "eligible", "pending_decisions": []})
    DB.sales_orders.update_one({"id": so}, {"$set": {"items": [{"product_id": "pX", "quantity": 120, "line_total": 108000}]}})
    DB.sales_returns.update_one({"id": rid}, {"$set": {"items": [{"product_id": "pX", "product_name": "TEST", "unit": "yard",
                                                                  "quantity_returned": 120}]}})
    s = requests.post(f"{BASE}/sales-returns/{rid}/settle", headers=ADMIN, json={"outcome": "nego"})
    assert s.status_code == 409 and "Finance" in s.text
    no = requests.post(f"{BASE}/sales-returns/{rid}/cutloss", headers=FIN, json={"product_id": "pX", "defect_yard": 15})
    assert no.status_code == 403
    c = requests.post(f"{BASE}/sales-returns/{rid}/cutloss", headers=ADMIN, json={"product_id": "pX", "defect_yard": 15})
    assert c.status_code == 200 and c.json()["qty_base"] == 15, c.text
    pv = requests.get(f"{BASE}/sales-returns/{rid}/compensation", headers=ADMIN).json()
    assert pv["cutloss"][0]["unit_price"] == 900 and pv["cutloss"][0]["amount"] == 13500
    d = requests.post(f"{BASE}/sales-returns/{rid}/compensation", headers=FIN,
                      json={"lines": [{"kind": "cutloss", "product_id": "pX"}], "note": "cacat 15 yd sesuai QC"})
    assert d.status_code == 200 and d.json()["total"] == 13500, d.text
    st = requests.post(f"{BASE}/sales-returns/{rid}/settle", headers=ADMIN, json={"outcome": "nego"})
    assert st.status_code == 200, st.text
    cn = DB.credit_notes.find_one({"return_id": rid})
    assert cn["net_amount"] == 13500 and cn["lines"][0]["quantity"] == 15 and cn["cogs_amount"] == 0


def test_ln092_discount_from_photo_without_goods():
    _, rid = _seed(status="approved", elig={"decision": "eligible", "pending_decisions": []})
    DB.sales_returns.update_one({"id": rid}, {"$set": {"items": [{"product_id": "pX", "product_name": "TEST", "unit": "yard",
                                                                  "quantity_returned": 20}]}})
    bad = requests.post(f"{BASE}/sales-returns/{rid}/compensation", headers=FIN,
                        json={"lines": [{"kind": "discount", "product_id": "pX", "qty": 25, "amount": 1000}], "note": "foto noda"})
    assert bad.status_code == 400
    d = requests.post(f"{BASE}/sales-returns/{rid}/compensation", headers=FIN,
                      json={"lines": [{"kind": "discount", "product_id": "pX", "qty": 5, "amount": 7500,
                                       "evidence_ids": [f"att_{rid}"]}], "note": "foto noda 5 yd"})
    assert d.status_code == 200, d.text
    st = requests.post(f"{BASE}/sales-returns/{rid}/settle", headers=ADMIN, json={"outcome": "nego"})
    assert st.status_code == 200, st.text
    doc = DB.sales_returns.find_one({"id": rid})
    assert doc["status"] == "nego_settled" and DB.credit_notes.find_one({"return_id": rid})["net_amount"] == 7500


def test_ln024_payment_reminder_job():
    from services import interco_service as ics
    pay = (date.today() + timedelta(days=2)).isoformat()
    rows = [{"interco_id": f"TEST_{T}", "number": f"TEST_IC-{T}", "payer_entity_name": "CST", "payee_entity_name": "KSC",
             "remaining": 1000.0, "pay_date": pay}]

    async def fake_schedule(entities, payer="", payee=""):
        return {"cutoff_status": "configured", "rows": rows if payer == _CST() else []}

    async def fake_settings(entity_id=""):
        return {"reminder_days": 3}

    async def run():
        orig = (ics.payment_schedule, ics.payment_settings)
        ics.payment_schedule, ics.payment_settings = fake_schedule, fake_settings
        try:
            a = await ics.job_interco_payment_reminder()
            b = await ics.job_interco_payment_reminder()
        finally:
            ics.payment_schedule, ics.payment_settings = orig
        return a, b
    a, b = _loop().run_until_complete(run())
    assert a["created"] == 1 and b["created"] == 0   # tidak dobel
    n = DB.notifications.find_one({"type": "interco_payment_due", "ref": f"TEST_{T}:{pay}"})
    assert n and n["recipient_role"] == "finance" and n["entity_id"] == _CST()


def test_ln091_klr10_nego_payout_choice_saldo_with_source_paid():
    so, rid = _seed(open_total=0.0, credit=30.0, elig={"decision": "eligible", "pending_decisions": []})
    DB.sales_returns.update_one({"id": rid}, {"$set": {"items": [{"product_id": "pX", "product_name": "TEST", "unit": "yard",
                                                                  "quantity_returned": 1}], "customer_id": ADMIN_U.get("_x", "cust_x")}})
    if not DB.customers.find_one({"id": "cust_x"}):
        DB.customers.insert_one({"id": "cust_x", "name": "TEST cust", "entity_id": "ent_ksc", "TEST": True})
    d = requests.post(f"{BASE}/sales-returns/{rid}/compensation", headers=FIN,
                      json={"lines": [{"kind": "discount", "product_id": "pX", "qty": 1, "amount": 10, "evidence_ids": [f"att_{rid}"]}],
                            "note": "diskon noda kecil"})
    assert d.status_code == 200, d.text
    st = requests.post(f"{BASE}/sales-returns/{rid}/settle", headers=ADMIN, json={"outcome": "nego", "payout": "store_credit"})
    assert st.status_code == 200, st.text
    cn = DB.credit_notes.find_one({"return_id": rid})
    assert cn["settlement"] == "store_credit" and cn.get("ar_applied", 0) == 0 and cn["excess_amount"] == 10
    assert DB.store_credit_ledger.find_one({"ref_id": rid, "type": "issue"})["amount"] == 10
    DB.customers.delete_many({"id": "cust_x", "TEST": True})


def test_ln091_klr11_logistics_bearer_per_case():
    _, rid = _seed(elig={"decision": "eligible", "pending_decisions": []})
    bad = requests.put(f"{BASE}/sales-returns/{rid}/logistics", headers=ADMIN, json={"costs": [{"type": "x", "bearer": "company"}]})
    assert bad.status_code == 400
    ok = requests.put(f"{BASE}/sales-returns/{rid}/logistics", headers=ADMIN, json={"costs": [
        {"type": "customer_return", "bearer": "customer", "amount": 50000},
        {"type": "qc_trip", "bearer": "company", "amount": 120000},
        {"type": "replacement_shipping", "bearer": "customer", "amount": 30000}]})
    assert ok.status_code == 200 and ok.json()["customer_total"] == 80000 and ok.json()["company_total"] == 120000
