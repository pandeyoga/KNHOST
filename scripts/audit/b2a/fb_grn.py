"""Alur B — mode GRN (Kedatangan Barang) KSC → Rancamalang: SJ satuan meter vs PO yard, kiriman parsial 2 dari 3 roll,
foto SJ + baca otomatis (OCR tanpa kunci), isi manual, hitung roll, selisih, tutup → karantina + SPK → sisa PO."""
import io
import json
import kn

ENT = "ent_ksc"
ADM = "admin"
W = "warehouse.rancamalang"
PID = "prod_97ef39b63081"
SUP = "sup_a47057e2dfc2"
out = {}

c, o = kn.call(ADM, "GET", "/goods-receipts/mode", entity=ENT)
c, o = kn.call(ADM, "GET", "/goods-receipts/mode", entity=ENT, quiet=True) if False else (0,0)
#, {"entity_id": ENT, "mode": "grn", "reason": "Audit B2a uji alur GRN"}, entity=ENT)
out["mode_switch"] = (c, o)
c, po = kn.call(ADM, "POST", "/purchase-orders", {
    "supplier_id": SUP, "ship_to_site_id": "site_c0c8400b0017",
    "items": [{"product_id": PID, "quantity": 300, "unit": "yard", "price": 20000, "expected_grade": "A", "qty_rolls": 3}],
    "expected_delivery_date": "2026-11-12", "notes": "B2A alur B GRN"}, entity=ENT, quiet=True)
PO = po["id"]
task = kn.db.wms_tasks.find_one({"po_id": PO}, {"_id": 0})
TID = task["id"]
print("PO", po["po_number"], "task", TID, task["status"], task["warehouse_id"])
# Mode GRN: jalur lama ditolak?
kn.call(W, "POST", f"/inbound/tasks/{TID}/scan-receive", {"product_id": PID, "actual_qty": 10}, entity=ENT)
# 1) buat GRN (petugas gudang)
c, g = kn.call(W, "POST", "/goods-receipts", {"partner_type": "supplier", "partner_id": SUP, "po_ids": [PO]}, entity=ENT, quiet=True)
print("create GRN", c, (g or {}).get("number"), (g or {}).get("status"), (g or {}).get("warehouse_id"))
if c != 200:
    c, g = kn.call("wh.admin", "POST", "/goods-receipts", {"partner_type": "supplier", "partner_id": SUP, "po_ids": [PO]}, entity=ENT)
GID = g["id"]
WHO = W if c == 200 else "wh.admin"
REV = "wh.admin"
v = g["version"]
# 2) foto SJ
from PIL import Image  # noqa: E402
buf = io.BytesIO()
Image.new("RGB", (1200, 900), (250, 250, 250)).save(buf, "PNG")
c, f = kn.call(WHO, "POST", f"/goods-receipts/{GID}/files", {"expected_version": str(v)}, entity=ENT,
               files={"file": ("sj.png", buf.getvalue(), "image/png")}, quiet=True)
print("file", c, str(f)[:200])
v = kn.db.goods_receipts.find_one({"id": GID})["version"]
c, o = kn.call(WHO, "POST", f"/goods-receipts/{GID}/read", {"expected_version": v}, entity=ENT)
g = kn.db.goods_receipts.find_one({"id": GID}, {"_id": 0})
print("after read: status", g["status"], "extraction", g.get("extraction", {}).get("read_failed"), g.get("extraction", {}).get("error_code"))
v = g["version"]
if g["status"] == "draft":
    c, o = kn.call(REV, "POST", f"/goods-receipts/{GID}/manual-entry", {"expected_version": v}, entity=ENT, quiet=True)
    v = kn.db.goods_receipts.find_one({"id": GID})["version"]
c, o = kn.call(REV, "PATCH", f"/goods-receipts/{GID}/dn", {"expected_version": v, "number": "SJ-B2A-001", "date": "2026-11-09"}, entity=ENT, quiet=True)
print("dn", c, str(o)[:150])
v = kn.db.goods_receipts.find_one({"id": GID})["version"]
c, t = kn.call(REV, "GET", f"/goods-receipts/{GID}/targets", entity=ENT, quiet=True)
print("targets", c, [(x.get("type"), x.get("task_id"), x.get("remaining"), x.get("unit")) for x in (t if isinstance(t, list) else [])][:5])
# baris SJ: 182.88 meter (= 200 yard), 2 roll
c, o = kn.call(REV, "POST", f"/goods-receipts/{GID}/lines", {"expected_version": v, "declared": {"qty": 200, "unit": "yard", "rolls": 2},
               "target": {"type": "po_task", "task_id": TID}, "decision": "accept", "item_code": "SUP-UJI-1", "description": "Kain uji"}, entity=ENT, quiet=True)
print("line", c, str(o)[:300])
g = kn.db.goods_receipts.find_one({"id": GID}, {"_id": 0})
ln = g["lines"][0]
print("line converted", ln.get("converted"), "checks", ln.get("checks"), "verified", ln.get("verified"))
v = g["version"]
c, o = kn.call(REV, "PATCH", f"/goods-receipts/{GID}/lines/{ln['line_no']}", {"expected_version": v, "verified": True}, entity=ENT, quiet=True)
print("verify line", c, str(o)[:200])
v = kn.db.goods_receipts.find_one({"id": GID})["version"]
c, o = kn.call(REV, "POST", f"/goods-receipts/{GID}/start-count", {"expected_version": v}, entity=ENT)
# hitung roll: 100 yard + 101 yard
for L in (100, 101):
    c, o = kn.call(WHO, "POST", f"/goods-receipts/{GID}/lines/{ln['line_no']}/rolls", {"length": L, "length_unit": "yard", "lot": "SLOT-B", "grade": "A"}, entity=ENT, quiet=True)
    print("roll", L, c, str(o)[:160])
g = kn.db.goods_receipts.find_one({"id": GID}, {"_id": 0})
print("counted", g["lines"][0].get("counted"), "status", g["status"])
rr = kn.snap("inventory_rolls", {"grn_id": GID}, ["id", "roll_no", "status", "length_initial", "unit", "warehouse_id", "bin_id", "journey", "rfid_tag_id"])
print("rolls receiving:", [(r["roll_no"], r["status"], r["length_initial"], r["unit"], (r.get("journey") or {}).get("stage")) for r in rr])
print("balances (receiving terlihat?)", kn.snap("inventory_balances", {"product_id": PID, "warehouse_id": task["warehouse_id"], "owner_entity_id": ENT}))
c, o = kn.call(WHO, "POST", f"/goods-receipts/{GID}/finish-count", {"expected_version": g["version"]}, entity=ENT, quiet=True)
g = kn.db.goods_receipts.find_one({"id": GID}, {"_id": 0})
print("finish-count", c, "status", g["status"], "disc", [(d["key"], d["blocking"], d["detail"]) for d in g.get("discrepancies") or []])
for d in g.get("discrepancies") or []:
    if d.get("blocking"):
        c, o = kn.call(REV, "POST", f"/goods-receipts/{GID}/discrepancies/{d['key']}/resolve",
                       {"expected_version": kn.db.goods_receipts.find_one({"id": GID})["version"], "action": "accept_note", "reason": "kiriman susulan"}, entity=ENT, quiet=True)
        print("resolve", d["key"], c, str(o)[:200])
before = kn.counts(kn.WATCH)
g = kn.db.goods_receipts.find_one({"id": GID}, {"_id": 0})
c, o = kn.call(REV, "POST", f"/goods-receipts/{GID}/close", {"expected_version": g["version"]}, entity=ENT, quiet=True)
print("close", c, str(o)[:400])
print("delta counts", kn.delta(before, kn.counts(kn.WATCH)))
g = kn.db.goods_receipts.find_one({"id": GID}, {"_id": 0})
print("GRN status", g["status"], "lines.posted", [x.get("posted") for x in g["lines"]])
rr = kn.snap("inventory_rolls", {"grn_id": GID}, ["id", "roll_no", "status", "length_initial", "unit", "warehouse_id", "journey", "qc_task_id", "unit_cost"])
print("rolls after close:", [(r["roll_no"], r["status"], r["length_initial"], (r.get("journey") or {}).get("stage"), r.get("unit_cost")) for r in rr])
print("tasks for PO:", kn.snap("wms_tasks", {"po_id": PO}, ["id", "status", "expected_qty", "received_qty", "remainder_of", "qty_rolls"]))
print("PO:", kn.db.purchase_orders.find_one({"id": PO}, {"_id": 0, "status": 1, "items.received_qty": 1, "items.received_rolls": 1}))
print("JE:", kn.snap("journal_entries", {"source_id": TID}, ["source_type", "status", "total_debit"]))
print("SPK:", kn.snap("inspections", {"task_id": TID}, ["number", "kind", "status", "md_only"]))
json.dump({"PO": PO, "TID": TID, "GID": GID}, open("/tmp/b2a/fb_ids.json", "w"))
