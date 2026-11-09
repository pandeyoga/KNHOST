#!/usr/bin/env python3
"""FIX-5 — uji beban WMS (roll/stok/gudang) pada data sintetis sebesar produksi. HANYA DB salinan uji.

Mode
  synth    roll (bawaan 300.000) + tag + lot + mutasi (±2 per roll) bertanda `PF_<tag>`, tersebar ke gudang, produk
           dan PT yang ada; status & bin menyerupai produksi (±45 % tersedia, ±35 % terkirim, 80 % roll fisik ber-bin).
  bench    p50/p95/maks endpoint panas WMS lewat HTTP (akun demo; sandi dibaca dari `KN_DEMO_PASS` atau AGENTS.md —
           tidak pernah ditulis di sini) + ukuran respons; opsional profil Mongo (`--profile-slowms`) → ringkasan
           kueri lambat per koleksi/rencana.
  explain  rencana & dokumen diperiksa untuk kueri jalur stok/WMS (bukti index).
  purge    hapus data `PF_<tag>`.

    cd /app/backend && python /app/scripts/wms_perf_bench.py synth --confirm-db test_database --rolls 300000
    cd /app/backend && python /app/scripts/wms_perf_bench.py bench --confirm-db test_database --out /tmp/bench.json

Keamanan: MONGO_URL wajib localhost/127.0.0.1 dan `--confirm-db` = DB_NAME. Penghapusan hanya data bertanda.
"""
import argparse
import asyncio
import json
import os
import random
import re
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
ENTS = ["ent_ksc", "ent_kanda", "ent_cst"]


def guard(args):
    host = urlparse(os.environ.get("MONGO_URL", "")).hostname
    if host not in ("localhost", "127.0.0.1"):
        sys.exit(f"Ditolak: MONGO_URL harus localhost (sekarang {host!r}).")
    if args.confirm_db != os.environ.get("DB_NAME"):
        sys.exit("Ditolak: --confirm-db wajib sama dengan DB_NAME (DB salinan uji).")


def iso(t):
    return t.isoformat()


def pct(values, q):
    s = sorted(values)
    if not s:
        return None
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 1)


# ─── synth ───────────────────────────────────────────────────────────────────────────────────────────────
async def mode_synth(args):
    from db import db
    rng = random.Random(5)
    tag = args.tag
    now = datetime.now(timezone.utc)
    whs = await db.warehouses.find({"active": {"$ne": False}}, {"_id": 0, "id": 1, "zones": 1}).to_list(200)
    from services import placement_rules as pr
    bins = {w["id"]: [n["bin"]["id"] for n in pr.flatten_nodes(w)] for w in whs}
    wids = [w["id"] for w in whs]
    prods = [p["id"] for p in await db.products.find({}, {"_id": 0, "id": 1}).to_list(2000)]
    ents = [e["id"] for e in await db.business_entities.find({}, {"_id": 0, "id": 1}).to_list(20)] or ENTS
    statuses = ["available", "delivered", "consumed", "reserved", "committed", "in_transit_transfer", "blocked",
                "quarantine"]
    weights = [45, 35, 5, 5, 3, 2, 2, 3]
    t0 = time.perf_counter()
    B = 5000
    n_mov = 0
    for start in range(0, args.rolls, B):
        rolls, tags, movs, lots = [], [], [], []
        for i in range(start, min(args.rolls, start + B)):
            rid, tid = f"roll_PF_{tag}_{i}", f"tag_PF_{tag}_{i}"
            st = rng.choices(statuses, weights)[0]
            wid = rng.choice(wids)
            pid = prods[(i // 50) % len(prods)] if rng.random() < 0.7 else rng.choice(prods)
            own = ents[0] if rng.random() < 0.7 else rng.choice(ents)
            created = now - timedelta(days=rng.randint(0, 720), seconds=rng.randint(0, 86000))
            physical = st not in ("delivered", "consumed", "in_transit_transfer")
            b = rng.choice(bins[wid]) if physical and bins.get(wid) and rng.random() < 0.8 else None
            lot_no = i // 200
            ln = 0.0 if st in ("delivered", "consumed") else float(rng.choice([25, 30, 40, 50, 60]))
            rolls.append({"id": rid, "roll_no": f"PF{tag}{i:07d}", "product_id": pid, "warehouse_id": wid,
                          "owner_entity_id": own, "status": st, "length_remaining": ln, "length_initial": 50.0,
                          "unit": "meter", "grade": rng.choice("AAAB"), "lot": f"L-PF-{tag}-{lot_no}",
                          "lot_id": f"lot_PF_{tag}_{lot_no}", "dye_lot": f"DL{lot_no % 97}",
                          "base_unit_cost": 15000, "unit_cost": 15000, "cost_basis": "synthetic_bench",
                          "rfid_tag_id": tid, "bin_id": b, "bin_code": b or "", "active_movement": None,
                          "reserved_ref": ({"type": "sales_order", "id": f"so_PF_{tag}_{i % 900}"}
                                           if st in ("reserved", "committed") else None),
                          "length_reserved": 0, "length_reservations": [], "created_at": iso(created),
                          "updated_at": iso(created),
                          "journey": {"stage": "stored" if b else "tag_verified", "routing": "store",
                                      "verified_tag_id": tid}})
            tags.append({"id": tid, "epc": f"E2PF{tag.upper()}{i:016X}", "roll_id": rid,
                         "status": "active" if physical else "retired", "warehouse_id": wid, "created_at": iso(created)})
            if i % 200 == 0:
                lots.append({"id": f"lot_PF_{tag}_{lot_no}", "lot_number": f"L-PF-{tag}-{lot_no}", "product_id": pid,
                             "owner_entity_id": own, "lot_status": "active", "created_at": iso(created),
                             "roll_count": 200})
            for k in range(rng.choice([1, 2, 2, 3])):
                n_mov += 1
                movs.append({"id": f"mov_PF_{tag}_{i}_{k}", "product_id": pid, "warehouse_id": wid, "owner_entity_id": own,
                             "movement_type": ["receipt", "transfer_in", "shipment", "putaway"][k % 4],
                             "quantity": 50.0 if k == 0 else -ln, "unit": "meter", "roll_id": rid, "qty_rolls": 1,
                             "lot_id": f"lot_PF_{tag}_{lot_no}", "source_document": f"PF-{tag}-{i}",
                             "timestamp": iso(created + timedelta(days=k * 3))})
        await db.inventory_rolls.insert_many(rolls, ordered=False)
        await db.rfid_tags.insert_many(tags, ordered=False)
        await db.inventory_movements.insert_many(movs, ordered=False)
        if lots:
            await db.inventory_lots.insert_many(lots, ordered=False)
        if (start // B) % 10 == 0:
            print(f"[synth] {start + len(rolls)} roll, {n_mov} mutasi ({time.perf_counter() - t0:.0f} dtk)", flush=True)
    sizes = {}
    for c in ("inventory_rolls", "inventory_movements", "rfid_tags", "inventory_lots"):
        st = await db.command("collStats", c)
        sizes[c] = {"count": st.get("count"), "size_mb": round(st.get("size", 0) / 1e6, 1),
                    "index_mb": round(st.get("totalIndexSize", 0) / 1e6, 1)}
    out = {"tag": tag, "rolls": args.rolls, "movements": n_mov, "seconds": round(time.perf_counter() - t0), "sizes": sizes}
    print(json.dumps(out, indent=1))
    Path(args.out).write_text(json.dumps(out, indent=1))


async def mode_purge(args):
    from db import db
    rx = {"$regex": f"^[a-z]+_PF_{re.escape(args.tag)}_"}
    for c in ("inventory_rolls", "rfid_tags", "inventory_movements", "inventory_lots"):
        r = await db[c].delete_many({"id": rx})
        print(c, r.deleted_count)


# ─── bench ───────────────────────────────────────────────────────────────────────────────────────────────
def _pw():
    if os.environ.get("KN_DEMO_PASS"):
        return os.environ["KN_DEMO_PASS"]
    m = re.search(r"Login demo:.*?/\s*`([^`]+)`", (ROOT / "AGENTS.md").read_text(encoding="utf-8"))
    return m.group(1)


async def _busiest_warehouse(db):
    rows = await db.inventory_rolls.aggregate([
        {"$match": {"status": {"$in": ["available", "reserved", "committed", "blocked", "quarantine"]}}},
        {"$group": {"_id": "$warehouse_id", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 1}]).to_list(1)
    return rows[0]["_id"] if rows else ""


def endpoints(wh, pid, roll_no):
    return [
        ("rolls_paged", "/inventory/rolls", {"page": 1, "page_size": 100}),
        ("rolls_paged_wh", "/inventory/rolls", {"page": 1, "page_size": 100, "warehouse_id": wh}),
        ("rolls_paged_search", "/inventory/rolls", {"page": 1, "page_size": 50, "q": roll_no}),
        ("rolls_array_default", "/inventory/rolls", {}),
        ("rolls_groups", "/inventory/roll-groups", {"warehouse_id": wh}),
        ("putaway_queue", "/inventory/putaway/queue", {"warehouse_id": wh, "limit": 100}),
        ("wh_locations", f"/warehouses/{wh}/locations", {}),
        ("wh_stock_tree", f"/warehouses/{wh}/stock-tree", {}),
        ("movements_paged", "/inventory/movements", {"page": 1, "page_size": 100}),
        ("movements_product", "/inventory/movements", {"page": 1, "page_size": 100, "product_id": pid}),
        ("lots_paged", "/lots", {"page": 1, "page_size": 50}),
        ("balances", "/inventory/balances", {}),
        ("status_board", "/inventory/status-board", {}),
        ("rfid_tags", "/rfid/tags", {}),
        ("rfid_lookup", "/rfid/lookup", {"code": roll_no}),
        ("putaway_orders", "/putaway-orders", {}),
        ("transfers", "/transfers", {}),
        ("goods_receipts", "/goods-receipts", {}),
        ("wms_tasks", "/wms/tasks", {}),
        ("dashboard", "/dashboard", {}),
    ]


async def mode_bench(args):
    import requests
    from db import db
    base = args.base_url.rstrip("/") + "/api"
    r = requests.post(f"{base}/auth/login", json={"email": args.user, "password": _pw()}, timeout=60)
    r.raise_for_status()
    hdr = {"Authorization": f"Bearer {r.json()['token']}"}
    wh = args.warehouse or await _busiest_warehouse(db)
    pid = (await db.inventory_rolls.find_one({"warehouse_id": wh}, {"_id": 0, "product_id": 1}) or {}).get("product_id", "")
    roll_no = (await db.inventory_rolls.find_one({"roll_no": {"$regex": "^PF"}}, {"_id": 0, "roll_no": 1})
               or await db.inventory_rolls.find_one({}, {"_id": 0, "roll_no": 1}) or {}).get("roll_no", "")
    only = set(args.only.split(",")) if args.only else None
    if args.profile_slowms is not None:
        await db.command({"profile": 0})
        await db.system.profile.drop()
        await db.command({"profile": 1, "slowms": args.profile_slowms})
    out = {"user": args.user, "warehouse": wh, "rounds": args.rounds, "endpoints": {}}
    for name, path, params in endpoints(wh, pid, roll_no):
        if only and name not in only:
            continue
        lat, size, code = [], 0, None
        for i in range(args.warmup + args.rounds):
            t0 = time.perf_counter()
            try:
                resp = requests.get(f"{base}{path}", params=params, headers=hdr, timeout=args.timeout)
                code = resp.status_code
                size = len(resp.content)
            except requests.RequestException as exc:
                code = f"ERR {type(exc).__name__}"
                lat.append(args.timeout * 1000)
                break
            if i >= args.warmup:
                lat.append((time.perf_counter() - t0) * 1000)
        out["endpoints"][name] = {"path": path, "params": params, "status": code, "bytes": size, "n": len(lat),
                                  "p50_ms": pct(lat, 0.5), "p95_ms": pct(lat, 0.95), "max_ms": round(max(lat), 1) if lat else None}
        e = out["endpoints"][name]
        print(f"{name:<22} {str(code):>5} {e['p50_ms']!s:>8} {e['p95_ms']!s:>8} {e['max_ms']!s:>8} ms  {size / 1024:>8.0f} KB", flush=True)
    if args.profile_slowms is not None:
        await db.command({"profile": 0})
        agg = await db.system.profile.aggregate([
            {"$group": {"_id": {"ns": "$ns", "plan": "$planSummary", "op": "$op"}, "n": {"$sum": 1},
                        "ms": {"$sum": "$millis"}, "docs": {"$sum": "$docsExamined"}}},
            {"$sort": {"ms": -1}}, {"$limit": 30}]).to_list(30)
        out["profile"] = [{"ns": a["_id"].get("ns"), "op": a["_id"].get("op"), "plan": a["_id"].get("plan"), "n": a["n"],
                           "ms_total": a["ms"], "docs_examined": a["docs"]} for a in agg]
        for a in out["profile"][:20]:
            print(f"  {a['ms_total']:>7} ms  {a['n']:>5}×  {a['op']:<8} {a['ns']:<45} {str(a['plan'])[:60]}")
    Path(args.out).write_text(json.dumps(out, indent=1, ensure_ascii=False))


# ─── explain ─────────────────────────────────────────────────────────────────────────────────────────────
async def mode_explain(args):
    from db import db
    roll = await db.inventory_rolls.find_one({"roll_no": {"$regex": "^PF"}}, {"_id": 0}) or \
        await db.inventory_rolls.find_one({}, {"_id": 0})
    ids = [r["id"] for r in await db.inventory_rolls.find({}, {"_id": 0, "id": 1}).skip(5000).limit(200).to_list(200)]
    Q = [
        ("inventory_rolls", {"id": roll["id"]}, "roll per id"),
        ("inventory_rolls", {"id": {"$in": ids}}, "roll id $in 200"),
        ("inventory_movements", {"id": "mov_x"}, "mutasi per id (upsert PA)"),
        ("inventory_rolls", {"reserved_ref.id": "so_x"}, "roll per reserved_ref.id"),
        ("inventory_rolls", {"$or": [{"reserved_ref.type": "wh_transfer", "reserved_ref.id": "t"}, {"transfer_ref.id": "t"}],
                             "status": {"$in": ["in_transit_transfer"]}}, "roll milik transfer"),
        ("inventory_rolls", {"last_transfer.ref_id": "t"}, "roll diterima transfer"),
        ("inventory_lots", {"id": roll.get("lot_id") or "x"}, "lot per id (recompute)"),
        ("rfid_tags", {"epc": "E2X"}, "tag per EPC"),
        ("rfid_tags", {"roll_id": roll["id"], "status": "active"}, "tag per roll"),
        ("inventory_rolls", {"product_id": roll["product_id"], "warehouse_id": roll["warehouse_id"],
                             "owner_entity_id": roll["owner_entity_id"]}, "segmen saldo (rebuild)"),
        ("inventory_rolls", {"warehouse_id": roll["warehouse_id"], "length_remaining": {"$gt": 0},
                             "status": {"$in": ["available", "reserved"]},
                             "$or": [{"bin_id": None}, {"bin_id": ""}]}, "antrean rak"),
    ]
    out = []
    for coll, flt, label in Q:
        ex = await db.command("explain", {"find": coll, "filter": flt}, verbosity="executionStats")
        es = ex.get("executionStats") or {}
        plan = json.dumps(ex.get("queryPlanner", {}).get("winningPlan", {}))
        stage = "COLLSCAN" if "COLLSCAN" in plan else "IXSCAN"
        idx = re.findall(r'"indexName": "([^"]+)"', plan)
        out.append({"query": label, "coll": coll, "stage": stage, "index": idx[:2], "docs": es.get("totalDocsExamined"),
                    "keys": es.get("totalKeysExamined"), "ms": es.get("executionTimeMillis")})
        print(f"{label:<28} {stage:<9} {','.join(idx[:2]):<40} docs {es.get('totalDocsExamined')!s:>8}  {es.get('executionTimeMillis')} ms")
    Path(args.out).write_text(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("synth", "bench", "explain", "purge"))
    ap.add_argument("--confirm-db", required=True)
    ap.add_argument("--tag", default="a")
    ap.add_argument("--rolls", type=int, default=300000)
    ap.add_argument("--out", default="/tmp/wms_perf_bench.json")
    ap.add_argument("--base-url", default="http://127.0.0.1:8001")
    ap.add_argument("--user", default="admin@kainnusantara.id")
    ap.add_argument("--warehouse", default="")
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--warmup", type=int, default=2)
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--only", default="")
    ap.add_argument("--profile-slowms", type=int, default=None)
    args = ap.parse_args()
    guard(args)
    asyncio.run({"synth": mode_synth, "bench": mode_bench, "explain": mode_explain, "purge": mode_purge}[args.mode](args))


if __name__ == "__main__":
    main()
