#!/usr/bin/env python3
"""FIX-5 — skenario KESETARAAN terima transfer & tiba Putaway Order (sebelum vs sesudah batch).

Menjalankan layanan SUNGGUHAN (`transfer_receipt_service.receive`, `putaway_arrival_service.confirm_arrival_trip`,
`close_remaining`) pada data uji deterministik (`*_EQ5_*`), lalu menulis keadaan DB yang dihasilkan dalam bentuk
ternormalisasi (tanpa waktu/id acak) ke JSON. Jalankan di kode dasar dan di kode baru pada salinan DB yang sama lalu
bandingkan (`diff`): harus identik.

    cd /app/backend && python /app/scripts/fix5_equivalence.py --confirm-db test_database --out /tmp/eq_base.json

Kasus: terima per id / nomor roll / EPC, baris ganda dalam & antar panggilan, kode asing, rusak + keterangan, roll
berkomitmen SO (alokasi & tugas ambil ikut pindah), aturan gudang tujuan (ditolak → pengecualian supervisor →
ditahan); PA: trip gate (EPC asing & ganda), trip yang sama diulang (duplikat), trip handheld sebagian tumpang tindih,
tutup sisa (kembali ke transit), PA ke gedung beraturan grade (pengecualian).
Keamanan: hanya MONGO_URL localhost/127.0.0.1 dan `--confirm-db` = DB_NAME; data uji dihapus sebelum & sesudah.
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

ENT = "ent_ksc"
P = "EQ5"
WH = {k: f"wh_{P}_{k}" for k in ("src", "dst", "rule", "transit", "store", "store_rule")}
SITE = f"site_{P}"
DROP = {"_id", "updated_at", "created_at", "at", "date", "timestamp", "rebuild_ticket", "rebuild_applied",
        "last_trip_at", "confirmed_at", "resolved_at", "dispatched_at", "arrived_at", "claimed_at", "_saga",
        "cancelled_at", "completed_at", "returned_at", "btg_number", "pending_demand_qty", "on_order_qty",
        "incoming_qty", "atp_qty", "exception_id"}
GEN_ID = re.compile(r"^(mov|tex|trc|alloc|wms|patrip|bal|pad|pa)_[0-9a-f]{6,}$")
TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")


def guard(args):
    host = urlparse(os.environ.get("MONGO_URL", "")).hostname
    if host not in ("localhost", "127.0.0.1"):
        sys.exit(f"Ditolak: MONGO_URL harus localhost (sekarang {host!r}).")
    if args.confirm_db != os.environ.get("DB_NAME"):
        sys.exit("Ditolak: --confirm-db wajib sama dengan DB_NAME.")


def norm(v):
    if isinstance(v, dict):
        return {k: norm(x) for k, x in sorted(v.items()) if k not in DROP and not k.endswith("_at")}
    if isinstance(v, list):
        return [norm(x) for x in v]
    if isinstance(v, str):
        if GEN_ID.match(v):
            return "<id>"
        if TS.match(v):
            return "<ts>"
    if isinstance(v, float):
        return round(v, 4)
    return v


async def purge(db):
    rx = {"$regex": f"_{P}_"}
    for c in ("inventory_rolls", "rfid_tags", "warehouse_transfers", "putaway_orders", "sales_orders", "wms_tasks",
              "inventory_lots", "warehouses", "warehouse_sites"):
        await db[c].delete_many({"id": rx})
    await db.inventory_movements.delete_many({"roll_id": rx})
    await db.inventory_balances.delete_many({"warehouse_id": rx})
    await db.warehouse_sites.delete_many({"id": SITE})
    await db.wms_tasks.delete_many({"order_id": rx})   # tugas pindahan (id acak) dari terima transfer


async def seed(db):
    prods = [p["id"] for p in await db.products.find({"base_unit": "meter", "status": {"$ne": "inactive"}},
                                                     {"_id": 0, "id": 1}).sort("id", 1).to_list(3)]
    assert len(prods) == 3, "data acuan butuh 3 produk meter"
    await db.warehouse_sites.insert_one({"id": SITE, "name": f"Situs {P}", "code": P})
    for k, roles, rules in (("src", ["storage"], None), ("dst", ["storage"], None),
                            ("rule", ["storage"], {"mode": "restrict", "grades": ["A"]}),
                            ("transit", ["transit", "receiving"], None), ("store", ["storage"], None),
                            ("store_rule", ["storage"], {"mode": "restrict", "grades": ["A"]})):
        await db.warehouses.insert_one({"id": WH[k], "name": f"Uji {P} {k}", "code": f"{P}{k.upper()}", "roles": roles,
                                        "site_id": SITE, "sharing_mode": "shared", "active": True,
                                        "gate_config": {"has_gate": False},
                                        **({"storage_rules": rules} if rules else {})})
    for j, pid in enumerate(prods):
        await db.inventory_lots.insert_one({"id": f"lot_{P}_{j}", "lot_number": f"L-{P}-{j}", "product_id": pid,
                                            "owner_entity_id": ENT, "lot_status": "active", "roll_count": 0})
    return prods


def roll_doc(i, pid, j, wh, status, **extra):
    rid, tid = f"roll_{P}_{i:04d}", f"tag_{P}_{i:04d}"
    return ({"id": rid, "roll_no": f"{P}R{i:04d}", "product_id": pid, "warehouse_id": wh, "owner_entity_id": ENT,
             "status": status, "length_remaining": float(30 + i % 7), "length_initial": float(30 + i % 7),
             "unit": "meter", "grade": extra.pop("grade", "A"), "lot": f"L-{P}-{j}", "lot_id": f"lot_{P}_{j}",
             "rfid_tag_id": tid, "bin_id": None, "length_reserved": 0, "length_reservations": [],
             "journey": {"stage": "tag_verified", "verified_tag_id": tid, "routing": "store"}, **extra},
            {"id": tid, "epc": f"E2{P}{i:020X}", "roll_id": rid, "status": "active", "warehouse_id": wh})


async def make_transfer(db, prods, tid, code, dest, idx, so=None, grade_b=()):
    rolls, tags, items = [], [], {}
    for n, i in enumerate(idx):
        j = i % 3
        if so and n < so["n"]:
            extra = {"reserved_ref": {"type": "sales_order", "id": so["id"]},
                     "transfer_ref": {"type": "wh_transfer", "id": tid, "so_id": so["id"]},
                     "transfer_prior_status": "committed"}
        else:
            extra = {"reserved_ref": {"type": "wh_transfer", "id": tid}, "transfer_prior_status": "available"}
        r, t = roll_doc(i, prods[j], j, WH["src"], "in_transit_transfer", grade="B" if i in grade_b else "A", **extra)
        rolls.append(r)
        tags.append(t)
        items.setdefault(prods[j], []).append({"roll_id": r["id"], "roll_no": r["roll_no"], "length": r["length_remaining"],
                                               "lot": r["lot"], **({"committed_so": so["id"]} if "transfer_ref" in r else {})})
    await db.inventory_rolls.insert_many(rolls)
    await db.rfid_tags.insert_many(tags)
    await db.warehouse_transfers.insert_one({
        "id": tid, "code": code, "status": "dispatched", "transfer_kind": "warehouse", "source_warehouse_id": WH["src"],
        "dest_warehouse_id": dest, "owner_entity_id": ENT, "entity_id": ENT,
        "items": [{"product_id": pid, "unit": "meter", "rolls": rs} for pid, rs in items.items()]})
    return rolls, tags


async def make_so(db, prods, so_id, rolls):
    allocs, tasks = [], []
    by_p = {}
    for r in rolls:
        by_p.setdefault(r["product_id"], []).append(r)
    for k, (pid, rs) in enumerate(sorted(by_p.items())):
        aid = f"alloc_{P}_{k}"
        q = round(sum(r["length_remaining"] for r in rs), 2)
        allocs.append({"id": aid, "product_id": pid, "warehouse_id": WH["src"], "warehouse_name": "src",
                       "owner_entity_id": ENT, "quantity": q, "rolls": [{"roll_id": r["id"], "length": r["length_remaining"]}
                                                                        for r in rs], "status": "allocated"})
        tasks.append({"id": f"wms_{P}_{k}", "allocation_id": aid, "flow_type": "outbound", "status": "created",
                      "quantity": q, "order_id": so_id, "product_id": pid, "warehouse_id": WH["src"], "entity_id": ENT})
    await db.sales_orders.insert_one({"id": so_id, "number": f"SO-{P}", "status": "confirmed", "entity_id": ENT,
                                      "allocations": allocs})
    await db.wms_tasks.insert_many(tasks)


async def make_pa(db, prods, pa_id, number, src, dst, idx, grade_b=()):
    rolls, tags, items = [], [], []
    for i in idx:
        j = i % 3
        r, t = roll_doc(i, prods[j], j, src, "in_transit_transfer", grade="B" if i in grade_b else "A",
                        active_movement={"type": "putaway", "id": pa_id, "number": number})
        r["journey"]["stage"] = "putaway_in_transit"
        rolls.append(r)
        tags.append(t)
        items.append({"roll_id": r["id"], "roll_no": r["roll_no"], "epc": t["epc"], "sku": "", "product_name": "",
                      "category": "", "grade": r["grade"], "product_id": r["product_id"], "lot": r["lot"],
                      "qty": r["length_remaining"], "unit": "meter", "status": "pending"})
    await db.inventory_rolls.insert_many(rolls)
    await db.rfid_tags.insert_many(tags)
    await db.putaway_orders.insert_one({"id": pa_id, "pa_number": number, "from_warehouse_id": src, "to_warehouse_id": dst,
                                        "owner_entity_id": ENT, "items": items, "status": "in_transit", "purpose": "storage",
                                        "btg_number": None, "arrival_trips": [], "dispatched_at": "2026-11-09T00:00:00+00:00"})
    return rolls, tags


async def dump(db, out):
    rx = {"$regex": f"_{P}_"}
    keep_roll = ("id", "status", "warehouse_id", "bin_id", "reserved_ref", "transfer_ref", "transfer_prior_status",
                 "last_transfer", "journey", "hold", "last_pa_landed", "active_movement", "returned_from_transfer")
    out["rolls"] = [norm({k: r.get(k) for k in keep_roll}) for r in
                    await db.inventory_rolls.find({"id": rx}, {"_id": 0}).sort("id", 1).to_list(None)]
    out["tags"] = [norm(t) for t in await db.rfid_tags.find({"id": rx}, {"_id": 0}).sort("id", 1).to_list(None)]
    mv = await db.inventory_movements.find({"roll_id": rx}, {"_id": 0}).to_list(None)
    out["movements"] = sorted((norm(m) for m in mv), key=lambda m: json.dumps(m, sort_keys=True))
    out["balances"] = [norm(b) for b in await db.inventory_balances.find({"warehouse_id": rx}, {"_id": 0})
                       .sort([("warehouse_id", 1), ("product_id", 1)]).to_list(None)]
    out["lots"] = [norm(x) for x in await db.inventory_lots.find({"id": rx}, {"_id": 0}).sort("id", 1).to_list(None)]
    out["transfers"] = [norm(x) for x in await db.warehouse_transfers.find({"id": rx}, {"_id": 0}).sort("id", 1).to_list(None)]
    out["putaway_orders"] = [norm(x) for x in await db.putaway_orders.find({"id": rx}, {"_id": 0}).sort("id", 1).to_list(None)]
    out["sales_orders"] = [norm(x) for x in await db.sales_orders.find({"id": rx}, {"_id": 0}).sort("id", 1).to_list(None)]
    tasks = await db.wms_tasks.find({"$or": [{"id": rx}, {"order_id": rx}]}, {"_id": 0}).to_list(None)
    out["wms_tasks"] = sorted((norm(t) for t in tasks), key=lambda t: json.dumps(t, sort_keys=True))


async def big(db, prods, n, out):
    """Hanya ukur waktu: terima transfer N roll (per 500 baris, seperti pekerja gate) + satu trip PA N roll."""
    from schemas import TransferReceiveIn, TransferReceiveLine
    from services import putaway_arrival_service as arr
    from services import transfer_receipt_service as trs
    actor = {"id": f"u_{P}", "name": f"Petugas {P}", "role": "warehouse"}
    tid = f"trf_{P}_big"
    rolls, _ = await make_transfer(db, prods, tid, f"TRF-{P}-BIG", WH["dst"], range(10000, 10000 + n))
    t0 = time.perf_counter()
    for i in range(0, n, 500):
        t = await db.warehouse_transfers.find_one({"id": tid}, {"_id": 0})
        await trs.receive(t, TransferReceiveIn(lines=[TransferReceiveLine(roll_id=r["id"]) for r in rolls[i:i + 500]]), actor)
    out["timing_ms"][f"transfer_{n}"] = round((time.perf_counter() - t0) * 1000, 1)
    pa = f"pa_{P}_big"
    _, tags = await make_pa(db, prods, pa, f"PA-{P}-BIG", WH["transit"], WH["store"], range(20000, 20000 + n))
    t0 = time.perf_counter()
    res = await arr.confirm_arrival_trip(pa, [t["epc"] for t in tags], {"type": "gate", "passage_id": f"pas_{P}_big"}, actor)
    out["timing_ms"][f"putaway_{n}"] = round((time.perf_counter() - t0) * 1000, 1)
    out["big"] = {"transfer_status": (await db.warehouse_transfers.find_one({"id": tid}, {"_id": 0, "status": 1}))["status"],
                  "pa_status": res.get("status"), "pa_arrived": res.get("arrived_count")}


async def main(args):
    from db import db
    from schemas import TransferReceiveIn, TransferReceiveLine
    from services import putaway_arrival_service as arr
    from services import transfer_receipt_service as trs
    await purge(db)
    prods = await seed(db)
    if args.big:
        out = {"timing_ms": {}}
        await big(db, prods, args.big, out)
        await purge(db)
        print(json.dumps(out))
        return
    out = {"calls": [], "timing_ms": {}}
    actor = {"id": f"u_{P}", "name": f"Petugas {P}", "role": "warehouse"}
    sup = {"id": f"u_{P}_sup", "name": f"Supervisor {P}", "role": "warehouse_admin"}

    async def recv(tid, lines, who, label, **kw):
        t = await db.warehouse_transfers.find_one({"id": tid}, {"_id": 0})
        body = TransferReceiveIn(lines=[TransferReceiveLine(**ln) for ln in lines], **kw)
        t0 = time.perf_counter()
        res = await trs.receive(t, body, who)
        out["timing_ms"][label] = round((time.perf_counter() - t0) * 1000, 1)
        out["calls"].append({"label": label, "transfer_status": res["transfer_status"],
                             "results": norm(res["results"]), "counts": res["summary"]["counts"],
                             "open_exceptions": res["summary"]["open_exceptions"],
                             "putaway_draft": bool(res.get("putaway_draft"))})

    # ── transfer 1: 250 roll, 20 berkomitmen SO ─────────────────────────────────────────────
    t1 = f"trf_{P}_1"
    rolls, tags = await make_transfer(db, prods, t1, f"TRF-{P}-1", WH["dst"], range(0, 250),
                                      so={"id": f"so_{P}_1", "n": 20})
    await make_so(db, prods, f"so_{P}_1", rolls[:20])
    l1 = []
    for i in range(0, 150):
        if 30 <= i < 35:
            l1.append({"code": rolls[i]["roll_no"]})
        elif 35 <= i < 40:
            l1.append({"code": tags[i]["epc"]})
        elif i == 41:
            l1.append({"roll_id": rolls[i]["id"], "outcome": "damaged", "note": "Robek di ujung roll"})
        else:
            l1.append({"roll_id": rolls[i]["id"]})
    l1 += [{"roll_id": rolls[3]["id"]}, {"code": f"{P}-TIDAK-ADA"}, {"code": rolls[5]["roll_no"]}]
    await recv(t1, l1, actor, "t1_call1")
    l2 = [{"roll_id": r["id"]} for r in rolls[150:]] + [{"roll_id": rolls[0]["id"]}, {"roll_id": rolls[150]["id"]}]
    await recv(t1, l2, actor, "t1_call2")
    # ── transfer 2: aturan grade di tujuan → ditolak lalu pengecualian supervisor ────────────
    t2 = f"trf_{P}_2"
    idx2 = list(range(300, 330))
    rolls2, _ = await make_transfer(db, prods, t2, f"TRF-{P}-2", WH["rule"], idx2, grade_b=set(idx2[::3]))
    await recv(t2, [{"roll_id": r["id"]} for r in rolls2], actor, "t2_call1")
    await recv(t2, [{"roll_id": r["id"]} for r in rolls2 if r["grade"] == "B"], sup, "t2_call2_override",
               rule_exception_reason="Pengecualian uji kesetaraan FIX-5")
    # ── PA 1: trip gate, trip ulang, trip handheld, tutup sisa ───────────────────────────────
    pa1 = f"pa_{P}_1"
    _, ptags = await make_pa(db, prods, pa1, f"PA-{P}-1", WH["transit"], WH["store"], range(400, 620))
    epcs = [t["epc"] for t in ptags]

    async def trip(label, coro):
        t0 = time.perf_counter()
        res = await coro
        out["timing_ms"][label] = round((time.perf_counter() - t0) * 1000, 1)
        trip_ = res.get("trip") or {}
        out["calls"].append({"label": label, "status": res.get("status"), "duplicate_trip": res.get("duplicate_trip"),
                             "trip": norm({k: trip_.get(k) for k in ("arrived_roll_nos", "already_roll_nos", "unknown_epcs",
                                                                       "failed_roll_nos", "trip_no", "source")}),
                             "counts": {k: res.get(k) for k in ("arrived_count", "pending_count", "exception_count",
                                                                 "returned_count")}})

    gate = {"type": "gate", "passage_id": f"pas_{P}_1", "device_id": f"dev_{P}"}
    await trip("pa1_trip_gate", arr.confirm_arrival_trip(pa1, epcs[:120] + ["E2FFFF00000000000000DEAD", epcs[5]], gate, actor))
    await trip("pa1_trip_gate_repeat", arr.confirm_arrival_trip(pa1, epcs[:120], gate, actor))
    await trip("pa1_trip_handheld", arr.confirm_arrival_trip(pa1, epcs[100:200], {"type": "handheld",
                                                                                  "client_trip_id": f"ht_{P}_2"}, actor))
    t0 = time.perf_counter()
    res = await arr.close_remaining(pa1, "return_transit", "Sisa roll kembali ke transit (uji kesetaraan)", None, actor)
    out["timing_ms"]["pa1_close_remaining"] = round((time.perf_counter() - t0) * 1000, 1)
    out["calls"].append({"label": "pa1_close_remaining", "status": res.get("status"),
                         "closed": norm(res.get("closed_remaining"))})
    # ── PA 2: tujuan beraturan grade A → roll grade B jadi pengecualian ───────────────────────
    pa2 = f"pa_{P}_2"
    idx_pa2 = list(range(700, 730))
    _, ptags2 = await make_pa(db, prods, pa2, f"PA-{P}-2", WH["transit"], WH["store_rule"], idx_pa2, grade_b=set(idx_pa2[::4]))
    await trip("pa2_trip_gate", arr.confirm_arrival_trip(pa2, [t["epc"] for t in ptags2],
                                                         {"type": "gate", "passage_id": f"pas_{P}_2"}, actor))
    await dump(db, out)
    if not args.keep:
        await purge(db)
    Path(args.out).write_text(json.dumps(out, indent=1, sort_keys=True, ensure_ascii=False))
    print(json.dumps(out["timing_ms"]))
    print(f"rolls {len(out['rolls'])} · movements {len(out['movements'])} · balances {len(out['balances'])} → {args.out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm-db", required=True)
    ap.add_argument("--out", default="/tmp/fix5_equivalence.json")
    ap.add_argument("--keep", action="store_true", help="jangan hapus data uji (untuk diperiksa)")
    ap.add_argument("--big", type=int, default=0, help="hanya ukur waktu terima transfer + trip PA N roll")
    a = ap.parse_args()
    guard(a)
    asyncio.run(main(a))
