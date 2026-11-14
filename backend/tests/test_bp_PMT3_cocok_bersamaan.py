"""PM-T3 U17 — di MongoDB ASLI (lingkungan A): dua `auto_match` BERSAMAAN atas mutasi berkode bayar.

Persiapan (FIXTURE disisip langsung ke database uji `MONGO_URL`/`DB_NAME`, ditandai `TAG` dan dihapus sesudahnya):
rekening penerimaan uji di `ent_ksc` (melayani transfer), pelanggan, pesanan bersisa Rp 1.500.000 dengan rekening tujuan
itu dan kode bayar acak `KN-xxxxx`. ALUR lewat API: kwitansi Rp 1.500.000 ke rekening itu, impor mutasi Rp 1.500.000
berberita kode bayar, lalu dua `POST /api/bank-reconciliation/auto-match` bersamaan.

Harapan (spesifikasi U17): satu tautan; `reconciled_amount` kas kwitansi = 1.500.000 (bukan 3.000.000); kwitansi
`bank_verified: true` sekali (satu `bank_line_ids`). Pembersihan: lepas pencocokan → batalkan kwitansi (pembalik lewat
API) → hapus fixture. Tidak untuk data nyata.
"""
import datetime
import os
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
ACC, CUS, SO = f"ba_pmt3_{TAG}", f"cus_pmt3_{TAG}", f"so_pmt3_{TAG}"
KODE = "KN-" + "".join(secrets.choice("23456789ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(5))


def _login():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture()
def siap():
    DB.bank_accounts.insert_one({
        "id": ACC, "name": f"Uji PMT3 {TAG}", "account_type": "bank", "cash_type": "kas_besar", "bank_name": "BCA",
        "account_number": f"9{TAG}", "entity_id": "ent_ksc", "is_active": True, "opening_balance": 0,
        "holder_name": "PT Kain Suka Cita", "purposes": ["penerimaan_pelanggan"], "payment_method_codes": ["transfer"],
        "default_receiving_methods": [], "show_on_documents": False, "created_at": NOW, "updated_at": NOW})
    DB.customers.insert_one({"id": CUS, "name": f"Toko Uji PMT3 {TAG}", "entity_id": "ent_ksc", "status": "active"})
    DB.sales_orders.insert_one({
        "id": SO, "number": f"SO-PMT3-{TAG}", "entity_id": "ent_ksc", "customer_id": CUS,
        "customer_name": f"Toko Uji PMT3 {TAG}", "status": "confirmed", "grand_total": 1_500_000.0, "payments": [],
        "paid_total": 0, "payment_status": "unpaid", "payment_term_code": "NET30", "created_at": NOW,
        "payment_method_code": "transfer", "receiving_account_id": ACC,
        "receiving_account": {"bank_name": "BCA", "account_number": f"9{TAG}", "holder_name": "PT Kain Suka Cita"},
        "payment_code": KODE})
    DB.payment_codes.insert_one({
        "id": f"pyc_pmt3_{TAG}", "code": KODE, "entity_id": "ent_ksc", "order_id": SO, "order_number": f"SO-PMT3-{TAG}",
        "customer_id": CUS, "plan_id": "", "line_id": "", "order_level": True, "percent": 100.0, "amount": 1_500_000.0,
        "due_date": "", "status": "aktif", "created_at": NOW, "updated_at": NOW})
    yield
    DB.bank_statement_lines.delete_many({"bank_account_id": ACC})
    DB.payment_codes.delete_many({"order_id": SO})
    DB.bank_accounts.delete_one({"id": ACC})
    DB.bank_match_rules.delete_many({"bank_account_id": ACC})
    DB.customers.delete_one({"id": CUS})


def test_PMT3_U17_dua_auto_match_bersamaan_satu_tautan(siap):
    h = _login()
    r = requests.post(f"{BASE}/ar-receipts", headers=h, timeout=60, json={
        "customer_id": CUS, "amount": 1_500_000, "method": "transfer", "account_id": ACC, "notes": f"uji PM-T3 {TAG}",
        "allocations": [{"order_id": SO, "amount": 1_500_000}]})
    assert r.status_code == 200, r.text
    rc = r.json()
    try:
        kas = DB.cash_transactions.find_one({"ref_type": "ar_receipt", "ref_id": rc["id"]})
        assert kas["account_id"] == ACC
        r = requests.post(f"{BASE}/bank-reconciliation/import", headers=h, timeout=60, json={
            "bank_account_id": ACC, "lines": [{"stmt_date": NOW[:10], "amount": 1_500_000, "direction": "in",
                                               "description": f"TRSF {KODE} TOKO UJI", "external_id": f"ext_{TAG}"}]})
        assert r.status_code == 200 and r.json()["imported"] == 1, r.text
        ln = DB.bank_statement_lines.find_one({"bank_account_id": ACC, "external_id": f"ext_{TAG}"})
        assert [x["code"] for x in ln.get("pay_code_hits") or []] == [KODE]

        def cocok():
            return requests.post(f"{BASE}/bank-reconciliation/auto-match", headers=h, timeout=120,
                                 json={"bank_account_id": ACC})
        with ThreadPoolExecutor(2) as ex:
            hasil = [f.result() for f in [ex.submit(cocok), ex.submit(cocok)]]
        assert any(x.status_code == 200 for x in hasil), [x.text for x in hasil]
        assert sum(x.json().get("matched", 0) for x in hasil if x.status_code == 200) == 1, [x.text for x in hasil]
        ln = DB.bank_statement_lines.find_one({"id": ln["id"]})
        assert ln["status"] == "matched" and [a["txn_id"] for a in ln["allocations"]] == [kas["id"]]
        kas = DB.cash_transactions.find_one({"id": kas["id"]})
        assert kas["reconciled_amount"] == 1_500_000 and kas["matched_line_ids"] == [ln["id"]]
        rc_db = DB.ar_receipts.find_one({"id": rc["id"]})
        assert rc_db["bank_verified"] is True and rc_db["bank_line_ids"] == [ln["id"]]
    finally:
        line = DB.bank_statement_lines.find_one({"bank_account_id": ACC, "status": "matched"})
        if line:
            requests.post(f"{BASE}/bank-reconciliation/lines/{line['id']}/unmatch", headers=h, json={}, timeout=60)
        requests.post(f"{BASE}/ar-receipts/{rc['id']}/void", headers=h, params={"reason": f"bersih uji PM-T3 {TAG}"},
                      timeout=60)
