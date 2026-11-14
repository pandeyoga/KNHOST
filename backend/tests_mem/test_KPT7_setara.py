"""KP-T7 U5 — setara: penerima bawaan pengingat terjadwal sama persis dengan sebelum unit (docs/blueprint/unit/KP-T7.md).

`data/kpt7_u5_acuan.json` dibuat dari kode SEBELUM unit ini (langkah kerja 1) di basis data tiruan baru dengan fixture
`siapkan()` (fixture sisip: tagihan pemasok, pelanggan + pesanan + surat jalan, aset tetap, perintah kerja, tugas
gudang, pesanan pendingan; dua pembaca ditiru: `budget_service.budget_vs_actual` dan `alert_ops_service._available_qty`).
Isi: himpunan (`notif_type`, `ref`, `recipient_role`, `recipient_user`, `entity_id`) notifikasi yang lahir dari sembilan
job. Sesudah unit harus SAMA.

Membuat ulang berkas acuan (hanya dari kode lama): `KN_TULIS_ACUAN_KPT7=1 python -m pytest tests_mem/test_KPT7_setara.py
-p no:cacheprovider` — tes menulis berkas lalu dilewati. Modul sendiri (basis data sendiri). Tes ini sengaja tidak
mengimpor modul baru KP-T7, supaya bisa dijalankan di kode lama.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

pytestmark = pytest.mark.anyio

BERKAS_ACUAN = Path(__file__).parent / "data" / "kpt7_u5_acuan.json"
SALES = "user_sales_01"

JOBS = [("services.alert_service", "job_ap_due"), ("services.alert_service", "job_ar_overdue"),
        ("services.alert_service", "job_depreciation_due"), ("services.alert_service", "job_budget_alert"),
        ("services.alert_service", "job_production_stalled"), ("services.alert_service", "job_ops_stalled"),
        ("services.alert_ops_service", "job_po_arrival"), ("services.alert_ops_service", "job_backorder_ready"),
        ("services.alert_ops_service", "job_ar_due_soon")]


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def _jurnal_kirim(oid: str, entitas: str, nilai: float, tanggal: str, sj: str) -> None:
    """PK-41 (K-16) — fixture jurnal pendapatan surat jalan (Dr piutang / Cr pendapatan, bentuk `post_shipment_revenue`):
    piutang kini berumur per surat jalan BERJURNAL, jadi fixture "sudah dikirim" memuat jurnalnya juga."""
    from services import gl_service as gl
    await gl._insert_entry(lines=[{"account_code": "1-1200", "debit": nilai, "credit": 0.0},
                                  {"account_code": "4-1000", "debit": 0.0, "credit": nilai}],
                           description=f"Pengakuan penjualan {oid} · {sj}", date=tanggal, source_type="shipment_revenue",
                           source_id=sj, entity_id=entitas, created_by="uji", source_label=sj,
                           ref={"order_id": oid, "order_number": f"SO-{oid}"})


async def siapkan(db) -> None:
    """Fixture sisip. Waktu relatif terhadap sekarang supaya umur/selisih hari tetap sama kapan pun dijalankan."""
    from services.analytics_time import now_wib
    now = datetime.now(timezone.utc)
    hari_ini = now_wib().date()

    def tgl(d: int) -> str:
        return (hari_ini + timedelta(days=d)).isoformat()

    # Tagihan pemasok: pemasok tanpa termin → jatuh tempo = tanggal tagihan.
    await db.vendor_bills.insert_many([
        {"id": "u5_vb_ksc", "bill_number": "VB-U5-1", "bill_date": tgl(3), "grand_total": 1_000_000, "amount_paid": 0,
         "supplier_id": "u5_sup", "supplier_name": "Pemasok U5", "entity_id": "ent_ksc", "status": "posted"},
        {"id": "u5_vb_kanda", "bill_number": "VB-U5-2", "bill_date": tgl(-5), "grand_total": 2_000_000,
         "amount_paid": 500_000, "supplier_id": "u5_sup", "supplier_name": "Pemasok U5", "entity_id": "ent_kanda",
         "status": "posted"},
        {"id": "u5_vb_jauh", "bill_number": "VB-U5-3", "bill_date": tgl(20), "grand_total": 3_000_000,
         "amount_paid": 0, "supplier_id": "u5_sup", "entity_id": "ent_ksc", "status": "posted"},
        {"id": "u5_vb_lunas", "bill_number": "VB-U5-4", "bill_date": tgl(1), "grand_total": 4_000_000,
         "amount_paid": 4_000_000, "supplier_id": "u5_sup", "entity_id": "ent_ksc", "status": "posted"},
    ])
    # Piutang: jatuh tempo = surat jalan pertama + termin pesanan (30 hari).
    await db.customers.insert_many([
        {"id": "u5_c1", "name": "Pelanggan U5 A", "entity_id": "ent_ksc", "assigned_sales_id": SALES,
         "payment_profile": {}, "credit_limit": 0, "status": "active"},
        {"id": "u5_c2", "name": "Pelanggan U5 B", "entity_id": "ent_kanda", "assigned_sales_id": "",
         "payment_profile": {}, "credit_limit": 0, "status": "active"},
    ])
    so = {"status": "confirmed", "payment_term_days": 30, "payments": [], "payment_term_code": "",
          "created_at": _iso(now - timedelta(days=45))}
    await db.sales_orders.insert_many([
        {**so, "id": "u5_so_lewat", "number": "SO-U5-1", "customer_id": "u5_c1", "customer_name": "Pelanggan U5 A",
         "grand_total": 1_500_000, "entity_id": "ent_ksc"},
        {**so, "id": "u5_so_h3", "number": "SO-U5-2", "customer_id": "u5_c2", "customer_name": "Pelanggan U5 B",
         "grand_total": 700_000, "entity_id": "ent_kanda"},
        {**so, "id": "u5_so_h0", "number": "SO-U5-3", "customer_id": "u5_c1", "customer_name": "Pelanggan U5 A",
         "grand_total": 800_000, "entity_id": "ent_ksc"},
        {**so, "id": "u5_so_bo", "number": "SO-U5-4", "customer_id": "u5_c1", "customer_name": "Pelanggan U5 A",
         "grand_total": 0, "entity_id": "ent_ksc", "status": "waiting_stock", "has_backorder": True,
         "backorders": [{"product_id": "u5_p1", "backorder_qty": 5, "status": "open"}]},
    ])
    await db.shipments.insert_many([
        {"id": "u5_sj1", "order_id": "u5_so_lewat", "status": "delivered", "created_at": _iso(now - timedelta(days=40))},
        {"id": "u5_sj2", "order_id": "u5_so_h3", "status": "delivered", "created_at": _iso(now - timedelta(days=27))},
        {"id": "u5_sj3", "order_id": "u5_so_h0", "status": "delivered", "created_at": _iso(now - timedelta(days=30))},
    ])
    from services.book_date import tanggal_buku   # PK-41 — jurnal pendapatan surat jalan (umur per surat jalan berjurnal)
    for oid, ent, nilai, sj, hari in (("u5_so_lewat", "ent_ksc", 1_500_000, "u5_sj1", 40),
                                      ("u5_so_h3", "ent_kanda", 700_000, "u5_sj2", 27),
                                      ("u5_so_h0", "ent_ksc", 800_000, "u5_sj3", 30)):
        await _jurnal_kirim(oid, ent, nilai, tanggal_buku(now - timedelta(days=hari)), sj)
    await db.fin_fixed_assets.insert_one({"id": "u5_fa1", "number": "FA-U5-1", "name": "Mesin U5", "status": "active",
                                         "entity_id": "ent_ksc", "monthly_depreciation": 250_000})
    await db.mfg_work_orders.insert_many([
        {"id": "u5_wo1", "wo_number": "WO-U5-1", "status": "released", "released_at": _iso(now - timedelta(days=5)),
         "created_at": _iso(now - timedelta(days=6)), "entity_id": "ent_ksc", "output_name": "Kain U5",
         "planned_qty": 10, "output_unit": "m", "warehouse_name": "Gudang U5", "material_plan": []},
        {"id": "u5_wo2", "wo_number": "WO-U5-2", "status": "draft", "created_at": _iso(now - timedelta(days=10)),
         "entity_id": "ent_kanda", "output_name": "Kain U5 B", "planned_qty": 5, "output_unit": "m",
         "warehouse_name": "Gudang U5 B", "material_plan": []},
        {"id": "u5_wo3", "wo_number": "WO-U5-3", "status": "released", "released_at": _iso(now - timedelta(days=1)),
         "created_at": _iso(now - timedelta(days=2)), "entity_id": "ent_ksc", "output_name": "Kain U5 C",
         "planned_qty": 1, "output_unit": "m", "warehouse_name": "Gudang U5", "material_plan": []},
    ])
    await db.wms_tasks.insert_many([
        {"id": "u5_t1", "flow_type": "outbound", "status": "pending", "warehouse_id": "u5_wh1",
         "warehouse_name": "Gudang U5", "order_number": "SO-U5-1", "entity_id": "ent_ksc",
         "created_at": _iso(now - timedelta(days=3))},
        {"id": "u5_t2", "flow_type": "inbound", "source_type": "purchase_order", "status": "completed",
         "warehouse_id": "u5_wh2", "warehouse_name": "Gudang U5 B", "po_number": "PO-U5-1", "product_id": "u5_p1",
         "product_name": "Benang U5", "received_qty": 12.5, "unit": "kg", "entity_id": "ent_kanda",
         "created_at": _iso(now - timedelta(days=1)), "completed_at": _iso(now - timedelta(hours=2))},
        {"id": "u5_t3", "flow_type": "inbound", "status": "receiving", "warehouse_id": "u5_wh1",
         "warehouse_name": "Gudang U5", "entity_id": "ent_ksc", "created_at": _iso(now - timedelta(hours=20))},
    ])


def _tiru_pembaca(monkeypatch) -> None:
    """Dua pembaca ditiru (fixture): anggaran untuk `ent_ksc` dan stok tersedia produk pendingan."""
    from services import alert_ops_service, budget_service

    async def _anggaran(scope, year, entity_id):
        if entity_id != "ent_ksc":
            return {"alerts": []}
        return {"alerts": [
            {"status": "over", "used_pct": 112, "month": 1, "key": "6-1100", "label": "Beban Kantor", "budget": 1000,
             "actual": 1100, "committed": 20, "remaining": -120},
            {"status": "warning", "used_pct": 85, "month": 0, "key": "6-1200", "label": "Beban Listrik",
             "budget": 2000, "actual": 1700, "committed": 0, "remaining": 300}]}

    async def _tersedia(product_id, entity_id):
        return 10.0 if product_id == "u5_p1" else 0.0

    monkeypatch.setattr(budget_service, "budget_vs_actual", _anggaran)
    monkeypatch.setattr(alert_ops_service, "_available_qty", _tersedia)


def _normal(db_users: Dict[str, str], n: Dict[str, Any]) -> List[Any]:
    """Id akun → email; bulan/tahun berjalan → penanda (acuan tidak bergantung bulan pembuatan)."""
    uid = n.get("recipient_user")
    ref = str(n.get("ref") or "")
    if "#" in ref:
        base, _, u = ref.partition("#")
        ref = f"{base}#{db_users.get(u, u)}"
    ref = re.sub(r"\d{4}-\d{2}", "<bulan>", ref)
    ref = re.sub(r":\d{4}$", ":<tahun>", ref)
    return [n.get("type"), ref, n.get("recipient_role"), db_users.get(uid, uid) if uid else uid, n.get("entity_id")]


async def test_KPT7_U5_penerima_bawaan_sama_persis(db, monkeypatch):
    import importlib
    await siapkan(db)
    _tiru_pembaca(monkeypatch)
    await db.notifications.delete_many({})
    for mod, fn in JOBS:
        await getattr(importlib.import_module(mod), fn)()
    users = {u["id"]: u.get("email", u["id"]) for u in await db.users.find({}, {"_id": 0, "id": 1, "email": 1})
             .to_list(None)}
    hasil = sorted(_normal(users, n) for n in await db.notifications.find({}, {"_id": 0}).to_list(None))
    # Hitungan tangan (bawaan): ap_due 2 (VB-U5-1 3 hari lagi, VB-U5-2 lewat 5 hari; VB-U5-3 20 hari > 7; lunas
    # dilewati) · ar_overdue 2 (manajer + salinan sales pemegang akun) · penyusutan 1 · anggaran 2 · WO 2 (WO-U5-1
    # dirilis 5 > 3, WO-U5-2 draf 10 > 7; WO-U5-3 1 hari) · tugas gudang 1 (u5_t1 3 > 2 hari; u5_t3 20 jam) · barang PO
    # datang 3 (manajer, gudang, sales pemilik pendingan) · pendingan siap 2 (sales + manajer) · piutang H-3/H 2 pesanan
    # × (pemegang akun bila ada + pemegang izin ar_receipt.create di PT itu).
    assert {r[0] for r in hasil} >= {"ap_due", "ar_overdue", "depreciation_due", "budget_alert",
                                     "production_stalled", "ops_stalled", "po_arrival", "backorder_ready",
                                     "ar_due_soon"}, hasil
    if os.environ.get("KN_TULIS_ACUAN_KPT7") == "1":
        BERKAS_ACUAN.write_text(json.dumps(hasil, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        pytest.skip(f"acuan ditulis ({len(hasil)} notifikasi) — jalankan ulang tanpa KN_TULIS_ACUAN_KPT7")
    acuan = json.loads(BERKAS_ACUAN.read_text(encoding="utf-8"))
    assert hasil == acuan
