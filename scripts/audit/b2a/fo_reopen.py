"""Alur O — tugas masuk yang sudah diputus QC (qc_rejected) / sedang QC (qc_pending) masih tampil di HP sebagai
tugas terbuka: bisakah 'Terima' + 'Selesai' dijalankan lagi → roll & GR ganda?"""
import kn

ENT, W, PID = "ent_kanda", "warehouse.soreang", "prod_97ef39b63081"
t = kn.db.wms_tasks.find_one({"entity_id": ENT, "status": "qc_rejected", "po_id": {"$exists": True}}, {"_id": 0}, sort=[("updated_at", -1)])
print("task", t["id"], t["status"], t["received_qty"], t["expected_qty"], "PO", t["po_number"])
c, rows = kn.call(W, "GET", "/wms/tasks", entity=ENT, quiet=True)
mob = [x for x in rows if (x.get("flow_type") == "inbound") and x["status"] not in ("completed", "shipped", "cancelled", "done", "dispatched")]
print("HP daftar 'Tugas barang masuk' memuat:", sorted({x["status"] for x in mob}), "tugas ini tampil:", t["id"] in [x["id"] for x in mob])
before = kn.counts(["inventory_rolls", "inventory_movements", "journal_entries"])
po0 = kn.db.purchase_orders.find_one({"id": t["po_id"]}, {"_id": 0, "status": 1, "items.received_qty": 1})
c, o = kn.call(W, "POST", f"/inbound/tasks/{t['id']}/scan-receive", {"product_id": PID, "actual_qty": 1}, entity=ENT, quiet=True)
print("scan-receive pada qc_rejected:", c, (o or {}).get("status") if isinstance(o, dict) else o, (o or {}).get("received_qty") if isinstance(o, dict) else "")
c, o = kn.call(W, "POST", f"/inbound/tasks/{t['id']}/complete", {}, entity=ENT, quiet=True)
print("complete lagi:", c, str(o)[:200] if c != 200 else (o.get("status"), o.get("created_rolls")))
print("delta", kn.delta(before, kn.counts(["inventory_rolls", "inventory_movements", "journal_entries"])))
print("PO sebelum", po0, "sesudah", kn.db.purchase_orders.find_one({"id": t["po_id"]}, {"_id": 0, "status": 1, "items.received_qty": 1}))
print("JE GR task", kn.snap("journal_entries", {"source_id": t["id"]}, ["source_type", "total_debit"]))
