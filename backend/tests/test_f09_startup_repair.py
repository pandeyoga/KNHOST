"""F-09 — keputusan owner 2026-10-21: perbaikan SO yang terkunci penolakan yang sudah diajukan ulang
dijalankan di produksi. Dipasang sebagai migrasi startup sekali jalan (`bootstrap.apply_f09_...`,
penanda di `migrations`) — ikut jalan otomatis saat VPS di-deploy/restart; idempoten.
Uji tingkat layanan (event loop bersama tests/_shared_loop.py).
Jalankan: cd /app/backend && python -m pytest tests/test_f09_startup_repair.py -p no:randomly -n 0 -q
"""
import os
import sys
import uuid

from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
from _shared_loop import run  # noqa: E402

DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
FLAG = "f09_superseded_rejections_2026_10_21"


def _entry(eid, typ, status, pid=None):
    return {"id": eid, "type": typ, "status": status, "product_id": pid, "required_role": "manager",
            "decided_by": "Manajer Uji" if status == "rejected" else "", "decision_notes": "terlalu murah"}


def test_migrasi_startup_sekali_jalan_membuka_so_yang_sudah_diajukan_ulang():
    tag = uuid.uuid4().hex[:6]
    locked, untouched = f"so_TEST_F09M_{tag}_a", f"so_TEST_F09M_{tag}_b"
    DB.sales_orders.insert_many([
        {"id": locked, "number": f"TEST/SO-F09M-{tag}A", "status": "waiting_approval", "pending_approvals": [
            _entry("ap1", "special_price", "rejected", "p1"), _entry("ap2", "special_price", "approved", "p1"),
            _entry("ap3", "kredit", "rejected"), _entry("ap4", "kredit", "pending")]},
        # penolakan TANPA pengajuan ulang tetap memblokir (KN-D02)
        {"id": untouched, "number": f"TEST/SO-F09M-{tag}B", "status": "waiting_approval", "pending_approvals": [
            _entry("bp1", "special_price", "rejected", "p9")]},
    ])
    saved = DB.migrations.find_one({"id": FLAG})
    DB.migrations.delete_one({"id": FLAG})
    try:
        run(bootstrap.apply_f09_superseded_rejections_2026_10_21())
        pa = {p["id"]: p for p in DB.sales_orders.find_one({"id": locked})["pending_approvals"]}
        assert pa["ap1"]["status"] == "superseded" and pa["ap1"]["superseded_by"] == "ap2"
        assert pa["ap1"]["decided_by"] == "Manajer Uji"                     # keputusan lama tetap tersimpan
        assert pa["ap3"]["status"] == "superseded" and pa["ap3"]["superseded_by"] == "ap4"
        assert DB.sales_orders.find_one({"id": locked})["status"] == "waiting_approval"   # tidak dinaikkan otomatis
        assert DB.sales_orders.find_one({"id": untouched})["pending_approvals"][0]["status"] == "rejected"
        flag = DB.migrations.find_one({"id": FLAG})
        assert flag and f"TEST/SO-F09M-{tag}A" in flag["orders"]
        # sekali jalan: data yang terkunci SESUDAH penanda ada tidak disentuh lagi oleh startup berikutnya
        DB.sales_orders.update_one({"id": locked}, {"$set": {"pending_approvals.0.status": "rejected"}})
        run(bootstrap.apply_f09_superseded_rejections_2026_10_21())
        assert DB.sales_orders.find_one({"id": locked})["pending_approvals"][0]["status"] == "rejected"
    finally:
        DB.sales_orders.delete_many({"id": {"$in": [locked, untouched]}})
        DB.migrations.delete_one({"id": FLAG})          # penanda kembali seperti sebelum tes
        if saved:
            DB.migrations.insert_one(saved)
