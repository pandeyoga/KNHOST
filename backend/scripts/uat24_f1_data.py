"""UAT 24 Okt — data fase F1 (P9 lokasi gudang). Idempoten.

Keputusan pemilik 24 Okt (usulan bawaan §4 ANALISIS_TEMUAN_UAT_23OKT.md):
* P9-K1 — lokasi bergudang tunggal (Soreang SRG-01, Jakarta WH-JKT): gudang itu MERANGKAP transit + simpan →
  diberi peran `central_inbound` + `transit` (tetap `storage`).
* P8-K2 — satuan lokasi = site. Tiap PT mendapat lokasi bawaan (`business_entities.default_site_id`) = lokasi gudang
  khusus PT itu, else Rancamalang (gudang bersama). Akun sales / Admin Sales yang belum punya lokasi diberi lokasi
  bawaan PT rumahnya (bisa diubah di Akun & Akses).
* P9-K3 — roll lama ber-stage `received_transit` yang sudah tersedia di gudang simpan diluruskan ke `stored`.

Pemakaian (di container backend): DB_NAME=<db> python scripts/uat24_f1_data.py [--dry-run]
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402

DRY = "--dry-run" in sys.argv
MERGED_SITES = ("Soreang", "Jakarta")     # lokasi bergudang tunggal → gudangnya merangkap penerimaan
SHARED_SITE = "Rancamalang"


async def main() -> None:
    print("DB:", os.environ.get("DB_NAME"), "(dry-run)" if DRY else "")
    sites = {s["name"]: s async for s in db.warehouse_sites.find({}, {"_id": 0, "id": 1, "name": 1})}
    # 1 — gudang tunggal lokasi merangkap penerimaan
    for name in MERGED_SITES:
        s = sites.get(name)
        if not s:
            print(f"  lokasi {name}: tidak ada — lewati")
            continue
        whs = await db.warehouses.find({"site_id": s["id"], "active": {"$ne": False}}, {"_id": 0}).to_list(20)
        if len(whs) != 1:
            print(f"  lokasi {name}: {len(whs)} gudang aktif — tidak diubah (bukan gudang tunggal)")
            continue
        w = whs[0]
        roles = sorted(set(w.get("roles") or []) | {"storage", "transit", "central_inbound"})
        if roles != sorted(w.get("roles") or []):
            print(f"  {w['code']}: peran {w.get('roles')} → {roles}")
            if not DRY:
                await db.warehouses.update_one({"id": w["id"]}, {"$set": {"roles": roles, "updated_at": now_iso()}})
    # 2 — lokasi bawaan PT
    async for ent in db.business_entities.find({}, {"_id": 0, "id": 1, "doc_prefix": 1, "default_site_id": 1}):
        if ent.get("default_site_id"):
            print(f"  PT {ent.get('doc_prefix')}: lokasi bawaan sudah ada")
            continue
        ded = await db.warehouses.find_one({"entity_ids": ent["id"], "sharing_mode": "dedicated", "active": {"$ne": False},
                                            "site_id": {"$nin": [None, ""]}}, {"_id": 0, "site_id": 1})
        sid = (ded or {}).get("site_id") or (sites.get(SHARED_SITE) or {}).get("id", "")
        name = next((n for n, s in sites.items() if s["id"] == sid), sid)
        print(f"  PT {ent.get('doc_prefix')}: lokasi bawaan → {name}")
        if sid and not DRY:
            await db.business_entities.update_one({"id": ent["id"]}, {"$set": {"default_site_id": sid, "updated_at": now_iso()}})
    # 3 — akun sales / Admin Sales tanpa lokasi → lokasi bawaan PT rumah
    ents = {e["id"]: e async for e in db.business_entities.find({}, {"_id": 0, "id": 1, "default_site_id": 1})}
    async for u in db.users.find({"role": {"$in": ["sales", "sales_admin"]}},
                                 {"_id": 0, "id": 1, "email": 1, "home_entity_id": 1, "entity_ids": 1, "allowed_entity_ids": 1,
                                  "location_site_ids": 1}):
        if u.get("location_site_ids"):
            continue
        home = u.get("home_entity_id") or (u.get("entity_ids") or u.get("allowed_entity_ids") or [""])[0]
        sid = (ents.get(home) or {}).get("default_site_id")
        if not sid and DRY:
            ded = await db.warehouses.find_one({"entity_ids": home, "sharing_mode": "dedicated", "site_id": {"$nin": [None, ""]}},
                                               {"_id": 0, "site_id": 1})
            sid = (ded or {}).get("site_id") or (sites.get(SHARED_SITE) or {}).get("id", "")
        name = next((n for n, s in sites.items() if s["id"] == sid), sid)
        print(f"  akun {u['email']}: lokasi → {name}")
        if sid and not DRY:
            await db.users.update_one({"id": u["id"]}, {"$set": {"location_site_ids": [sid], "updated_at": now_iso()}})
    # 4 — roll lama received_transit yang sudah tersedia di gudang ber-peran simpan → stored
    store_wh = [w["id"] async for w in db.warehouses.find({"roles": "storage"}, {"_id": 0, "id": 1})]
    q = {"journey.stage": "received_transit", "status": {"$in": ["available", "reserved"]}, "warehouse_id": {"$in": store_wh}}
    n = await db.inventory_rolls.count_documents(q)
    print(f"  roll received_transit tersedia di gudang simpan: {n} → stored")
    if n and not DRY:
        await db.inventory_rolls.update_many(q, {"$set": {"journey.stage": "stored", "journey.updated_at": now_iso(),
                                                          "journey.note": "diluruskan UAT 24 Okt (P9-K3)"}})
    print("selesai")


if __name__ == "__main__":
    asyncio.run(main())
