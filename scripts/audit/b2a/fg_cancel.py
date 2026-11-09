"""Alur G — batal di tengah & cabang lain (Kanda, legacy):
G1 pindai label 2 roll (roll `receiving` lahir) → batalkan PO → roll yatim?
G2 terima sebagian lewat eskalasi; pindai lagi saat masih eskalasi
G3 SPK 'tolak' + retur ke supplier → nota retur, status roll, PO received_qty, sisa tugas
G4 GRN (KSC, mode grn): hitung 1 roll lalu batalkan GRN → roll & tugas kembali?"""
import kn

ENT, W, PID, SUP = "ent_kanda", "warehouse.soreang", "prod_97ef39b63081", "sup_a47057e2dfc2"
SRG = "site_fd9f6aa41d36"
sit = kn.db.supplier_items.find_one({"product_id": PID}, {"_id": 0})


def new_po(qty, rolls, note, ent=ENT, site=SRG):
    c, po = kn.call("admin", "POST", "/purchase-orders", {"supplier_id": SUP, "ship_to_site_id": site,
                    "items": [{"product_id": PID, "quantity": qty, "unit": "yard", "price": 21000, "expected_grade": "A", "qty_rolls": rolls}],
                    "notes": note}, entity=ent, quiet=True)
    return po, kn.db.wms_tasks.find_one({"po_id": po["id"]}, {"_id": 0})


# G1
po, t = new_po(100, 2, "B2A G1")
for n in ("SR-G1-01", "SR-G1-02"):
    c, o = kn.call(W, "POST", f"/inbound/tasks/{t['id']}/scan-label", {"manual": {"supplier_item_id": sit["id"], "supplier_roll_no": n,
                   "declared_length": 50, "length_unit": "yard", "reason": "label_unreadable"}}, entity=ENT, quiet=True)
    print("G1 scan-label", n, c, str(o)[:160] if c != 200 else (o["roll"].get("roll_no"), o["roll"].get("status")))
c, o = kn.call("admin", "POST", f"/purchase-orders/{po['id']}/cancel", {}, entity=ENT, quiet=True)
print("G1 cancel PO", c, (o or {}).get("status") if isinstance(o, dict) else o)
print("G1 task", kn.db.wms_tasks.find_one({"id": t["id"]}, {"_id": 0, "status": 1}),
      "rolls", kn.snap("inventory_rolls", {"grn_task_id": t["id"]}, ["roll_no", "status", "length_remaining", "warehouse_id"]))
print("G1 balance on_hand/receiving?", kn.snap("inventory_balances", {"product_id": PID, "warehouse_id": t["warehouse_id"], "owner_entity_id": ENT}, ["on_hand_qty", "available_qty", "roll_count"]))
# G2
po, t = new_po(100, 2, "B2A G2")
kn.call(W, "POST", f"/inbound/tasks/{t['id']}/scan-receive", {"product_id": PID, "actual_qty": 60}, entity=ENT, quiet=True)
c, o = kn.call(W, "POST", f"/inbound/tasks/{t['id']}/complete", {}, entity=ENT, quiet=True)
print("G2 complete saat 60/100:", c, str(o)[:150])
c, o = kn.call(W, "POST", f"/inbound/tasks/{t['id']}/escalate", params={"reason": "Kiriman hanya 60 yard"}, entity=ENT, quiet=True)
print("G2 escalate", c, (o or {}).get("status") if isinstance(o, dict) else o)
c, o = kn.call(W, "POST", f"/inbound/tasks/{t['id']}/scan-receive", {"product_id": PID, "actual_qty": 40}, entity=ENT, quiet=True)
print("G2 scan-receive saat ESKALASI:", c, (o or {}).get("status") if isinstance(o, dict) else o, (o or {}).get("received_qty") if isinstance(o, dict) else "")
tt = kn.db.wms_tasks.find_one({"id": t["id"]}, {"_id": 0, "status": 1, "received_qty": 1, "escalation": 1})
print("G2 task", tt["status"], tt["received_qty"], (tt.get("escalation") or {}).get("status"))
# G3 tolak + retur supplier
po, t = new_po(50, 1, "B2A G3")
kn.call(W, "POST", f"/inbound/tasks/{t['id']}/scan-receive", {"product_id": PID, "actual_qty": 50}, entity=ENT, quiet=True)
kn.call(W, "POST", f"/inbound/tasks/{t['id']}/complete", {}, entity=ENT, quiet=True)
spk = kn.db.inspections.find_one({"task_id": t["id"]}, {"_id": 0})
mdq = kn.db.users.find_one({"email": "mdquality@kainnusantara.id"}, {"_id": 0, "id": 1})
kn.call("wh.admin", "POST", f"/inspections/{spk['id']}/assign", {"assigned_to": mdq["id"]}, entity=ENT, quiet=True)
for ln in spk["lines"]:
    kn.call("mdquality", "POST", f"/inspections/{spk['id']}/lines/{ln['id']}/inspect", {"part": "md_quality", "color_result": "tolak", "handfeel_result": "sesuai"}, entity=ENT, quiet=True)
print("G3 roll setelah warna tolak (kebijakan tahan):", kn.snap("inventory_rolls", {"po_id": po["id"]}, ["roll_no", "status", "inspection"]))
c, o = kn.call("mdquality", "POST", f"/inspections/{spk['id']}/finish", {"decision": "tolak", "remark": "Warna jauh berbeda dari sample ACC", "reject_disposition": "return"}, entity=ENT, quiet=True)
print("G3 finish tolak/return:", c, str(o)[:300] if c != 200 else o.get("quarantine_result"))
print("G3 rolls", kn.snap("inventory_rolls", {"po_id": po["id"]}, ["roll_no", "status", "returned_ref", "length_remaining"]))
print("G3 PO", kn.db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0, "status": 1, "items.received_qty": 1}))
print("G3 purchase_return", kn.snap("purchase_returns", {"po_id": po["id"]}, ["number", "status", "stock_adjusted", "total", "items"]))
print("G3 tasks", kn.snap("wms_tasks", {"po_id": po["id"]}, ["id", "status", "expected_qty", "remainder_of"]))
print("G3 JE", kn.snap("journal_entries", {"$or": [{"source_id": t["id"]}, {"source_id": {"$in": [x.get("id") for x in kn.snap("purchase_returns", {"po_id": po["id"]}, ["id"])]}}]}, ["source_type", "total_debit", "status"]))
# G4 GRN batal
po4, t4 = new_po(80, 1, "B2A G4", ent="ent_ksc", site="site_c0c8400b0017")
c, g = kn.call("wh.admin", "POST", "/goods-receipts", {"partner_type": "supplier", "partner_id": SUP, "po_ids": [po4["id"]]}, entity="ent_ksc", quiet=True)
G = g["id"]
v = lambda: kn.db.goods_receipts.find_one({"id": G})["version"]  # noqa: E731
kn.call("wh.admin", "POST", f"/goods-receipts/{G}/manual-entry", {"expected_version": v()}, entity="ent_ksc", quiet=True)
kn.call("wh.admin", "PATCH", f"/goods-receipts/{G}/dn", {"expected_version": v(), "number": "SJ-B2A-G4", "date": "2026-11-09"}, entity="ent_ksc", quiet=True)
kn.call("wh.admin", "POST", f"/goods-receipts/{G}/lines", {"expected_version": v(), "declared": {"qty": 80, "unit": "yard", "rolls": 1},
        "target": {"type": "po_task", "task_id": t4["id"]}, "decision": "accept"}, entity="ent_ksc", quiet=True)
kn.call("wh.admin", "PATCH", f"/goods-receipts/{G}/lines/1", {"expected_version": v(), "verified": True}, entity="ent_ksc", quiet=True)
kn.call("wh.admin", "POST", f"/goods-receipts/{G}/start-count", {"expected_version": v()}, entity="ent_ksc", quiet=True)
c, o = kn.call("warehouse.rancamalang", "POST", f"/goods-receipts/{G}/lines/1/rolls", {"length": 80, "length_unit": "yard", "grade": "A"}, entity="ent_ksc", quiet=True)
print("G4 count roll", c)
c, o = kn.call("admin", "POST", f"/purchase-orders/{po4['id']}/cancel", {}, entity="ent_ksc", quiet=True)
print("G4 cancel PO saat dihitung:", c, str(o)[:150])
c, o = kn.call("wh.admin", "POST", f"/goods-receipts/{G}/cancel", {"reason": "SJ salah kirim, barang dikembalikan"}, entity="ent_ksc", quiet=True)
print("G4 cancel GRN", c, (o or {}).get("status") if isinstance(o, dict) else o)
print("G4 rolls", kn.snap("inventory_rolls", {"grn_id": G}, ["roll_no", "status"]), "task", kn.db.wms_tasks.find_one({"id": t4["id"]}, {"_id": 0, "status": 1, "grn_active_id": 1, "received_qty": 1}))
