"""P08 — IX-12, RF-01, RF-07, RF-10, RF-11, RF-14, RF-15, UX-02 — regression invariant (data sintetis).

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-08-P08-tag-printer-verify/repro_p08.py
Data sintetis ber-prefix `audit_p8_*` dihapus di akhir. Tidak ada perangkat fisik yang dipakai.
"""
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
results = []
FE = os.path.join(os.path.dirname(os.path.abspath(".")), "frontend", "src", "features")


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def guarded(fid, coro):
    try:
        await coro
    except Exception as exc:  # noqa: BLE001
        check(fid, f"bagian {fid} crash", False, repr(exc)[:200])


async def code_of(coro):
    try:
        await coro
        return 200
    except Exception as exc:  # noqa: BLE001
        return getattr(exc, "status_code", repr(exc)[:80])


async def main():
    from db import db
    from core_utils import now_iso
    from services import rfid_service as rs, rfid_print_service as rps, rfid_ingest_service as ing
    T = f"audit_p8_{uuid.uuid4().hex[:6]}"
    A, WH = "ent_ksc", "wh_jakarta"
    prod = await db.products.find_one({}, {"_id": 0, "id": 1})

    async def mk_roll(n, **kw):
        r = {"id": f"{T}_r{n}", "roll_no": f"{T.upper()}-{n}", "product_id": prod["id"], "owner_entity_id": A,
             "warehouse_id": WH, "status": "available", "length_remaining": 10.0, "unit": "meter",
             "rfid_tag_id": None, "journey": {"stage": "received_transit"}, "created_at": now_iso(), **kw}
        await db.inventory_rolls.insert_one(dict(r))
        return r

    async def rf01():
        epc = rs.generate_epc()
        check("RF-01", "generate_epc kanonik 24 hex tanpa pemisah", len(epc) == 24 and "-" not in epc, epc)
        r = await mk_roll(1)
        tag = await rs.encode_tag(r["id"], [A])
        zpl = rps.generate_rfid_zpl(tag["epc"], r, tag)
        chip = zpl.split("^RFW,H^FD", 1)[1].split("^FS", 1)[0]
        check("RF-01", "EPC chip (^RFW) == EPC database", chip == tag["epc"], f"{chip} vs {tag['epc']}")
        grouped = "-".join(tag["epc"][i:i + 4] for i in range(0, 24, 4)).lower()
        dev = {"id": f"{T}_hh", "type": "handheld", "warehouse_id": WH, "name": "HH"}
        res = await ing.ingest(dev, [tag["epc"], grouped])
        ok = res["count"] == 1 and res["results"][0].get("roll_no") == r["roll_no"]
        check("RF-01", "raw reader & bentuk berpemisah/lowercase → roll yang sama (1 hasil)", ok, res["results"])
        r2 = await mk_roll(2)
        c = await code_of(rs.encode_tag(r2["id"], [A], epc=grouped))
        check("RF-01", "representasi lain dari EPC aktif → 409 (bukan tag kedua)", c == 409, c)
        r3 = await mk_roll(3)
        custom = "e2" + uuid.uuid4().hex[:22]
        t3 = await rs.encode_tag(r3["id"], [A], epc="-".join(custom[i:i + 4] for i in range(0, 24, 4)))
        check("RF-01", "custom EPC berpemisah/lowercase disimpan kanonik", t3["epc"] == custom.upper(), t3["epc"])
        idx = [i["name"] for i in await db.rfid_tags.list_indexes().to_list(20)]
        check("RF-01", "indeks unik EPC tag hidup ada", "uniq_live_epc" in idx, idx)

    async def rf11():
        r = await mk_roll(11)
        tag = {"sku": "S^XZ~JA", "product_name": "Kain ^FS^FO0,0^FDINJECTED\nbaris~DG ñ"}
        zpl = rps.generate_rfid_zpl(rs.generate_epc(), r, tag)
        body = zpl.replace("^XA", "", 1).rsplit("^XZ", 1)[0]
        check("RF-11", "teks bebas tidak menyisipkan perintah ZPL (^FD/^XZ/~)",
              "^FDINJECTED" not in zpl and "^XZ~JA" not in zpl and "~DG" not in zpl and body.count("^XZ") == 0, zpl[:200])
        check("RF-11", "newline dibuang dari field", "INJECTED\n" not in zpl)
        for bad in ["E2" + "0" * 21, "E2" + "0" * 23, "E2" + "0" * 30, "E2ZZ" + "0" * 20]:
            c = await code_of(rs.encode_tag((await mk_roll(f"b{len(bad)}{bad[3]}"))["id"], [A], epc=bad))
            check("RF-11", f"custom EPC invalid ({len(bad)} char) ditolak 400", c == 400, c)
        try:
            rps.generate_rfid_zpl("E2" + "A" * 26, r, {})
            check("RF-11", "ZPL menolak EPC >24 hex (tanpa potong diam-diam)", False)
        except ValueError:
            check("RF-11", "ZPL menolak EPC >24 hex (tanpa potong diam-diam)", True)

    async def rf14_15():
        r1, r2 = await mk_roll(21), await mk_roll(22)
        job = await rps.create_print_job([r1["id"], r2["id"]], [A], "audit")
        roll = await db.inventory_rolls.find_one({"id": r1["id"]}, {"_id": 0})
        tag = await db.rfid_tags.find_one({"id": roll["rfid_tag_id"]}, {"_id": 0})
        check("RF-14", "job queued: journey BUKAN tag_printed", roll["journey"]["stage"] != "tag_printed", roll["journey"])
        check("RF-14", "job queued: tag belum aktif (pending_print)", tag["status"] == "pending_print", tag["status"])
        c = await code_of(rps.start_verify(job["id"], [A], "audit"))
        check("RF-14", "verifikasi job queued ditolak 400", c == 400, c)
        # RF-15 lease
        p1 = {"id": f"{T}_p1", "type": "printer", "warehouse_id": WH}
        p2 = {"id": f"{T}_p2", "type": "printer", "warehouse_id": WH}
        gate = {"id": f"{T}_g", "type": "gate", "warehouse_id": WH}
        await db.rfid_print_jobs.update_many({"warehouse_id": WH, "status": "queued", "id": {"$ne": job["id"]}},
                                             {"$set": {"lease": {"device_id": "audit_hold", "attempt_id": "x",
                                                                 "expires_at": "2999-01-01"}}})
        a, b = await asyncio.gather(ing.pending_jobs_for_device(p1), ing.pending_jobs_for_device(p2))
        ids_a = {j["id"] for j in a["jobs"]}
        ids_b = {j["id"] for j in b["jobs"]}
        check("RF-15", "dua pull paralel tidak berbagi job", not (ids_a & ids_b) and job["id"] in (ids_a | ids_b), (ids_a, ids_b))
        owner, other = (p1, p2) if job["id"] in ids_a else (p2, p1)
        att = next(j for j in (a["jobs"] + b["jobs"]) if j["id"] == job["id"])["lease"]["attempt_id"]
        check("RF-15", "ack printer lain ditolak 409", await code_of(ing.ack_job_printed(other, job["id"], att)) == 409)
        check("RF-15", "ack dari gate ditolak 403", await code_of(ing.ack_job_printed(gate, job["id"], att)) == 403)
        check("RF-15", "ack attempt lama/salah ditolak 409", await code_of(ing.ack_job_printed(owner, job["id"], "patt_old")) == 409)
        await db.rfid_print_jobs.update_one({"id": job["id"]}, {"$set": {"lease.expires_at": "2000-01-01"}})
        check("RF-15", "ack lease kedaluwarsa ditolak 409", await code_of(ing.ack_job_printed(owner, job["id"], att)) == 409)
        await db.rfid_print_jobs.update_one({"id": job["id"]}, {"$set": {"lease.expires_at": "2999-01-01"}})
        ok = await code_of(ing.ack_job_printed(owner, job["id"], att))
        check("RF-15", "ack pemilik lease 200", ok == 200, ok)
        await db.rfid_print_jobs.update_many({"lease.device_id": "audit_hold"}, {"$unset": {"lease": ""}})
        roll = await db.inventory_rolls.find_one({"id": r1["id"]}, {"_id": 0})
        tag = await db.rfid_tags.find_one({"id": roll["rfid_tag_id"]}, {"_id": 0})
        check("RF-14", "sesudah ack printer: tag aktif + journey tag_printed",
              tag["status"] == "active" and roll["journey"]["stage"] == "tag_printed", (tag["status"], roll["journey"]))
        s1 = await rps.start_verify(job["id"], [A], "audit")
        await rps.scan_verify(s1["id"], [tag["epc"]], [A])
        done = await rps.complete_verify(s1["id"], [A])
        j = await db.rfid_print_jobs.find_one({"id": job["id"]}, {"_id": 0, "status": 1})
        check("RF-14", "verify missing → verified_with_issues", done["result"] == "with_issues" and j["status"] == "verified_with_issues", j)
        c = await code_of(rps.start_verify(job["id"], [A], "audit"))
        check("RF-14", "verify bermasalah dapat diulang (revisi baru)", c == 200, c)
        # reprint roll tersimpan tidak memundurkan journey
        r3 = await mk_roll(23, journey={"stage": "stored"})
        j3 = await rps.create_print_job([r3["id"]], [A], "audit")
        await rps.mark_printed(j3["id"], [A])
        st = (await db.inventory_rolls.find_one({"id": r3["id"]}, {"_id": 0, "journey": 1}))["journey"]["stage"]
        check("RF-14", "reprint roll stored: journey tetap stored", st == "stored", st)
        # item ke-2 gagal → tag item ke-1 tidak tertinggal
        r4 = await mk_roll(24)
        r5 = await mk_roll(25)
        bad = {"id": f"{T}_badtag", "epc": "LEGACY-BAD", "roll_id": r5["id"], "status": "active", "owner_entity_id": A}
        await db.rfid_tags.insert_one(dict(bad))
        await db.inventory_rolls.update_one({"id": r5["id"]}, {"$set": {"rfid_tag_id": bad["id"]}})
        c = await code_of(rps.create_print_job([r4["id"], r5["id"]], [A], "audit"))
        r4d = await db.inventory_rolls.find_one({"id": r4["id"]}, {"_id": 0, "rfid_tag_id": 1})
        left = await db.rfid_tags.count_documents({"roll_id": r4["id"], "status": {"$in": ["active", "pending_print"]}})
        check("RF-14", "job gagal item ke-2 → tag item ke-1 dicabut", c == 400 and not r4d.get("rfid_tag_id") and left == 0, (c, r4d, left))

    async def rf10_07():
        from services import loading_check_service as lc
        so_id = f"{T}_so"
        await db.sales_orders.insert_one({"id": so_id, "number": f"{T}-SO", "entity_id": A, "created_at": now_iso()})
        tags = []
        for n in (31, 32):
            r = await mk_roll(n, status="committed", reserved_ref={"type": "sales_order", "id": so_id})
            tags.append((await rs.encode_tag(r["id"], [A]))["epc"])
        sess = await lc.start(so_id, [A], "audit")
        # paralel union
        await asyncio.gather(*[rps.scan_session(sess["id"], [e], [A], ["loading_check"]) for e in tags]) \
            if hasattr(rps, "scan_session") else await asyncio.gather(*[rps.scan_verify(sess["id"], [e], [A]) for e in tags])
        got = (await db.rfid_verify_sessions.find_one({"id": sess["id"]}, {"_id": 0, "scanned_epcs": 1}))["scanned_epcs"]
        check("RF-10", "dua batch scan paralel → union terjaga", set(tags) <= set(got), got)
        c = await code_of(rps.complete_verify(sess["id"], [A]))
        st = (await db.rfid_verify_sessions.find_one({"id": sess["id"]}, {"_id": 0, "status": 1}))["status"]
        check("RF-10", "endpoint complete print menolak sesi loading_check", c in (400, 404) and st == "open", (c, st))
        c = await code_of(rps.scan_verify(sess["id"], tags, [A]))
        check("RF-10", "endpoint scan print menolak sesi loading_check", c in (400, 404), c)
        check("RF-10", "sesi tak dikenal → 404", await code_of(rps.scan_verify(f"{T}_nope", tags, [A])) == 404)
        await lc.complete(sess["id"], [A])
        c = await code_of(rps.scan_session(sess["id"], tags, [A], ["loading_check"]))
        check("RF-10", "scan sesudah complete ditolak", c == 400, c)
        # RF-07 — simulasi
        await db.sales_orders.update_one({"id": so_id}, {"$unset": {"loading_check": ""}})
        s2 = await lc.start(so_id, [A], "audit")
        await rps.scan_session(s2["id"], [e for e in tags], [A], ["loading_check"], "simulated", "audit")
        out = await lc.complete(s2["id"], [A])
        so = await db.sales_orders.find_one({"id": so_id}, {"_id": 0, "loading_check": 1})
        check("RF-07", "loading check dari scan simulasi → result 'simulated'", so["loading_check"]["result"] == "simulated", out.get("result"))
        c = await code_of(lc.dispatch_guard(so_id, WH))
        check("RF-07", "hasil simulasi tidak membuka dispatch (400)", c == 400, c)
        s3 = await lc.start(so_id, [A], "audit")
        await rps.scan_session(s3["id"], tags, [A], ["loading_check"], "manual", "audit")
        await lc.complete(s3["id"], [A])
        c = await code_of(lc.dispatch_guard(so_id, WH))
        check("RF-07", "scan nyata (manual tercatat) bersih → dispatch guard lolos", c == 200, c)
        log = (await db.rfid_verify_sessions.find_one({"id": s3["id"]}, {"_id": 0, "scan_log": 1})).get("scan_log") or []
        check("RF-07", "asal scan + pelaku tercatat", log and log[-1].get("source") == "manual" and log[-1].get("by") == "audit", log[-1:])
        c = await code_of(rps.scan_session(s3["id"], tags, [A], ["loading_check"], "bogus"))
        check("RF-07", "sumber scan tak dikenal ditolak", c in (400, 404), c)
        # print verify simulasi → job & journey tidak berubah
        r = await mk_roll(33)
        job = await rps.create_print_job([r["id"]], [A], "audit")
        await rps.mark_printed(job["id"], [A])
        sv = await rps.start_verify(job["id"], [A], "audit")
        await rps.scan_session(sv["id"], [e["epc"] for e in sv["expected"]], [A], ["print_verify"], "simulated")
        out = await rps.complete_verify(sv["id"], [A])
        j = await db.rfid_print_jobs.find_one({"id": job["id"]}, {"_id": 0, "status": 1})
        st = (await db.inventory_rolls.find_one({"id": r["id"]}, {"_id": 0, "journey": 1}))["journey"]["stage"]
        check("RF-07", "verify cetak simulasi: job tetap printed, journey tidak naik tag_verified",
              out["result"] == "simulated" and j["status"] == "printed" and st != "tag_verified", (out["result"], j, st))

    async def ix12():
        from services import receiving_roll_service as rrs
        task = {"id": f"{T}_task", "status": "waiting_goods", "product_id": prod["id"], "warehouse_id": WH,
                "expected_qty": 100, "received_qty": 0, "qty_rolls_scanned": 0}
        await db.wms_tasks.insert_one({**task, "status": "completed", "created_at": now_iso()})  # DB sudah selesai
        r = await mk_roll(41, status="receiving", grn_task_id=task["id"])
        tag = await rs.encode_tag(r["id"], [A])
        roll_doc = {**r, "rfid_tag_id": tag["id"]}
        c = await code_of(rrs.attach_roll_to_task(task, roll_doc, task_qty=10, over=False, tol_close=0,
                                                  supplier_lot="", actor={"name": "audit"},
                                                  scan_entry_extra={}, audit_extra={}))
        t = await db.rfid_tags.find_one({"id": tag["id"]}, {"_id": 0, "status": 1})
        gone = not await db.inventory_rolls.find_one({"id": r["id"]})
        wt = await db.wms_tasks.find_one({"id": task["id"]}, {"_id": 0, "received_qty": 1, "qty_rolls_scanned": 1})
        check("IX-12", "attach gagal → 409, roll dihapus, tag TIDAK aktif", c == 409 and gone and t["status"] != "active", (c, gone, t))
        check("IX-12", "counter tugas tidak bertambah", wt["received_qty"] == 0 and wt["qty_rolls_scanned"] == 0, wt)
        orphan = {"id": f"{T}_orph", "epc": rs.generate_epc(), "roll_id": f"{T}_ghost", "status": "active", "owner_entity_id": A}
        await db.rfid_tags.insert_one(dict(orphan))
        if hasattr(rs, "retire_orphan_tags"):
            await rs.retire_orphan_tags()
        t = await db.rfid_tags.find_one({"id": orphan["id"]}, {"_id": 0, "status": 1})
        check("IX-12", "retry cleanup: tag yatim (crash di antara hapus roll & retire) → retired", t["status"] == "retired", t)

    async def ux02():
        src = open(os.path.join(FE, "rfid", "RfidPrintVerifyPanel.jsx")).read()
        check("UX-02", "tidak ada href mentah ke /zpl", "href={`${API}/rfid/print-jobs" not in src)
        check("UX-02", "unduh via apiClient blob + revokeObjectURL",
              'responseType: "blob"' in src and "revokeObjectURL" in src)

    for fid, fn in [("RF-01", rf01), ("RF-11", rf11), ("RF-14", rf14_15), ("RF-10", rf10_07), ("IX-12", ix12), ("UX-02", ux02)]:
        await guarded(fid, fn())

    # cleanup
    await db.rfid_tags.delete_many({"$or": [{"roll_id": {"$regex": f"^{T}"}}, {"id": {"$regex": f"^{T}"}}]})
    await db.rfid_print_jobs.delete_many({"items.roll_id": {"$regex": f"^{T}"}})
    await db.rfid_verify_sessions.delete_many({"$or": [{"order_id": {"$regex": f"^{T}"}}, {"expected.roll_id": {"$regex": f"^{T}"}}]})
    await db.rfid_reads.delete_many({"device_id": {"$regex": f"^{T}"}})
    await db.inventory_rolls.delete_many({"id": {"$regex": f"^{T}"}})
    await db.sales_orders.delete_many({"id": {"$regex": f"^{T}"}})
    await db.wms_tasks.delete_many({"id": {"$regex": f"^{T}"}})
    await db.rfid_print_jobs.update_many({"lease.device_id": "audit_hold"}, {"$unset": {"lease": ""}})

    for r in results:
        print(("PASS " if r["pass"] else "FAIL ") + f"[{r['id']}] {r['invariant']}" + ("" if r["pass"] else f" :: {r['detail']}"))
    print(json.dumps({"pass": sum(r["pass"] for r in results), "fail": sum(not r["pass"] for r in results)}))


if __name__ == "__main__":
    _ = datetime, timedelta, timezone
    asyncio.run(main())
