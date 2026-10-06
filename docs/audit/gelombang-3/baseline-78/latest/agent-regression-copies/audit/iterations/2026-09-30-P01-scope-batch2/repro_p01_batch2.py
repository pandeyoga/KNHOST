"""P01 batch 2 invariants (AX-04, AX-06, CX-02, GN-04, GN-10, GN-16, RF-08, RF-09) — real service functions,
LOCAL synthetic Mongo. Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-09-30-P01-scope-batch2/repro_p01_batch2.py
All synthetic docs use id prefix `audit_p01b_` and are removed in finally.
"""
import asyncio
import json
import sys
import uuid

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402
load_dotenv(".env")
from fastapi import HTTPException  # noqa: E402
from db import db  # noqa: E402

A, B = "ent_ksc", "ent_kanda"
T = f"audit_p01b_{uuid.uuid4().hex[:6]}"
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:200]})


async def expect_error(coro):
    try:
        await coro
        return None
    except Exception as exc:  # noqa: BLE001
        return exc


async def main():
    base = await db.inventory_rolls.find_one({"status": "available", "owner_entity_id": A, "length_remaining": {"$gt": 5}}, {"_id": 0})
    P, W = base["product_id"], base["warehouse_id"]

    def roll(suffix, owner, **kw):
        d = {**{k: v for k, v in base.items() if k not in ("rfid_tag_id", "reserved_ref")}, "id": f"{T}_{suffix}",
             "roll_no": f"{T}-{suffix}", "owner_entity_id": owner, "status": "available", "length_remaining": 10.0,
             "rfid_tag_id": None}
        d.update(kw)
        return d
    await db.inventory_rolls.insert_many([roll("a1", A), roll("a2", A), roll("b1", B)])
    try:
        # AX-04
        from services import roll_service as rs
        err = await expect_error(rs.reserve_rolls_for_wh_transfer(P, W, A, 0, f"{T}_trf", roll_ids=[f"{T}_b1"]))
        st = (await db.inventory_rolls.find_one({"id": f"{T}_b1"}, {"_id": 0, "status": 1}))["status"]
        check("AX-04", "owner A transfer cannot reserve roll of B", isinstance(err, HTTPException) and st == "available", [type(err).__name__, st])
        await rs.rebuild_balance(P, W, A)
        q_bal = {"product_id": P, "warehouse_id": W, "owner_entity_id": A}
        rq0 = float((await db.inventory_balances.find_one(q_bal, {"_id": 0, "reserved_qty": 1}) or {}).get("reserved_qty", 0))
        res = await rs.reserve_rolls_for_wh_transfer(P, W, A, 0, f"{T}_trf2", roll_ids=[f"{T}_a1"])
        rq1 = float((await db.inventory_balances.find_one(q_bal, {"_id": 0, "reserved_qty": 1}) or {}).get("reserved_qty", 0))
        bal = {"reserved_before": rq0, "reserved_after": rq1}
        check("AX-04", "explicit A roll reserved (control)", len(res) == 1)
        check("AX-04", "explicit pick rebuilds balance projection", abs(rq1 - rq0 - 10.0) < 1e-6 and
              (await db.inventory_rolls.find_one({"id": f"{T}_a1"}))["status"] == "reserved", bal)

        # AX-06
        from services import rfid_print_service as ps
        tags_before = await db.rfid_tags.count_documents({"roll_id": {"$in": [f"{T}_a2", f"{T}_b1"]}})
        err = await expect_error(ps.create_print_job([f"{T}_a2", f"{T}_b1"], [A, B], "audit"))
        tags_after = await db.rfid_tags.count_documents({"roll_id": {"$in": [f"{T}_a2", f"{T}_b1"]}})
        check("AX-06", "multi-owner print job rejected before encode side effects",
              isinstance(err, HTTPException) and tags_after == tags_before, [type(err).__name__, tags_before, tags_after])

        # GN-04
        from services import rnd_sample_service as rnd
        await db[rnd.COLL].insert_one({"id": f"{T}_smp", "entity_id": A, "status": "draft", "number": f"{T}-SMP"})
        err = await expect_error(rnd.issue_material(f"{T}_smp", {"roll_id": f"{T}_b1", "qty": 1}, "audit"))
        b1 = await db.inventory_rolls.find_one({"id": f"{T}_b1"}, {"_id": 0, "length_remaining": 1})
        check("GN-04", "sample of A cannot take material from roll of B", err is not None and b1["length_remaining"] == 10.0, [repr(err)[:120], b1])

        # CX-02
        from services import store_credit_service as scs
        so_b = await db.sales_orders.find_one({"entity_id": B}, {"_id": 0})
        so_a = await db.sales_orders.find_one({"entity_id": A, "customer_id": {"$ne": so_b.get("customer_id")}}, {"_id": 0})
        before = json.dumps(so_b.get("payments") or so_b.get("payment_history") or [], default=str)
        cust = await db.customers.find_one({"id": so_a["customer_id"]}, {"_id": 0}) or {"id": so_a["customer_id"]}
        err = await expect_error(scs._redeem_locked(customer_id=so_a["customer_id"], entity_id=A, amount=1.0,
                                                   allocations=[{"order_id": so_b["id"], "amount": 1.0}], note="audit",
                                                   actor={"name": "audit"}, ref_type="audit", ref_id=T, ref_number=T,
                                                   customer=cust))
        after_doc = await db.sales_orders.find_one({"id": so_b["id"]}, {"_id": 0})
        after = json.dumps(after_doc.get("payments") or after_doc.get("payment_history") or [], default=str)
        check("CX-02", "store credit cannot be allocated to order of other customer/entity", isinstance(err, HTTPException) and before == after,
              [type(err).__name__, getattr(err, "status_code", None)])

        # GN-10
        from services import pos_recommendation_service as pos
        await db.sales_orders.insert_one({"id": f"{T}_so", "entity_id": B, "status": "confirmed", "customer_id": T,
                                          "items": [{"product_id": f"{T}_prod", "quantity": 999}]})
        await db.products.insert_one({"id": f"{T}_prod", "sku": f"{T}-SKU", "name": "Synthetic", "status": "active"})
        try:
            rows = await pos.best_sellers([A], limit=30)
        except TypeError:
            rows = await pos.best_sellers(entity_id=None, limit=30)
        check("GN-10", "POS best-sellers for scope A excludes B orders", all(r["product_id"] != f"{T}_prod" for r in rows), len(rows))

        # GN-16 — digest scope
        from services import digest_service as dg
        from core_utils import now_iso
        day = now_iso()[:10]
        await db.notifications.insert_one({"id": f"{T}_ntf", "entity_id": B, "recipient_role": "all", "recipient_user": None,
                                           "type": "audit_probe", "title": "B only", "severity": "critical", "read": False,
                                           "created_at": now_iso()})
        sales = await db.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0, "id": 1, "role": 1})
        summ = await dg.summarize_for(sales["id"], sales["role"], day, 0)
        check("GN-16", "digest of A-only user excludes entity B notifications", "B only" not in json.dumps(summ, default=str), summ.get("total"))
        src = open("services/ai_schedules.py").read()
        check("GN-16", "scheduled AI report is private (recipient_role empty)", 'recipient_role=""' in src)

        # RF-08 / RF-09
        from services import cycle_count_service as cc
        tagged = await db.inventory_rolls.find_one({"warehouse_id": W, "owner_entity_id": A, "rfid_tag_id": {"$nin": [None, ""]}}, {"_id": 0})
        sess = await cc.start(W, [A, B], "audit") if tagged else None
        if sess:
            err = await expect_error(ps.scan_verify(sess["id"], [], [A, B]))
            check("RF-09", "multi-entity count session is scannable by its creator scope", err is None, repr(err)[:120])
            err = await expect_error(cc.complete(sess["id"], "audit", [A]) if cc.complete.__code__.co_argcount >= 3 else cc.complete(sess["id"], "audit"))
            check("RF-08", "A-only user cannot complete A+B session", isinstance(err, HTTPException), repr(err)[:120])
            res = await cc.complete(sess["id"], "audit", [A, B]) if cc.complete.__code__.co_argcount >= 3 else None
            if res:
                lst = await cc.list_counts(W, [A])
                check("RF-08", "A-only history excludes A+B count", all(r["id"] != res["id"] for r in lst))
                err = await expect_error(cc.get_count(res["id"], [A]))
                check("RF-08", "A-only detail of A+B count denied", isinstance(err, HTTPException))
                await db.rfid_cycle_counts.delete_one({"id": res["id"]})
            await db.rfid_verify_sessions.delete_one({"id": sess["id"]})
        else:
            check("RF-08", "fixture: tagged roll available", False, "no tagged roll")
    finally:
        await db.inventory_rolls.delete_many({"id": {"$regex": f"^{T}"}})
        await db.rfid_tags.delete_many({"roll_id": {"$regex": f"^{T}"}})
        await db.rfid_print_jobs.delete_many({"items.roll_id": {"$regex": f"^{T}"}})
        await db.sales_orders.delete_many({"id": {"$regex": f"^{T}"}})
        await db.products.delete_many({"id": {"$regex": f"^{T}"}})
        await db.notifications.delete_many({"id": {"$regex": f"^{T}"}})
        await db["md_samples"].delete_many({"id": {"$regex": f"^{T}"}})
        await db.store_credit_redemptions.delete_many({"ref_id": T})
        from services import roll_service as rs
        await rs.rebuild_balance(P, W, A)
        await rs.rebuild_balance(P, W, B)


asyncio.run(main())
print(json.dumps(results, indent=1))
print(f"SUMMARY pass={sum(r['pass'] for r in results)} fail={sum(not r['pass'] for r in results)}")
sys.exit(0 if all(r["pass"] for r in results) else 1)
