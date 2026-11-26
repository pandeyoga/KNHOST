"""Lapor Bayar CBD — pemeriksaan di MongoDB SUNGGUHAN (bukan mongomock), pada SALINAN DB (`DB_NAME`, mis. lb9_test).

Yang diperiksa (tinjauan akhir, rekomendasi 9b):
  (a) indeks wajib: `ensure_required_indexes` + `diff_required` tanpa selisih untuk koleksi lapor bayar & kwitansi;
  (b) prasyarat saga bertitik `pay_hold.due_at` pada penyapu kedaluwarsa (klaim berhasil hanya bila nilainya sama);
  (c) perbandingan teks ISO `$lte`/`$gt` di penyapu dan pengingat H-1 (`pay_due_soon`).
Butuh pesanan CBD & DP50 tertahan dari `siapkan_lb.py` (id dibaca dari lb_data.json) yang sudah ikut tersalin.

Jalankan (dari backend/, DB salinan, penjadwal mati):
  set -a; . ./.env; set +a; DB_NAME=lb9_test KN_DISABLE_SCHEDULER=1 python <folder>/cek_mongo_nyata.py
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone

assert os.environ.get("DB_NAME") not in (None, "", "test_database"), "pakai DB salinan, bukan test_database"
sys.path.insert(0, os.getcwd())
DATA = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "lb_data.json")))


async def main():
    from db import db
    import indexes
    from services import inventory_service, notification_service
    hasil = []

    # (a) indeks wajib
    diffs = await indexes.required_index_diffs()
    terkait = [d for d in diffs if d.get("collection") in ("payment_reports", "ar_receipts", "sales_orders")]
    info = await db.ar_receipts.index_information()
    uq = info.get("uq_payment_report") or {}
    hasil.append(f"(a) selisih indeks wajib: {len(diffs)} total, {len(terkait)} di payment_reports/ar_receipts/"
                 f"sales_orders; uq_payment_report unique={uq.get('unique')} partial={uq.get('partialFilterExpression')}")

    cbd, dp = DATA["cbd"], DATA["dp"]
    for so in (cbd, dp):
        d = await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0, "status": 1, "pay_hold": 1})
        assert d and d["status"] == "approved" and d.get("pay_hold"), (so["number"], d)
    now = datetime.now(timezone.utc)

    # (c) pengingat H-1 — DP50: batas 2 jam lagi (di dalam jendela), CBD: 5 hari lagi (di luar jendela)
    await db.sales_orders.update_one({"id": dp["id"]}, {"$set": {"pay_hold.due_at": (now + timedelta(hours=2)).isoformat()}})
    await db.sales_orders.update_one({"id": cbd["id"]}, {"$set": {"pay_hold.due_at": (now + timedelta(days=5)).isoformat()}})
    soon = (now + timedelta(hours=24)).isoformat()
    n = await notification_service._notify_pay_due_soon(now.isoformat(), soon)
    refs = await db.notifications.distinct("ref", {"type": "pay_due_soon"})   # per penerima: "paydue:<so>#<user>"
    n_dp = sum(1 for r in refs if r.startswith("paydue:" + dp["id"] + "#"))
    n_cbd = sum(1 for r in refs if r.startswith("paydue:" + cbd["id"] + "#"))
    hasil.append(f"(c) pengingat H-1: {n} notifikasi dibuat; untuk DP50 {n_dp} penerima, untuk CBD {n_cbd} (harus 0)")

    # (b)+(c) penyapu — DP50 lewat batas 1 menit (harus gugur), CBD masih 5 hari (harus hidup)
    await db.sales_orders.update_one({"id": dp["id"]}, {"$set": {"pay_hold.due_at": (now - timedelta(minutes=1)).isoformat()}})
    k = await inventory_service.expire_old_reservations()
    a = await db.sales_orders.find_one({"id": dp["id"]}, {"_id": 0, "status": 1})
    b = await db.sales_orders.find_one({"id": cbd["id"]}, {"_id": 0, "status": 1})
    rolls = await db.inventory_rolls.count_documents({"reservations.order_id": dp["id"]})
    hasil.append(f"(b) penyapu: {k} pesanan dikedaluwarsakan; DP50 → {a['status']} (roll masih dicadangkan: {rolls}); "
                 f"CBD → {b['status']}")

    # (b) prasyarat bertitik: klaim dengan due_at basi harus GAGAL (pesanan CBD tetap approved)
    from fastapi import HTTPException
    from services import atomic_claim as saga
    basi = (now - timedelta(days=9)).isoformat()
    try:
        await saga.claim("sales_orders", cbd["id"], "cek_basi", precondition={"status": "approved",
                                                                            "pay_hold.due_at": basi}, actor="system")
        ok = "TERKLAIM (salah)"
    except HTTPException as e:
        ok = f"ditolak {e.status_code} (benar)"
    hasil.append(f"(b) klaim berprasyarat pay_hold.due_at basi pada CBD: {ok}")
    print("\n".join(hasil))


asyncio.run(main())
