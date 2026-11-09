import kn

ENT = "ent_ksc"
ses = kn.db.cycle_count_sessions.find_one({"name": "B2A opname zona A", "status": "open"}, {"_id": 0}, sort=[("created_at", -1)])
SID = ses["id"]
rc = ses["roll_count"]
exp = rc["expected"]
e3 = exp[2]
tag3 = kn.db.rfid_tags.find_one({"roll_id": e3["roll_id"], "status": {"$ne": "retired"}}, {"_id": 0, "id": 1, "epc": 1, "status": 1})
unk = next(s for s in rc["scans"] if not s.get("roll_id"))
foreign = next(s for s in rc["scans"] if s.get("roll_id") and s["roll_id"] not in {e["roll_id"] for e in exp})
prod = kn.db.products.find_one({"id": exp[0]["product_id"]}, {"_id": 0, "sku": 1, "harga_pokok": 1, "standard_cost": 1, "cost_price": 1})
uc = [r.get("unit_cost") for r in kn.db.inventory_rolls.find({"id": {"$in": [e["roll_id"] for e in exp]}}, {"_id": 0, "unit_cost": 1})]
print("product", prod, "unit_cost rolls", uc)
c, o = kn.call("wh.admin", "POST", f"/cycle-count/sessions/{SID}/roll-finalize", {"reason": "Hasil opname zona A",
               "zero_cost_reason": "barang temuan tanpa harga acuan, dinilai nol",
               "new_rolls": [{"scan_id": unk["id"], "product_id": exp[0]["product_id"], "owner_entity_id": ENT, "qty": 12.5}]}, entity=ENT, quiet=True)
print("finalize", c, str(o)[:500])
ses = kn.db.cycle_count_sessions.find_one({"id": SID}, {"_id": 0})
print("session", ses["status"], {k: v for k, v in (ses.get("roll_count") or {}).items() if k in ("result", "summary", "missing_adjustments")})
print("foreign (tanpa bin):", kn.snap("inventory_rolls", {"id": foreign["roll_id"]}, ["roll_no", "bin_id", "bin_code", "status"]))
print("e3 hilang:", kn.snap("inventory_rolls", {"id": e3["roll_id"]}, ["roll_no", "status", "length_remaining", "lost_in_count", "rfid_tag_id"]))
print("tag e3:", tag3, kn.snap("rfid_tags", {"id": (tag3 or {}).get("id", "-")}, ["status"]))
others = [e for e in exp if e["roll_id"] not in {s.get("roll_id") for s in rc["scans"]} and e["roll_id"] != e3["roll_id"]]
print("hilang tanpa hitung ulang:", [(e["roll_no"]) for e in others], kn.snap("inventory_rolls", {"id": {"$in": [e["roll_id"] for e in others]}}, ["roll_no", "status"]))
print("found:", kn.snap("inventory_rolls", {"opname_found_code": "KODE-ASING-B2A-001"}, ["roll_no", "status", "bin_id", "bin_code", "unit_cost", "length_remaining", "rfid_tag_id", "journey", "lot"]))
print("JE:", kn.snap("journal_entries", {"source_type": "cycle_count_variance", "source_id": {"$regex": SID}}, ["source_id", "total_debit", "status", "lines"]))
print("mov:", kn.snap("inventory_movements", {"source_document": {"$regex": SID}}, ["movement_type", "quantity", "roll_id"]) or kn.snap("inventory_movements", {"reference_id": SID}, ["movement_type", "quantity"]))
c, o = kn.call("wh.admin", "POST", f"/cycle-count/sessions/{SID}/roll-finalize", {"reason": "ulang ACC", "zero_cost_reason": "ulang"}, entity=ENT, quiet=True)
print("finalize ulang", c, str(o)[:200])
c, o = kn.call("wh.admin", "POST", f"/cycle-count/sessions/{SID}/reopen", {"reason": "buka ulang setelah ACC"}, entity=ENT, quiet=True)
print("reopen sesudah ACC", c, str(o)[:200])
