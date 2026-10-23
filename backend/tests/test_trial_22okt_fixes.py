"""Perbaikan temuan trial 22 Okt 2026 (`docs/uat/2026-10-21/CATATAN_TEMUAN_TRIAL_22OKT.md`).

E1. Tanggal kirim/ambil dibanding dengan tanggal WIB (dulu UTC): "hari ini" WIB diterima, "kemarin" WIB ditolak.
D1. PR tanpa satuan = satuan dasar produk (dulu "meter" paten).
D2. Hitung fisik GRN: panjang diketik dalam satuan SJ/PO dikonversi ke satuan dasar roll (dulu disimpan mentah).
D3. Harga estimasi PR & harga master PO dikonversi dari per-satuan-dasar ke satuan baris.
D6. Tugas ambil SO berlabel satuan dasar (qty alokasi = satuan dasar; dulu label satuan baris SO).
D7. Tugas potong sample baris lama tanpa base_unit dikonversi ke satuan dasar.
D8. Barang yang bisa diretur berlabel satuan dasar (angkanya panjang roll).

Tes ini sengaja TIDAK meninggalkan data di DB (DB lokal = data acuan UAT): permintaan API dibuat gagal sesudah
validasi yang diuji, dan dokumen uji sementara dihapus di `finally`.
Jalankan: cd /app/backend && python -m pytest tests/test_trial_22okt_fixes.py -p no:randomly -n 0 -q
"""
import asyncio
import os
import sys
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_f10_cbd_dp_dispatch_gate as base  # noqa: E402

DB = base.DB
MASA_LALU = "tidak boleh di masa lalu"
M_PER_YD = 0.9144


@pytest.fixture(scope="module")
def sales():
    return base.Api("sales@kainnusantara.id")


def _so_body(**extra):
    return {"customer_id": base.CUST, "shipping_address_id": "", "entity_id": base.ENT,
            "items": [{"product_id": "prod_tidak_ada_uji_e1", "quantity": 1, "unit": "yard"}], **extra}


def _today_wib():
    from services.analytics_time import now_wib
    return now_wib().date()


def test_e1_tanggal_kirim_hari_ini_wib_diterima_kemarin_ditolak(sales):
    today = _today_wib()
    c, b = sales.call("POST", "/sales-orders", _so_body(fulfillment_method="kirim", delivery_date=today.isoformat()))
    assert MASA_LALU not in str(b), b             # lolos validasi tanggal → gagal di produk (tidak ada SO tersimpan)
    assert c != 200, b
    c, b = sales.call("POST", "/sales-orders",
                      _so_body(fulfillment_method="kirim", delivery_date=(today - timedelta(days=1)).isoformat()))
    assert c == 400 and MASA_LALU in str(b), b


def test_e1_tanggal_ambil_hari_ini_wib_diterima_kemarin_ditolak(sales):
    today = _today_wib()
    c, b = sales.call("POST", "/sales-orders", _so_body(fulfillment_method="ambil", pickup_date=today.isoformat()))
    assert MASA_LALU not in str(b), b
    assert c != 200, b
    c, b = sales.call("POST", "/sales-orders",
                      _so_body(fulfillment_method="ambil", pickup_date=(today - timedelta(days=1)).isoformat()))
    assert c == 400 and MASA_LALU in str(b), b


# ─── D-series (satuan) ──────────────────────────────────────────────────────────────────────────────────────
_LOOP = asyncio.new_event_loop()   # satu loop untuk semua tes layanan: klien Motor global terikat ke loop pertama


def _run(_mods, coro_fn):
    # Klien Motor global terikat ke loop PERTAMA yang memakainya — pakai loop itu bila modul lain sudah mengikatnya.
    from db import db as _db
    lp = _db.client._io_loop
    if lp is None or lp.is_closed():
        lp = _db.client._io_loop = _LOOP
    return lp.run_until_complete(coro_fn())


@pytest.fixture(scope="module")
def yard_product():
    p = DB.products.find_one({"base_unit": "yard", "harga_pokok": {"$gt": 0}, "is_active": {"$ne": False}}, {"_id": 0})
    if not p:
        pytest.skip("produk ber-satuan dasar yard dengan harga pokok tidak ada — restore data acuan")
    return p


def test_d1_d3_pr_tanpa_satuan_pakai_satuan_dasar_dan_harga_dikonversi(yard_product):
    from services import purchase_requisition_service as prs
    p = yard_product

    async def go():
        a, _ = await prs._enrich_items([SimpleNamespace(product_id=p["id"], quantity=10, est_price=0, unit="")])
        b, _ = await prs._enrich_items([SimpleNamespace(product_id=p["id"], quantity=10, est_price=0, unit="meter")])
        return a[0], b[0]
    a, b = _run(["services.purchase_requisition_service"], go)
    assert a["unit"] == "yard" and a["est_price"] == pytest.approx(p["harga_pokok"]) and a["est_price_source"] == "harga_pokok"
    assert b["unit"] == "meter" and b["quantity_base"] == pytest.approx(10 / M_PER_YD, abs=0.01)
    assert b["est_price"] == pytest.approx(p["harga_pokok"] / M_PER_YD, rel=1e-3)   # Rp/yard → Rp/meter


def test_d3_harga_master_di_po_dikonversi_ke_satuan_baris(yard_product):
    from services import pr_sourcing_service as pss
    p = yard_product

    async def go():
        return await pss.resolve_line_sourcing(supplier_id=f"sup_uji_{uuid.uuid4().hex[:6]}", product_id=p["id"],
                                               qty=10, entity_id=base.ENT, est_price=0, unit="meter")
    out = _run(["services.pr_sourcing_service"], go)
    assert out["source"] == "product_master" and out["unit"] == "meter"
    assert out["price"] == pytest.approx(p["harga_pokok"] / M_PER_YD, rel=1e-3)


def test_d2_hitung_grn_panjang_satuan_sj_dikonversi_ke_satuan_dasar(yard_product, monkeypatch):
    from services import receiving_roll_service as rrs
    got = {}

    async def fake_build(task, product, owner, actor, **kw):
        got["length_base"] = kw["length_base"]
        return {"id": "roll_uji"}

    async def fake_attach(task, roll_doc, task_qty, **kw):
        got["task_qty"] = task_qty
        return task
    monkeypatch.setattr(rrs, "build_receiving_roll", fake_build)
    monkeypatch.setattr(rrs, "attach_roll_to_task", fake_attach)
    task = {"id": "wms_uji", "unit": "meter", "product_id": yard_product["id"]}

    async def go():
        await rrs.create_counted_roll(task=task, product=yard_product, owner_entity_id=base.ENT, actor={"name": "Uji"},
                                      length=100, length_unit="meter", lot="L1")
        a = dict(got)
        await rrs.create_counted_roll(task=task, product=yard_product, owner_entity_id=base.ENT, actor={"name": "Uji"},
                                      length=100, length_unit="yard", lot="L1")
        return a, dict(got)
    as_meter, as_yard = _run(["services.receiving_roll_service"], go)
    assert as_meter["length_base"] == pytest.approx(100 / M_PER_YD, abs=0.01)
    assert as_meter["task_qty"] == pytest.approx(100, abs=0.01)
    assert as_yard["length_base"] == pytest.approx(100)
    assert as_yard["task_qty"] == pytest.approx(100 * M_PER_YD, abs=0.01)


def test_d2_hitung_grn_kain_kg_lewat_kolom_kg_diterima(monkeypatch):
    """23 Okt — kain rajut (satuan dasar kg): berat saja (satuan panjang kosong / "kg" dari layar) DITERIMA;
    hanya angka panjang berisi bersatuan kg yang ditolak. Dulu seluruh hitung kain kg ditolak."""
    from fastapi import HTTPException
    from services import receiving_roll_service as rrs
    got = {}

    async def fake_build(task, product, owner, actor, **kw):
        got["weight_kg"] = kw["weight_kg"]
        return {"id": "roll_uji"}

    async def fake_attach(task, roll_doc, task_qty, **kw):
        got["task_qty"] = task_qty
        return task
    monkeypatch.setattr(rrs, "build_receiving_roll", fake_build)
    monkeypatch.setattr(rrs, "attach_roll_to_task", fake_attach)
    prod = {"id": "prod_uji_kg", "base_unit": "kg", "name": "Rajut uji"}
    task = {"id": "wms_uji", "unit": "kg", "product_id": prod["id"]}

    async def go():
        out = []
        for lu in ("", "kg"):
            await rrs.create_counted_roll(task=task, product=prod, owner_entity_id=base.ENT, actor={"name": "Uji"},
                                          weight_kg=25, length_unit=lu, lot="L1")
            out.append(dict(got))
        with pytest.raises(HTTPException) as e:
            await rrs.create_counted_roll(task=task, product=prod, owner_entity_id=base.ENT, actor={"name": "Uji"},
                                          length=25, length_unit="kg", lot="L1")
        return out, e.value
    out, err = _run(["services.receiving_roll_service"], go)
    assert all(o["weight_kg"] == pytest.approx(25) and o["task_qty"] == pytest.approx(25) for o in out)
    assert err.status_code == 400 and "kolom Kg" in err.detail


def test_d6_tugas_ambil_berlabel_satuan_dasar(yard_product):
    from services import fulfillment_status as fs
    tag = uuid.uuid4().hex[:6]
    so_id = f"so_uji_d6_{tag}"
    DB.sales_orders.insert_one({"id": so_id, "number": f"UJI/SO-D6-{tag}", "entity_id": base.ENT, "status": "confirmed",
                                "items": [{"product_id": yard_product["id"], "unit": "meter", "quantity": 100}],
                                "allocations": [{"id": f"al_{tag}", "product_id": yard_product["id"],
                                                 "warehouse_id": "wh_jakarta", "quantity": 109.36}]})
    try:
        tasks = _run(["services.fulfillment_status"], lambda: fs.create_outbound_tasks_for_order(so_id, "Uji"))
        assert [(t["quantity"], t["unit"]) for t in tasks] == [(109.36, "yard")]   # dulu (109.36, "meter")
    finally:
        DB.sales_orders.delete_one({"id": so_id})
        DB.wms_tasks.delete_many({"order_id": so_id})


def test_d7_tugas_potong_sample_baris_lama_dikonversi(yard_product):
    from services import sample_sale_service as smp
    tag = uuid.uuid4().hex[:6]
    order = {"id": f"so_uji_d7_{tag}", "number": f"UJI/SOS-D7-{tag}", "entity_id": base.ENT,
             "items": [{"product_id": yard_product["id"], "is_sample": True, "unit": "meter", "quantity": 1,
                        "suggested_warehouse_id": "wh_jakarta"}]}
    try:
        tasks = _run(["services.sample_sale_service"], lambda: smp.create_sample_cut_tasks(
            order, "Uji", "created", ["created"], {}, "kirim", ""))
        assert [(t["unit"], t["quantity"]) for t in tasks] == [("yard", round(1 / M_PER_YD, 2))]
    finally:
        DB.wms_tasks.delete_many({"order_id": order["id"]})


def test_d8_barang_retur_berlabel_satuan_dasar(yard_product):
    from services import return_rolls_service as rrs
    tag = uuid.uuid4().hex[:6]
    order_id = f"so_uji_d8_{tag}"
    DB.shipments.insert_one({"id": f"shp_uji_{tag}", "order_id": order_id, "product_id": yard_product["id"],
                             "status": "dispatched", "unit": "meter", "shipment_no": f"UJI-SJ-{tag}",
                             "rolls": [{"roll_id": f"roll_uji_{tag}", "length": 10.94}]})
    try:
        out = _run(["services.return_rolls_service"], lambda: rrs.returnable(order_id))
        assert [(p["unit"], p["shipped_qty"]) for p in out["products"]] == [("yard", 10.94)]
    finally:
        DB.shipments.delete_one({"id": f"shp_uji_{tag}"})


# ─── E4 — status SO memperhitungkan sisa backorder ─────────────────────────────────────────────────────────
def test_e4_so_dengan_sisa_backorder_tidak_dikirim_penuh():
    from services import fulfillment_status as fs
    tag = uuid.uuid4().hex[:6]
    so_id = f"so_uji_e4_{tag}"
    DB.sales_orders.insert_one({"id": so_id, "number": f"UJI/SO-E4-{tag}", "entity_id": base.ENT, "status": "confirmed",
                                "items": [{"product_id": f"p_{tag}", "unit": "yard", "quantity": 1000}],
                                "backorders": [{"id": f"bo_{tag}", "product_id": f"p_{tag}", "backorder_qty": 200,
                                                "status": "waiting_stock"},
                                               {"id": f"bo2_{tag}", "product_id": f"p_{tag}", "backorder_qty": 0,
                                                "status": "fulfilled"}],
                                "has_backorder": True})
    DB.wms_tasks.insert_one({"id": f"wms_e4_{tag}", "order_id": so_id, "flow_type": "outbound", "product_id": f"p_{tag}",
                             "quantity": 800, "picked_qty": 800, "shipped_qty": 800, "status": "dispatched"})
    try:
        assert _run([], lambda: fs.recompute_so_status(so_id)) == "partially_shipped"      # dulu "shipped" 800/800
        so = DB.sales_orders.find_one({"id": so_id})
        assert so["fulfillment"] == {"total_qty": 1000, "picked_qty": 800, "shipped_qty": 800, "backorder_qty": 200,
                                     "remaining_qty": 200}
        assert so["sub_status"] == ["sebagian_dikirim", "menunggu_stok"]
        DB.sales_orders.update_one({"id": so_id}, {"$set": {"backorders.0.backorder_qty": 0, "backorders.0.status": "fulfilled",
                                                            "has_backorder": False}})
        assert _run([], lambda: fs.recompute_so_status(so_id)) == "shipped"
    finally:
        DB.sales_orders.delete_one({"id": so_id})
        DB.wms_tasks.delete_many({"order_id": so_id})


def test_e10_cetak_so_harga_khusus_belum_final_bercap():
    from services import pdf_resolvers as pr
    base_doc = {"number": "UJI/SO", "items": [{"product_name": "Batik", "quantity": 5, "unit": "yard", "price": 1000}],
                "grand_total": 5000}
    menunggu = {**base_doc, "pending_approvals": [{"type": "special_price", "status": "pending"}]}
    beres = {**base_doc, "pending_approvals": [{"type": "special_price", "status": "approved"}]}
    assert _run([], lambda: pr.resolve_sales_order(menunggu, None))["watermark"] == "HARGA BELUM FINAL"
    assert _run([], lambda: pr.resolve_sales_order(beres, None))["watermark"] is None


# ─── Audit pola Lurik di retur & pesanan khusus (22 Okt malam) ────────────────────────────────────────────────
# Pola: angka dalam satuan dasar (yard) dikali/diberi label satuan dokumen (meter) tanpa konversi, atau sebaliknya.
def test_audit_estimasi_nilai_retur_per_satuan_dasar(yard_product):
    """Detail retur: estimasi & saran nominal diskon Finance = harga transaksi PER SATUAN DASAR (dulu harga per meter
    dikali qty yard)."""
    admin = base.Api("admin@kainnusantara.id")
    tag = uuid.uuid4().hex[:6]
    so_id, ret_id = f"so_uji_aud_{tag}", f"sret_uji_aud_{tag}"
    DB.sales_orders.insert_one({"id": so_id, "number": f"UJI/SO-{tag}", "entity_id": base.ENT, "status": "done",
                                "items": [{"product_id": yard_product["id"], "quantity": 100, "unit": "meter",
                                           "base_quantity": round(100 / M_PER_YD, 2), "price": 10000, "line_total": 1000000}]})
    DB.sales_returns.insert_one({"id": ret_id, "number": f"UJI/SRET-{tag}", "entity_id": base.ENT, "order_id": so_id,
                                 "status": "pending", "customer_id": base.CUST,
                                 "items": [{"product_id": yard_product["id"], "quantity_returned": 10, "unit": "yard"}]})
    try:
        c, b = admin.call("GET", f"/sales-returns/{ret_id}")
        assert c == 200, b
        it = b["items"][0]
        assert it["unit_price_est"] == pytest.approx(10000 * M_PER_YD, rel=1e-3)   # Rp/meter → Rp/yard
        assert it["line_total_est"] == pytest.approx(10 * 10000 * M_PER_YD, rel=1e-3)
    finally:
        DB.sales_returns.delete_one({"id": ret_id})
        DB.sales_orders.delete_one({"id": so_id})


def test_audit_harga_po_retur_pembelian_per_satuan_dasar(yard_product):
    from services import purchase_return_service as prs
    p = yard_product
    po_jejak = {"items": [{"product_id": p["id"], "quantity": 1000, "unit": "meter", "price": 95000,
                           "quantity_base": round(1000 / M_PER_YD, 2)}]}
    po_lama = {"items": [{"product_id": p["id"], "quantity": 1000, "unit": "meter", "price": 95000}]}
    a = _run([], lambda: prs._po_item_price(po_jejak, p))
    b = _run([], lambda: prs._po_item_price(po_lama, p))
    assert a == pytest.approx(95000 * M_PER_YD, rel=1e-3) and b == pytest.approx(95000 * M_PER_YD, rel=1e-3)


def test_audit_harga_kontrak_od_ke_satuan_baris(yard_product):
    """Harga kontrak pemenang (per satuan dasar yard) → per meter untuk PR/PO item OD bersatuan meter."""
    from services import special_order_fulfillment as ful
    n = {"cost_price": 86868, "product_id": yard_product["id"]}
    assert _run([], lambda: ful._cost_in_unit(n, "meter")) == pytest.approx(86868 / M_PER_YD, rel=1e-3)
    assert _run([], lambda: ful._cost_in_unit(n, "yard")) == 86868


def test_f5_qc_retur_grade_wajib_diisi_petugas(yard_product):
    """Keputusan pemilik F5 — QC retur tidak lagi mengisi grade otomatis dari poin; tanpa grade ditolak sebelum ditulis."""
    from services import return_service as rs
    tag = uuid.uuid4().hex[:6]
    ret_id = f"sret_uji_f5_{tag}"
    DB.sales_returns.insert_one({"id": ret_id, "number": f"UJI/SRET-{tag}", "entity_id": base.ENT, "order_id": "",
                                 "status": "inspecting", "goods_arrived_at": "2026-10-22T10:00:00+00:00",
                                 "items": [{"product_id": yard_product["id"], "product_name": "Kain uji", "quantity_returned": 5,
                                            "unit": "yard"}]})
    try:
        with pytest.raises(ValueError, match="Pilih grade"):
            _run([], lambda: rs.complete_inspection(ret_id, "uji", inspections=[
                {"index": 0, "defects": [{"point_value": 2, "count": 1}], "condition": "ok"}]))
        assert DB.sales_returns.find_one({"id": ret_id})["status"] == "inspecting"
    finally:
        DB.sales_returns.delete_one({"id": ret_id})


# ─── Audit dual name (22 Okt malam) ──────────────────────────────────────────────────────────────────────────
def test_dn2_kolom_asal_sama_dengan_nama_kn_bukan_versi_supplier():
    from services.supplier_item_service import supplier_alias
    kn = {"name": "ALICE KNIT (94139 - 45) 10 A", "color": "10", "source_name": "ALICE KNIT (94139 - 45)", "source_color": "10",
          "supplier_codes": []}
    assert supplier_alias(kn) == {"name": "", "color": "", "supplier_name": ""}          # dulu: nama KN tampil sebagai "SUP"
    beda = {**kn, "source_name": "Cotton Jersey 30s Combed", "source_color": "Merah Cabe"}
    assert supplier_alias(beda)["name"] == "Cotton Jersey 30s Combed" and supplier_alias(beda)["color"] == "Merah Cabe"
    sup = {**kn, "supplier_codes": [{"supplier_item_name": "Twill Cotton 40s Combed", "supplier_color": "Dark Navy",
                                     "supplier_name": "PT Kain Jadi Nusantara"}]}
    assert supplier_alias(sup) == {"name": "Twill Cotton 40s Combed", "color": "Dark Navy", "supplier_name": "PT Kain Jadi Nusantara"}
