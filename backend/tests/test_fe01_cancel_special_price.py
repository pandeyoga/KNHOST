"""Lanjutan F-09 × FE-01 — keputusan owner 2026-10-21: item Pesanan Khusus dibatalkan SESUDAH SO terbit → baris SO
keluar dan entri harga khusus produk baris itu (menunggu/ditolak) ikut DIBATALKAN, sehingga SO tidak terkunci.
Proses bisnis lewat API (OD → ACC pelanggan → kunci harga → SO → ajukan harga khusus → tolak → batal item OD).
Memakai helper & fixture tes FE-01 batal item.
Jalankan: cd /app/backend && python -m pytest tests/test_fe01_cancel_special_price.py -p no:randomly -n 0 -q
"""
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_fe01_od_cancel_item as fe  # noqa: E402
from test_fe01_od_cancel_item import H, cleanup_od  # noqa: E402,F401 — fixture modul FE-01

BASE, DB = fe.BASE, fe.DB


def test_batal_item_od_sesudah_so_membatalkan_harga_khusus_baris_itu(H):  # noqa: F811
    od = fe._approved(H, [fe.PA, fe.PB], qtys=(100, 200))
    i1, i2 = od["items"]
    fe._decide(i1, fe.PA, 10)
    fe._decide(i2, fe.PB, 30)
    assert requests.post(f"{BASE}/special-orders/{od['id']}/customer-decision", json={"decision": "acc"},
                         headers=H["admin"]).status_code == 200
    assert requests.post(f"{BASE}/special-orders/{od['id']}/lock-price", json={"margin_pct": 30, "auto_po": False},
                         headers=H["admin"]).status_code == 200
    so = fe._so(H, od["id"])
    req = requests.post(f"{BASE}/sales-orders/{so['id']}/request-special-price", headers=H["admin"],
                        json={"product_id": fe.PB["id"], "requested_price": 1234, "reason": "TEST nego item 2"})
    assert req.status_code == 200, req.text[:300]
    entry = [p for p in req.json()["pending_approvals"] if p["type"] == "special_price"][-1]
    mgr = fe.m._login("manager@kainnusantara.id", "demo12345")
    dec = requests.post(f"{BASE}/sales-orders/{so['id']}/approvals/{entry['id']}/decide", headers=mgr,
                        json={"decision": "reject", "notes": "TEST terlalu rendah"})
    assert dec.status_code == 200, dec.text[:300]
    r = fe._cancel(H, od["id"], i2["id"], reason="Pelanggan batal item 2 sesudah SO")
    assert r.status_code == 200, r.text
    after = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert [i["product_id"] for i in after["items"]] == [fe.PA["id"]]
    got = next(p for p in after["pending_approvals"] if p["id"] == entry["id"])
    assert got["status"] == "cancelled" and got["previous_status"] == "rejected", got
    assert got["cancel_reason"].startswith("Item Pesanan Khusus dibatalkan")
    assert DB.price_approvals.find_one({"id": entry["ref_id"]})["status"] == "rejected"   # riwayat keputusan tetap
    from services import so_approvals
    assert so_approvals.summarize(after)["has_rejected"] is False                       # SO tidak lagi terkunci
