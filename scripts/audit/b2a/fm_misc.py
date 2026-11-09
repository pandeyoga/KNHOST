"""Alur M — sisa uji cepat:
M1 sesi pendaftaran DITOLAK lalu dibuka lewat endpoint opname biasa (reopen) → status/mode?
M2 opname per roll menghapus roll ber-tag RFID aktif → tag ikut dicabut?"""
import sys
sys.path.insert(0, "/app/backend")
import kn
from services.placement_rules import flatten_nodes

ENT, WH, W = "ent_kanda", "wh_40e831c5bb53", "warehouse.soreang"
wh = kn.db.warehouses.find_one({"id": WH}, {"_id": 0})
rack = next(n["rack"]["id"] for n in flatten_nodes(wh) if n["rack"]["id"] != "rack_sim_srg_01_w01")
c, s = kn.call(W, "POST", "/registration/sessions", {"warehouse_id": WH, "name": "B2A M1", "freeze_mode": "zone", "node_ids": [rack]}, entity=ENT, quiet=True)
SID = s["id"]
kn.call(W, "POST", f"/registration/sessions/{SID}/start", {}, entity=ENT, quiet=True)
c, o = kn.call("wh.admin", "POST", f"/registration/sessions/{SID}/reject", {"reason": "salah pilih rak"}, entity=ENT, quiet=True)
print("M1 reject", c, (o or {}).get("status") if isinstance(o, dict) else o)
c, o = kn.call("wh.admin", "POST", f"/cycle-count/sessions/{SID}/reopen", {"reason": "buka lagi"}, entity=ENT, quiet=True)
print("M1 reopen via opname biasa:", c, str(o)[:160])
print("M1 sesi:", kn.db.cycle_count_sessions.find_one({"id": SID}, {"_id": 0, "status": 1, "mode": 1, "registration.freeze.active": 1}))
c, o = kn.call(W, "POST", f"/cycle-count/sessions/{SID}/roll-scope", {"node_id": rack}, entity=ENT, quiet=True)
print("M1 roll-scope pada sesi pendaftaran:", c, str(o)[:120], kn.db.cycle_count_sessions.find_one({"id": SID}, {"_id": 0, "status": 1, "mode": 1}))
# M2
tag = None
for t in kn.db.rfid_tags.find({"status": "active"}, {"_id": 0}):
    r = kn.db.inventory_rolls.find_one({"id": t.get("roll_id"), "status": "available", "bin_id": {"$nin": [None, ""]}, "length_remaining": {"$gt": 0}}, {"_id": 0})
    if r:
        tag, roll = t, r
        break
if not tag:
    print("M2 lewati — tidak ada roll ber-tag aktif di bin")
    raise SystemExit
ent = roll["owner_entity_id"]
who = {"wh_jakarta": "warehouse", "wh_40e831c5bb53": "warehouse.soreang"}.get(roll["warehouse_id"], "wh.admin")
print("M2 roll", roll["roll_no"], roll["warehouse_id"], roll["bin_id"], "tag", tag["epc"], "pemilik", ent, "petugas", who)
c, cs = kn.call(who, "POST", "/cycle-count/sessions", {"warehouse_id": roll["warehouse_id"], "name": "B2A M2"}, entity=ent, quiet=True)
print("M2 create", c, str(cs)[:120])
CS = cs["id"]
c, o = kn.call(who, "POST", f"/cycle-count/sessions/{CS}/roll-scope", {"node_id": roll["bin_id"]}, entity=ent, quiet=True)
print("M2 scope", c)
kn.call(who, "POST", f"/cycle-count/sessions/{CS}/roll-missing-recount", {"roll_id": roll["id"], "note": "tidak ditemukan"}, entity=ent, quiet=True)
c, o = kn.call("manager", "POST", f"/cycle-count/sessions/{CS}/roll-finalize", {"reason": "roll hilang", "zero_cost_reason": "-"}, entity=ent, quiet=True)
print("M2 finalize", c, str(o)[:150])
print("M2 roll", kn.snap("inventory_rolls", {"id": roll["id"]}, ["status", "length_remaining", "rfid_tag_id"]), "tag", kn.snap("rfid_tags", {"id": tag["id"]}, ["status", "roll_id"]))
