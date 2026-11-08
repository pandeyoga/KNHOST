#!/usr/bin/env python3
"""B3a (audit 2026-11-09) — pemindai STATIK operasi Mongo per koleksi & field (baca-saja, stdlib).

Tujuan: menyusun "Peta SSOT fakta → pemilik → SEMUA penulis" dan sensus koleksi yang dipakai kode,
TANPA menjalankan aplikasi. Memakai `ast` (bukan grep) supaya panggilan multi-baris tertangkap.

Yang ditangkap untuk setiap panggilan `<h>.<koleksi>.<op>(...)` / `<h>["<koleksi>"].<op>(...)`
(`<h>` = nama apa pun yang berakhiran `db`/`mongo`/`dbx`, mis. db, _db, mdb, mongo):
  * koleksi, operasi, berkas:baris, fungsi pembungkus, jenis berkas (app | script | test)
  * field yang DITULIS (kunci di bawah $set/$inc/$unset/$push/$pull/$addToSet/$setOnInsert/$max/$min,
    atau kunci akar dokumen insert/replace) — termasuk bila argumennya variabel yang dirakit di fungsi yang
    sama (`doc = {...}`, `doc["k"] = ...`, `doc.update({...})`, `upd["$set"]["k"] = ...`)
  * nilai konstanta `status` / `journey.stage` yang ditulis
  * kunci filter (untuk baca maupun tulis)

Pemakaian:
  python scripts/audit/b3a_db_writers.py --json out.json           # semua koleksi
  python scripts/audit/b3a_db_writers.py --coll inventory_rolls --field status --kind app
Keluaran ringkas ke stdout; --json menulis daftar lengkap panggilan.
Keterbatasan (sengaja dicatat): dict yang dirakit lintas fungsi / dari parameter → field "?";
pemanggilan dinamis `db[var]` dicatat sebagai koleksi "<dinamis>".
"""
import argparse
import ast
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WRITE_OPS = {"insert_one", "insert_many", "update_one", "update_many", "find_one_and_update",
             "find_one_and_replace", "replace_one", "delete_one", "delete_many", "bulk_write",
             "find_one_and_delete"}
READ_OPS = {"find", "find_one", "aggregate", "count_documents", "distinct", "estimated_document_count"}
UPD_OPS = {"$set", "$inc", "$unset", "$push", "$pull", "$addToSet", "$setOnInsert", "$max", "$min",
           "$pullAll", "$rename", "$mul", "$currentDate"}
HANDLE_RE = re.compile(r"(^|_)(db|mongo|dbx|mdb|tdb)$")
SKIP_DIRS = {"node_modules", "__pycache__", ".git", "frontend", "middleware", "test_reports", "_legacy"}


def file_kind(rel: str) -> str:
    base = os.path.basename(rel)
    low = rel.replace("\\", "/").lower()
    if (base.startswith("test_") or base.endswith("_test.py") or base.startswith("backend_test")
            or "/tests/" in low or low.startswith("tests/") or base.startswith("poc_") or "_poc" in base
            or base.startswith("_smoke") or base.startswith("probe_") or "/test" in low.split("backend/")[-1][:6]):
        return "test"
    if (base.startswith(("seed", "migrate", "fix_", "backfill", "_fase", "demo_seed")) or "/scripts/" in low
            or low.startswith("scripts/") or base in ("bootstrap_demo.py",)):
        return "script"
    if low.startswith("backend/"):
        return "app"
    return "script"


def handle_and_coll(node, consts=None):
    """node = func.value of `<h>.<coll>.<op>`; return (handle, coll) or None.
    `consts` = konstanta string tingkat modul (mis. `LEDGER = 'rfid_v2_gate_txn'` -> `db[LEDGER]`)."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and HANDLE_RE.search(node.value.id):
        return node.value.id, node.attr
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute) and node.value.attr == "db":
        return "self.db", node.attr
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and HANDLE_RE.search(node.value.id):
        s = node.slice
        if isinstance(s, ast.Constant) and isinstance(s.value, str):
            return node.value.id, s.value
        if isinstance(s, ast.Name) and consts and s.id in consts:
            return node.value.id, consts[s.id]
        return node.value.id, "<dinamis>"
    return None


def const_str(n):
    return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else None


class FuncCtx:
    """Kumpulan perakitan dict per nama variabel dalam satu fungsi."""

    def __init__(self, fn):
        self.assign = defaultdict(list)       # name -> [Dict nodes]
        self.sub = defaultdict(list)          # name -> [(key or None, value node, subkey path)]
        if fn is None:
            return
        for n in ast.walk(fn):
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Name) and isinstance(n.value, (ast.Dict, ast.Call)):
                        self.assign[t.id].append(n.value)
                    elif isinstance(t, ast.Subscript):
                        chain = []
                        cur = t
                        while isinstance(cur, ast.Subscript):
                            chain.append(const_str(cur.slice))
                            cur = cur.value
                        if isinstance(cur, ast.Name):
                            chain.reverse()
                            self.sub[cur.id].append((chain, n.value))
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("update", "setdefault"):
                tgt = n.func.value
                chain = []
                while isinstance(tgt, ast.Subscript):
                    chain.append(const_str(tgt.slice))
                    tgt = tgt.value
                if isinstance(tgt, ast.Call) and isinstance(tgt.func, ast.Attribute) and tgt.func.attr == "setdefault":
                    chain.append(const_str(tgt.args[0]) if tgt.args else None)
                    tgt = tgt.func.value
                if isinstance(tgt, ast.Name):
                    chain.reverse()
                    if n.func.attr == "update" and n.args and isinstance(n.args[0], ast.Dict):
                        self.sub[tgt.id].append((chain + ["**update"], n.args[0]))
                    elif n.func.attr == "setdefault" and n.args:
                        k = const_str(n.args[0])
                        if len(n.args) > 1:
                            self.sub[tgt.id].append((chain + [k], n.args[1]))


def dict_keys(d, ctx, depth=0):
    """Kembalikan {key: valuenode} dari Dict / dict(...) / Name terakit."""
    out = {}
    if depth > 4 or d is None:
        return out
    if isinstance(d, ast.Dict):
        for k, v in zip(d.keys, d.values):
            if k is None:  # **spread
                if isinstance(v, ast.Name):
                    out.update(dict_keys(v, ctx, depth + 1))
                else:
                    out["**"] = v
            else:
                ks = const_str(k)
                out[ks if ks is not None else "?"] = v
    elif isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "dict":
        for a in d.args:
            out.update(dict_keys(a, ctx, depth + 1))
        for kw in d.keywords:
            if kw.arg:
                out[kw.arg] = kw.value
            else:
                out["**"] = kw.value
    elif isinstance(d, ast.Name):
        found = False
        for node in ctx.assign.get(d.id, []):
            out.update(dict_keys(node, ctx, depth + 1))
            found = True
        for chain, val in ctx.sub.get(d.id, []):
            found = True
            if not chain:
                continue
            if chain[-1] == "**update":
                sub = chain[:-1]
                for k2, v2 in dict_keys(val, ctx, depth + 1).items():
                    key = ".".join([c or "?" for c in sub] + [k2])
                    out[key] = v2
            else:
                out[".".join(c or "?" for c in chain)] = val
        if not found:
            out["?"] = d
    elif isinstance(d, ast.List):
        # pipeline update [{"$set": ...}]
        for e in d.elts:
            out.update(dict_keys(e, ctx, depth + 1))
    else:
        out["?"] = d
    return out


def written_fields(op, args, kws, ctx):
    """-> (fields set, status values list, stage values)"""
    fields, statuses = set(), []
    doc = None
    if op in ("insert_one", "replace_one", "find_one_and_replace"):
        doc = args[0] if op == "insert_one" and args else (args[1] if len(args) > 1 else None)
        keys = dict_keys(doc, ctx)
        for k, v in keys.items():
            fields.add(k)
            if k == "status":
                statuses.append(const_str(v) or "<expr>")
        return fields, statuses
    if op == "insert_many":
        doc = args[0] if args else None
        if isinstance(doc, ast.List) and doc.elts:
            keys = dict_keys(doc.elts[0], ctx)
        elif isinstance(doc, ast.ListComp):
            keys = dict_keys(doc.elt, ctx)
        else:
            keys = {"?": doc}
        for k, v in keys.items():
            fields.add(k)
            if k == "status":
                statuses.append(const_str(v) or "<expr>")
        return fields, statuses
    if op in ("update_one", "update_many", "find_one_and_update"):
        upd = args[1] if len(args) > 1 else next((k.value for k in kws if k.arg == "update"), None)
        top = dict_keys(upd, ctx)
        for k, v in top.items():
            if k in UPD_OPS:
                for k2, v2 in dict_keys(v, ctx).items():
                    fields.add(k2)
                    if k2 == "status" and k != "$unset":
                        statuses.append(const_str(v2) or "<expr>")
            elif "." in k and k.split(".")[0] in UPD_OPS:
                k2 = k.split(".", 1)[1]
                fields.add(k2)
                if k2 == "status":
                    statuses.append(const_str(v) or "<expr>")
            elif k == "?":
                fields.add("?")
            else:
                fields.add(k)
                if k == "status":
                    statuses.append(const_str(v) or "<expr>")
        return fields, statuses
    if op in ("delete_one", "delete_many", "find_one_and_delete"):
        return {"<hapus dokumen>"}, statuses
    if op == "bulk_write":
        return {"<bulk>"}, statuses
    return fields, statuses


def filter_keys(op, args, ctx):
    if not args:
        return []
    if op == "aggregate":
        return ["<pipeline>"]
    return sorted(k for k in dict_keys(args[0], ctx) if k not in ("?",))


def scan_file(path, rel):
    try:
        src = open(path, encoding="utf-8", errors="ignore").read()
        tree = ast.parse(src)
    except Exception:
        return []
    out = []
    consts = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    consts[t.id] = n.value.value
    parents = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            parents[c] = n

    def enclosing(n):
        while n in parents:
            n = parents[n]
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return n
        return None

    ctx_cache = {}
    kind = file_kind(rel)

    def coll_of_expr(e):
        """`collection('x')` (helper rfid_v2) atau `db.x` / `db['x']` → nama koleksi."""
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id == "collection" and e.args:
            a0 = e.args[0]
            if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
                return a0.value
            if isinstance(a0, ast.Name) and a0.id in consts:
                return consts[a0.id]
            return "<dinamis>"
        hc0 = handle_and_coll(e, consts)
        return hc0[1] if hc0 else None

    alias_cache = {}

    def aliases(fn):
        """var lokal yang menunjuk koleksi: `c = collection('x')` / `c = db.x`."""
        if fn in alias_cache:
            return alias_cache[fn]
        m = {}
        for a in (ast.walk(fn) if fn is not None else tree.body):
            if isinstance(a, ast.Assign) and len(a.targets) == 1 and isinstance(a.targets[0], ast.Name):
                c0 = coll_of_expr(a.value)
                if c0:
                    m[a.targets[0].id] = c0
        alias_cache[fn] = m
        return m

    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
            continue
        op = n.func.attr
        if op not in WRITE_OPS and op not in READ_OPS:
            continue
        hc = handle_and_coll(n.func.value, consts)
        if not hc:
            c1 = coll_of_expr(n.func.value)
            if not c1 and isinstance(n.func.value, ast.Name):
                c1 = aliases(enclosing(n)).get(n.func.value.id)
            hc = ("collection()", c1) if c1 else None
        if not hc:
            continue
        handle, coll = hc
        if coll in ("command", "client", "name", "list_collection_names"):
            continue
        fn = enclosing(n)
        if fn not in ctx_cache:
            ctx_cache[fn] = FuncCtx(fn)
        ctx = ctx_cache[fn]
        rec = {"coll": coll, "op": op, "file": rel.replace("\\", "/"), "line": n.lineno,
               "func": fn.name if fn else "<modul>", "kind": kind, "rw": "w" if op in WRITE_OPS else "r",
               "filter": filter_keys(op, n.args, ctx)}
        if op in WRITE_OPS:
            f, st = written_fields(op, n.args, n.keywords, ctx)
            rec["fields"] = sorted(f)
            rec["status_values"] = st
        out.append(rec)
    return out


def iter_py(root=ROOT):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for f in files:
            if f.endswith(".py"):
                p = os.path.join(base, f)
                yield p, os.path.relpath(p, root)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--coll")
    ap.add_argument("--field")
    ap.add_argument("--kind", default="")
    ap.add_argument("--rw", default="w")
    ap.add_argument("--root", default=ROOT, help="akar pohon kode yang dipindai (mis. hasil `git archive main`)")
    a = ap.parse_args()
    recs = []
    for p, rel in iter_py(os.path.abspath(a.root)):
        recs.extend(scan_file(p, rel))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(recs, fh, ensure_ascii=False, indent=0)
    sel = [r for r in recs if (not a.coll or r["coll"] == a.coll) and (not a.kind or r["kind"] in a.kind.split(","))
           and (a.rw == "rw" or r["rw"] == a.rw)]
    if a.field:
        sel = [r for r in sel if any(f == a.field or f.startswith(a.field + ".") or f in ("?", "**", "<bulk>")
                                     for f in r.get("fields", []))]
    for r in sorted(sel, key=lambda r: (r["file"], r["line"])):
        extra = ""
        if r.get("status_values"):
            extra = " status=" + "|".join(r["status_values"])
        print(f"{r['kind']:6s} {r['op']:20s} {r['file']}:{r['line']} [{r['func']}]{extra} "
              f"fields={','.join(r.get('fields', []))[:160]} filter={','.join(r['filter'])[:80]}")
    print(f"# {len(sel)} panggilan (dari {len(recs)} total)", file=sys.stderr)


if __name__ == "__main__":
    main()
