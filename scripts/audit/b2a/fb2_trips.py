"""Alur B2 — sisa PO-00172 (99 yd) lewat GRN kedua: 2 roll → SPK terima → draf → label → terbit (tanpa kirim) → trip 1
(1 roll) → tiba sebagian → tutup sisa 'return_transit' → status akhir; ulang trip yang sama (idempoten)."""
import json
import kn

ENT, SUP, REV, W = "ent_ksc", "sup_a47057e2dfc2", "wh.admin", "warehouse.rancamalang"
ids = json.load(open("/tmp/b2a/fb_ids.json"))
rem = kn.db.wms_tasks.find_one({"remainder_of": ids["TID"]}, {"_id": 0})
print("remainder task", rem["id"], rem["status"], rem["expected_qty"])
c, g = kn.call(REV, "POST", "/goods-receipts", {"partner_type": "supplier", "partner_id": SUP, "po_ids": [ids["PO"]]}, entity=ENT, quiet=True)
G = g["id"]
v = lambda: kn.db.goods_receipts.find_one({"id": G})["version"]  # noqa: E731
kn.call(REV, "POST", f"/goods-receipts/{G}/manual-entry", {"expected_version": v()}, entity=ENT, quiet=True)
c, o = kn.call(REV, "PATCH", f"/goods-receipts/{G}/dn", {"expected_version": v(), "number": "SJ-B2A-001", "date": "2026-11-09"}, entity=ENT, quiet=True)
c, o = kn.call(REV, "POST", f"/goods-receipts/{G}/lines", {"expected_version": v(), "declared": {"qty": 99, "unit": "yard", "rolls": 2},
               "target": {"type": "po_task", "task_id": rem["id"]}, "decision": "accept"}, entity=ENT, quiet=True)
kn.call(REV, "PATCH", f"/goods-receipts/{G}/lines/1", {"expected_version": v(), "verified": True}, entity=ENT, quiet=True)
c, o = kn.call(REV, "POST", f"/goods-receipts/{G}/start-count", {"expected_version": v()}, entity=ENT, quiet=True)
print("start-count SJ sama nomornya (SJ-B2A-001) di GRN kedua:", c, str(o)[:200])
if c != 200:
    kn.call(REV, "PATCH", f"/goods-receipts/{G}/dn", {"expected_version": v(), "number": "SJ-B2A-002"}, entity=ENT, quiet=True)
    c, o = kn.call(REV, "POST", f"/goods-receipts/{G}/start-count", {"expected_version": v()}, entity=ENT, quiet=True)
    print("start-count SJ-B2A-002:", c)
for L in (50, 49):
    kn.call(W, "POST", f"/goods-receipts/{G}/lines/1/rolls", {"length": L, "length_unit": "yard", "grade": "A"}, entity=ENT, quiet=True)
kn.call(W, "POST", f"/goods-receipts/{G}/finish-count", {"expected_version": v()}, entity=ENT, quiet=True)
c, o = kn.call(REV, "POST", f"/goods-receipts/{G}/close", {"expected_version": v()}, entity=ENT, quiet=True)
print("close", c, kn.db.goods_receipts.find_one({"id": G}, {"_id": 0, "status": 1}))
print("PO", kn.db.purchase_orders.find_one({"id": ids["PO"]}, {"_id": 0, "status": 1, "items.received_qty": 1, "items.received_rolls": 1}))
spk = kn.db.inspections.find_one({"task_id": rem["id"]}, {"_id": 0})
mdq = kn.db.users.find_one({"email": "mdquality@kainnusantara.id"}, {"_id": 0, "id": 1})
kn.call(REV, "POST", f"/inspections/{spk['id']}/assign", {"assigned_to": mdq["id"]}, entity=ENT, quiet=True)
for ln in spk["lines"]:
    kn.call("mdquality", "POST", f"/inspections/{spk['id']}/lines/{ln['id']}/inspect", {"part": "md_quality", "color_result": "sesuai", "handfeel_result": "sesuai"}, entity=ENT, quiet=True)
c, o = kn.call("mdquality", "POST", f"/inspections/{spk['id']}/finish", {"decision": "terima", "remark": "ok"}, entity=ENT, quiet=True)
rolls = kn.snap("inventory_rolls", {"grn_id": G}, ["id", "roll_no", "status"])
print("rolls", rolls)
pa = kn.db.putaway_orders.find_one({"items.roll_id": rolls[0]["id"], "status": "draft"}, {"_id": 0})
print("draft", pa["pa_number"], pa["to_warehouse_name"])
kn.call(W, "PATCH", f"/putaway-orders/{pa['id']}/draft", {"to_warehouse_id": "wh_adc8726d019e"}, entity=ENT, quiet=True)
kn.call(W, "POST", "/putaway-orders/verify-labels", {"warehouse_id": "wh_5ae35dcd8837", "codes": [r["roll_no"] for r in rolls]}, entity=ENT, quiet=True)
c, o = kn.call(W, "POST", f"/putaway-orders/{pa['id']}/publish", {}, entity=ENT, quiet=True)
print("publish", c, (o or {}).get("status"))
c, o = kn.call(W, "POST", f"/putaway-orders/{pa['id']}/arrival-trips", {"epcs": [rolls[0]["roll_no"], "KODE-ASING-X"], "client_trip_id": "b2a-pa-t1"}, entity=ENT, quiet=True)
print("trip1 (tanpa kirim/dispatch)", c, (o or {}).get("status"), (o or {}).get("trip", {}).get("arrived_roll_nos"), (o or {}).get("trip", {}).get("unknown_epcs"), "dispatched_at", (o or {}).get("dispatched_at"))
c, o = kn.call(W, "POST", f"/putaway-orders/{pa['id']}/arrival-trips", {"epcs": [rolls[0]["roll_no"]], "client_trip_id": "b2a-pa-t1"}, entity=ENT, quiet=True)
print("trip1 ulang", c, (o or {}).get("duplicate_trip"), (o or {}).get("status"))
print("roll2 setelah trip1:", kn.snap("inventory_rolls", {"id": rolls[1]["id"]}, ["status", "warehouse_id", "journey", "active_movement"]))
print("bal transit/woven:", kn.snap("inventory_balances", {"product_id": "prod_97ef39b63081", "owner_entity_id": ENT, "warehouse_id": {"$in": ["wh_5ae35dcd8837", "wh_adc8726d019e"]}}, ["warehouse_id", "available_qty", "in_transit_qty", "on_hand_qty"]))
c, o = kn.call(W, "POST", f"/putaway-orders/{pa['id']}/close", {"action": "return_transit", "reason": "roll kedua tertinggal di transit"}, entity=ENT, quiet=True)
print("close return_transit", c, (o or {}).get("status"), (o or {}).get("btg_number"), [(i["roll_no"], i["status"]) for i in (o or {}).get("items", [])])
print("roll2 setelah close:", kn.snap("inventory_rolls", {"id": rolls[1]["id"]}, ["status", "warehouse_id", "journey", "active_movement"]))
c, o = kn.call(W, "POST", "/putaway-orders/auto-draft", {"from_warehouse_id": "wh_5ae35dcd8837"}, entity=ENT, quiet=True)
print("siapkan draf ulang:", c, o.get("drafts") if isinstance(o, dict) else o)
