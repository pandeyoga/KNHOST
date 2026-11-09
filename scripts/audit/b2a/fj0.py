"""Seberapa banyak roll fisik per gudang yang TIDAK bisa masuk potret opname per roll (bin kosong / bin tak dikenal struktur)."""
import sys
from collections import Counter
sys.path.insert(0, "/app/backend")
import kn
from services.placement_rules import flatten_nodes

PHYS = ["available", "reserved", "committed", "picked", "packed", "quarantine", "blocked", "hold", "damaged"]
for wh in kn.db.warehouses.find({"site_id": {"$exists": True}}, {"_id": 0}):
    ids = {n["bin"]["id"] for n in flatten_nodes(wh)}
    q = {"warehouse_id": wh["id"], "status": {"$in": PHYS}, "length_remaining": {"$gt": 0}}
    tot = kn.db.inventory_rolls.count_documents(q)
    nob = kn.db.inventory_rolls.count_documents({**q, "$or": [{"bin_id": None}, {"bin_id": ""}, {"bin_id": {"$exists": False}}]})
    unk = Counter()
    for r in kn.db.inventory_rolls.find({**q, "bin_id": {"$nin": [None, ""] + list(ids)}}, {"_id": 0, "bin_id": 1}):
        unk[r["bin_id"]] += 1
    print(f"{wh.get('code'):14} bins_struktur={len(ids):4} roll_fisik={tot:6} tanpa_bin={nob:6} bin_tak_dikenal={sum(unk.values()):6} contoh={unk.most_common(3)}")
