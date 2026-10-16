"""PG01 (QC Cek semua / Sampling) + IX-15 (keputusan parsial) invariants — real service functions, LOCAL synthetic DB.

Usage: cd /app/backend && python ../audit/iterations/2026-10-01-P06-qc-sampling/repro_pg01_ix15.py
Fixture: synthetic qc_pending wms_task + 3 quarantine rolls (10 m each), prefix audit_pg01_*; removed at the end.
"""
import asyncio
import json
import sys
import uuid

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def main():
    from db import db
    from services import qc_service as qc
    T = f"audit_pg01_{uuid.uuid4().hex[:6]}"
    pid = f"{T}_prod"
    actor = {"id": "u_audit", "name": "Audit QC"}
    task = {"id": f"{T}_task", "type": "inbound", "status": "qc_pending", "product_id": pid,
            "warehouse_id": "wh_jakarta", "entity_id": "ent_ksc", "quantity": 30, "unit": "meter"}
    await db.products.insert_one({"id": pid, "sku": f"SKU-{T}", "name": "Synthetic QC", "base_unit": "meter"})
    await db.wms_tasks.insert_one(dict(task))
    await db.inventory_rolls.insert_many([{
        "id": f"{T}_r{i}", "roll_no": f"R-{T}-{i}", "product_id": pid, "warehouse_id": "wh_jakarta",
        "owner_entity_id": "ent_ksc", "status": "quarantine", "qc_task_id": task["id"], "length_initial": 10.0,
        "length_remaining": 10.0, "unit": "meter", "grade": "A"} for i in range(3)])

    async def decide(acc, rej=0.0):
        t = await db.wms_tasks.find_one({"id": task["id"]}, {"_id": 0})
        try:
            return await qc.process_qc_decision(t, acc, rej, "damaged", "synthetic", actor)
        except Exception as exc:  # noqa: BLE001
            return exc

    async def inspect(i):
        await db.inventory_rolls.update_one({"id": f"{T}_r{i}"}, {"$set": {"inspection.inspected_at": "2026-10-01T00:00:00+00:00"}})
    try:
        cov = await qc.qc_coverage(task)
        check("PG01", "default plan = Cek semua (all rolls required)", cov["mode"] == "all" and cov["required_rolls"] == 3, cov)
        r = await decide(30)
        check("PG01", "Cek semua: decision blocked while rolls uninspected", isinstance(r, Exception) and "Inspeksi belum memenuhi" in str(r), r)
        t = await db.wms_tasks.find_one({"id": task["id"]}, {"_id": 0})
        check("PG01", "blocked decision leaves task qc_pending (no mutation)", t["status"] == "qc_pending"
              and await db.inventory_rolls.count_documents({"qc_task_id": task["id"], "status": "quarantine"}) == 3, t["status"])
        for bad in (("xyz", 10, 1), ("sampling", 0, 1), ("sampling", 10, 0)):
            try:
                await qc.set_qc_plan(t, *bad, actor)
                check("PG01", f"invalid plan {bad} rejected", False, "accepted")
            except ValueError as exc:
                check("PG01", f"invalid plan {bad} rejected", True, str(exc))
        cov = await qc.set_qc_plan(t, "sampling", 34, 1, actor)
        check("PG01", "Sampling 34% of 3 rolls → 2 required, plan recorded", cov["required_rolls"] == 2 and cov["mode"] == "sampling"
              and (await db.wms_tasks.find_one({"id": task["id"]}, {"_id": 0})).get("qc_plan", {}).get("planned_by") == "Audit QC", cov)
        await inspect(0)
        r = await decide(30)
        check("PG01", "Sampling: 1/2 inspected still blocked", isinstance(r, Exception), r)
        await inspect(1)
        r = await decide(4)
        check("IX-15", "partial decision (4 of 30) rejected before mutation", isinstance(r, Exception) and "seluruh qty karantina" in str(r)
              and (await db.wms_tasks.find_one({"id": task["id"]}, {"_id": 0}))["status"] == "qc_pending", r)
        r = await decide(25, 5)
        ok = isinstance(r, dict)
        t = await db.wms_tasks.find_one({"id": task["id"]}, {"_id": 0})
        check("PG01", "Sampling met: full decision succeeds", ok and t["status"] == "completed", r if not ok else t["status"])
        c = t.get("qc_coverage") or {}
        check("PG01", "coverage recorded on task (mode, 2/3, applies to uninspected)",
              c.get("mode") == "sampling" and c.get("inspected_rolls") == 2 and c.get("total_rolls") == 3
              and c.get("decision_applies_to_uninspected") is True, c)
        check("IX-15", "no residual quarantine after terminal task",
              await db.inventory_rolls.count_documents({"qc_task_id": task["id"], "status": "quarantine", "length_remaining": {"$gt": 0}}) == 0,
              "residual check")
        try:
            await qc.set_qc_plan(t, "all", 0, 0, actor)
            check("PG01", "plan locked after task leaves qc_pending", False, "accepted")
        except ValueError:
            check("PG01", "plan locked after task leaves qc_pending", True, "")
    except Exception as exc:  # noqa: BLE001
        check("SCRIPT", "script error", False, repr(exc))
    finally:
        await db.inventory_rolls.delete_many({"product_id": pid})
        await db.inventory_balances.delete_many({"product_id": pid})
        await db.inventory_movements.delete_many({"product_id": pid})
        await db.wms_tasks.delete_many({"id": task["id"]})
        await db.products.delete_one({"id": pid})


asyncio.run(main())
print(json.dumps(results, indent=1, ensure_ascii=False))
print(f"SUMMARY pass={sum(r['pass'] for r in results)} fail={sum(not r['pass'] for r in results)}")
sys.exit(0 if all(r["pass"] for r in results) else 1)
