"""PK-45 U13 — di MongoDB ASLI (lingkungan A): pesanan penjualan tanpa PPN butuh izin `order.tax_override` + alasan.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`) di atas data acuan (`scripts/dev_restore_demo.sh`:
pelanggan `cust_butik_bali` beralamat `addr_001`, barang `prod_lurik_classic`, PT PKP `ent_ksc`). Backend harus sudah
dinyalakan ulang sesudah PK-45 supaya pasangan bawaan baru tersalin ke matriks tersimpan (`sync_permission_modules`).
Database (`MONGO_URL`/`DB_NAME`) hanya dibaca untuk memeriksa hasil; pesanan yang lahir dibatalkan lewat API di akhir.
Tidak untuk database berisi data nyata.
"""
import os

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
ENT, CUST, ADDR, PROD = "ent_ksc", "cust_butik_bali", "addr_001", "prod_lurik_classic"
PESAN_403 = ("Anda belum punya akses untuk membuat pesanan tanpa PPN. "
             "Minta Admin menambahkan akses 'Pesanan Penjualan'.")


def _login(email):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


def _isi(**lain):
    return {"customer_id": CUST, "shipping_address_id": ADDR, "entity_id": ENT,
            "items": [{"product_id": PROD, "quantity": 5, "unit": "yard"}],
            "allow_backorder": True, "confirm_mixed_lot": True, **lain}


@pytest.fixture(scope="module")
def akun():
    if not DB.customers.find_one({"id": CUST}) or not DB.products.find_one({"id": PROD}):
        pytest.skip("data acuan belum dipulihkan (scripts/dev_restore_demo.sh)")
    return {"sls": _login("sales@kainnusantara.id"), "mgr": _login("manager@kainnusantara.id"),
            "adm": _login("admin@kainnusantara.id")}


def test_U13_pesanan_tanpa_ppn_izin_dan_alasan(akun):
    awal = DB.sales_orders.count_documents({})
    r = requests.post(f"{BASE}/sales-orders", headers=akun["sls"], timeout=90,
                      json=_isi(tax_override="non_ppn", tax_override_reason="pelanggan kawasan berikat"))
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == PESAN_403
    r = requests.post(f"{BASE}/sales-orders", headers=akun["mgr"], timeout=90, json=_isi(tax_override="non_ppn"))
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Alasan pesanan tanpa PPN wajib diisi (minimal 10 huruf)."
    r = requests.post(f"{BASE}/sales-orders", headers=akun["mgr"], timeout=90, json=_isi(tax_override="abc"))
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Pilihan pajak pesanan tidak dikenal."
    assert DB.sales_orders.count_documents({}) == awal

    r = requests.post(f"{BASE}/sales-orders", headers=akun["mgr"], timeout=90,
                      json=_isi(tax_override="non_ppn", tax_override_reason="pelanggan kawasan berikat"))
    assert r.status_code == 200, r.text
    so = r.json()
    try:
        assert float(so["ppn_amount"]) == 0
        doc = DB.sales_orders.find_one({"id": so["id"]})
        assert doc["tax_override"] == "non_ppn"
        assert doc["tax_override_reason"] == "pelanggan kawasan berikat"
        jejak = DB.audit_logs.find_one({"action": "order_created", "entity_id": so["id"]})
        assert jejak and jejak["after"].get("tax_override_reason") == "pelanggan kawasan berikat"
    finally:
        requests.post(f"{BASE}/sales-orders/{so['id']}/cancel", headers=akun["adm"], timeout=60,
                      json={"reason": "bersihkan uji PK-45"})
