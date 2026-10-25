"""Audit UI tahap 2 (UAT 24 Okt) — G2-08: Riwayat 360° pelanggan.

Jumlah pesanan & nilai seumur hidup (LTV) dulu ikut menghitung SO batal/kedaluwarsa ("1 order · LTV Rp 224.573"
untuk pelanggan yang satu-satunya pesanannya dibatalkan). Kini SO batal/kedaluwarsa tetap tampil di riwayat, tetapi
tidak dihitung di `stats.total_orders`/`stats.lifetime_value`; jumlahnya dilaporkan di `stats.cancelled_orders`.
Uji tingkat layanan (tanpa HTTP), satu event loop bersama.
Jalankan: cd /app/backend && python -m pytest tests/test_audit2_g2_customer360.py -p no:randomly -n 0 -q
"""
import os
import sys
import uuid

import pytest
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import customer_service  # noqa: E402

DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:6]
CUST = f"cust_TEST_G2_{TAG}"
ORDERS = [
    (f"so_TEST_G2_{TAG}_a", "done", 100000.0),
    (f"so_TEST_G2_{TAG}_b", "cancelled", 224573.0),
    (f"so_TEST_G2_{TAG}_c", "expired", 50000.0),
    (f"so_TEST_G2_{TAG}_d", "reserved", 30000.0),
]


@pytest.fixture(scope="module", autouse=True)
def seed():
    DB.customers.insert_one({"id": CUST, "name": f"Uji G2 {TAG}", "entity_id": "ent_ksc", "status": "active",
                             "addresses": [], "credit_limit": 0})
    DB.sales_orders.insert_many([
        {"id": oid, "number": f"KSC/SO-T{TAG}-{i}", "customer_id": CUST, "entity_id": "ent_ksc", "status": st,
         "payment_status": "unpaid", "grand_total": gt, "total_amount": gt, "payments": [],
         "created_at": f"2026-10-2{i}T01:00:00+00:00", "items": []}
        for i, (oid, st, gt) in enumerate(ORDERS)])
    yield
    DB.sales_orders.delete_many({"id": {"$in": [o[0] for o in ORDERS]}})
    DB.customers.delete_many({"id": CUST})


def test_stats_mengecualikan_so_batal_dan_kedaluwarsa():
    data = run(customer_service.customer_360(CUST))
    assert data is not None
    # Riwayat tetap utuh (4 SO, termasuk yang batal) …
    assert len(data["order_history"]) == 4
    stats = data["stats"]
    # … tetapi hitungan & LTV hanya SO hidup (done + reserved).
    assert stats["total_orders"] == 2
    assert stats["lifetime_value"] == pytest.approx(130000.0)
    assert stats["cancelled_orders"] == 2


def test_status_mati_terdefinisi_satu_tempat():
    assert set(customer_service.DEAD_ORDER_STATUSES) == {"cancelled", "expired"}
