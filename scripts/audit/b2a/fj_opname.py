"""Alur J — opname per roll WH-JKT zona A: potret → pindai (cocok, salah alamat, kode tak dikenal, petugas lokasi lain)
→ roll hilang dihitung ulang → ACC (hapus + temuan + jurnal). Cek: roll tanpa bin tidak ikut potret."""
import kn

ENT, WH = "ent_ksc", "wh_jakarta"
JKT, RCM = "warehouse", "warehouse.rancamalang"
import sys
sys.path.insert(0, "/app/backend")
from services.placement_rules import flatten_nodes
wh = kn.db.warehouses.find_one({"id": WH}, {"_id": 0})
nodes = flatten_nodes(wh)
from collections import Counter
cnt = Counter(r["bin_id"] for r in kn.db.inventory_rolls.find({"warehouse_id": WH, "owner_entity_id": ENT, "status": "available",
              "length_remaining": {"$gt": 0}, "bin_id": {"$in": [n["bin"]["id"] for n in nodes]}}, {"_id": 0, "bin_id": 1}))
pick = next(b for b, n in cnt.most_common() if 3 <= n <= 6)
node = next(n for n in nodes if n["bin"]["id"] == pick)
bin_ids = [n["bin"]["id"] for n in nodes if n["rack"]["id"] == node["rack"]["id"]]
print("scope bin", node["path"], "rolls", cnt[pick])
c, s = kn.call(JKT, "POST", "/cycle-count/sessions", {"warehouse_id": WH, "name": "B2A opname zona A"}, entity=ENT, quiet=True)
SID = s["id"]
c, o = kn.call(JKT, "POST", f"/cycle-count/sessions/{SID}/roll-scope", {"node_id": pick}, entity=ENT, quiet=True)
ses = kn.db.cycle_count_sessions.find_one({"id": SID}, {"_id": 0})
exp = ses["roll_count"]["expected"]
print("snapshot expected:", len(exp), [(e["roll_no"], e["bin_id"][-6:], e["qty"], e["status"]) for e in exp[:6]])
if len(exp) < 3:
    raise SystemExit("data zona kurang")
e1, e2, e3 = exp[0], exp[1], exp[2]
other_bin = e2["bin_id"]  # satu bin cakupan: salah alamat diuji lewat roll tanpa bin
nb = kn.db.inventory_rolls.find_one({"warehouse_id": WH, "owner_entity_id": ENT, "status": "available", "bin_id": None, "length_remaining": {"$gt": 0}}, {"_id": 0})
c, o = kn.call(JKT, "POST", f"/cycle-count/sessions/{SID}/roll-scans", {"code": nb["roll_no"], "bin_id": pick}, entity=ENT, quiet=True)
print("scan roll tanpa bin:", nb["roll_no"], (o or {}).get("scan", {}).get("kinds") if isinstance(o, dict) else o)
kn.call(JKT, "POST", f"/cycle-count/sessions/{SID}/roll-scans", {"code": e1["roll_no"], "bin_id": e1["bin_id"]}, entity=ENT, quiet=True)
kn.call(JKT, "POST", f"/cycle-count/sessions/{SID}/roll-scans", {"code": e2["roll_no"], "bin_id": other_bin}, entity=ENT, quiet=True)
c, o = kn.call(JKT, "POST", f"/cycle-count/sessions/{SID}/roll-scans", {"code": "KODE-ASING-B2A-001", "bin_id": e1["bin_id"]}, entity=ENT, quiet=True)
print("scan unknown", c, (o or {}).get("scan", {}).get("kinds") if isinstance(o, dict) else o)
# petugas Rancamalang memindai di sesi Jakarta
c, o = kn.call(RCM, "POST", f"/cycle-count/sessions/{SID}/roll-scans", {"code": e1["roll_no"], "bin_id": e1["bin_id"], "measured_qty": e1["qty"]}, entity=ENT, quiet=True)
print("RCM worker scan in JKT session:", c, str(o)[:150])
# semua sisanya dianggap hilang; hitung ulang e3 saja
c, rec = kn.call(JKT, "GET", f"/cycle-count/sessions/{SID}/roll-reconcile", entity=ENT, quiet=True)
print("reconcile counts", rec.get("counts"))
c, o = kn.call(JKT, "POST", f"/cycle-count/sessions/{SID}/roll-missing-recount", {"roll_id": e3["roll_id"], "note": "dicari ulang, tidak ada"}, entity=ENT, quiet=True)
tag3 = kn.db.rfid_tags.find_one({"roll_id": e3["roll_id"], "status": "active"}, {"_id": 0, "id": 1, "epc": 1})
unk = next(l for l in rec["lines"] if "unknown" in l["kinds"])
je_before = kn.count("journal_entries", {"source_type": "cycle_count_variance"})
c, o = kn.call("wh.admin", "POST", f"/cycle-count/sessions/{SID}/roll-finalize", {"reason": "Hasil opname zona A",
               "new_rolls": [{"scan_id": unk["id"], "product_id": e1["product_id"], "owner_entity_id": ENT, "qty": 12.5}]}, entity=ENT, quiet=True)
print("finalize", c, str(o)[:400])
ses = kn.db.cycle_count_sessions.find_one({"id": SID}, {"_id": 0})
print("session status", ses["status"], "result", {k: ses.get(k) for k in ("approved_by", "summary") if ses.get(k)})
print("roll tanpa bin sesudah ACC:", kn.snap("inventory_rolls", {"id": nb["id"]}, ["roll_no", "bin_id", "status"]))
print("e2:", kn.snap("inventory_rolls", {"id": e2["roll_id"]}, ["roll_no", "bin_id", "status"]))
print("e3 (hilang):", kn.snap("inventory_rolls", {"id": e3["roll_id"]}, ["roll_no", "status", "length_remaining", "lost_in_count", "rfid_tag_id"]))
print("tag e3 sesudah:", tag3, kn.snap("rfid_tags", {"id": (tag3 or {}).get("id")}, ["status", "roll_id"]))
found = kn.snap("inventory_rolls", {"opname_found_code": "KODE-ASING-B2A-001"}, ["roll_no", "status", "bin_id", "bin_code", "unit_cost", "length_remaining", "rfid_tag_id", "journey"])
print("found roll:", found)
print("JE cycle_count_variance +", kn.count("journal_entries", {"source_type": "cycle_count_variance"}) - je_before,
      kn.snap("journal_entries", {"source_type": "cycle_count_variance", "source_id": {"$regex": SID}}, ["source_id", "total_debit", "status"]))
others = [e for e in exp[3:]]
print("roll lain di potret yg tidak dipindai & tanpa hitung ulang:", len(others), "status tetap:", kn.snap("inventory_rolls", {"id": {"$in": [e["roll_id"] for e in others[:3]]}}, ["roll_no", "status"]))
