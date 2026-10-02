"""Iter 112 — HTTP-level checks for iter-323 label/reimburse/po-line/badge follow-up.

Complements repro_followup2.py by exercising HTTP contracts:
- vendor-bills: product on >1 PO lines without po_line_code → 400;
  same po_line_code twice → 400.
- finance/posting-failures/count: admin 200, sales 403.
- inventory/cut-children-unverified: admin 200.
"""
import asyncio
import os
import sys
import uuid

import pytest
import requests

sys.path.insert(0, "/app/backend")


@pytest.fixture(scope="module")
def loop():
    lp = asyncio.new_event_loop()
    yield lp
    lp.close()


def _run(loop, coro):
    return loop.run_until_complete(coro)


def _base():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        for ln in open("/app/frontend/.env"):
            if ln.startswith("REACT_APP_BACKEND_URL"):
                url = ln.split("=", 1)[1].strip()
                break
    assert url, "REACT_APP_BACKEND_URL missing"
    return url.rstrip("/") + "/api"


BASE = _base()
A = "ent_ksc"


def _login(email):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=20)
    assert r.status_code == 200, r.text
    s.headers["X-Entity-Id"] = A
    return s


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id")


@pytest.fixture(scope="module")
def sales():
    return _login("sales@kainnusantara.id")


# ── Badge counts ─────────────────────────────────────────────────────────
def test_posting_failures_count_admin(admin):
    r = admin.get(f"{BASE}/finance/posting-failures/count", timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "total" in data and isinstance(data["total"], int)


def test_posting_failures_count_sales_forbidden(sales):
    r = sales.get(f"{BASE}/finance/posting-failures/count", timeout=20)
    assert r.status_code == 403


# ── Unverified cut children list ─────────────────────────────────────────
def test_cut_children_unverified_admin(admin):
    r = admin.get(f"{BASE}/inventory/cut-children-unverified", timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body and isinstance(body["items"], list)


# ── Vendor bill line ambiguity / duplicate line rejection ────────────────
def _seed_po_two_lines(loop, tag):
    """Create a PO with the same product on two lines and both fully received."""
    from db import db

    async def _do():
        prod = await db.products.find_one({}, {"_id": 0, "id": 1})
        po_id = f"po_iter112_{tag}"
        doc = {
            "id": po_id,
            "po_number": f"PO-ITER112-{tag}",
            "entity_id": A,
            "status": "received",
            "supplier_id": "",
            "items": [
                {"product_id": prod["id"], "line_code": "LA", "quantity": 20, "received_qty": 20,
                 "price": 100000, "unit": "meter", "sku": "", "product_name": "x"},
                {"product_id": prod["id"], "line_code": "LB", "quantity": 20, "received_qty": 20,
                 "price": 110000, "unit": "meter", "sku": "", "product_name": "x"},
            ],
        }
        await db.purchase_orders.insert_one(doc)
        return po_id, prod["id"]

    return _run(loop, _do())


def _cleanup_po(loop, po_id):
    from db import db

    async def _do():
        bills = [b["id"] async for b in db.vendor_bills.find({"po_id": po_id}, {"id": 1})]
        await db.journal_entries.delete_many({"source_id": {"$in": bills}})
        await db.vendor_bills.delete_many({"po_id": po_id})
        await db.purchase_orders.delete_one({"id": po_id})
        await db.doc_refs.delete_many({"$or": [{"from_id": {"$in": bills}}, {"to_id": {"$in": bills}}]})

    _run(loop, _do())


def test_vendor_bill_ambiguous_line_rejected(admin, loop):
    tag = uuid.uuid4().hex[:6]
    po_id, prod_id = _seed_po_two_lines(loop, tag)
    try:
        body = {"po_id": po_id, "submit_now": False,
                "items": [{"product_id": prod_id, "billed_qty": 5}]}
        r = admin.post(f"{BASE}/vendor-bills", json=body, timeout=30)
        assert r.status_code == 400, (r.status_code, r.text)
    finally:
        _cleanup_po(loop, po_id)


def test_vendor_bill_duplicate_line_rejected(admin, loop):
    tag = uuid.uuid4().hex[:6]
    po_id, prod_id = _seed_po_two_lines(loop, tag)
    try:
        body = {"po_id": po_id, "submit_now": False,
                "items": [
                    {"product_id": prod_id, "po_line_code": "LA", "billed_qty": 5},
                    {"product_id": prod_id, "po_line_code": "LA", "billed_qty": 3},
                ]}
        r = admin.post(f"{BASE}/vendor-bills", json=body, timeout=30)
        assert r.status_code == 400, (r.status_code, r.text)
    finally:
        _cleanup_po(loop, po_id)


def test_vendor_bill_per_line_matched(admin, loop):
    tag = uuid.uuid4().hex[:6]
    po_id, prod_id = _seed_po_two_lines(loop, tag)
    try:
        body = {"po_id": po_id, "submit_now": False,
                "items": [
                    {"product_id": prod_id, "po_line_code": "LA", "billed_qty": 20},
                    {"product_id": prod_id, "po_line_code": "LB", "billed_qty": 20},
                ]}
        r = admin.post(f"{BASE}/vendor-bills", json=body, timeout=30)
        assert r.status_code in (200, 201), (r.status_code, r.text)
    finally:
        _cleanup_po(loop, po_id)
