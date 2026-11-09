import json
import kn

ids = json.load(open("/tmp/b2a/fk_ids.json"))
SID, rbins, ENT = ids["SID"], ids["rbins"], "ent_kanda"
W = "warehouse.soreang"
unrec = kn.db.initial_registration_lines.find_one({"session_id": SID, "unrecognized": {"$ne": None}, "live": True}, {"_id": 0})
print("(sudah diajukan)", kn.db.cycle_count_sessions.find_one({"id": SID}, {"_id": 0, "status": 1}))
c, o = kn.call("wh.admin", "PATCH", f"/registration/sessions/{SID}/lines/{unrec['id']}", {"product_id": "prod_97ef39b63081", "unrecognized": False, "qty": 20, "unit": "yard"}, entity=ENT, quiet=True)
print("map unrecognized", c, str(o)[:160])
c, rec = kn.call("wh.admin", "GET", f"/registration/sessions/{SID}/reconcile", entity=ENT, quiet=True)
if c == 200:
    for g in rec.get("groups") or []:
        print("GROUP", g.get("key"), g.get("product_sku") or g.get("product_id"), "lama", g.get("old_count"), "baru", g.get("new_count"),
              "hilang", g.get("missing_count"), "cocok", g.get("matched_count"), "selisih", g.get("diff_qty"), "nilai", g.get("value"), "cost", g.get("unit_cost"))
    print("rec keys", list(rec.keys()))
else:
    print("reconcile", c, rec)
before = kn.counts(kn.WATCH)
c, o = kn.call("wh.admin", "POST", f"/registration/sessions/{SID}/approve", {"reason": "Pendaftaran awal rak W01", "zero_cost_reason": "temuan tanpa harga"}, entity=ENT, quiet=True)
print("approve", c, json.dumps(o, default=str)[:1200])
print("delta", kn.delta(before, kn.counts(kn.WATCH)))
s = kn.db.cycle_count_sessions.find_one({"id": SID}, {"_id": 0})
print("session", s["status"], "freeze", (s.get("registration") or {}).get("freeze") or s.get("freeze"))
print("roll PO RL-46677:", kn.snap("inventory_rolls", {"roll_no": "RL-46677"}, ["status", "bin_id", "length_remaining", "registration"]))
newr = kn.snap("inventory_rolls", {"registration.session_id": SID}, ["roll_no", "status", "bin_id", "length_remaining", "unit_cost", "rfid_tag_id", "rfid_epc", "length_verified", "journey", "registration"])
print("roll hasil daftar:", [(r["roll_no"], r["status"], r.get("unit_cost"), r.get("rfid_epc"), r.get("length_verified"), (r.get("registration") or {}).get("old_roll_no")) for r in newr])
print("tags:", kn.snap("rfid_tags", {"roll_id": {"$in": [r.get("id") for r in kn.snap("inventory_rolls", {"registration.session_id": SID}, ["id"])]}}, ["epc", "status"]))
print("JE:", kn.snap("journal_entries", {"source_id": {"$regex": SID}}, ["source_id", "total_debit", "status"]))
print("written off:", kn.count("inventory_rolls", {"id": {"$in": ids["old"]}, "status": "consumed"}), "dari", len(ids["old"]))
print("area status:", kn.snap("registration_area_status", {}, None))
c, f = kn.call(W, "GET", "/registration/freeze", params={"warehouse_id": "wh_40e831c5bb53"}, entity=ENT, quiet=True)
print("freeze endpoint", c, str(f)[:300])
