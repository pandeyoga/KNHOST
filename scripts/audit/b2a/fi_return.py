"""Alur I — retur penjualan terima barang: SRET-00167 (approved). Pindai terima di Gedung Retur RCM → apakah stok
berubah? → inspeksi grade A (bukan B/BS/C) → selesaikan (store credit) → karantina di mana? → lepas karantina →
roll grade A di Gedung Retur (aturan grade B/BS/C)? draf PA?"""
import kn

ENT = "ent_ksc"
ret = kn.db.sales_returns.find_one({"number": "SRET-00167"}, {"_id": 0})
RID = ret["id"]
roll_id = ret["items"][0]["roll_ids"][0]
roll = kn.db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0})
print("roll awal", roll["roll_no"], roll["status"], roll["warehouse_id"], roll.get("grade"), roll.get("owner_entity_id"), roll.get("journey"))
RETUR = "wh_6cccc13554f8"
before = kn.counts(kn.WATCH)
c, o = kn.call("warehouse.rancamalang", "POST", f"/sales-returns/{RID}/journey/scan",
               {"stage": "received", "codes": [roll["roll_no"]], "warehouse_id": RETUR}, entity=ENT, quiet=True)
print("journey scan", c, str(o)[:250])
print("delta counts after scan:", kn.delta(before, kn.counts(kn.WATCH)))
r = kn.db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0})
print("roll after scan", r["status"], r["warehouse_id"], r.get("journey"))
# inspeksi lewat jalur retur
c, o = kn.call("wh.admin", "POST", f"/sales-returns/{RID}/inspect/start", {}, entity=ENT, quiet=True)
print("inspect start", c, str(o)[:200] if c != 200 else o.get("status"))
spk = kn.db.inspections.find_one({"ref_doc_id": RID, "kind": "return_customer", "status": {"$in": ["draft", "assigned", "in_progress"]}}, {"_id": 0})
print("SPK retur:", spk and (spk["number"], spk["status"]))
c, o = kn.call("wh.admin", "POST", f"/sales-returns/{RID}/inspect/complete",
               {"inspections": [{"index": 0, "grade": "A", "condition": "ok", "accepted_qty": roll.get("length_remaining") or 0}]}, entity=ENT, quiet=True)
print("inspect complete", c, str(o)[:300] if c != 200 else o.get("status"))
c, o = kn.call("manager", "POST", f"/sales-returns/{RID}/settle", {"outcome": "store_credit", "return_warehouse_id": RETUR,
               "decision_note": "ACC manajer"}, entity=ENT, quiet=True)
print("settle", c, str(o)[:300] if c != 200 else (o.get("status"), o.get("stock_adjusted")))
r = kn.db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0})
new = list(kn.db.inventory_rolls.find({"$or": [{"id": roll_id}, {"parent_roll_id": roll_id}, {"return_restore.return_id": RID}]}, {"_id": 0}))
print("rolls after settle", [(x["roll_no"], x["status"], x["warehouse_id"][-6:], x.get("grade"), x.get("qc_status"), (x.get("journey") or {}).get("stage"), x.get("bin_id")) for x in new])
print("mov", kn.snap("inventory_movements", {"roll_id": {"$in": [x["id"] for x in new]}, "movement_type": {"$regex": "return|quarantine"}}, ["movement_type", "warehouse_id", "quantity"]))
c, o = kn.call("manager", "POST", f"/sales-returns/{RID}/quarantine/release", {"decisions": [{"roll_id": x["id"], "action": "release", "grade": "A"} for x in new if x["status"] == "quarantine"]}, entity=ENT, quiet=True)
print("release", c, str(o)[:300])
new = list(kn.db.inventory_rolls.find({"id": {"$in": [x["id"] for x in new]}}, {"_id": 0}))
print("rolls after release", [(x["roll_no"], x["status"], x["warehouse_id"][-6:], x.get("grade"), (x.get("journey") or {}).get("stage"), x.get("bin_id")) for x in new])
print("PA", kn.snap("putaway_orders", {"items.roll_id": {"$in": [x["id"] for x in new]}}, ["pa_number", "status", "to_warehouse_name"]))
print("delta counts total:", kn.delta(before, kn.counts(kn.WATCH)))
