"""L00 (LN-003) — snapshot baseline READ-ONLY + dry-run migrasi: stok per owner/lokasi/satuan,
komitmen, AR/AP, identitas roll, record yatim/duplikat dan saldo tidak seimbang. Tidak menulis DB.

Pakai:  python scripts/l00_baseline_snapshot.py [--out path.json]
"""
import argparse
import json
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timezone

from pymongo import MongoClient

EPS = 0.01
OPEN_ROLL = ("available", "reserved", "subcon", "in_transit_sales", "in_transit_transfer")


def _db():
    url = os.environ.get("MONGO_URL") or "mongodb://localhost:27017"
    name = os.environ.get("DB_NAME") or "test_database"
    return MongoClient(url)[name]


def _sha() -> str:
    try:
        return subprocess.check_output(["git", "-C", "/app", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return ""


def stock(db):
    rows = defaultdict(lambda: {"qty": 0.0, "rolls": 0})
    for r in db.inventory_rolls.find({"status": {"$in": list(OPEN_ROLL)}},
                                     {"_id": 0, "owner_entity_id": 1, "warehouse_id": 1, "unit": 1,
                                      "status": 1, "length_remaining": 1}):
        k = (r.get("owner_entity_id") or "", r.get("warehouse_id") or "", r.get("unit") or "", r.get("status"))
        rows[k]["qty"] += float(r.get("length_remaining") or 0)
        rows[k]["rolls"] += 1
    return [{"owner": k[0], "warehouse": k[1], "unit": k[2], "status": k[3],
             "qty": round(v["qty"], 2), "rolls": v["rolls"]} for k, v in sorted(rows.items())]


def commitments(db):
    out = defaultdict(float)
    for m in db.material_reservations.find({"status": "active"}, {"_id": 0, "entity_id": 1, "qty": 1,
                                                                   "quantity": 1, "unit": 1}):
        out[(m.get("entity_id") or "", m.get("unit") or "")] += float(m.get("qty") or m.get("quantity") or 0)
    return [{"entity": k[0], "unit": k[1], "active_material_reserved": round(v, 2)} for k, v in sorted(out.items())]


def ar_ap(db):
    ar = defaultdict(lambda: {"so": 0, "grand_total": 0.0, "paid": 0.0, "unpaid_so": 0, "partial_so": 0})
    for s in db.sales_orders.find({"status": {"$nin": ["cancelled", "draft"]}},
                                  {"_id": 0, "entity_id": 1, "grand_total": 1, "paid_total": 1}):
        e = ar[s.get("entity_id") or ""]
        g, p = float(s.get("grand_total") or 0), float(s.get("paid_total") or 0)
        e["so"] += 1; e["grand_total"] += g; e["paid"] += p
        e["unpaid_so"] += int(p <= EPS and g > EPS); e["partial_so"] += int(EPS < p < g - EPS)
    ap = defaultdict(lambda: {"bills": 0, "grand_total": 0.0, "outstanding": 0.0})
    for b in db.vendor_bills.find({}, {"_id": 0, "entity_id": 1, "grand_total": 1, "outstanding": 1}):
        e = ap[b.get("entity_id") or ""]
        e["bills"] += 1; e["grand_total"] += float(b.get("grand_total") or 0)
        e["outstanding"] += float(b.get("outstanding") or 0)
    rnd = lambda d: {k: {kk: (round(vv, 2) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in d.items()}
    return {"ar_by_entity": rnd(ar), "ap_by_entity": rnd(ap)}


def integrity(db):
    pids = set(db.products.distinct("id"))
    whs = set(db.warehouses.distinct("id"))
    ents = set(db.business_entities.distinct("id"))
    rolls = list(db.inventory_rolls.find({}, {"_id": 0, "id": 1, "roll_no": 1, "product_id": 1, "warehouse_id": 1,
                                              "owner_entity_id": 1, "rfid_tag_id": 1, "status": 1,
                                              "length_remaining": 1, "unit": 1}))
    orphan = [r["id"] for r in rolls if r.get("product_id") not in pids or r.get("warehouse_id") not in whs
              or r.get("owner_entity_id") not in ents]
    dup_tag = defaultdict(list)
    dup_no = defaultdict(list)
    for r in rolls:
        if r.get("rfid_tag_id") and r.get("status") in OPEN_ROLL:
            dup_tag[r["rfid_tag_id"]].append(r["id"])
        if r.get("roll_no"):
            dup_no[(r.get("owner_entity_id"), r["roll_no"])].append(r["id"])
    neg = [r["id"] for r in rolls if float(r.get("length_remaining") or 0) < -EPS]
    # Saldo proyeksi vs Σ roll on-hand per (produk, gudang, owner)
    sums = defaultdict(float)
    for r in rolls:
        if r.get("status") in ("available", "reserved"):
            sums[(r["product_id"], r["warehouse_id"], r["owner_entity_id"])] += float(r.get("length_remaining") or 0)
    mismatch = []
    for b in db.inventory_balances.find({}, {"_id": 0, "product_id": 1, "warehouse_id": 1, "owner_entity_id": 1,
                                             "available_qty": 1, "reserved_qty": 1}):
        k = (b.get("product_id"), b.get("warehouse_id"), b.get("owner_entity_id"))
        bal = float(b.get("available_qty") or 0) + float(b.get("reserved_qty") or 0)
        if abs(bal - sums.pop(k, 0.0)) > EPS:
            mismatch.append({"key": list(k), "balance": round(bal, 2)})
    mismatch += [{"key": list(k), "balance": None, "rolls_qty": round(v, 2)} for k, v in sums.items() if v > EPS]
    unbalanced_je = [j.get("number") or j.get("id") for j in db.journal_entries.find(
        {}, {"_id": 0, "id": 1, "number": 1, "total_debit": 1, "total_credit": 1})
        if abs(float(j.get("total_debit") or 0) - float(j.get("total_credit") or 0)) > EPS]
    return {
        "rolls_total": len(rolls), "orphan_rolls": orphan[:50], "orphan_rolls_count": len(orphan),
        "duplicate_active_epc": {k: v for k, v in dup_tag.items() if len(v) > 1},
        "duplicate_roll_no_per_owner": {f"{k[0]}|{k[1]}": v for k, v in dup_no.items() if len(v) > 1},
        "negative_qty_rolls": neg,
        "balance_vs_roll_mismatch": mismatch[:50], "balance_vs_roll_mismatch_count": len(mismatch),
        "unbalanced_journal_entries": unbalanced_je,
    }


def master(db):
    return {
        "grades_on_rolls": sorted(x for x in db.inventory_rolls.distinct("grade") if x),
        "stages_on_products": sorted(x for x in db.products.distinct("stage") if x),
        "roles_on_users": sorted(x for x in db.users.distinct("role") if x),
        "custom_roles": db.custom_roles.count_documents({}) if "custom_roles" in db.list_collection_names() else 0,
        "restock_source_mapped_templates": db.product_templates.count_documents({"restock_source.mode": {"$in": ["supplier", "makloon", "both"]}}),
        "customer_grade_rules": db.customer_grade_rules.count_documents({}),
        "rolls_with_supplier_lot": db.inventory_rolls.count_documents({"dye_lot": {"$nin": ["", None]}}),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    db = _db()
    data = {"generated_at": datetime.now(timezone.utc).isoformat(), "commit": _sha(), "read_only": True,
            "stock": stock(db), "commitments": commitments(db), **ar_ap(db),
            "integrity_dry_run": integrity(db), "master": master(db)}
    txt = json.dumps(data, indent=1, ensure_ascii=False)
    if a.out:
        open(a.out, "w").write(txt)
    i = data["integrity_dry_run"]
    print(json.dumps({"rolls": i["rolls_total"], "orphan": i["orphan_rolls_count"],
                      "dup_epc": len(i["duplicate_active_epc"]), "dup_roll_no": len(i["duplicate_roll_no_per_owner"]),
                      "neg": len(i["negative_qty_rolls"]), "balance_mismatch": i["balance_vs_roll_mismatch_count"],
                      "unbalanced_je": len(i["unbalanced_journal_entries"]), "master": data["master"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
