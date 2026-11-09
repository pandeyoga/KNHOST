"""Alur K — pendaftaran awal gedung SRG-01 (Kanda), beku per rak: mulai → uji pembekuan (terima PO lama dgn bin beku,
place_roll ke bin beku, opname biasa surplus di bin beku) → baris lapangan (roll lama cocok, roll baru, produk belum
dikenali) → ajukan → ACC → jurnal, tag, area terverifikasi, beku dilepas."""
import json
import sys
from collections import Counter
sys.path.insert(0, "/app/backend")
import kn
from services.placement_rules import flatten_nodes

ENT, WH = "ent_kanda", "wh_40e831c5bb53"
W = "warehouse.soreang"
wh = kn.db.warehouses.find_one({"id": WH}, {"_id": 0})
nodes = flatten_nodes(wh)
rack_of = {n["bin"]["id"]: n["rack"]["id"] for n in nodes}
cnt = Counter(rack_of.get(r["bin_id"]) for r in kn.db.inventory_rolls.find(
    {"warehouse_id": WH, "status": "available", "length_remaining": {"$gt": 0}, "bin_id": {"$in": list(rack_of)}}, {"_id": 0, "bin_id": 1}))
print("rack counts", sorted(cnt.items(), key=lambda x: x[1])[:8]); rack = sorted([kv for kv in cnt.items() if kv[0] and kv[1] >= 2], key=lambda x: x[1])[0][0]
rbins = [n["bin"]["id"] for n in nodes if n["rack"]["id"] == rack]
old = list(kn.db.inventory_rolls.find({"warehouse_id": WH, "bin_id": {"$in": rbins}, "length_remaining": {"$gt": 0},
                                       "status": {"$in": ["available", "reserved", "quarantine", "blocked"]}}, {"_id": 0}))
print("rak", rack, "bins", len(rbins), "roll lama", [(r["roll_no"], r["status"], r["product_id"][-6:], r["length_remaining"], r.get("owner_entity_id")) for r in old])
c, s = kn.call(W, "POST", "/registration/sessions", {"warehouse_id": WH, "name": "B2A daftar awal rak", "freeze_mode": "zone",
               "epc_mode": "system", "node_ids": [rack]}, entity=ENT, quiet=True)
print("create", c, str(s)[:200] if c != 200 else (s.get("number"), s.get("status")))
SID = s["id"]
c, o = kn.call(W, "POST", f"/registration/sessions/{SID}/start", {}, entity=ENT, quiet=True)
print("start", c, (o or {}).get("status") if isinstance(o, dict) else o)
# ── uji pembekuan ──
fb = rbins[0]
r_free = kn.db.inventory_rolls.find_one({"warehouse_id": WH, "status": "available", "bin_id": {"$nin": rbins}, "length_remaining": {"$gt": 0}, "owner_entity_id": ENT}, {"_id": 0})
c, o = kn.call(W, "POST", "/inventory/putaway", {"roll_id": r_free["id"], "bin_id": fb}, entity=ENT, quiet=True)
print("FREEZE place_roll ke bin beku:", c, str(o)[:160])
c, po = kn.call("admin", "POST", "/purchase-orders", {"supplier_id": "sup_a47057e2dfc2", "ship_to_site_id": "site_fd9f6aa41d36",
                "items": [{"product_id": "prod_97ef39b63081", "quantity": 40, "unit": "yard", "price": 21000, "expected_grade": "A", "qty_rolls": 1}],
                "notes": "B2A K beku"}, entity=ENT, quiet=True)
t = kn.db.wms_tasks.find_one({"po_id": po["id"]}, {"_id": 0})
kn.call(W, "POST", f"/inbound/tasks/{t['id']}/scan-receive", {"product_id": "prod_97ef39b63081", "actual_qty": 40, "bin_id": fb}, entity=ENT, quiet=True)
c, o = kn.call(W, "POST", f"/inbound/tasks/{t['id']}/complete", {"supplier_lot": "K", "dye_lot": "K"}, entity=ENT, quiet=True)
print("FREEZE terima PO jalur lama dgn bin beku:", c, kn.snap("inventory_rolls", {"po_id": po["id"]}, ["roll_no", "bin_id", "status"]))
c, cs = kn.call(W, "POST", "/cycle-count/sessions", {"warehouse_id": WH, "name": "B2A opname biasa saat beku"}, entity=ENT, quiet=True)
c, o = kn.call(W, "POST", f"/cycle-count/sessions/{cs['id']}/items", {"product_id": old[0]["product_id"], "bin_id": fb, "owner_entity_id": ENT}, entity=ENT, quiet=True)
print("FREEZE opname biasa tambah item bin beku:", c, str(o)[:120])
# ── baris lapangan ──
sess = kn.db.cycle_count_sessions.find_one({"id": SID}, {"_id": 0})
lines = []
o0 = old[0]
c, o = kn.call(W, "POST", f"/registration/sessions/{SID}/lines", {"product_id": o0["product_id"], "qty": o0["length_remaining"], "unit": o0.get("unit"),
               "length_from_label": True, "grade": "A", "owner_entity_id": ENT, "bin_id": o0["bin_id"], "old_roll_no": o0["roll_no"]}, entity=ENT, quiet=True)
print("line lama-cocok", c, str(o)[:200] if c != 200 else (o.get("line", o).get("status"), o.get("line", o).get("epc")))
c, o = kn.call(W, "POST", f"/registration/sessions/{SID}/lines", {"product_id": "prod_97ef39b63081", "qty": 33, "unit": "yard",
               "length_from_label": False, "grade": "A", "owner_entity_id": ENT, "bin_id": rbins[-1]}, entity=ENT, quiet=True)
print("line baru", c, str(o)[:200] if c != 200 else "ok")
c, o = kn.call(W, "POST", f"/registration/sessions/{SID}/lines", {"unrecognized": True, "note": "kain motif bunga tanpa label", "qty": 20, "unit": "yard",
               "grade": "A", "owner_entity_id": ENT, "bin_id": rbins[-1]}, entity=ENT, quiet=True)
print("line belum dikenali", c, str(o)[:200] if c != 200 else "ok")
c, o = kn.call(W, "POST", f"/registration/sessions/{SID}/submit", {}, entity=ENT, quiet=True)
print("submit", c, str(o)[:200] if c != 200 else o.get("status"))
c, d = kn.call("wh.admin", "GET", f"/registration/sessions/{SID}", entity=ENT, quiet=True)
print("detail", c, json.dumps({k: d.get(k) for k in ("status", "progress", "plan")}, default=str)[:1500] if c == 200 else d)
json.dump({"SID": SID, "rack": rack, "rbins": rbins, "old": [r["id"] for r in old], "cc": cs["id"]}, open("/tmp/b2a/fk_ids.json", "w"))
