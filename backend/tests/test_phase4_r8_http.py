"""Fase 4 · R8 (26 Okt 2026) — uji HTTP (butuh backend yang sudah di-RESTART dengan kode R8).

Data uji ditanam langsung (SO bertanda `so_R8H_<tag>` di PT `ent_ksc`) dan DIHAPUS lagi (SO, override kredit, jejak audit).
* `/approvals/queue` — entri SO mati tidak tampil; SO hidup tetap tampil.
* `/sales-orders/{id}/approvals/{aid}/decide` & `/sales-orders/{id}/approve` pada SO mati → 409 `SO_CLOSED`, data tidak
  berubah (dulu `approve` menandai entri `nilai` disetujui SEBELUM transisi menolak).
* `/sales-orders/{id}/cancel` — entri yang masih menunggu ditutup `cancelled`, override kredit rinciannya ikut
  `cancelled`, `has_backorder` → False; keputusan lama tidak disentuh.
* `/inspections` — `stats.hold` = baris antrean `inspection_hold` di `/approvals/backlog` (PT sama) = total saringan
  "Hanya yang DITAHAN".

Jalankan: cd /app/backend && python -m pytest tests/test_phase4_r8_http.py -p no:randomly -n 0 -q
"""
import os
import uuid

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

fe = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or fe.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
PWD = "demo12345"
TAG = uuid.uuid4().hex[:8]
DEAD = f"so_R8H_{TAG}_dead"
LIVE = f"so_R8H_{TAG}_live"
CRO = f"cro_R8H_{TAG}"
T0 = "2026-10-20T00:00:00+00:00"


def _login(who: str, entity: str = ENT) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "X-Entity-Id": entity})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": f"{who}@kainnusantara.id", "password": PWD}, timeout=60)
    assert r.status_code == 200, f"login {who} gagal: {r.status_code} {r.text[:200]}"
    s.headers.update({"Authorization": f"Bearer {r.json().get('token')}"})
    return s


@pytest.fixture(scope="module")
def adm():
    d = {"entity_id": ENT, "created_at": T0, "updated_at": T0, "customer_name": "Toko Uji R8", "items": [],
         "grand_total": 1000}
    DB.sales_orders.insert_many([
        {**d, "id": DEAD, "number": f"R8H-{TAG}-X", "status": "expired", "stage": "Cancelled",
         "sub_status": ["kedaluwarsa"],
         "pending_approvals": [{"id": "pa_dead", "type": "nilai", "status": "pending", "required_role": "manager"}]},
        {**d, "id": LIVE, "number": f"R8H-{TAG}-L", "status": "waiting_approval", "stage": "Reserved",
         "has_backorder": True, "backorders": [{"product_id": "p1", "backorder_qty": 2, "status": "waiting_stock"}],
         "pending_approvals": [{"id": "pa_k", "type": "kredit", "status": "pending", "required_role": "manager",
                                "ref_id": CRO},
                               {"id": "pa_ok", "type": "nilai", "status": "approved", "required_role": "manager"}]},
    ])
    DB.credit_overrides.insert_one({"id": CRO, "entity_id": ENT, "order_id": LIVE, "status": "pending", "amount": 1000,
                                    "created_at": T0})
    yield _login("admin")
    DB.sales_orders.delete_many({"id": {"$in": [DEAD, LIVE]}})
    DB.credit_overrides.delete_many({"id": CRO})
    DB.audit_logs.delete_many({"entity_id": {"$in": [DEAD, LIVE]}})


def test_antrean_tanpa_so_mati(adm):
    rows = adm.get(f"{BASE_URL}/api/approvals/queue", timeout=60).json()
    ids = {r["order_id"] for r in rows}
    assert DEAD not in ids and LIVE in ids
    assert not [r for r in rows if r.get("order_status") in ("cancelled", "expired", "rejected", "void", "done")]


def test_keputusan_atas_so_mati_409(adm):
    r = adm.post(f"{BASE_URL}/api/sales-orders/{DEAD}/approvals/pa_dead/decide", json={"decision": "approve"}, timeout=60)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "SO_CLOSED" and "kedaluwarsa" in r.json()["detail"]["message"]
    r2 = adm.post(f"{BASE_URL}/api/sales-orders/{DEAD}/approve", timeout=60)
    assert r2.status_code == 409 and r2.json()["detail"]["code"] == "SO_CLOSED", r2.text
    so = DB.sales_orders.find_one({"id": DEAD})
    assert so["status"] == "expired" and so["pending_approvals"][0]["status"] == "pending"   # tidak ada yang tertulis


def test_batal_menutup_entri_dan_penanda(adm):
    r = adm.post(f"{BASE_URL}/api/sales-orders/{LIVE}/cancel", json={"reason": "uji R8 batal HTTP"}, timeout=60)
    assert r.status_code == 200, r.text
    so = DB.sales_orders.find_one({"id": LIVE})
    st = {p["id"]: p["status"] for p in so["pending_approvals"]}
    assert so["status"] == "cancelled" and so["has_backorder"] is False
    assert st == {"pa_k": "cancelled", "pa_ok": "approved"}
    assert DB.credit_overrides.find_one({"id": CRO})["status"] == "cancelled"
    ids = {x["order_id"] for x in adm.get(f"{BASE_URL}/api/approvals/queue", timeout=60).json()}
    assert LIVE not in ids


def test_qc_hub_ditahan_sama_dengan_antrean(adm):
    body = adm.get(f"{BASE_URL}/api/inspections", params={"hold_only": "true", "limit": 500}, timeout=60).json()
    bl = adm.get(f"{BASE_URL}/api/approvals/backlog", params={"entity_id": ENT}, timeout=60).json()
    queue = {x["key"]: x["count"] for x in bl["all_items"]}
    assert body["stats"]["hold"] == queue.get("inspection_hold", 0) == body["total"]
