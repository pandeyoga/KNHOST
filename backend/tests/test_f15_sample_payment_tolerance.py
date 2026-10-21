"""F-15 (uji pra-UAT 2026-10-21, keputusan owner Q-04) — sample berbayar: toleransi selisih tagihan saat potong.

Reproduksi SOS-00002: sample berbayar disetujui Rp83.250, setelah dipotong 3,1 yd tagihan jadi Rp86.025 tetapi status
persetujuan tidak berubah dan selisihnya tidak tercatat. Kini (toleransi `sales.sample_payment_tolerance_pct`,
bawaan 5 %): selisih ≤ 5 % → nominal disetujui ikut disesuaikan otomatis (tercatat); di atasnya → persetujuan ULANG
Finance/Admin Sample (antrean Meja Admin Sample), kiriman sample ditahan (409) sampai disetujui.
Alur nyata lewat API akun peran (data acuan): Sales → Finance setujui bayar → Admin Sample teruskan → Gudang potong.
Jalankan: cd /app/backend && python -m pytest tests/test_f15_sample_payment_tolerance.py -p no:randomly -n 0 -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_f10_cbd_dp_dispatch_gate as base  # noqa: E402 — Api + koneksi DB

DB = base.DB
ENT, CUST = "ent_ksc", "cust_toko_kain"


@pytest.fixture(scope="module")
def u():
    return {k: base.Api(e) for k, e in (("sales", "sales@kainnusantara.id"), ("fin", "finance@kainnusantara.id"),
                                       ("sadm", "sampleadmin@kainnusantara.id"), ("wh", "warehouse@kainnusantara.id"),
                                       ("whadm", "wh.admin@kainnusantara.id"))}


def _woven_product():
    for g in DB.inventory_rolls.aggregate([
            {"$match": {"owner_entity_id": ENT, "status": "available", "length_remaining": {"$gt": 20},
                        "length_reserved": {"$not": {"$gt": 0}}}},
            {"$group": {"_id": "$product_id", "n": {"$sum": 1}}}, {"$match": {"n": {"$gte": 2}}}, {"$limit": 200}]):
        p = DB.products.find_one({"id": g["_id"], "base_unit": "yard", "is_active": {"$ne": False}}, {"_id": 0, "id": 1})
        if p:
            return p["id"]
    pytest.skip("stok roll woven uji tidak cukup — jalankan restore data acuan")


def _paid_sample_cut(u, requested, actual):
    """Sample berbayar `requested` yd → disetujui Finance → diteruskan Admin Sample → dipotong `actual` yd."""
    pid = _woven_product()
    c, so = u["sales"].call("POST", "/sales-orders", {
        "customer_id": CUST, "shipping_address_id": "", "entity_id": ENT, "order_type": "sample", "sample_billing": "paid",
        "items": [{"product_id": pid, "quantity": requested, "unit": "yard"}], "fulfillment_method": "kirim"})
    assert c == 200, so
    c, b = u["fin"].call("POST", f"/sample-orders/{so['id']}/approve-payment", {"note": "uji F-15"})
    assert c == 200, b
    approved = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert approved["sample_payment_approved_amount"] == approved["grand_total"], approved.get("sample_payment_approved_amount")
    c, b = u["sadm"].call("POST", f"/sample-orders/{so['id']}/confirm")
    assert c == 200, b
    task = DB.wms_tasks.find_one({"order_id": so["id"], "task_subtype": "sample_cut"}, {"_id": 0})
    assert task, "tugas potong sample tidak lahir"
    c, cut = u["wh"].call("POST", f"/outbound/tasks/{task['id']}/cut-sample",
                          {"roll_id": task.get("suggested_roll_id") or "", "actual_length": actual})
    assert c == 200, cut
    return so, approved["grand_total"], task, cut


def _dispatch(u, so, task):
    """Admin Sample terima hasil potong (L06 Admin Cutting) → label anak diverifikasi → loading check → kirim."""
    if not DB.wms_tasks.find_one({"id": task["id"], "cutting_handoff.received_at": {"$exists": True}}, {"_id": 1}):
        c, b = u["sadm"].call("POST", f"/cutting/tasks/{task['id']}/receive", {})
        assert c == 200, b
    kid = DB.wms_tasks.find_one({"id": task["id"]}, {"_id": 0, "roll_id": 1})["roll_id"]
    roll = DB.inventory_rolls.find_one({"id": kid}, {"_id": 0, "roll_no": 1})
    u["wh"].call("POST", f"/inventory/rolls/{kid}/verify-identity", {"scanned_code": roll["roll_no"]})
    u["whadm"].call("POST", f"/outbound/so/{so['id']}/loading-check/override",
                    {"reason": "uji F-15 tanpa perangkat RFID - validasi manual"})
    return u["wh"].call("POST", f"/outbound/tasks/{task['id']}/dispatch")


def test_selisih_dalam_toleransi_disesuaikan_otomatis(u):
    so, before, task, cut = _paid_sample_cut(u, 3.0, 3.1)                    # +3,3 %
    adj = cut["payment_adjustment"]
    assert adj and adj["auto"] and adj["from"] == before and adj["tolerance_pct"] == 5, adj
    o = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert o["grand_total"] > before                                           # tagihan ikut panjang aktual
    assert o["sample_payment_status"] == "approved" and o["sample_payment_approved_amount"] == o["grand_total"], o
    assert len(o["sample_payment_adjustments"]) == 1
    c, b = _dispatch(u, so, task)
    assert c == 200, b                                                         # tidak ditahan


def test_selisih_di_atas_toleransi_perlu_persetujuan_ulang_dan_kiriman_ditahan(u):
    so, before, task, cut = _paid_sample_cut(u, 3.0, 3.5)                    # +16,7 %
    adj = cut["payment_adjustment"]
    assert adj and not adj["auto"] and adj["pct"] > 5, adj
    o = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert o["sample_payment_status"] == "reapproval_required", o["sample_payment_status"]   # dulu: tetap "approved"
    assert any(p["type"] == "pembayaran_sampel" and p["status"] == "pending" for p in o["pending_approvals"])
    c, desk = u["sadm"].call("GET", "/sample-orders/desk")
    q = next(x for x in desk["queues"] if x["id"] == "bayar_sampel")
    row = next(r for r in q["rows"] if r["ref_id"] == so["id"])
    assert row["badge"] == "persetujuan ulang", row
    c, b = _dispatch(u, so, task)
    assert c == 409 and "persetujuan ulang" in b["detail"], b
    c, b = u["sales"].call("POST", f"/sample-orders/{so['id']}/approve-payment", {"note": "sales"})
    assert c == 403, b                                                         # hanya Finance/Admin Sample
    c, b = u["sadm"].call("POST", f"/sample-orders/{so['id']}/approve-payment", {"note": "pelanggan setuju tagihan baru"})
    assert c == 200 and b["sample_payment_status"] == "approved", b
    assert b["sample_payment_approved_amount"] == b["grand_total"] and b["status"] != "approved", b   # status SO tidak mundur
    c, b = _dispatch(u, so, task)
    assert c == 200, b


def test_tautan_dokumen_pesanan_sample_membuka_layar_sample(u):
    """Cek UI F-15 — ?doc=KSC/SOS-… dulu membuka Pesanan Penjualan (tanpa sample) → "Tidak ada pesanan yang cocok"."""
    o = DB.sales_orders.find_one({"entity_id": ENT, "sample_billing": "paid"}, {"_id": 0, "id": 1, "number": 1})
    if not o:
        pytest.skip("belum ada pesanan sample")
    c, r = u["sadm"].call("GET", "/documents/resolve", params={"number": o["number"]})
    assert c == 200 and r["ref_type"] == "sample_order" and r["ref_id"] == o["id"], r
