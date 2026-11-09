import kn

g = kn.db.goods_receipts.find_one({"dn.number": "SJ-B2A-G4"}, {"_id": 0})
G = g["id"]
c, o = kn.call("wh.admin", "POST", f"/goods-receipts/{G}/cancel", {"expected_version": g["version"], "reason": "SJ salah kirim, barang dikembalikan"}, entity="ent_ksc", quiet=True)
print("G4 cancel GRN", c, (o or {}).get("status") if isinstance(o, dict) else o)
t = kn.db.wms_tasks.find_one({"grn_ids": G}, {"_id": 0}) or kn.db.wms_tasks.find_one({"id": g["lines"][0]["target"]["task_id"]}, {"_id": 0})
print("G4 rolls", kn.snap("inventory_rolls", {"grn_id": G}, ["roll_no", "status"]), "task", {k: t.get(k) for k in ("status", "grn_active_id", "received_qty", "qty_rolls_scanned")})
print("G4 audit", [a["action"] for a in kn.snap("audit_logs", {"entity_id": G}, ["action"])])
