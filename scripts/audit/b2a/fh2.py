"""Alur H2 — (a) selesaikan roll hilang transfer H (return_to_source, alasan) ; (b) transfer 1 roll: 0 diterima, semua
dikembalikan ke asal → status akhir?"""
import kn

ENT = "ent_ksc"
tr = kn.db.warehouse_transfers.find_one({"code": "KSC/TRF-00018"}, {"_id": 0})
exc = [e for e in tr.get("exceptions") or [] if e.get("kind") == "missing" and e.get("status") == "open"]
c, o = kn.call("wh.admin", "POST", f"/transfers/{tr['id']}/exceptions/{exc[0]['id']}/resolve",
               {"action": "return_to_source", "reason": "roll ternyata tertinggal di gudang asal"}, entity=ENT, quiet=True)
print("resolve", c, str(o)[:200])
tr = kn.db.warehouse_transfers.find_one({"id": tr["id"]}, {"_id": 0})
print("TRF-18", tr["status"], tr.get("completion_basis"))
# (b)
SRC, DST = "wh_adc8726d019e", "wh_jakarta"
r = kn.db.inventory_rolls.find_one({"warehouse_id": SRC, "owner_entity_id": ENT, "status": "available", "length_remaining": {"$gt": 0},
                                    "active_movement": None, "length_reserved": {"$not": {"$gt": 0}}}, {"_id": 0})
c, t = kn.call("wh.admin", "POST", "/transfers", {"source_warehouse_id": SRC, "dest_warehouse_id": DST,
               "items": [{"product_id": r["product_id"], "qty": r["length_remaining"], "roll_ids": [r["id"]]}], "notes": "B2A H2"}, entity=ENT, quiet=True)
TRF = t["id"]
kn.call("manager", "POST", f"/transfers/{TRF}/approve", {}, entity=ENT, quiet=True)
for s in ("picking", "staging", "dispatched"):
    kn.call("warehouse.rancamalang", "POST", f"/transfers/{TRF}/status", {"status": s}, entity=ENT, quiet=True)
c, o = kn.call("warehouse", "POST", f"/transfers/{TRF}/exceptions", {"kind": "missing", "roll_id": r["id"], "reason": "tidak ada di truk"}, entity=ENT, quiet=True)
eid = o["exception"]["id"]
c, o = kn.call("wh.admin", "POST", f"/transfers/{TRF}/exceptions/{eid}/resolve", {"action": "return_to_source", "reason": "truk batal muat roll ini"}, entity=ENT, quiet=True)
print("resolve b", c, str(o)[:200])
t = kn.db.warehouse_transfers.find_one({"id": TRF}, {"_id": 0})
print("TRF-b", t["code"], t["status"], t.get("completion_basis"), t.get("completed_at"))
print("roll", kn.snap("inventory_rolls", {"id": r["id"]}, ["roll_no", "status", "warehouse_id", "returned_from_transfer"]))
c, s = kn.call("wh.admin", "GET", f"/transfers/{TRF}/receipt", entity=ENT, quiet=True)
print("receipt summary", c, str(s)[:400])
