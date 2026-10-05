"""P18d — APAR-01: Vendor Bill 3-way (receipt/PO) → posting → bayar sebagian/lunas → BATAL pembayaran
(endpoint baru) → bayar ulang; serta overbilling ditolak. Net jurnal kas per pembayaran batal = 0.

Usage: cd /app/backend && python ../audit/iterations/2026-10-03-P18-partial-coverage/repro_p18d.py
Self-clean: bill/kas/jurnal baru dihapus, PO & saldo bank dipulihkan.
"""
import asyncio
import json
import sys
import uuid
from collections import defaultdict

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402

T = f"TEST_P18D_{uuid.uuid4().hex[:6]}"
ENT = "ent_ksc"
results = []
NEW = ["vendor_bills", "cash_transactions", "journal_entries", "audit_logs", "notifications", "payment_variance_decisions",
       "gl_outbox", "posting_failures", "period_closings", "saga_locks"]


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def net(db, source_ids):
    tot = defaultdict(float)
    async for j in db.journal_entries.find({"source_id": {"$in": source_ids}}, {"_id": 0, "lines": 1}):
        for ln in j["lines"]:
            tot[ln["account_code"]] += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return {k: round(v, 2) for k, v in tot.items() if abs(v) > 0.005}


async def run(c, h, hs, db):
    over = await c.post("/api/vendor-bills", json={"po_id": "po_001", "supplier_invoice_no": f"{T}-OVR", "notes": T,
                                                  "items": [{"product_id": "prod_batik_mega", "po_line_id": "L1", "billed_qty": 151, "price": 0}]}, headers=h)
    check("APAR-01", "3-way: tagihan qty > diterima (151 > 150) ditolak/ditandai tak cocok, tidak langsung posted",
          over.status_code >= 400 or (over.json().get("status") != "posted" and (over.json().get("match") or {}).get("status") != "matched"),
          (over.status_code, over.text[:160]))
    if over.status_code == 200:
        await c.post(f"/api/vendor-bills/{over.json()['id']}/cancel", json={"notes": f"{T} batal"}, headers=h)
    r = await c.post("/api/vendor-bills", json={"po_id": "po_001", "supplier_invoice_no": f"{T}-INV", "notes": T,
                                               "items": [{"product_id": "prod_batik_mega", "po_line_id": "L1", "billed_qty": 10, "price": 0}]}, headers=h)
    bill = r.json()
    bid = bill.get("id")
    for step in ("submit", "approve"):
        if (await db.vendor_bills.find_one({"id": bid}, {"_id": 0, "status": 1}) or {}).get("status") != "posted":
            await c.post(f"/api/vendor-bills/{bid}/{step}", json={"notes": T}, headers=h)
    b = await db.vendor_bills.find_one({"id": bid}, {"_id": 0})
    g = round(float(b.get("grand_total") or 0), 2)
    check("APAR-01", "bill 10 yd dari penerimaan PO-00001 → posted, jurnal AP ada", r.status_code == 200 and b["status"] == "posted" and g > 0
          and await db.journal_entries.count_documents({"source_id": bid}) >= 1, (r.status_code, r.text[:120], b.get("status"), g))
    pay = lambda amt: c.post(f"/api/vendor-bills/{bid}/pay", json={"amount": amt, "method": "transfer", "cash_type": "kas_besar", "notes": T}, headers=h)  # noqa: E731
    p1, p2 = await pay(round(g / 2, 2)), await pay(round(g - round(g / 2, 2), 2))
    b = await db.vendor_bills.find_one({"id": bid}, {"_id": 0})
    check("APAR-01", "bayar 2× (setengah + sisa) → status paid, amount_paid = grand_total", p1.status_code == p2.status_code == 200
          and b["status"] == "paid" and round(float(b["amount_paid"]), 2) == g, (p1.status_code, p2.status_code, p2.text[:100], b["status"]))
    pid2, cash2 = b["payments"][-1]["id"], b["payments"][-1]["cash_txn_id"]
    direct = await c.post(f"/api/cash-transactions/{cash2}/void", headers=h)
    check("APAR-01", "kas pembayaran bill tak bisa di-void dari layar kas (409, harus lewat bill)", direct.status_code == 409, direct.status_code)
    deny = await c.post(f"/api/vendor-bills/{bid}/payments/{pid2}/void", json={"notes": f"{T} salah"}, headers=hs)
    nor = await c.post(f"/api/vendor-bills/{bid}/payments/{pid2}/void", json={"notes": ""}, headers=h)
    v = await c.post(f"/api/vendor-bills/{bid}/payments/{pid2}/void", json={"notes": f"{T} salah nominal"}, headers=h)
    b = await db.vendor_bills.find_one({"id": bid}, {"_id": 0})
    txn = await db.cash_transactions.find_one({"id": cash2}, {"_id": 0})
    po = await db.purchase_orders.find_one({"id": "po_001"}, {"_id": 0})
    check("APAR-01", "batal pembayaran ke-2: peran tanpa izin 403, tanpa alasan 400; sukses → bill posted, outstanding = sisa, kas void, net jurnal kas itu = 0",
          deny.status_code == 403 and nor.status_code == 400 and v.status_code == 200 and b["status"] == "posted"
          and round(float(b["amount_paid"]), 2) == round(g / 2, 2) and txn["status"] == "void" and not await net(db, [cash2]),
          (deny.status_code, nor.status_code, v.status_code, v.text[:120], b["status"], b.get("amount_paid"), txn.get("status"), await net(db, [cash2])))
    again = await c.post(f"/api/vendor-bills/{bid}/payments/{pid2}/void", json={"notes": f"{T} ulang"}, headers=h)
    para = await asyncio.gather(*(c.post(f"/api/vendor-bills/{bid}/payments/{b['payments'][0]['id']}/void", json={"notes": f"{T} paralel"}, headers=h) for _ in range(3)))
    b = await db.vendor_bills.find_one({"id": bid}, {"_id": 0})
    check("APAR-01", "batal ulang 409; batal paralel 3× pembayaran-1 → tepat 1 sukses, amount_paid = 0 (tak negatif)",
          again.status_code == 409 and sorted(x.status_code for x in para).count(200) == 1 and round(float(b["amount_paid"]), 2) == 0,
          (again.status_code, [x.status_code for x in para], b.get("amount_paid")))
    p3 = await pay(g)
    b = await db.vendor_bills.find_one({"id": bid}, {"_id": 0})
    live = [p for p in b["payments"] if not p.get("voided")]
    check("APAR-01", "bayar ulang penuh sesudah pembatalan → paid; hanya 1 pembayaran aktif = grand_total; net kas semua pembayaran = −grand_total",
          p3.status_code == 200 and b["status"] == "paid" and len(live) == 1 and round(float(live[0]["amount"]), 2) == g
          and round(sum(v for k, v in (await net(db, [p["cash_txn_id"] for p in b["payments"]])).items() if k.startswith("1-11")), 2) == -g,
          (p3.status_code, b["status"], len(live)))
    check("APAR-05", "status pembayaran PO tersinkron dengan bill (payment_status bukan 'paid' saat bill dibuka lagi)",
          po.get("payment_status") != "paid", po.get("payment_status"))


async def main():
    import httpx
    from db import db
    full = snapshot_stock(["number_sequences", "purchase_orders", "bank_accounts", "cash_balances"])
    ids = snapshot_new_ids(NEW)
    async with httpx.AsyncClient(base_url="http://localhost:8001", timeout=120) as c:
        lg = lambda e: c.post("/api/auth/login", json={"email": e, "password": "demo12345"})  # noqa: E731
        h = {"Authorization": f"Bearer {(await lg('admin@kainnusantara.id')).json()['token']}", "X-Entity-Id": ENT}
        hs = {"Authorization": f"Bearer {(await lg('warehouse@kainnusantara.id')).json()['token']}", "X-Entity-Id": ENT}
        try:
            await run(c, h, hs, db)
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check("P18D", "eksekusi", False, repr(exc)[:200])
        purge_new_ids(ids, verbose=False)
        restore_stock(full)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
