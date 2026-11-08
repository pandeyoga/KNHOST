#!/usr/bin/env python3
"""B3a (audit 2026-11-09) — endpoint GET yang MENULIS (efek samping) — pemindai statik (stdlib).

Untuk setiap fungsi ber-dekorator `@router.get(...)` di backend/routers: catat
  (a) operasi tulis Mongo LANGSUNG di badan fungsi (insert/update/delete/replace/find_one_and_*), dan
  (b) panggilan ke fungsi layanan yang dikenal menulis stok/dokumen (daftar KNOWN_WRITERS, transitif satu tingkat
      dihitung dari peta fungsi→tulis hasil pemindaian semua modul services/).
Keluaran: daftar `routers/x.py:baris GET /path -> penulis`.
"""
import ast
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WRITE_OPS = {"insert_one", "insert_many", "update_one", "update_many", "find_one_and_update", "replace_one",
             "delete_one", "delete_many", "find_one_and_replace", "find_one_and_delete", "bulk_write"}


def writes_in(fn):
    out = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in WRITE_OPS:
            v = n.func.value
            coll = v.attr if isinstance(v, ast.Attribute) else (getattr(getattr(v, "slice", None), "value", "?") if isinstance(v, ast.Subscript) else "?")
            if coll in ("sessions", "audit_logs", "login_attempts", "idempotency_keys", "notifications", "ai_usage_log", "export_jobs"):
                continue
            out.append(f"{coll}.{n.func.attr}@{n.lineno}")
    return out


def called_names(fn):
    names = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute):
                names.add(f.attr)
            elif isinstance(f, ast.Name):
                names.add(f.id)
    return names


def main():
    svc_writers = {}
    for base, _, files in os.walk(os.path.join(ROOT, "backend", "services")):
        for f in files:
            if not f.endswith(".py"):
                continue
            p = os.path.join(base, f)
            try:
                tree = ast.parse(open(p, encoding="utf-8", errors="ignore").read())
            except Exception:
                continue
            for n in tree.body:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    w = writes_in(n)
                    if w:
                        svc_writers.setdefault(n.name, []).append(f"services/{f}:{n.lineno}")
    rows = []
    rdir = os.path.join(ROOT, "backend", "routers")
    for f in sorted(os.listdir(rdir)):
        if not f.endswith(".py"):
            continue
        p = os.path.join(rdir, f)
        tree = ast.parse(open(p, encoding="utf-8", errors="ignore").read())
        for n in tree.body:
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            path = None
            for d in n.decorator_list:
                if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "get" and d.args:
                    a0 = d.args[0]
                    if isinstance(a0, ast.Constant):
                        path = a0.value
            if not path:
                continue
            direct = writes_in(n)
            trans = sorted(nm for nm in called_names(n) if nm in svc_writers and not nm.startswith(("get_", "list_", "_get")))
            if direct or trans:
                rows.append(f"routers/{f}:{n.lineno} GET {path} -> langsung={direct} via={[(t, svc_writers[t][0]) for t in trans][:5]}")
    print("\n".join(rows))
    print(f"# {len(rows)} endpoint GET berpotensi menulis", file=sys.stderr)


if __name__ == "__main__":
    main()
