#!/usr/bin/env python3
"""FIX-2 (9 Nov 2026) — uji silang otomatis angka stok: SEMUA endpoint angka stok vs hitungan LANGSUNG dari
`inventory_rolls` menurut definisi tunggal (`services/stock_figures.py`). Dasar: `b3a_compare_numbers.py` (audit B3a).

BACA-SAJA: Mongo hanya `find`/`aggregate`; API hanya GET (+ login). Sandi demo dibaca dari env `KN_DEMO_PASS` atau baris
"Login demo" di AGENTS.md (tidak ditulis di sini). Dijalankan DI DALAM kontainer backend (pymongo tersedia):

  docker compose -f docker-compose.dev.yml exec backend \
      python /app/scripts/audit/fix2_stock_crosscheck.py --base http://localhost:8001 --pids /tmp/sample_pids.json \
      --out /tmp/fix2_cmp.md

Kebenaran (truth) dihitung per produk × PT × gudang dari roll di gudang yang DIHITUNG (aktif, bukan data uji):
  gudang      = master `active != false` dan tidak bertanda `is_test`
  free(roll)  = length_remaining − length_reserved bila status `available` ∧ tanpa klaim PA (`active_movement`) ∧
                tanpa tahan inspeksi/hold; selain itu 0
  K-04        = Σ free − cadangan makloon aktif (dialokasikan ke gudang PT itu: tersedia terbesar dulu)
  fisik       = Σ length_remaining status fisik (available, reserved, committed, picked, packed, hold, wip,
                quarantine, blocked, damaged)
Keluaran: tabel markdown selisih + ringkasan per endpoint; kode keluar 0 (selisih dilaporkan, bukan dilempar).
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict

PHYS = {"available", "reserved", "committed", "picked", "packed", "hold", "wip", "quarantine", "blocked", "damaged"}
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ACCOUNTS = ["admin@kainnusantara.id", "manager@kainnusantara.id", "sales@kainnusantara.id",
            "sales.kanda@kainnusantara.id", "warehouse.soreang@kainnusantara.id",
            "warehouse.rancamalang@kainnusantara.id", "wh.admin@kainnusantara.id"]
EPS = 0.011


def demo_password():
    if os.environ.get("KN_DEMO_PASS"):
        return os.environ["KN_DEMO_PASS"]
    txt = open(os.path.join(ROOT, "AGENTS.md"), encoding="utf-8").read()
    m = re.search(r"Login demo:.*?/\s*`([^`]+)`", txt)
    if not m:
        sys.exit("sandi demo tidak ditemukan (set KN_DEMO_PASS)")
    return m.group(1)


class Api:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.tokens = {}
        self.users = {}

    def call(self, path, email=None, entity=None, body=None):
        req = urllib.request.Request(self.base + path, method="POST" if body is not None else "GET")
        req.add_header("Accept", "application/json")
        if email:
            req.add_header("Authorization", f"Bearer {self.tokens[email]}")
        if entity:
            req.add_header("X-Entity-Id", entity)
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, data=data, timeout=180) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"null")
            except Exception:  # noqa: BLE001
                return e.code, None

    def login(self, email, pw):
        st, body = self.call("/api/auth/login", body={"email": email, "password": pw})
        if st == 200:
            self.tokens[email] = body["token"]
            self.users[email] = body.get("user") or {}
        return st


def r2(x):
    return round(float(x or 0), 2)


def build_truth(db, pids):
    sites = {s["id"]: s for s in db.warehouse_sites.find({}, {"_id": 0})}
    whs = {}
    for w in db.warehouses.find({}, {"_id": 0}):
        site = sites.get(w.get("site_id") or "") or {}
        w["counted"] = w.get("active") is not False and w.get("is_test") is not True and site.get("is_test") is not True
        whs[w["id"]] = w
    counted = {k for k, w in whs.items() if w["counted"]}
    seg = defaultdict(lambda: {"free": 0.0, "free_rolls": 0, "phys": 0.0})
    for r in db.inventory_rolls.find({"product_id": {"$in": pids}},
                                     {"_id": 0, "product_id": 1, "warehouse_id": 1, "owner_entity_id": 1, "status": 1,
                                      "length_remaining": 1, "length_reserved": 1, "active_movement": 1,
                                      "inspection.hold": 1, "hold": 1}):
        if r.get("warehouse_id") not in counted:
            continue
        k = (r["product_id"], r.get("owner_entity_id") or "", r["warehouse_id"])
        ln = float(r.get("length_remaining") or 0)
        st = r.get("status")
        if st in PHYS:
            seg[k]["phys"] += ln
        held = bool((r.get("active_movement") or {}).get("id")) or bool(((r.get("inspection") or {}).get("hold") or {}).get("held"))
        if st == "available" and not held:
            f = ln - float(r.get("length_reserved") or 0)
            seg[k]["free"] += f
            if f > 0.001:
                seg[k]["free_rolls"] += 1
    mk = defaultdict(float)
    for m in db.material_reservations.find({"status": "active", "product_id": {"$in": pids}}, {"_id": 0}):
        mk[(m["product_id"], m.get("owner_entity_id") or "")] += float(m.get("qty") or 0)
    for (pid, eid), q in mk.items():
        left = q
        for k in sorted([k for k in seg if k[0] == pid and k[1] == eid], key=lambda k: (-seg[k]["free"], k[2])):
            cut = min(left, max(seg[k]["free"], 0))
            seg[k]["free"] -= cut
            left -= cut
            if left <= 0.001:
                break
    return seg, whs, mk


def agg(seg, pid, owners=None, wh_ids=None):
    q = rolls = phys = 0.0
    for (p, o, w), v in seg.items():
        if p != pid or (owners is not None and o not in owners) or (wh_ids is not None and w not in wh_ids):
            continue
        q += max(v["free"], 0)
        rolls += v["free_rolls"]
        phys += v["phys"]
    return {"qty": round(q, 2), "rolls": int(rolls), "phys": round(phys, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8001")
    ap.add_argument("--pids", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--mongo", default=os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    ap.add_argument("--db", default=os.environ.get("DB_NAME", "test_database"))
    a = ap.parse_args()
    from pymongo import MongoClient
    db = MongoClient(a.mongo)[a.db]
    pids = json.load(open(a.pids))
    seg, whs, mk = build_truth(db, pids)
    units = {p["id"]: p.get("base_unit") for p in db.products.find({"id": {"$in": pids}}, {"_id": 0, "id": 1, "base_unit": 1})}
    skus = {p["id"]: p.get("sku") for p in db.products.find({"id": {"$in": pids}}, {"_id": 0, "id": 1, "sku": 1})}
    ents = ["ent_ksc", "ent_kanda", "ent_82b52ed6ee8b"]
    site_whs = defaultdict(set)
    for wid, w in whs.items():
        if w["counted"] and w.get("site_id"):
            site_whs[w["site_id"]].add(wid)
    api = Api(a.base)
    pw = demo_password()
    for e in ACCOUNTS:
        api.login(e, pw)
    ADMIN = ACCOUNTS[0]
    rows = []

    def add(group, pid, owner, got, expect, note=""):
        if got is None:
            return
        rows.append((group, skus.get(pid, pid), units.get(pid, ""), owner, r2(got), r2(expect), r2(r2(got) - r2(expect)), note))

    prods = {e: {p["id"]: p for p in (api.call("/api/products", ADMIN, e)[1] or []) if isinstance(p, dict)} for e in ents}
    dash = {e: {p["id"]: p for p in ((api.call("/api/dashboard", ADMIN, e)[1] or {}).get("products") or [])} for e in ents}
    site_stock = {}
    for e in ents:
        for s in site_whs:
            st, b = api.call(f"/api/pos/site-stock?site_id={s}&entity_id={e}&product_ids={','.join(pids)}", ADMIN, e)
            site_stock[(s, e)] = (b or {}).get("stock") or {}
    low = {(i["product_id"], i["entity_id"]): i["available"] for i in
           ((api.call("/api/inventory/low-stock-summary?owner_entity_id=all&limit=500", ADMIN, "all")[1] or {}).get("items") or [])}
    tpl_av = {}
    tpls = sorted({p.get("template_id") for p in db.products.find({"id": {"$in": pids}}, {"_id": 0, "template_id": 1}) if p.get("template_id")})
    for tp in tpls:
        b = api.call(f"/api/product-templates/{tp}/summary", ADMIN, "all")[1] or {}
        for v in b.get("variants") or []:
            tpl_av[v["id"]] = v.get("available")
    for pid in pids:
        owners = sorted({k[1] for k in seg if k[0] == pid})
        if not owners and pid not in prods["ent_ksc"]:
            continue
        g = agg(seg, pid)
        k04 = {e: agg(seg, pid, {e}) for e in set(owners) | set(ents)}
        sb = (api.call(f"/api/inventory/status-board?product_id={pid}", ADMIN, "all")[1] or [])
        sb = sb[0] if isinstance(sb, list) and sb else {}
        add("status-board total", pid, "all", sb.get("total_available"), g["qty"])
        for be in sb.get("by_entity") or []:
            add("status-board per PT", pid, be["entity_id"], be.get("available"), k04.get(be["entity_id"], {"qty": 0})["qty"])
        bk = api.call(f"/api/stock/buckets?product_id={pid}", ADMIN, "all")[1] or []
        bk = bk[0] if isinstance(bk, list) and bk else {}
        add("stock/buckets totals", pid, "all", (bk.get("totals") or {}).get("available_qty"), g["qty"])
        br = api.call(f"/api/products/{pid}/stock-breakdown", ADMIN, "all")[1] or {}
        add("stock-breakdown saldo", pid, "all", sum(float(b.get("available_qty") or 0) for b in br.get("balances") or []), g["qty"])
        add("stock-breakdown matriks", pid, "all", sum(float(c.get("available_qty") or 0) for c in br.get("ownership_matrix") or []), g["qty"])
        ra = api.call(f"/api/inventory/rolls/available?product_id={pid}&all_entities=true&limit=1000", ADMIN, "all")[1] or {}
        ra_val = ra.get("available_total") if "available_total" in ra else sum(float(i.get("length_remaining") or 0) for i in ra.get("items") or [])
        add("rolls/available (pemilih roll)", pid, "all", ra_val, g["qty"])
        ir = api.call(f"/api/internal-requests-availability/{pid}", ADMIN, "all")[1] or {}
        add("internal-requests-availability", pid, "all", ir.get("group_available"), g["qty"])
        atpall = api.call(f"/api/stock/atp?product_id={pid}&owner_entity_id=all", ADMIN, "all")[1] or {}
        add("stock/atp semua PT", pid, "all", atpall.get("available"), g["qty"])
        if pid in tpl_av:
            add("product-templates summary", pid, "all", tpl_av[pid], g["qty"])
        for e in ents:
            P = prods[e].get(pid)
            if P:
                add("/products available_qty (global)", pid, "all", P.get("available_qty"), g["qty"])
                if e in owners or P.get("entity_available_qty"):
                    add("/products entity_available_qty", pid, e, P.get("entity_available_qty"), k04[e]["qty"])
            D = dash[e].get(pid)
            if D and (e in owners or D.get("entity_available_qty")):
                add("/dashboard entity_available_qty", pid, e, D.get("entity_available_qty"), k04[e]["qty"])
            if e in owners:
                atp = api.call(f"/api/stock/atp?product_id={pid}&owner_entity_id={e}", ADMIN, e)[1] or {}
                add("stock/atp per PT", pid, e, atp.get("available"), k04[e]["qty"])
                ss = api.call(f"/api/sales/stock-summary?product_id={pid}&entity_id={e}", ADMIN, e)[1] or {}
                rr = ss.get("rows") or []
                if rr:
                    add("sales/stock-summary bebas", pid, e, sum(float(x.get("free") or 0) for x in rr), k04[e]["qty"])
                    add("sales/stock-summary fisik", pid, e, sum(float(x.get("physical") or 0) for x in rr), k04[e]["phys"])
            if (pid, e) in low:
                add("low-stock-summary", pid, e, low[(pid, e)], k04[e]["qty"])
            for s, wset in site_whs.items():
                st = site_stock[(s, e)].get(pid)
                if st is not None:
                    add(f"pos/site-stock own_qty", pid, f"{e}@{s[-6:]}", st.get("own_qty"), agg(seg, pid, {e}, wset)["qty"])
            if P and P.get("stock_figures"):
                add("/products stock_figures.global", pid, "all", P["stock_figures"]["global"]["qty"], g["qty"])
    # KPI dasbor per satuan, mode "Semua PT" (STK-8)
    st, dall = api.call("/api/dashboard?entity_id=all", ADMIN, "all")
    all_pids = [p["id"] for p in db.products.find({}, {"_id": 0, "id": 1})]
    seg_all, _w, _m = build_truth(db, all_pids)
    unit_all = {p["id"]: p.get("base_unit") or "" for p in db.products.find({}, {"_id": 0, "id": 1, "base_unit": 1})}
    by_unit = defaultdict(float)
    for (p, o, w), v in seg_all.items():
        if o in ents:
            by_unit[unit_all.get(p) or "(satuan belum diisi)"] += max(v["free"], 0)
    for u, q in sorted(by_unit.items()):
        got = ((dall or {}).get("metrics") or {}).get("available_by_unit", {}).get(u)
        if got is not None or q > 0.004:
            rows.append(("dasbor KPI Semua PT per satuan", u, u, "all", r2(got), r2(q), r2(r2(got) - r2(q)), "STK-8"))
    # RFID summary — roll belum ber-tag (STK-14), akun admin PT aktif KSC
    st, rs = api.call("/api/rfid/summary", ADMIN)
    phys_untag = db.inventory_rolls.count_documents({"owner_entity_id": {"$in": ["ent_ksc"]}, "length_remaining": {"$gt": 0},
                                                     "status": {"$in": list(PHYS) + ["allocated", "in_transit_sales",
                                                                                     "in_transit_transfer", "receiving"]},
                                                     "$or": [{"rfid_tag_id": None}, {"rfid_tag_id": {"$exists": False}}, {"rfid_tag_id": ""}]})
    rows.append(("rfid/summary untagged_rolls", "KSC", "roll", "ent_ksc", r2((rs or {}).get("untagged_rolls")), r2(phys_untag),
                 r2(r2((rs or {}).get("untagged_rolls")) - phys_untag), "STK-14"))
    # Dua angka per peran (endpoint baru — hanya bila ada)
    role_rows = []
    probe = api.call(f"/api/stock/figures?product_ids={pids[0]}", ADMIN)
    if probe[0] == 200:
        for email in ACCOUNTS:
            if email not in api.tokens:
                continue
            st, fb = api.call(f"/api/stock/figures?product_ids={','.join(pids)}", email)
            if st != 200:
                role_rows.append((email, st, None))
                continue
            sc = fb["scope"]
            ents_l = set(sc.get("entity_ids") or [])
            wset = None
            if sc.get("site_ids"):
                wset = set().union(*[site_whs.get(s, set()) for s in sc["site_ids"]])
            role_rows.append((email, st, sc))
            for pid, f in (fb.get("items") or {}).items():
                exp_l = agg(seg, pid, ents_l, wset)
                exp_g = agg(seg, pid)
                rows.append((f"dua angka LOKAL [{email.split('@')[0]}]", skus.get(pid, pid), units.get(pid, ""), sc.get("label"),
                             r2(f["local"]["qty"]), exp_l["qty"], r2(r2(f["local"]["qty"]) - exp_l["qty"]), "qty"))
                rows.append((f"dua angka LOKAL roll [{email.split('@')[0]}]", skus.get(pid, pid), "roll", sc.get("label"),
                             r2(f["local"]["rolls"]), exp_l["rolls"], r2(f["local"]["rolls"] - exp_l["rolls"]), "roll"))
                rows.append((f"dua angka GLOBAL [{email.split('@')[0]}]", skus.get(pid, pid), units.get(pid, ""), "all",
                             r2(f["global"]["qty"]), exp_g["qty"], r2(r2(f["global"]["qty"]) - exp_g["qty"]), "qty"))
            # rincian satu produk: Σ per PT dan Σ per site = GLOBAL
        for pid in pids[:8]:
            st, d = api.call(f"/api/stock/figures/{pid}", ADMIN)
            if st != 200:
                continue
            g = agg(seg, pid)
            rows.append(("rincian Σ per PT", skus.get(pid, pid), units.get(pid, ""), "all",
                         r2(sum(x["available_qty"] for x in d["by_entity"])), g["qty"],
                         r2(sum(x["available_qty"] for x in d["by_entity"]) - g["qty"]), ""))
            rows.append(("rincian Σ per site", skus.get(pid, pid), units.get(pid, ""), "all",
                         r2(sum(x["available_qty"] for x in d["by_site"])), g["qty"],
                         r2(sum(x["available_qty"] for x in d["by_site"]) - g["qty"]), ""))
    out = []
    out.append("| kelompok endpoint | SKU | satuan | PT/cakupan | angka endpoint | acuan roll | selisih |")
    out.append("|---|---|---|---|---:|---:|---:|")
    nd = 0
    by = defaultdict(lambda: [0, 0])
    for r in rows:
        by[r[0].split(" [")[0]][0] += 1
        if abs(r[6]) > EPS:
            nd += 1
            by[r[0].split(" [")[0]][1] += 1
            out.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | **{r[6]}** |")
    out.append("")
    out.append(f"**{len(rows)} perbandingan, {nd} berselisih** (|Δ| > 0,01).")
    out.append("")
    out.append("| kelompok endpoint | dibandingkan | berselisih |")
    out.append("|---|---:|---:|")
    for k, (n, d) in sorted(by.items()):
        out.append(f"| {k} | {n} | {d} |")
    if role_rows:
        out.append("")
        out.append("| akun | HTTP | cakupan LOKAL |")
        out.append("|---|---|---|")
        for email, st, sc in role_rows:
            out.append(f"| {email.split('@')[0]} | {st} | {(sc or {}).get('label')} · site={(sc or {}).get('site_ids')} · PT={(sc or {}).get('entity_ids')} |")
    txt = "\n".join(out)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(txt)
    print(txt)
    print(f"\n{len(rows)} perbandingan, {nd} berselisih", file=sys.stderr)


if __name__ == "__main__":
    main()
