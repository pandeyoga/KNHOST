"""PK-25 U14 — di MongoDB ASLI (lingkungan A): dua penyelesaian kasus keuangan bersamaan.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); fixture disisipkan langsung ke database uji
lokal (`MONGO_URL`/`DB_NAME`). Tidak untuk database berisi data nyata.

Persiapan (fixture): pelanggan uji, pesanan A1 Rp 1.000.000 (terkirim) milik `ent_ksc` dengan baris pembayaran kwitansi
Rp 993.500 (sisa 6.500). Kasus "Nominal kurang karena biaya bank" Rp 6.500 dibuat lewat API.

  U14  dua `POST /api/finance-cases/{id}/resolve` (bebankan biaya bank 6.500) bersamaan → satu 200, satu 409/400;
       A1 berbaris `kasus` tepat satu (6.500); jurnal `finance_case` kasus itu tepat satu
       (Dr 6-8000 6.500 / Cr 1-1200 6.500); kasus `resolved`, niat `done`, tanpa `saga_lock`.
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
KSC = "ent_ksc"


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": KSC}


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture(scope="module")
def h():
    hh = _login()
    # Label alasan kasus dibuat saat daftar alasan pertama kali dibaca (layar penyelesaian memanggilnya sebelum
    # menyimpan); database data acuan yang baru dipulihkan belum punya `amendment_reasons`.
    r = requests.get(f"{BASE}/finance-cases/reasons", headers=hh, timeout=30)
    assert r.status_code == 200, r.text
    return hh


def _dunia(hh):
    tag = uuid.uuid4().hex[:8]
    cus, so, rc = f"cus_bp25_{tag}", f"so_bp25_{tag}", f"rc_bp25_{tag}"
    DB.customers.insert_one({"id": cus, "name": f"Toko BP25 {tag}", "entity_id": KSC, "status": "active",
                             "deposit_balance": 0.0, "created_at": _now()})
    DB.ar_receipts.insert_one({"id": rc, "number": f"KW-BP25-{tag}", "entity_id": KSC, "customer_id": cus,
                               "amount": 993_500.0, "status": "posted", "receipt_date": _now()[:10],
                               "created_at": _now(), "allocations": [{"order_id": so, "amount": 993_500.0}]})
    DB.sales_orders.insert_one({
        "id": so, "number": f"SO-BP25-{tag}", "entity_id": KSC, "customer_id": cus, "customer_name": f"Toko {tag}",
        "status": "shipped", "grand_total": 1_000_000.0, "paid_total": 993_500.0, "payment_status": "partial",
        "payments": [{"id": f"pay_{rc}", "kind": "kas", "amount": 993_500.0, "receipt_id": rc,
                      "receipt_number": f"KW-BP25-{tag}", "method": "transfer", "date": _now(),
                      "created_at": _now()}],
        "payment_term_code": "NET30", "items": [], "created_at": _now()})
    r = requests.post(f"{BASE}/finance-cases", headers=hh, timeout=60, json={
        "case_type": "selisih_biaya_bank", "amount": 6_500, "customer_id": cus, "order_ids": [so],
        "source": {"kind": "ar_receipt", "id": rc, "label": "Kwitansi uji BP25"}})
    assert r.status_code == 200, r.text
    return r.json()["id"], so


def _bersamaan(fn):
    with ThreadPoolExecutor(2) as ex:
        return sorted(ex.map(fn, [0, 1]))


def test_PK25_U14_dua_penyelesaian_bersamaan(h):
    for _ in range(3):   # beberapa putaran: balapan tidak selalu muncul di satu percobaan
        cid, so = _dunia(h)
        body = {"action": "bebankan_biaya_bank", "reason_code": "bank_charge", "order_id": so, "amount": 6_500}
        codes = _bersamaan(lambda _i: requests.post(f"{BASE}/finance-cases/{cid}/resolve", headers=h, json=body,
                                                    timeout=60).status_code)
        assert codes[0] == 200 and codes[1] in (400, 409), codes
        rows = [p for p in DB.sales_orders.find_one({"id": so})["payments"] if p.get("kind") == "kasus"]
        assert [p["amount"] for p in rows] == [6_500]
        jes = list(DB.journal_entries.find({"source_type": "finance_case", "source_id": {"$regex": f"^{cid}:"},
                                            "status": {"$ne": "void"}}))
        assert len(jes) == 1 and jes[0]["total_debit"] == 6_500
        k = DB.finance_cases.find_one({"id": cid})
        assert k["status"] == "resolved" and k["resolution_intent"]["status"] == "done" and "saga_lock" not in k
