"""Alur L — daftar tugas masuk/putaway/opname: siapa melihat apa (gudang & PT) per peran, dengan konteks PT bawaan & 'all'."""
from collections import Counter
import kn

WH = {w["id"]: (w.get("code") or w["id"]) for w in kn.db.warehouses.find({}, {"_id": 0, "id": 1, "code": 1})}
SITE = {w["id"]: w.get("site_id") for w in kn.db.warehouses.find({}, {"_id": 0, "id": 1, "site_id": 1})}
SITEN = {s["id"]: s["name"] for s in kn.db.warehouse_sites.find({}, {"_id": 0})}
ENT = {e["id"]: e.get("code") or e.get("short_name") for e in kn.db.business_entities.find({}, {"_id": 0})}
USERS = ["warehouse.soreang", "warehouse.rancamalang", "warehouse", "wh.admin", "qc", "mdquality", "manager"]
EPS = [("/wms/tasks", None, lambda r: r, ("warehouse_id",)),
       ("/inbound/tasks", None, lambda r: r, ("warehouse_id",)),
       ("/inbound/qc/queue", None, lambda r: r, ("warehouse_id",)),
       ("/putaway-orders", None, lambda r: r.get("orders", []), ("from_warehouse_id", "to_warehouse_id")),
       ("/goods-receipts", None, lambda r: r.get("items", r) if isinstance(r, dict) else r, ("warehouse_id",)),
       ("/cycle-count/sessions", None, lambda r: r, ("warehouse_id",)),
       ("/registration/sessions", None, lambda r: r, ("warehouse_id",)),
       ("/inspections", {"limit": 200}, lambda r: r.get("items", r) if isinstance(r, dict) else r, ("warehouse_id",)),
       ("/transfers", None, lambda r: r.get("items", r) if isinstance(r, dict) else r, ("source_warehouse_id", "dest_warehouse_id"))]


def site_of(row, fields):
    return {SITEN.get(SITE.get(row.get(f)), "?") for f in fields if row.get(f)}


for u in USERS:
    user = kn.db.users.find_one({"email": f"{u}@kainnusantara.id"}, {"_id": 0, "role": 1, "location_site_ids": 1})
    mine = {SITEN.get(s) for s in user.get("location_site_ids") or []}
    print(f"\n### {u} ({user['role']}) lokasi={mine or 'semua'}")
    for ent in (None, "all"):
        for path, params, pick, fields in EPS:
            c, o = kn.call(u, "GET", path, params=params, entity=ent, quiet=True)
            if c != 200:
                print(f"  [{ent or 'bawaan'}] {path}: {c} {str(o)[:80]}")
                continue
            rows = pick(o) or []
            if not isinstance(rows, list):
                rows = []
            sites = Counter(s for r in rows if isinstance(r, dict) for s in site_of(r, fields))
            ents = Counter(ENT.get(r.get("entity_id") or r.get("owner_entity_id"), r.get("entity_id") or r.get("owner_entity_id")) for r in rows if isinstance(r, dict))
            out = {s: n for s, n in sites.items() if mine and s not in mine}
            print(f"  [{ent or 'bawaan'}] {path}: n={len(rows)} site={dict(sites)} PT={dict(ents)}" + (f"  ⚠ di luar lokasi: {out}" if out else ""))
