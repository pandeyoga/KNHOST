"""Alur D — GRN-00028 (2 roll karantina): tahan 1 roll → tutup SPK 'terima' (B1: harus PERINGATAN) → buat SPK QC 4-point
untuk 1 roll → konfigurasi RCM-RETUR jadi gedung inspeksi → putus SPK → draf PA ke gedung inspeksi?"""
import json
import kn

ids = json.load(open("/tmp/b2a/fb_ids.json"))
TID, ENT = ids["TID"], "ent_ksc"
rolls = kn.snap("inventory_rolls", {"qc_task_id": TID}, ["id", "roll_no", "status"])
print("rolls", rolls)
R1, R2 = rolls[0]["id"], rolls[1]["id"]
spk = kn.db.inspections.find_one({"task_id": TID, "kind": "po_receipt"}, {"_id": 0})
SID = spk["id"]
mdq = kn.db.users.find_one({"email": "mdquality@kainnusantara.id"}, {"_id": 0, "id": 1})
qc = kn.db.users.find_one({"email": "qc@kainnusantara.id"}, {"_id": 0, "id": 1})
kn.call("wh.admin", "POST", f"/inspections/{SID}/assign", {"assigned_to": mdq["id"]}, entity=ENT, quiet=True)
for ln in spk["lines"]:
    kn.call("mdquality", "POST", f"/inspections/{SID}/lines/{ln['id']}/inspect",
            {"part": "md_quality", "color_result": "sesuai", "handfeel_result": "sesuai"}, entity=ENT, quiet=True)
# 1) Tahan roll 1 (alasan) — oleh petugas gudang
c, o = kn.call("warehouse.rancamalang", "POST", f"/inventory/rolls/{R1}/hold", {"reason": "Ada noda di ujung roll"}, entity=ENT)
print("after hold:", kn.snap("inventory_rolls", {"id": R1}, ["status", "hold", "qc_task_id"]))
print("qc queue quarantine qty:", [(t["id"], t.get("quarantine_qty")) for t in kn.call("wh.admin", "GET", "/inbound/qc/queue", entity=ENT, quiet=True)[1] if t["id"] == TID])
# 2) Tutup SPK 'terima' — B1 bawaan peringatkan
c, o = kn.call("mdquality", "POST", f"/inspections/{SID}/finish", {"decision": "terima", "remark": "sesuai sample"}, entity=ENT)
print("SPK status:", kn.db.inspections.find_one({"id": SID}, {"_id": 0, "status": 1, "decision": 1, "accepted_with_held_rolls": 1}))
# 3) Jalur antrean karantina (qc-decision) — ditolak karena SPK terbuka
c, o = kn.call("wh.admin", "POST", f"/inbound/tasks/{TID}/qc-decision", {"accept_qty": 101, "reject_qty": 0, "accept_grade": "A"}, entity=ENT)
# 4) 'terima_sebagian' dgn roll ditahan dianggap tolak?
c, o = kn.call("mdquality", "POST", f"/inspections/{SID}/finish", {"decision": "terima_sebagian", "remark": "roll noda ditolak",
               "rejected_roll_ids": [R1], "reject_disposition": "damaged"}, entity=ENT)
# 5) SPK QC 4-point untuk roll 2 (masih karantina)
c, q4 = kn.call("qc", "POST", "/inspections/qc-4point", {"inspection_id": SID, "roll_ids": [R2], "assigned_to": qc["id"]}, entity=ENT, quiet=True)
print("qc4", c, (q4 or {}).get("number"), (q4 or {}).get("status"))
# 6) Konfigurasi RCM-RETUR sebagai gedung inspeksi (seperti skrip nilai awal PREP-C)
c, o = kn.call("admin", "PATCH", "/warehouses/wh_6cccc13554f8", {"roles": ["inspection", "return", "storage"]}, quiet=True)
print("patch RCM-RETUR roles:", c, str(o)[:200])
# 7) Lepas tahanan roll 1 (manajer) lalu tutup SPK 'terima'
c, o = kn.call("manager", "POST", f"/inventory/rolls/{R1}/release", {"note": "Noda hanya di ujung, sudah dipotong"}, entity=ENT)
c, o = kn.call("mdquality", "POST", f"/inspections/{SID}/finish", {"decision": "terima", "remark": "sesuai sample"}, entity=ENT, quiet=True)
print("finish terima:", c, str(o.get("putaway_draft") if isinstance(o, dict) else o)[:300], "accepted_with_held", (o or {}).get("accepted_with_held_rolls") if isinstance(o, dict) else "")
rr = kn.snap("inventory_rolls", {"qc_task_id": None, "id": {"$in": [R1, R2]}}, ["roll_no", "status", "journey", "hold", "qc_hold_pending"])
print("rolls:", [(r["roll_no"], r["status"], (r.get("journey") or {}).get("stage")) for r in rr])
pas = kn.snap("putaway_orders", {"items.roll_id": {"$in": [R1, R2]}}, ["pa_number", "status", "to_warehouse_name", "purpose", "item_count", "items", "auto"])
for p in pas:
    print("PA", p["pa_number"], p["status"], p["to_warehouse_name"], p["purpose"], [(i["roll_no"], i.get("inspection_requested")) for i in p["items"]], p.get("auto", {}).get("trigger"))
json.dump({"R1": R1, "R2": R2, "Q4": (q4 or {}).get("id"), "SID": SID}, open("/tmp/b2a/fd_ids.json", "w"))
