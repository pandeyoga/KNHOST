#!/usr/bin/env python3
"""Inventaris endpoint tulis multi-koleksi (T-01 Langkah 2, audit 2026-09; pencacah diperbaiki PK-33).

Untuk tiap endpoint tulis di backend/routers: kumpulkan koleksi yang ditulis LANGSUNG
(`await db.X.<op>`) DAN satu tingkat ke bawah — fungsi layanan yang dipanggil di badan
endpoint. Hasil: tabel Markdown. Ini INVENTARIS, bukan vonis.

PK-33 (DB-01) — pemanggilan dihubungkan ke fungsi layanan HANYA lewat impor yang nyata di
berkas router itu (impor tingkat modul + impor di dalam badan endpoint):
  `from services import X [as a]`   → `a.fn(...)`  = `X.fn`
  `import services.X as a`          → `a.fn(...)`  = `X.fn`
  `import services.X`               → `services.X.fn(...)` = `X.fn`
  `from services.X import fn [as g]`→ `g(...)`     = `X.fn`
Pencocokan nama polos (dulu `idx.setdefault(nama, …)`) DIHAPUS: dekorator `@router.delete`,
`dict.update`, `_saga.claim` dulu tercatat menulis koleksi milik fungsi layanan mana pun yang
kebetulan bernama `delete`/`update`/`claim`. Berkas dibaca berurutan (`sorted`) supaya hasil
sama di semua mesin; tiap baris membawa metode HTTP (`"POST /path"`).

Batas yang disengaja: hanya SATU tingkat (layanan yang memanggil layanan lain, atau pembantu
router yang memanggil layanan, tidak ditelusuri) → angka tetap batas bawah (sisa DB-01).

Pakai: python3 scripts/inventaris_multi_koleksi.py [--md memory/INVENTARIS_MULTI_KOLEKSI_2026-09.md]
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BE = ROOT / "backend"
WRITE_OPS = {"insert_one", "insert_many", "update_one", "update_many", "delete_one", "delete_many",
             "find_one_and_update", "replace_one", "find_one_and_delete", "bulk_write"}
LOG_ONLY = {"audit_logs", "notifications", "activity_logs", "wa_messages", "doc_refs"}
ROUTE_VERBS = ("post", "put", "patch", "delete")
FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)


def writes_in(node: ast.AST) -> set[str]:
    cols = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in WRITE_OPS:
            v = n.func.value
            if isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name) and v.value.id in ("db", "database"):
                cols.add(v.attr)
    return cols


def _files(folder: pathlib.Path) -> list[pathlib.Path]:
    # PK-33 — urutan berkas tetap (glob tidak menjamin urutan antar mesin/sistem berkas).
    return sorted(folder.glob("*.py"), key=lambda p: p.name)


def service_index(files=None) -> dict[str, set[str]]:
    """{'modul.fungsi': koleksi yang ditulis} untuk semua fungsi tingkat modul di services/*.py.

    Kunci SELALU berawalan modul — tidak ada kunci nama polos, jadi dua fungsi kembar nama di
    modul berbeda tidak pernah saling menutupi."""
    idx: dict[str, set[str]] = {}
    for f in sorted(files if files is not None else _files(BE / "services"), key=lambda p: p.name):
        try:
            tree = ast.parse(f.read_text(errors="ignore"))
        except SyntaxError:
            continue
        for n in tree.body:
            if isinstance(n, FUNCS):
                idx[f"{f.stem}.{n.name}"] = writes_in(n)
    return idx


def _walk_outside_functions(tree: ast.AST):
    """ast.walk tanpa masuk ke badan fungsi/kelas (impor tingkat modul, termasuk di dalam try/if)."""
    stack = [tree]
    while stack:
        n = stack.pop()
        yield n
        for c in ast.iter_child_nodes(n):
            if not isinstance(c, FUNCS + (ast.ClassDef,)):
                stack.append(c)


def _imports_from(nodes) -> dict[str, tuple[str, str]]:
    """Nama lokal → ("mod", "X") untuk `a.fn` | ("fn", "X.fn") untuk `g(...)` | ("pkg", "") untuk `services`."""
    m: dict[str, tuple[str, str]] = {}
    for n in nodes:
        if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            if n.module == "services":
                for a in n.names:
                    m[a.asname or a.name] = ("mod", a.name)
            elif n.module.startswith("services.") and n.module.count(".") == 1:
                mod = n.module.split(".", 1)[1]
                for a in n.names:
                    m[a.asname or a.name] = ("fn", f"{mod}.{a.name}")
        elif isinstance(n, ast.Import):
            for a in n.names:
                if a.name.startswith("services.") and a.name.count(".") == 1:
                    if a.asname:
                        m[a.asname] = ("mod", a.name.split(".", 1)[1])
                    else:
                        m["services"] = ("pkg", "")
    return m


def module_imports(tree: ast.Module) -> dict[str, tuple[str, str]]:
    return _imports_from(_walk_outside_functions(tree))


def function_imports(fn: ast.AST) -> dict[str, tuple[str, str]]:
    return _imports_from(ast.walk(fn))


def resolved_calls(fn: ast.AST, imports: dict[str, tuple[str, str]]) -> list[str]:
    """'modul.fungsi' layanan yang dipanggil di badan `fn`, HANYA lewat nama yang diimpor."""
    out = []
    for n in ast.walk(fn):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Name):
            kind, ref = imports.get(f.id, ("", ""))
            if kind == "fn":
                out.append(ref)
        elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
            kind, ref = imports.get(f.value.id, ("", ""))
            if kind == "mod":
                out.append(f"{ref}.{f.attr}")
        elif (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Attribute)
              and isinstance(f.value.value, ast.Name) and imports.get(f.value.value.id, ("",))[0] == "pkg"):
            out.append(f"{f.value.attr}.{f.attr}")
    return out


def route_keys(fn: ast.AST) -> list[str]:
    """['POST /path', …] untuk tiap dekorator rute tulis pada fungsi."""
    keys = []
    for d in fn.decorator_list:
        if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr in ROUTE_VERBS and d.args:
            keys.append(f"{d.func.attr.upper()} {getattr(d.args[0], 'value', '?')}")
    return keys


def rows_for_source(fname: str, src: str, idx: dict[str, set[str]]) -> list:
    """Baris inventaris satu berkas router (fungsi murni — dipakai uji-diri penjaga)."""
    tree = ast.parse(src)
    mod_imp = module_imports(tree)
    rows = []
    for n in tree.body:
        if not isinstance(n, FUNCS):
            continue
        keys = route_keys(n)
        if not keys:
            continue
        direct = writes_in(n)
        imports = {**mod_imp, **function_imports(n)}
        via: dict[str, set[str]] = {}
        for ref in resolved_calls(n, imports):
            w = idx.get(ref)
            if w:
                via[ref] = w
        allc = set(direct)
        for w in via.values():
            allc |= w
        if len(allc) >= 2:
            for key in keys:
                rows.append((fname, n.lineno, key, sorted(direct), dict(sorted(via.items())), sorted(allc)))
    return rows


def collect_rows(router_files=None, service_files=None) -> list:
    """[(router file, lineno, 'METHOD /path', direct, via, allc)] untuk endpoint tulis ≥2 koleksi."""
    idx = service_index(service_files)
    rows = []
    for f in sorted(router_files if router_files is not None else _files(BE / "routers"), key=lambda p: p.name):
        rows += rows_for_source(f.name, f.read_text(errors="ignore"), idx)
    rows.sort(key=lambda r: (-len(r[5]), r[0], r[1], r[2]))
    return rows


def _reviewed():
    sys.path.insert(0, str(ROOT / "scripts" / "guardrails"))
    from verify_atomic_claim import REVIEWED  # noqa: E402
    return REVIEWED


def main() -> int:
    rows = collect_rows()
    reviewed = _reviewed()
    L = ["# Inventaris endpoint tulis ≥2 koleksi (T-01 Langkah 2) — dihasilkan `scripts/inventaris_multi_koleksi.py`", "",
         f"Total: **{len(rows)}** endpoint (router langsung + satu tingkat layanan, dihubungkan lewat impor nyata — PK-33). "
         "Penelusuran hanya SATU tingkat: layanan yang memanggil layanan lain, atau pembantu router yang memanggil "
         "layanan, TIDAK ikut dihitung — angka ini masih batas bawah.", "",
         "| # | Berkas:baris | Endpoint | Koleksi (semua) | Langsung di router | Lewat layanan (1 tingkat) | Klasifikasi |",
         "|---|---|---|---|---|---|---|"]
    for i, (fn, ln, path, direct, via, allc) in enumerate(rows, 1):
        substantive = [c for c in allc if c not in LOG_ONLY]
        rv = reviewed.get((fn, path))
        if len(substantive) < 2:
            kls = "TIDAK RELEVAN (koleksi lain hanya log/audit/notifikasi)"
        elif rv and rv[0] == "unit":
            kls = f"DITANGANI UNIT — {rv[1]} (INV-ATOMIC-01)"
        elif rv:
            kls = f"AMAN [{rv[0]}] — {rv[1]} (INV-ATOMIC-01)"
        else:
            kls = "BELUM DITINJAU — perlu pemeriksaan penjaga idempotensi satu per satu"
        via_s = "; ".join(f"`{k}`→{sorted(v)}" for k, v in via.items()) or "—"
        L.append(f"| {i} | `{fn}:{ln}` | `{path}` | {len(allc)}: {', '.join(allc)} | {', '.join(direct) or '—'} | {via_s} | {kls} |")
    text = "\n".join(L) + "\n"
    if "--md" in sys.argv:
        out = ROOT / sys.argv[sys.argv.index("--md") + 1]
        out.write_text(text)
        print(f"ditulis: {out} ({len(rows)} baris)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
