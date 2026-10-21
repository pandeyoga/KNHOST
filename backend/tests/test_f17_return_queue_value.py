"""F-17 (uji pra-UAT 2026-10-21) — antrean retur bernilai Rp0.

Reproduksi: Meja Admin Sales "Retur menunggu proses dokumen" dan Meja Manajer "Retur menunggu ACC" menampilkan nilai
Rp0 — dokumen retur tidak menyimpan nilai (`total_refund`/`total_amount` tidak pernah diisi). Kini nilai = Σ qty klaim
× harga transaksi baris SO produk itu (`work_desk_service.return_claim_values`).
Jalankan: cd /app/backend && python -m pytest tests/test_f17_return_queue_value.py -p no:randomly -n 0 -q
"""
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_f11_layar_return_screen_access as fl  # noqa: E402 — pembuat retur (data acuan SO-00001)

DB = fl.DB


@pytest.fixture(scope="module")
def hs():
    return {k: fl._login(v) for k, v in (("sales", "sales@kainnusantara.id"), ("mgr", "manager@kainnusantara.id"),
                                       ("sadm", "salesadmin@kainnusantara.id"), ("adm", "admin@kainnusantara.id"))}


def _new_return(hs, qty=2):
    data = requests.get(f"{fl.BASE}/sales-returns/returnable", headers=hs["adm"], params={"order_id": fl.SO["id"]}).json()
    rolls = sorted((x for x in data["rolls"] if x["remaining"] >= qty), key=lambda x: x["roll_no"])
    if not rolls:
        pytest.skip("tidak ada roll SO-00001 yang masih bisa diretur — jalankan restore data acuan")
    roll = rolls[0]
    rid = fl._create(hs, roll, qty=qty, approve=False)
    price = next(float(i["price"]) for i in fl.SO["items"] if i["product_id"] == roll["product_id"])
    return rid, round(qty * price, 2)


def _row(resp, queue_id, rid):
    q = next(x for x in resp["queues"] if x["id"] == queue_id)
    return next(r for r in q["rows"] if r["ref_id"] == rid)


def test_nilai_retur_di_meja_admin_sales_dan_manajer(hs):
    rid, expect = _new_return(hs)
    assert expect > 0
    st = DB.sales_returns.find_one({"id": rid}, {"_id": 0, "status": 1})["status"]
    r = requests.get(f"{fl.BASE}/sales-admin/desk", headers=hs["sadm"])
    assert r.status_code == 200, r.text
    if st in ("pending_approval", "approved", "pending_process", "quarantine"):
        assert abs(_row(r.json(), "retur", rid)["value"] - expect) < 0.01         # dulu 0
    if st == "pending_approval":
        r = requests.get(f"{fl.BASE}/desks/me", headers=hs["mgr"])
        assert r.status_code == 200, r.text
        assert abs(_row(r.json(), "retur_acc", rid)["value"] - expect) < 0.01     # dulu 0
