PO_NO = "KSC/PO-00028"; SO = "so_485cecbd17f4"
mgr = Api("manager@kainnusantara.id"); wh = Api("warehouse@kainnusantara.id"); whadm = Api("wh.admin@kainnusantara.id"); qc = Api("qc@kainnusantara.id"); sadm = Api("salesadmin@kainnusantara.id"); mdq = Api("mdquality@kainnusantara.id")
c, gl = whadm.get("/goods-receipts")
gl = gl if isinstance(gl, list) else gl.get("items", [])
g = next(x for x in gl if x.get("number") == "KSC/GRN-00001")
G = g["id"]; c, g = whadm.get(f"/goods-receipts/{G}"); v = g["version"]
PO = (g.get("po_ids") or [None])[0]
print("GRN", g["number"], g["status"], v, "po", PO)
c, g2 = whadm._do("PATCH", f"/goods-receipts/{G}/dn", json={"expected_version": v, "number": "SJ-SUP-UAT-01", "date": "2026-10-21"})
step("admin gudang: kepala SJ", c, {k: g2.get(k) for k in ("status", "version")} if isinstance(g2, dict) and "status" in g2 else g2)
v = g2.get("version", v)
c, tg = whadm.get(f"/goods-receipts/{G}/targets"); print("targets:", short(tg, 600))
tgl = tg if isinstance(tg, list) else (tg.get("items") or tg.get("targets") or tg.get("po_tasks") or [])
t0 = tgl[0] if tgl else {}
tid = t0.get("task_id") or t0.get("id") or ""
c, g2 = whadm.post(f"/goods-receipts/{G}/lines", {"expected_version": v, "declared": {"qty": 40, "unit": "kg", "rolls": 2},
                   "target": {"type": "po_task", "task_id": tid}, "decision": "accept", "description": "ALICE KNIT 14"})
step("admin gudang: baris SJ 40 kg / 2 roll", c, {k: g2.get(k) for k in ("status", "version")} if isinstance(g2, dict) and "status" in g2 else g2)
v = g2.get("version", v) if isinstance(g2, dict) else v
c, g2 = whadm.post(f"/goods-receipts/{G}/start-count", {"expected_version": v})
step("mulai hitung", c, {k: g2.get(k) for k in ("status", "version")} if isinstance(g2, dict) and "status" in g2 else g2)
for w in (19.6, 18.9):
    c, g2 = wh.post(f"/goods-receipts/{G}/lines/1/rolls", {"weight_kg": w, "grade": "A", "lot": "UAT-LOT-1"})
    step(f"gudang: timbang roll aktual {w} kg", c, {k: g2.get(k) for k in ("status", "version")} if isinstance(g2, dict) and "status" in g2 else g2)
c, g2 = whadm.get(f"/goods-receipts/{G}"); v = g2["version"]
c, g2 = wh.post(f"/goods-receipts/{G}/finish-count", {"expected_version": v})
step("gudang: selesai hitung", c, {"status": g2.get("status"), "disc": [(d.get("key"), d.get("kind"), d.get("status")) for d in g2.get("discrepancies", [])]} if isinstance(g2, dict) and "status" in g2 else g2)
c, g2 = whadm.get(f"/goods-receipts/{G}"); v = g2["version"]
print("rekonsiliasi:", short(g2.get("reconcile") or g2.get("recon") or g2.get("discrepancies"), 800))
for d in g2.get("discrepancies", []) or []:
    if d.get("status") in (None, "open"):
        c, g3 = whadm.post(f"/goods-receipts/{G}/discrepancies/{d['key']}/resolve", {"expected_version": v, "action": "accept_note", "reason": "UAT selisih timbang diterima"})
        step(f"admin gudang: selesaikan selisih {d.get('kind')}", c, {"status": g3.get("status")} if isinstance(g3, dict) and "status" in g3 else g3)
        if isinstance(g3, dict) and g3.get("version"): v = g3["version"]
c, g2 = whadm.get(f"/goods-receipts/{G}"); v = g2["version"]
c, g2 = whadm.post(f"/goods-receipts/{G}/close", {"expected_version": v})
step("admin gudang: tutup penerimaan", c, {"status": g2.get("status")} if isinstance(g2, dict) and "status" in g2 else g2)
c, pod = mgr.get(f"/purchase-orders/{PO}")
print("PO setelah terima:", pod.get("status"), [(i.get("quantity"), i.get("received_qty")) for i in pod.get("items", [])])
c, q = qc.get("/inbound/qc/queue")
ql = [t for t in (q if isinstance(q, list) else []) if t.get("po_id") == PO]
step("QC: antrean karantina", c, [(t["id"], t.get("quarantine_qty"), t.get("status")) for t in ql])
c, ins = mdq.get("/inspections", params={"source": "receiving"})
print("MDQ inspeksi:", c, short(ins, 300))
for t in ql:
    c, b = qc.post(f"/inbound/tasks/{t['id']}/qc-decision", {"accept_qty": t.get("quarantine_qty"), "reject_qty": 0, "reason": "UAT lulus", "accept_grade": "A"})
    step("QC: lepas karantina", c, short(b, 300))
c, so = sadm.get(f"/sales-orders/{SO}")
print("SO backorder setelah barang masuk:", so.get("status"), so.get("stage"), so.get("sub_status"), [(x.get("backorder_qty"), x.get("reserved_qty"), x.get("status")) for x in so.get("backorders", [])])
c, it = sadm.get(f"/sales-orders/{SO}/restock-state"); print("restock-state:", short(it, 500))
dump("/tmp/uat_grn.json")
