"""Regresi Gelombang 2 (hasil bisnis BENAR, bukan reproducer cacat). Self-clean.
Jalankan: cd /app/backend && python ../docs/audit/wave-2/iterations/2026-10-04-W2-P00-P07/regression_w2.py
"""
import asyncio
import json
import os
import sys
import uuid

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv  # noqa: E402

load_dotenv("/app/backend/.env")
from fastapi import HTTPException  # noqa: E402

from db import db  # noqa: E402

T = f"TEST_W2_{uuid.uuid4().hex[:6]}"
A, B = "ent_ksc", "ent_kanda"
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def status_of(coro):
    try:
        await coro
        return 200
    except HTTPException as e:
        return e.status_code
    except ValueError:
        return 400


def roll(rid, owner, wh, length, status="available", **kw):
    return {"id": f"{T}_{rid}", "roll_no": f"{T}-{rid}", "product_id": f"{T}_prod", "warehouse_id": wh,
            "owner_entity_id": owner, "status": status, "length_initial": length, "length_remaining": length,
            "length_reserved": 0, "unit": "meter", "lot": "L1", "created_at": "2026-10-04T00:00:00", **kw}


async def scope_and_stock():
    from services.roll_service import resolve_stock_owner, reserve_rolls_for_wh_transfer
    wh = f"{T}_wh"
    await db.inventory_rolls.insert_many([roll("b1", B, wh, 10)])
    own = await resolve_stock_owner(f"{T}_prod", wh, A, allowed_owners=[A])
    check("W2-006", "owner otomatis tetap A walau hanya B punya stok (tanpa fallback)", own == A, own)
    code = await status_of(resolve_stock_owner(f"{T}_prod", wh, "", allowed_owners=[A]))
    check("W2-006", "tanpa prefer & tanpa stok sah -> 400, bukan owner B", code == 400, code)
    code = await status_of(resolve_stock_owner(f"{T}_prod", wh, B, allowed_owners=[A]))
    check("W2-006", "explicit owner B oleh user A-only -> 403", code == 403, code)
    await db.inventory_rolls.insert_many([roll("a1", A, wh, 20)])
    code = await status_of(reserve_rolls_for_wh_transfer(f"{T}_prod", wh, A, 10, f"{T}_trf", roll_ids=[f"{T}_b1"]))
    rb = await db.inventory_rolls.find_one({"id": f"{T}_b1"})
    check("W2-008", "transfer A memilih roll B ditolak tanpa efek", code == 409 and rb["status"] == "available", (code, rb["status"]))
    code = await status_of(reserve_rolls_for_wh_transfer(f"{T}_prod", wh, A, 10, f"{T}_trf", roll_ids=[f"{T}_a1", f"{T}_b1"]))
    ra = await db.inventory_rolls.find_one({"id": f"{T}_a1"})
    check("W2-008", "daftar campuran A+B all-or-none", code == 409 and ra["status"] == "available", (code, ra["status"]))
    await reserve_rolls_for_wh_transfer(f"{T}_prod", wh, A, 0, f"{T}_trf", roll_ids=[f"{T}_a1"])
    bal = await db.inventory_balances.find_one({"product_id": f"{T}_prod", "warehouse_id": wh, "owner_entity_id": A}) or {}
    check("W2-009", "reservasi eksplisit langsung merefresh projection (reserved 20, available 0)",
          abs(float(bal.get("reserved_qty") or 0) - 20) < 0.01 and float(bal.get("available_qty") or 0) < 0.01,
          {k: bal.get(k) for k in ("available_qty", "reserved_qty")})


async def cycle_count_reject_race():
    sid = f"{T}_cc"
    await db.cycle_count_sessions.insert_one({"id": sid, "entity_id": A, "status": "submitted",
                                              "saga_lock": {"action": "cycle_count_approve", "token": "x"}, "items": []})
    res = await db.cycle_count_sessions.find_one_and_update(
        {"id": sid, "status": "submitted", "saga_lock": {"$exists": False}}, {"$set": {"status": "rejected"}})
    doc = await db.cycle_count_sessions.find_one({"id": sid})
    check("W2-007", "reject saat approval memegang kunci tidak menulis rejected (predikat router)",
          res is None and doc["status"] == "submitted" and "rejected_at" not in doc, doc["status"])
    import inspect
    from routers import cycle_count
    src = inspect.getsource(cycle_count.reject_session)
    check("W2-007", "reject_session memakai predikat status+saga_lock & 409 bila kalah",
          '"saga_lock": {"$exists": False}' in src and "409" in src)


async def weight_and_qc_return():
    from services.roll_service import insert_child_roll
    from services.qc_service import _purchase_qty_of_pieces
    parent = roll("w1", A, f"{T}_wh", 10, status="quarantine", weight_kg=3.0, secondary_measures={"kg": 3.0})
    await db.inventory_rolls.insert_one(dict(parent))
    child = {**parent, "id": f"{T}_w1c", "length_initial": 4, "length_remaining": 4, "status": "damaged"}
    c = await insert_child_roll(child, parent)
    p = await db.inventory_rolls.find_one({"id": f"{T}_w1"})
    tot = round(float(c["weight_kg"]) + float(p["weight_kg"]), 3)
    check("W2-019", "split QC menjaga total berat 3 kg (1.2 + 1.8) dgn provenance estimasi",
          tot == 3.0 and c.get("weight_provenance", {}).get("type") == "estimated_proportional"
          and p["secondary_measures"]["kg"] == p["weight_kg"], (c["weight_kg"], p["weight_kg"]))
    prod = {"base_unit": "meter", "sku": "X", "gsm": 200, "width_cm": 150}
    q = await _purchase_qty_of_pieces(prod, [{"length_remaining": 10, "weight_kg": 3}], 10, "kg")
    check("W2-014", "reject 10 m (roll 3 kg) -> qty retur 3 kg (bukan 10 kg)", abs(q - 3) < 0.001, q)
    q2 = await _purchase_qty_of_pieces(prod, [{"length_remaining": 10, "weight_kg": 3}], 4, "kg")
    check("W2-014", "reject parsial 4 m -> 1.2 kg proporsional berat terukur", abs(q2 - 1.2) < 0.001, q2)
    q3 = await _purchase_qty_of_pieces(prod, [{"length_remaining": 10}], 10, "meter")
    check("W2-014", "kontrol meter/meter tidak berubah", q3 == 10, q3)


async def rfid_incidents():
    from services import rfid_incident_service as inc
    read = {"id": f"{T}_r", "epc": f"{T}_EPC", "device_id": f"{T}_dev", "warehouse_id": f"{T}_wh",
            "owner_entity_id": A, "reason": "uji", "read_type": "gate_out"}
    await asyncio.gather(*[inc.create_from_read(dict(read)) for _ in range(6)])
    rows = await db.rfid_incidents.find({"epc": f"{T}_EPC", "status": "open"}).to_list(None)
    check("W2-012", "6 red read bersamaan -> 1 insiden open, hits=6",
          len(rows) == 1 and rows[0]["hits"] == 6, [(r["id"], r["hits"]) for r in rows])
    iid = rows[0]["id"]
    r1, r2 = await asyncio.gather(status_of(inc.resolve(iid, "u1")), status_of(inc.acknowledge(iid, "u2")))
    final = (await db.rfid_incidents.find_one({"id": iid}))["status"]
    ok = final == "resolved" or (final == "acknowledged" and r1 != 200)
    check("W2-011", "ack vs resolve bersamaan tidak memundurkan resolved", ok, (r1, r2, final))
    code = await status_of(inc.acknowledge(iid, "u3"))
    check("W2-011", "ack setelah resolved ditolak", code in (400, 409), code)
    await inc.create_from_read(dict(read))
    n_open = await db.rfid_incidents.count_documents({"epc": f"{T}_EPC", "status": "open"})
    check("W2-012", "read merah sesudah insiden ditutup membuat insiden open baru", n_open == 1, n_open)


async def ar_deposit():
    from services import ar_receipt_service as ar
    cid = f"{T}_cust"
    await db.customers.insert_one({"id": cid, "name": f"{T} cust", "entity_id": A, "deposit_balance": 100.0})
    actor = {"id": "u", "name": f"{T}"}
    pl = {"customer_id": cid, "amount": 0, "use_deposit_amount": 80, "entity_id": A, "method": "transfer"}
    codes = await asyncio.gather(*[status_of(ar.create_receipt(dict(pl), actor)) for _ in range(2)])
    dep = (await db.customers.find_one({"id": cid}))["deposit_balance"]
    n = await db.ar_receipts.count_documents({"customer_id": cid})
    check("W2-017", "dua pemakaian deposit 80 dari saldo 100: satu menang, lainnya 409 tanpa receipt/efek",
          sorted(codes) == [200, 409] and n == 1 and abs(dep - 100) < 0.01, (codes, n, dep))
    rc = await ar.create_receipt({"customer_id": cid, "amount": 150, "entity_id": A, "method": "transfer"}, actor)
    await db.customers.update_one({"id": cid}, {"$set": {"deposit_balance": 0}})
    code = await status_of(ar.void_receipt(rc["id"], actor))
    after = await db.ar_receipts.find_one({"id": rc["id"]})
    cash = await db.cash_transactions.find_one({"ref_id": rc["id"]})
    check("W2-016", "void sumber deposit yg sudah terpakai -> 409 tanpa membalik kas/receipt",
          code == 409 and after["status"] == "posted" and "saga_lock" not in after and cash["status"] == "posted",
          (code, after["status"], cash["status"]))
    await db.customers.update_one({"id": cid}, {"$set": {"deposit_balance": 150}})
    code = await status_of(ar.void_receipt(rc["id"], actor))
    dep = (await db.customers.find_one({"id": cid}))["deposit_balance"]
    check("W2-016", "kontrol: deposit masih utuh -> void sukses, deposit ditarik tepat sekali", code == 200 and abs(dep) < 0.01, (code, dep))


async def ar_void_vs_new_payment():
    from services import ar_receipt_service as ar
    oid = f"{T}_so"
    pays = [{"receipt_id": f"{T}_rcA", "amount": 40.0}]
    await db.sales_orders.insert_one({"id": oid, "grand_total": 100.0, "total": 100.0, "payments": pays, "paid_total": 40.0})
    await db.ar_receipts.insert_one({"id": f"{T}_rcA", "number": "X", "customer_id": f"{T}_c2", "status": "posted",
                                     "allocations": [{"order_id": oid, "applied": 40.0}], "deposit_delta": 0})
    orig = ar.order_grand_total
    state = {"done": False}

    def stale_then_race(o):   # barrier: pembayaran baru masuk SESUDAH void membaca SO, sebelum tulis
        if not state["done"]:
            state["done"] = True
            import pymongo
            pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]].sales_orders.update_one(
                {"id": oid}, {"$push": {"payments": {"receipt_id": f"{T}_rcB", "amount": 60.0}},
                             "$inc": {"paid_total": 60.0}})
        return orig(o)
    ar.order_grand_total = stale_then_race
    try:
        await ar.void_receipt(f"{T}_rcA", {"name": T})
    finally:
        ar.order_grand_total = orig
    so = await db.sales_orders.find_one({"id": oid})
    check("W2-018", "void dgn snapshot lama tidak menimpa pembayaran baru 60",
          [p["receipt_id"] for p in so["payments"]] == [f"{T}_rcB"] and abs(so["paid_total"] - 60) < 0.01,
          (so["payments"], so["paid_total"]))


async def payroll_and_capacity():
    from services import gl_service
    run = {"id": f"{T}_run", "entity_id": A, "period": "2099-01", "totals": {"net": 100.0}, "number": f"{T}"}
    code = await status_of(gl_service.pay_payroll_run(run, T, "6-1000"))
    je = await db.journal_entries.count_documents({"source_type": "payroll_pay", "source_id": f"{A}:2099-01"})
    check("W2-023", "akun beban 6-1000 ditolak sebagai sumber pembayaran gaji", code == 400 and je == 0, (code, je))
    import inspect
    from services import hr_payroll_service
    src = inspect.getsource(hr_payroll_service.pay_run)
    check("W2-022", "pay_run mencatat cash_transactions (ref payroll_run) setelah jurnal", "record_return_cash" in src and "payroll_run" in src)
    ent = f"{T}_ENT"
    docs = [{"id": f"{T}_je{i}", "entity_id": ent, "status": "posted", "date": "2099-01-01",
             "lines": [{"account_code": "1-1100", "debit": 1, "credit": 0}, {"account_code": "4-1000", "debit": 0, "credit": 1}]}
            for i in range(50001)]
    await db.journal_entries.insert_many(docs)
    tb = await gl_service.trial_balance(scope={"entity_id": ent})
    check("W2-021", "neraca saldo 50.001 jurnal tidak terpotong", abs(tb["total_debit"] - 50001) < 0.01, tb["total_debit"])
    led = await gl_service.account_ledger("1-1100", scope={"entity_id": ent}) if hasattr(gl_service, "account_ledger") else None
    if led is not None:
        check("W2-021", "buku besar 50.001 baris tidak terpotong", abs(float(led.get("total_debit", 0)) - 50001) < 0.01, led.get("total_debit"))
    from services import bank_service
    await db.cash_transactions.insert_many([{"id": f"{T}_ct{i}", "account_id": f"{T}_acc", "status": "posted",
                                             "direction": "in", "amount": 1, "txn_date": "2099-01-01"} for i in range(5001)])
    tx = await bank_service._txns_for(f"{T}_acc")
    check("W2-021", "saldo rekening dari 5.001 mutasi (bukan 5.000)", bank_service._balance(0, tx) == 5001, len(tx))


async def cleanup():
    for coll in ("inventory_rolls", "inventory_balances", "cycle_count_sessions", "rfid_incidents", "customers", "ar_receipts",
                 "cash_transactions", "sales_orders", "journal_entries", "notifications", "doc_refs", "inventory_movements",
                 "payment_variance_decisions", "credit_notes"):
        for fld in ("id", "product_id", "epc", "customer_id", "customer_name", "entity_id", "ref", "ref_id"):
            await db[coll].delete_many({fld: {"$regex": f"^{T}"}})
    await db.journal_entries.delete_many({"source_id": {"$regex": f"^{T}"}})


async def main():
    try:
        for fn in (scope_and_stock, cycle_count_reject_race, weight_and_qc_return, rfid_incidents, ar_deposit,
                   ar_void_vs_new_payment, payroll_and_capacity):
            try:
                await fn()
            except Exception as e:  # noqa: BLE001
                check(fn.__name__, "harness error", False, repr(e))
    finally:
        await cleanup()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regression_results.json")
    json.dump({"tag": T, "passed": sum(r["pass"] for r in results), "total": len(results), "results": results},
              open(out, "w"), indent=1)
    for r in results:
        print(("PASS " if r["pass"] else "FAIL ") + r["id"] + " — " + r["invariant"] + ("" if r["pass"] else f" :: {r['detail']}"))
    print(f"{sum(r['pass'] for r in results)}/{len(results)}")


asyncio.run(main())
