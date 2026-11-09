"""Alur H — transfer masuk antar site: RCM-WOVEN → WH-JKT (KSC), 2 roll; terima 1 roll (parsial) oleh petugas Jakarta,
roll ke-2 dilaporkan hilang lalu dikembalikan ke asal → status akhir? Uji juga: petugas Rancamalang menerima di Jakarta."""
import kn

ENT = "ent_ksc"
SRC, DST = "wh_adc8726d019e", "wh_jakarta"
rolls = list(kn.db.inventory_rolls.find({"warehouse_id": SRC, "owner_entity_id": ENT, "status": "available",
                                         "length_remaining": {"$gt": 0}, "active_movement": None,
                                         "length_reserved": {"$not": {"$gt": 0}}}, {"_id": 0}).limit(2))
print("rolls", [(r["roll_no"], r["product_id"], r["length_remaining"], r.get("bin_id")) for r in rolls])
items = {}
for r in rolls:
    it = items.setdefault(r["product_id"], {"product_id": r["product_id"], "qty": 0, "roll_ids": []})
    it["qty"] += r["length_remaining"]
    it["roll_ids"].append(r["id"])
c, t = kn.call("wh.admin", "POST", "/transfers", {"source_warehouse_id": SRC, "dest_warehouse_id": DST,
               "items": list(items.values()), "notes": "B2A alur H"}, entity=ENT, quiet=True)
print("create", c, str(t)[:300] if c != 200 else (t.get("code"), t.get("status")))
TRF = t["id"]
for st_, who in (("approve", "manager"),):
    c, o = kn.call(who, "POST", f"/transfers/{TRF}/approve", {}, entity=ENT, quiet=True)
    print("approve", c, str(o)[:200] if c != 200 else o.get("status"))
for s in ("picking", "staging", "dispatched"):
    c, o = kn.call("warehouse.rancamalang", "POST", f"/transfers/{TRF}/status", {"status": s}, entity=ENT, quiet=True)
    print(s, c, str(o)[:200] if c != 200 else o.get("status"))
print("rolls after dispatch", kn.snap("inventory_rolls", {"id": {"$in": [r["id"] for r in rolls]}}, ["roll_no", "status", "warehouse_id", "bin_id", "journey", "transfer_ref"]))
# Petugas RANCAMALANG menerima di gudang Jakarta (uji cakupan lokasi)
c, o = kn.call("warehouse.rancamalang", "POST", f"/transfers/{TRF}/receive", {"lines": [{"roll_id": rolls[0]["id"]}]}, entity=ENT, quiet=True)
print("RCM worker receive at JKT:", c, str(o)[:250] if c != 200 else (o.get("status"), o.get("received")))
r0 = kn.db.inventory_rolls.find_one({"id": rolls[0]["id"]}, {"_id": 0})
print("roll0", r0["status"], r0["warehouse_id"], r0.get("bin_id"), r0.get("journey"))
# Ulang kirim yang sama (idempoten?)
c, o = kn.call("warehouse.rancamalang", "POST", f"/transfers/{TRF}/receive", {"lines": [{"roll_id": rolls[0]["id"]}]}, entity=ENT, quiet=True)
print("repeat receive:", c, str(o)[:250])
if len(rolls) > 1:
    c, o = kn.call("warehouse", "POST", f"/transfers/{TRF}/exceptions", {"kind": "missing", "roll_id": rolls[1]["id"], "reason": "roll tidak ada di truk"}, entity=ENT, quiet=True)
    print("missing", c, str(o)[:200])
    tr = kn.db.warehouse_transfers.find_one({"id": TRF}, {"_id": 0})
    exc = [e for e in tr.get("exceptions") or [] if e.get("kind") == "missing"]
    if exc:
        c, o = kn.call("wh.admin", "POST", f"/transfers/{TRF}/exceptions/{exc[0]['id']}/resolve", {"action": "return_to_source", "note": "kembali ke asal"}, entity=ENT, quiet=True)
        print("resolve return_to_source", c, str(o)[:250])
tr = kn.db.warehouse_transfers.find_one({"id": TRF}, {"_id": 0})
print("TRANSFER", tr["status"], tr.get("completion_basis"), [(e.get("kind"), e.get("status")) for e in tr.get("exceptions") or []], len(tr.get("receipt_events") or []))
print("rolls", kn.snap("inventory_rolls", {"id": {"$in": [r["id"] for r in rolls]}}, ["roll_no", "status", "warehouse_id", "bin_id", "journey", "last_transfer"]))
print("mov", kn.snap("inventory_movements", {"roll_id": {"$in": [r["id"] for r in rolls]}, "reference_id": TRF}, ["movement_type", "warehouse_id", "quantity"]))
print("mov2", kn.snap("inventory_movements", {"roll_id": {"$in": [r["id"] for r in rolls]}, "movement_type": {"$regex": "transfer"}}, ["movement_type", "warehouse_id", "quantity", "source_document"]))
# Draf putaway di Jakarta untuk roll yang tiba?
print("PA for rolls", kn.snap("putaway_orders", {"items.roll_id": {"$in": [r["id"] for r in rolls]}, "status": {"$ne": "completed"}}, ["pa_number", "status"]))
