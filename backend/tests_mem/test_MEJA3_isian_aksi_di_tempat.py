"""MEJA-3 — isian baris untuk pratinjau konfirmasi & pop-up (§5.3, §5.4, §5.6)."""
from __future__ import annotations
import pytest
from core_utils import now_iso

pytestmark = pytest.mark.anyio


def _baris(desk_json, qid, ref_id):
    return next(x for q in desk_json["queues"] if q["id"] == qid for x in q["rows"] if x["ref_id"] == ref_id)


async def test_ditahan_membawa_baris_dan_gudang(klien, db, kepala_admin):
    t = now_iso()
    await db.sales_orders.insert_one({
        "id": "so_m3_hold", "number": "SO-M3H", "status": "approved", "entity_id": "ent_ksc", "customer_name": "Toko H",
        "customer_city": "Bandung", "sales_name": "Ayu", "reservation_expires_at": "2026-11-30T10:00:00+00:00",
        "grand_total": 250000, "created_at": t, "release": {"requested": True, "hold": True, "by": "Admin"},
        "items": [{"product_id": "p1", "product_name": "Kain A", "sku": "KA-1", "quantity": 10, "unit": "yard",
                   "allocations": [{"warehouse_name": "Gudang Woven"}, {"warehouse_name": "Gudang Knit"}]}]})
    row = _baris((await klien.get("/api/sales-admin/desk", headers=kepala_admin)).json(), "siap_dikonfirmasi", "so_m3_hold")
    assert row["order_lines"] == [{"product_name": "Kain A", "sku": "KA-1", "quantity": 10.0, "unit": "yard",
                                   "warehouse": "Gudang Woven, Gudang Knit"}]
    assert (row["sales_name"], row["customer_city"], row["booking_until"]) == ("Ayu", "Bandung", "2026-11-30T10:00:00+00:00")


async def test_baris_pakai_satuan_jual_bukan_satuan_dasar(klien, db, kepala_admin):
    """R6 — satu aturan: `quantity` + `unit` pesanan (sama dengan Faktur Komersial), bukan base_quantity/base_unit."""
    await db.sales_orders.insert_one({
        "id": "so_m3_unit", "number": "SO-M3U", "status": "approved", "entity_id": "ent_ksc", "customer_name": "Toko U",
        "grand_total": 1, "created_at": now_iso(), "release": {"requested": True, "hold": True, "by": "Admin"},
        "items": [{"product_id": "p1", "product_name": "Kain Y", "sku": "KY", "quantity": 10, "unit": "yard",
                   "base_quantity": 9.144, "base_unit": "meter", "warehouse_name": "Gudang Utama"}]})
    row = _baris((await klien.get("/api/sales-admin/desk", headers=kepala_admin)).json(), "siap_dikonfirmasi", "so_m3_unit")
    assert row["order_lines"] == [{"product_name": "Kain Y", "sku": "KY", "quantity": 10.0, "unit": "yard",
                                   "warehouse": "Gudang Utama"}]


async def test_siap_cetak_aksi_print(klien, db, kepala_admin):
    await db.sales_orders.insert_one({"id": "so_m3_cetak", "number": "SO-M3C", "status": "confirmed", "entity_id": "ent_ksc",
                                      "customer_name": "Toko C", "grand_total": 1, "created_at": now_iso(), "items": []})
    row = _baris((await klien.get("/api/sales-admin/desk", headers=kepala_admin)).json(), "siap_cetak_dokumen", "so_m3_cetak")
    assert row["action_kind"] == "print"


async def test_faktur_pajak_membawa_ppn_dpp_npwp(klien, db, kepala_admin):
    await db.customers.insert_one({"id": "cus_m3", "name": "Toko Pajak", "npwp": "01.234.567.8-901.000", "entity_id": "ent_ksc"})
    await db.sales_orders.insert_one({
        "id": "so_m3_pajak", "number": "SO-M3P", "status": "confirmed", "entity_id": "ent_ksc", "customer_id": "cus_m3",
        "customer_name": "Toko Pajak", "is_pkp": True, "ppn_amount": 110000, "dpp": 1000000, "grand_total": 1110000,
        "created_at": now_iso(), "items": []})
    row = _baris((await klien.get("/api/finance/desk", headers=kepala_admin)).json(), "siap_faktur_pajak", "so_m3_pajak")
    assert (row["ppn_amount"], row["dpp"], row["customer_npwp"]) == (110000.0, 1000000.0, "01.234.567.8-901.000")


async def test_qc_pesanan_aksi_spk_di_tempat(klien, db, kepala_admin):
    await db.sales_orders.insert_one({"id": "so_m3_qc", "number": "SO-M3Q", "status": "confirmed", "entity_id": "ent_ksc",
                                      "customer_name": "Toko Q", "qc_request": {"mode": "full", "status": "requested"},
                                      "created_at": now_iso(), "items": []})
    row = _baris((await klien.get("/api/warehouse-admin/desk", headers=kepala_admin)).json(), "qc_pesanan", "so_m3_qc")
    assert row["action_kind"] == "create_qc_spk" and row["link_view"] == "inspections"


async def test_sample_bayar_membawa_uang_masuk(klien, db, kepala_admin):
    t = now_iso()
    await db.sales_orders.insert_one({
        "id": "sos_m3", "number": "KSC/SOS-M3", "order_type": "sample", "status": "waiting_approval", "sample_billing": "paid",
        "grand_total": 83250, "paid_total": 50000, "entity_id": "ent_ksc", "customer_name": "Toko S", "created_at": t,
        "updated_at": t, "items": [{"product_id": "p1", "product_name": "Sample A", "sku": "SA", "quantity": 1, "unit": "meter"}]})
    row = _baris((await klien.get("/api/sample-orders/desk", headers=kepala_admin)).json(), "bayar_sampel", "sos_m3")
    assert (row["sample_billing"], row["grand_total"], row["paid_total"]) == ("paid", 83250.0, 50000.0)
    assert row["order_lines"][0]["product_name"] == "Sample A"
