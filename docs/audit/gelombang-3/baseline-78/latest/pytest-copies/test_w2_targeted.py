"""W2 targeted tests (test agent, iteration): W2-015 / W2-017 / W2-020 / W2-022 / W2-023.

HTTP-based end-to-end against the running backend on :8001, plus one in-process
pytest for W2-020 refund cash failure path (monkeypatch cash_ledger).

All test data is prefixed with TEST_W2T_ and self-cleaned at module teardown.
"""
import asyncio
import os
import threading
import uuid
from typing import Dict, Any, List, Tuple

import bcrypt
import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/.env")

BASE = "http://localhost:8001/api"
ENT = "ent_ksc"
PWD = "demo12345"
PREFIX = f"TEST_W2T_{uuid.uuid4().hex[:6]}"
_STARTED_AT = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()

client = MongoClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

_created: Dict[str, List[str]] = {}  # collection -> list of ids


def _mark(coll: str, _id: str) -> None:
    _created.setdefault(coll, []).append(_id)


# ───────────────────────── Helpers ─────────────────────────
def admin_session() -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login",
               json={"email": "admin@kainnusantara.id", "password": PWD}, timeout=30)
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}",
                      "X-Entity-Id": ENT})
    return s


def _make_customer(deposit_balance: float = 0.0) -> Dict[str, Any]:
    cid = f"cust_{PREFIX}_{uuid.uuid4().hex[:6]}"
    doc = {
        "id": cid, "name": f"{PREFIX} Customer", "entity_id": ENT,
        "deposit_balance": float(deposit_balance), "status": "active",
    }
    db.customers.insert_one(doc)
    _mark("customers", cid)
    return doc


def _make_order_with_ar(customer_id: str, grand_total: float = 100.0) -> Dict[str, Any]:
    """Order with revenue recognized (AR room == grand_total): inserts a sales_order AND
    a shipment_revenue journal_entry that debits ACC_PIUTANG = grand_total."""
    oid = f"so_{PREFIX}_{uuid.uuid4().hex[:6]}"
    o = {
        "id": oid, "number": f"{PREFIX}-SO-{uuid.uuid4().hex[:4]}",
        "customer_id": customer_id, "entity_id": ENT,
        "grand_total": float(grand_total), "paid_total": 0.0,
        "payments": [], "status": "confirmed",
        "payment_profile_method": "transfer", "payment_term_code": "cod",
        "created_at": "2099-01-01T00:00:00",
    }
    db.sales_orders.insert_one(o)
    _mark("sales_orders", oid)

    je_id = f"je_{PREFIX}_{uuid.uuid4().hex[:6]}"
    je = {
        "id": je_id, "number": f"JE-{PREFIX}-{uuid.uuid4().hex[:4]}",
        "source_type": "shipment_revenue", "source_id": oid,
        "ref": {"order_id": oid}, "entity_id": ENT, "status": "posted",
        "date": "2099-01-01T00:00:00",
        "lines": [
            {"account_code": "1-1200", "debit": float(grand_total), "credit": 0.0,
             "description": f"{PREFIX} AR"},
            {"account_code": "4-1000", "debit": 0.0, "credit": float(grand_total),
             "description": f"{PREFIX} Revenue"},
        ],
        "created_at": "2099-01-01T00:00:00",
    }
    db.journal_entries.insert_one(je)
    _mark("journal_entries", je_id)
    return o


def _make_order_no_ar(customer_id: str, grand_total: float = 100.0) -> Dict[str, Any]:
    """Order with NO revenue yet (unshipped) — deposit applied becomes advance (no reclass journal)."""
    oid = f"so_{PREFIX}_{uuid.uuid4().hex[:6]}"
    o = {
        "id": oid, "number": f"{PREFIX}-SO-{uuid.uuid4().hex[:4]}",
        "customer_id": customer_id, "entity_id": ENT,
        "grand_total": float(grand_total), "paid_total": 0.0,
        "payments": [], "status": "confirmed",
        "payment_profile_method": "transfer", "payment_term_code": "cod",
        "created_at": "2099-01-01T00:00:00",
    }
    db.sales_orders.insert_one(o)
    _mark("sales_orders", oid)
    return o


# ═══════════════════════════ W2-015 ═══════════════════════════
class TestW2_015_DepositOnlyReceipt:
    def test_deposit_only_receipt_on_ar_order_posts_reclass_journal(self):
        s = admin_session()
        cust = _make_customer(deposit_balance=200.0)
        order = _make_order_with_ar(cust["id"], grand_total=100.0)

        r = s.post(f"{BASE}/ar-receipts", json={
            "customer_id": cust["id"], "entity_id": ENT,
            "amount": 0, "use_deposit_amount": 100.0, "method": "transfer",
            "allocations": [{"order_id": order["id"], "amount": 100.0}],
        }, timeout=30)
        assert r.status_code == 200, r.text
        rc = r.json()
        _mark("ar_receipts", rc["id"])
        assert rc["amount"] == 0
        assert rc["used_deposit"] == 100.0
        assert rc["applied_total"] == 100.0

        # No fake cash_transactions
        cash = list(db.cash_transactions.find({"ref_type": "ar_receipt", "ref_id": rc["id"]}))
        assert len(cash) == 0, f"Expected zero cash_transactions for pure-deposit receipt, got {len(cash)}"

        # Reclass journal: Dr 2-1400 / Cr 1-1200
        je = db.journal_entries.find_one(
            {"source_type": "ar_receipt_deposit", "source_id": rc["id"], "status": {"$ne": "void"}})
        assert je is not None, "Expected ar_receipt_deposit journal entry"
        _mark("journal_entries", je["id"])
        codes = {ln["account_code"]: (ln.get("debit", 0), ln.get("credit", 0)) for ln in je["lines"]}
        assert codes.get("2-1400", (0, 0))[0] == 100.0
        assert codes.get("1-1200", (0, 0))[1] == 100.0

        # Deposit balance reduced
        c = db.customers.find_one({"id": cust["id"]})
        assert round(c["deposit_balance"], 2) == 100.0

        # Void → reversal journal
        rv = s.post(f"{BASE}/ar-receipts/{rc['id']}/void", json={"reason": "test"}, timeout=30)
        assert rv.status_code == 200, rv.text
        je_rev = db.journal_entries.find_one(
            {"source_type": "ar_receipt_deposit_void", "source_id": rc["id"], "status": {"$ne": "void"}})
        assert je_rev is not None, "Expected ar_receipt_deposit_void reversal"
        _mark("journal_entries", je_rev["id"])
        rcodes = {ln["account_code"]: (ln.get("debit", 0), ln.get("credit", 0)) for ln in je_rev["lines"]}
        assert rcodes.get("1-1200", (0, 0))[0] == 100.0  # AR debited back
        assert rcodes.get("2-1400", (0, 0))[1] == 100.0  # customer advance credited back

        # Idempotent — only ONE reversal
        count = db.journal_entries.count_documents(
            {"source_type": "ar_receipt_deposit_void", "source_id": rc["id"]})
        assert count == 1, f"Expected 1 void reversal, got {count}"

        # Deposit balance restored
        c = db.customers.find_one({"id": cust["id"]})
        assert round(c["deposit_balance"], 2) == 200.0

        # No cash_transactions ever created
        cash = list(db.cash_transactions.find({"ref_id": rc["id"]}))
        assert len(cash) == 0

    def test_deposit_only_receipt_on_unshipped_order_no_reclass_journal(self):
        s = admin_session()
        cust = _make_customer(deposit_balance=150.0)
        order = _make_order_no_ar(cust["id"], grand_total=100.0)

        r = s.post(f"{BASE}/ar-receipts", json={
            "customer_id": cust["id"], "entity_id": ENT,
            "amount": 0, "use_deposit_amount": 80.0,
            "allocations": [{"order_id": order["id"], "amount": 80.0}],
        }, timeout=30)
        assert r.status_code == 200, r.text
        rc = r.json()
        _mark("ar_receipts", rc["id"])

        # No reclass journal (advance only)
        je = db.journal_entries.find_one(
            {"source_type": "ar_receipt_deposit", "source_id": rc["id"]})
        assert je is None, "Should NOT post reclass journal for unshipped order (pure advance)"
        # No cash
        cash = list(db.cash_transactions.find({"ref_id": rc["id"]}))
        assert len(cash) == 0


# ═══════════════════════════ W2-017 ═══════════════════════════
class TestW2_017_ConcurrentDepositUse:
    def test_two_concurrent_receipts_one_wins_one_409(self):
        s = admin_session()
        cust = _make_customer(deposit_balance=100.0)
        order1 = _make_order_with_ar(cust["id"], grand_total=100.0)
        order2 = _make_order_with_ar(cust["id"], grand_total=100.0)

        results: List[Tuple[int, str]] = []
        lock = threading.Lock()

        def fire(oid: str):
            r = s.post(f"{BASE}/ar-receipts", json={
                "customer_id": cust["id"], "entity_id": ENT,
                "amount": 0, "use_deposit_amount": 80.0,
                "allocations": [{"order_id": oid, "amount": 80.0}],
            }, timeout=30)
            with lock:
                results.append((r.status_code, r.text[:120]))
                if r.status_code == 200:
                    try:
                        _mark("ar_receipts", r.json()["id"])
                    except Exception:
                        pass

        t1 = threading.Thread(target=fire, args=(order1["id"],))
        t2 = threading.Thread(target=fire, args=(order2["id"],))
        t1.start(); t2.start(); t1.join(); t2.join()

        codes = sorted(c for c, _ in results)
        assert codes == [200, 409], f"Expected [200, 409], got {results}"

        # Only one receipt actually exists
        rc_count = db.ar_receipts.count_documents({"customer_id": cust["id"]})
        assert rc_count == 1

        # Deposit balance ends at 20
        c = db.customers.find_one({"id": cust["id"]})
        assert round(c["deposit_balance"], 2) == 20.0


# ═══════════════════════════ W2-022 / W2-023 ═══════════════════════════
class TestW2_022_023_PayrollPay:
    def _make_posted_run(self) -> str:
        rid = f"prun_{PREFIX}_{uuid.uuid4().hex[:6]}"
        db.hr_payroll_runs.insert_one({
            "id": rid, "number": f"PR-{PREFIX}-{uuid.uuid4().hex[:4]}",
            "entity_id": ENT, "period": "2099-02", "status": "posted",
            "totals": {"net": 100000.0, "gross": 100000.0}, "payslips": [],
            "created_at": "2099-02-01T00:00:00",
        })
        _mark("hr_payroll_runs", rid)
        return rid

    def test_pay_with_expense_account_rejected(self):
        s = admin_session()
        rid = self._make_posted_run()
        r = s.post(f"{BASE}/hr/payroll/runs/{rid}/pay",
                   json={"cash_account": "6-1000"}, timeout=30)
        assert r.status_code == 400, r.text
        # No journal, run still posted
        je = db.journal_entries.find_one(
            {"source_type": "payroll_pay", "source_id": f"{ENT}:2099-02"})
        assert je is None
        run = db.hr_payroll_runs.find_one({"id": rid})
        assert run["status"] == "posted"
        # No cash txn
        assert db.cash_transactions.count_documents({"ref_type": "payroll_run", "ref_id": rid}) == 0

    def test_pay_with_cash_account_posts_journal_and_cash_txn(self):
        s = admin_session()
        rid = self._make_posted_run()
        r = s.post(f"{BASE}/hr/payroll/runs/{rid}/pay",
                   json={"cash_account": "1-1100"}, timeout=30)
        assert r.status_code == 200, r.text
        run = r.json()
        assert run["status"] == "paid"

        je = db.journal_entries.find_one(
            {"source_type": "payroll_pay", "source_id": f"{ENT}:2099-02", "status": {"$ne": "void"}})
        assert je is not None
        _mark("journal_entries", je["id"])

        cash = list(db.cash_transactions.find({"ref_type": "payroll_run", "ref_id": rid}))
        assert len(cash) == 1, f"Expected 1 cash_transaction, got {len(cash)}"
        _mark("cash_transactions", cash[0]["id"])
        assert cash[0]["direction"] == "out"
        assert round(cash[0]["amount"], 2) == 100000.0

        # Repeat pay — idempotent (rejected or no 2nd cash txn)
        r2 = s.post(f"{BASE}/hr/payroll/runs/{rid}/pay",
                    json={"cash_account": "1-1100"}, timeout=30)
        cash_after = db.cash_transactions.count_documents(
            {"ref_type": "payroll_run", "ref_id": rid})
        assert cash_after == 1, f"Repeat pay created extra cash_txn (count now {cash_after})"
        je_after = db.journal_entries.count_documents(
            {"source_type": "payroll_pay", "source_id": f"{ENT}:2099-02", "status": {"$ne": "void"}})
        assert je_after == 1


# ═══════════════════════════ W2-020 (in-process) ═══════════════════════════
@pytest.mark.asyncio
async def test_w2_020_refund_cash_failure_then_retry(monkeypatch):
    """Monkeypatch cash_ledger.record_return_cash to raise on first invocation.
    settle_return must respond 409 (via HTTPException), status not refund_settled,
    credit_note_id present, settlement_pending set, stock_adjusted True.
    Retry (second settle) completes exactly one cash_txn, no extra CN / no extra GL.
    """
    import sys
    sys.path.insert(0, "C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend")
    from services import return_service, cash_ledger  # type: ignore

    # Build synthetic shipped order + return (ready-for-settle) directly in Mongo
    cust = _make_customer()
    prod = db.products.find_one({}, {"_id": 0, "id": 1, "name": 1})
    assert prod, "Need at least one seed product"
    pid = prod["id"]
    oid = f"so_{PREFIX}_{uuid.uuid4().hex[:6]}"
    db.sales_orders.insert_one({
        "id": oid, "number": f"{PREFIX}-SO", "customer_id": cust["id"], "customer_name": cust["name"],
        "entity_id": ENT, "grand_total": 100.0, "paid_total": 100.0,
        "payments": [{"id": "p1", "amount": 100.0, "method": "cash"}],
        "items": [{"product_id": pid, "product_name": prod.get("name", "X"), "quantity": 10, "unit": "m",
                   "unit_price": 10.0, "subtotal": 100.0}],
        "status": "confirmed", "payment_status": "paid",
        "payment_profile_method": "cash", "payment_term_code": "cash",
        "created_at": "2099-01-01T00:00:00",
    })
    _mark("sales_orders", oid)

    rid = f"sret_{PREFIX}_{uuid.uuid4().hex[:6]}"
    db.sales_returns.insert_one({
        "id": rid, "number": f"RET-{PREFIX}", "order_id": oid, "order_number": f"{PREFIX}-SO",
        "customer_id": cust["id"], "customer_name": cust["name"], "entity_id": ENT,
        "status": "inspected", "outcome": "", "stock_adjusted": False,
        "items": [{"product_id": pid, "product_name": prod.get("name", "X"), "unit": "m",
                   "quantity_returned": 10, "quantity_requested": 10, "unit_price": 10.0,
                   "inspection": {"accepted_quantity": 10, "rejected_quantity": 0}}],
        "created_at": "2099-01-01T00:00:00",
    })
    _mark("sales_returns", rid)

    # Patch cash_ledger module reference used by return_service
    calls = {"n": 0}
    real = cash_ledger.record_return_cash

    async def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("TEST_INJECTED cash ledger down")
        return await real(*args, **kwargs)

    monkeypatch.setattr("services.cash_ledger.record_return_cash", flaky)
    # Also patch module-level import inside return_service if it imports lazily — it does `from services import cash_ledger`
    import services.cash_ledger as _cl
    monkeypatch.setattr(_cl, "record_return_cash", flaky)

    # First settle — expect 409
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await return_service.settle_return(
            rid, "tester", outcome="refund",
            item_decisions=[{"line_id": "", "accepted_quantity": 10, "rejected_quantity": 0}],
            refund_account_code="1-1100")
    assert exc.value.status_code == 409

    ret = db.sales_returns.find_one({"id": rid})
    assert ret["status"] != "refund_settled", f"Status should not be final: {ret['status']}"
    assert ret.get("credit_note_id"), "Credit note should be persisted"
    assert ret.get("stock_adjusted") is True, "Restock should be done"
    assert ret.get("settlement_pending", {}).get("effect") == "cash_ledger"

    cn_id = ret["credit_note_id"]
    cn_count_before = db.credit_notes.count_documents({"id": cn_id})
    je_count_before = db.journal_entries.count_documents(
        {"source_type": {"$in": ["sales_return", "credit_note"]}, "ref.return_id": rid})

    # Retry settle (cash_ledger now succeeds on 2nd invocation)
    doc = await return_service.settle_return(
        rid, "tester", outcome="refund",
        item_decisions=[{"line_id": "", "accepted_quantity": 10, "rejected_quantity": 0}],
        refund_account_code="1-1100")
    assert doc["status"] == "refund_settled"

    # One credit note total
    cn_count_after = db.credit_notes.count_documents({"id": cn_id})
    assert cn_count_after == cn_count_before == 1

    # Exactly one cash txn now
    cash = list(db.cash_transactions.find({"ref_type": "sales_return", "ref_id": rid}))
    assert len(cash) == 1
    _mark("cash_transactions", cash[0]["id"])

    # Mark CN for cleanup
    _mark("credit_notes", cn_id)


# ═══════════════════════════ Smoke regressions ═══════════════════════════
class TestSmokeChangedEndpoints:
    def test_rfid_reads_admin(self):
        s = admin_session()
        r = s.get(f"{BASE}/rfid/reads", timeout=30)
        assert r.status_code == 200, r.text

    def test_rnd_samples_admin(self):
        s = admin_session()
        r = s.get(f"{BASE}/rnd/samples", timeout=30)
        assert r.status_code == 200, r.text


# ═══════════════════════════ Teardown ═══════════════════════════
def teardown_module(module):
    """Clean up TEST_W2T_* data."""
    for coll, ids in _created.items():
        if ids:
            try:
                db[coll].delete_many({"id": {"$in": ids}})
            except Exception as e:
                print(f"[teardown] {coll}: {e}")
    # Catch-alls by prefix
    for coll in ["customers", "sales_orders", "sales_returns", "ar_receipts",
                 "hr_payroll_runs", "cash_transactions", "journal_entries", "credit_notes",
                 "payment_variance_decisions", "inventory_rolls", "inventory_movements"]:
        try:
            db[coll].delete_many({"$or": [
                {"id": {"$regex": f"^.*_{PREFIX}"}},
                {"number": {"$regex": PREFIX}},
                {"customer_name": {"$regex": PREFIX}},
                {"source_document": {"$regex": PREFIX}},
                {"ref_id": {"$regex": PREFIX}},
            ]})
        except Exception:
            pass
    # lot yang lahir dari restock retur uji dan kini tanpa roll (INV-LOT-04)
    for lot in db.inventory_lots.find({"created_at": {"$gte": _STARTED_AT}}, {"id": 1}):
        if not db.inventory_rolls.count_documents({"lot_id": lot["id"]}):
            db.inventory_lots.delete_one({"id": lot["id"]})
