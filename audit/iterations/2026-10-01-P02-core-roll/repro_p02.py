"""P02 invariants (WM-01, AX-07, AX-05, FN-03, IX-13, GN-12, GN-13) — real service functions, LOCAL synthetic DB.

Usage: cd /app/backend && python ../audit/iterations/2026-10-01-P02-core-roll/repro_p02.py
All synthetic rolls/products use id prefix `audit_p02_*` and are removed at the end.
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
    from services import roll_service as rs
    from services import costing_service as cs
    T = f"audit_p02_{uuid.uuid4().hex[:6]}"
    A, W1, W2 = "ent_ksc", "wh_jakarta", "wh_bandung"
    pid = f"{T}_prod"
    await db.products.insert_one({"id": pid, "sku": f"SKU-{T}", "name": "Synthetic P02", "base_unit": "meter", "price": 100000})

    def roll(i, **kw):
        d = {"id": f"{T}_r{i}", "roll_no": f"R-{T}-{i}", "product_id": pid, "warehouse_id": W1, "owner_entity_id": A,
             "status": "available", "length_initial": 10.0, "length_remaining": 10.0, "unit": "meter",
             "unit_cost": 50000.0, "lot": "L1", "created_at": "2026-10-01T00:00:00+00:00"}
        d.update(kw)
        return d
    try:
        # WM-01 — 5 potongan bersamaan 1 m dari roll 10 m: konservasi panjang
        r0 = roll(0)
        await db.inventory_rolls.insert_one(dict(r0))
        outs = await asyncio.gather(*[rs._split_roll(r0, 1.0, f"so_{T}_{k}") for k in range(5)], return_exceptions=True)
        parent = await db.inventory_rolls.find_one({"id": r0["id"]}, {"_id": 0})
        errs = [repr(o)[:80] for o in outs if isinstance(o, Exception)]
        kids = await db.inventory_rolls.find({"parent_roll_id": r0["id"]}, {"_id": 0}).to_list(None)
        total = round(parent["length_remaining"] + sum(k["length_remaining"] for k in kids), 2)
        check("WM-01", "concurrent splits conserve length (parent+children == 10)", total == 10.0 and len(kids) == 5,
              {"parent": parent["length_remaining"], "children": len(kids), "sum": total, "errors": errs})

        # AX-07 — 3 generasi: parent langsung benar, root tetap
        child = kids[0]
        await db.inventory_rolls.update_one({"id": child["id"]}, {"$set": {"status": "available", "reserved_ref": None}})
        child = await db.inventory_rolls.find_one({"id": child["id"]}, {"_id": 0})
        grand = await rs._split_roll(child, 0.5, f"so_{T}_g")
        check("AX-07", "grandchild.parent_roll_id == child (direct parent)", grand and grand.get("parent_roll_id") == child["id"],
              {"grand_parent": (grand or {}).get("parent_roll_id"), "child": child["id"], "root": (grand or {}).get("root_roll_id")})
        check("AX-07", "grandchild.root_roll_id == root", grand and grand.get("root_roll_id") == r0["id"], (grand or {}).get("root_roll_id"))

        # AX-05 — terima transfer intra-entitas: acquired asal PO tetap, bin lama dikosongkan
        r1 = roll(1, status="in_transit_transfer", reserved_ref={"type": "wh_transfer", "id": f"tr_{T}"}, bin_id="BIN-W1",
                  acquired={"via": "purchase", "ref_id": f"po_{T}", "date": "2026-10-01"})
        await db.inventory_rolls.insert_one(dict(r1))
        await rs.receive_wh_transfer_rolls(f"tr_{T}", W2)
        r1b = await db.inventory_rolls.find_one({"id": r1["id"]}, {"_id": 0})
        check("AX-05", "transfer keeps acquisition origin (PO)", (r1b.get("acquired") or {}).get("ref_id") == f"po_{T}", r1b.get("acquired"))
        check("AX-05", "source bin not carried to destination warehouse", r1b.get("warehouse_id") == W2 and not r1b.get("bin_id"),
              {"wh": r1b.get("warehouse_id"), "bin": r1b.get("bin_id")})
        from services.landed_cost_service import resolve_target_rolls
        tgt = [x["id"] for x in await resolve_target_rolls([f"po_{T}"], A)]
        check("AX-05", "late landed cost still targets transferred roll", r1["id"] in tgt, tgt)

        # FN-03 — WAC lintas unit: roll 10 yard @ 45.720/yard (=50.000/m) + roll 10 m @ 50.000/m → WAC 50.000/m
        await db.inventory_rolls.delete_many({"product_id": pid})
        await db.inventory_rolls.insert_many([roll(10), roll(11, unit="yard", unit_cost=45720.0)])
        w = await cs.wac_for_product(pid, A, use_cache=False)
        check("FN-03", "WAC converts yard to base unit (≈50.000/m)", abs(float(w.get("wac") or 0) - 50000.0) < 1.0, w.get("wac"))

        # GN-13 — unit tak terkonversi tidak dicampur; saldo ditandai invalid
        await db.inventory_rolls.insert_one(roll(12, unit="unitgaib"))
        bal = await rs.rebuild_balance(pid, W1, A)
        check("GN-13", "unconvertible roll excluded + projection_valid False",
              bal.get("projection_valid") is False and abs(bal.get("available_qty", 0) - 19.14) < 0.05,
              {"available": bal.get("available_qty"), "valid": bal.get("projection_valid")})
        # GN-13 — rebuild lama (tiket kecil) tidak menimpa hasil yang lebih baru
        seg = {"product_id": pid, "warehouse_id": W1, "owner_entity_id": A}
        cur = await db.inventory_balances.find_one(seg, {"_id": 0})
        res = await db.inventory_balances.update_one(
            {**seg, "$or": [{"rebuild_applied": {"$lt": 1}}, {"rebuild_applied": {"$exists": False}}]},
            {"$set": {"available_qty": 999.0}})
        check("GN-13", "stale rebuild write (older ticket) is rejected", res.modified_count == 0 and cur.get("rebuild_applied", 0) >= 1,
              {"modified": res.modified_count, "applied": cur.get("rebuild_applied")})

        # GN-12 — WAC atas >5000 roll: tidak terpotong
        await db.inventory_rolls.delete_many({"product_id": pid})
        docs = [roll(1000 + i, unit_cost=10000.0) for i in range(5001)] + [roll(9999, unit_cost=10010000.0)]
        await db.inventory_rolls.insert_many(docs)
        w = await cs.wac_for_product(pid, A, use_cache=False)
        exp = (5001 * 10000.0 + 10010000.0) / 5002
        check("GN-12", "WAC over 5002 rolls includes the last roll", abs(float(w.get("wac") or 0) - exp) < 1.0, [w.get("wac"), round(exp, 2)])

        # IX-13 — konversi hitung manual penerimaan kanonik
        from services import receiving_roll_service as rr
        eng = await rr.uom_engine()
        prod_cm = {"id": pid, "base_unit": "cm"}
        check("IX-13", "100 cm → 1 meter via canonical converter", abs(rr.conv_qty(prod_cm, 100, "cm", "meter", eng) - 1.0) < 1e-6,
              rr.conv_qty(prod_cm, 100, "cm", "meter", eng))
        try:
            rr.conv_qty(prod_cm, 100, "unitgaib", "meter", eng)
            check("IX-13", "unknown unit rejected before roll/tag/counter", False, "no error")
        except Exception as exc:  # noqa: BLE001
            check("IX-13", "unknown unit rejected before roll/tag/counter", getattr(exc, "status_code", 0) == 400, repr(exc)[:120])
        src = open("services/receiving_roll_service.py").read()
        check("IX-13", "create_counted_roll/scan-label no longer use local _LEN_FACTOR for task qty",
              "from_meter(to_meter(length_base" not in src and "_from_meter(length_m, task_unit)" not in src, "static")
    except Exception as exc:  # noqa: BLE001
        check("SCRIPT", "script error", False, repr(exc))
    finally:
        await db.inventory_rolls.delete_many({"product_id": pid})
        await db.inventory_balances.delete_many({"product_id": pid})
        await db.inventory_movements.delete_many({"product_id": pid})
        await db.products.delete_one({"id": pid})


asyncio.run(main())
print(json.dumps(results, indent=1, ensure_ascii=False))
print(f"SUMMARY pass={sum(r['pass'] for r in results)} fail={sum(not r['pass'] for r in results)}")
sys.exit(0 if all(r["pass"] for r in results) else 1)
