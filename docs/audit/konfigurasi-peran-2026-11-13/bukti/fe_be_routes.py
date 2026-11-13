"""Cocokkan setiap panggilan API di frontend dengan rute backend (statik)."""
import os, re, json, sys, collections
from pathlib import Path
FE = str(Path(__file__).resolve().parents[4] / "frontend" / "src")
INV = json.load(open(sys.argv[1]))
def norm(p):
    p = p.split("?")[0]
    p = re.sub(r"\$\{[^}]*\}", "{}", p)
    p = re.sub(r"\{[^}]*\}", "{}", p)
    p = re.sub(r"/+$", "", p)
    return p
routes = collections.defaultdict(set)
for r in INV:
    p = norm(r["path"])
    if p.startswith("/api"): p = p[4:]
    routes[p].add(r["method"])
route_res = [(re.compile("^" + re.escape(p).replace(r"\{\}", r"[^/]+") + "$"), p) for p in routes]
def find(path):
    if path in routes: return path
    # panggilan dengan segmen dinamis di tengah: cocokkan pola
    cand = [p for rx, p in route_res if rx.match(path.replace("{}", "x"))]
    return cand[0] if cand else None
calls = []
rx_call = re.compile(r"(?:axios|api|http|client)\s*\.\s*(get|post|put|patch|delete)\s*(?:<[^>]*>)?\(\s*`\$\{(?:API|API_BASE|BASE|api)\}([^`]*)`", re.I)
rx_any = re.compile(r"`\$\{API\}(/[^`]*)`")
for root, dirs, files in os.walk(FE):
    dirs[:] = [d for d in dirs if d not in ("node_modules", "__tests__")]
    for f in files:
        if not f.endswith((".js", ".jsx")) or f.endswith(".test.js"): continue
        p = os.path.join(root, f); txt = open(p, encoding="utf-8", errors="ignore").read()
        seen = set()
        for m in rx_call.finditer(txt):
            line = txt[:m.start()].count("\n") + 1
            calls.append((m.group(1).upper(), norm(m.group(2)), os.path.relpath(p, FE), line)); seen.add(m.start(2))
        for m in rx_any.finditer(txt):
            if m.start(1) in seen: continue
            line = txt[:m.start()].count("\n") + 1
            calls.append(("?", norm(m.group(1)), os.path.relpath(p, FE), line))
print("panggilan API di frontend:", len(calls), "| unik:", len({(c[0], c[1]) for c in calls}))
miss, wrong = [], []
for meth, path, f, line in calls:
    if "{}" == path or not path.startswith("/"): continue
    hit = find(path)
    if not hit:
        # jalur yang diakhiri segmen dinamis gabungan (mis. `/x/${a}${b}`) dilewati bila awalan cocok
        miss.append((meth, path, f, line)); continue
    if meth != "?" and meth not in routes[hit]: wrong.append((meth, path, sorted(routes[hit]), f, line))
print("TIDAK ADA rute:", len(miss)); 
for x in sorted(set(miss), key=lambda x: (x[2], x[3]))[:70]: print("   %-6s %-58s %s:%d" % x)
print("METODE berbeda:", len(wrong))
for x in sorted(set((w[0], w[1], tuple(w[2]), w[3], w[4]) for w in wrong), key=lambda x: (x[3], x[4]))[:40]: print("   %-6s %-50s ada=%s %s:%d" % x)
