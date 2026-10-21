"""F-09 (uji pra-UAT 2026-10-21) — entri persetujuan yang DITOLAK tidak boleh mengunci SO selamanya.

Alur harian: Sales minta harga khusus → Manajer TOLAK → Sales ajukan ulang → Manajer SETUJUI →
pesanan harus naik ke Approved. Dulu entri yang ditolak tetap dihitung `has_rejected`, jadi
`POST /sales-orders/{id}/approve` selalu 409 APPROVAL_REJECTED (bukti: KSC/SO-00039, SO-00083).
Sama untuk permintaan kredit. Penolakan TANPA pengajuan ulang tetap memblokir (regresi KN-D02).

Akun peran sesuai UAT: sales@ (ajukan), salesadmin@ (ajukan persetujuan), manager@ (putuskan).
"""
import os
import sys
from pathlib import Path

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import so_approvals  # noqa: E402

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ENT = "ent_ksc"
CUST = "cust_toko_kain"
CREATED = []


def _products(n):
    rows = list(DB.inventory_rolls.aggregate([
        {"$match": {"status": "available", "owner_entity_id": ENT, "unit": "yard"}},
        {"$group": {"_id": "$product_id", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": n}]))
    if len(rows) < n:
        pytest.skip("stok roll yard ent_ksc tidak cukup untuk uji F-09")
    return [r["_id"] for r in rows]


def _login(email):
    # F-01 (digabung bersama) — satu sandi untuk semua akun seed
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login gagal {email}: {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


@pytest.fixture(scope="module")
def H():
    hs = {k: _login(v) for k, v in (("admin", "admin@kainnusantara.id"), ("sales", "sales@kainnusantara.id"),
                                     ("sadm", "salesadmin@kainnusantara.id"), ("mgr", "manager@kainnusantara.id"))}
    yield hs
    for sid in CREATED:
        requests.post(f"{BASE}/sales-orders/{sid}/cancel", headers=hs["admin"], json={"reason": "TEST_F09 cleanup"})
    DB.price_approvals.delete_many({"so_id": {"$in": CREATED}})
    DB.credit_overrides.delete_many({"order_id": {"$in": CREATED}})
    DB.inventory_rolls.update_many({"reserved_for_order": {"$in": CREATED}},
                                   {"$set": {"status": "available", "reserved_for_order": None, "length_reserved": 0}})
    DB.sales_orders.delete_many({"id": {"$in": CREATED}})


def _so(h, pids):
    r = requests.post(f"{BASE}/sales-orders", headers=h, timeout=120, json={
        "customer_id": CUST, "shipping_address_id": "", "entity_id": ENT, "notes": "TEST_F09",
        "payment_term_code": "NET30", "confirm_mixed_lot": True, "allow_backorder": True,
        "items": [{"product_id": p, "quantity": 10, "unit": "yard"} for p in pids]})
    assert r.status_code in (200, 201), r.text[:400]
    CREATED.append(r.json()["id"])
    return r.json()


def _entries(so, atype):
    return [p for p in so["pending_approvals"] if p["type"] == atype]


def _req_price(h, sid, pid, price):
    r = requests.post(f"{BASE}/sales-orders/{sid}/request-special-price", headers=h, timeout=60,
                      json={"product_id": pid, "requested_price": price, "reason": "TEST_F09 nego"})
    assert r.status_code == 200, r.text[:300]
    return r.json(), _entries(r.json(), "special_price")[-1]


def _req_credit(h, sid):
    r = requests.post(f"{BASE}/sales-orders/{sid}/request-credit-approval", headers=h, timeout=60,
                      json={"reason": "TEST_F09 over-limit"})
    assert r.status_code == 200, r.text[:300]
    return r.json(), _entries(r.json(), "kredit")[-1]


def _decide(h, sid, aid, decision, notes=""):
    r = requests.post(f"{BASE}/sales-orders/{sid}/approvals/{aid}/decide", headers=h, timeout=60,
                      json={"decision": decision, "notes": notes or f"TEST_F09 {decision}"})
    assert r.status_code == 200, r.text[:300]
    return r.json()


def _submit(h, sid):
    return requests.post(f"{BASE}/sales-orders/{sid}/submit-for-approval", headers=h, timeout=60)


def _approve(h, sid):
    return requests.post(f"{BASE}/sales-orders/{sid}/approve", headers=h, json={}, timeout=60)


def _code(r):
    d = r.json().get("detail")
    return d.get("code") if isinstance(d, dict) else None


def test_harga_khusus_ditolak_diajukan_ulang_disetujui_so_approved(H):
    [p] = _products(1)
    so = _so(H["sales"], [p])
    _, first = _req_price(H["sales"], so["id"], p, 11111)
    sub = _submit(H["sadm"], so["id"])
    assert sub.status_code == 200 and sub.json()["status"] == "waiting_approval", sub.text[:300]
    _decide(H["mgr"], so["id"], first["id"], "reject", "terlalu rendah")
    blocked = _approve(H["mgr"], so["id"])
    assert blocked.status_code == 409 and _code(blocked) == "APPROVAL_REJECTED", blocked.text[:300]

    after_resubmit, second = _req_price(H["sales"], so["id"], p, 12222)
    old = next(e for e in after_resubmit["pending_approvals"] if e["id"] == first["id"])
    assert old["status"] == "superseded" and old["superseded_by"] == second["id"], old
    # Riwayat keputusan lama tetap utuh.
    assert old["decided_by"] and old["decision_notes"] == "terlalu rendah" and old["previous_status"] == "rejected"
    assert DB.price_approvals.find_one({"id": first["ref_id"]})["status"] == "rejected"

    done = _decide(H["mgr"], so["id"], second["id"], "approve")
    assert done["status"] == "approved", (done["status"], done["pending_approvals"])
    item = next(i for i in done["items"] if i["product_id"] == p)
    assert item["price"] == 12222 and item["special_price_id"] == second["ref_id"]
    again = _approve(H["mgr"], so["id"])
    assert again.status_code == 200 and again.json()["status"] == "approved", again.text[:300]


def test_tolak_tanpa_ajukan_ulang_tetap_memblokir(H):
    """KN-D02 — penolakan yang belum diajukan ulang tetap memblokir, termasuk saat produk LAIN
    di pesanan yang sama diajukan & disetujui (pengganti harus produk yang sama)."""
    p1, p2 = _products(2)
    so = _so(H["sales"], [p1, p2])
    _, e1 = _req_price(H["sales"], so["id"], p1, 11111)
    _decide(H["mgr"], so["id"], e1["id"], "reject")
    _, e2 = _req_price(H["sales"], so["id"], p2, 12222)
    done = _decide(H["mgr"], so["id"], e2["id"], "approve")
    assert done["status"] != "approved", done["status"]
    assert next(e for e in done["pending_approvals"] if e["id"] == e1["id"])["status"] == "rejected"
    blocked = _approve(H["mgr"], so["id"])
    assert blocked.status_code == 409 and _code(blocked) == "APPROVAL_REJECTED", blocked.text[:300]


def test_kredit_ditolak_diajukan_ulang_disetujui_so_approved(H):
    [p] = _products(1)
    so = _so(H["sales"], [p])
    _, k1 = _req_credit(H["sales"], so["id"])
    assert _submit(H["sadm"], so["id"]).status_code == 200
    _decide(H["mgr"], so["id"], k1["id"], "reject", "limit penuh")
    blocked = _approve(H["mgr"], so["id"])
    assert blocked.status_code == 409 and _code(blocked) == "APPROVAL_REJECTED", blocked.text[:300]

    after_resubmit, k2 = _req_credit(H["sales"], so["id"])
    old = next(e for e in after_resubmit["pending_approvals"] if e["id"] == k1["id"])
    assert old["status"] == "superseded" and old["superseded_by"] == k2["id"], old
    assert old["decision_notes"] == "limit penuh" and old["previous_status"] == "rejected"
    assert DB.credit_overrides.find_one({"id": k1["ref_id"]})["status"] == "rejected"

    done = _decide(H["mgr"], so["id"], k2["id"], "approve")
    assert done["status"] == "approved" and done["credit_hold"] is False, (done["status"], done["pending_approvals"])


def test_submit_saat_menunggu_persetujuan_diarahkan_ke_pusat_persetujuan(H):
    [p] = _products(1)
    so = _so(H["sales"], [p])
    _req_price(H["sales"], so["id"], p, 11111)
    assert _submit(H["sadm"], so["id"]).status_code == 200
    before = DB.sales_orders.find_one({"id": so["id"]})["pending_approvals"]
    again = _submit(H["sadm"], so["id"])
    assert again.status_code == 409 and _code(again) == "ALREADY_WAITING_APPROVAL", again.text[:300]
    assert "Pusat Persetujuan" in again.json()["detail"]["message"]
    # Tidak ada efek samping: entri persetujuan tidak bertambah.
    assert DB.sales_orders.find_one({"id": so["id"]})["pending_approvals"] == before


def test_perbaikan_data_lama_menggantikan_penolakan_yang_sudah_diajukan_ulang():
    """SO yang terlanjur terkunci sebelum perbaikan (pola SO-00039): entri ditolak lalu entri
    baru untuk tipe+produk yang sama → ditandai superseded oleh entri sesudahnya."""
    pa = [
        {"id": "a1", "type": "special_price", "product_id": "P1", "status": "rejected"},
        {"id": "a2", "type": "special_price", "product_id": "P2", "status": "rejected"},
        {"id": "a3", "type": "special_price", "product_id": "P1", "status": "rejected"},
        {"id": "a4", "type": "special_price", "product_id": "P1", "status": "approved"},
        {"id": "k1", "type": "kredit", "status": "rejected"},
        {"id": "k2", "type": "kredit", "status": "approved"},
    ]
    assert so_approvals.repair_resubmitted_rejections(pa) == 3
    st = {p["id"]: (p["status"], p.get("superseded_by")) for p in pa}
    assert st["a1"] == ("superseded", "a3") and st["a3"] == ("superseded", "a4")
    assert st["a2"] == ("rejected", None)          # P2 belum diajukan ulang → tetap memblokir
    assert st["k1"] == ("superseded", "k2")
    assert so_approvals.summarize({"pending_approvals": pa})["has_rejected"] is True
    assert so_approvals.repair_resubmitted_rejections(pa) == 0   # idempoten
