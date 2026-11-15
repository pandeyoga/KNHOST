"""PM-T4 U16 — di MongoDB ASLI (lingkungan A): dua `receive` BERSAMAAN untuk setoran titipan yang sama.

Persiapan (FIXTURE disisip langsung ke database uji `MONGO_URL`/`DB_NAME`, ditandai `TAG` dan dihapus sesudahnya):
rekening Kas Kecil uji di `ent_ksc` (penerimaan pelanggan, melayani tunai), pelanggan, pesanan bersisa Rp 1.000.000.
ALUR lewat API: pengaturan `pembayaran.sales_terima_tunai = titipan` untuk `ent_ksc` (admin, dicabut di akhir), kwitansi
tunai Rp 100.000 oleh akun seed `sales@` (tanpa `cash.create`) → titipan, setoran Rp 100.000 oleh sales, lalu dua
`POST /api/cash-deposits/{id}/receive` BERSAMAAN oleh admin ke rekening uji.

Harapan (spesifikasi U16): satu 200, satu 409; tepat SATU transaksi kas `ref_type: cash_deposit` dan satu jurnalnya;
titipan `disetor` dengan `deposited_amount` 100.000 (bukan 200.000). Pembersihan: dokumen uji ber-`TAG` dan turunannya
(kwitansi, titipan, setoran, kas, jurnal) dihapus langsung — setoran yang sudah diterima tidak punya jalur batal.
Tidak untuk data nyata.
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
ACC, CUS, SO = f"ba_pmt4_{TAG}", f"cus_pmt4_{TAG}", f"so_pmt4_{TAG}"
KEY = "pembayaran.sales_terima_tunai"


def _login(email):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture()
def siap():
    DB.bank_accounts.insert_one({
        "id": ACC, "name": f"Kas Uji PMT4 {TAG}", "account_type": "cash", "cash_type": "kas_kecil", "bank_name": "",
        "account_number": "", "entity_id": "ent_ksc", "is_active": True, "opening_balance": 0, "holder_name": "",
        "purposes": ["penerimaan_pelanggan"], "payment_method_codes": ["cash"], "default_receiving_methods": [],
        "show_on_documents": False, "created_at": NOW, "updated_at": NOW})
    DB.customers.insert_one({"id": CUS, "name": f"Toko Uji PMT4 {TAG}", "entity_id": "ent_ksc", "status": "active"})
    DB.sales_orders.insert_one({
        "id": SO, "number": f"SO-PMT4-{TAG}", "entity_id": "ent_ksc", "customer_id": CUS,
        "customer_name": f"Toko Uji PMT4 {TAG}", "status": "confirmed", "grand_total": 1_000_000.0, "payments": [],
        "paid_total": 0, "payment_status": "unpaid", "payment_term_code": "NET30", "created_at": NOW,
        "payment_method_code": "", "receiving_account_id": "", "receiving_account": {}})
    admin = _login("admin@kainnusantara.id")
    r = requests.put(f"{BASE}/config/values", headers=admin, timeout=30, json={"items": [{
        "key": KEY, "value": "titipan", "scope_type": "entity", "scope_id": "ent_ksc", "reason": f"uji PM-T4 {TAG}"}]})
    assert r.status_code == 200, r.text
    yield admin
    requests.post(f"{BASE}/config/values/clear", headers=admin, timeout=30, json={
        "key": KEY, "scope_type": "entity", "scope_id": "ent_ksc", "reason": f"bersih uji PM-T4 {TAG}"})
    rcs = [r["id"] for r in DB.ar_receipts.find({"customer_id": CUS}, {"id": 1})]
    hs = [h["id"] for h in DB.cash_holdings.find({"receipt_id": {"$in": rcs}}, {"id": 1})]
    deps = [d["id"] for d in DB.cash_deposits.find({"allocations.holding_id": {"$in": hs}}, {"id": 1})]
    kas = [c["id"] for c in DB.cash_transactions.find({"ref_id": {"$in": deps + rcs}}, {"id": 1})]
    DB.journal_entries.delete_many({"source_id": {"$in": hs + kas}})
    DB.cash_transactions.delete_many({"id": {"$in": kas}})
    DB.cash_deposits.delete_many({"id": {"$in": deps}})
    DB.cash_holdings.delete_many({"id": {"$in": hs}})
    DB.ar_receipts.delete_many({"id": {"$in": rcs}})
    DB.sales_orders.delete_one({"id": SO})
    DB.customers.delete_one({"id": CUS})
    DB.bank_accounts.delete_one({"id": ACC})


def test_PMT4_U16_dua_terima_bersamaan_satu_kas(siap):
    admin = siap
    sales = _login("sales@kainnusantara.id")
    r = requests.post(f"{BASE}/ar-receipts", headers=sales, timeout=60, json={
        "customer_id": CUS, "amount": 100_000, "method": "cash", "notes": f"uji PM-T4 {TAG}",
        "allocations": [{"order_id": SO, "amount": 100_000}]})
    assert r.status_code == 200, r.text
    rc = r.json()
    assert rc.get("cash_holding_id"), rc
    assert DB.cash_transactions.count_documents({"ref_type": "ar_receipt", "ref_id": rc["id"]}) == 0
    r = requests.post(f"{BASE}/cash-deposits", headers=sales, timeout=60, json={"amount": 100_000, "note": TAG})
    assert r.status_code == 200, r.text
    dep = r.json()

    def terima():
        return requests.post(f"{BASE}/cash-deposits/{dep['id']}/receive", headers=admin, timeout=120,
                             json={"account_id": ACC})
    with ThreadPoolExecutor(2) as ex:
        hasil = [f.result() for f in [ex.submit(terima), ex.submit(terima)]]
    assert sorted(x.status_code for x in hasil) == [200, 409], [x.text for x in hasil]
    kas = list(DB.cash_transactions.find({"ref_type": "cash_deposit", "ref_id": dep["id"]}))
    assert len(kas) == 1 and kas[0]["amount"] == 100_000 and kas[0]["account_id"] == ACC
    assert DB.journal_entries.count_documents({"source_type": "cash_transaction", "source_id": kas[0]["id"],
                                               "status": {"$ne": "void"}}) == 1
    h = DB.cash_holdings.find_one({"id": rc["cash_holding_id"]})
    assert (h["status"], h["deposited_amount"], h["deposit_ids"]) == ("disetor", 100_000, [dep["id"]])
    assert DB.cash_deposits.find_one({"id": dep["id"]})["status"] == "diterima"
