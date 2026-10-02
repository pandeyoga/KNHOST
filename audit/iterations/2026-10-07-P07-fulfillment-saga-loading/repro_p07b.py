"""P07 sisa — CX-12, GN-11, RF-04, RF-06 — regression invariant pada data sintetis.

Usage: cd /app/backend && python ../audit/iterations/2026-10-07-P07-fulfillment-saga-loading/repro_p07b.py
Data sintetis ber-prefix `audit_p7b_*` dihapus di akhir. Bagian GN-11 memanggil server lokal (REACT_APP_BACKEND_URL).
"""
import asyncio
import inspect
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def guarded(fid, coro):
    try:
        await coro
    except Exception as exc:  # noqa: BLE001
        check(fid, f"bagian {fid} crash", False, repr(exc)[:200])


def ago(minutes):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


async def main():
    import requests
    from db import db
    from core_utils import now_iso
    T = f"audit_p7b_{uuid.uuid4().hex[:6]}"
    A = "ent_ksc"
    base = [ln.split("=", 1)[1].strip() for ln in open("../frontend/.env") if ln.startswith("REACT_APP_BACKEND_URL")][0] + "/api"
    s = requests.Session()
    s.post(f"{base}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=20)
    s.headers["X-Entity-Id"] = A

    async def guard(order, wh):
        from services import loading_check_service as lc
        if "warehouse_id" in inspect.signature(lc.dispatch_guard).parameters:
            return await lc.dispatch_guard(order, wh)
        return await lc.dispatch_guard(order)  # HEAD lama

    async def blocked(order, wh):
        try:
            await guard(order, wh)
            return False
        except Exception as exc:  # noqa: BLE001
            return getattr(exc, "status_code", 0) == 400

    async def cx12():
        from services import special_order_phase2 as p2
        so, od = f"{T}_so12", f"{T}_od12"
        await db.special_orders.insert_one({"id": od, "number": f"OD-{T}", "status": "shipped", "linked_sales_order_id": so,
                                            "entity_id": A, "created_at": now_iso()})
        await db.shipments.insert_many([{"id": f"{T}_s1", "order_id": so, "qty": 10, "status": "dispatched"},
                                        {"id": f"{T}_s2", "order_id": so, "qty": 10, "status": "dispatched"}])
        await db.logistics_deliveries.insert_many([
            {"id": f"{T}_d1", "order_id": so, "shipment_ids": [f"{T}_s1"], "status": "delivered", "mode": "own_fleet"},
            {"id": f"{T}_d2", "order_id": so, "shipment_ids": [f"{T}_s2"], "status": "in_transit", "mode": "own_fleet"}])
        await p2.on_delivered(so)
        st = (await db.special_orders.find_one({"id": od}, {"_id": 0, "status": 1}))["status"]
        check("CX-12", "D1 terkirim + D2 masih jalan → OD tidak done", st == "shipped", st)
        await db.logistics_deliveries.update_one({"id": f"{T}_d2"}, {"$set": {"status": "failed"}})
        await p2.on_delivered(so)
        st = (await db.special_orders.find_one({"id": od}, {"_id": 0, "status": 1}))["status"]
        check("CX-12", "D2 gagal (belum dijadwalkan ulang) → OD tidak done", st == "shipped", st)
        await db.logistics_deliveries.update_one({"id": f"{T}_d2"}, {"$set": {"status": "delivered", "mode": "self_pickup"}})
        await p2.on_delivered(so)
        st = (await db.special_orders.find_one({"id": od}, {"_id": 0, "status": 1}))["status"]
        check("CX-12", "semua surat jalan diterima → OD done", st == "done", st)
        await p2.on_delivered(so)
        n = await db.special_orders.count_documents({"id": od, "status": "done"})
        check("CX-12", "replay event idempoten", n == 1, n)

    async def rf04_06():
        from services import loading_check_service as lc, rfid_print_service as rps
        wh = f"{T}_wh"
        so = f"{T}_so4"
        await db.warehouses.insert_one({"id": wh, "code": wh, "name": "Audit WH", "loading_check_policy": "required"})
        await db.sales_orders.insert_one({"id": so, "entity_id": A, "number": f"SO-{T}", "items": []})
        roll = lambda n, **kw: {"id": f"{T}_r{n}", "roll_no": f"R-{T}-{n}", "product_id": "p", "warehouse_id": wh,  # noqa: E731
                                "owner_entity_id": A, "status": "committed", "length_remaining": 20.0,
                                "reserved_ref": {"type": "sales_order", "id": so}, **kw}
        epc = f"EPC{T.upper()}"
        await db.rfid_tags.insert_one({"id": f"{T}_tag", "epc": epc, "status": "active", "roll_id": f"{T}_ra"})
        await db.inventory_rolls.insert_one(roll("a", rfid_tag_id=f"{T}_tag"))
        check("RF-04", "gudang 'wajib': dispatch tanpa loading check ditolak", await blocked(so, wh), "")
        await db.warehouses.update_one({"id": wh}, {"$set": {"loading_check_policy": "optional"}})
        check("RF-04", "gudang 'opsional': tetap boleh tanpa check", not await blocked(so, wh), "")
        await db.warehouses.update_one({"id": wh}, {"$set": {"loading_check_policy": "required"}})
        if hasattr(lc, "override"):
            try:
                await lc.override(so, "x", "audit")
                check("RF-04", "override tanpa alasan cukup ditolak", False, "lolos")
            except Exception as exc:  # noqa: BLE001
                check("RF-04", "override tanpa alasan cukup ditolak", getattr(exc, "status_code", 0) == 400, exc)
            await lc.override(so, "RFID reader rusak, cek manual supervisor", "audit")
            check("RF-04", "override berizin + alasan membuka dispatch", not await blocked(so, wh), "")
        else:
            check("RF-04", "override berizin tersedia", False, "tidak ada lc.override")
        sess = await lc.start(so, [A], "audit")
        await (rps.scan_session(sess["id"], [epc], [A], ["loading_check"]) if hasattr(rps, "scan_session") else rps.scan_verify(sess["id"], [epc], [A]))  # P08 RF-10: kind wajib
        r = await lc.complete(sess["id"], [A])
        check("RF-06", "check bersih → dispatch boleh", r.get("result") == "clean" and not await blocked(so, wh), r.get("result"))
        await db.inventory_rolls.insert_one(roll("b"))
        check("RF-06", "roll baru dialokasikan sesudah check → dispatch ditolak", await blocked(so, wh), "")
        await db.inventory_rolls.delete_one({"id": f"{T}_rb"})
        await db.inventory_rolls.update_one({"id": f"{T}_ra"}, {"$set": {"length_remaining": 12.0}})
        check("RF-06", "panjang roll berubah sesudah check → dispatch ditolak", await blocked(so, wh), "")
        await db.inventory_rolls.update_one({"id": f"{T}_ra"}, {"$set": {"length_remaining": 20.0, "status": "in_transit_sales"}})
        check("RF-06", "roll yang sudah terkirim tidak membatalkan hasil (partial dispatch)", not await blocked(so, wh), "")

    async def gn11():
        tid = f"{T}_task"
        await db.wms_tasks.insert_one({"id": tid, "task_number": f"WMS-{T}", "flow_type": "outbound", "entity_id": A,
                                       "status": "packing", "saga_lock": {"action": "dispatch", "by": "audit",
                                                                         "started_at": ago(1), "token": f"{T}_tok"}})
        u = f"{base}/saga-locks/wms_tasks/{tid}/release"
        r1 = s.post(u, json={"reason": "audit pelepasan kunci"}, timeout=20)
        check("GN-11", "kunci yang masih aktif (<5 menit) tidak bisa dilepas", r1.status_code == 409, (r1.status_code, r1.text[:120]))
        await db.wms_tasks.update_one({"id": tid}, {"$set": {"saga_lock.started_at": ago(30)}})
        await db.shipments.insert_one({"id": f"{T}_shp", "task_id": tid, "shipment_no": f"SJ-{T}", "qty": 5, "created_at": now_iso()})
        r2 = s.post(u, json={"reason": "audit pelepasan kunci"}, timeout=20)
        check("GN-11", "efek terposting (surat jalan) → lepas tanpa pengakuan ditolak & efek ditampilkan",
              r2.status_code == 409 and "shipments" in r2.text, (r2.status_code, r2.text[:160]))
        r3 = s.post(u, json={"reason": "audit pelepasan kunci", "acknowledge_effects": True, "lock_token": "token-lain"}, timeout=20)
        check("GN-11", "fencing: token berbeda tidak melepas kunci baru", r3.status_code == 409, r3.status_code)
        r4 = s.post(u, json={"reason": "audit pelepasan kunci", "acknowledge_effects": True}, timeout=20)
        t = await db.wms_tasks.find_one({"id": tid}, {"_id": 0, "saga_lock": 1})
        au = await db.audit_logs.find_one({"entity_id": tid, "action": "saga_lock_released"}, {"_id": 0}) or \
            await db.audit_logs.find_one({"target_id": tid, "action": "saga_lock_released"}, {"_id": 0}) or {}
        check("GN-11", "pengakuan + alasan → dilepas; audit mencatat efek & alasan",
              r4.status_code == 200 and not t.get("saga_lock") and "shipments" in json.dumps(au), (r4.status_code, list(au.keys())[:8]))

    try:
        for fid, fn in (("CX-12", cx12), ("RF-04/06", rf04_06), ("GN-11", gn11)):
            await guarded(fid, fn())
    finally:
        await db.special_orders.delete_many({"id": {"$regex": f"^{T}"}})
        await db.shipments.delete_many({"id": {"$regex": f"^{T}"}})
        await db.logistics_deliveries.delete_many({"id": {"$regex": f"^{T}"}})
        await db.warehouses.delete_many({"id": {"$regex": f"^{T}"}})
        await db.sales_orders.delete_many({"id": {"$regex": f"^{T}"}})
        await db.rfid_tags.delete_many({"id": {"$regex": f"^{T}"}})
        await db.inventory_rolls.delete_many({"id": {"$regex": f"^{T}"}})
        await db.rfid_verify_sessions.delete_many({"order_id": {"$regex": f"^{T}"}})
        await db.wms_tasks.delete_many({"id": {"$regex": f"^{T}"}})
    npass = sum(r["pass"] for r in results)
    print(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"pass={npass} fail={len(results) - npass}")


asyncio.run(main())
