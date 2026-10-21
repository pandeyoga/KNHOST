"""Cek UI UAT v3 (2026-10-21) — celah antarmuka yang ditemukan saat menjalankan skenario S1 di browser.

1. SO terverifikasi tetapi masih "Dicadangkan" hilang dari semua antrean Meja Admin Sales → antrean baru
   `terverifikasi_ajukan` (aksi "Ajukan persetujuan"); respons verifikasi membawa status untuk pesan langkah berikutnya.
2. Barang Keluar tidak menunjukkan roll yang harus diambil → `GET /outbound/tasks/{id}/pick-list`.
3. Antrean "Surat Jalan belum diangkut logistik" bernilai 0 & berjudul nomor SO → qty SJ + nama pelanggan + satuan.
4. Antrean meja dipotong 60 baris & `count` ikut terpotong → `count` = total sebenarnya, `shown` = baris terkirim.
Jalankan: cd /app/backend && python -m pytest tests/test_uat_v3_ui_gaps.py -p no:randomly -n 0 -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_f10_cbd_dp_dispatch_gate as base  # noqa: E402

DB = base.DB


@pytest.fixture(scope="module")
def u():
    return {k: base.Api(e) for k, e in (("sales", "sales@kainnusantara.id"), ("sadm", "salesadmin@kainnusantara.id"),
                                       ("mgr", "manager@kainnusantara.id"), ("wh", "warehouse@kainnusantara.id"),
                                       ("whadm", "wh.admin@kainnusantara.id"))}


def _queue(desk, qid):
    return next(q for q in desk["queues"] if q["id"] == qid)


def test_so_terverifikasi_muncul_di_antrean_ajukan_lalu_disetujui(u):
    c, so = u["sales"].call("POST", "/sales-orders", {
        "customer_id": base.CUST, "shipping_address_id": "", "entity_id": base.ENT, "payment_term_code": "NET30",
        "items": [{"product_id": base._product(), "quantity": 12.5, "unit": "yard"}], "confirm_mixed_lot": True,
        "fulfillment_method": "kirim", "qc_request": "none"})
    assert c == 200, so
    c, v = u["sadm"].call("POST", f"/sales-orders/{so['id']}/verify", {"note": "cek UI v3"})
    assert c == 200 and v["status"] == "reserved", v                      # status untuk pesan langkah berikutnya
    c, desk = u["sadm"].call("GET", "/sales-admin/desk")
    row = next(r for r in _queue(desk, "terverifikasi_ajukan")["rows"] if r["ref_id"] == so["id"])   # dulu: tak ada
    assert row["action_kind"] == "submit" and row["action"] == "Ajukan persetujuan", row
    c, b = u["sadm"].call("POST", f"/sales-orders/{so['id']}/submit-for-approval")
    assert c == 200 and b["status"] in ("approved", "waiting_approval"), b
    c, desk = u["sadm"].call("GET", "/sales-admin/desk")
    assert not any(r["ref_id"] == so["id"] for r in _queue(desk, "terverifikasi_ajukan")["rows"])


def test_pick_list_dan_antrean_sj_bernilai_qty_dan_nama_pelanggan(u):
    pid = base._product()
    c, so = u["sales"].call("POST", "/sales-orders", {
        "customer_id": base.CUST, "shipping_address_id": "", "entity_id": base.ENT, "payment_term_code": "NET30",
        "items": [{"product_id": pid, "quantity": 12.5, "unit": "yard"}], "confirm_mixed_lot": True,
        "fulfillment_method": "kirim", "qc_request": "none"})
    assert c == 200, so
    assert u["sadm"].call("POST", f"/sales-orders/{so['id']}/verify", {"note": "cek UI v3"})[0] == 200
    c, b = u["sadm"].call("POST", f"/sales-orders/{so['id']}/submit-for-approval")
    if b.get("status") == "waiting_approval":
        u["mgr"].call("POST", f"/sales-orders/{so['id']}/approve")
    assert u["sadm"].call("POST", f"/sales-orders/{so['id']}/confirm")[0] == 200
    task = DB.wms_tasks.find_one({"order_id": so["id"], "flow_type": "outbound"}, {"_id": 0})
    c, pl = u["wh"].call("GET", f"/outbound/tasks/{task['id']}/pick-list")
    assert c == 200, pl
    assert pl["rolls"] or pl["pending_cuts"], pl                           # dulu: tidak ada sumber daftar ambil
    assert all(not r["picked"] for r in pl["rolls"])
    c, ts = u["wh"].call("GET", "/outbound/tasks")
    assert next(t for t in ts if t["id"] == task["id"])["customer_name"], "nama pelanggan kosong di panel"
    # selesaikan sampai kirim (helper yang sama dengan F-10)
    so2, tasks = base._ready_to_ship(u, "NET30")
    t2 = tasks[0]
    c, pl = u["wh"].call("GET", f"/outbound/tasks/{t2['id']}/pick-list")
    assert pl["rolls"] and all(r["picked"] for r in pl["rolls"]), pl       # sudah di-pick → bertanda
    for c, b in base._dispatch(u, tasks):
        assert c == 200, b
    sj = DB.shipments.find_one({"order_id": so2["id"]}, {"_id": 0, "id": 1, "qty": 1})
    c, desk = u["whadm"].call("GET", "/warehouse-admin/desk")
    row = next(r for r in _queue(desk, "sj_belum_diangkut")["rows"] if r["ref_id"] == sj["id"])
    assert abs(row["value"] - sj["qty"]) < 0.01 and row["unit"] == "yard", row       # dulu: 0
    assert row["title"] == "Toko Kain Sejahtera", row                                  # dulu: nomor SO


def test_antrean_menghitung_total_sebenarnya_walau_baris_dibatasi():
    from services import work_desk_service as wds
    rows = [wds._row(ref_type="x", ref_id=f"r{i}", number=f"N{i}", title="t", value=1.0, age_days=i)
            for i in range(wds.ROW_LIMIT + 25)]
    q = wds._queue("uji", "Uji", "", rows)
    assert q["count"] == wds.ROW_LIMIT + 25 and q["shown"] == wds.ROW_LIMIT == len(q["rows"]), q["count"]
    assert q["total_value"] == wds.ROW_LIMIT + 25 and q["oldest_age_days"] == wds.ROW_LIMIT + 24
