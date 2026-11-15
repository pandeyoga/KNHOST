#!/usr/bin/env python3
"""FIX-7 — ukur & bandingkan endpoint baca yang dioptimalkan (cari roll, papan stok, pohon stok, dasbor, mutasi
petugas berpagar lokasi) pada data sintetis sebesar produksi. HANYA DB salinan uji.

Mode
  balances  bangun ulang saldo (`roll_service.rebuild_balance`) untuk segmen roll sintetis `PF_` (data `synth`
            `wms_perf_bench.py` tidak membuat saldo → papan stok/dasbor tidak melihat volume itu).
  bench     p50/p95/maks lewat HTTP per (pengguna, endpoint) + ukuran respons.
  snap      satu respons per (pengguna, endpoint), dinormalisasi (tanpa waktu/kunci acak), ke berkas JSON.
  diff      bandingkan dua berkas `snap` → identik / beda (jalur JSON pertama yang berbeda).
  explain   rencana kueri: mutasi petugas berpagar lokasi, cari roll.

    cd /app/backend && DB_NAME=kn_perf python /app/scripts/fix7_perf.py balances --confirm-db kn_perf
    cd /app/backend && DB_NAME=kn_perf python /app/scripts/fix7_perf.py bench --confirm-db kn_perf \
        --base-url http://127.0.0.1:8002 --out /tmp/f7_bench_base.json
    cd /app/backend && DB_NAME=kn_perf python /app/scripts/fix7_perf.py snap --confirm-db kn_perf \
        --base-url http://127.0.0.1:8002 --out /tmp/f7_snap_base.json
    python /app/scripts/fix7_perf.py diff --confirm-db x /tmp/f7_snap_base.json /tmp/f7_snap_new.json

Sandi akun demo dibaca dari `KN_DEMO_PASS` atau AGENTS.md (tidak pernah ditulis di sini).
Keamanan: MONGO_URL wajib localhost/127.0.0.1 dan `--confirm-db` = DB_NAME (kecuali mode `diff`).
"""
import argparse
import asyncio
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

USERS = {"admin": "admin@kainnusantara.id", "manager": "manager@kainnusantara.id", "sales": "sales@kainnusantara.id",
         "gudang": "warehouse@kainnusantara.id"}
VOLATILE = {"generated_at", "updated_at", "now", "server_time", "elapsed_ms", "duration_ms", "took_ms", "as_of",
            "expired_released"}


def guard(args):
    if args.mode == "diff":
        return
    host = urlparse(os.environ.get("MONGO_URL", "")).hostname
    if host not in ("localhost", "127.0.0.1"):
        sys.exit("Ditolak: MONGO_URL bukan localhost.")
    if args.confirm_db != os.environ.get("DB_NAME"):
        sys.exit("Ditolak: --confirm-db wajib sama dengan DB_NAME (DB salinan uji).")


def _pw():
    if os.environ.get("KN_DEMO_PASS"):
        return os.environ["KN_DEMO_PASS"]
    m = re.search(r"Login demo:.*?/\s*`([^`]+)`", (ROOT / "AGENTS.md").read_text(encoding="utf-8"))
    return m.group(1)


def pct(values, q):
    if not values:
        return None
    s = sorted(values)
    return round(s[min(len(s) - 1, int(round(q * (len(s) - 1))))], 1)


# ─── data sintetis: saldo ────────────────────────────────────────────────────────────────────────────────
async def mode_balances(args):
    from db import db
    from services.roll_service import rebuild_balance
    segs = await db.inventory_rolls.aggregate([
        {"$match": {"id": {"$regex": "^roll_PF_"}}},
        {"$group": {"_id": {"p": "$product_id", "w": "$warehouse_id", "o": "$owner_entity_id"}}}],
        allowDiskUse=True).to_list(None)
    keys = [(s["_id"]["p"], s["_id"]["w"], s["_id"]["o"]) for s in segs]
    print(f"[balances] {len(keys)} segmen", flush=True)
    t0 = time.perf_counter()
    sem = asyncio.Semaphore(args.concurrency)

    async def one(k):
        async with sem:
            await rebuild_balance(*k)

    for i in range(0, len(keys), 500):
        await asyncio.gather(*(one(k) for k in keys[i:i + 500]))
        print(f"[balances] {min(i + 500, len(keys))}/{len(keys)} ({time.perf_counter() - t0:.0f} dtk)", flush=True)
    print(json.dumps({"segments": len(keys), "seconds": round(time.perf_counter() - t0),
                      "balances": await db.inventory_balances.count_documents({})}))


# ─── titik ukur ──────────────────────────────────────────────────────────────────────────────────────────
async def _targets(db):
    """Nilai nyata dari DB untuk parameter endpoint (roll sintetis, roll acuan, lot, gudang tersibuk, dst.)."""
    pf = await db.inventory_rolls.find_one({"roll_no": {"$regex": "^PF"}, "status": "available"},
                                           {"_id": 0, "roll_no": 1, "lot": 1, "id": 1}, sort=[("roll_no", -1)]) or \
        await db.inventory_rolls.find_one({"status": "available", "lot": {"$nin": [None, ""]}},   # data acuan (tanpa PF)
                                          {"_id": 0, "roll_no": 1, "lot": 1, "id": 1}, sort=[("roll_no", -1)]) or {}
    real = await db.inventory_rolls.find_one({"roll_no": {"$regex": "^RL-"}, "status": "available"},
                                             {"_id": 0, "roll_no": 1, "lot": 1, "product_id": 1}) or {}
    busiest = await db.inventory_rolls.aggregate([
        {"$match": {"status": {"$in": ["available", "reserved", "committed", "blocked", "quarantine"]}}},
        {"$group": {"_id": "$warehouse_id", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 1}]).to_list(1)
    wh = busiest[0]["_id"] if busiest else ""
    whdoc = await db.warehouses.find_one({"id": wh}, {"_id": 0, "site_id": 1}) or {}
    gud = await db.users.find_one({"email": USERS["gudang"]}, {"_id": 0, "location_site_ids": 1}) or {}
    gsite = (gud.get("location_site_ids") or [""])[0]
    gwh = await db.warehouses.find_one({"site_id": gsite, "active": {"$ne": False}}, {"_id": 0, "id": 1}) or {}
    groll = await db.inventory_rolls.find_one({"warehouse_id": gwh.get("id"), "roll_no": {"$regex": "^PF"}},
                                              {"_id": 0, "roll_no": 1}) or \
        await db.inventory_rolls.find_one({"warehouse_id": gwh.get("id")}, {"_id": 0, "roll_no": 1}) or {}
    prod = await db.products.find_one({"id": real.get("product_id")}, {"_id": 0, "name": 1}) or {}
    tag = await db.rfid_tags.find_one({"roll_id": pf.get("id")}, {"_id": 0, "epc": 1}) or {}
    return {"pf_roll": pf.get("roll_no", ""), "pf_suffix": (pf.get("roll_no") or "")[-6:], "pf_lot": pf.get("lot", ""),
            "real_roll": real.get("roll_no", ""), "product_word": (prod.get("name") or "kain").split()[0],
            "wh": wh, "site": whdoc.get("site_id", ""), "g_wh": gwh.get("id", ""), "g_roll": groll.get("roll_no", ""),
            "epc": tag.get("epc", "")}


def endpoints(t):
    R = "/inventory/rolls"
    pg = {"page": 1, "page_size": 50}
    return [
        # 1 — cari roll
        ("admin", "rolls_q_pf_exact", R, {**pg, "q": t["pf_roll"]}),
        ("admin", "rolls_q_pf_suffix", R, {**pg, "q": t["pf_suffix"]}),
        ("admin", "rolls_q_real_roll", R, {**pg, "q": t["real_roll"]}),
        ("admin", "rolls_q_lot", R, {**pg, "q": t["pf_lot"]}),
        ("admin", "rolls_q_product", R, {**pg, "q": t["product_word"]}),
        ("admin", "rolls_q_none", R, {**pg, "q": "TIDAK-ADA-ROLL-INI"}),
        ("admin", "rolls_q_epc", R, {**pg, "q": t["epc"]}),
        ("admin", "rolls_array_q", R, {"limit": 50, "q": t["pf_roll"]}),
        ("gudang", "rolls_q_fenced", R, {**pg, "q": t["g_roll"], "location_view": 1}),
        ("admin", "roll_groups_q", "/inventory/roll-groups", {"q": t["pf_lot"]}),
        # 2 — papan stok, pohon stok, dasbor
        ("admin", "status_board", "/inventory/status-board", {}),
        ("gudang", "status_board", "/inventory/status-board", {}),
        ("sales", "status_board", "/inventory/status-board", {}),
        ("admin", "stock_tree", f"/warehouses/{t['wh']}/stock-tree", {}),
        ("admin", "site_stock_tree", f"/warehouse-sites/{t['site']}/stock-tree", {}),
        ("gudang", "stock_tree", f"/warehouses/{t['g_wh']}/stock-tree", {}),
        ("admin", "dashboard", "/dashboard", {}),
        ("manager", "dashboard", "/dashboard", {}),
        ("sales", "dashboard", "/dashboard", {}),
        ("gudang", "dashboard", "/dashboard", {}),
        # 3 — mutasi petugas berpagar lokasi
        ("admin", "movements_p1", "/inventory/movements", {"page": 1, "page_size": 100}),
        ("gudang", "movements_p1", "/inventory/movements", {"page": 1, "page_size": 100}),
        ("gudang", "movements_p1_wh", "/inventory/movements", {"page": 1, "page_size": 100, "warehouse_id": t["g_wh"]}),
        ("gudang", "movements_p5", "/inventory/movements", {"page": 5, "page_size": 100}),
    ]


def _login(base, email):
    import requests
    r = requests.post(f"{base}/auth/login", json={"email": email, "password": _pw()}, timeout=60)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


async def mode_bench(args):
    import requests
    from db import db
    base = args.base_url.rstrip("/") + "/api"
    t = await _targets(db)
    hdrs = {u: _login(base, e) for u, e in USERS.items()}
    only = set(args.only.split(",")) if args.only else None
    out = {"targets": t, "rounds": args.rounds, "endpoints": {}}
    for user, name, path, params in endpoints(t):
        key = f"{user}:{name}"
        if only and name not in only and key not in only:
            continue
        lat, size, code = [], 0, None
        for i in range(args.warmup + args.rounds):
            t0 = time.perf_counter()
            try:
                resp = requests.get(f"{base}{path}", params=params, headers=hdrs[user], timeout=args.timeout)
                code, size = resp.status_code, len(resp.content)
            except requests.RequestException as exc:
                code = f"ERR {type(exc).__name__}"
                break
            if i >= args.warmup:
                lat.append((time.perf_counter() - t0) * 1000)
        e = {"path": path, "params": params, "status": code, "bytes": size, "n": len(lat), "p50_ms": pct(lat, 0.5),
             "p95_ms": pct(lat, 0.95), "max_ms": round(max(lat), 1) if lat else None}
        out["endpoints"][key] = e
        print(f"{key:<26} {str(code):>5} {e['p50_ms']!s:>8} {e['p95_ms']!s:>8} {e['max_ms']!s:>8} ms {size / 1024:>8.0f} KB",
              flush=True)
    Path(args.out).write_text(json.dumps(out, indent=1, ensure_ascii=False))


def _norm(x):
    if isinstance(x, dict):
        out = {k: _norm(v) for k, v in sorted(x.items()) if k not in VOLATILE}
        if isinstance(out.get("by_owner"), list):   # pohon stok: urutan PT dulu = urutan roll pertama terbaca (acak)
            out["by_owner"] = sorted(out["by_owner"], key=lambda o: str(o.get("owner_entity_id")))
        return out
    if isinstance(x, list):
        return [_norm(v) for v in x]
    if isinstance(x, float):
        return round(x, 6)
    return x


async def mode_snap(args):
    import requests
    from db import db
    base = args.base_url.rstrip("/") + "/api"
    t = await _targets(db)
    hdrs = {u: _login(base, e) for u, e in USERS.items()}
    out = {"targets": t, "responses": {}}
    only = set(args.only.split(",")) if args.only else None
    out["ms"] = {}
    for user, name, path, params in endpoints(t):
        key = f"{user}:{name}"
        if only and name not in only and key not in only:
            continue
        t0 = time.perf_counter()
        r = requests.get(f"{base}{path}", params=params, headers=hdrs[user], timeout=args.timeout)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
        out["responses"][key] = {"status": r.status_code, "total": r.headers.get("x-total-count"), "body": _norm(body)}
        out["ms"][key] = ms
        print(f"{key:<26} {r.status_code} {ms:>10} ms {len(r.content) / 1024:>8.0f} KB", flush=True)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, sort_keys=True))


def _first_diff(a, b, path="$"):
    if type(a) is not type(b):
        return f"{path}: tipe {type(a).__name__} ≠ {type(b).__name__}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return f"{path}.{k}: hanya di {'B' if k not in a else 'A'}"
            d = _first_diff(a[k], b[k], f"{path}.{k}")
            if d:
                return d
        return ""
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: panjang {len(a)} ≠ {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = _first_diff(x, y, f"{path}[{i}]")
            if d:
                return d
        return ""
    return "" if a == b else f"{path}: {str(a)[:80]!r} ≠ {str(b)[:80]!r}"


def mode_diff(args):
    a = json.loads(Path(args.files[0]).read_text())
    b = json.loads(Path(args.files[1]).read_text())
    same = diff = 0
    for k in sorted(set(a["responses"]) | set(b["responses"])):
        ra, rb = a["responses"].get(k), b["responses"].get(k)
        if ra is None or rb is None:
            print(f"BEDA   {k}: hanya di {'B' if ra is None else 'A'}")
            diff += 1
            continue
        d = "" if (ra["status"], ra["total"]) == (rb["status"], rb["total"]) else \
            f"status/total {ra['status']}/{ra['total']} ≠ {rb['status']}/{rb['total']}"
        d = d or _first_diff(ra["body"], rb["body"])
        if d:
            diff += 1
            print(f"BEDA   {k}: {d}")
        else:
            same += 1
            print(f"SAMA   {k}")
    print(f"ringkas: {same} identik, {diff} berbeda")


async def mode_explain(args):
    from db import db
    t = await _targets(db)
    gud = await db.users.find_one({"email": USERS["gudang"]}, {"_id": 0})
    from services import location_scope
    whs = await location_scope.allowed_warehouse_ids(gud) if hasattr(location_scope, "allowed_warehouse_ids") else None
    if not whs:
        site = (gud.get("location_site_ids") or [""])[0]
        whs = [w["id"] async for w in db.warehouses.find({"site_id": site}, {"_id": 0, "id": 1})]
    ents = ["ent_ksc", "ent_kanda", "ent_cst", None, ""]
    mq = {"owner_entity_id": {"$in": ents}, "warehouse_id": {"$in": whs}}
    rows = []

    async def ex(label, coll, flt, sort=None, limit=0):
        cmd = {"find": coll, "filter": flt}
        if sort:
            cmd["sort"] = sort
        if limit:
            cmd["limit"] = limit
        e = await db.command("explain", cmd, verbosity="executionStats")
        es = e.get("executionStats") or {}
        plan = json.dumps(e.get("queryPlanner", {}).get("winningPlan", {}))
        stage = "COLLSCAN" if "COLLSCAN" in plan else ("IXSCAN" if "IXSCAN" in plan else "?")
        idx = re.findall(r'"indexName": "([^"]+)"', plan)
        rows.append({"query": label, "stage": stage, "index": sorted(set(idx)), "keys": es.get("totalKeysExamined"),
                     "docs": es.get("totalDocsExamined"), "n": es.get("nReturned"), "ms": es.get("executionTimeMillis")})
        print(f"{label:<44} {stage:<9} {','.join(sorted(set(idx)))[:60]:<60} keys {es.get('totalKeysExamined')!s:>8} "
              f"docs {es.get('totalDocsExamined')!s:>8} n {es.get('nReturned')!s:>5} {es.get('executionTimeMillis')} ms")

    async def ex_count(label, coll, flt):
        e = await db.command("explain", {"count": coll, "query": flt}, verbosity="executionStats")
        es = e.get("executionStats") or {}
        plan = json.dumps(e.get("queryPlanner", {}).get("winningPlan", {}))
        idx = re.findall(r'"indexName": "([^"]+)"', plan)
        stage = "COLLSCAN" if "COLLSCAN" in plan else ("COUNT_SCAN" if "COUNT_SCAN" in plan else "IXSCAN")
        rows.append({"query": label, "stage": stage, "index": sorted(set(idx)), "keys": es.get("totalKeysExamined"),
                     "docs": es.get("totalDocsExamined"), "ms": es.get("executionTimeMillis")})
        print(f"{label:<44} {stage:<9} {','.join(sorted(set(idx)))[:60]:<60} keys {es.get('totalKeysExamined')!s:>8} "
              f"docs {es.get('totalDocsExamined')!s:>8} {es.get('executionTimeMillis')} ms")

    await ex("mutasi berpagar: halaman 1 (urut waktu)", "inventory_movements", mq, {"timestamp": -1}, 100)
    await ex_count("mutasi berpagar: hitung", "inventory_movements", mq)
    await ex("mutasi gudang tunggal: halaman 1", "inventory_movements",
             {"owner_entity_id": {"$in": ents}, "warehouse_id": t["g_wh"]}, {"timestamp": -1}, 100)
    rx = {"$regex": re.escape(t["pf_suffix"]), "$options": "i"}
    await ex("roll: nomor roll mengandung (regex i)", "inventory_rolls", {"roll_no": rx}, {"created_at": -1}, 50)
    Path(args.out).write_text(json.dumps(rows, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("balances", "bench", "snap", "diff", "explain"))
    ap.add_argument("files", nargs="*")
    ap.add_argument("--confirm-db", default="")
    ap.add_argument("--base-url", default="http://127.0.0.1:8002")
    ap.add_argument("--out", default="/tmp/fix7_perf.json")
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--warmup", type=int, default=2)
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--only", default="")
    ap.add_argument("--concurrency", type=int, default=8)
    args = ap.parse_args()
    guard(args)
    if args.mode == "diff":
        mode_diff(args)
        return
    asyncio.run({"balances": mode_balances, "bench": mode_bench, "snap": mode_snap, "explain": mode_explain}[args.mode](args))


if __name__ == "__main__":
    main()
