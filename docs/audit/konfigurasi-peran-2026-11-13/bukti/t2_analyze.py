import json, re, collections, sys
SP = sys.argv[1]
T = json.load(open(SP + "/t2_roles.json")); INV = json.load(open(SP + "/endpoints.json"))
def tmpl(p): return re.sub(r"\{[^}]+\}", "{}", p)
inv = {}
for r in INV:
    if r["method"] == "GET": inv.setdefault(tmpl(r["path"]), r)
def pairs(e):
    out = set()
    for g in e["guards"]:
        if g["k"] == "require_permission" and len(g["a"]) >= 2 and all(isinstance(x, str) for x in g["a"][:2]): out.add((g["a"][0], g["a"][1]))
        if g["k"] == "require_any_permission" and g["a"] and isinstance(g["a"][0], list):
            for x in g["a"][0]:
                if isinstance(x, (list, tuple)) and len(x) == 2: out.add((x[0], x[1]))
    return out
def has(perms, pair):
    a = perms.get(pair[0]) or []
    return pair[1] in a or "*" in a
def klass(st, det):
    if st == 403 and ("Permission ditolak" in det or "Role Anda tidak" in det): return "TOLAK_GERBANG"
    if st == 403: return "TOLAK_LAIN"
    if st == 401: return "401"
    if st == 422: return "422"
    if st >= 500 or st < 0: return "GALAT"
    return "LOLOS"
roles = T["roles"]; res = T["results"]
print("peran:", {k: (v["label"], v["base_role"]) for k, v in roles.items() if v["custom"]})
print("buat peran kustom:", {k: v["status"] for k, v in T["custom"].items()})
A = collections.defaultdict(list); B = collections.defaultdict(list); unmatched = set()
for rid, rr in res.items():
    perms = roles[rid]["permissions"]
    for path, (st, det) in rr.items():
        e = inv.get(tmpl(path))
        if not e: unmatched.add(path); continue
        if e["cat"] != "IZIN": continue
        ps = pairs(e)
        if not ps: continue
        k = klass(st, det)
        anyp = any(has(perms, p) for p in ps); allp = all(has(perms, p) for p in ps)
        if rid != "admin" and not anyp and k == "LOLOS": A[path].append((rid, st))
        if allp and k == "TOLAK_GERBANG": B[path].append((rid, det[:70]))
        if allp and k == "TOLAK_LAIN": B[path].append((rid, "LAIN: " + det[:60]))
print("rute GET:", T["get_count"], "| tak terpetakan ke inventaris:", len(unmatched))
print("\n== A. LOLOS tanpa satu pun izin yang disebut endpoint:", len(A))
for p, l in sorted(A.items())[:60]:
    print("  %-62s %s  izin=%s" % (p.replace("/api","")[:62], ",".join(sorted({x[0] for x in l}))[:70], sorted(pairs(inv[tmpl(p)]))[:2]))
print("\n== B. DITOLAK padahal punya semua izin yang disebut endpoint:", len(B))
for p, l in sorted(B.items())[:70]:
    print("  %-58s %s | %s" % (p.replace("/api","")[:58], ",".join(sorted({x[0] for x in l}))[:60], l[0][1]))
json.dump({"A": A, "B": B}, open(SP + "/t2_mismatch.json", "w"), ensure_ascii=False)
