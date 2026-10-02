"""P07 (sebagian) + jurnal pembalik — regression invariant pada data sintetis.

Usage: cd /app/backend && python ../audit/iterations/2026-10-06-P07-dispatch-identity-reversal/repro_p07.py
Data sintetis ber-prefix `audit_p07_*` dihapus di akhir. Bagian WM-06 memanggil server lokal (REACT_APP_BACKEND_URL).
"""
import asyncio
import json
import sys
import uuid
from types import SimpleNamespace as NS

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


async def main():
    import requests
    from db import db
    from core_utils import now_iso
    from services import gl_service as gl, closing_service as cs
    T = f"audit_p07_{uuid.uuid4().hex[:6]}"
    A, WH, E = "ent_ksc", "wh_jakarta", f"ent_audit_p07_{T[-6:]}"
    admin = {"id": f"u_{T}", "name": "Audit Admin", "role": "admin"}
    prods = [p["id"] for p in await db.products.find({}, {"_id": 0, "id": 1}).limit(2).to_list(2)]
    base = [ln.split("=", 1)[1].strip() for ln in open("../frontend/.env") if ln.startswith("REACT_APP_BACKEND_URL")][0] + "/api"
    s = requests.Session()
    s.post(f"{base}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=20)
    s.headers["X-Entity-Id"] = A

    def roll(n, order, length=50.0, pid=None, status="committed", created="2026-01-01T00:00:00", **kw):
        return {"id": f"{T}_r{n}", "roll_no": f"R-{T}-{n}", "product_id": pid or prods[0], "warehouse_id": WH,
                "owner_entity_id": A, "status": status, "length_remaining": length, "length_initial": length,
                "unit": "meter", "reserved_ref": {"type": "sales_order", "id": order}, "created_at": created, **kw}

    def task(n, order, qty, picked=0.0):
        return {"id": f"{T}_t{n}", "flow_type": "outbound", "entity_id": A, "order_id": order, "product_id": prods[0],
                "warehouse_id": WH, "quantity": qty, "picked_qty": picked, "shipped_qty": 0.0, "status": "created",
                "scan_log": [], "created_at": now_iso()}

    async def wm06():
        o = f"{T}_so6"
        await db.inventory_rolls.insert_many([roll("6a", o), roll("6b", "other_order", pid=prods[1])])
        await db.wms_tasks.insert_one(task(6, o, 50))
        u = f"{base}/outbound/tasks/{T}_t6/scan-pick"
        neg = s.post(u, params={"actual_qty": -5, "roll_id": f"{T}_r6a"}, timeout=20)
        nan = s.post(u, params={"actual_qty": "nan", "roll_id": f"{T}_r6a"}, timeout=20)
        check("WM-06", "qty negatif / NaN ditolak", neg.status_code == 400 and nan.status_code in (400, 422), (neg.status_code, nan.status_code))
        bad = s.post(u, params={"actual_qty": 50, "roll_id": f"{T}_r6b"}, timeout=20)
        rnd = s.post(u, params={"actual_qty": 50, "roll_id": "random-string"}, timeout=20)
        check("WM-06", "roll produk lain / tak dikenal ditolak",
              bad.status_code == 400 and rnd.status_code == 400, (bad.status_code, rnd.status_code))
        ok = s.post(u, params={"actual_qty": 50, "roll_id": f"R-{T}-6a"}, timeout=20)
        t = await db.wms_tasks.find_one({"id": f"{T}_t6"}, {"_id": 0})
        check("WM-06", "scan no. roll sah → roll_id di-resolve server", ok.status_code == 200 and t["scan_log"][-1]["roll_id"] == f"{T}_r6a",
              (ok.status_code, ok.text[:120]))

    async def ax01():
        from services.shipment_service import dispatch_task
        o = f"{T}_so1"
        await db.inventory_rolls.insert_many([roll("old", o, created="2025-01-01T00:00:00"), roll("new", o, created="2026-02-01T00:00:00")])
        await db.wms_tasks.insert_one(task(1, o, 50))
        r = s.post(f"{base}/outbound/tasks/{T}_t1/scan-pick", params={"actual_qty": 50, "roll_id": f"{T}_rnew"}, timeout=20)
        t = await db.wms_tasks.find_one({"id": f"{T}_t1"}, {"_id": 0})
        _, shp = await dispatch_task(t, 50, "audit")
        check("AX-01", "roll dikirim = roll yang dipindai (NEW, bukan OLD terlama)",
              r.status_code == 200 and [x["roll_id"] for x in shp["rolls"]] == [f"{T}_rnew"], shp.get("rolls"))

    async def ax03():
        from services.shipment_service import dispatch_task
        o = f"{T}_so3"
        await db.inventory_rolls.insert_one(roll("3", o, length=100.0))
        await db.wms_tasks.insert_one({**task(3, o, 100, picked=100.0), "status": "packing"})
        stale = await db.wms_tasks.find_one({"id": f"{T}_t3"}, {"_id": 0})
        await dispatch_task(stale, 30, "audit")
        try:
            await dispatch_task(stale, 30, "audit")  # snapshot lama
        except Exception as exc:  # noqa: BLE001
            check("AX-03", "dispatch kedua dgn snapshot lama tetap menghitung progres terbaru", False, exc)
        t = await db.wms_tasks.find_one({"id": f"{T}_t3"}, {"_id": 0})
        tot = sum(x["qty"] for x in await db.shipments.find({"task_id": f"{T}_t3"}, {"_id": 0, "qty": 1}).to_list(10))
        check("AX-03", "task.shipped_qty = Σ surat jalan (60)", t["shipped_qty"] == 60 and tot == 60, (t["shipped_qty"], tot))
        try:
            await dispatch_task(stale, 80, "audit")
            check("AX-03", "snapshot lama tidak boleh kirim melebihi sisa terbaru", False, "lolos")
        except Exception as exc:  # noqa: BLE001
            check("AX-03", "snapshot lama tidak boleh kirim melebihi sisa terbaru", getattr(exc, "status_code", 0) in (400, 409), exc)

    async def rf05():
        from services import loading_check_service as lc, rfid_print_service as rps
        o = f"{T}_so5"
        await db.sales_orders.insert_one({"id": o, "entity_id": A, "number": f"SO-{T}", "items": []})
        await db.rfid_tags.insert_one({"id": f"{T}_tag", "epc": f"EPC{T.upper()}", "status": "active", "roll_id": f"{T}_r5a"})
        await db.inventory_rolls.insert_many([roll("5a", o, rfid_tag_id=f"{T}_tag"), roll("5b", o)])
        s1 = await lc.start(o, [A], "audit")
        await (rps.scan_session(s1["id"], [f"EPC{T.upper()}"], [A], ["loading_check"]) if hasattr(rps, "scan_session") else rps.scan_verify(s1["id"], [f"EPC{T.upper()}"], [A]))  # P08 RF-10: kind wajib
        r1 = await lc.complete(s1["id"], [A])
        check("RF-05", "1 bertag + 1 tanpa tag, scan 1 EPC → tidak clean", r1.get("result") != "clean", r1.get("result"))
        s2 = await lc.start(o, [A], "audit")
        await (rps.scan_session(s2["id"], [f"EPC{T.upper()}"], [A], ["loading_check"]) if hasattr(rps, "scan_session") else rps.scan_verify(s2["id"], [f"EPC{T.upper()}"], [A]))  # P08 RF-10: kind wajib
        await lc.scan_label(s2["id"], f" r-{T}-5b ".lower(), [A])
        r2 = await lc.complete(s2["id"], [A])
        check("RF-05", "roll tanpa tag diverifikasi lewat label → clean", r2.get("result") == "clean", r2.get("result"))

    async def cx11():
        from services import return_service as rs
        lines = [[10.0, 10.0], [10.0, 20.0]]
        full = rs._consume_lines([list(x) for x in lines], 20)
        first = rs._consume_lines(lines, 10)
        second = rs._consume_lines(lines, 10)
        check("CX-11", "retur penuh 10@10+10@20 = 300", round(full, 2) == 300, full)
        check("CX-11", "retur bertahap: pertama 100, kedua 200 (bukan harga baris terakhir)", (first, second) == (100, 200), (first, second))

    async def rev():
        await db.business_entities.insert_one({"id": E, "short_name": "AUDP07", "is_group": False})
        je = lambda ln, d: NS(lines=[{"account_code": c, "debit": a, "credit": b} for c, a, b in ln], date=d, description="audit", entity_id=E)  # noqa: E731
        m = await gl.create_manual_entry(je([("6-4000", 120, 0), ("1-1100", 0, 120)], "2025-03-10T10:00:00"), admin, entity_id=E)
        auto = await gl._insert_entry(lines=[{"account_code": "6-4000", "debit": 30, "credit": 0}, {"account_code": "1-1100", "debit": 0, "credit": 30}],
                                      description="auto", date="2025-03-11T10:00:00", source_type="audit_auto", source_id=T,
                                      entity_id=E, created_by="audit")
        await cs.close_period("month", "2025-03", admin, E)
        try:
            await gl.reverse_entry(m["id"], "2025-03-20", "salah akun", admin)
            check("REV", "tanggal pembalik di periode tertutup ditolak", False, "lolos")
        except gl.ClosedPeriodError:
            check("REV", "tanggal pembalik di periode tertutup ditolak", True)
        try:
            await gl.reverse_entry(m["id"], now_iso()[:10], " ", admin)
            check("REV", "alasan wajib", False, "lolos")
        except ValueError:
            check("REV", "alasan wajib", True)
        r = await gl.reverse_entry(m["id"], now_iso()[:10], "salah akun", admin)
        orig = await db.journal_entries.find_one({"id": m["id"]}, {"_id": 0})
        swapped = {(ln["account_code"], ln["debit"], ln["credit"]) for ln in r["lines"]} == {("6-4000", 0, 120), ("1-1100", 120, 0)}
        check("REV", "pembalik di periode berjalan: debit↔kredit, asli tetap posted & tertaut", swapped and orig["status"] == "posted"
              and orig["reversed_by_entry_id"] == r["id"] and r["source_type"] == "reversal", (r["lines"], orig.get("reversed_by_entry_id")))
        try:
            await gl.reverse_entry(m["id"], now_iso()[:10], "lagi", admin)
            check("REV", "pembalikan kedua ditolak", False, "lolos")
        except ValueError:
            check("REV", "pembalikan kedua ditolak", True)
        try:
            await gl.reverse_entry(r["id"], now_iso()[:10], "balik pembalik", admin)
            check("REV", "jurnal pembalik tidak bisa dibalik", False, "lolos")
        except ValueError:
            check("REV", "jurnal pembalik tidak bisa dibalik", True)
        ra = await gl.reverse_entry(auto["id"], now_iso()[:10], "koreksi otomatis", admin)
        check("REV", "jurnal otomatis boleh dibalik", ra and ra["status"] == "posted", ra and ra.get("number"))
        cl = await db.period_closings.find_one({"entity_id": E, "status": "closed"}, {"_id": 0, "stale": 1})
        check("REV", "periode tertutup tidak berubah (closing tidak stale)", cl and not cl.get("stale"), cl)
        res = await asyncio.gather(*[gl.reverse_entry(m2["id"], now_iso()[:10], "race", admin) for m2 in
                                     [await gl.create_manual_entry(je([("6-4000", 5, 0), ("1-1100", 0, 5)], now_iso()), admin, entity_id=E)] * 3],
                                   return_exceptions=True)
        check("REV", "3 pembalikan bersamaan → tepat 1", sum(isinstance(x, dict) for x in res) == 1, [type(x).__name__ for x in res])

    try:
        for fid, fn in (("WM-06", wm06), ("AX-01", ax01), ("AX-03", ax03), ("RF-05", rf05), ("CX-11", cx11), ("REV", rev)):
            await guarded(fid, fn())
    finally:
        await db.wms_tasks.delete_many({"id": {"$regex": f"^{T}"}})
        await db.inventory_rolls.delete_many({"$or": [{"id": {"$regex": f"^{T}"}}, {"reserved_ref.id": {"$regex": f"^{T}"}}]})
        await db.shipments.delete_many({"task_id": {"$regex": f"^{T}"}})
        await db.inventory_movements.delete_many({"source_document": {"$regex": f"^{T}"}})
        await db.sales_orders.delete_many({"id": {"$regex": f"^{T}"}})
        await db.rfid_tags.delete_many({"id": {"$regex": f"^{T}"}})
        await db.rfid_verify_sessions.delete_many({"order_id": {"$regex": f"^{T}"}})
        await db.doc_refs.delete_many({"$or": [{"a.id": {"$regex": f"^{T}"}}, {"b.id": {"$regex": f"^{T}"}}]})
        await db.journal_entries.delete_many({"entity_id": E})
        await db.period_closings.delete_many({"entity_id": E})
        await db.business_entities.delete_many({"id": E})
    npass = sum(r["pass"] for r in results)
    print(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"pass={npass} fail={len(results) - npass}")


asyncio.run(main())
