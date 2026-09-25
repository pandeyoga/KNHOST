"""GRN Fase 0.7 — laporkan duplikat (supplier_id, supplier_sku) di `supplier_items` SEBELUM indeks unik dibuat.

Pemakaian: cd /app/backend && python ../scripts/check_supplier_item_duplicates.py
Keluar 1 bila ada duplikat (bereskan dulu — nonaktifkan/ubah kodenya — lalu restart backend
agar indeks `uq_supplier_sku` lahir).
"""
import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")

db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
rows = list(db.supplier_items.aggregate([
    {"$match": {"supplier_sku": {"$type": "string", "$gt": ""}}},
    {"$group": {"_id": {"supplier_id": "$supplier_id", "supplier_sku": "$supplier_sku"},
                "n": {"$sum": 1}, "ids": {"$push": "$id"}, "status": {"$push": "$status"}}},
    {"$match": {"n": {"$gt": 1}}},
]))
if not rows:
    print("OK — tidak ada duplikat (supplier_id, supplier_sku).")
    sys.exit(0)
print(f"DUPLIKAT: {len(rows)} pasangan")
for r in rows:
    k = r["_id"]
    print(f"  supplier={k['supplier_id']} kode={k['supplier_sku']} × {r['n']} → {list(zip(r['ids'], r['status']))}")
sys.exit(1)
