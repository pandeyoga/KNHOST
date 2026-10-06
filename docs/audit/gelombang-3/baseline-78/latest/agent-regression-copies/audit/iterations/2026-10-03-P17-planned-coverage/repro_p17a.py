"""P17a — GRN-04: penerimaan multi-baris + parsial membentuk tugas sisa yang benar.

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-03-P17-planned-coverage/repro_p17a.py
Fixture: PO uji 2 baris + 2 tugas inbound (salinan tugas seed). Semua dokumen baru dibuang, stok dipulihkan.
"""
import json
import os
import sys
import uuid

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, ".")
load_dotenv(".env")
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402

BASE = "http://127.0.0.1:8009/api"
ENT = "ent_ksc"
T = f"TEST_P17A_{uuid.uuid4().hex[:6]}"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
NEW = ["inventory_rolls", "inventory_movements", "inventory_lots", "journal_entries", "inspections", "notifications",
       "audit_logs", "rfid_tags", "doc_refs", "backorders", "qc_inspections", "goods_receipts", "supplier_dn_profiles",
       "wms_tasks", "purchase_orders"]
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


def login(email):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT})
    return s


def ok(r):
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    return r.json()


def fixture():
    src_po = db.purchase_orders.find_one({"po_number": "PO-00004"}, {"_id": 0})
    po_id = f"po_{T.lower()}"
    items = []
    for it, qty in zip(src_po["items"][:2], (60.0, 120.0)):
        items.append({**it, "quantity": qty, "received_qty": 0.0})
    po = {**src_po, "id": po_id, "po_number": f"{T}-PO", "status": "pending", "items": items}
    db.purchase_orders.insert_one(dict(po))
    tasks = []
    for it in items:
        seed = db.wms_tasks.find_one({"flow_type": "inbound", "product_id": it["product_id"], "entity_id": ENT},
                                     {"_id": 0}, sort=[("created_at", -1)])
        t = {k: v for k, v in seed.items() if k not in ("grn_active_id", "grn_active_number", "saga_lock")}
        t.update({"id": f"wms_{T.lower()}_{len(tasks)}", "po_id": po_id, "po_number": po["po_number"],
                  "status": "waiting_goods", "expected_qty": it["quantity"], "received_qty": 0.0, "quantity": 0.0,
                  "qty_rolls_scanned": 0, "scan_log": [], "refs": [], "grn_ids": [], "supplier_dn_numbers": [],
                  "declared_qty_total": 0.0, "warehouse_id": po["warehouse_id"]})
        db.wms_tasks.insert_one(dict(t))
        tasks.append(t)
    return po, tasks


def grn(s, po, lines, dn):
    g = ok(s.post(f"{BASE}/goods-receipts", json={"partner_type": "supplier", "partner_id": po["supplier_id"],
                                                 "warehouse_id": po["warehouse_id"], "po_ids": [po["id"]]}))
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/manual-entry", json={"expected_version": g["version"]}))
    g = ok(s.patch(f"{BASE}/goods-receipts/{g['id']}/dn", json={"expected_version": g["version"], "number": dn,
                                                              "date": "2026-10-03", "recipient_name": T}))
    for task, qty, rolls in lines:
        g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/lines", json={
            "expected_version": g["version"], "declared": {"qty": qty, "unit": task.get("unit"), "rolls": rolls},
            "target": {"type": "po_task", "task_id": task["id"]}, "description": f"{T} barang"}))
    return ok(s.post(f"{BASE}/goods-receipts/{g['id']}/start-count", json={"expected_version": g["version"]}))


def count(s, g, per_line):
    for line_no, lengths in per_line.items():
        for n in lengths:
            ok(s.post(f"{BASE}/goods-receipts/{g['id']}/lines/{line_no}/rolls", json={"length": n, "lot": f"{T}-L{line_no}"}))
    v = db.goods_receipts.find_one({"id": g["id"]})["version"]
    return ok(s.post(f"{BASE}/goods-receipts/{g['id']}/finish-count", json={"expected_version": v}))


def active_tasks(po_id, pid):
    return list(db.wms_tasks.find({"po_id": po_id, "product_id": pid, "flow_type": "inbound",
                                   "status": {"$in": ["waiting_goods", "receiving", "qc_check", "put_away"]}}, {"_id": 0}))


def run(s):
    po, (ta, tb) = fixture()
    # GRN 1: baris A penuh (60 = 2 roll), baris B dipecah dua baris SJ (50 + 20) dari 120 → sisa 50
    g = grn(s, po, [(ta, 60, 2), (tb, 50, 1), (tb, 20, 1)], f"{T}-SJ1")
    g = count(s, g, {1: [30, 30], 2: [50], 3: [20]})
    blockers = [d for d in g.get("discrepancies") or [] if d.get("blocking")]
    check("GRN-04", "3 baris (2 tugas) sesuai SJ → rekonsiliasi tanpa pemblokir", g["status"] == "reconcile" and not blockers,
          [d["key"] for d in blockers])
    out = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/close", json={"expected_version": g["version"]}))
    res = {r["result_ref"]: r for r in out["results"]}
    check("GRN-04", "GRN closed; semua baris terposting done", out["grn"]["status"] == "closed"
          and all((ln.get("posted") or {}).get("status") == "done" for ln in out["grn"]["lines"]), out["grn"]["status"])
    check("GRN-04", "dua baris SJ ke tugas yang sama diposting SEKALI sebagai satu grup",
          len(out["results"]) == 2 and sorted(res[tb["id"]]["lines"]) == [2, 3], out["results"])
    pod = db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})
    rec = {i["product_id"]: float(i.get("received_qty") or 0) for i in pod["items"]}
    check("GRN-04", "PO received_qty: A 60, B 70 (50+20)", rec == {ta["product_id"]: 60.0, tb["product_id"]: 70.0}, rec)
    ra, rb = res[ta["id"]]["remainder"], res[tb["id"]]["remainder"]
    check("GRN-04", "baris penuh tidak membentuk tugas sisa", not ra["created"] and ra["reason"] == "fulfilled"
          and not active_tasks(po["id"], ta["product_id"]), ra)
    act_b = active_tasks(po["id"], tb["product_id"])
    check("GRN-04", "baris parsial → tepat SATU tugas sisa expected 50, remainder_of tugas asal",
          rb["created"] and rb["remaining"] == 50 and len(act_b) == 1 and act_b[0]["expected_qty"] == 50
          and act_b[0]["remainder_of"] == tb["id"] and act_b[0]["received_qty"] == 0, (rb, [(t["id"], t["expected_qty"]) for t in act_b]))
    from asyncio import run as arun
    from services.goods_receipt_close_service import ensure_remainder_task
    again = arun(ensure_remainder_task(po["id"], tb["product_id"], T, tb["id"]))
    check("GRN-04", "ensure_remainder_task ulang idempoten (exists, tidak menggandakan)",
          not again["created"] and again["reason"] == "exists" and len(active_tasks(po["id"], tb["product_id"])) == 1, again)
    dbl = s.post(f"{BASE}/goods-receipts/{g['id']}/close", json={"expected_version": out["grn"]["version"]})
    rolls1 = db.inventory_rolls.count_documents({"grn_id": g["id"]})
    check("GRN-04", "close ulang ditolak 409; roll GRN tetap 4", dbl.status_code == 409 and rolls1 == 4, f"{dbl.status_code} rolls={rolls1}")
    # GRN 2: sisa 50 datang penuh → tidak ada sisa lagi, PO B = 120
    rem_task = act_b[0]
    g2 = grn(s, po, [(rem_task, 50, 1)], f"{T}-SJ2")
    g2 = count(s, g2, {1: [50]})
    out2 = ok(s.post(f"{BASE}/goods-receipts/{g2['id']}/close", json={"expected_version": g2["version"]}))
    r2 = out2["results"][0]["remainder"]
    pod = db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})
    rec = {i["product_id"]: float(i.get("received_qty") or 0) for i in pod["items"]}
    check("GRN-04", "kiriman sisa lunas → tanpa tugas sisa baru, PO B 120, tak ada tugas aktif",
          out2["grn"]["status"] == "closed" and not r2["created"] and rec[tb["product_id"]] == 120.0
          and not active_tasks(po["id"], tb["product_id"]), (r2, rec))
    total = sum(float(r.get("length_initial") or 0) for r in
                db.inventory_rolls.find({"grn_id": {"$in": [g["id"], g2["id"]]}}, {"_id": 0}))
    check("GRN-04", "Σ panjang roll dari 2 GRN = Σ received PO (180)", round(total, 2) == 180.0, total)


def main():
    full = snapshot_stock(["inventory_balances", "number_sequences"])
    ids = snapshot_new_ids(NEW)
    s = login("admin@kainnusantara.id")
    try:
        run(s)
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        check("GRN-04", "eksekusi skenario", False, repr(exc)[:200])
    finally:
        purge_new_ids(ids, verbose=False)
        restore_stock(full)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


if __name__ == "__main__":
    main()
