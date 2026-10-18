"""Backend tests — Panel Posting Gagal (P03 lanjutan) + gate checks (iter 111).

GET  /api/finance/posting-failures  (admin 200, sales 403)
POST /api/finance/posting-failures/{kind}/{id}/retry (unknown 400, missing 404)
Seed synthetic failed cash_transaction, verify surfaces, retry flips status, exactly
one journal_entries row w/ source_type cash_transaction; then cleanup.
"""
import asyncio
import os
import sys
import uuid
import pytest
import requests

sys.path.insert(0, "/app/backend")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0]).rstrip("/")
ENTITY = "ent_ksc"


def _login(email: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    s.headers.update({"X-Entity-Id": ENTITY})
    return s


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id")


@pytest.fixture(scope="module")
def sales():
    return _login("sales@kainnusantara.id")


def test_posting_failures_admin_ok(admin):
    r = admin.get(f"{BASE_URL}/api/finance/posting-failures", timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "items" in d and "counts" in d and "labels" in d
    assert "cash_transaction" in d["labels"]


def test_posting_failures_sales_forbidden(sales):
    r = sales.get(f"{BASE_URL}/api/finance/posting-failures", timeout=30)
    assert r.status_code == 403, r.text


def test_retry_unknown_kind_400(admin):
    r = admin.post(f"{BASE_URL}/api/finance/posting-failures/foobar/xxx/retry", timeout=30)
    assert r.status_code == 400, r.text


def test_retry_missing_id_404(admin):
    r = admin.post(
        f"{BASE_URL}/api/finance/posting-failures/cash_transaction/does_not_exist_TEST/retry",
        timeout=30)
    assert r.status_code == 404, r.text


def test_failed_cash_txn_surfaces_retry_and_cleanup(admin):
    from db import db as db_ref  # type: ignore
    from core_utils import now_iso, new_id  # type: ignore

    async def _main():
        txn_id = new_id("cash_txn_TEST")
        number = f"TEST_KAS_{uuid.uuid4().hex[:6]}"
        doc = {
            "id": txn_id, "entity_id": ENTITY, "number": number,
            "txn_date": now_iso(), "cash_type": "kas_besar", "direction": "in",
            "amount": 12345.0, "status": "posted",
            "category": "modal", "ref_type": "manual", "ref_id": "",
            "account_id": "bank_kas_besar_ksc",
            "description": "TEST synthetic failed posting",
            "gl_status": "failed", "gl_error": "TEST synthetic error",
            "created_by": "test",
            "created_at": now_iso(), "updated_at": now_iso(),
        }
        await db_ref.cash_transactions.insert_one(doc)
        try:
            r = admin.get(f"{BASE_URL}/api/finance/posting-failures", timeout=30)
            assert r.status_code == 200
            row = next((i for i in r.json()["items"] if i["id"] == txn_id), None)
            assert row is not None, "seeded failed cash_txn did not surface"
            assert row["kind"] == "cash_transaction"

            pre = await db_ref.journal_entries.count_documents(
                {"source_type": "cash_transaction", "source_id": txn_id})
            r2 = admin.post(
                f"{BASE_URL}/api/finance/posting-failures/cash_transaction/{txn_id}/retry",
                timeout=60)
            assert r2.status_code == 200, r2.text
            assert r2.json().get("gl_status") == "posted", r2.text

            post = await db_ref.journal_entries.count_documents(
                {"source_type": "cash_transaction", "source_id": txn_id})
            assert post == pre + 1, f"expected exactly 1 new JE, pre={pre} post={post}"

            r3 = admin.get(f"{BASE_URL}/api/finance/posting-failures", timeout=30)
            assert not any(i["id"] == txn_id for i in r3.json()["items"])
        finally:
            await db_ref.cash_transactions.delete_one({"id": txn_id})
            jes = await db_ref.journal_entries.find(
                {"source_type": "cash_transaction", "source_id": txn_id},
                {"id": 1, "_id": 0}).to_list(50)
            je_ids = [j["id"] for j in jes]
            if je_ids:
                await db_ref.journal_entries.delete_many({"id": {"$in": je_ids}})
                await db_ref.gl_entries.delete_many(
                    {"journal_entry_id": {"$in": je_ids}})

    asyncio.run(_main())
