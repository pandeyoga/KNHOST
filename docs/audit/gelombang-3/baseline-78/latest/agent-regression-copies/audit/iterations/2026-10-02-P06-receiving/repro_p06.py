"""P06 invariants (AX-08, WM-03, WM-04, WM-05, WM-09, IX-09) — service asli, DB sintetis lokal.

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-02-P06-receiving/repro_p06.py
Data sintetis ber-prefix `audit_p06_*` dihapus di akhir.
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


def err(exc):
    return getattr(exc, "status_code", 0), getattr(exc, "detail", str(exc))


async def main():
    from db import db
    from services import putaway_order_service as pa
    T = f"audit_p06_{uuid.uuid4().hex[:6]}"
    A = "ent_ksc"
    WA, WB = f"{T}_whA", f"{T}_whB"
    pid = f"{T}_prod"
    await db.warehouses.insert_many([{"id": WA, "name": "Transit P06", "roles": ["transit"], "active": True},
                                     {"id": WB, "name": "Store P06", "roles": ["storage"], "active": True}])
    await db.products.insert_one({"id": pid, "sku": f"SKU-{T}", "name": "Synthetic P06", "base_unit": "meter", "category": "kain"})

    async def roll(i, **kw):
        d = {"id": f"{T}_r{i}", "roll_no": f"R-{T}-{i}", "product_id": pid, "warehouse_id": WA, "owner_entity_id": A,
             "status": "available", "length_initial": 10.0, "length_remaining": 10.0, "unit": "meter",
             "rfid_tag_id": f"{T}_tag{i}", "journey": {"stage": "tag_verified", "routing": "store"}, "lot": "L1"}
        d.update(kw)
        await db.inventory_rolls.insert_one(dict(d))
        await db.rfid_tags.insert_one({"id": d["rfid_tag_id"], "epc": f"EPC{T}{i}".upper(), "roll_id": d["id"],
                                       "status": "active", "warehouse_id": WA})
        return d
    try:
        r = [await roll(i) for i in range(4)]
        q = await roll(9, status="quarantine")
        # AX-08
        try:
            await pa.create_order(WA, WB, [q["id"]], [A], "tester")
            check("AX-08", "roll quarantine bertag terverifikasi ditolak PA", False, "diterima")
        except Exception as exc:  # noqa: BLE001
            check("AX-08", "roll quarantine bertag terverifikasi ditolak PA", err(exc)[0] == 400, err(exc))
        # WM-05 — dua PA bersamaan satu roll
        outs = await asyncio.gather(pa.create_order(WA, WB, [r[0]["id"]], [A], "a"),
                                    pa.create_order(WA, WB, [r[0]["id"]], [A], "b"), return_exceptions=True)
        wins = [o for o in outs if not isinstance(o, Exception)]
        check("WM-05", "dua PA serentak satu roll: tepat satu menang", len(wins) == 1,
              [err(o) if isinstance(o, Exception) else o["pa_number"] for o in outs])
        pa1 = wins[0]
        # WM-04 — dispatch mengubah bucket
        await pa.dispatch(pa1["id"], [A])
        rr = await db.inventory_rolls.find_one({"id": r[0]["id"]}, {"_id": 0})
        bal = await db.inventory_balances.find_one({"product_id": pid, "warehouse_id": WA, "owner_entity_id": A}, {"_id": 0})
        check("WM-04", "dispatch: roll in_transit_transfer, ATP asal turun, owned tetap",
              rr["status"] == "in_transit_transfer" and bal["available_qty"] == 30 and bal["in_transit_transfer_qty"] == 10
              and bal["owned_qty"] == 50, {"status": rr["status"], **{k: bal.get(k) for k in ("available_qty", "in_transit_transfer_qty", "owned_qty")}})
        # WM-03 — scan kosong
        try:
            await pa.confirm_arrival(pa1["id"], None, [A], "tester")
            check("WM-03", "tanpa scan & tanpa override → 400", False, "diterima")
        except Exception as exc:  # noqa: BLE001
            check("WM-03", "tanpa scan & tanpa override → 400", err(exc)[0] == 400, err(exc))
        try:
            await pa.confirm_arrival(pa1["id"], None, [A], "tester", manual_all=True, reason="x")
            check("WM-03", "override manual tanpa alasan cukup → 400", False, "diterima")
        except Exception as exc:  # noqa: BLE001
            check("WM-03", "override manual tanpa alasan cukup → 400", err(exc)[0] == 400, err(exc))
        o = await pa.confirm_arrival(pa1["id"], [], [A], "tester")
        rr = await db.inventory_rolls.find_one({"id": r[0]["id"]}, {"_id": 0})
        check("WM-03", "scanned_epcs=[] → nol roll pindah, semua exception",
              o["arrived_count"] == 0 and o["exception_count"] == 1 and rr["warehouse_id"] == WA and not o.get("btg_number"),
              {"arrived": o["arrived_count"], "wh": rr["warehouse_id"]})
        # WM-09 — accept exception menulis mutasi
        await pa.resolve_exception(pa1["id"], [r[0]["id"]], "accept", [A], "mgr", "handheld scan ulang ok")
        movs = await db.inventory_movements.find({"roll_id": r[0]["id"], "reference_id": pa1["id"]}, {"_id": 0}).to_list(None)
        rr = await db.inventory_rolls.find_one({"id": r[0]["id"]}, {"_id": 0})
        check("WM-09", "accept exception: tepat satu pasangan out/in + roll di tujuan available",
              sorted(m["movement_type"] for m in movs) == ["putaway_transfer_in", "putaway_transfer_out"]
              and rr["warehouse_id"] == WB and rr["status"] == "available" and not rr.get("active_movement"),
              [m["movement_type"] for m in movs])
        try:
            await pa.resolve_exception(pa1["id"], [r[0]["id"]], "accept", [A], "mgr")
        except Exception:  # noqa: BLE001
            pass
        n = await db.inventory_movements.count_documents({"roll_id": r[0]["id"], "reference_id": pa1["id"]})
        check("WM-09", "retry accept tidak menggandakan mutasi", n == 2, n)
        # WM-05 — subset scan + stale roll
        pa2 = await pa.create_order(WA, WB, [r[1]["id"], r[2]["id"], r[3]["id"]], [A], "tester")
        await db.inventory_rolls.update_one({"id": r[3]["id"]}, {"$set": {"status": "reserved"}})  # dipesan sebelum dispatch
        try:
            await pa.dispatch(pa2["id"], [A])
            check("WM-05", "dispatch ditolak bila roll PA berubah status", False, "diterima")
        except Exception as exc:  # noqa: BLE001
            r1 = await db.inventory_rolls.find_one({"id": r[1]["id"]}, {"_id": 0})
            check("WM-05", "dispatch ditolak bila roll PA berubah status (kompensasi all-or-none)",
                  err(exc)[0] == 409 and r1["status"] == "available", {"err": err(exc), "r1": r1["status"]})
        o2 = await pa.confirm_arrival(pa2["id"], [f"EPC{T}1".upper()], [A], "tester")
        r3 = await db.inventory_rolls.find_one({"id": r[3]["id"]}, {"_id": 0})
        check("WM-03", "subset scan memindahkan subset saja", o2["arrived_count"] == 1 and o2["exception_count"] == 2,
              {"arrived": o2["arrived_count"], "exc": o2["exception_count"]})
        check("WM-05", "roll yang berubah status tidak ditimpa lokasinya", r3["warehouse_id"] == WA and r3["status"] == "reserved",
              {"wh": r3["warehouse_id"], "status": r3["status"]})
        # IX-09 — reopen inspeksi mengosongkan milestone retur
        from services import inspection_service as ins
        ret_id, ins_id = f"{T}_ret", f"{T}_ins"
        await db.sales_returns.insert_one({"id": ret_id, "inspect_done_at": "2026-10-01T10:00:00+00:00"})
        await db.inspections.insert_one({"id": ins_id, "status": "done", "ref_doc_type": "sales_return", "ref_doc_id": ret_id,
                                         "lines": [], "history": []})
        try:
            await ins.reopen(ins_id, "Salah input grade, perlu periksa ulang barang", {"name": "tester", "role": "manager"})
            sr = await db.sales_returns.find_one({"id": ret_id}, {"_id": 0})
            check("IX-09", "reopen inspeksi mengosongkan inspect_done_at retur (riwayat disimpan)",
                  sr["inspect_done_at"] == "" and sr.get("inspect_reopen_history"), sr)
        except Exception as exc:  # noqa: BLE001
            check("IX-09", "reopen inspeksi mengosongkan inspect_done_at retur", False, repr(exc)[:200])
        await db.sales_returns.delete_one({"id": ret_id})
        await db.inspections.delete_one({"id": ins_id})
    finally:
        await db.inventory_rolls.delete_many({"product_id": pid})
        await db.rfid_tags.delete_many({"id": {"$regex": f"^{T}"}})
        await db.inventory_balances.delete_many({"product_id": pid})
        await db.inventory_movements.delete_many({"product_id": pid})
        await db.putaway_orders.delete_many({"from_warehouse_id": WA})
        await db.warehouses.delete_many({"id": {"$in": [WA, WB]}})
        await db.products.delete_one({"id": pid})
    passed = sum(1 for r_ in results if r_["pass"])
    print(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"pass={passed} fail={len(results) - passed}")


try:
    asyncio.run(main())
except Exception as _exc:  # noqa: BLE001 — HEAD tanpa kontrak baru: cetak hasil parsial + titik crash
    passed = sum(1 for r_ in results if r_["pass"])
    print(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"CRASH (kontrak belum ada di kode ini): {type(_exc).__name__}: {_exc}")
    print(f"pass={passed} fail={len(results) - passed} crashed=1")
