"""Alur A bagian 3 — draf PA (salah tujuan) → ubah tujuan → verifikasi label → uji cakupan lokasi (petugas Jakarta
menerbitkan/mengirim/menerima PA Rancamalang) → tiba → simpan ke bin."""
import json
import kn
exec(open("/tmp/b2a/fa_legacy.py").read().split("stp(\"0_awal\")")[0])

roll = kn.db.inventory_rolls.find_one({"po_id": PO}, {"_id": 0})
pa = kn.db.putaway_orders.find_one({"items.roll_id": roll["id"], "status": "draft"}, {"_id": 0})
PAID = pa["id"]
JKT = "warehouse"   # petugas Jakarta (KSC)
c, d = kn.call(W, "GET", f"/putaway-orders/{PAID}", entity="ent_ksc", quiet=True)
print("detail draf (petugas RCM):", c, d.get("to_warehouse_name"), [(i.get("roll_no"), i.get("ready"), i.get("block_reason")) for i in d.get("items", [])],
      [o["warehouse_name"] for o in d.get("destination_options", [])])
c, d = kn.call(JKT, "GET", f"/putaway-orders/{PAID}", quiet=True)
print("detail draf (petugas JAKARTA):", c, str(d)[:200])
# Daftar PA: siapa lihat
for who, ent in [(W, None), (W, "ent_ksc"), (JKT, None), ("warehouse.soreang", None)]:
    c, o = kn.call(who, "GET", "/putaway-orders", entity=ent, quiet=True)
    print(f"LIST PA {who} {ent}: {c} n={len(o.get('orders', [])) if isinstance(o, dict) else o} lihat={PAID in [x['id'] for x in o.get('orders', [])] if isinstance(o, dict) else '-'}")
# Ubah tujuan ke Gudang Woven
c, d = kn.call(W, "PATCH", f"/putaway-orders/{PAID}/draft", {"to_warehouse_id": "wh_adc8726d019e"}, entity="ent_ksc")
# Terbitkan sebelum label diverifikasi
c, d = kn.call(W, "POST", f"/putaway-orders/{PAID}/publish", {}, entity="ent_ksc")
# verifikasi label QR di transit
c, d = kn.call(W, "POST", "/putaway-orders/verify-labels", {"warehouse_id": roll["warehouse_id"], "codes": [roll["roll_no"]]}, entity="ent_ksc")
stp("5_label_verified")
# Petugas JAKARTA menerbitkan PA Rancamalang (uji cakupan lokasi)
c, d = kn.call(JKT, "POST", f"/putaway-orders/{PAID}/publish", {})
stp("6_published")
c, d = kn.call(JKT, "POST", f"/putaway-orders/{PAID}/dispatch", {})
stp("7_dispatched")
c, d = kn.call(JKT, "POST", f"/putaway-orders/{PAID}/arrival-trips", {"epcs": [roll["roll_no"]], "client_trip_id": "b2a-trip-1"})
c, d = kn.call(JKT, "POST", f"/putaway-orders/{PAID}/arrival-trips", {"epcs": [roll["roll_no"]], "client_trip_id": "b2a-trip-1"})
stp("8_arrived")
# simpan ke bin (petugas RCM) — saran bin lalu putaway
r2 = kn.db.inventory_rolls.find_one({"id": roll["id"]}, {"_id": 0})
c, s = kn.call(W, "GET", f"/inventory/rolls/{roll['id']}/bin-suggestions", entity="ent_ksc", quiet=True)
print("bin-suggestions:", c, str(s)[:300])
wh = kn.db.warehouses.find_one({"id": r2["warehouse_id"]}, {"_id": 0, "zones": 1})
b0 = wh["zones"][0]["racks"][0]["bins"][0]
c, o = kn.call(W, "POST", "/inventory/putaway", {"roll_id": roll["id"], "bin_id": b0["id"]}, entity="ent_ksc")
stp("9_binned")
json.dump(R, open("/tmp/b2a/fa3_state.json", "w"), default=str)
