#!/usr/bin/env python3
"""B3a (audit 2026-11-09) — bandingkan angka stok tiap endpoint dengan hitungan langsung dari roll (truth.json).

Masukan: truth.json (b3a_stock_truth.js), folder api/ (b3a_api_fetch.py), sample_pids.json (opsional).
"Kebenaran" dihitung per produk × PT dari segmen roll:
  avail_bal  = Σ len(status=available ∧ ¬klaim PA) − Σ length_reserved  (= ember available_qty saldo)
  k04        = avail_bal (gudang terdaftar) − cadangan makloon PT (dibatasi ≥ 0)      — definisi K-04 (D1)
  raw_avail  = Σ len(status=available) tanpa mengurangi apa pun                       — rumus D4/D7/D8
  physical   = Σ len status fisik (available, reserved, committed, picked, packed, hold, wip, quarantine, blocked, damaged)
Keluaran: tabel markdown selisih per produk/endpoint ke stdout.
"""
import json
import os
import sys
from collections import defaultdict

PHYS = {"available", "reserved", "committed", "picked", "packed", "hold", "wip", "quarantine", "blocked", "damaged"}
ENTS = ["ent_ksc", "ent_kanda", "ent_82b52ed6ee8b"]
SITE_OF = {}


def load(api, name):
    p = os.path.join(api, f"admin__{name}.json")
    if not os.path.exists(p):
        return None
    d = json.load(open(p, encoding="utf-8"))
    return d["body"] if d.get("status") == 200 else {"_status": d.get("status"), "_body": d.get("body")}


def r2(x):
    return round(float(x or 0), 2)


def main():
    truth = json.load(open(sys.argv[1], encoding="utf-8"))
    api = sys.argv[2]
    pids = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else list(truth["products"])
    reg = set(truth["registered"])
    rows = []
    # data global endpoint
    prods = {e: {p["id"]: p for p in (load(api, f"products_{e}") or []) if isinstance(p, dict)} for e in ENTS}
    dash = {e: {p["id"]: p for p in ((load(api, f"dashboard_{e}") or {}).get("products") or [])} for e in ENTS}
    site = {}
    for e in ENTS:
        for s in ["site_c0c8400b0017", "site_fd9f6aa41d36", "site_54bed6261604"]:
            b = load(api, f"sitestock_{s}_{e}") or {}
            site[(s, e)] = b.get("stock") or {}
    low = {(i["product_id"], i["entity_id"]): i["available"] for i in ((load(api, "lowstock_all") or {}).get("items") or [])}
    tpl = {}
    for fn in os.listdir(api):
        if fn.startswith("admin__tplsum_"):
            b = json.load(open(os.path.join(api, fn), encoding="utf-8")).get("body") or {}
            for v in b.get("variants") or []:
                tpl[v["id"]] = (v.get("available"), v.get("reserved"), v.get("rolls"))
    for pid in pids:
        segs = (truth["products"].get(pid) or {}).get("segs")
        if segs is None:
            continue
        mk = defaultdict(float)
        for m in truth["products"][pid]["makloon"]:
            mk[m["owner"]] += float(m["qty"] or 0)
        T = defaultdict(lambda: defaultdict(float))
        for s in segs:
            o = s["o"]
            if s["s"] == "available":
                T[o]["raw_avail"] += s["len"]
                if not s["am"]:
                    T[o]["avail_bal"] += s["len"] - s["lres"]
                    if s["ih"]:
                        T[o]["insp_hold"] += s["len"]
                T[o]["lres"] += s["lres"]
            if s["s"] in PHYS:
                T[o]["physical"] += s["len"]
            if s["s"] == "committed":
                T[o]["committed"] += s["len"]
            if s["s"] in ("available",) and s.get("site"):
                T[(o, s["site"])]["site_raw"] += s["len"]
                T[(o, s["site"])]["site_free"] += s["len"] - s["lres"]
        owners = sorted({s["o"] for s in segs})
        k04 = {o: r2(max(T[o]["avail_bal"] - min(mk.get(o, 0), T[o]["avail_bal"]), 0)) for o in owners}
        glob_bal = sum(T[o]["avail_bal"] for o in owners)
        glob_k04 = sum(k04.values())
        glob_d3 = max(glob_bal - sum(mk.values()), 0)
        sb = load(api, f"statusboard_{pid}") or []
        sb = sb[0] if isinstance(sb, list) and sb else {}
        bk = load(api, f"buckets_{pid}") or []
        bk = bk[0] if isinstance(bk, list) and bk else {}
        br = load(api, f"breakdown_{pid}") or {}
        ra = load(api, f"rollsavail_{pid}") or {}
        ir = load(api, f"iravail_{pid}") or {}
        sku = truth["products"][pid]["product"]["sku"]
        unit = truth["products"][pid]["product"]["base_unit"]

        def add(endpoint, owner, got, expect, note=""):
            if got is None:
                return
            d = r2(got) - r2(expect)
            rows.append((sku, unit, owner, endpoint, r2(got), r2(expect), r2(d), note))
        add("status-board total_available (semua PT)", "all", sb.get("total_available"), glob_k04, "K-04")
        for be in sb.get("by_entity") or []:
            add("status-board by_entity.available", be["entity_id"], be.get("available"), k04.get(be["entity_id"], 0), "K-04")
        add("stock/buckets totals.available_qty", "all", (bk.get("totals") or {}).get("available_qty"), glob_k04, "K-04 (D2 mentah)")
        add("stock-breakdown Σ balances.available_qty", "all", sum(float(b.get("available_qty") or 0) for b in br.get("balances") or []), glob_k04, "K-04 (D2)")
        add("stock-breakdown Σ matriks.available_qty", "all", sum(float(c.get("available_qty") or 0) for c in br.get("ownership_matrix") or []), glob_k04, "K-04 (D8)")
        add("rolls/available Σ length_remaining", "all", sum(float(i.get("length_remaining") or 0) for i in ra.get("items") or []), glob_k04, "K-04")
        add("internal-requests-availability group_available", "all", ir.get("group_available"), glob_k04, "K-04 (D2)")
        for e in ENTS:
            P = prods[e].get(pid)
            if P:
                add(f"/products available_qty (aktif {e[4:]})", "all", P.get("available_qty"), glob_k04, "K-04 vs D3 global")
                if e in owners or P.get("entity_available_qty"):
                    add(f"/products entity_available_qty (aktif {e[4:]})", e, P.get("entity_available_qty"), k04.get(e, 0), "K-04 PT")
            D = dash[e].get(pid)
            if D and (e in owners or D.get("entity_available_qty")):
                add(f"/dashboard entity_available_qty (aktif {e[4:]})", e, D.get("entity_available_qty"), k04.get(e, 0), "K-04 PT")
            atp = load(api, f"atp_{pid}_{e}") or {}
            if e in owners:
                add("stock/atp available", e, atp.get("available"), k04.get(e, 0), "K-04 PT")
            ss = load(api, f"salessum_{pid}_{e}") or {}
            reg_row = next((r for r in ss.get("rows") or [] if r.get("class") == "regular"), None)
            bs_row = next((r for r in ss.get("rows") or [] if r.get("class") == "bs"), None)
            if reg_row and e in owners:
                free = float(reg_row.get("free") or 0) + float((bs_row or {}).get("free") or 0)
                add("sales/stock-summary free (reg+BS)", e, free, k04.get(e, 0), "K-04 PT")
                phys = float(reg_row.get("physical") or 0) + float((bs_row or {}).get("physical") or 0)
                add("sales/stock-summary physical (reg+BS)", e, phys, T[e]["physical"], "fisik roll")
            if (pid, e) in low:
                add("low-stock-summary available", e, low[(pid, e)], k04.get(e, 0), "K-04 PT")
            for s in ["site_c0c8400b0017", "site_fd9f6aa41d36", "site_54bed6261604"]:
                st = site[(s, e)].get(pid)
                if st is not None:
                    exp_free = T[(e, s)]["site_free"]
                    add(f"pos/site-stock own_qty @{s[-6:]}", e, st.get("own_qty"), exp_free, "tersedia bebas di site")
        if pid in tpl:
            add("product-templates summary variant.available", "all", tpl[pid][0], glob_k04, "K-04")
        atpall = load(api, f"atp_{pid}_all") or {}
        add("stock/atp?owner=all available", "all", atpall.get("available"), glob_k04, "K-04")
    print("| SKU | satuan | PT | endpoint | angka endpoint | acuan | selisih | acuan |")
    print("|---|---|---|---|---:|---:|---:|---|")
    nd = 0
    for r in rows:
        if abs(r[6]) > 0.011:
            nd += 1
            print(f"| {r[0]} | {r[1]} | {r[2][4:] if r[2].startswith('ent_') else r[2]} | {r[3]} | {r[4]} | {r[5]} | **{r[6]}** | {r[7]} |")
    print(f"\n{len(rows)} perbandingan, {nd} berselisih (|Δ| > 0,01).", file=sys.stderr)
    by_ep = defaultdict(lambda: [0, 0])
    for r in rows:
        by_ep[r[3].split(" (")[0]][0] += 1
        if abs(r[6]) > 0.011:
            by_ep[r[3].split(" (")[0]][1] += 1
    print("\n| endpoint | dibandingkan | berselisih |\n|---|---:|---:|")
    for k, (a, b) in sorted(by_ep.items()):
        print(f"| {k} | {a} | {b} |")


if __name__ == "__main__":
    main()
