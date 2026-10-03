"""P18c — Retur beli: PRET-02 (reversal → retry, net akun nol), PRET-03 (PPN + refund tunai = dokumen),
PRET-05 (kurang stok / periode tertutup ditolak lalu pulih), PRET-06 (multi-item parsial, owner mismatch,
approve bersamaan), QC-04 (retur → AP berkurang tepat nilai dokumen).

Usage: cd /app/backend && python ../audit/iterations/2026-10-03-P18-partial-coverage/repro_p18c.py
Self-clean: roll/saldo/PO di-snapshot & dipulihkan; dokumen/jurnal/kas/mutasi baru dihapus.
"""
import asyncio
import json
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402

T = f"TEST_P18C_{uuid.uuid4().hex[:6]}"
ENT = "ent_ksc"
SUP = "sup_a14677b676a6"
results = []
NEW = ["purchase_returns", "journal_entries", "cash_transactions", "inventory_movements", "audit_logs", "notifications",
       "period_closings", "debit_notes", "roll_cost_history", "inventory_lots", "saga_locks", "posting_failures",
       "gl_outbox", "interco_returns"]


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def free_rolls(db, pid, n=2):
    return await db.inventory_rolls.find({"product_id": pid, "warehouse_id": "wh_jakarta", "owner_entity_id": ENT,
                                          "status": "available", "length_reserved": {"$not": {"$gt": 0}}},
                                         {"_id": 0}).sort("length_remaining", 1).to_list(n)


async def net_by_account(db, rid):
    tot = defaultdict(float)
    async for j in db.journal_entries.find({"source_id": rid}, {"_id": 0, "lines": 1, "status": 1}):
        for ln in j["lines"]:
            tot[ln["account_code"]] += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return {k: round(v, 2) for k, v in tot.items() if abs(v) > 0.005}


async def mk(c, h, items, po="po_001", flow=False, submit=True):
    body = {"supplier_id": SUP, "po_id": po, "warehouse_id": "wh_jakarta", "reason": "cacat", "notes": T,
            "supplier_flow": flow, "submit_now": submit, "items": items}
    return await c.post("/api/purchase-returns", json=body, headers=h)


async def pret02(c, h, db):
    r0 = (await free_rolls(db, "prod_batik_mega", 1))[0]
    po0 = await db.purchase_orders.find_one({"id": "po_001"}, {"_id": 0})
    L = float(r0["length_remaining"])
    res = await mk(c, h, [{"product_id": r0["product_id"], "quantity": L, "unit": "yard", "price": 100000, "roll_ids": [r0["id"]]}])
    ret = res.json()
    ap = await c.post(f"/api/purchase-returns/{ret.get('id')}/approve", json={"notes": T}, headers=h)
    rr = await db.inventory_rolls.find_one({"id": r0["id"]}, {"_id": 0})
    po1 = await db.purchase_orders.find_one({"id": "po_001"}, {"_id": 0})
    d = ap.json() if ap.status_code == 200 else {}
    gross = float(d.get("grand_total") or 0)
    check("QC-04", "retur DIRECT disetujui: roll keluar stok (returned_supplier), Nota Debit, AP PO berkurang = grand_total, jurnal posted",
          res.status_code == 200 and ap.status_code == 200 and rr["status"] != "available" and d.get("debit_note_number")
          and round(float(po1.get("returned_amount") or 0) - float(po0.get("returned_amount") or 0), 2) == round(gross, 2) and d.get("gl_status") == "posted",
          (res.status_code, ap.status_code, ap.text[:150], rr["status"], po1.get("returned_amount"), gross))
    rv = await c.post(f"/api/purchase-returns/{ret['id']}/reverse", json={"notes": f"{T} salah retur"}, headers=h)
    rr = await db.inventory_rolls.find_one({"id": r0["id"]}, {"_id": 0})
    po2 = await db.purchase_orders.find_one({"id": "po_001"}, {"_id": 0})
    net = await net_by_account(db, ret["id"])
    doc = await db.purchase_returns.find_one({"id": ret["id"]}, {"_id": 0})
    check("PRET-02", "reverse: retur cancelled, roll kembali available panjang utuh, AP pulih, net jurnal per akun = 0",
          rv.status_code == 200 and doc["status"] == "cancelled" and rr["status"] == "available"
          and float(rr["length_remaining"]) == L and float(po2.get("returned_amount") or 0) == float(po0.get("returned_amount") or 0) and not net,
          (rv.status_code, rv.text[:120], doc["status"], rr["status"], po2.get("returned_amount"), net))
    again = await c.post(f"/api/purchase-returns/{ret['id']}/reverse", json={"notes": f"{T} ulang"}, headers=h)
    check("PRET-02", "reverse ulang idempoten (no-op, tanpa jurnal/stok ganda)", again.status_code in (200, 400) and
          await db.journal_entries.count_documents({"source_id": ret["id"]}) == 2, (again.status_code, await db.journal_entries.count_documents({"source_id": ret["id"]})))
    res2 = await mk(c, h, [{"product_id": r0["product_id"], "quantity": L, "unit": "yard", "price": 100000, "roll_ids": [r0["id"]]}])
    ap2 = await c.post(f"/api/purchase-returns/{res2.json().get('id')}/approve", json={"notes": T}, headers=h)
    po3 = await db.purchase_orders.find_one({"id": "po_001"}, {"_id": 0})
    rr = await db.inventory_rolls.find_one({"id": r0["id"]}, {"_id": 0})
    check("PRET-02", "retry (retur baru roll yang sama) sukses sekali: AP berkurang satu kali, roll keluar lagi",
          ap2.status_code == 200 and round(float(po3["returned_amount"]) - float(po0.get("returned_amount") or 0), 2) == round(float(ap2.json()["grand_total"]), 2)
          and rr["status"] != "available", (ap2.status_code, po3.get("returned_amount")))
    await c.post(f"/api/purchase-returns/{res2.json()['id']}/reverse", json={"notes": f"{T} bersih"}, headers=h)


async def pret03(c, h, db):
    r0 = (await free_rolls(db, "prod_batik_mega", 1))[0]
    res = await mk(c, h, [{"product_id": r0["product_id"], "quantity": 10, "unit": "yard", "price": 100000, "roll_ids": [r0["id"]]}],
                   po="po_2c5398d9b5a5", flow=True)
    ret = res.json()
    steps = [await c.post(f"/api/purchase-returns/{ret.get('id')}/approve", json={"notes": T}, headers=h),
             await c.post(f"/api/purchase-returns/{ret.get('id')}/ship-to-supplier", json={"carrier": "JNE", "tracking_no": T}, headers=h),
             await c.post(f"/api/purchase-returns/{ret.get('id')}/supplier-accept", json={"outcome": "refund", "refund_account_code": "1-1100"}, headers=h)]
    d = steps[-1].json() if steps[-1].status_code == 200 else {}
    cash = await db.cash_transactions.find_one({"ref_id": ret.get("id")}, {"_id": 0})
    je = await db.journal_entries.find_one({"source_id": ret.get("id"), "source_type": "purchase_return"}, {"_id": 0})
    print("PRET03_LINES", [(ln["account_code"], ln.get("debit"), ln.get("credit")) for ln in (je or {}).get("lines", [])])
    kas = sum(float(ln.get("debit") or 0) for ln in (je or {}).get("lines", []) if ln["account_code"] == "1-1100")
    ppn_cr = sum(float(ln.get("credit") or 0) for ln in (je or {}).get("lines", []) if ln["account_code"] == "1-1500")
    gross = float(d.get("grand_total") or 0)
    check("PRET-03", "RMA ber-PPN → refund: grand_total = net + PPN, kas masuk = jurnal Dr Kas = grand_total, PPN masukan dibalik",
          [s.status_code for s in steps] == [200, 200, 200] and float(d.get("ppn_amount") or 0) > 0
          and round(gross, 2) == round(float(d.get("total_amount") or 0) + float(d.get("ppn_amount") or 0), 2)
          and cash and round(float(cash["amount"]), 2) == round(gross, 2) == round(kas, 2) and round(ppn_cr, 2) == round(float(d["ppn_amount"]), 2),
          {"steps": [s.status_code for s in steps], "err": steps[-1].text[:120], "gross": gross, "ppn": d.get("ppn_amount"),
           "cash": (cash or {}).get("amount"), "kas_je": kas, "ppn_je": ppn_cr})
    po = await db.purchase_orders.find_one({"id": "po_2c5398d9b5a5"}, {"_id": 0, "returned_amount": 1})
    check("PRET-03", "refund tunai tidak mengurangi AP PO (hanya kas)", float(po.get("returned_amount") or 0) == 0, po)
    rv = await c.post(f"/api/purchase-returns/{ret.get('id')}/reverse", json={"notes": f"{T} batal refund"}, headers=h)
    cash2 = await db.cash_transactions.find_one({"id": (cash or {}).get("id")}, {"_id": 0})
    check("PRET-03", "reverse refund: kas di-void, net jurnal nol", rv.status_code == 200 and cash2 and cash2.get("status") in ("void", "voided", "cancelled")
          and not await net_by_account(db, ret["id"]), (rv.status_code, rv.text[:100], (cash2 or {}).get("status")))


async def pret05(c, h, db):
    r0 = (await free_rolls(db, "prod_batik_mega", 1))[0]
    L = float(r0["length_remaining"])
    big = await mk(c, h, [{"product_id": r0["product_id"], "quantity": L + 50, "unit": "yard", "price": 100000, "roll_ids": [r0["id"]]}])
    ap = await c.post(f"/api/purchase-returns/{big.json().get('id')}/approve", json={}, headers=h) if big.status_code == 200 else big
    rr = await db.inventory_rolls.find_one({"id": r0["id"]}, {"_id": 0})
    bid = big.json().get("id")
    mv = [(m.get("roll_id"), m.get("parent_roll_id"), m.get("quantity")) async for m in db.inventory_movements.find({"ref_id": bid}, {"_id": 0})]
    check("PRET-05", "qty retur > sisa roll → ditolak 400 saat dibuat (tidak dipotong diam-diam), roll utuh", 400 <= ap.status_code < 500 and rr["status"] == "available"
          and float(rr["length_remaining"]) == L, (big.status_code, ap.status_code, L, r0["id"], mv, ap.text[-150:]))
    if ap.status_code == 200:
        await c.post(f"/api/purchase-returns/{bid}/reverse", json={"notes": f"{T} bersih"}, headers=h)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pid = f"pc_{T}"
    res = await mk(c, h, [{"product_id": r0["product_id"], "quantity": 5, "unit": "yard", "price": 100000, "roll_ids": [r0["id"]]}])
    rid = res.json().get("id")
    await db.period_closings.insert_one({"id": pid, "entity_id": ENT, "status": "closed", "period_type": "month",
                                         "period_key": today[:7], "start_date": today, "end_date": today})
    ap = await c.post(f"/api/purchase-returns/{rid}/approve", json={}, headers=h)
    doc = await db.purchase_returns.find_one({"id": rid}, {"_id": 0})
    rr = await db.inventory_rolls.find_one({"id": r0["id"]}, {"_id": 0})
    check("PRET-05", "periode tertutup → approve 4xx, retur tetap pending, roll & AP tak berubah, tanpa jurnal",
          400 <= ap.status_code < 500 and doc["status"] in ("pending_approval", "draft") and float(rr["length_remaining"]) == L
          and not doc.get("stock_adjusted") and await db.journal_entries.count_documents({"source_id": rid}) == 0, (ap.status_code, ap.text[:120], doc["status"]))
    await db.period_closings.delete_one({"id": pid})
    ap = await c.post(f"/api/purchase-returns/{rid}/approve", json={}, headers=h)
    rr = await db.inventory_rolls.find_one({"id": r0["id"]}, {"_id": 0})
    check("PRET-05", "periode dibuka → approve ulang sukses, roll berkurang tepat 5, satu jurnal",
          ap.status_code == 200 and round(L - float(rr["length_remaining"]), 2) == 5 and await db.journal_entries.count_documents({"source_id": rid}) == 1,
          (ap.status_code, rr["length_remaining"]))
    await c.post(f"/api/purchase-returns/{rid}/reverse", json={"notes": f"{T} bersih"}, headers=h)


async def pret06(c, h, db):
    a = next(r for r in await free_rolls(db, "prod_batik_mega", 10) if float(r["length_remaining"]) >= 20)
    b = (await free_rolls(db, "prod_tenun_ikat", 1))[0]
    la, lb = float(a["length_remaining"]), float(b["length_remaining"])
    res = await mk(c, h, [{"product_id": a["product_id"], "quantity": 12.5, "unit": "yard", "price": 100000, "roll_ids": [a["id"]]},
                          {"product_id": b["product_id"], "quantity": 7, "unit": "yard", "price": 90000, "roll_ids": [b["id"]]}])
    rid = res.json().get("id")
    outs = await asyncio.gather(*(c.post(f"/api/purchase-returns/{rid}/approve", json={}, headers=h) for _ in range(3)))
    codes = sorted(o.status_code for o in outs)
    ra, rb = (await db.inventory_rolls.find_one({"id": a["id"]}, {"_id": 0}), await db.inventory_rolls.find_one({"id": b["id"]}, {"_id": 0}))
    movs = await db.inventory_movements.count_documents({"source_document": {"$regex": rid}}) or \
        await db.inventory_movements.count_documents({"reference_id": rid})
    check("PRET-06", "multi-item parsial: approve 3× bersamaan → tepat 1 sukses; roll A −12.5, roll B −7 (sekali), satu jurnal",
          codes.count(200) == 1 and round(la - float(ra["length_remaining"]), 2) == 12.5 and round(lb - float(rb["length_remaining"]), 2) == 7
          and await db.journal_entries.count_documents({"source_id": rid, "source_type": "purchase_return"}) == 1,
          {"codes": codes, "la": la, "lb": lb, "a": ra["length_remaining"], "b": rb["length_remaining"], "movs": movs})
    await c.post(f"/api/purchase-returns/{rid}/reverse", json={"notes": f"{T} bersih"}, headers=h)
    kr = await db.inventory_rolls.find_one({"owner_entity_id": "ent_kanda", "length_remaining": {"$gt": 1}}, {"_id": 0})
    res = await mk(c, h, [{"product_id": kr["product_id"], "quantity": 1, "unit": "yard", "price": 1000, "roll_ids": [kr["id"]]}])
    ap = await c.post(f"/api/purchase-returns/{res.json().get('id')}/approve", json={}, headers=h) if res.status_code == 200 else res
    kr2 = await db.inventory_rolls.find_one({"id": kr["id"]}, {"_id": 0})
    check("PRET-06", "roll milik PT lain di retur KSC → ditolak (create/approve 4xx), roll PT lain utuh",
          400 <= ap.status_code < 500 and kr2["length_remaining"] == kr["length_remaining"] and kr2["status"] == kr["status"],
          (res.status_code, ap.status_code, ap.text[:120]))


async def main():
    import httpx
    from db import db
    full = snapshot_stock(["number_sequences", "inventory_rolls", "inventory_balances", "inventory_lots", "purchase_orders", "bank_accounts", "cash_balances"])
    ids = snapshot_new_ids(NEW)
    async with httpx.AsyncClient(base_url="http://localhost:8001", timeout=120) as c:
        r = await c.post("/api/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
        h = {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}
        for fn in (pret02, pret03, pret05, pret06):
            try:
                await fn(c, h, db)
            except Exception as exc:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check("P18C", f"eksekusi {fn.__name__}", False, repr(exc)[:200])
        await db.period_closings.delete_many({"id": {"$regex": T}})
        purge_new_ids(ids, verbose=False)
        restore_stock(full)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
