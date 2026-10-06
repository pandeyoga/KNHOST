"""P17g — DESIGN-05: biaya bahan/trial sample ⇄ stok ⇄ GL terekonsiliasi (termasuk ambil bersamaan).

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-03-P17-planned-coverage/repro_p17g.py
Sample & roll yang disentuh dipulihkan dari snapshot; jurnal/mutasi/audit baru dibuang.
"""
import asyncio
import json
import sys

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402

ENT = "ent_ksc"
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def run(c, h, db):
    smp = await db.md_samples.find_one({"entity_id": ENT, "status": {"$in": ["sent", "in_progress"]}}, {"_id": 0})
    roll = await db.inventory_rolls.find_one({"owner_entity_id": ENT, "status": "available", "length_remaining": {"$gt": 20},
                                              "unit_cost": {"$gt": 0}, "length_reserved": {"$in": [0, None]}}, {"_id": 0})
    snap = {k: smp.get(k) for k in ("material_issues", "timeline", "cost_total", "updated_at")}
    try:
        cost0 = float(smp.get("cost_total") or 0)
        r = await c.post(f"/api/rnd/samples/{smp['id']}/issue-material", headers=h, json={"roll_id": roll["id"], "qty": 2.5, "note": "TEST_P17G"})
        s1 = await db.md_samples.find_one({"id": smp["id"]}, {"_id": 0})
        mi = (s1.get("material_issues") or [])[-1]
        exp = round(roll["unit_cost"] * 2.5, 2)
        check("DESIGN-05", "ambil bahan 2,5: biaya = unit_cost × qty, cost_total sample naik sebesar itu",
              r.status_code == 200 and mi["cost"] == exp and round(s1["cost_total"] - cost0, 2) == exp, (r.status_code, mi.get("cost"), exp))
        r1 = await db.inventory_rolls.find_one({"id": roll["id"]}, {"_id": 0})
        mov = await db.inventory_movements.find_one({"id": mi["movement_id"]}, {"_id": 0})
        check("DESIGN-05", "stok: roll berkurang 2,5 + mutasi sample_issue -2,5 ber-referensi sample",
              round(roll["length_remaining"] - r1["length_remaining"], 3) == 2.5 and mov["quantity"] == -2.5
              and mov["reference_id"] == smp["id"], (r1["length_remaining"], mov and mov["quantity"]))
        je = await db.journal_entries.find_one({"id": mi["journal_id"]}, {"_id": 0})
        dr = {ln["account_code"]: round(ln["debit"] - ln["credit"], 2) for ln in (je or {}).get("lines", [])}
        check("DESIGN-05", "GL: Dr 6-7000 Beban Sample / Cr 1-1300 Persediaan = biaya bahan",
              dr.get("6-7000") == exp and dr.get("1-1300") == -exp, dr)
        a, b = await asyncio.gather(
            c.post(f"/api/rnd/samples/{smp['id']}/issue-material", headers=h, json={"roll_id": roll["id"], "qty": 1, "note": "TEST_P17G a"}),
            c.post(f"/api/rnd/samples/{smp['id']}/issue-material", headers=h, json={"roll_id": roll["id"], "qty": 1, "note": "TEST_P17G b"}))
        s2 = await db.md_samples.find_one({"id": smp["id"]}, {"_id": 0})
        r2 = await db.inventory_rolls.find_one({"id": roll["id"]}, {"_id": 0})
        n_ok = [a.status_code, b.status_code].count(200)
        movs = await db.inventory_movements.count_documents({"reference_id": smp["id"], "movement_type": "sample_issue", "roll_id": roll["id"]})
        check("DESIGN-05", "dua ambil bersamaan pada roll sama: hasil roll = Σ yang sukses (tanpa lost update)",
              round(r1["length_remaining"] - r2["length_remaining"], 3) == n_ok and len(s2["material_issues"]) - len(s1["material_issues"]) == n_ok
              and movs == 1 + n_ok, (a.status_code, b.status_code, r2["length_remaining"], movs))
        tot_mi = round(sum(m["cost"] for m in s2["material_issues"]), 2)
        tot_je = 0.0
        for m in s2["material_issues"]:
            j = await db.journal_entries.find_one({"id": m.get("journal_id")}, {"_id": 0, "total_debit": 1}) or {}
            tot_je += float(j.get("total_debit") or 0)
        rounds = round(sum(float(x.get("cost") or 0) for x in s2.get("rounds") or []), 2)
        check("DESIGN-05", "rekonsiliasi: Σ biaya bahan = Σ jurnal; cost_total = biaya round + bahan",
              round(tot_je, 2) == tot_mi and round(s2["cost_total"], 2) == round(rounds + tot_mi, 2), (tot_mi, round(tot_je, 2), s2["cost_total"], rounds))
        over = await c.post(f"/api/rnd/samples/{smp['id']}/issue-material", headers=h, json={"roll_id": roll["id"], "qty": 99999})
        check("DESIGN-05", "ambil melebihi sisa roll ditolak 400 tanpa efek", over.status_code == 400
              and (await db.inventory_rolls.find_one({"id": roll["id"]}))["length_remaining"] == r2["length_remaining"], over.status_code)
    finally:
        await db.md_samples.update_one({"id": smp["id"]}, {"$set": snap})


async def main():
    import httpx
    from db import db
    full = snapshot_stock(["inventory_rolls", "inventory_balances", "inventory_movements", "inventory_lots", "number_sequences"])
    ids = snapshot_new_ids(["journal_entries", "gl_postings", "audit_logs", "notifications"])
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8009", timeout=120) as c:
        r = await c.post("/api/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
        h = {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}
        try:
            await run(c, h, db)
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check("DESIGN-05", "eksekusi skenario", False, repr(exc)[:200])
        finally:
            purge_new_ids(ids, verbose=False)
            restore_stock(full)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
