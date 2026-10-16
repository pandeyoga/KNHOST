"""Gelombang 3 · Fase 02 — uji API live (preview DB) untuk D4-ICLOAN-01,
D4-RFQ-02, dan D4-DASH-01.

Pola: data uji ber-prefix TEST_ disuntik langsung ke DB; dibersihkan di akhir.
Tidak menyentuh data demo yang sudah ada.

Jalankan:
    cd /app && python -m pytest backend/tests/test_g3_phase02_api.py -q -n0
"""
import asyncio
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone

import pytest
import requests

sys.path.insert(0, "/app/backend")
try:
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
except Exception:  # noqa: BLE001
    pass

from pymongo import MongoClient  # noqa: E402

BASE = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"
BASE = BASE.rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

TEST_PREFIX = "TEST_G3P2_"


# ─── helpers ────────────────────────────────────────────────────────────────
def _mdb():
    return MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)[DB_NAME]


def _login(email, password="demo12345"):
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


def _hdr(token, entity="all"):
    return {"Authorization": f"Bearer {token}", "X-Entity-Id": entity,
            "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_token():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def db():
    return _mdb()


@pytest.fixture(scope="module")
def limited_user(db):
    """TEST_ user ber-role NON-cross-entity (finance) dengan allowed_entity_ids=[ent_ksc].

    Perilaku `admin` dan `manager` adalah CROSS_ENTITY (lihat role_registry.py) → mereka
    MELEWATI `allowed_entity_ids` dan selalu melihat seluruh entitas aktif. Jadi untuk
    menguji guard entitas kita WAJIB memakai peran lain. Peran `finance` default tidak
    punya izin interco/rfq, karena itu kita TAMBAH izin yang dibutuhkan ke matriks izin
    DEFAULT selama uji berjalan, lalu dikembalikan di teardown.
    """
    uid = f"{TEST_PREFIX}user_fin_ksc"
    db.users.replace_one(
        {"id": uid},
        {"id": uid, "email": f"{TEST_PREFIX}fin_ksc@test.local",
         "name": "TEST Limited Finance",
         "role": "finance", "status": "active",
         "home_entity_id": "ent_ksc", "allowed_entity_ids": ["ent_ksc"],
         "password_hash": "n/a"},
        upsert=True)
    # Backup matriks izin dan tambahkan interco + rfq ke peran finance.
    original = db.permission_settings.find_one({"id": "default"}, {"_id": 0})
    matrix = (original or {}).get("matrix", {})
    finance_perms = dict(matrix.get("finance", {}))
    finance_perms["interco"] = ["view", "create", "update", "approve", "cancel",
                                "ship", "receive", "invoice", "settle", "return"]
    finance_perms["rfq"] = ["view", "create", "update", "award"]
    new_matrix = {**matrix, "finance": finance_perms}
    db.permission_settings.update_one({"id": "default"},
                                      {"$set": {"matrix": new_matrix}}, upsert=True)
    token = secrets.token_urlsafe(32)
    db.sessions.insert_one({
        "id": f"{TEST_PREFIX}sess_fin_ksc",
        "token": token, "user_id": uid,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=4),
    })
    yield token
    # Pulihkan matriks awal — JANGAN tinggalkan izin tambahan di DB preview.
    if original is not None:
        db.permission_settings.replace_one({"id": "default"}, original, upsert=True)
    else:
        db.permission_settings.delete_one({"id": "default"})
    db.sessions.delete_many({"id": {"$regex": f"^{TEST_PREFIX}"}})
    db.users.delete_many({"id": {"$regex": f"^{TEST_PREFIX}"}})


@pytest.fixture(scope="module", autouse=True)
def _cleanup(db):
    """Nol residu — hapus semua data TEST_ di akhir modul."""
    yield
    for coll in ["interco_loans", "rfqs", "sessions", "users", "audit_logs"]:
        db[coll].delete_many({"id": {"$regex": f"^{TEST_PREFIX}"}})
    db.interco_loans.delete_many({"pair_id": {"$regex": f"^{TEST_PREFIX}"}})
    db.rfqs.delete_many({"number": {"$regex": f"^{TEST_PREFIX}"}})


# ─── D4-ICLOAN-01 ───────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def seeded_loan(db):
    """Pinjaman: lender=ent_ksc, borrower=ent_kanda, status=draft."""
    pair = f"{TEST_PREFIX}pair01"
    lender_id = f"{TEST_PREFIX}loan_lender"
    borrower_id = f"{TEST_PREFIX}loan_borrower"
    common = {
        "pair_id": pair, "principal": 1_000_000.0, "outstanding": 1_000_000.0,
        "repaid_amount": 0.0, "purpose": "TEST pinjaman antar-PT",
        "interest_note": "", "agreed_return_date": "", "doc_date": "2026-10-06",
        "status": "draft", "created_at": "2026-10-06", "updated_at": "2026-10-06",
        "lender_entity_id": "ent_ksc", "lender_entity_name": "Sukacita",
        "borrower_entity_id": "ent_kanda", "borrower_entity_name": "Kanda Fabric",
        "number": f"{TEST_PREFIX}ICL-01", "status_history": [],
    }
    db.interco_loans.delete_many({"pair_id": pair})
    db.interco_loans.insert_many([
        {**common, "id": lender_id, "role": "lender", "entity_id": "ent_ksc",
         "counterpart_id": borrower_id, "counterpart_number": f"{TEST_PREFIX}ICL-01B"},
        {**common, "id": borrower_id, "role": "borrower", "entity_id": "ent_kanda",
         "counterpart_id": lender_id, "counterpart_number": f"{TEST_PREFIX}ICL-01A"},
    ])
    yield {"pair_id": pair, "lender_id": lender_id, "borrower_id": borrower_id}
    db.interco_loans.delete_many({"pair_id": pair})


def _snapshot_loan(db, loan_id):
    doc = db.interco_loans.find_one({"id": loan_id}, {"_id": 0})
    return doc


def test_icloan01_limited_user_cannot_read_other_entity_side(limited_user, seeded_loan):
    r = requests.get(f"{BASE}/api/interco/loans/{seeded_loan['borrower_id']}",
                     headers=_hdr(limited_user, "ent_ksc"), timeout=15)
    assert r.status_code in (403, 404), f"borrower side (ent_kanda) wajib tertolak: {r.status_code} {r.text[:200]}"


def test_icloan01_limited_user_disburse_rejected(limited_user, seeded_loan, db):
    before = _snapshot_loan(db, seeded_loan["borrower_id"])
    r = requests.post(f"{BASE}/api/interco/loans/{seeded_loan['borrower_id']}/disburse",
                      headers=_hdr(limited_user, "ent_ksc"), json={}, timeout=15)
    assert r.status_code in (403, 404), f"disburse wajib tertolak: {r.status_code} {r.text[:200]}"
    after = _snapshot_loan(db, seeded_loan["borrower_id"])
    assert before["status"] == after["status"] == "draft", "status TIDAK boleh berubah saat ditolak"
    assert before["outstanding"] == after["outstanding"], "saldo TIDAK boleh berubah"


def test_icloan01_limited_user_repay_rejected(limited_user, seeded_loan, db):
    before = _snapshot_loan(db, seeded_loan["borrower_id"])
    r = requests.post(f"{BASE}/api/interco/loans/{seeded_loan['borrower_id']}/repay",
                      headers=_hdr(limited_user, "ent_ksc"),
                      json={"amount": 100, "note": "x"}, timeout=15)
    assert r.status_code in (403, 404), f"repay wajib tertolak: {r.status_code} {r.text[:200]}"
    after = _snapshot_loan(db, seeded_loan["borrower_id"])
    assert before["outstanding"] == after["outstanding"]
    assert before["repaid_amount"] == after["repaid_amount"]


def test_icloan01_limited_user_cancel_rejected(limited_user, seeded_loan, db):
    before = _snapshot_loan(db, seeded_loan["borrower_id"])
    r = requests.post(f"{BASE}/api/interco/loans/{seeded_loan['borrower_id']}/cancel",
                      headers=_hdr(limited_user, "ent_ksc"),
                      json={"reason": "test cancel"}, timeout=15)
    assert r.status_code in (403, 404), f"cancel wajib tertolak: {r.status_code} {r.text[:200]}"
    after = _snapshot_loan(db, seeded_loan["borrower_id"])
    assert before["status"] == after["status"]


def test_icloan01_limited_user_can_read_own_entity_side(limited_user, seeded_loan):
    r = requests.get(f"{BASE}/api/interco/loans/{seeded_loan['lender_id']}",
                     headers=_hdr(limited_user, "ent_ksc"), timeout=15)
    assert r.status_code == 200, f"lender side (ent_ksc) wajib bisa dibaca: {r.status_code} {r.text[:200]}"


def test_icloan01_admin_can_read_both_sides(admin_token, seeded_loan):
    for side in ("lender_id", "borrower_id"):
        r = requests.get(f"{BASE}/api/interco/loans/{seeded_loan[side]}",
                         headers=_hdr(admin_token, "all"), timeout=15)
        assert r.status_code == 200, f"admin {side}: {r.status_code} {r.text[:200]}"


# ─── D4-RFQ-02 ──────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def seeded_rfq(db):
    rfq_id = f"{TEST_PREFIX}rfq01"
    doc = {
        "id": rfq_id, "number": f"{TEST_PREFIX}RFQ-01",
        "entity_id": "ent_kanda",                 # ← milik ent_kanda
        "status": "draft",
        "created_at": "2026-10-06", "updated_at": "2026-10-06",
        "items": [{"line_id": "l1", "product_id": "p_TEST_x", "quantity": 10,
                   "unit": "meter", "description": "TEST item", "expected_grade": "A"}],
        "suppliers": [], "quotes": [], "award": {}, "notes": "TEST",
        "pr_id": "", "pr_number": "",
    }
    db.rfqs.delete_many({"id": rfq_id})
    db.rfqs.insert_one(doc)
    yield rfq_id
    db.rfqs.delete_many({"id": rfq_id})


def test_rfq02_limited_user_cannot_get_other_entity_rfq(limited_user, seeded_rfq):
    r = requests.get(f"{BASE}/api/rfqs/{seeded_rfq}",
                     headers=_hdr(limited_user, "ent_ksc"), timeout=15)
    assert r.status_code in (403, 404), f"get wajib tertolak: {r.status_code} {r.text[:200]}"


def test_rfq02_limited_user_cannot_compare_other_entity_rfq(limited_user, seeded_rfq):
    r = requests.get(f"{BASE}/api/rfqs/{seeded_rfq}/compare",
                     headers=_hdr(limited_user, "ent_ksc"), timeout=15)
    assert r.status_code in (403, 404), f"compare wajib tertolak: {r.status_code} {r.text[:200]}"


def test_rfq02_limited_user_send_rejected(limited_user, seeded_rfq, db):
    before = db.rfqs.find_one({"id": seeded_rfq}, {"_id": 0})
    r = requests.post(f"{BASE}/api/rfqs/{seeded_rfq}/send",
                      headers=_hdr(limited_user, "ent_ksc"),
                      json={"supplier_ids": ["sup1"]}, timeout=15)
    assert r.status_code in (403, 404), f"send wajib tertolak: {r.status_code} {r.text[:200]}"
    after = db.rfqs.find_one({"id": seeded_rfq}, {"_id": 0})
    assert before["status"] == after["status"] == "draft"


def test_rfq02_limited_user_quote_rejected(limited_user, seeded_rfq, db):
    before_quotes = len(db.rfqs.find_one({"id": seeded_rfq})["quotes"])
    r = requests.post(f"{BASE}/api/rfqs/{seeded_rfq}/quote",
                      headers=_hdr(limited_user, "ent_ksc"),
                      json={"supplier_id": "sup1",
                            "lines": [{"line_id": "l1", "price": 1000, "available": True}]},
                      timeout=15)
    assert r.status_code in (403, 404), f"quote wajib tertolak: {r.status_code} {r.text[:200]}"
    after_quotes = len(db.rfqs.find_one({"id": seeded_rfq})["quotes"])
    assert before_quotes == after_quotes, "jumlah kutipan TIDAK boleh berubah"


def test_rfq02_limited_user_award_rejected(limited_user, seeded_rfq):
    r = requests.post(f"{BASE}/api/rfqs/{seeded_rfq}/award",
                      headers=_hdr(limited_user, "ent_ksc"),
                      json={"mode": "full", "full_supplier_id": "sup1"},
                      timeout=15)
    assert r.status_code in (403, 404)


def test_rfq02_limited_user_cancel_rejected(limited_user, seeded_rfq, db):
    before = db.rfqs.find_one({"id": seeded_rfq}, {"_id": 0})
    r = requests.post(f"{BASE}/api/rfqs/{seeded_rfq}/cancel",
                      headers=_hdr(limited_user, "ent_ksc"),
                      json={"reason": "test cancel"}, timeout=15)
    assert r.status_code in (403, 404)
    after = db.rfqs.find_one({"id": seeded_rfq}, {"_id": 0})
    assert before["status"] == after["status"]


def test_rfq02_admin_can_access(admin_token, seeded_rfq):
    r = requests.get(f"{BASE}/api/rfqs/{seeded_rfq}",
                     headers=_hdr(admin_token, "all"), timeout=15)
    assert r.status_code == 200
    r = requests.get(f"{BASE}/api/rfqs/{seeded_rfq}/compare",
                     headers=_hdr(admin_token, "all"), timeout=15)
    assert r.status_code == 200


# ─── D4-DASH-01 ─────────────────────────────────────────────────────────────
def test_dash01_dashboard_200_and_counts_all_products(admin_token, db):
    r = requests.get(f"{BASE}/api/dashboard",
                     headers=_hdr(admin_token, "all"), timeout=30)
    assert r.status_code == 200, f"dashboard tidak 200: {r.status_code} {r.text[:200]}"
    data = r.json()
    metrics = data.get("metrics", {})
    actual_total = db.products.count_documents({})
    assert metrics.get("products") == actual_total, (
        f"metrics.products ({metrics.get('products')}) wajib == count_documents "
        f"({actual_total}) tanpa batas 3000")
    # Jumlah produk yang dipaparkan di `products` juga harus sama (tanpa to_list(3000)).
    assert len(data.get("products", [])) == actual_total, (
        f"products array ({len(data.get('products', []))}) wajib == {actual_total} (tanpa limit)")


def test_dash01_dashboard_balance_scope_unlimited(admin_token, db):
    r = requests.get(f"{BASE}/api/dashboard?entity_id=ent_ksc",
                     headers=_hdr(admin_token, "ent_ksc"), timeout=30)
    assert r.status_code == 200
    data = r.json()
    metrics = data.get("metrics", {})
    assert metrics.get("products", -1) >= 0
    # Hanya memastikan endpoint menghitung tanpa gagal pada katalog penuh.
