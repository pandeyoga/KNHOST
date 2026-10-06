"""P20a — GRN-05 (periode tertutup & jurnal gagal saat tutup GRN → pemulihan tanpa stok ganda) ·
PRET-01 (retur DIRECT atas PO non-PPN: stok, PO/hutang dan jurnal konsisten).

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-04-P20-partial-api/repro_p20a.py
Self-clean: dokumen/roll/jurnal baru dihapus; saldo, nomor, akun GL dan setting dipulihkan.
"""
import json
import os
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, ".")
load_dotenv(".env")
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402

BASE = "http://127.0.0.1:8009/api"
ENT = "ent_ksc"
T = f"TEST_P20A_{uuid.uuid4().hex[:6]}"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
NEW = ["inventory_rolls", "inventory_movements", "inventory_lots", "journal_entries", "inspections", "notifications",
       "audit_logs", "rfid_tags", "doc_refs", "backorders", "qc_inspections", "goods_receipts", "supplier_dn_profiles",
       "wms_tasks", "purchase_orders", "purchase_returns", "vendor_bills", "approval_requests", "timeline_events",
       "period_closings", "saga_locks", "posting_failures", "gl_outbox", "roll_cost_history", "cash_transactions"]
results = []
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:400]})


def login(email):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT})
    return s


def ok(r):
    assert r.status_code == 200, f"{r.request.method} {r.url} → {r.status_code} {r.text[:400]}"
    return r.json()


def make_po(s, qty, **extra):
    sup = db.suppliers.find_one({"name": "Cirebon Craft", "entity_id": ENT})["id"]
    po = ok(s.post(f"{BASE}/purchase-orders", json={
        "supplier_id": sup, "warehouse_id": "wh_jakarta", "notes": f"{T} PO", **extra,
        "items": [{"product_id": "prod_batik_mega", "quantity": qty, "unit": "yard", "price": 100000, "expected_grade": "A"}]}))
    po = po.get("po") or po
    return po, list(db.wms_tasks.find({"po_id": po["id"], "flow_type": "inbound"}, {"_id": 0}))


def counted_grn(s, po, task, lengths, dn):
    g = ok(s.post(f"{BASE}/goods-receipts", json={"partner_type": "supplier", "partner_id": po["supplier_id"],
                                                 "warehouse_id": po["warehouse_id"], "po_ids": [po["id"]]}))
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/manual-entry", json={"expected_version": g["version"]}))
    g = ok(s.patch(f"{BASE}/goods-receipts/{g['id']}/dn", json={"expected_version": g["version"], "number": dn,
                                                              "date": TODAY, "recipient_name": T}))
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/lines", json={
        "expected_version": g["version"], "declared": {"qty": sum(lengths), "unit": task.get("unit"), "rolls": len(lengths)},
        "target": {"type": "po_task", "task_id": task["id"]}, "description": f"{T} barang"}))
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/start-count", json={"expected_version": g["version"]}))
    for n in lengths:
        ok(s.post(f"{BASE}/goods-receipts/{g['id']}/lines/1/rolls", json={"length": n, "lot": f"{T}-LOT"}))
    v = db.goods_receipts.find_one({"id": g["id"]})["version"]
    return ok(s.post(f"{BASE}/goods-receipts/{g['id']}/finish-count", json={"expected_version": v}))


def close(s, gid):
    return s.post(f"{BASE}/goods-receipts/{gid}/close", json={"expected_version": db.goods_receipts.find_one({"id": gid})["version"]})


def bal(pid="prod_batik_mega", wh="wh_jakarta"):
    b = db.inventory_balances.find_one({"product_id": pid, "warehouse_id": wh, "owner_entity_id": ENT}, {"_id": 0}) or {}
    return {k: round(float(b.get(k) or 0), 2) for k in ("available_qty", "quarantine_qty", "on_hand_qty")}


def gr_jes(task_id):
    return list(db.journal_entries.find({"source_type": "goods_receipt", "source_id": task_id, "status": {"$ne": "void"}}, {"_id": 0}))


def net(source_id):
    tot = defaultdict(float)
    for j in db.journal_entries.find({"source_id": source_id, "status": {"$ne": "void"}}, {"_id": 0, "lines": 1}):
        for ln in j["lines"]:
            tot[ln["account_code"]] += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return {k: round(v, 2) for k, v in tot.items() if abs(v) > 0.005}


def grn05(s):
    po, tasks = make_po(s, 30)
    task = tasks[0]
    g = counted_grn(s, po, task, [30], f"{T}-SJ1")
    b0 = bal()
    pc = f"pc_{T}"
    db.period_closings.insert_one({"id": pc, "entity_id": ENT, "status": "closed", "period_type": "month",
                                   "period_key": TODAY[:7], "start_date": TODAY, "end_date": TODAY})
    r = close(s, g["id"])
    gd = db.goods_receipts.find_one({"id": g["id"]}, {"_id": 0})
    rolls = list(db.inventory_rolls.find({"grn_id": g["id"]}, {"_id": 0, "status": 1}))
    check("GRN-05", "periode tertutup → tutup GRN 400 NOT_POSTABLE; GRN tetap reconcile, roll masih 'receiving', saldo & jurnal tak berubah",
          r.status_code == 400 and "NOT_POSTABLE" in r.text and gd["status"] == "reconcile"
          and [x["status"] for x in rolls] == ["receiving"] and bal() == b0 and not gr_jes(task["id"]),
          (r.status_code, r.text[:160], gd["status"], [x["status"] for x in rolls], b0, bal()))
    db.period_closings.delete_one({"id": pc})

    # Jurnal gagal di TENGAH tutup (akun GR/IR nonaktif) → stok sudah diterima, GRN tertahan 'closing'
    db.gl_accounts.update_many({"code": "2-1150"}, {"$set": {"is_active": False}})
    r = close(s, g["id"])
    gd = db.goods_receipts.find_one({"id": g["id"]}, {"_id": 0})
    tk = db.wms_tasks.find_one({"id": task["id"]}, {"_id": 0})
    b1 = bal()
    n_rolls = db.inventory_rolls.count_documents({"grn_id": g["id"]})
    check("GRN-05", "jurnal GR gagal → GRN 'closing' (bukan closed), baris posted.status=failed, gl_posting failed, tanpa jurnal",
          r.status_code == 200 and gd["status"] == "closing" and gd["lines"][0]["posted"]["status"] == "failed"
          and (tk.get("gl_posting") or {}).get("status") == "failed" and not gr_jes(task["id"]),
          (r.status_code, gd["status"], gd["lines"][0].get("posted"), (tk.get("gl_posting") or {}).get("status")))
    check("GRN-05", "stok fisik tercatat sekali (1 roll, karantina +30)", n_rolls == 1 and round(b1["quarantine_qty"] - b0["quarantine_qty"], 2) == 30,
          (n_rolls, b0, b1))
    r2 = close(s, g["id"])
    check("GRN-05", "tutup ulang saat akun masih nonaktif → tetap closing, roll tidak bertambah",
          r2.status_code == 200 and db.goods_receipts.find_one({"id": g["id"]})["status"] == "closing"
          and db.inventory_rolls.count_documents({"grn_id": g["id"]}) == 1 and bal() == b1, (r2.status_code, r2.text[:120]))
    db.gl_accounts.update_many({"code": "2-1150"}, {"$set": {"is_active": True}})

    r3 = close(s, g["id"])
    gd = db.goods_receipts.find_one({"id": g["id"]}, {"_id": 0})
    jes = gr_jes(task["id"])
    po_after = db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})
    rcv = sum(float(i.get("received_qty") or 0) for i in po_after.get("items") or [])
    check("GRN-05", "penyebab dibereskan → tutup ulang: GRN closed, tepat 1 jurnal GR 3.000.000 (Dr 1-1300 / Cr 2-1150)",
          r3.status_code == 200 and gd["status"] == "closed" and len(jes) == 1
          and net(task["id"]) == {"1-1300": 3000000.0, "2-1150": -3000000.0},
          (r3.status_code, r3.text[:150], gd["status"], len(jes), net(task["id"])))
    check("GRN-05", "pemulihan tanpa stok ganda: tetap 1 roll, karantina +30 (bukan +60), PO received_qty = 30",
          db.inventory_rolls.count_documents({"grn_id": g["id"]}) == 1 and bal() == b1 and round(rcv, 2) == 30,
          (bal(), b1, rcv))
    r4 = close(s, g["id"])
    check("GRN-05", "tutup GRN yang sudah closed → 4xx, tanpa jurnal/stok tambahan",
          400 <= r4.status_code < 500 and len(gr_jes(task["id"])) == 1 and bal() == b1, (r4.status_code, r4.text[:100]))


def pret01(s):
    po, tasks = make_po(s, 20, tax_mode="non_ppn")
    po = db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})
    check("PRET-01", "PO non-PPN: ppn 0, grand_total = 2.000.000", float(po.get("ppn_amount") or 0) == 0
          and round(float(po.get("grand_total") or 0), 2) == 2000000, (po.get("tax_mode"), po.get("ppn_amount"), po.get("grand_total")))
    g = counted_grn(s, po, tasks[0], [20], f"{T}-SJ2")
    ok(close(s, g["id"]))
    roll = db.inventory_rolls.find_one({"grn_id": g["id"]}, {"_id": 0})
    ok(s.post(f"{BASE}/inbound/rolls/{roll['id']}/inspect", json={"defects": [], "note": T}))
    ok(s.post(f"{BASE}/inbound/tasks/{tasks[0]['id']}/qc-decision", json={"accept_qty": 20, "reject_qty": 0, "accept_grade": "A", "reason": T}))
    b0, po0 = bal(), db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})
    ret = ok(s.post(f"{BASE}/purchase-returns", json={
        "supplier_id": po["supplier_id"], "po_id": po["id"], "warehouse_id": "wh_jakarta", "reason": "cacat", "notes": T,
        "supplier_flow": False, "submit_now": True,
        "items": [{"product_id": "prod_batik_mega", "quantity": 8, "unit": "yard", "price": 0, "roll_ids": [roll["id"]]}]}))
    check("PRET-01", "retur dibuat: ppn_rate 0, ppn 0, grand_total = total = 8 × 100.000",
          float(ret.get("ppn_amount") or 0) == 0 and float(ret.get("ppn_rate") or 0) == 0
          and round(float(ret["grand_total"]), 2) == round(float(ret["total_amount"]), 2) == 800000,
          (ret.get("ppn_rate"), ret.get("ppn_amount"), ret.get("total_amount"), ret.get("grand_total")))
    ap = ok(s.post(f"{BASE}/purchase-returns/{ret['id']}/approve", json={"notes": T}))
    rr = db.inventory_rolls.find_one({"id": roll["id"]}, {"_id": 0})
    b1 = bal()
    check("PRET-01", "stok: roll 20 → 12, available −8 & on_hand −8 (sekali)",
          round(float(rr["length_remaining"]), 2) == 12 and round(b0["available_qty"] - b1["available_qty"], 2) == 8
          and round(b0["on_hand_qty"] - b1["on_hand_qty"], 2) == 8, (rr["length_remaining"], b0, b1))
    po1 = db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})
    pod = ok(s.get(f"{BASE}/purchase-orders/{po['id']}"))["financials"]
    check("PRET-01", "PO: returned_amount +800.000; outstanding = 2.000.000 − 800.000; status bayar belum lunas",
          round(float(po1.get("returned_amount") or 0) - float(po0.get("returned_amount") or 0), 2) == 800000
          and round(float(pod["outstanding"]), 2) == 1200000 and pod["payment_status"] in ("unpaid", "partial"),
          (po1.get("returned_amount"), pod.get("outstanding"), pod.get("payment_status")))
    je = list(db.journal_entries.find({"source_type": "purchase_return", "source_id": ret["id"], "status": {"$ne": "void"}}, {"_id": 0}))
    n = net(ret["id"])
    check("PRET-01", "jurnal: tepat 1, seimbang, Dr 2-1150 800.000 / Cr 1-1300 800.000, TANPA baris PPN (1-1500)",
          len(je) == 1 and ap.get("gl_status") == "posted" and n == {"2-1150": 800000.0, "1-1300": -800000.0},
          (len(je), ap.get("gl_status"), n))
    mv = round(sum(abs(float(m.get("quantity") or 0)) for m in db.inventory_movements.find({"$or": [{"ref_id": ret["id"]}, {"reference_id": ret["id"]}]})), 2)
    check("PRET-01", "nilai persediaan keluar (Cr 1-1300) = qty mutasi × harga PO", mv == 8 and -n.get("1-1300", 0) == mv * 100000, (mv, n))
    rv = s.post(f"{BASE}/purchase-returns/{ret['id']}/reverse", json={"notes": f"{T} bersih"})
    po2 = db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})
    fam = list(db.inventory_rolls.find({"$or": [{"id": roll["id"]}, {"parent_roll_id": roll["id"]}]}, {"_id": 0, "status": 1, "length_remaining": 1}))
    avail = round(sum(float(x["length_remaining"]) for x in fam if x["status"] == "available"), 2)
    check("PRET-01", "reverse: 20 yd kembali available (roll asal + potongan anak), saldo pulih, returned_amount pulih, net jurnal 0",
          rv.status_code == 200 and avail == 20 and bal() == b0
          and float(po2.get("returned_amount") or 0) == float(po0.get("returned_amount") or 0) and not net(ret["id"]),
          (rv.status_code, fam, bal(), b0, po2.get("returned_amount"), net(ret["id"])))


def main():
    full = snapshot_stock(["inventory_balances", "number_sequences", "system_settings", "gl_accounts"])
    ids = snapshot_new_ids(NEW)
    s = login("admin@kainnusantara.id")
    try:
        for fn in (grn05, pret01):
            try:
                fn(s)
            except Exception as exc:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check("RUN", f"eksekusi {fn.__name__}", False, repr(exc)[:300])
    finally:
        db.gl_accounts.update_many({"code": "2-1150"}, {"$set": {"is_active": True}})
        db.period_closings.delete_many({"id": {"$regex": T}})
        purge_new_ids(ids, verbose=False)
        restore_stock(full)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


if __name__ == "__main__":
    main()
