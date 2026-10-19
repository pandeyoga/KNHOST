"""L02 LN-023 — AR ledger vs exposure (T01), PO short-close settlement (T02), retry idempotency (T03)."""
import os
import subprocess
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ENT = "ent_ksc"
CUST = "cust_TEST_ln023"
SO = "so_TEST_ln023_a"
PO1 = "po_TEST_ln023_close"
PO2 = "po_TEST_ln023_var"
VB = "vbill_TEST_ln023"
GT = 10_000_000.0


def _h(email="admin@kainnusantara.id", pwd="demo12345"):
    t = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pwd}).json()["token"]
    return {"Authorization": f"Bearer {t}", "X-Entity-Id": ENT}


def _cleanup():
    rids = [r["id"] for r in DB.ar_receipts.find({"customer_id": CUST}, {"id": 1})]
    cids = [c["id"] for c in DB.cash_transactions.find({"ref_id": {"$in": rids}}, {"id": 1})]
    DB.journal_entries.delete_many({"$or": [{"source_id": {"$in": rids + cids + [SO, PO1, PO2, VB]}},
                                            {"ref.order_id": SO}, {"description": {"$regex": "TEST_LN023"}}]})
    DB.cash_transactions.delete_many({"id": {"$in": cids}})
    DB.ar_receipts.delete_many({"customer_id": CUST})
    DB.idempotency_keys.delete_many({"key": {"$regex": "^TEST_ln023"}})
    DB.notifications.delete_many({"ref": {"$in": [PO1, PO2, SO] + rids}})
    DB.notifications.delete_many({"link": {"$regex": "TEST_ln023"}})
    DB.po_variance_tasks.delete_many({"po_id": {"$in": [PO1, PO2]}})
    DB.vendor_bills.delete_many({"id": VB})
    DB.purchase_orders.delete_many({"id": {"$in": [PO1, PO2]}})
    DB.sales_orders.delete_many({"id": SO})
    DB.customers.delete_many({"id": CUST})
    DB.doc_refs.delete_many({"$or": [{"from_id": {"$in": rids + [SO]}}, {"to_id": {"$in": rids + [SO]}}]})


@pytest.fixture(scope="module", autouse=True)
def fixtures():
    _cleanup()
    cust = DB.customers.find_one({"id": "cust_butik_bali"}, {"_id": 0}) or DB.customers.find_one({"id": {"$not": {"$regex": "TEST"}}}, {"_id": 0})
    cust.update({"id": CUST, "code": "TEST_LN023", "name": "TEST_LN023 Customer", "entity_id": ENT, "credit_limit": 0, "status": "active",
                 "deposit_balance": 0})
    DB.customers.insert_one(dict(cust))
    so = DB.sales_orders.find_one({"id": "so_97e1a0a7a24c"}, {"_id": 0}) or DB.sales_orders.find_one({"entity_id": ENT, "items.0": {"$exists": True}, "id": {"$not": {"$regex": "TEST"}}}, {"_id": 0})
    so.update({"id": SO, "number": "KSC/TEST_SO-LN023-A", "customer_id": CUST, "customer_name": cust["name"],
               "status": "confirmed", "payments": [], "paid_total": 0, "payment_status": "pending",
               "grand_total": GT, "allocations": [], "refs": []})
    DB.sales_orders.insert_one(dict(so))
    base = DB.purchase_orders.find_one({"entity_id": ENT, "items.0": {"$exists": True}}, {"_id": 0})
    for pid, num in ((PO1, "KSC/TEST_PO-LN023-1"), (PO2, "KSC/TEST_PO-LN023-2")):
        po = dict(base)
        it = dict(base["items"][0])
        it.update({"quantity": 1000.0, "received_qty": 960.0, "price": 10000.0, "discount_percent": 0.0,
                   "subtotal": GT, "line_total": GT})
        po.update({"id": pid, "po_number": num, "status": "partial", "items": [it], "amount_paid": 0,
                   "payments": [], "grand_total": GT, "total_amount": GT, "returned_amount": 0, "refs": [],
                   "timeline": [], "notes": "TEST_LN023"})
        po.pop("close_settlement", None)
        DB.purchase_orders.insert_one(po)
    bill = DB.vendor_bills.find_one({"status": "posted"}, {"_id": 0})
    bill.update({"id": VB, "bill_number": "TEST_VB-LN023", "po_id": PO1, "po_number": "KSC/TEST_PO-LN023-1",
                 "entity_id": ENT, "grand_total": GT, "total_amount": GT, "amount_paid": 9_800_000.0,
                 "status": "posted"})
    DB.vendor_bills.insert_one(bill)
    yield
    if not os.environ.get("LN023_KEEP"):   # set LN023_KEEP=1 to inspect data in UI, then rerun cleanup
        _cleanup()


@pytest.fixture(scope="module")
def H():
    return _h()


def _detail_item(H):
    r = requests.get(f"{BASE}/ar/aging/{CUST}", headers=H)
    assert r.status_code == 200, r.text
    d = r.json()
    it = next(i for i in d["items"] if i["order_id"] == SO)
    return d, it


def _row(H):
    r = requests.get(f"{BASE}/ar/aging", headers=H)
    assert r.status_code == 200, r.text
    d = r.json()
    return d, next(c for c in d["customers"] if c["customer_id"] == CUST)


def _gl_1200(order_id, rid=None):
    bal = 0.0
    q = {"status": {"$ne": "void"}, "$or": [{"ref.order_id": order_id}, {"source_id": order_id}]}
    for je in DB.journal_entries.find(q, {"_id": 0, "lines": 1}):
        for ln in je["lines"]:
            if ln["account_code"] == "1-1200":
                bal += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return round(bal, 2)


# ── T01 — AR ledger vs exposure across stages ──
class TestT01ARSplit:
    def test_aging_totals_and_definitions(self, H):
        d, _ = _row(H)
        t = d["totals"]
        assert abs(t["ar_ledger"] + t["exposure"] - t["total"]) < 0.05
        assert {"outstanding", "ar_ledger", "exposure"} <= set(d["definitions"])
        for c in d["customers"]:
            assert abs(c["ar_ledger"] + c["exposure"] - c["outstanding"]) < 0.05, c["customer_id"]

    def test_stage1_confirmed_unshipped(self, H):
        d, it = _detail_item(H)
        assert it["ar_ledger"] == 0 and it["exposure"] == GT and it["outstanding"] == GT
        assert it["status"] == "confirmed"
        _, row = _row(H)
        assert row["ar_ledger"] == 0 and row["exposure"] == GT
        assert _gl_1200(SO) == 0

    def test_stage2_partial_shipment(self, H):
        DB.journal_entries.insert_one({
            "id": "je_TEST_ln023_shp", "number": "KSC/TEST_JE-LN023", "source_type": "shipment_revenue",
            "source": "shipment_revenue", "source_id": "shp_TEST_ln023", "status": "posted", "entity_id": ENT,
            "description": "TEST_LN023 pengakuan", "ref": {"order_id": SO, "order_number": "KSC/TEST_SO-LN023-A"},
            "date": "2026-01-10T00:00:00+00:00", "created_at": "2026-01-10T00:00:00+00:00",
            "lines": [{"account_code": "1-1200", "debit": 4_000_000.0, "credit": 0.0},
                      {"account_code": "4-1000", "debit": 0.0, "credit": 4_000_000.0}],
            "total_debit": 4_000_000.0, "total_credit": 4_000_000.0})
        _, it = _detail_item(H)
        assert it["ar_ledger"] == 4_000_000.0 and it["exposure"] == 6_000_000.0
        _, row = _row(H)
        assert row["ar_ledger"] == 4_000_000.0 and row["exposure"] == 6_000_000.0
        assert _gl_1200(SO) == 4_000_000.0

    # ── T03 — same Idempotency-Key twice → one receipt / one payment / one journal ──
    def test_stage3_partial_payment_idempotent(self, H):
        key = f"TEST_ln023_{uuid.uuid4().hex[:8]}"
        body = {"customer_id": CUST, "amount": 1_500_000.0, "method": "transfer", "entity_id": ENT,
                "notes": "TEST_LN023", "allocations": [{"order_id": SO, "amount": 1_500_000.0}]}
        hh = {**H, "Idempotency-Key": key}
        r1 = requests.post(f"{BASE}/ar-receipts", json=body, headers=hh)
        assert r1.status_code == 200, r1.text
        r2 = requests.post(f"{BASE}/ar-receipts", json=body, headers=hh)
        assert r2.status_code == 200, r2.text
        assert r2.headers.get("X-Idempotent-Replay") == "true"
        assert r1.json()["id"] == r2.json()["id"]
        assert DB.ar_receipts.count_documents({"customer_id": CUST}) == 1
        so = DB.sales_orders.find_one({"id": SO}, {"_id": 0})
        assert round(sum(p["amount"] for p in so["payments"]), 2) == 1_500_000.0
        assert len(so["payments"]) == 1
        rid = r1.json()["id"]
        cids = [c["id"] for c in DB.cash_transactions.find({"ref_id": rid}, {"id": 1})]
        assert len(cids) == 1
        jes = list(DB.journal_entries.find({"source_id": {"$in": cids + [rid]}, "status": {"$ne": "void"}},
                                           {"_id": 0, "lines": 1, "source_type": 1}))
        assert len(jes) == 1, jes
        cr1200 = sum(float(l.get("credit") or 0) for l in jes[0]["lines"] if l["account_code"] == "1-1200")
        assert cr1200 == 1_500_000.0
        _, it = _detail_item(H)
        assert it["paid_total"] == 1_500_000.0 and it["outstanding"] == 8_500_000.0
        assert it["ar_ledger"] == 2_500_000.0 and it["exposure"] == 6_000_000.0
        assert it["ar_ledger"] == round(_gl_1200(SO) - cr1200, 2)
        _, row = _row(H)
        assert row["ar_ledger"] == 2_500_000.0 and row["exposure"] == 6_000_000.0
        assert row["outstanding"] == 8_500_000.0

    def test_idempotency_key_different_payload_409(self, H):
        key = f"TEST_ln023_{uuid.uuid4().hex[:8]}"
        hh = {**H, "Idempotency-Key": key}
        b = {"customer_id": CUST, "amount": 100.0, "entity_id": ENT,
             "allocations": [{"order_id": SO, "amount": 100.0}]}
        assert requests.post(f"{BASE}/ar-receipts", json=b, headers=hh).status_code == 200
        r = requests.post(f"{BASE}/ar-receipts", json={**b, "amount": 200.0}, headers=hh)
        assert r.status_code == 409
        assert DB.ar_receipts.count_documents({"customer_id": CUST}) == 2


# ── T02 — PO short-close settlement ──
class TestT02POClose:
    def test_close_settlement_over_billed_over_paid(self, H):
        before_je = DB.journal_entries.count_documents({"$or": [{"source_id": PO1}, {"ref.po_id": PO1}]})
        r = requests.post(f"{BASE}/purchase-orders/{PO1}/close", json={"reason": "TEST_LN023 supplier stop"},
                          headers=H)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "closed_short"
        s = DB.purchase_orders.find_one({"id": PO1})["close_settlement"]
        assert s["ordered_value"] == GT and s["received_value"] == 9_600_000.0
        assert s["cancelled_value"] == 400_000.0 and s["billed_total"] == GT
        assert s["paid_total"] == 9_800_000.0 and s["unbilled_received"] == 0
        assert s["over_billed"] == 400_000.0 and s["over_paid"] == 200_000.0
        assert s["balanced"] is True
        codes = {f["code"]: f for f in s["follow_ups"]}
        assert {"remaining_cancelled", "supplier_credit_note", "overpayment"} <= set(codes)
        assert codes["supplier_credit_note"]["owner"] == "finance" and codes["overpayment"]["owner"] == "finance"
        assert DB.notifications.count_documents({"type": "po_close_settlement", "ref": PO1}) == 1
        n = DB.notifications.find_one({"type": "po_close_settlement", "ref": PO1})
        assert n["recipient_role"] == "finance"
        assert DB.journal_entries.count_documents({"$or": [{"source_id": PO1}, {"ref.po_id": PO1}]}) == before_je

    def test_retry_close_400_no_dup(self, H):
        at1 = DB.purchase_orders.find_one({"id": PO1})["close_settlement"]["computed_at"]
        r = requests.post(f"{BASE}/purchase-orders/{PO1}/close", json={"reason": "TEST_LN023 retry"}, headers=H)
        assert r.status_code == 400
        assert DB.purchase_orders.find_one({"id": PO1})["close_settlement"]["computed_at"] == at1
        assert DB.notifications.count_documents({"type": "po_close_settlement", "ref": PO1}) == 1

    def test_get_close_settlement(self, H):
        r = requests.get(f"{BASE}/purchase-orders/{PO1}/close-settlement", headers=H)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["at_close"]["over_billed"] == 400_000.0
        assert d["current"]["over_paid"] == 200_000.0 and d["current"]["balanced"] is True
        r404 = requests.get(f"{BASE}/purchase-orders/po_TEST_nope/close-settlement", headers=H)
        assert r404.status_code == 404

    def test_variance_task_short_close(self, H):
        code = ("import asyncio,sys;sys.path.insert(0,'/app/backend')\n"
                "from services import po_variance_task_service as p\n"
                f"print([t['id'] for t in asyncio.run(p.ensure_for_po('{PO2}','TEST_seed','TEST_seed'))])")
        out = subprocess.run(["python", "-c", code], cwd="/app/backend", capture_output=True, text=True)
        tasks = list(DB.po_variance_tasks.find({"po_id": PO2, "status": "open"}, {"_id": 0}))
        assert tasks, out.stderr[-500:]
        tid = tasks[0]["id"]
        body = {"decision": "short_close", "reason": "TEST_LN023 short close"}
        r = requests.post(f"{BASE}/po-variance-tasks/{tid}/decide", json=body, headers=H)
        assert r.status_code == 200, r.text
        po = DB.purchase_orders.find_one({"id": PO2})
        assert po["status"] == "closed_short"
        s = po["close_settlement"]
        assert s["unbilled_received"] == 9_600_000.0 and s["cancelled_value"] == 400_000.0
        assert s["balanced"] is True
        assert {"remaining_cancelled", "bill_received"} <= {f["code"] for f in s["follow_ups"]}
        assert DB.notifications.count_documents({"type": "po_close_settlement", "ref": PO2}) == 1
        r2 = requests.post(f"{BASE}/po-variance-tasks/{tid}/decide", json=body, headers=H)
        assert r2.status_code == 200
        assert DB.notifications.count_documents({"type": "po_close_settlement", "ref": PO2}) == 1
        assert DB.purchase_orders.find_one({"id": PO2})["close_settlement"]["computed_at"] == s["computed_at"]
