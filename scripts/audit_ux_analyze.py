"""Olah hasil audit_ux_crawl.py → temuan terstruktur (JSON + ringkasan markdown).
  python scripts/audit_ux_analyze.py <crawl_dir> [<crawl_dir> ...]
"""
import json
import re
import sys
from collections import defaultdict

SETTING_RE = re.compile(r"(pengaturan|konfigurasi|config|setelan|profil|\bmode\b|aturan|kebijakan|template|biaya|sampel uji|ambang|parameter|"
                        r"rule|policy|setup|shift|geofence|kalibrasi|perangkat|integrasi|format|tarif)", re.I)
PAIRS = [("masuk", "keluar"), ("terima", "kirim"), ("inbound", "outbound"), ("penerimaan", "pengiriman")]
COUNT_RE = re.compile(r"(\d+)\s*$")


def is_list(s):
    return (s.get("rows") or 0) + (s.get("listRows") or 0) > 0 or s.get("empty")


def analyze(path):
    data = json.load(open(f"{path}/crawl.json"))
    F = defaultdict(list)
    for rec in sorted(data, key=lambda r: r["view"]):
        v = rec["view"]
        if rec.get("error"):
            F["gagal_buka"].append({"view": v, "err": rec["error"]})
        if rec.get("pageerrors"):
            F["js_error"].append({"view": v, "err": rec["pageerrors"][:2]})
        for s in rec["states"]:
            if s.get("error") or "title" not in s:
                if s.get("error"):
                    F["tab_gagal_dibuka"].append({"view": v, "tab": s.get("tab"), "err": s["error"]})
                continue
            where = f"{v}" + (f" › {s['tab']}" if s.get("tab") else "")
            lst = is_list(s)
            n = (s.get("rows") or 0) or (s.get("listRows") or 0)
            if lst and not s["searches"]:
                F["daftar_tanpa_search"].append({"where": where, "rows": n})
            if lst and not s["searches"] and not s["chips"] and not s["selects"] and not s["dates"]:
                F["daftar_tanpa_filter_dan_search"].append({"where": where, "rows": n})
            if n >= 20 and not s.get("pager"):
                F["daftar_panjang_tanpa_paginasi"].append({"where": where, "rows": n})
            for st in s.get("search_test") or []:
                if st.get("works") is False:
                    F["search_tidak_bekerja"].append({"where": where, "placeholder": st["ph"], "rows": st["before"], "rows_setelah_kata_acak": st["junk"]})
            for g in s.get("filters") or []:
                res = [r for r in g["results"] if "error" not in r]
                if len(res) < 2:
                    continue
                base = res[0]["after"] if res else 0
                for r in res[1:]:
                    m = COUNT_RE.search(r["label"])
                    badge = int(m.group(1)) if m and not re.search(r"\d{4}", r["label"]) else None
                    if base and not r["changed"] and not r["empty"]:
                        F["filter_tidak_mengubah_daftar"].append({"where": where, "filter": r["label"], "rows": r["after"]})
                    elif badge is not None and badge <= 20 and r["after"] != badge and not (badge == 0 and r["empty"]):
                        F["badge_filter_beda_dengan_isi"].append({"where": where, "filter": r["label"], "badge": badge, "rows": r["after"]})
            for g in s["tabs"]:
                for lab in g["labels"]:
                    if SETTING_RE.search(lab or "") and not v.startswith(("settings", "admin", "permission", "approval-rules", "entity-masters", "domain-registry", "pdf-templates", "doc-templates", "entities-access", "scheduler")):
                        F["tab_bernuansa_pengaturan_di_menu_operasional"].append({"where": v, "tab": lab})
            s["_sig"] = {"search": [(x["w"], x["sig"], x["icon"]) for x in s["searches"]], "kpi": len(s["kpis"]),
                         "tabs": [(t["hub"], t["sig"]) for t in s["tabs"]], "chips": bool(s["chips"]), "pager": s["pager"]}
        labels = []
        for s in rec["states"]:
            for g in s.get("tabs") or []:
                labels += [(g["hub"], s.get("tab") or "", lab) for lab in g["labels"]]
        for a, b in PAIRS:
            la = [x for x in labels if a in (x[2] or "").lower()]
            lb = [x for x in labels if b in (x[2] or "").lower()]
            if la and lb:
                lvl = lambda x: 0 if x[0] else (1 if not x[1] else 2)  # noqa: E731
                if {lvl(x) for x in la} != {lvl(x) for x in lb}:
                    F["konteks_sama_beda_level_tab"].append({"view": v, a: [x[2] for x in la][:3], b: [x[2] for x in lb][:3]})
    dedup = {}
    for k, items in F.items():
        seen, out = set(), []
        for it in items:
            key = json.dumps(it, sort_keys=True)
            if key not in seen:
                seen.add(key)
                out.append(it)
        dedup[k] = out
    sigs = {}
    for rec in data:
        s0 = next((s for s in rec["states"] if "title" in s), None)
        if s0:
            sigs[rec["view"]] = {"title": s0["title"], "kpi": len(s0["kpis"]), "search": [(x["w"], x["y"], x["sig"][:80]) for x in s0["searches"]],
                                 "tabs": [(t["hub"], t["y"], t["sig"][:60], t["labels"][:8]) for t in s0["tabs"]], "chips": [c["labels"][:8] for c in s0["chips"]],
                                 "selects": len(s0["selects"]), "rows": s0["rows"], "listRows": s0["listRows"], "pager": s0["pager"], "heads": s0["heads"][:3],
                                 "inner_tabs": [s.get("tab") for s in rec["states"][1:]]}
    json.dump({"findings": dedup, "signatures": sigs}, open(f"{path}/findings.json", "w"), ensure_ascii=False, indent=1)
    print(f"== {path}: {len(data)} view, {sum(len(r['states']) for r in data)} state")
    for k, items in sorted(dedup.items()):
        print(f"  {k}: {len(items)}")


for p in sys.argv[1:]:
    analyze(p)
