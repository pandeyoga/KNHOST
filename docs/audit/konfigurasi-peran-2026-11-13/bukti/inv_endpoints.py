"""Inventaris gerbang tiap endpoint (statik, AST). Keluaran: JSON + ringkasan."""
import ast, json, os, re, sys, collections
from pathlib import Path
BACKEND = str(Path(__file__).resolve().parents[4] / "backend")
PRIMS = {"require_permission", "require_any_permission", "require_role", "current_user", "has_permission"}
HTTP = {"get", "post", "put", "patch", "delete"}

def py_files():
    for root, dirs, files in os.walk(BACKEND):
        dirs[:] = [d for d in dirs if d not in ("tests", "__pycache__", "tools", "data")]
        for f in files:
            if f.endswith(".py") and not re.match(r"(test_|backend_test|_smoke|_fase)", f):
                yield os.path.join(root, f)

def call_name(node):
    f = node.func
    if isinstance(f, ast.Name): return f.id
    if isinstance(f, ast.Attribute): return f.attr
    return ""

def lit(node):
    try: return ast.literal_eval(node)
    except Exception: return None

# 1) peta fungsi -> panggilan langsung (nama) + primitif dengan argumen
funcs = {}   # name -> list of dict(file, prims[], calls set)
trees = {}
for p in py_files():
    try:
        t = ast.parse(open(p, encoding="utf-8").read())
    except Exception as e:
        print("gagal parse", p, e, file=sys.stderr); continue
    trees[p] = t
    for node in ast.walk(t):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            prims, calls = [], set()
            for c in ast.walk(node):
                if isinstance(c, ast.Call):
                    n = call_name(c)
                    if n in PRIMS:
                        args = [lit(a) for a in c.args[1:]]
                        prims.append((n, args))
                    elif n:
                        calls.add(n)
            funcs.setdefault(node.name, []).append({"file": p, "prims": prims, "calls": calls})

# hanya ikuti pembantu yang menerima `request` atau namanya berbau penjaga, satu–dua tingkat
REQ_FUNCS = set()
for _p, _t in trees.items():
    for _n in ast.walk(_t):
        if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(a.arg == "request" for a in _n.args.args):
            REQ_FUNCS.add(_n.name)
_memo = {}
def helper_prims(name, depth=0, seen=None):
    if depth == 0 and name in _memo: return _memo[name]
    seen = seen if seen is not None else set()
    if name in seen or depth > 3 or name not in funcs or name not in REQ_FUNCS: return []
    seen.add(name)
    out = []
    for d in funcs[name]:
        out += [(k, a, name) for k, a in d["prims"]]
        for c in d["calls"]:
            if c in REQ_FUNCS:
                out += helper_prims(c, depth + 1, seen)
    if depth == 0: _memo[name] = out
    return out

rows = []
for p, t in trees.items():
    if "/routers/" not in p and not p.endswith("server.py"): continue
    prefix = ""
    for node in ast.walk(t):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and call_name(node.value) == "APIRouter":
            for kw in node.value.keywords:
                if kw.arg == "prefix": prefix = lit(kw.value) or ""
    for node in t.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)): continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in HTTP:
                path = lit(dec.args[0]) if dec.args else ""
                guards = []
                for c in ast.walk(node):
                    if isinstance(c, ast.Call):
                        n = call_name(c)
                        if n in PRIMS:
                            guards.append({"k": n, "a": [lit(a) for a in c.args[1:]], "via": ""})
                        elif n in funcs:
                            for k, a, via in helper_prims(n):
                                guards.append({"k": k, "a": a, "via": via})
                # Depends(...) di parameter
                for d in list(node.args.defaults) + list(node.args.kw_defaults):
                    if isinstance(d, ast.Call) and call_name(d) == "Depends" and d.args:
                        n = d.args[0].id if isinstance(d.args[0], ast.Name) else ""
                        if n in PRIMS: guards.append({"k": n, "a": [], "via": "Depends"})
                        else:
                            for k, a, via in helper_prims(n): guards.append({"k": k, "a": a, "via": via})
                kinds = {g["k"] for g in guards}
                if kinds & {"require_permission", "require_any_permission"}: cat = "IZIN"
                elif "require_role" in kinds: cat = "PERAN"
                elif "has_permission" in kinds and "current_user" in kinds: cat = "IZIN_CABANG"
                elif "current_user" in kinds: cat = "LOGIN"
                else: cat = "TANPA"
                rows.append({"method": dec.func.attr.upper(), "path": (prefix or "") + (path or ""),
                             "file": os.path.relpath(p, BACKEND), "line": node.lineno, "func": node.name,
                             "cat": cat, "guards": guards})
json.dump(rows, open(sys.argv[1], "w"), ensure_ascii=False, indent=0, default=str)
cnt = collections.Counter(r["cat"] for r in rows)
print("endpoint:", len(rows), dict(cnt))
bymeth = collections.Counter((r["cat"], r["method"] in ("GET",)) for r in rows)
print("per kategori (baca?):", {f"{k[0]}:{'baca' if k[1] else 'tulis'}": v for k, v in sorted(bymeth.items())})
