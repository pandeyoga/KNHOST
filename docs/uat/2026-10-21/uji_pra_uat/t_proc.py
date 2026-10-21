# Cabang PENGADAAN: PR (dari SO kurang) -> PO -> Kedatangan Barang (SJ) -> hitung roll -> rekonsiliasi -> tutup -> QC -> stok
import os
PR = os.environ.get("PR", "pr_ba51772c657a")
SO = os.environ.get("SO", "so_485cecbd17f4")
mgr = Api("manager@kainnusantara.id"); adm = Api("admin@kainnusantara.id")
wh = Api("warehouse@kainnusantara.id"); whadm = Api("wh.admin@kainnusantara.id"); qc = Api("qc@kainnusantara.id")
sadm = Api("salesadmin@kainnusantara.id"); md = Api("md@kainnusantara.id")

c, pr = mgr.get(f"/purchase-requisitions/{PR}")
step("PR", c, {k: pr.get(k) for k in ("number", "status", "warehouse_id", "preferred_supplier_id")} if isinstance(pr, dict) else pr)
print("baris PR:", [(l.get("line_no"), l.get("product_name"), l.get("quantity"), l.get("unit"), l.get("mode") or l.get("route")) for l in pr.get("items", [])])
c, sup = mgr.get("/purchase-requisitions/eligible-suppliers", params={"product_id": pr["items"][0]["product_id"]})
sl = sup if isinstance(sup, list) else sup.get("items", sup.get("suppliers", []))
step("supplier layak", c, [(s.get("id"), s.get("name"), s.get("reason") or s.get("source")) for s in sl][:5])
c, srcv = mgr.get(f"/purchase-requisitions/{PR}/sourcing")
step("sourcing PR", c, short(srcv, 700))
c, allsup = mgr.get("/suppliers")
asl = allsup if isinstance(allsup, list) else allsup.get("items", [])
SUP = (sl[0].get("id") if sl else None) or (asl[0]["id"] if asl else "")
c, b = md.post(f"/purchase-requisitions/{PR}/realize-po", {"supplier_id": SUP, "warehouse_id": "wh_jakarta"})
step("CEK: MD realisasi PO (izin)", c, short(b, 300), (200, 400, 403))
c, b = mgr.post(f"/purchase-requisitions/{PR}/realize-po", {"supplier_id": SUP, "warehouse_id": "wh_jakarta", "notes": "UAT"})
if c != 200:
    step("info realize-po", c, b, (400, 409))
    c, b = mgr.post(f"/purchase-requisitions/{PR}/convert-to-po", {"supplier_id": SUP, "warehouse_id": "wh_jakarta"})
po = need("mgr: realisasi PR -> PO", c, b)
PO = (po.get("po") or {}).get("id")
print("PO", (po.get("po") or {}).get("po_number"), (po.get("po") or {}).get("status"), (po.get("po") or {}).get("total_amount") or (po.get("po") or {}).get("grand_total"))
c, b = mgr.post(f"/purchase-requisitions/{PR}/realize-po", {"supplier_id": SUP, "warehouse_id": "wh_jakarta"})
step("NEG realisasi PR yang sama dua kali", c, short(b, 300), (400, 409))
c, b = mgr.post(f"/purchase-orders/{PO}/approve", {"notes": "UAT"})
step("mgr: setujui/kirim PO", c, {k: b.get(k) for k in ("po_number", "status")} if isinstance(b, dict) and "status" in b else b, (200, 400, 409))
c, pod = mgr.get(f"/purchase-orders/{PO}")
print("PO status:", pod.get("status"), "items", [(i.get("quantity"), i.get("unit"), i.get("received_qty")) for i in pod.get("items", [])], "tasks?", short(pod.get("inbound_task_ids") or pod.get("tasks"), 200))
c, tasks = wh.get("/inbound/tasks")
tl = [t for t in (tasks if isinstance(tasks, list) else tasks.get("items", [])) if t.get("po_id") == PO]
step("gudang: tugas inbound PO", c, [(t["id"], t.get("status"), t.get("quantity"), t.get("unit")) for t in tl])

# Kedatangan Barang (GRN)
c, g = wh.post("/goods-receipts", {"partner_type": "supplier", "partner_id": pod.get("supplier_id") or SUP, "warehouse_id": "wh_jakarta", "po_ids": [PO]})
step("gudang: buat Kedatangan Barang", c, {k: g.get(k) for k in ("number", "status", "version")} if isinstance(g, dict) and "status" in g else g, (200,))
if isinstance(g, dict) and g.get("id"):
    G = g["id"]; v = g.get("version", 1)
    c, g = wh._do("POST", f"/goods-receipts/{G}/manual-entry", json={"expected_version": v})
    step("gudang: entri manual (tanpa OCR)", c, {k: g.get(k) for k in ("status", "version")} if isinstance(g, dict) and "status" in g else g, (200, 400, 403, 409, 422))
    v = g.get("version", v) if isinstance(g, dict) else v
    c, g = wh._do("PATCH", f"/goods-receipts/{G}/dn", json={"expected_version": v, "number": "SJ-SUP-UAT-01", "date": "2026-10-21"})
    step("gudang: kepala SJ", c, {k: g.get(k) for k in ("status", "version")} if isinstance(g, dict) and "status" in g else g, (200, 400, 403, 404, 405, 409, 422))
    v = g.get("version", v) if isinstance(g, dict) else v
    c, tg = wh.get(f"/goods-receipts/{G}/targets")
    tgl = tg if isinstance(tg, list) else tg.get("items", tg.get("targets", []))
    print("target:", short(tgl, 500))
    t0 = tgl[0] if tgl else {}
    c, g = wh.post(f"/goods-receipts/{G}/lines", {"expected_version": v, "declared": {"qty": 40, "unit": "kg", "rolls": 2},
                                                   "target": {"type": "po_task", "task_id": t0.get("task_id") or t0.get("id", "")},
                                                   "decision": "accept", "description": "ALICE KNIT 14"})
    step("gudang: baris SJ (40 kg / 2 roll)", c, {k: g.get(k) for k in ("status", "version")} if isinstance(g, dict) and "status" in g else g, (200, 400, 409, 422))
    v = g.get("version", v) if isinstance(g, dict) else v
    c, g = whadm.post(f"/goods-receipts/{G}/start-count", {"expected_version": v})
    step("mulai hitung", c, {k: g.get(k) for k in ("status", "version")} if isinstance(g, dict) and "status" in g else g, (200, 400, 403, 409, 422))
    v = g.get("version", v) if isinstance(g, dict) else v
    for w in (19.6, 18.9):
        c, g = wh.post(f"/goods-receipts/{G}/lines/1/rolls", {"weight_kg": w, "grade": "A", "lot": "UAT-LOT-1"})
        step(f"hitung roll aktual {w} kg", c, {k: g.get(k) for k in ("status", "version")} if isinstance(g, dict) and "status" in g else g, (200, 400, 403, 409, 422))
    c, g = wh.get(f"/goods-receipts/{G}"); v = g.get("version", v)
    c, g = whadm.post(f"/goods-receipts/{G}/finish-count", {"expected_version": v})
    step("selesai hitung -> rekonsiliasi", c, {"status": g.get("status"), "disc": [(d.get("key"), d.get("kind")) for d in g.get("discrepancies", [])]} if isinstance(g, dict) and "status" in g else g, (200, 400, 403, 409, 422))
    if isinstance(g, dict):
        v = g.get("version", v)
        for d in g.get("discrepancies", []) or []:
            if d.get("status") in (None, "open"):
                c, g2 = whadm.post(f"/goods-receipts/{G}/discrepancies/{d['key']}/resolve", {"expected_version": v, "action": "accept_note", "reason": "UAT selisih timbang 1,5 kg diterima"})
                step(f"selesaikan selisih {d.get('kind')}", c, {"status": g2.get("status")} if isinstance(g2, dict) and "status" in g2 else g2, (200, 400, 403, 409))
                if isinstance(g2, dict) and g2.get("version"):
                    v = g2["version"]
        c, g = wh.get(f"/goods-receipts/{G}"); v = g.get("version", v)
        c, g = whadm.post(f"/goods-receipts/{G}/close", {"expected_version": v})
        step("tutup penerimaan (posting stok)", c, {"status": g.get("status")} if isinstance(g, dict) and "status" in g else g, (200, 400, 403, 409, 422))
c, q = qc.get("/inbound/qc/queue")
ql = [t for t in (q if isinstance(q, list) else []) if t.get("po_id") == PO]
step("QC: antrean karantina kedatangan", c, [(t["id"], t.get("quarantine_qty")) for t in ql])
for t in ql:
    c, b = qc.post(f"/inbound/tasks/{t['id']}/qc-decision", {"accept_qty": t.get("quarantine_qty") or 38.5, "reject_qty": 0, "reason": "UAT lulus", "accept_grade": "A"})
    step("QC: lepas karantina", c, short(b, 300), (200, 400, 422))
c, so = sadm.get(f"/sales-orders/{SO}")
print("SO backorder setelah barang masuk:", so.get("status"), so.get("stage"), so.get("sub_status"), [(x.get("backorder_qty"), x.get("status")) for x in so.get("backorders", [])])
dump("/tmp/uat_proc.json")
