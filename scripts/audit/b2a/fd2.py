"""Alur D2 — konfigurasi RCM-RETUR = inspeksi (seperti skrip PREP-C), batalkan draf salah tujuan, siapkan draf ulang
(pemicu manual) → roll yang diminta inspeksi ke gedung inspeksi? Tutup QC 4-point (1 roll tolak) → tahan."""
import json
import kn

ids = json.load(open("/tmp/b2a/fd_ids.json"))
R1, R2, Q4, ENT = ids["R1"], ids["R2"], ids["Q4"], "ent_ksc"
W = "warehouse.rancamalang"
c, o = (0, 0)  # kn.call("admin", "PATCH", "/warehouses/wh_6cccc13554f8", {"data": {"roles": ["inspection", "return", "storage"]}}, quiet=True)
print("patch roles", c, (o or {}).get("roles") if isinstance(o, dict) else o)

print("cancel draft", c, (o or {}).get("status") if isinstance(o, dict) else o)

for p in kn.snap("putaway_orders", {"items.roll_id": {"$in": [R1, R2]}, "status": "draft"}, ["pa_number", "status", "to_warehouse_name", "purpose", "items"]):
    print("DRAFT", p["pa_number"], p["to_warehouse_name"], p["purpose"], [(i["roll_no"], i.get("inspection_requested")) for i in p["items"]])
# Tutup QC 4-point: baris R2 tolak
q = kn.db.inspections.find_one({"id": Q4}, {"_id": 0})
for ln in q["lines"]:
    c, o = kn.call("qc", "POST", f"/inspections/{Q4}/lines/{ln['id']}/inspect",
                   {"part": "qc", "defects": [{"code": "BL", "point_value": 4, "count": 3, "interval": 2}], "inspect_length_yard": 101,
                    "grade": "B", "decision": "tolak", "remark": "Belang di tengah"}, entity=ENT)
c, o = kn.call("qc", "POST", f"/inspections/{Q4}/finish", {"decision": "terima_sebagian", "remark": "sebagian roll gagal"}, entity=ENT, quiet=True)
print("finish qc4", c, str(o)[:300] if c != 200 else (o.get("status"), o.get("putaway_draft")))
c, o = kn.call("qc", "POST", f"/inspections/{Q4}/finish", {"decision": "tolak", "remark": "Roll belang di tengah, tidak lolos 4-point"}, entity=ENT, quiet=True)
print("finish qc4 tolak", c, str(o)[:300] if c != 200 else (o.get("status"), o.get("putaway_draft")))
print("R2:", kn.snap("inventory_rolls", {"id": R2}, ["roll_no", "status", "hold", "journey", "grade", "active_movement"]))
for p in kn.snap("putaway_orders", {"items.roll_id": {"$in": [R1, R2]}}, ["pa_number", "status", "to_warehouse_name", "purpose", "items"]):
    print("PA", p["pa_number"], p["status"], p["to_warehouse_name"], p["purpose"], [(i["roll_no"], i.get("inspection_requested")) for i in p["items"]])
