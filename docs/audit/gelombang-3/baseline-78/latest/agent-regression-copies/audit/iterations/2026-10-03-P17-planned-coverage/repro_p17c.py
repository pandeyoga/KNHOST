"""P17c — PROD-04 (shortage multi-komponen tanpa efek parsial) & PROD-06 (recovery sesudah worker mati).

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-03-P17-planned-coverage/repro_p17c.py
Stok (roll/saldo/mutasi/lot) dipulihkan dari snapshot; BOM/WO/jurnal/audit buatan skrip dibuang.
"""
import asyncio
import json
import sys
import uuid

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402

T = f"TEST_P17C_{uuid.uuid4().hex[:6]}"
WH, ENT = "wh_bandung", "ent_ksc"
BATIK, LURIK = "prod_batik_mega", "prod_lurik_classic"
NEW = ["mfg_boms", "mfg_work_orders", "journal_entries", "audit_logs", "notifications", "doc_refs", "inventory_lots"]
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def stock(db):
    out = {}
    for p in (BATIK, LURIK):
        rolls = await db.inventory_rolls.find({"product_id": p, "warehouse_id": WH, "owner_entity_id": ENT},
                                              {"_id": 0, "id": 1, "length_remaining": 1, "status": 1}).to_list(500)
        bal = await db.inventory_balances.find_one({"product_id": p, "warehouse_id": WH, "owner_entity_id": ENT},
                                                   {"_id": 0, "on_hand_qty": 1}) or {}
        out[p] = {"rolls": sorted((r["id"], round(r["length_remaining"], 2), r["status"]) for r in rolls),
                  "on_hand": round(float(bal.get("on_hand_qty") or 0), 2)}
    return out


async def net_consumed(db, wo_id):
    agg = await db.inventory_movements.aggregate([
        {"$match": {"source_document": wo_id, "movement_type": {"$in": ["production_consume", "production_consume_reversal"]}}},
        {"$group": {"_id": "$product_id", "q": {"$sum": "$quantity"}}}]).to_list(10)
    return {a["_id"]: round(-a["q"], 2) for a in agg}


async def run(c, h, db):
    import services.production_service as prod
    from services import roll_service
    r = await c.post("/api/production/boms", headers=h, json={
        "name": f"{T} BOM", "output_product_id": "prod_kombinasi_batik_lurik", "overhead_per_unit": 1000,
        "components": [{"material_product_id": BATIK, "qty_per_unit": 0.5}, {"material_product_id": LURIK, "qty_per_unit": 1.0}]})
    bom = r.json()
    free_l = await prod._available_qty(LURIK, WH, ENT)
    qty = round(free_l + 20, 2)        # batik cukup (0.5×), lurik kurang 20
    free_b = await prod._available_qty(BATIK, WH, ENT)
    wo = (await c.post("/api/production/work-orders", headers=h, json={"bom_id": bom["id"], "planned_qty": qty, "warehouse_id": WH})).json()
    plan = {p["material_product_id"]: p["sufficient"] for p in wo["material_plan"]}
    check("PROD-04", "rencana bahan menandai komponen kurang (batik cukup, lurik kurang)",
          free_b >= qty * 0.5 and plan == {BATIK: True, LURIK: False}, (free_b, free_l, plan))
    await c.post(f"/api/production/work-orders/{wo['id']}/release", headers=h)
    s0 = await stock(db)
    r = await c.post(f"/api/production/work-orders/{wo['id']}/complete", headers=h)
    w = await db.mfg_work_orders.find_one({"id": wo["id"]}, {"_id": 0})
    check("PROD-04", "selesai WO ditolak 400 sebelum mutasi; stok & status tetap, tanpa kunci",
          r.status_code == 400 and "tidak cukup" in r.text and await stock(db) == s0 and w["status"] == "released"
          and "saga_lock" not in w and "completion" not in w, f"{r.status_code} {r.text[:120]}")
    # balapan: cek awal lolos (dipalsukan), lurik habis di tengah konsumsi → batik yang sudah diambil dibalik
    real = prod._available_qty

    async def fake_avail(*a):
        return 1e9
    prod._available_qty = fake_avail
    try:
        await prod.complete_work_order(wo["id"], {"entity_id": ENT}, T)
        exc = None
    except Exception as e:  # noqa: BLE001
        exc = e
    finally:
        prod._available_qty = real
    w = await db.mfg_work_orders.find_one({"id": wo["id"]}, {"_id": 0})
    check("PROD-04", "shortage komponen ke-2 saat konsumsi → 409 'Tidak ada stok yang berubah'",
          getattr(exc, "status_code", None) == 409 and "Tidak ada stok" in str(getattr(exc, "detail", "")), repr(exc)[:200])
    check("PROD-04", "konsumsi batik dibalik penuh: panjang tiap roll & saldo identik snapshot",
          await stock(db) == s0 and await net_consumed(db, wo["id"]) in ({}, {BATIK: 0.0, LURIK: 0.0}, {BATIK: 0.0}),
          await net_consumed(db, wo["id"]))
    check("PROD-04", "WO tetap released tanpa kunci/completion, tanpa roll output & jurnal",
          w["status"] == "released" and "saga_lock" not in w and "completion" not in w
          and not await db.inventory_rolls.find_one({"acquired.ref_id": wo["id"]})
          and not await db.journal_entries.find_one({"source_id": wo["id"]}), w.get("status"))

    # PROD-06a — worker mati sesudah tahap 'consumed' (output gagal) → kunci tertahan, ulang melanjutkan
    wo2 = (await c.post("/api/production/work-orders", headers=h, json={"bom_id": bom["id"], "planned_qty": 10, "warehouse_id": WH})).json()
    await c.post(f"/api/production/work-orders/{wo2['id']}/release", headers=h)
    real_out = roll_service.create_inbound_roll

    async def boom(*a, **k):
        raise RuntimeError(f"{T} worker mati saat membuat roll output")
    roll_service.create_inbound_roll = boom
    try:
        await prod.complete_work_order(wo2["id"], {"entity_id": ENT}, T)
    except RuntimeError:
        pass
    finally:
        roll_service.create_inbound_roll = real_out
    w2 = await db.mfg_work_orders.find_one({"id": wo2["id"]}, {"_id": 0})
    check("PROD-06", "crash sesudah konsumsi: tahap 'consumed' tersimpan, kunci tertahan + failed_at",
          (w2.get("completion") or {}).get("stage") == "consumed" and (w2.get("saga_lock") or {}).get("failed_at"), w2.get("completion", {}).get("stage"))
    rr = await c.post(f"/api/production/work-orders/{wo2['id']}/complete", headers=h)
    check("PROD-06", "operator menekan Selesai lagi → 409 SAGA_IN_PROGRESS (tidak menggandakan)",
          rr.status_code == 409 and "SAGA_IN_PROGRESS" in rr.text, rr.status_code)
    ins = (await c.get(f"/api/saga-locks/mfg_work_orders/{wo2['id']}/inspect", headers=h)).json()
    no_ack = await c.post(f"/api/saga-locks/mfg_work_orders/{wo2['id']}/release", headers=h, json={"reason": f"{T} worker mati"})
    rel = await c.post(f"/api/saga-locks/mfg_work_orders/{wo2['id']}/release", headers=h,
                       json={"reason": f"{T} worker mati", "acknowledge_effects": True, "lock_token": ins["lock"]["token"]})
    check("PROD-06", "admin melihat efek hilir; lepas tanpa pengakuan efek 409, dengan pengakuan 200",
          ins.get("active") is False and (no_ack.status_code == 409 if ins.get("effects") else no_ack.status_code == 200)
          and rel.status_code in (200, 404), (ins.get("effects"), no_ack.status_code, rel.status_code))
    done = await c.post(f"/api/production/work-orders/{wo2['id']}/complete", headers=h)
    w2 = await db.mfg_work_orders.find_one({"id": wo2["id"]}, {"_id": 0})
    outs = await db.inventory_rolls.count_documents({"acquired.ref_id": wo2["id"], "acquired.via": "production_output"})
    check("PROD-06", "ulang melanjutkan dari 'consumed': bahan terpakai SEKALI (batik 5, lurik 10), 1 roll output, completed",
          done.status_code == 200 and w2["status"] == "completed" and outs == 1
          and await net_consumed(db, wo2["id"]) == {BATIK: 5.0, LURIK: 10.0}, (done.status_code, await net_consumed(db, wo2["id"]), outs))

    # PROD-06b — proses dibunuh DI TENGAH konsumsi (BaseException, kunci tanpa failed_at)
    wo3 = (await c.post("/api/production/work-orders", headers=h, json={"bom_id": bom["id"], "planned_qty": 8, "warehouse_id": WH})).json()
    await c.post(f"/api/production/work-orders/{wo3['id']}/release", headers=h)
    real_consume, calls = prod._consume_material, {"n": 0}

    async def die_on_second(*a, **k):
        calls["n"] += 1
        if calls["n"] == 2:
            raise asyncio.CancelledError()
        return await real_consume(*a, **k)
    prod._consume_material = die_on_second
    try:
        await prod.complete_work_order(wo3["id"], {"entity_id": ENT}, T)
    except asyncio.CancelledError:
        pass
    finally:
        prod._consume_material = real_consume
    w3 = await db.mfg_work_orders.find_one({"id": wo3["id"]}, {"_id": 0})
    part = await net_consumed(db, wo3["id"])
    check("PROD-06", "dibunuh di tengah: stage 'consuming', batik terambil sebagian, kunci aktif tanpa failed_at",
          (w3.get("completion") or {}).get("stage") == "consuming" and part == {BATIK: 4.0}
          and w3.get("saga_lock") and not w3["saga_lock"].get("failed_at"), (part, (w3.get("completion") or {}).get("stage")))
    early = await c.post(f"/api/saga-locks/mfg_work_orders/{wo3['id']}/release", headers=h,
                         json={"reason": f"{T} terlalu dini", "acknowledge_effects": True})
    check("PROD-06", "kunci yang masih 'aktif' tidak bisa dilepas (409)", early.status_code == 409, early.status_code)
    await db.mfg_work_orders.update_one({"id": wo3["id"]}, {"$set": {"saga_lock.started_at": "2026-01-01T00:00:00+00:00"}})
    rel = await c.post(f"/api/saga-locks/mfg_work_orders/{wo3['id']}/release", headers=h,
                       json={"reason": f"{T} proses mati", "acknowledge_effects": True})
    done = await c.post(f"/api/production/work-orders/{wo3['id']}/complete", headers=h)
    w3 = await db.mfg_work_orders.find_one({"id": wo3["id"]}, {"_id": 0})
    check("PROD-06", "sesudah lepas kunci, ulang membalik sisa konsumsi lama lalu konsumsi penuh SEKALI",
          rel.status_code == 200 and done.status_code == 200 and w3["status"] == "completed"
          and await net_consumed(db, wo3["id"]) == {BATIK: 4.0, LURIK: 8.0}, (rel.status_code, done.status_code, await net_consumed(db, wo3["id"])))
    rev = await db.inventory_movements.count_documents({"source_document": wo3["id"], "movement_type": "production_consume_reversal"})
    check("PROD-06", "jejak pembalikan tercatat (mutasi production_consume_reversal)", rev >= 1, rev)


async def main():
    import httpx
    from db import db
    full = snapshot_stock(["inventory_rolls", "inventory_balances", "inventory_movements", "inventory_lots", "number_sequences"])
    ids = snapshot_new_ids(NEW)
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8009", timeout=120) as c:
        r = await c.post("/api/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
        h = {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}
        try:
            await run(c, h, db)
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check("PROD", "eksekusi skenario", False, repr(exc)[:200])
        finally:
            purge_new_ids(ids, verbose=False)
            restore_stock(full)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
