"""Lanjutan F-09 — keputusan owner 2026-10-21: baris dihapus dari pesanan → entri harga khusus produk itu
(menunggu / ditolak) otomatis DIBATALKAN, riwayat tetap. Dulu: entri menunggu tak bisa disetujui ("produk sudah
tidak ada") dan entri ditolak mengunci SO selamanya karena produknya tak bisa diajukan ulang.
Jalur Override SO (Admin Sales) — proses bisnis lewat API, helper & akun tes F-09.
Jalankan: cd /app/backend && python -m pytest tests/test_f09_baris_dihapus.py -p no:randomly -n 0 -q
"""
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_f09_resubmit_after_reject as f9  # noqa: E402
from test_f09_resubmit_after_reject import H  # noqa: E402,F401 — fixture modul F-09

BASE, DB = f9.BASE, f9.DB


def _remove(h, sid, pid):
    return requests.post(f"{BASE}/sales-orders/{sid}/override", headers=h, timeout=120,
                         json={"note": "TEST_F09 pelanggan tidak jadi produk ini", "lines": [{"product_id": pid, "remove": True}]})


def _entry(sid, eid):
    return next(p for p in DB.sales_orders.find_one({"id": sid})["pending_approvals"] if p["id"] == eid)


def test_hapus_baris_harga_khusus_ditolak_dibatalkan_so_bisa_disetujui(H):  # noqa: F811
    p1, p2 = f9._products(2)
    so = f9._so(H["sales"], [p1, p2])
    _, e = f9._req_price(H["sales"], so["id"], p1, 11111)
    assert f9._submit(H["sadm"], so["id"]).status_code == 200
    f9._decide(H["mgr"], so["id"], e["id"], "reject", "terlalu rendah")
    blocked = f9._approve(H["mgr"], so["id"])
    assert blocked.status_code == 409 and f9._code(blocked) == "APPROVAL_REJECTED"
    r = _remove(H["sadm"], so["id"], p1)
    assert r.status_code == 200, r.text[:300]
    got = _entry(so["id"], e["id"])
    assert got["status"] == "cancelled" and got["previous_status"] == "rejected", got
    assert got["decided_by"] and got["cancel_reason"].startswith("Baris dihapus lewat override SO")   # riwayat tetap
    assert DB.price_approvals.find_one({"id": e["ref_id"]})["status"] == "rejected"                # keputusan lama tetap
    assert any(c["field"] == "special_price_cancelled" for c in r.json()["changes"])
    ok = f9._approve(H["mgr"], so["id"])                                                            # tidak lagi terkunci
    assert ok.status_code == 200, ok.text[:300]


def test_hapus_baris_harga_khusus_menunggu_dokumen_harga_ikut_batal(H):  # noqa: F811
    p1, p2 = f9._products(2)
    so = f9._so(H["sales"], [p1, p2])
    _, e = f9._req_price(H["sales"], so["id"], p1, 11111)
    _, keep = f9._req_price(H["sales"], so["id"], p2, 22222)                 # baris lain tidak tersentuh
    r = _remove(H["sadm"], so["id"], p1)
    assert r.status_code == 200, r.text[:300]
    got = _entry(so["id"], e["id"])
    assert got["status"] == "cancelled" and got["previous_status"] == "pending"
    assert DB.price_approvals.find_one({"id": e["ref_id"]})["status"] == "cancelled"
    assert _entry(so["id"], keep["id"])["status"] == "pending"
    assert DB.price_approvals.find_one({"id": keep["ref_id"]})["status"] == "pending"
    order = DB.sales_orders.find_one({"id": so["id"]})
    assert f9.so_approvals.summarize(order)["pending_count"] == 1   # yang dibatalkan tidak dihitung menunggu
