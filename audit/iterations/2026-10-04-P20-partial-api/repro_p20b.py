"""P20b — PROD-02 (WO complete: jurnal gagal → retry tidak menggandakan output/konsumsi) ·
PROD-05 (makloon: issue → kiriman sebagian (batal & ulang) → kiriman akhir → biaya jasa/WIP → klaim potong bon).

Usage: cd /app/backend && python ../audit/iterations/2026-10-04-P20-partial-api/repro_p20b.py
Self-clean: dokumen/roll/jurnal baru dihapus; MKO, saldo, akun GL, nomor dipulihkan.
"""
import io
import json
import os
import sys
import uuid
from collections import defaultdict

import requests
from dotenv import load_dotenv
from PIL import Image
from pymongo import MongoClient

sys.path.insert(0, ".")
load_dotenv(".env")
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402

BASE = "http://localhost:8001/api"
ENT = "ent_ksc"
T = f"TEST_P20B_{uuid.uuid4().hex[:6]}"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
NEW = ["inventory_rolls", "inventory_movements", "inventory_lots", "journal_entries", "notifications", "audit_logs",
       "doc_refs", "goods_receipts", "supplier_dn_profiles", "wms_tasks", "vendor_bills", "mfg_boms", "mfg_work_orders",
       "saga_locks", "posting_failures", "gl_outbox", "roll_cost_history", "timeline_events", "lot_genealogy", "uploads"]
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


def net(q):
    tot = defaultdict(float)
    for j in db.journal_entries.find({**q, "status": {"$ne": "void"}}, {"_id": 0, "lines": 1}):
        for ln in j["lines"]:
            tot[ln["account_code"]] += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return {k: round(v, 2) for k, v in tot.items() if abs(v) > 0.005}


def free_len(pid, wh="wh_jakarta"):
    return round(sum(float(r["length_remaining"]) - float(r.get("length_reserved") or 0) for r in db.inventory_rolls.find(
        {"product_id": pid, "warehouse_id": wh, "owner_entity_id": ENT, "status": "available"})), 2)


def prod02(s):
    mat, out = "prod_batik_mega", "prod_tenun_ikat"
    bom = ok(s.post(f"{BASE}/production/boms", json={"name": f"{T} BOM", "output_product_id": out, "overhead_per_unit": 5000,
                                                     "components": [{"material_product_id": mat, "qty_per_unit": 1}]}))
    wo = ok(s.post(f"{BASE}/production/work-orders", json={"bom_id": bom["id"], "planned_qty": 4, "warehouse_id": "wh_jakarta",
                                                           "notes": T}))
    ok(s.post(f"{BASE}/production/work-orders/{wo['id']}/release"))
    m0 = free_len(mat)
    db.gl_accounts.update_many({"code": "5-1100"}, {"$set": {"is_active": False}})
    r1 = s.post(f"{BASE}/production/work-orders/{wo['id']}/complete")
    w = db.mfg_work_orders.find_one({"id": wo["id"]}, {"_id": 0})
    outs = db.inventory_rolls.count_documents({"acquired.via": "production_output", "acquired.ref_id": wo["id"]})
    check("PROD-02", "jurnal overhead gagal → complete ditolak 4xx berpesan jelas (bukan 500), WO tetap released, kunci tercatat gagal",
          400 <= r1.status_code < 500 and "5-1100" in r1.text and w["status"] == "released" and (w.get("saga_lock") or {}).get("failed_at"),
          (r1.status_code, r1.text[:160], w["status"], (w.get("saga_lock") or {}).get("error")))
    check("PROD-02", "efek fisik tercatat SEKALI sebelum gagal: bahan −4, 1 roll output, tahap 'output', tanpa jurnal",
          round(m0 - free_len(mat), 2) == 4 and outs == 1 and (w.get("completion") or {}).get("stage") == "output"
          and not net({"source_type": "production_output", "source_id": wo["id"]}),
          (m0, free_len(mat), outs, (w.get("completion") or {}).get("stage")))
    r2 = s.post(f"{BASE}/production/work-orders/{wo['id']}/complete")
    check("PROD-02", "complete ulang saat kunci gagal belum dilepas → 409, tidak ada konsumsi/output tambahan",
          r2.status_code == 409 and round(m0 - free_len(mat), 2) == 4
          and db.inventory_rolls.count_documents({"acquired.via": "production_output", "acquired.ref_id": wo["id"]}) == 1,
          (r2.status_code, r2.text[:120]))
    db.gl_accounts.update_many({"code": "5-1100"}, {"$set": {"is_active": True}})
    lk = s.post(f"{BASE}/saga-locks/mfg_work_orders/{wo['id']}/release",
                json={"reason": f"{T} akun overhead sudah aktif lagi", "acknowledge_effects": True})
    r3 = s.post(f"{BASE}/production/work-orders/{wo['id']}/complete")
    w = db.mfg_work_orders.find_one({"id": wo["id"]}, {"_id": 0})
    rolls = list(db.inventory_rolls.find({"acquired.via": "production_output", "acquired.ref_id": wo["id"]}, {"_id": 0}))
    n = net({"source_type": "production_output", "source_id": wo["id"]})
    check("PROD-02", "lepas kunci (admin, alasan) → retry: WO completed, tetap 1 roll output 4, bahan −4 (bukan −8)",
          lk.status_code == 200 and r3.status_code == 200 and w["status"] == "completed" and len(rolls) == 1
          and float(rolls[0]["length_remaining"]) == 4 and round(m0 - free_len(mat), 2) == 4,
          (lk.status_code, lk.text[:120], r3.status_code, r3.text[:120], w["status"], len(rolls)))
    check("PROD-02", "tepat 1 jurnal overhead 20.000 (Dr 1-1300 / Cr 5-1100); HPP output = bahan + overhead",
          db.journal_entries.count_documents({"source_type": "production_output", "source_id": wo["id"], "status": {"$ne": "void"}}) == 1
          and n == {"1-1300": 20000.0, "5-1100": -20000.0}
          and round(float(w["total_cost"]), 2) == round(float(w["material_cost"]) + 20000, 2) and not w.get("saga_lock"),
          (n, w.get("material_cost"), w.get("total_cost")))
    r4 = s.post(f"{BASE}/production/work-orders/{wo['id']}/complete")
    check("PROD-02", "complete ke-3 (sudah completed) idempoten: tanpa output/jurnal tambahan",
          r4.status_code == 200 and db.inventory_rolls.count_documents({"acquired.ref_id": wo["id"], "acquired.via": "production_output"}) == 1
          and net({"source_type": "production_output", "source_id": wo["id"]}) == n, r4.status_code)


def photo():
    buf = io.BytesIO()
    Image.new("RGB", (800, 1000), "white").save(buf, "JPEG")
    return buf.getvalue()


def mko_grn(s, mko, step, dn, lengths, partial):
    g = ok(s.post(f"{BASE}/goods-receipts", json={"partner_type": "makloon", "partner_id": step["makloon_id"],
                                                 "warehouse_id": step.get("from_warehouse_id") or "wh_surabaya", "mko_ids": [mko["id"]]}))
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/files", files={"file": ("sj.jpg", photo(), "image/jpeg")},
                  data={"expected_version": str(g["version"])}))["grn"]
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/manual-entry", json={"expected_version": g["version"]}))
    g = ok(s.patch(f"{BASE}/goods-receipts/{g['id']}/dn", json={"expected_version": g["version"], "number": dn}))
    lot = f"{T}-MKL"
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/lines", json={
        "expected_version": g["version"], "role": "output",
        "declared": {"qty": sum(lengths), "unit": step.get("output_unit") or "yard", "rolls": len(lengths), "lot": lot},
        "target": {"type": "mko_step", "mko_id": mko["id"], "step_seq": step["seq"]}, "description": f"{T} hasil"}))
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/start-count", json={"expected_version": g["version"]}))
    for ln in lengths:
        g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/lines/1/rolls", json={"length": ln, "lot": lot, "grade": "A"}))["grn"]
    g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/finish-count", json={"expected_version": g["version"]}))
    for d in [d for d in g.get("discrepancies") or [] if d.get("blocking") and not d.get("resolution")]:
        g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/discrepancies/{d['key']}/resolve", json={
            "expected_version": g["version"], "action": "accept_note", "reason": f"{T} terima"}))
    if partial:
        g = ok(s.post(f"{BASE}/goods-receipts/{g['id']}/mko-partial", json={"expected_version": g["version"], "partial": True}))
    return ok(s.post(f"{BASE}/goods-receipts/{g['id']}/close", json={"expected_version": g["version"]}))["grn"]


def step_of(mko_id, seq=1):
    return next(x for x in db.makloon_orders.find_one({"id": mko_id})["steps"] if x["seq"] == seq)


def prod05(s):
    mko = db.makloon_orders.find_one({"entity_id": ENT, "steps": {"$elemMatch": {"status": "issued", "material_flow": "moves"}}}, {"_id": 0})
    step = next(x for x in mko["steps"] if x["status"] == "issued")
    src = f"{mko['id']}:{step['seq']}"
    wip0 = net({"source_id": src}).get("1-1350", 0)
    rq = {"acquired.via": "subcon_receipt", "acquired.ref_id": mko["id"]}
    pre = {r["id"] for r in db.inventory_rolls.find(rq, {"id": 1})}
    rq = {**rq, "id": {"$nin": list(pre)}}
    check("PROD-05", "langkah MKO sudah di-issue: WIP (1-1350) bertambah sebesar nilai bahan", wip0 > 0, (mko["mko_number"], wip0))
    g1 = mko_grn(s, mko, step, f"{T}-P1", [15.0, 15.0], True)
    st = step_of(mko["id"], step["seq"])
    out_rolls = lambda: db.inventory_rolls.count_documents({**rq, "status": {"$ne": "receiving"}})  # noqa: E731
    check("PROD-05", "kiriman sebagian 30 → GRN closed, langkah tetap issued, kiriman DITAHAN (tanpa stok/tagihan)",
          g1["status"] == "closed" and st["status"] == "issued" and len(st.get("partial_receipts") or []) == 1
          and out_rolls() == 0 and not st.get("service_bill_id"), (g1["status"], st["status"], out_rolls()))
    bad = s.post(f"{BASE}/makloon-orders/{mko['id']}/steps/{step['seq']}/partial-receipts/{g1['id']}/cancel", json={"reason": "x"})
    cx = s.post(f"{BASE}/makloon-orders/{mko['id']}/steps/{step['seq']}/partial-receipts/{g1['id']}/cancel",
                json={"reason": f"{T} SJ salah gudang"})
    st = step_of(mko["id"], step["seq"])
    check("PROD-05", "batal kiriman sebagian: alasan pendek 400; sukses → partial kosong, GRN cancelled",
          bad.status_code == 400 and cx.status_code == 200 and not st.get("partial_receipts")
          and db.goods_receipts.find_one({"id": g1["id"]})["status"] == "cancelled", (bad.status_code, cx.status_code, cx.text[:120]))
    g2 = mko_grn(s, mko, step, f"{T}-P2", [15.0, 15.0], True)
    g3 = mko_grn(s, mko, step, f"{T}-P3", [21.0, 21.0], False)
    st = step_of(mko["id"], step["seq"])
    rolls = list(db.inventory_rolls.find(rq, {"_id": 0}))
    check("PROD-05", "kiriman akhir menyerap kiriman sebagian: langkah received, 4 roll = 72 (bukan 102), actual_output 72",
          g3["status"] == "closed" and st["status"] == "received" and len(rolls) == 4
          and round(sum(float(r["length_remaining"]) for r in rolls), 2) == 72 and round(float(st.get("actual_output_qty") or 0), 2) == 72,
          (g3["status"], st["status"], len(rolls), [r["length_remaining"] for r in rolls], st.get("actual_output_qty")))
    bills = list(db.vendor_bills.find({"bill_type": "makloon_service", "$or": [{"mko_id": mko["id"]}, {"id": st.get("service_bill_id")}]}, {"_id": 0}))
    bill = next((b for b in bills if b["id"] == st.get("service_bill_id")), {})
    check("PROD-05", "tepat 1 tagihan jasa makloon untuk langkah ini (kiriman sebagian tak membuat tagihan sendiri)",
          len([b for b in bills if b.get("step_seq", step["seq"]) == step["seq"]]) == 1 and float(bill.get("grand_total") or 0) > 0,
          [(b.get("bill_number"), b.get("grand_total"), b.get("step_seq")) for b in bills])
    n = net({"source_id": {"$in": [src, bill.get("id", "")]}})
    out_val = round(sum(float(r.get("unit_cost") or 0) * float(r["length_remaining"]) for r in rolls), 2)
    check("PROD-05", "biaya: WIP langkah ter-clear (net 1-1350 = 0); nilai roll output = bahan + jasa (±1)",
          abs(n.get("1-1350", 0)) < 0.01 and abs(out_val - (wip0 + float(bill.get("net_amount") or bill.get("grand_total") or 0))) <= 1
          and round(float(st.get("output_value") or 0)) == round(out_val), (n, out_val, wip0, bill.get("net_amount"), st.get("output_value")))
    g_partial = db.goods_receipts.find_one({"id": g2["id"]}, {"_id": 0, "status": 1})
    check("PROD-05", "GRN kiriman sebagian tertaut ke tagihan akhir; tidak bisa dibatalkan lagi (409)",
          s.post(f"{BASE}/makloon-orders/{mko['id']}/steps/{step['seq']}/partial-receipts/{g2['id']}/cancel",
                 json={"reason": f"{T} coba batal"}).status_code in (404, 409) and g_partial["status"] == "closed", g_partial)
    grand0 = float(bill["grand_total"])
    over = s.post(f"{BASE}/makloon-orders/{mko['id']}/claim", json={"step_seq": step["seq"], "action": "potong_bon",
                                                                    "amount": grand0 + 1, "reason": f"{T} cacat"})
    if over.status_code == 200:
        over = s.post(f"{BASE}/makloon-orders/{mko['id']}/claim/approve", json={"step_seq": step["seq"], "note": T})
    st = step_of(mko["id"], step["seq"])
    if (st.get("claim") or {}).get("status") == "pending_approval":
        db.makloon_orders.update_one({"id": mko["id"], "steps.seq": step["seq"]}, {"$unset": {"steps.$.claim": ""}})
    check("PROD-05", "retur/klaim potong bon > sisa tagihan ditolak 400 tanpa jurnal", over.status_code == 400
          and not db.journal_entries.find_one({"source_type": {"$regex": "makloon_claim"}, "source_id": {"$regex": mko["id"]}}),
          (over.status_code, over.text[:150]))
    sales = login("sales@kainnusantara.id")
    ok(s.post(f"{BASE}/makloon-orders/{mko['id']}/claim", json={"step_seq": step["seq"], "action": "potong_bon",
                                                               "amount": 50000, "reason": f"{T} 3 yd cacat tenun"}))
    deny = sales.post(f"{BASE}/makloon-orders/{mko['id']}/claim/approve", json={"step_seq": step["seq"], "note": T})
    apv = s.post(f"{BASE}/makloon-orders/{mko['id']}/claim/approve", json={"step_seq": step["seq"], "note": T})
    b2 = db.vendor_bills.find_one({"id": bill["id"]}, {"_id": 0})
    cje = list(db.journal_entries.find({"source_type": {"$regex": "makloon_claim"}, "source_id": {"$regex": mko["id"]}}, {"_id": 0}))
    bal = cje and round(sum(float(x.get("debit") or 0) for x in cje[0]["lines"]), 2) == round(sum(float(x.get("credit") or 0) for x in cje[0]["lines"]), 2) == 50000
    check("PROD-05", "klaim potong bon 50.000: sales tak bisa menyetujui (403); disetujui → tagihan jasa −50.000, 1 jurnal klaim seimbang",
          deny.status_code == 403 and apv.status_code == 200 and round(grand0 - float(b2["grand_total"]), 2) == 50000
          and len(cje) == 1 and bal, (deny.status_code, apv.status_code, apv.text[:120], b2.get("grand_total"), len(cje)))
    again = s.post(f"{BASE}/makloon-orders/{mko['id']}/claim/approve", json={"step_seq": step["seq"], "note": T})
    check("PROD-05", "setujui ulang → 400, potongan tidak ganda", again.status_code == 400
          and float(db.vendor_bills.find_one({"id": bill["id"]})["grand_total"]) == float(b2["grand_total"]), again.status_code)


def main():
    full = snapshot_stock(["inventory_balances", "number_sequences", "system_settings", "gl_accounts", "makloon_orders",
                           "inventory_rolls", "inventory_lots"])
    ids = snapshot_new_ids(NEW)
    s = login("admin@kainnusantara.id")
    try:
        for fn in (prod02, prod05):
            try:
                fn(s)
            except Exception as exc:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check("RUN", f"eksekusi {fn.__name__}", False, repr(exc)[:300])
    finally:
        db.gl_accounts.update_many({"code": "5-1100"}, {"$set": {"is_active": True}})
        purge_new_ids(ids, verbose=False)
        restore_stock(full)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


if __name__ == "__main__":
    main()
