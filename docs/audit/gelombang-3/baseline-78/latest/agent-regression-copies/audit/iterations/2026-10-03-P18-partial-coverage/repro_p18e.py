"""P18e — INV-03: cycle count menjaga cutoff (expected beku), stok bergerak → 409, HITUNG ULANG (reopen,
endpoint baru) → expected baru, approve bersamaan → penyesuaian tepat sekali.

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-03-P18-partial-coverage/repro_p18e.py
Self-clean: roll/saldo/PO dipulihkan dari snapshot; dokumen baru dihapus.
"""
import asyncio
import json
import sys
import uuid

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402

T = f"TEST_P18E_{uuid.uuid4().hex[:6]}"
ENT, WH, PID = "ent_ksc", "wh_jakarta", "prod_tenun_ikat"
results = []
NEW = ["cycle_count_sessions", "purchase_returns", "journal_entries", "inventory_movements", "audit_logs", "notifications",
       "stock_adjustments", "saga_locks", "gl_outbox", "posting_failures", "roll_cost_history"]


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def run(c, h, db):
    from services import stock_count_service as scs
    q0 = await scs.scope_qty(PID, WH, ENT, "")
    s = (await c.post("/api/cycle-count/sessions", json={"warehouse_id": WH, "name": T}, headers=h)).json()
    sid = s["id"]
    await c.post(f"/api/cycle-count/sessions/{sid}/items", json={"product_id": PID, "owner_entity_id": ENT}, headers=h)
    s = await db.cycle_count_sessions.find_one({"id": sid}, {"_id": 0})
    item = s["items"][0]
    await c.patch(f"/api/cycle-count/sessions/{sid}/items/{item['id']}", json={"actual_qty": q0 - 2, "notes": T}, headers=h)
    sub = await c.post(f"/api/cycle-count/sessions/{sid}/submit", headers=h)
    check("INV-03", "expected dibekukan saat item ditambah (cutoff) & submit mencatat selisih −2",
          float(item["expected_qty"]) == q0 and sub.status_code == 200 and sub.json()["discrepancies"][0]["difference"] == -2,
          (item.get("expected_qty"), q0, sub.status_code))
    roll = await db.inventory_rolls.find_one({"product_id": PID, "warehouse_id": WH, "owner_entity_id": ENT, "status": "available",
                                              "length_reserved": {"$not": {"$gt": 0}}, "length_remaining": {"$gte": 5}}, {"_id": 0})
    pr = await c.post("/api/purchase-returns", json={"supplier_id": "sup_a14677b676a6", "warehouse_id": WH, "notes": T, "submit_now": True,
                                                     "items": [{"product_id": PID, "quantity": 1, "unit": "yard", "price": 1000, "roll_ids": [roll["id"]]}]}, headers=h)
    pa = await c.post(f"/api/purchase-returns/{pr.json().get('id')}/approve", json={}, headers=h)
    q1 = await scs.scope_qty(PID, WH, ENT, "")
    ap = await c.post(f"/api/cycle-count/sessions/{sid}/approve", json={}, headers=h)
    check("INV-03", "stok bergerak sesudah dihitung (retur 1 yd) → approve 409, stok tidak disesuaikan",
          pa.status_code == 200 and q1 == q0 - 1 and ap.status_code == 409 and await scs.scope_qty(PID, WH, ENT, "") == q1,
          (pa.status_code, q0, q1, ap.status_code, ap.text[:120]))
    ro = await c.post(f"/api/cycle-count/sessions/{sid}/reopen", headers=h)
    rj = ro.json()
    it = rj.get("items", [{}])[0]
    blocked = await c.post(f"/api/cycle-count/sessions/{sid}/submit", headers=h)
    check("INV-03", "hitung ulang (reopen): sesi open, expected = stok terkini, item wajib dihitung lagi (submit 400)",
          ro.status_code == 200 and rj["status"] == "open" and float(it["expected_qty"]) == q1 and it["status"] == "pending"
          and it.get("recount_no") == 1 and blocked.status_code == 400, (ro.status_code, ro.text[:120], blocked.status_code))
    await c.patch(f"/api/cycle-count/sessions/{sid}/items/{item['id']}", json={"actual_qty": q1 - 2, "notes": f"{T} ulang"}, headers=h)
    await c.post(f"/api/cycle-count/sessions/{sid}/submit", headers=h)
    outs = await asyncio.gather(*(c.post(f"/api/cycle-count/sessions/{sid}/approve", json={}, headers=h) for _ in range(3)))
    q2 = await scs.scope_qty(PID, WH, ENT, "")
    doc = await db.cycle_count_sessions.find_one({"id": sid}, {"_id": 0})
    check("INV-03", "approve 3× bersamaan → tepat 1 sukses, stok turun tepat 2 (sekali), sesi approved",
          sorted(o.status_code for o in outs).count(200) == 1 and round(q1 - q2, 2) == 2 and doc["status"] == "approved",
          ([o.status_code for o in outs], q1, q2, doc["status"]))
    again = await c.post(f"/api/cycle-count/sessions/{sid}/reopen", headers=h)
    check("INV-03", "sesi approved tidak bisa dibuka ulang (400)", again.status_code == 400, again.status_code)
    hw = {**h}
    lw = await c.post("/api/auth/login", json={"email": "warehouse@kainnusantara.id", "password": "demo12345"})
    hw["Authorization"] = f"Bearer {lw.json()['token']}"
    s2 = (await c.post("/api/cycle-count/sessions", json={"warehouse_id": WH, "name": f"{T}-2"}, headers=h)).json()
    await c.post(f"/api/cycle-count/sessions/{s2['id']}/items", json={"product_id": PID, "owner_entity_id": ENT}, headers=h)
    s2 = await db.cycle_count_sessions.find_one({"id": s2["id"]}, {"_id": 0})
    await c.patch(f"/api/cycle-count/sessions/{s2['id']}/items/{s2['items'][0]['id']}", json={"actual_qty": q2}, headers=h)
    await c.post(f"/api/cycle-count/sessions/{s2['id']}/submit", headers=h)
    deny = await c.post(f"/api/cycle-count/sessions/{s2['id']}/reopen", headers=hw)
    check("INV-03", "staf gudang (tanpa approve_count) tidak bisa membuka ulang sesi (403)", deny.status_code == 403, deny.status_code)


async def main():
    import httpx
    from db import db
    full = snapshot_stock(["number_sequences", "inventory_rolls", "inventory_balances", "inventory_lots", "purchase_orders"])
    ids = snapshot_new_ids(NEW)
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8009", timeout=120) as c:
        r = await c.post("/api/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
        h = {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}
        try:
            await run(c, h, db)
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check("P18E", "eksekusi", False, repr(exc)[:200])
        purge_new_ids(ids, verbose=False)
        restore_stock(full)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
