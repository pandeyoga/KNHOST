"""P16c — kasus planned penerimaan supplier: GRN-02 (batal saat counting lalu batal ulang tanpa efek
tambahan) & GRN-03 (versi basi, entitas asing, surat jalan duplikat ditolak).

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-09-P16-close-coverage/repro_p16c.py
Data uji TEST_P16C; GRN/roll/tugas yang disentuh dikembalikan dari snapshot di akhir.
"""
import asyncio
import json
import sys
import uuid

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
T = f"TEST_P16C_{uuid.uuid4().hex[:6]}"
results = []
grns = []
created_tasks = []
snap_tasks = {}


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def login(c, email, ent="ent_ksc", pwd="demo12345"):
    r = await c.post("/api/auth/login", json={"email": email, "password": pwd})
    return {"Authorization": f"Bearer {r.json().get('token')}", "X-Entity-Id": ent}


async def grn_ready(c, h, db, dn_no, task, non_stock=False):
    r = await c.post("/api/goods-receipts", json={"partner_type": "supplier", "partner_id": task["supplier_id"],
                                                  "warehouse_id": task["warehouse_id"], "po_ids": [task["po_id"]]}, headers=h)
    g = r.json()
    if r.status_code != 200:
        return r, g
    grns.append(g["id"])
    v = lambda: db.goods_receipts.find_one({"id": g["id"]}, {"_id": 0})  # noqa: E731
    cur = await v()
    if cur["status"] == "draft":
        await c.post(f"/api/goods-receipts/{g['id']}/manual-entry", json={"expected_version": cur["version"]}, headers=h)
        cur = await v()
    await c.patch(f"/api/goods-receipts/{g['id']}/dn", json={"expected_version": cur["version"], "number": dn_no,
                                                              "date": "2026-10-09", "recipient_name": T}, headers=h)
    cur = await v()
    if not cur.get("lines"):
        line = ({"is_non_stock": True, "description": f"{T} karton"} if non_stock else
                {"target": {"type": "po_task", "task_id": task["id"]}})
        await c.post(f"/api/goods-receipts/{g['id']}/lines", json={
            "expected_version": cur["version"], "declared": {"qty": 10, "unit": "yard", "rolls": 1},
            "decision": "accept", **line}, headers=h)
        cur = await v()
    return r, cur


async def run(c, h, db):
    task = await db.wms_tasks.find_one({"flow_type": "inbound", "status": "waiting_goods", "entity_id": "ent_ksc",
                                        "received_qty": {"$in": [0, 0.0, None]}}, {"_id": 0})
    po = await db.purchase_orders.find_one({"id": task["po_id"]}, {"_id": 0})
    task = {**task, "supplier_id": po["supplier_id"], "warehouse_id": po["warehouse_id"]}
    snap_tasks[task["id"]] = task
    dn = f"{T}-SJ1"
    r, g1 = await grn_ready(c, h, db, dn, task)
    check("GRN-03", "GRN dibuat & siap hitung (review) dengan SJ + baris target tugas PO",
          r.status_code == 200 and g1.get("status") == "review" and g1.get("lines"), f"{r.status_code} {g1.get('status') if isinstance(g1, dict) else r.text[:150]}")
    stale = await c.post(f"/api/goods-receipts/{g1['id']}/start-count", json={"expected_version": g1["version"] - 1}, headers=h)
    check("GRN-03", "versi basi ditolak 409 STATE_CHANGED", stale.status_code == 409, f"{stale.status_code} {stale.text[:120]}")
    hk = {**h, "X-Entity-Id": "ent_kanda"}
    foreign_r = await c.get(f"/api/goods-receipts/{g1['id']}", headers=hk)
    foreign_w = await c.post(f"/api/goods-receipts/{g1['id']}/cancel", json={"expected_version": g1["version"], "reason": "asing"}, headers=hk)
    g1b = await db.goods_receipts.find_one({"id": g1["id"]}, {"_id": 0, "status": 1})
    check("GRN-03", "konteks entitas lain tidak bisa membaca/membatalkan GRN (403/404), status tetap",
          foreign_r.status_code in (403, 404) and foreign_w.status_code in (403, 404) and g1b["status"] == "review",
          f"{foreign_r.status_code}/{foreign_w.status_code} {g1b['status']}")
    sc = await c.post(f"/api/goods-receipts/{g1['id']}/start-count", json={"expected_version": g1["version"]}, headers=h)
    # fixture: tugas inbound kedua (supplier & PO sama) agar yang diuji murni kunci surat jalan
    t2 = {k: v for k, v in task.items() if k not in ("supplier_id", "warehouse_id", "_id")}
    t2.update({"id": f"wms_{T.lower()}", "warehouse_id": task["warehouse_id"], "grn_ids": []})
    t2.pop("grn_active_id", None)
    await db.wms_tasks.insert_one(dict(t2))
    created_tasks.append(t2["id"])
    _, g2 = await grn_ready(c, h, db, f" {dn.lower().replace('-', '/')} ", {**task, "id": t2["id"]})
    dup = await c.post(f"/api/goods-receipts/{g2['id']}/start-count", json={"expected_version": g2["version"]}, headers=h)
    check("GRN-03", "surat jalan yang sama (beda huruf/tanda baca) dari supplier sama ditolak 409 DN_DUPLICATE",
          sc.status_code == 200 and dup.status_code == 409 and "DN_DUPLICATE" in dup.text, f"start={sc.status_code} dup={dup.status_code} {dup.text[:150]}")

    # GRN-02 — batal saat counting, lalu batal ulang
    cur = await db.goods_receipts.find_one({"id": g1["id"]}, {"_id": 0})
    rolls0 = await db.inventory_rolls.count_documents({})
    movs0 = await db.inventory_movements.count_documents({})
    c1 = await c.post(f"/api/goods-receipts/{g1['id']}/cancel", json={"expected_version": cur["version"], "reason": f"{T} batal"}, headers=h)
    t_after = await db.wms_tasks.find_one({"id": task["id"]}, {"_id": 0})
    g_after = await db.goods_receipts.find_one({"id": g1["id"]}, {"_id": 0})
    check("GRN-02", "batal saat counting → cancelled, kunci SJ dilepas, tugas PO bebas lagi",
          c1.status_code == 200 and g_after["status"] == "cancelled" and not g_after.get("active_key")
          and t_after.get("grn_active_id") in (None, ""), f"{c1.status_code} {g_after['status']} task_lock={t_after.get('grn_active_id')}")
    c2 = await c.post(f"/api/goods-receipts/{g1['id']}/cancel", json={"expected_version": g_after["version"], "reason": f"{T} batal ulang"}, headers=h)
    g_again = await db.goods_receipts.find_one({"id": g1["id"]}, {"_id": 0})
    check("GRN-02", "batal ulang tidak menambah efek: status, versi, roll & mutasi tetap",
          c2.status_code in (200, 400, 409) and g_again["status"] == "cancelled" and g_again["version"] == g_after["version"]
          and await db.inventory_rolls.count_documents({}) == rolls0 and await db.inventory_movements.count_documents({}) == movs0,
          f"{c2.status_code} v {g_after['version']}→{g_again['version']}")
    sc2 = await c.post(f"/api/goods-receipts/{g2['id']}/start-count", json={"expected_version": (await db.goods_receipts.find_one({"id": g2['id']}))["version"]}, headers=h)
    check("GRN-02", "setelah GRN batal, SJ yang sama boleh dihitung di kedatangan lain", sc2.status_code == 200, f"{sc2.status_code} {sc2.text[:120]}")


async def cleanup(db):
    from services.goods_receipt_service import release_tasks
    for g in grns:
        await release_tasks(g)
    for tid, t in snap_tasks.items():
        t = {k: v for k, v in t.items() if k not in ("supplier_id",)} if "supplier_id" not in (await db.wms_tasks.find_one({"id": tid}, {"_id": 0}) or {}) else t
        await db.wms_tasks.update_one({"id": tid}, {"$unset": {"grn_active_id": "", "grn_active_number": ""}, "$pull": {"grn_ids": {"$in": grns}}})
    await db.wms_tasks.update_many({"grn_ids": {"$in": grns}}, {"$unset": {"grn_active_id": "", "grn_active_number": ""}, "$pull": {"grn_ids": {"$in": grns}}})
    await db.wms_tasks.delete_many({"id": {"$in": created_tasks}})
    await db.goods_receipts.delete_many({"id": {"$in": grns}})
    await db.doc_refs.delete_many({"$or": [{"from_id": {"$in": grns}}, {"to_id": {"$in": grns}}]})
    await db.audit_logs.delete_many({"entity_id": {"$in": grns}})


async def main():
    import httpx
    from db import db
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8009", timeout=120) as c:
        h = await login(c, "admin@kainnusantara.id")
        try:
            await run(c, h, db)
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check("GRN", "eksekusi skenario", False, repr(exc)[:200])
        finally:
            await cleanup(db)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
