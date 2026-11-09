"""Alur A — PO KSC → Rancamalang (mode legacy, jalur HP petugas): terima → selesai → karantina+SPK → putus SPK
→ draf PA → verifikasi label → terbit → kirim → trip 1 → trip 2 → simpan ke bin. Potret DB tiap langkah."""
import json
import kn

po = json.load(open("/tmp/b2a/po_a.json"))
PO, PID = po["id"], "prod_97ef39b63081"
W = "warehouse.rancamalang"
task = kn.db.wms_tasks.find_one({"po_id": PO}, {"_id": 0})
TID = task["id"]
R = {}


def stp(label):
    rolls = kn.snap("inventory_rolls", {"po_id": PO}, ["id", "roll_no", "status", "warehouse_id", "bin_id", "length_initial",
                                                      "length_remaining", "unit", "grade", "journey", "qc_task_id",
                                                      "rfid_tag_id", "active_movement", "lot", "owner_entity_id",
                                                      "unit_cost", "inspection", "hold"])
    t = kn.db.wms_tasks.find_one({"id": TID}, {"_id": 0, "status": 1, "received_qty": 1, "quantity": 1, "qty_rolls": 1,
                                               "qc_status": 1, "saga_lock": 1})
    p = kn.db.purchase_orders.find_one({"id": PO}, {"_id": 0, "status": 1, "items.received_qty": 1, "items.received_rolls": 1})
    rid = [r["id"] for r in rolls]
    mv = kn.snap("inventory_movements", {"roll_id": {"$in": rid}}, ["movement_type", "warehouse_id", "quantity", "roll_id"])
    je = kn.snap("journal_entries", {"$or": [{"source_id": {"$regex": TID}}, {"source_id": PO}]},
                 ["source_type", "source_id", "status", "total_debit", "description"])
    bal = kn.snap("inventory_balances", {"product_id": PID, "warehouse_id": {"$in": list({r["warehouse_id"] for r in rolls})}},
                  ["warehouse_id", "owner_entity_id", "on_hand", "available", "quarantine_qty", "in_transit_qty",
                   "reserved_qty", "blocked_qty", "quantity", "available_qty"])
    pas = kn.snap("putaway_orders", {"items.roll_id": {"$in": rid}}, ["id", "pa_number", "status", "to_warehouse_id",
                                                                      "to_warehouse_name", "purpose", "item_count",
                                                                      "arrived_count", "pending_count", "btg_number",
                                                                      "auto", "items"])
    spk = kn.snap("inspections", {"task_id": TID}, ["id", "number", "kind", "status", "md_only", "decision", "lines"])
    aud = kn.snap("audit_logs", {"$or": [{"entity_id": TID}, {"entity_id": PO}, {"entity_id": {"$in": [x["id"] for x in pas]}}]},
                  ["action", "entity_type", "user", "timestamp"])
    R[label] = {"task": t, "po": p, "rolls": rolls, "mov": mv, "je": je, "bal": bal, "pa": pas, "spk": spk,
                "aud": [a["action"] for a in aud], "counts": kn.counts(kn.WATCH)}
    print(f"\n=== {label} :: task={t} po={p}")
    print(f"  rolls={[(r['roll_no'], r['status'], r['warehouse_id'][-6:], r.get('bin_id'), r['length_remaining'], (r.get('journey') or {}).get('stage'), r.get('rfid_tag_id')) for r in rolls]}")
    print(f"  mov={[(m['movement_type'], m['warehouse_id'][-6:], m['quantity']) for m in mv]}")
    print(f"  je={[(j['source_type'], j['status'], j.get('total_debit')) for j in je]}")
    print(f"  bal={bal}")
    print(f"  pa={[(x['pa_number'], x['status'], x.get('to_warehouse_name'), x.get('purpose'), x.get('item_count'), x.get('arrived_count'), x.get('btg_number')) for x in pas]}")
    print(f"  spk={[(s['number'], s['kind'], s['status'], s.get('md_only'), s.get('decision'), len(s.get('lines') or [])) for s in spk]}")
    print(f"  audit={R[label]['aud']}")


stp("0_awal")
# 1) siapa melihat tugas ini?
for who, ent in [(W, None), (W, "ent_ksc"), (W, "all"), ("warehouse.soreang", None), ("warehouse", None),
                 ("wh.admin", None), ("wh.admin", "all")]:
    c, rows = kn.call(who, "GET", "/wms/tasks", entity=ent, quiet=True)
    ids = [t["id"] for t in rows] if c == 200 and isinstance(rows, list) else []
    ents = sorted({t.get("entity_id") for t in rows}) if ids else []
    whs = sorted({t.get("warehouse_name") for t in rows if t.get("flow_type") == "inbound"}) if ids else []
    print(f"LIST {who} X-Entity={ent}: code={c} n={len(ids)} lihat_tugas_ini={TID in ids} PT={ents} gudang_inbound={whs[:6]}")
# 2) Terima (HP): qty saja
c, o = kn.call(W, "POST", f"/inbound/tasks/{TID}/scan-receive", {"product_id": PID, "actual_qty": 300}, entity="ent_ksc")
stp("1_scan_receive")
# 3) Selesai terima (HP): lot + dye saja
c, o = kn.call(W, "POST", f"/inbound/tasks/{TID}/complete", {"supplier_lot": "SLOT-A1", "dye_lot": "DYE-A1"}, entity="ent_ksc")
R["complete_resp"] = o
stp("2_complete")
json.dump(R, open("/tmp/b2a/fa_state.json", "w"), default=str)
