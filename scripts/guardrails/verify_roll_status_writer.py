#!/usr/bin/env python3
"""INV-ROLL-02 — status roll (`inventory_rolls.status`) hanya ditulis lewat `services/roll_state.py` (FIX-10 · SSOT-1).

KELAS CACAT YANG DICEGAH (audit 9 Nov 2026 B3a SSOT-1): 63 panggilan tulis `status` roll di 18 berkas + 2 router,
tanpa tabel transisi. Tiap penulis memegang daftar status asalnya sendiri (atau tidak sama sekali — tulis `{id}` saja
sesudah membaca status di Python), tanpa jejak, dan status liar (`allocated` milik alokasi SO) bocor ke daftar status
roll. `roll_state.transition()` menjadi SATU pintu: daftar-izin `ROLL_TRANSITIONS`, CAS (status asal wajib cocok),
jejak `status_history` roll, dan saldo segmen terdampak dibangun ulang.

APA YANG DIHITUNG (statik, `ast`, tanpa basis data): di `backend/routers/**` & `backend/services/**` (kode aplikasi —
bukan uji, bukan skrip data), setiap panggilan `<db>.inventory_rolls.<update_one|update_many|find_one_and_update|
replace_one|find_one_and_replace|bulk_write>(…)` yang dokumen ubahannya MENULIS kunci `status` (di `$set`/
`$setOnInsert`, tahap pipeline `$set`/`$addFields`, atau `UpdateOne/UpdateMany(…)` di dalam `bulk_write`) — termasuk
dict yang dirakit di fungsi yang sama (`x = {…}`, `x: T = {…}`, `x["status"] = …`, `x.update({…})`) dan pembungkus
`finish_set({...})`. `services/roll_state.py` dikecualikan (itulah pintunya). Penyisipan roll baru (`insert_*`) tidak
dihitung — itu kelahiran roll, bukan transisi.

RATCHET: angka per berkas hanya boleh TURUN dari baseline `baselines/roll_status_writer.json` (sisa sesudah FIX-10);
berkas BARU dengan angka > 0 → MERAH. Pakai:
    python scripts/guardrails/verify_roll_status_writer.py
    python scripts/guardrails/verify_roll_status_writer.py --list        # daftar penulis tersisa (berkas:baris)
    python scripts/guardrails/verify_roll_status_writer.py --self-test   # bukti-merah dua arah
    python scripts/guardrails/verify_roll_status_writer.py --update      # kencangkan baseline (tak pernah naik)
"""
from __future__ import annotations

import ast
import os
import re
import sys

from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import Guard, ROOT, G, X  # noqa: E402
from _ratchet import compare, load_baseline, tightened, write_baseline  # noqa: E402

NAME = "roll_status_writer"
COLL = "inventory_rolls"
OWNER = "backend/services/roll_state.py"
UPDATE_OPS = {"update_one", "update_many", "find_one_and_update", "replace_one", "find_one_and_replace"}
SET_OPS = {"$set", "$setOnInsert"}
PIPE_SET = {"$set", "$addFields"}
HANDLE_RE = re.compile(r"(^|_)(db|mongo|dbx|mdb|tdb)$")


def _const(n) -> Optional[str]:
    return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else None


class _Fn:
    """Perakitan dict per nama variabel di satu fungsi (cukup untuk pola tulis repo ini)."""

    def __init__(self, fn):
        self.assign: Dict[str, List[ast.AST]] = {}
        self.sub: Dict[str, List[Tuple[List[Optional[str]], ast.AST]]] = {}
        if fn is None:
            return
        for n in ast.walk(fn):
            tgts, val = [], None
            if isinstance(n, ast.Assign):
                tgts, val = n.targets, n.value
            elif isinstance(n, ast.AnnAssign) and n.value is not None:
                tgts, val = [n.target], n.value
            for t in tgts:
                if isinstance(t, ast.Name):
                    self.assign.setdefault(t.id, []).append(val)
                elif isinstance(t, ast.Subscript):
                    chain, cur = [], t
                    while isinstance(cur, ast.Subscript):
                        chain.append(_const(cur.slice))
                        cur = cur.value
                    if isinstance(cur, ast.Name):
                        self.sub.setdefault(cur.id, []).append((list(reversed(chain)), val))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "update" and n.args:
                chain, tgt = [], n.func.value
                while isinstance(tgt, ast.Subscript):
                    chain.append(_const(tgt.slice))
                    tgt = tgt.value
                if isinstance(tgt, ast.Name):
                    self.sub.setdefault(tgt.id, []).append((list(reversed(chain)) + ["**"], n.args[0]))


def _keys(node, fn: _Fn, depth: int = 0) -> Dict[str, ast.AST]:
    """{kunci: nilai} dari Dict / dict(...) / Name terakit / finish_set({...}). Kunci tak terbaca = '?'."""
    out: Dict[str, ast.AST] = {}
    if node is None or depth > 5:
        return out
    if isinstance(node, ast.Dict):
        for k, v in zip(node.keys, node.values):
            if k is None:
                out.update(_keys(v, fn, depth + 1))
            else:
                out[_const(k) or "?"] = v
    elif isinstance(node, ast.IfExp):   # `{...} if c else {...}` — gabungan kedua cabang
        out.update(_keys(node.body, fn, depth + 1))
        out.update(_keys(node.orelse, fn, depth + 1))
    elif isinstance(node, ast.Call):
        f = node.func
        fname = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
        if fname == "dict":
            for a in node.args:
                out.update(_keys(a, fn, depth + 1))
            for kw in node.keywords:
                if kw.arg:
                    out[kw.arg] = kw.value
                else:
                    out.update(_keys(kw.value, fn, depth + 1))
        elif fname == "finish_set" and node.args:
            out["$set"] = node.args[0]
        else:
            out["?"] = node
    elif isinstance(node, ast.Name):
        for v in fn.assign.get(node.id, []):
            out.update(_keys(v, fn, depth + 1))
        for chain, v in fn.sub.get(node.id, []):
            if not chain:
                continue
            if chain[-1] == "**":
                inner = _keys(v, fn, depth + 1)
                if len(chain) == 1:
                    out.update(inner)
                else:
                    holder = out.setdefault(chain[0] or "?", ast.Dict(keys=[], values=[]))
                    if isinstance(holder, ast.Dict):
                        for k2, v2 in inner.items():
                            holder.keys.append(ast.Constant(k2))
                            holder.values.append(v2)
            elif len(chain) == 1:
                out[chain[0] or "?"] = v
            else:
                holder = out.setdefault(chain[0] or "?", ast.Dict(keys=[], values=[]))
                if isinstance(holder, ast.Dict):
                    holder.keys.append(ast.Constant(chain[1] or "?"))
                    holder.values.append(v)
    else:
        out["?"] = node
    return out


def _writes_status(upd, fn: _Fn, op: str) -> bool:
    if op in ("replace_one", "find_one_and_replace"):
        return "status" in _keys(upd, fn)
    if isinstance(upd, ast.List):   # pipeline
        for st in upd.elts:
            for k, v in _keys(st, fn).items():
                if k in PIPE_SET and "status" in _keys(v, fn):
                    return True
        return False
    if isinstance(upd, ast.Name) and any(isinstance(v, ast.List) for v in fn.assign.get(upd.id, [])):
        return any(_writes_status(v, fn, op) for v in fn.assign.get(upd.id, []) if isinstance(v, ast.List))
    for k, v in _keys(upd, fn).items():
        if k in SET_OPS and "status" in _keys(v, fn):
            return True
    return False


def _coll_of(func: ast.Attribute, consts: Dict[str, str]) -> Optional[str]:
    base = func.value
    if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) and HANDLE_RE.search(base.value.id):
        return base.attr
    if isinstance(base, ast.Subscript) and isinstance(base.value, ast.Name) and HANDLE_RE.search(base.value.id):
        s = base.slice
        if _const(s):
            return _const(s)
        if isinstance(s, ast.Name):
            return consts.get(s.id)
    return None


def scan_source(src: str) -> List[Tuple[int, str]]:
    """→ [(baris, fungsi)] panggilan tulis status roll dalam satu sumber. Fungsi murni (diuji --self-test)."""
    tree = ast.parse(src)
    consts = {t.id: n.value.value for n in tree.body if isinstance(n, ast.Assign)
              for t in n.targets if isinstance(t, ast.Name) and _const(n.value)}
    hits: List[Tuple[int, str]] = []
    fns = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    owner: Dict[int, ast.AST] = {}
    for f in fns:   # fungsi TERDALAM yang memuat tiap node
        for n in ast.walk(f):
            owner[id(n)] = f
    ctx_cache: Dict[int, _Fn] = {}
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
            continue
        op = n.func.attr
        if op not in UPDATE_OPS and op != "bulk_write":
            continue
        if _coll_of(n.func, consts) != COLL:
            continue
        f = owner.get(id(n))
        fn = ctx_cache.setdefault(id(f), _Fn(f))
        name = getattr(f, "name", "<modul>")
        if op == "bulk_write":
            scope = f if f is not None else n
            for c in ast.walk(scope):
                if isinstance(c, ast.Call) and isinstance(c.func, (ast.Name, ast.Attribute)):
                    cname = c.func.id if isinstance(c.func, ast.Name) else c.func.attr
                    if cname in ("UpdateOne", "UpdateMany") and len(c.args) > 1 and _writes_status(c.args[1], fn,
                                                                                                    "update_one"):
                        hits.append((n.lineno, name))
                        break
            continue
        upd = n.args[1] if len(n.args) > 1 else next(
            (k.value for k in n.keywords if k.arg in ("update", "replacement")), None)
        if _writes_status(upd, fn, op):
            hits.append((n.lineno, name))
    return hits


def is_app(rel: str) -> bool:
    base = rel.rsplit("/", 1)[-1]
    return not (base.startswith(("test_", "seed", "migrate", "fix_", "backfill", "poc_", "_"))
                or "/tests/" in rel or "/scripts/" in rel)


def scan_repo() -> Dict[str, List[Tuple[int, str]]]:
    out: Dict[str, List[Tuple[int, str]]] = {}
    for sub in ("routers", "services"):
        for p in sorted((ROOT / "backend" / sub).rglob("*.py")):
            rel = str(p.relative_to(ROOT)).replace("\\", "/")
            if rel == OWNER or not is_app(rel):
                continue
            try:
                hits = scan_source(p.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            if hits:
                out[rel] = hits
    return out


def run(update: bool = False, listing: bool = False) -> int:
    g = Guard("INV-ROLL-02", "status roll hanya ditulis lewat services/roll_state.py (ratchet)")
    found = scan_repo()
    current = {rel: len(h) for rel, h in found.items()}
    g.bump(sum(current.values()) or 1)
    base = load_baseline(NAME)
    if listing:
        for rel, hits in sorted(found.items()):
            for ln, fn in hits:
                print(f"  {rel}:{ln} [{fn}]")
        print(f"  — {sum(current.values())} penulis di {len(current)} berkas (baseline {sum(base.values())})")
    if update:
        p = write_baseline(NAME, tightened(current, base),
                           "FIX-10 (SSOT-1) — sisa penulis status roll di luar roll_state; hanya boleh turun.")
        print(f"{G}baseline dikencangkan → {p}{X}")
        return 0
    naik, baru, turun = compare(current, base)
    for rel, n, b in naik:
        lines = ", ".join(str(ln) for ln, _ in found.get(rel, []))
        g.add(f"{rel}: {n} penulis status roll (baseline {b}) — baris {lines}. Pakai roll_state.transition().")
    for rel, n, _ in baru:
        lines = ", ".join(str(ln) for ln, _ in found.get(rel, []))
        g.add(f"{rel} (berkas BARU di daftar): {n} penulis status roll — baris {lines}. "
              f"Pakai services/roll_state.transition() (daftar-izin + CAS + jejak + saldo).")
    for rel, n, b in turun:
        print(f"  {G}↓{X} {rel}: {b} → {n} (jalankan --update untuk mengencangkan baseline)")
    print(f"  total sekarang {sum(current.values())} · baseline {sum(base.values())}")
    return g.finish()


SELF_CASES = [
    # (nama, sumber, jumlah temuan yang diharapkan)
    ("set langsung", 'async def f(db):\n    await db.inventory_rolls.update_one({"id": 1}, {"$set": {"status": "x"}})\n', 1),
    ("dict dirakit", 'async def f(db):\n    st = {"status": "a"}\n    await db.inventory_rolls.update_one({}, {"$set": st})\n', 1),
    ("anotasi tipe", 'async def f(db):\n    st: dict = {"status": "a"}\n    await db.inventory_rolls.update_many({}, {"$set": st})\n', 1),
    ("subscript", 'async def f(db):\n    upd = {"$set": {}}\n    upd["$set"]["status"] = "a"\n    await db.inventory_rolls.update_one({}, upd)\n', 1),
    ("update()", 'async def f(db):\n    st = {"x": 1}\n    st.update({"status": "b"})\n    await db.inventory_rolls.update_one({}, {"$set": st})\n', 1),
    ("pipeline", 'async def f(db):\n    await db.inventory_rolls.update_one({}, [{"$set": {"status": "b"}}])\n', 1),
    ("konstanta koleksi", 'C = "inventory_rolls"\nasync def f(db):\n    await db[C].find_one_and_update({}, {"$set": {"status": "b"}})\n', 1),
    ("bulk_write", 'from pymongo import UpdateOne\nasync def f(db):\n    await db.inventory_rolls.bulk_write([UpdateOne({}, {"$set": {"status": 1}})])\n', 1),
    ("cabang if", 'async def f(db, n):\n    u = {"status": "consumed"} if n else {"x": 1}\n    await db.inventory_rolls.update_one({}, {"$set": {**u}})\n', 1),
    # anti tuduh palsu
    ("koleksi lain", 'async def f(db):\n    await db.wms_tasks.update_one({}, {"$set": {"status": "x"}})\n', 0),
    ("field lain", 'async def f(db):\n    await db.inventory_rolls.update_one({}, {"$set": {"bin_id": "x"}})\n', 0),
    ("status di filter saja", 'async def f(db):\n    await db.inventory_rolls.update_one({"status": "a"}, {"$set": {"x": 1}})\n', 0),
    ("insert bukan transisi", 'async def f(db):\n    await db.inventory_rolls.insert_one({"status": "a"})\n', 0),
    ("journey.status bukan status", 'async def f(db):\n    await db.inventory_rolls.update_one({}, {"$set": {"journey.stage": "x", "hold.status": 1}})\n', 0),
]


def self_test() -> int:
    g = Guard("INV-ROLL-02 SELF-TEST", "detektor penulis status roll (bukti-merah dua arah)")
    for name, src, want in SELF_CASES:
        g.bump()
        got = len(scan_source(src))
        if got != want:
            g.add(f"kasus '{name}': diharapkan {want} temuan, dapat {got}")
    # ratchet: naik & berkas baru memerah, turun hijau
    g.bump(3)
    naik, baru, turun = compare({"a.py": 3, "b.py": 1, "c.py": 0}, {"a.py": 2, "c.py": 1})
    if [x[0] for x in naik] != ["a.py"] or [x[0] for x in baru] != ["b.py"] or [x[0] for x in turun] != ["c.py"]:
        g.add(f"logika ratchet salah: naik={naik} baru={baru} turun={turun}")
    # pemilik dikecualikan, uji/skrip bukan kode aplikasi
    g.bump(3)
    if is_app("backend/services/tests/x.py") or is_app("backend/services/seed_x.py") or not is_app("backend/services/a.py"):
        g.add("penyaring kode aplikasi salah")
    return g.finish()


if __name__ == "__main__":
    args = set(sys.argv[1:])
    if "--self-test" in args:
        sys.exit(self_test())
    sys.exit(run(update="--update" in args, listing="--list" in args))
