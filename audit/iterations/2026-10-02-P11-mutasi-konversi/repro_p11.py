"""P11 — CX-13, GN-05, GN-06, GN-07, GN-08, IX-11 — regression invariant (in-process, data sintetis).

Usage: cd /app/backend && python ../audit/iterations/2026-10-02-P11-mutasi-konversi/repro_p11.py
Data sintetis ber-prefix `audit_p11_*` dihapus di akhir.
"""
import asyncio
import json
import sys
import uuid

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
results = []
A, WH = "ent_ksc", "wh_jakarta"
T = f"audit_p11_{uuid.uuid4().hex[:6]}"


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def guarded(fid, coro):
    try:
        await coro
    except Exception as exc:  # noqa: BLE001
        check(fid, f"bagian {fid} crash", False, repr(exc)[:300])


def status_of(exc):
    return getattr(exc, "status_code", None) or type(exc).__name__


async def main():
    from db import db
    from core_utils import now_iso

    async def mk_prod(n, **kw):
        p = {"id": f"{T}_p{n}", "sku": f"{T.upper()}-{n}", "name": f"Audit P11 {n}", "base_unit": "meter",
             "unit": "meter", **kw}
        await db.products.insert_one(dict(p))
        return p["id"]

    async def mk_roll(pid, n, qty, status="available", cost=100.0, owner=A, **kw):
        rid = f"{T}_r{n}"
        await db.inventory_rolls.insert_one({
            "id": rid, "roll_no": f"{T}-{n}", "product_id": pid, "owner_entity_id": owner, "warehouse_id": WH,
            "status": status, "length_remaining": float(qty), "length_initial": float(qty), "unit": "meter",
            "unit_cost": cost, "lot": f"{T}-LOT", "created_at": f"2020-01-01T00:00:{n:02d}", **kw})
        return rid

    async def roll(rid):
        return await db.inventory_rolls.find_one({"id": rid}, {"_id": 0}) or {}

    # ── IX-11 + GN-06 — produksi ────────────────────────────────────────────
    async def production():
        from services import production_service as ps
        mat, out = await mk_prod("mat"), await mk_prod("out")
        held = await mk_roll(mat, 1, 100, inspection={"hold": {"held": True, "reason": "warna beda"}})
        bom = await ps.create_bom({"name": f"{T} BOM", "output_product_id": out,
                                   "components": [{"material_product_id": mat, "qty_per_unit": 1}]}, A, "audit")
        wo = await ps.create_work_order({"bom_id": bom["id"], "planned_qty": 10, "warehouse_id": WH}, A, "audit")
        try:
            await ps.complete_work_order(wo["id"], {"entity_id": A}, "audit")
            check("GN-06", "draft tidak bisa langsung complete", False, "lolos")
        except ValueError as exc:
            check("GN-06", "draft tidak bisa langsung complete", True, exc)
        await ps.release_work_order(wo["id"], {"entity_id": A}, "audit")
        try:
            await ps.complete_work_order(wo["id"], {"entity_id": A}, "audit")
            check("IX-11", "roll held QC ditolak sebelum stok/output berubah", False, "lolos")
        except ValueError as exc:
            r = await roll(held)
            n_out = await db.inventory_rolls.count_documents({"acquired.ref_id": wo["id"]})
            check("IX-11", "roll held QC ditolak sebelum stok/output berubah",
                  r["length_remaining"] == 100 and n_out == 0, f"{exc} len={r['length_remaining']} out={n_out}")
        await db.inventory_rolls.update_one({"id": held}, {"$set": {"inspection.hold.held": False}})
        # BOM diubah sesudah release → WO tetap pakai resep beku (1/unit, bukan 5/unit)
        await ps.update_bom(bom["id"], {"components": [{"material_product_id": mat, "qty_per_unit": 5}]}, {"entity_id": A})
        res = await asyncio.gather(*[ps.complete_work_order(wo["id"], {"entity_id": A}, "audit") for _ in range(3)],
                                   return_exceptions=True)
        ok = [x for x in res if isinstance(x, dict)]
        n_out = await db.inventory_rolls.count_documents({"acquired.via": "production_output", "acquired.ref_id": wo["id"]})
        r = await roll(held)
        check("GN-06", "complete bersamaan → satu output, konsumsi sekali",
              len(ok) >= 1 and n_out == 1 and r["length_remaining"] == 90,
              f"ok={len(ok)} errs={[status_of(x) for x in res if not isinstance(x, dict)]} out={n_out} len={r['length_remaining']}")
        check("GN-06", "perubahan BOM sesudah release tidak mengubah WO",
              ok and ok[0]["consumed"][0]["qty"] == 10, ok and ok[0]["consumed"])
        # Dua WO berbeda berebut stok 90 (masing-masing butuh 60) → satu menang, total konsumsi 60
        w1 = await ps.create_work_order({"bom_id": bom["id"], "planned_qty": 12, "warehouse_id": WH}, A, "audit")
        w2 = await ps.create_work_order({"bom_id": bom["id"], "planned_qty": 12, "warehouse_id": WH}, A, "audit")
        for w in (w1, w2):
            await ps.release_work_order(w["id"], {"entity_id": A}, "audit")
        res = await asyncio.gather(ps.complete_work_order(w1["id"], {"entity_id": A}, "audit"),
                                   ps.complete_work_order(w2["id"], {"entity_id": A}, "audit"), return_exceptions=True)
        r = await roll(held)
        done = [x for x in res if isinstance(x, dict) and x.get("status") == "completed"]
        check("GN-06", "dua WO tidak memakai qty yang sama", len(done) == 1 and r["length_remaining"] == 30,
              f"done={len(done)} len={r['length_remaining']} errs={[str(x)[:80] for x in res if not isinstance(x, dict)]}")
        loser = w2 if done and done[0]["id"] == w1["id"] else w1
        lw = await db.mfg_work_orders.find_one({"id": loser["id"]}, {"_id": 0})
        check("GN-06", "WO yang kalah tanpa efek parsial & tanpa kunci",
              lw["status"] == "released" and not lw.get("saga_lock") and not lw.get("produced_roll_ids"),
              {k: lw.get(k) for k in ("status", "saga_lock")})
        # Reservasi panjang pada roll tidak boleh dikonsumsi produksi
        await db.inventory_rolls.update_one({"id": held}, {"$set": {"length_reserved": 25}})
        w3 = await ps.create_work_order({"bom_id": bom["id"], "planned_qty": 2, "warehouse_id": WH}, A, "audit")
        await ps.release_work_order(w3["id"], {"entity_id": A}, "audit")
        try:
            await ps.complete_work_order(w3["id"], {"entity_id": A}, "audit")
            check("GN-06", "panjang yang dipesan tidak dikonsumsi", False, "lolos (bebas hanya 5, butuh 10)")
        except ValueError:
            check("GN-06", "panjang yang dipesan tidak dikonsumsi", (await roll(held))["length_remaining"] == 30)
        # Resume: crash sesudah konsumsi (stage consumed) → retry tidak mengonsumsi ulang
        await db.inventory_rolls.update_one({"id": held}, {"$set": {"length_reserved": 0}})
        orig = ps.roll_service.create_inbound_roll

        async def boom(*a, **k):
            raise RuntimeError("crash sesudah konsumsi")
        ps.roll_service.create_inbound_roll = boom
        try:
            await ps.complete_work_order(w3["id"], {"entity_id": A}, "audit")
        except RuntimeError:
            pass
        ps.roll_service.create_inbound_roll = orig
        mid = await roll(held)
        lw = await db.mfg_work_orders.find_one({"id": w3["id"]}, {"_id": 0})
        await db.mfg_work_orders.update_one({"id": w3["id"]}, {"$unset": {"saga_lock": ""}})  # admin lepas kunci
        fin = await ps.complete_work_order(w3["id"], {"entity_id": A}, "audit")
        end = await roll(held)
        check("GN-06", "fault sesudah konsumsi dapat dilanjutkan tanpa konsumsi ganda",
              (lw.get("saga_lock") or {}).get("failed_at") and mid["length_remaining"] == 20
              and end["length_remaining"] == 20 and fin["status"] == "completed",
              f"lock={(lw.get('saga_lock') or {}).get('error')} mid={mid['length_remaining']} end={end['length_remaining']}")

    # ── GN-05 — rollback R&D hanya membalik kontribusinya ──────────────────
    async def rnd():
        from services import rnd_sample_service as rs
        from services import gl_service
        pid = await mk_prod("rnd")
        rid = await mk_roll(pid, 10, 100)
        sids = []
        for i in range(2):
            sid = f"{T}_smp{i}"
            await db.md_samples.insert_one({"id": sid, "number": f"{T}-SMP{i}", "entity_id": A,
                                                 "status": "in_progress", "timeline": [], "material_issues": [],
                                                 "created_at": now_iso()})
            sids.append(sid)
        orig = gl_service.post_sample_material_issue
        state = {"n": 0}

        async def flaky(**kw):
            state["n"] += 1
            if state["n"] == 1:   # GL A: sebelum gagal, B mengambil 20 dan sukses
                gl_service.post_sample_material_issue = orig
                await rs.issue_material(sids[1], {"roll_id": rid, "qty": 20}, actor="audit")
                raise RuntimeError("GL A gagal")
            return await orig(**kw)
        gl_service.post_sample_material_issue = flaky
        try:
            await rs.issue_material(sids[0], {"roll_id": rid, "qty": 10}, actor="audit")
        except Exception as exc:  # noqa: BLE001
            r = await roll(rid)
            check("GN-05", "GL A gagal + B sukses → panjang 80", r["length_remaining"] == 80,
                  f"{type(exc).__name__}: {str(exc)[:160]} len={r['length_remaining']}")
        finally:
            gl_service.post_sample_material_issue = orig

    # ── GN-07 — retur beli ─────────────────────────────────────────────────
    async def preturn():
        from services import purchase_return_service as prs_
        pid = await mk_prod("ret")
        rid = await mk_roll(pid, 20, 100, rfid_tag_id=f"{T}-TAG")
        other = await mk_roll(pid, 21, 50, owner="ent_other")

        async def mk_ret(n, items):
            doc = {"id": f"{T}_pr{n}", "number": f"{T}-PR{n}", "entity_id": A, "warehouse_id": WH,
                   "supplier_id": "", "supplier_name": "Audit", "po_id": "", "status": "draft",
                   "supplier_flow": False, "items": items, "total_amount": 0, "grand_total": 0, "created_at": now_iso()}
            await db.purchase_returns.insert_one(dict(doc))
            return doc["id"]
        bad = await mk_ret(0, [{"product_id": pid, "sku": "X", "quantity": 10, "unit": "meter", "roll_ids": [other]}])
        try:
            await prs_.approve_and_adjust_stock(bad, "audit")
            check("GN-07", "roll beda pemilik ditolak", False, "lolos")
        except ValueError as exc:
            r = await roll(other)
            pr = await db.purchase_returns.find_one({"id": bad}, {"_id": 0})
            check("GN-07", "roll beda pemilik ditolak tanpa efek & tanpa kunci",
                  r["length_remaining"] == 50 and not pr.get("saga_lock") and not pr.get("stock_adjusted"), exc)
        ret = await mk_ret(1, [{"product_id": pid, "sku": "X", "quantity": 30, "unit": "meter", "roll_ids": [rid]}])
        res = await asyncio.gather(*[prs_.approve_and_adjust_stock(ret, "audit") for _ in range(2)], return_exceptions=True)
        parent = await roll(rid)
        kids = await db.inventory_rolls.find({"parent_roll_id": rid}, {"_id": 0}).to_list(10)
        check("GN-07", "finalisasi bersamaan → konsumsi sekali",
              parent["length_remaining"] == 70 and len(kids) == 1,
              f"len={parent['length_remaining']} kids={len(kids)} res={[status_of(x) if isinstance(x, Exception) else 'ok' for x in res]}")
        k = kids[0] if kids else {}
        check("GN-07", "parent 70 & child retur 30 beridentitas sendiri",
              k.get("length_remaining") == 30 and k.get("status") == "returned_supplier" and k.get("roll_no") != parent.get("roll_no")
              and not k.get("rfid_tag_id") and parent.get("rfid_tag_id") == f"{T}-TAG", {x: k.get(x) for x in ("roll_no", "status", "length_remaining")})
        mov = await db.inventory_movements.find_one({"ref_id": ret, "type": "return_out"}, {"_id": 0})
        check("GN-07", "movement return_out menunjuk potongan retur", mov and mov["roll_id"] == k.get("id"), mov and mov.get("roll_id"))
        # Mixed UOM: 10 yard = 9.144 meter
        ret2 = await mk_ret(2, [{"product_id": pid, "sku": "X", "quantity": 10, "unit": "yard", "roll_ids": [rid]}])
        try:
            await prs_.approve_and_adjust_stock(ret2, "audit")
        except Exception as exc:  # noqa: BLE001
            check("GN-07", "mixed UOM", False, repr(exc)[:200])
        p2 = await roll(rid)
        check("GN-07", "mixed UOM dikonversi (10 yd → 9,14 m)", abs(p2["length_remaining"] - 60.86) < 0.02, p2["length_remaining"])
        # Reversal mengembalikan potongan retur ke stok
        await prs_.reverse_settlement(ret, "audit", "uji")
        k2 = await roll(k["id"])
        check("GN-07", "reversal: potongan retur kembali available", k2.get("status") == "available", k2.get("status"))

    # ── GN-08 — konversi permintaan internal ───────────────────────────────
    async def interco():
        from services import internal_request_service as irs
        from services import interco_service as ics
        pid = await mk_prod("ic", harga_pokok=1000)
        ents = [e["id"] for e in await db.business_entities.find({"id": {"$ne": A}, "status": {"$ne": "inactive"}},
                                                                 {"_id": 0, "id": 1}).to_list(5)]
        seller = ents[0]
        await mk_roll(pid, 30, 100, owner=seller)
        rq = f"{T}_pin"
        await db.internal_requests.insert_one({"id": rq, "number": f"{T}-PIN", "entity_id": A, "status": "submitted",
                                               "reason": "uji", "items": [{"product_id": pid, "sku": "X", "quantity": 5,
                                                                            "unit": "meter"}], "timeline": []})
        actor = {"name": "audit", "role": "admin", "id": "audit"}
        res = await asyncio.gather(*[irs.convert(rq, actor, source_entity_id=seller, pricing_mode="at_cost")
                                     for _ in range(3)], return_exceptions=True)
        n = await db[ics.COLL_ICT].count_documents({"source_request_id": rq})
        req = await db.internal_requests.find_one({"id": rq}, {"_id": 0})
        check("GN-08", "convert paralel → satu pasangan", n == 2 and req["status"] == "converted" and not req.get("saga_lock"),
              f"ict={n} status={req['status']} res={[str(x)[:60] if isinstance(x, Exception) else 'ok' for x in res]}")
        try:
            await irs.cancel(rq, actor, "telat")
            check("GN-08", "cancel sesudah convert ditolak", False, "lolos")
        except irs.InternalRequestError:
            check("GN-08", "cancel sesudah convert ditolak", (await db.internal_requests.find_one({"id": rq}))["status"] == "converted")
        # Fault sesudah pair dibuat sebelum update request → retry memakai pasangan yang sama
        rq2 = f"{T}_pin2"
        await db.internal_requests.insert_one({"id": rq2, "number": f"{T}-PIN2", "entity_id": A, "status": "submitted",
                                               "reason": "uji", "items": [{"product_id": pid, "sku": "X", "quantity": 5,
                                                                            "unit": "meter"}], "timeline": []})
        await ics.create({"seller_entity_id": seller, "buyer_entity_id": A, "pricing_mode": "at_cost",
                          "items": [{"product_id": pid, "quantity": 5}], "source_request_id": rq2}, "audit")
        await irs.convert(rq2, actor, source_entity_id=seller, pricing_mode="at_cost")
        n2 = await db[ics.COLL_ICT].count_documents({"source_request_id": rq2})
        check("GN-08", "retry sesudah fault melanjutkan pasangan yang sama", n2 == 2, n2)
        await db.doc_refs.delete_many({"$or": [{"from_id": {"$regex": f"^{T}"}}, {"to_id": {"$regex": f"^{T}"}}]})

    # ── CX-13 — makloon receive ────────────────────────────────────────────
    async def makloon():
        from services import makloon_order_service as mos
        inp, outp = await mk_prod("mk_in"), await mk_prod("mk_out")
        ref = f"{T}_iss"
        sub = await mk_roll(inp, 40, 50, status="subcon", bucket_ref={"id": ref})
        mko = f"{T}_mko"
        step = {"seq": 1, "status": "issued", "material_flow": "moves", "issue_ref": ref, "input_product_id": inp,
                "output_product_id": outp, "output_unit": "meter", "input_qty": 50, "tariff_basis": "lumpsum",
                "tariff_rate": 0, "material_value": 5000, "makloon_name": "Audit", "expected_output_qty": 48}
        await db.makloon_orders.insert_one({"id": mko, "mko_number": f"{T}-MKO", "entity_id": A, "status": "in_progress",
                                            "steps": [step], "timeline": [], "from_warehouse_id": WH,
                                            "target_warehouse_id": WH, "created_at": now_iso()})
        data = {"actual_output_qty": 48, "rolls": [{"length": 48, "lot": f"{T}-OUT"}], "tariff": 100000}
        res = await asyncio.gather(*[mos.receive_step(mko, 1, dict(data), actor_name="audit") for _ in range(3)],
                                   return_exceptions=True)
        ok = [x for x in res if isinstance(x, dict)]
        n_out = await db.inventory_rolls.count_documents({"acquired.via": "subcon_receipt", "acquired.ref_id": mko})
        n_bill = await db.vendor_bills.count_documents({"makloon_order_id": mko})
        o = await db.makloon_orders.find_one({"id": mko}, {"_id": 0})
        check("CX-13", "receive bersamaan → satu output, satu tagihan, lainnya 409",
              len(ok) == 1 and n_out == 1 and n_bill == 1 and all(status_of(x) == 409 for x in res if not isinstance(x, dict)),
              f"ok={len(ok)} out={n_out} bill={n_bill} errs={[status_of(x) for x in res if not isinstance(x, dict)]}")
        check("CX-13", "kunci dilepas & step received tanpa receive_progress",
              not o.get("saga_lock") and o["steps"][0]["status"] == "received" and "receive_progress" not in o["steps"][0],
              o.get("saga_lock"))
        # Input sudah dikonsumsi tanpa receipt sah → 409, tidak memakai fallback nilai step
        mko2 = f"{T}_mko2"
        await db.makloon_orders.insert_one({"id": mko2, "mko_number": f"{T}-MKO2", "entity_id": A, "status": "in_progress",
                                            "steps": [{**step, "issue_ref": f"{ref}_gone"}], "timeline": [],
                                            "from_warehouse_id": WH, "created_at": now_iso()})
        try:
            await mos.receive_step(mko2, 1, dict(data), actor_name="audit")
            check("CX-13", "input 0 tanpa receipt sah ditolak", False, "lolos")
        except Exception as exc:  # noqa: BLE001
            o2 = await db.makloon_orders.find_one({"id": mko2}, {"_id": 0})
            n2 = await db.vendor_bills.count_documents({"makloon_order_id": mko2})
            check("CX-13", "input 0 tanpa receipt sah ditolak", status_of(exc) == 409 and n2 == 0 and not o2.get("saga_lock"), exc)
        _ = sub

    for fid, fn in (("GN-06", production), ("GN-05", rnd), ("GN-07", preturn), ("GN-08", interco), ("CX-13", makloon)):
        await guarded(fid, fn())

    # ── cleanup ─────────────────────────────────────────────────────────────
    rx = {"$regex": f"^{T}"}
    wos = [w["id"] for w in await db.mfg_work_orders.find({"bom_name": {"$regex": T}}, {"_id": 0, "id": 1}).to_list(50)]
    mkos = [f"{T}_mko", f"{T}_mko2"]
    roll_ids = [r["id"] for r in await db.inventory_rolls.find(
        {"$or": [{"product_id": rx}, {"id": rx}]}, {"_id": 0, "id": 1}).to_list(500)]
    lot_ids = [r.get("lot_id") for r in await db.inventory_rolls.find({"id": {"$in": roll_ids}}, {"_id": 0, "lot_id": 1}).to_list(500)]
    srcs = wos + mkos + [f"{T}_pr1", f"{T}_pr2"]
    await db.journal_entries.delete_many({"$or": [{"source_id": {"$in": srcs}}, {"source_id": rx}, {"description": {"$regex": T}},
                                                  {"source_label": {"$regex": T}}]})
    await db.inventory_movements.delete_many({"$or": [{"roll_id": {"$in": roll_ids}}, {"product_id": rx}]})
    await db.inventory_rolls.delete_many({"id": {"$in": roll_ids}})
    await db.inventory_lots.delete_many({"$or": [{"id": {"$in": [x for x in lot_ids if x]}}, {"product_id": rx}]})
    await db.inventory_balances.delete_many({"product_id": rx})
    await db.mfg_work_orders.delete_many({"id": {"$in": wos}})
    await db.mfg_boms.delete_many({"name": {"$regex": T}})
    await db.md_samples.delete_many({"id": rx})
    await db.purchase_returns.delete_many({"id": rx})
    await db.interco_transactions.delete_many({"source_request_id": rx})
    await db.internal_requests.delete_many({"id": rx})
    await db.makloon_orders.delete_many({"id": {"$in": mkos}})
    await db.vendor_bills.delete_many({"makloon_order_id": {"$in": mkos}})
    await db.products.delete_many({"id": rx})
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
