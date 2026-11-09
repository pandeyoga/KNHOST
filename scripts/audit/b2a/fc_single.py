"""Alur C — gedung tunggal Soreang (SRG-01): PO Kanda (legacy) multi-roll lewat payload rolls + PO KSC ke Soreang
(gedung dipakai bersama, K-GDG-07) → apakah petugas Soreang bisa melihat/mengerjakan?"""
import kn

W = "warehouse.soreang"
PID = "prod_97ef39b63081"
SUP = "sup_a47057e2dfc2"
SRG = "site_fd9f6aa41d36"
c, po = kn.call("admin", "POST", "/purchase-orders", {
    "supplier_id": SUP, "ship_to_site_id": SRG,
    "items": [{"product_id": PID, "quantity": 150, "unit": "yard", "price": 21000, "expected_grade": "A", "qty_rolls": 3}],
    "notes": "B2A alur C Kanda"}, entity="ent_kanda", quiet=True)
PO = po["id"]
t = kn.db.wms_tasks.find_one({"po_id": PO}, {"_id": 0})
TID = t["id"]
print("PO Kanda", po["po_number"], "gudang", po["warehouse_id"], po.get("warehouse_name"), "task", TID)
c, o = kn.call(W, "POST", f"/inbound/tasks/{TID}/scan-receive", {"product_id": PID, "actual_qty": 150, "bin_id": "TIDAK-ADA-BIN"}, quiet=True)
print("scan-receive", c, (o or {}).get("status") if isinstance(o, dict) else o)
c, o = kn.call(W, "POST", f"/inbound/tasks/{TID}/complete", {"supplier_lot": "SL-C", "dye_lot": "DY-C",
               "rolls": [{"length": 50, "grade": "A"}, {"length": 50, "grade": "A"}, {"length": 50, "grade": "B"}]}, quiet=True)
print("complete", c, str(o)[:200] if c != 200 else (o.get("status"), o.get("created_rolls")))
rr = kn.snap("inventory_rolls", {"po_id": PO}, ["id", "roll_no", "status", "bin_id", "journey", "grade", "rfid_tag_id", "warehouse_id"])
print("rolls", [(r["roll_no"], r["status"], r.get("bin_id"), (r.get("journey") or {}).get("stage"), r["grade"], r.get("rfid_tag_id")) for r in rr])
spk = kn.db.inspections.find_one({"task_id": TID}, {"_id": 0})
mdq = kn.db.users.find_one({"email": "mdquality@kainnusantara.id"}, {"_id": 0, "id": 1})
kn.call("wh.admin", "POST", f"/inspections/{spk['id']}/assign", {"assigned_to": mdq["id"]}, entity="ent_kanda", quiet=True)
for ln in spk["lines"]:
    kn.call("mdquality", "POST", f"/inspections/{spk['id']}/lines/{ln['id']}/inspect", {"part": "md_quality", "color_result": "sesuai", "handfeel_result": "sesuai"}, entity="ent_kanda", quiet=True)
c, o = kn.call("mdquality", "POST", f"/inspections/{spk['id']}/finish", {"decision": "terima", "remark": "ok"}, entity="ent_kanda", quiet=True)
print("finish", c, str(o)[:200] if c != 200 else o.get("quarantine_result"), (o or {}).get("putaway_draft") if isinstance(o, dict) else "")
rr = kn.snap("inventory_rolls", {"po_id": PO}, ["id", "roll_no", "status", "bin_id", "journey", "grade"])
print("rolls after QC", [(r["roll_no"], r["status"], r.get("bin_id"), (r.get("journey") or {}).get("stage"), r["grade"]) for r in rr])
print("PA drafts", kn.snap("putaway_orders", {"items.roll_id": {"$in": [r["id"] for r in rr]}}, ["pa_number", "status"]))
# PO KSC ke Soreang
c, po2 = kn.call("admin", "POST", "/purchase-orders", {
    "supplier_id": SUP, "ship_to_site_id": SRG,
    "items": [{"product_id": PID, "quantity": 50, "unit": "yard", "price": 21000, "expected_grade": "A", "qty_rolls": 1}],
    "notes": "B2A alur C KSC ke Soreang"}, entity="ent_ksc", quiet=True)
t2 = kn.db.wms_tasks.find_one({"po_id": po2["id"]}, {"_id": 0})
print("PO KSC→Soreang", po2["po_number"], po2["warehouse_id"], "task", t2["id"], t2["status"])
for who, ent in [(W, None), (W, "all"), (W, "ent_ksc")]:
    c, rows = kn.call(who, "GET", "/wms/tasks", entity=ent, quiet=True)
    print(f"  {who} X-Entity={ent}: {c} lihat_tugas_KSC={isinstance(rows, list) and t2['id'] in [x['id'] for x in rows]} {'' if isinstance(rows, list) else rows}")
c, o = kn.call(W, "POST", "/goods-receipts", {"partner_type": "supplier", "partner_id": SUP, "po_ids": [po2["id"]]}, entity="ent_ksc")
c, o = kn.call(W, "POST", "/goods-receipts", {"partner_type": "supplier", "partner_id": SUP, "po_ids": [po2["id"]]})
