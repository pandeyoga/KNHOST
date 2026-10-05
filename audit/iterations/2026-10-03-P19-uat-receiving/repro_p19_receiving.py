"""P19 — GRN-01 · QC-04 · QC-06: rantai penerimaan end-to-end lewat API (self-clean).

Usage: cd /app/backend && python ../audit/iterations/2026-10-03-P19-uat-receiving/repro_p19_receiving.py
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

BASE = "http://localhost:8001/api"
ENT = "ent_ksc"
T = f"TEST_P19_{uuid.uuid4().hex[:6]}"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
NEW = ["inventory_rolls", "inventory_movements", "inventory_lots", "journal_entries", "inspections", "notifications",
       "audit_logs", "rfid_tags", "doc_refs", "backorders", "qc_inspections", "goods_receipts", "supplier_dn_profiles",
       "wms_tasks", "purchase_orders", "purchase_returns", "vendor_bills", "approval_requests", "timeline_events"]
results = []


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


def make_po(s, qty):
    po = ok(s.post(f"{BASE}/purchase-orders", json={
        "supplier_id": db.suppliers.find_one({"name": "Cirebon Craft", "entity_id": ENT})["id"], "warehouse_id": "wh_jakarta", "notes": f"{T} PO",
        "items": [{"product_id": "prod_batik_mega", "quantity": qty, "unit": "yard", "price": 100000, "expected_grade": "A"}]}))
    po = po.get("po") or po
    tasks = list(db.wms_tasks.find({"po_id": po["id"], "flow_type": "inbound"}, {"_id": 0}))
    return po, tasks


def receive(s, po, task, lengths, dn):
    g = ok(s.post(f"{BASE}/goods-receipts", json={"partner_type": "supplier", "partner_id": po["supplier_id"],
                                                 "warehouse_id": po["warehouse_id"], "po_ids": [po["id"]]}))
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/manual-entry", json={"expected_version": g["version"]}))
    g = ok(s.patch(f"{BASE}/goods-receipts/{g['id']}/dn", json={"expected_version": g["version"], "number": dn,
                                                              "date": "2026-10-03", "recipient_name": T}))
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/lines", json={
        "expected_version": g["version"], "declared": {"qty": sum(lengths), "unit": task.get("unit"), "rolls": len(lengths)},
        "target": {"type": "po_task", "task_id": task["id"]}, "description": f"{T} barang"}))
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/start-count", json={"expected_version": g["version"]}))
    for n in lengths:
        ok(s.post(f"{BASE}/goods-receipts/{g['id']}/lines/1/rolls", json={"length": n, "lot": f"{T}-LOT"}))
    v = db.goods_receipts.find_one({"id": g["id"]})["version"]
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/finish-count", json={"expected_version": v}))
    return ok(s.post(f"{BASE}/goods-receipts/{g['id']}/close", json={"expected_version": g["version"]}))["grn"]


def balanced(je):
    d = round(sum(float(ln.get("debit") or 0) for ln in je.get("lines") or []), 2)
    c = round(sum(float(ln.get("credit") or 0) for ln in je.get("lines") or []), 2)
    return d == c and d > 0, (d, c, [(ln.get("account_code"), ln.get("debit"), ln.get("credit")) for ln in je.get("lines") or []])


def journals_for(*ids):
    return list(db.journal_entries.find({"$or": [{"source_id": {"$in": list(ids)}}, {"reference": {"$in": list(ids)}}],
                                         "status": {"$ne": "void"}}, {"_id": 0}))


def bal(pid="prod_batik_mega", wh="wh_jakarta"):
    b = db.inventory_balances.find_one({"product_id": pid, "warehouse_id": wh, "owner_entity_id": ENT}, {"_id": 0}) or {}
    return {k: float(b.get(k) or 0) for k in ("available_qty", "quarantine_qty", "blocked_qty", "on_hand_qty")}


def grn01_qc04(s):
    po, tasks = make_po(s, 50)
    check("GRN-01", "PO dibuat & 1 tugas inbound terbentuk", po.get("po_number") and len(tasks) == 1,
          (po.get("po_number"), po.get("status"), len(tasks)))
    b0 = bal()
    grn = receive(s, po, tasks[0], [50], f"{T}-SJ1")
    rolls = list(db.inventory_rolls.find({"grn_id": grn["id"]}, {"_id": 0}))
    check("GRN-01", "GRN closed bernomor KSC/GRN-", grn["status"] == "closed" and "GRN-" in grn["number"], grn["number"])
    check("GRN-01", "1 roll 50 berstatus karantina (bukan ATP)", len(rolls) == 1 and rolls[0]["status"] == "quarantine"
          and rolls[0]["length_remaining"] == 50, [(r["roll_no"], r["status"], r["length_remaining"]) for r in rolls])
    b1 = bal()
    check("GRN-01", "balance: quarantine +50, available tetap", round(b1["quarantine_qty"] - b0["quarantine_qty"], 2) == 50
          and b1["available_qty"] == b0["available_qty"], (b0, b1))
    jes = journals_for(grn["id"], tasks[0]["id"], po["id"], grn["number"])
    gr_je = [j for j in jes if "goods_receipt" in (j.get("source_type") or "") or j.get("source_id") in (tasks[0]["id"], grn["id"])]
    okb, det = balanced(gr_je[0]) if gr_je else (False, jes and [j.get("source_type") for j in jes])
    check("GRN-01", "jurnal GRN posted & seimbang (Dr Persediaan / Cr GRNI)", gr_je and gr_je[0].get("status") == "posted" and okb,
          (gr_je and gr_je[0].get("entry_number"), gr_je and gr_je[0].get("source_type"), det))
    task = db.wms_tasks.find_one({"id": tasks[0]["id"]}, {"_id": 0})
    check("GRN-01", "tugas inbound qc_pending", task["status"] == "qc_pending", task["status"])

    # QC-04 — inspeksi + reject semua → retur supplier
    roll = rolls[0]
    ins = s.post(f"{BASE}/inbound/rolls/{roll['id']}/inspect", json={"defects": [{"point_value": 4, "count": 15}], "note": T})
    check("QC-04", "inspeksi 4-point tersimpan (grade BS)", ins.status_code == 200 and ins.json()["grade"] == "BS", ins.text[:200])
    dec = ok(s.post(f"{BASE}/inbound/tasks/{task['id']}/qc-decision", json={
        "accept_qty": 0, "reject_qty": 50, "reject_disposition": "return", "reason": f"{T} cacat berat"}))
    pr = dec.get("purchase_return") or {}
    rr = db.inventory_rolls.find_one({"id": roll["id"]}, {"_id": 0})
    check("QC-04", "reject semua → roll returned_supplier & Purchase Return otomatis", rr["status"] == "returned_supplier"
          and pr.get("number") and dec["qc_status"] == "rejected", (rr["status"], pr, dec.get("qc_status")))
    b2 = bal()
    check("QC-04", "balance: quarantine kembali, on_hand tidak bertambah", b2["quarantine_qty"] == b0["quarantine_qty"]
          and b2["on_hand_qty"] == b0["on_hand_qty"], (b0, b2))
    po_before = db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})
    ap = ok(s.post(f"{BASE}/purchase-returns/{pr['id']}/approve", json={"notes": T}))
    ret = db.purchase_returns.find_one({"id": pr["id"]}, {"_id": 0})
    po_after = db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})
    check("QC-04", "approve retur → Nota Debit terbit", ret["status"] == "approved" and ret.get("debit_note_number"),
          (ret["status"], ret.get("debit_note_number"), ap.get("status")))
    ret_val = round(float(po_after.get("returned_amount") or 0) - float(po_before.get("returned_amount") or 0), 2)
    gross_po = float(po_after.get("grand_total") or po_after.get("total_amount") or 0)
    check("QC-04", "hutang PO berkurang sebesar nilai retur (termasuk PPN) — retur penuh → sisa hutang 0",
          ret_val > 0 and abs(ret_val - gross_po) < 1, (ret_val, gross_po, po_after.get("payment_status"),
                                                       ret.get("total_amount"), ret.get("ppn_amount"), ret.get("grand_total")))
    rje = journals_for(pr["id"])
    okr, detr = balanced(rje[0]) if rje else (False, None)
    check("QC-04", "jurnal retur posted & seimbang", rje and okr, detr)
    pod = ok(s.get(f"{BASE}/purchase-orders/{po['id']}"))
    check("QC-04", "PO diretur penuh → status bayar 'settled_by_return' (Lunas lewat retur), outstanding 0",
          po_after.get("payment_status") == "settled_by_return" and pod["financials"]["payment_status"] == "settled_by_return"
          and pod["financials"]["outstanding"] == 0, (po_after.get("payment_status"), pod["financials"]))
    lst = ok(s.get(f"{BASE}/purchase-orders", params={"page": 1, "page_size": 100, "payment": "settled_by_return"}))
    cnt = ok(s.get(f"{BASE}/purchase-orders/status-counts", params={"payment": "settled_by_return"}))
    unp = ok(s.get(f"{BASE}/purchase-orders", params={"page": 1, "page_size": 100, "payment": "unpaid"}))
    check("QC-04", "chip filter ?payment=settled_by_return memuat PO ini (unpaid tidak); by_payment terhitung",
          po["id"] in [i["id"] for i in lst["items"]] and po["id"] not in [i["id"] for i in unp["items"]]
          and cnt["by_payment"].get("settled_by_return", 0) >= 1 and cnt["total"] == lst["total"],
          (lst["total"], cnt))
    rv = s.post(f"{BASE}/purchase-returns/{pr['id']}/reverse", json={"notes": f"{T} uji balik"})
    po_rev = db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})
    check("QC-04", "retur dibalik → status bayar kembali 'unpaid' & outstanding pulih",
          rv.status_code == 200 and po_rev.get("payment_status") == "unpaid" and float(po_rev.get("outstanding") or 0) > 0,
          (rv.status_code, rv.text[:150], po_rev.get("payment_status"), po_rev.get("outstanding")))
    return po


def qc04_accept(s):
    po, tasks = make_po(s, 40)
    grn = receive(s, po, tasks[0], [40], f"{T}-SJ2")
    roll = db.inventory_rolls.find_one({"grn_id": grn["id"]}, {"_id": 0})
    ok(s.post(f"{BASE}/inbound/rolls/{roll['id']}/inspect", json={"defects": [], "note": T}))
    dec = ok(s.post(f"{BASE}/inbound/tasks/{tasks[0]['id']}/qc-decision", json={
        "accept_qty": 40, "reject_qty": 0, "accept_grade": "A", "reason": T}))
    rr = db.inventory_rolls.find_one({"id": roll["id"]}, {"_id": 0})
    check("QC-04", "variasi ACCEPT semua → roll available, keluar karantina", rr["status"] == "available"
          and dec["qc_status"] == "passed", (rr["status"], dec.get("qc_status")))


def qc06(s, mgr_sales):
    po, tasks = make_po(s, 150)
    grn = receive(s, po, tasks[0], [50, 50, 50], f"{T}-SJ3")
    tid = tasks[0]["id"]
    rolls = sorted(db.inventory_rolls.find({"grn_id": grn["id"]}, {"_id": 0}), key=lambda r: r["roll_no"])
    check("QC-06", "3 roll karantina", len(rolls) == 3 and all(r["status"] == "quarantine" for r in rolls),
          [r["status"] for r in rolls])
    cov = ok(s.put(f"{BASE}/inbound/qc/tasks/{tid}/plan", json={"mode": "sampling", "sample_pct": 30, "sample_min": 1}))
    check("QC-06", "rencana sampling 30% dari 3 roll → wajib 1 roll", cov["required_rolls"] == 1 and not cov["met"], cov)
    ok(s.post(f"{BASE}/inbound/rolls/{rolls[0]['id']}/inspect", json={"defects": [{"point_value": 1, "count": 2}], "note": T}))
    cov = ok(s.get(f"{BASE}/inbound/qc/tasks/{tid}/plan"))
    check("QC-06", "1/3 diinspeksi → cakupan sampling terpenuhi", cov["met"] and cov["inspected_rolls"] == 1, cov)
    # HOLD roll ke-2 (belum diinspeksi)
    b0 = bal()
    short = s.post(f"{BASE}/inventory/rolls/{rolls[1]['id']}/hold", json={"reason": "x"})
    check("QC-06", "hold tanpa alasan memadai → 400", short.status_code == 400, short.status_code)
    h = ok(s.post(f"{BASE}/inventory/rolls/{rolls[1]['id']}/hold", json={"reason": f"{T} cek shading"}))["roll"]
    b1 = bal()
    check("QC-06", "hold → status blocked, quarantine −50, blocked +50", h["status"] == "blocked"
          and round(b0["quarantine_qty"] - b1["quarantine_qty"], 2) == 50 and round(b1["blocked_qty"] - b0["blocked_qty"], 2) == 50, (b0, b1))
    blocked_dec = s.post(f"{BASE}/inbound/tasks/{tid}/qc-decision", json={"accept_qty": 100, "reject_qty": 0, "accept_grade": "A", "reason": T})
    check("QC-06", "keputusan QC ditolak selama ada roll DITAHAN", blocked_dec.status_code == 400 and "DITAHAN" in blocked_dec.text,
          blocked_dec.text[:200])
    no_perm = mgr_sales.post(f"{BASE}/inventory/rolls/{rolls[1]['id']}/release", json={"note": "lepas sales"})
    check("QC-06", "release oleh sales (tanpa wms.approve) → 403", no_perm.status_code == 403, no_perm.status_code)
    rel = ok(s.post(f"{BASE}/inventory/rolls/{rolls[1]['id']}/release", json={"note": f"{T} shading OK"}))["roll"]
    b2 = bal()
    check("QC-06", "release → kembali quarantine; balance pulih", rel["status"] == "quarantine" and b2 == b0, (rel["status"], b0, b2))
    again = s.post(f"{BASE}/inventory/rolls/{rolls[1]['id']}/release", json={"note": "ulang"})
    check("QC-06", "release roll yang tidak ditahan → 400", again.status_code == 400, again.status_code)
    st = [db.inventory_rolls.find_one({"id": r["id"]})["status"] for r in rolls]
    check("QC-06", "roll belum diinspeksi tetap karantina sebelum keputusan", st == ["quarantine"] * 3, st)
    dec = ok(s.post(f"{BASE}/inbound/tasks/{tid}/qc-decision", json={"accept_qty": 150, "reject_qty": 0, "accept_grade": "A", "reason": T}))
    after = [db.inventory_rolls.find_one({"id": r["id"]}, {"_id": 0}) for r in rolls]
    check("QC-06", "keputusan sampel berlaku ke sisa lot: 3 roll available; 2 roll tak-terinspeksi ditandai qc_via_sampling",
          all(r["status"] == "available" for r in after) and [bool(r.get("qc_via_sampling")) for r in after] == [False, True, True]
          and dec["qc_coverage"]["decision_applies_to_uninspected"], [(r["status"], bool(r.get("qc_via_sampling"))) for r in after])
    # hold/release pada roll available → keluar/masuk ATP
    b3 = bal()
    ok(s.post(f"{BASE}/inventory/rolls/{rolls[2]['id']}/hold", json={"reason": f"{T} klaim pelanggan"}))
    b4 = bal()
    ok(s.post(f"{BASE}/inventory/rolls/{rolls[2]['id']}/release", json={"note": f"{T} klaim selesai"}))
    b5 = bal()
    check("QC-06", "hold roll available → available −50 (keluar ATP); release → pulih",
          round(b3["available_qty"] - b4["available_qty"], 2) == 50 and b5 == b3, (b3, b4, b5))
    tl = ok(s.get(f"{BASE}/inventory/rolls/{rolls[1]['id']}/journey-timeline"))
    labels = " | ".join(e["label"] for e in tl["events"])
    want = [f"GRN {grn['number']}", "SAMPLING", "Keputusan QC: DITERIMA", "DITAHAN oleh", "Tahanan DILEPAS"]
    check("QC-06", "genealogy roll: asal GRN, sampling, keputusan QC, tahan/lepas", all(w in labels for w in want),
          [w for w in want if w not in labels] or labels[:300])
    tl0 = ok(s.get(f"{BASE}/inventory/rolls/{rolls[0]['id']}/journey-timeline"))
    check("QC-06", "genealogy roll terinspeksi memuat event Inspeksi 4-point",
          any("Inspeksi 4-point" in e["label"] for e in tl0["events"]), [e["label"] for e in tl0["events"]][:6])


def main():
    full = snapshot_stock(["inventory_balances", "number_sequences", "system_settings"])
    ids = snapshot_new_ids(NEW)
    s = login("admin@kainnusantara.id")
    sales = login("sales@kainnusantara.id")
    try:
        for fn in (lambda: grn01_qc04(s), lambda: qc04_accept(s), lambda: qc06(s, sales)):
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check("RUN", "eksekusi skenario", False, repr(exc)[:300])
    finally:
        purge_new_ids(ids, verbose=False)
        restore_stock(full)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


if __name__ == "__main__":
    main()
