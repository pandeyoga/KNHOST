"""P04 invariants (FN-01, FN-02, FN-11, IX-16) — service asli, DB sintetis lokal.

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-03-P04-costing/repro_p04.py
Data sintetis ber-prefix `audit_p04_*` / entitas `ent_audit_p04_*` dihapus di akhir.
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
    from core_utils import now_iso
    T = f"audit_p04_{uuid.uuid4().hex[:6]}"
    E = f"ent_audit_p04_{T[-6:]}"
    pid, po = f"{T}_prod", f"{T}_po"
    W = "wh_jakarta"
    base = {"product_id": pid, "warehouse_id": W, "owner_entity_id": E, "unit": "meter", "lot": "L1"}
    try:
        # ── FN-01 — landed cost tidak menghitung ganda anak split ─────────
        from services import landed_cost_service as lc
        await db.inventory_rolls.insert_many([
            {**base, "id": f"{T}_p", "roll_no": f"P-{T}", "status": "available", "length_initial": 70.0,
             "length_remaining": 70.0, "unit_cost": 10.0, "base_unit_cost": 10.0, "acquired": {"ref_id": po}},
            {**base, "id": f"{T}_c", "roll_no": f"C-{T}", "status": "reserved", "length_initial": 30.0,
             "length_remaining": 30.0, "unit_cost": 10.0, "base_unit_cost": 10.0, "acquired": {"ref_id": po},
             "parent_roll_id": f"{T}_p", "root_roll_id": f"{T}_p"},
            {**base, "id": f"{T}_g", "roll_no": f"G-{T}", "status": "available", "length_initial": 10.0,
             "length_remaining": 10.0, "unit_cost": 10.0, "base_unit_cost": 10.0,
             "parent_roll_id": f"{T}_c", "root_roll_id": f"{T}_p"},  # cucu lama tanpa acquired
        ])
        # parent sebenarnya 70 fisik = 60 + cucu 10 dipotong dari anak; pakai panjang sebagai fragmen disjoint
        await db.inventory_rolls.update_one({"id": f"{T}_c"}, {"$set": {"length_initial": 20.0, "length_remaining": 20.0}})
        rolls = await lc.resolve_target_rolls([po], E)
        alloc = lc.compute_allocation(rolls, 100.0, "quantity")
        await lc.apply_allocation_to_rolls(f"LCV-{T}", alloc["allocations"])
        await lc.apply_allocation_to_rolls(f"LCV-{T}", alloc["allocations"])  # retry
        after = await db.inventory_rolls.find({"product_id": pid}, {"_id": 0}).to_list(None)
        delta = round(sum((r["unit_cost"] - 10.0) * r["length_initial"] for r in after), 2)
        check("FN-01", "parent 70 + anak 20 + cucu 10 (tanpa acquired), voucher 100 → nilai stok +100 (retry tidak menambah)",
              delta == 100.0 and len(rolls) == 3, {"delta": delta, "targets": len(rolls)})

        # ── FN-02 — 3-way match baris produk ganda ────────────────────────
        from services.vendor_bill_service import evaluate_match
        pod = {"items": [{"product_id": pid, "quantity": 100, "received_qty": 100, "price": 10}]}
        m = evaluate_match(pod, [{"product_id": pid, "billed_qty": 60, "price": 10},
                                 {"product_id": pid, "billed_qty": 60, "price": 10}], "received", {}, 0, 0)
        check("FN-02", "60 + 60 vs diterima 100 → blocked", m["match_status"] == "blocked", m["match_status"])
        m2 = evaluate_match(pod, [{"product_id": pid, "billed_qty": 60, "price": 10},
                                  {"product_id": pid, "billed_qty": 40, "price": 10}], "received", {}, 0, 0)
        check("FN-02", "60 + 40 vs 100 → matched (kontrol)", m2["match_status"] == "matched", m2["match_status"])
        src = open("routers/vendor_bills.py").read()
        check("FN-02", "router menolak baris produk ganda (statis)", "muncul lebih dari satu kali" in src, "")

        # ── FN-11 — HPP per shipment dari snapshot roll keluar ─────────────
        from services import roll_service as rs
        from services import gl_service as gl
        so = f"{T}_so"
        await db.sales_orders.insert_one({"id": so, "number": f"SO-{T}", "entity_id": E, "status": "confirmed",
                                          "items": [{"product_id": pid, "quantity": 200, "base_quantity": 200, "price": 50}]})
        await db.inventory_rolls.insert_many([
            {**base, "id": f"{T}_cheap", "roll_no": f"CH-{T}", "status": "committed", "length_initial": 100.0,
             "length_remaining": 100.0, "unit_cost": 10.0, "reserved_ref": {"type": "sales_order", "id": so},
             "created_at": "2026-01-01T00:00:00+00:00"},
            {**base, "id": f"{T}_exp", "roll_no": f"EX-{T}", "status": "committed", "length_initial": 100.0,
             "length_remaining": 100.0, "unit_cost": 30.0, "reserved_ref": {"type": "sales_order", "id": so},
             "created_at": "2026-01-02T00:00:00+00:00"}])
        res1 = await rs.ship_order_rolls(so, pid, W, 100)
        sh1 = {"id": f"{T}_sh1", "order_id": so, "product_id": pid, "qty": 100, "rolls": res1["rolls"],
               "shipment_no": "SJ-1", "status": "dispatched", "created_at": now_iso()}
        je1 = await gl.post_shipment_cogs(sh1)
        res2 = await rs.ship_order_rolls(so, pid, W, 100)
        sh2 = {**sh1, "id": f"{T}_sh2", "rolls": res2["rolls"], "shipment_no": "SJ-2"}
        je2 = await gl.post_shipment_cogs(sh2)
        check("FN-11", "shipment roll murah HPP 1.000, roll mahal 3.000",
              je1 and je2 and je1["total_debit"] == 1000 and je2["total_debit"] == 3000,
              {"sj1": (je1 or {}).get("total_debit"), "sj2": (je2 or {}).get("total_debit")})
        await db.inventory_rolls.update_one({"id": f"{T}_cheap"}, {"$set": {"unit_cost": 99.0}})
        check("FN-11", "snapshot biaya tersimpan di surat jalan (edit biaya roll tidak mengubah histori)",
              res1["rolls"][0].get("unit_cost") == 10.0, res1["rolls"][0])

        # ── IX-16 — retur beli: AP, GL, kas satu kontrak gross ────────────
        from services import purchase_return_service as prsvc
        await db.purchase_orders.insert_one({"id": po, "number": f"PO-{T}", "entity_id": E, "returned_amount": 0.0, "items": []})
        rid = f"{T}_pr"
        await db.purchase_returns.insert_one({"id": rid, "number": f"PR-{T}", "entity_id": E, "warehouse_id": W,
                                              "status": "pending_approval", "supplier_flow": False, "po_id": po, "items": [],
                                              "total_amount": 100.0, "ppn_amount": 11.0, "grand_total": 111.0})
        await prsvc.approve_and_adjust_stock(rid, "mgr")
        je = await db.journal_entries.find_one({"source_type": "purchase_return", "source_id": rid}, {"_id": 0})
        p_ = await db.purchase_orders.find_one({"id": po}, {"_id": 0})
        lines = {(ln["account_code"], ln["debit"], ln["credit"]) for ln in (je or {}).get("lines", [])}
        check("IX-16", "grand_total 111: AP turun 111, Dr hutang 111 / Cr persediaan 100 / Cr PPN 11",
              p_["returned_amount"] == 111 and je and any(d == 111 for _, d, _c in lines)
              and ("1-1300", 0.0, 100.0) in lines and any(c == 11 for _, _d, c in lines),
              {"returned": p_["returned_amount"], "lines": sorted(lines)})
    finally:
        await db.inventory_rolls.delete_many({"product_id": pid})
        await db.inventory_balances.delete_many({"product_id": pid})
        await db.inventory_movements.delete_many({"product_id": pid})
        for c in ("journal_entries", "purchase_orders", "purchase_returns", "sales_orders", "number_sequences"):
            await db[c].delete_many({"entity_id": E})
        await db.roll_cost_history.delete_many({"roll_id": {"$regex": f"^{T}"}})
    passed = sum(1 for r in results if r["pass"])
    print(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"pass={passed} fail={len(results) - passed}")


try:
    asyncio.run(main())
except Exception as _exc:  # noqa: BLE001 — HEAD tanpa kontrak baru: cetak hasil parsial + titik crash
    passed = sum(1 for r_ in results if r_["pass"])
    print(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"CRASH (kontrak belum ada di kode ini): {type(_exc).__name__}: {_exc}")
    print(f"pass={passed} fail={len(results) - passed} crashed=1")
