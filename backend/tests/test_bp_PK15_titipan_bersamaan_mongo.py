"""PK-15 U14 — di MongoDB ASLI (lingkungan A): dua alokasi titipan BERSAMAAN, masing-masing 6.000.000 dari titipan
10.000.000 → tepat satu berhasil; sisa titipan tidak pernah negatif; satu jurnal alokasi.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); data uji (baris rekening koran, dua pesanan)
disisipkan langsung ke database uji lokal (`MONGO_URL`/`DB_NAME`) lalu dihapus. Tidak untuk data nyata.
"""
import datetime
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()


def _login():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture()
def siap():
    acc = DB.bank_accounts.find_one({"entity_id": "ent_ksc", "account_type": "bank", "is_active": {"$ne": False}})
    if not acc:
        pytest.skip("tidak ada rekening bank aktif ent_ksc")
    cus = DB.customers.find_one({"entity_id": {"$in": ["ent_ksc", "all"]}}, {"_id": 0, "id": 1}) or {"id": "cus_pk15"}
    lid = f"stl_pk15_{TAG}"
    DB.bank_statement_lines.insert_one({
        "id": lid, "bank_account_id": acc["id"], "entity_id": "ent_ksc", "stmt_date": NOW[:10], "amount": 10_000_000.0,
        "direction": "in", "description": f"uji PK-15 U14 {TAG}", "counterparty": "", "desc_key": "", "ref": "",
        "external_id": f"pk15-{TAG}", "balance": 0.0, "status": "unmatched", "match_kind": "", "matched_txn_id": "",
        "matched_txn_ids": [], "allocations": [], "score": 0, "score_explain": [], "suggestions": [],
        "match_type": "", "matched_at": "", "matched_by": "", "holding": {}, "holding_allocated": [],
        "holding_remaining": 0.0, "import_batch": "pk15", "format_id": "", "created_at": NOW, "updated_at": NOW})
    so = []
    for k in ("a", "b"):
        oid = f"so_pk15_{TAG}_{k}"
        DB.sales_orders.insert_one({"id": oid, "number": f"SO-PK15-{TAG}-{k}", "entity_id": "ent_ksc",
                                    "customer_id": cus["id"], "grand_total": 7_000_000, "status": "confirmed",
                                    "payments": [], "paid_total": 0.0, "created_at": NOW})
        so.append(oid)
    yield lid, so, cus["id"]
    DB.sales_orders.delete_many({"id": {"$in": so}})


def test_U14_alokasi_bersamaan(siap):
    lid, so, cus = siap
    h = _login()
    r = requests.post(f"{BASE}/bank-reconciliation/lines/{lid}/holding", headers=h, json={"note": "uji PK-15 U14"},
                      timeout=60)
    assert r.status_code == 200, r.text

    def alokasi(oid):
        return requests.post(f"{BASE}/bank-reconciliation/lines/{lid}/holding/allocate", headers=h, timeout=60, json={
            "customer_id": cus, "reason_code": "titipan_teridentifikasi", "note": "uji bersamaan",
            "allocations": [{"order_id": oid, "amount": 6_000_000}]})
    with ThreadPoolExecutor(2) as ex:
        hasil = [f.result() for f in [ex.submit(alokasi, so[0]), ex.submit(alokasi, so[1])]]
    kode = sorted(x.status_code for x in hasil)
    print("kode:", kode, [x.text[:160] for x in hasil if x.status_code != 200])
    assert kode[0] == 200 and kode[1] in (400, 409), [x.text for x in hasil]
    b = DB.bank_statement_lines.find_one({"id": lid}, {"_id": 0})
    assert b["holding_remaining"] == 4_000_000
    assert "saga_lock" not in b
    assert DB.journal_entries.count_documents({"source_type": "bank_holding_alloc",
                                               "source_id": {"$regex": f"^{lid}:"}}) == 1
