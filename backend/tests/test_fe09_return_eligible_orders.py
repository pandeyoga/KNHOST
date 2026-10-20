"""FE-09 (review 2026-10-20) — pemilih SO retur: pencarian & paginasi SERVER atas SO yang masih punya
barang terkirim (Surat Jalan) belum habis diklaim retur aktif.

Fixture sementara (dibersihkan): 201 SO draf yang lebih baru (seperti reproduksi reviewer) dan satu retur
draf yang mengklaim habis barang terkirim sebuah SO. SO terkirim memakai data acuan.
Jalankan: cd /app/backend && python -m pytest tests/test_fe09_return_eligible_orders.py -p no:randomly -n 0 -q
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
TAG = uuid.uuid4().hex[:6]


def _login(email, pw="demo1234"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


@pytest.fixture(scope="module")
def H():
    return {"admin": _login("admin@kainnusantara.id", "demo12345"), "finance": _login("finance@kainnusantara.id")}


def _shipped_open(H):
    """SO KSC yang punya Surat Jalan dan sisa barang terkirim > 0 (data acuan)."""
    for oid in DB.shipments.distinct("order_id", {"status": {"$ne": "cancelled"}}):
        so = DB.sales_orders.find_one({"id": oid, "entity_id": ENT}, {"_id": 0, "id": 1, "number": 1})
        if not so:
            continue
        rt = requests.get(f"{BASE}/sales-returns/returnable", params={"order_id": oid}, headers=H["admin"]).json()
        if any(p["remaining"] > 0.01 for p in rt.get("products") or []):
            return so, rt
    pytest.skip("data acuan tidak punya SO terkirim dengan sisa barang untuk diretur")


@pytest.fixture(scope="module")
def flood():
    base = datetime.now(timezone.utc)
    cust = DB.customers.find_one({"entity_id": {"$in": [ENT, "all"]}}, {"_id": 0, "id": 1, "name": 1})
    docs = [{"id": f"so_TEST_FE09_{TAG}_{i}", "number": f"TEST-FE09-{TAG}-{i:03d}", "status": "draft", "entity_id": ENT,
             "customer_id": cust["id"], "customer_name": cust["name"], "items": [], "order_type": "regular",
             "created_at": (base + timedelta(seconds=i + 1)).isoformat()} for i in range(201)]
    DB.sales_orders.insert_many(docs)
    yield
    DB.sales_orders.delete_many({"id": {"$regex": f"^so_TEST_FE09_{TAG}_"}})


def test_so_terkirim_tetap_ditemukan_walau_ada_lebih_dari_200_pesanan_baru(H, flood):
    so, _ = _shipped_open(H)
    legacy = requests.get(f"{BASE}/sales-orders", headers=H["admin"]).json()
    assert len(legacy) == 200 and so["id"] not in {o["id"] for o in legacy}    # sumber lama: SO terkirim tersingkir
    r = requests.get(f"{BASE}/sales-returns/eligible-orders", params={"q": so["number"], "page": 1, "page_size": 20},
                     headers=H["admin"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert so["id"] in [o["id"] for o in body["items"]] and body["items"][0]["returnable_qty"] > 0
    # draf (belum ada barang terkirim) tidak pernah menjadi pilihan retur
    drafts = requests.get(f"{BASE}/sales-returns/eligible-orders", params={"q": f"TEST-FE09-{TAG}", "page": 1},
                          headers=H["admin"]).json()
    assert drafts["total"] == 0


def test_paginasi_dan_pencarian_pelanggan(H):
    first = requests.get(f"{BASE}/sales-returns/eligible-orders", params={"page": 1, "page_size": 2}, headers=H["admin"]).json()
    assert first["page_size"] == 2 and len(first["items"]) <= 2 and first["total"] >= len(first["items"])
    if first["total"] > 2:
        assert first["has_more"] is True
        second = requests.get(f"{BASE}/sales-returns/eligible-orders", params={"page": 2, "page_size": 2},
                              headers=H["admin"]).json()
        assert not ({o["id"] for o in first["items"]} & {o["id"] for o in second["items"]})
    so, _ = _shipped_open(H)
    cust = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0, "customer_name": 1})["customer_name"]
    by_cust = requests.get(f"{BASE}/sales-returns/eligible-orders", params={"q": cust[:6], "page": 1, "page_size": 50},
                           headers=H["admin"]).json()
    assert so["id"] in [o["id"] for o in by_cust["items"]]


def test_so_yang_sudah_habis_diklaim_retur_tidak_ditawarkan(H):
    so, rt = _shipped_open(H)
    rid = f"sret_TEST_FE09_{TAG}"
    DB.sales_returns.insert_one({"id": rid, "number": f"TEST-RET-{TAG}", "order_id": so["id"], "status": "draft",
                                 "entity_id": ENT, "created_at": datetime.now(timezone.utc).isoformat(),
                                 "items": [{"product_id": p["product_id"], "quantity_returned": p["shipped_qty"]}
                                           for p in rt["products"]]})
    try:
        r = requests.get(f"{BASE}/sales-returns/eligible-orders", params={"q": so["number"], "page": 1}, headers=H["admin"]).json()
        assert so["id"] not in [o["id"] for o in r["items"]]
    finally:
        DB.sales_returns.delete_one({"id": rid})
    r = requests.get(f"{BASE}/sales-returns/eligible-orders", params={"q": so["number"], "page": 1}, headers=H["admin"]).json()
    assert so["id"] in [o["id"] for o in r["items"]]                 # klaim dilepas → tersedia lagi


def test_izin_sama_dengan_membuat_retur(H):
    assert requests.get(f"{BASE}/sales-returns/eligible-orders", params={"page": 1}, headers=H["finance"]).status_code == 403
