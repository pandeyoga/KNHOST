#!/usr/bin/env python3
"""INV-CASH-01 (PK-20 · SL-11, `02_STANDAR.md` §1 P5) — kas hanya lahir dari SATU pembuat (`cash_ledger.create_cash`).

Statik (AST) atas `backend/` kecuali `tests/`, `tests_mem/`, `scripts/`, `bootstrap.py`, `seed_*.py` dan berkas uji/POC
di akar `backend/` (`test_*.py`). Empat aturan:

  [1] `cash_transactions.insert_one` / `.insert_many` / `.replace_one`, atau `.update_one(..., upsert=True)` (juga
      `update_many` / `find_one_and_update` ber-`upsert=True`)                       — kecuali di `services/cash_ledger.py`
  [2] pemanggilan `post_cash_transaction` / `_post_cash_transaction`                — kecuali di `services/gl_service.py`
  [3] pemanggilan `post_cash_durable`                — kecuali di `services/cash_ledger.py`, `services/posting_registry.py`
  [4] definisi fungsi bernama `_next_cash_number`                                     — di mana pun (pemberi nomor kas
      satu-satunya: `cash_ledger.next_cash_number`)

Garis dasar opsional `scripts/guardrails/baselines/cash_single_door.json` (serah-terima (a) PK-20: baris 1–17 tabel
"Keadaan sekarang"; dihapus di akhir (b)). Tiap baris `{lokasi: "berkas:fungsi", aturan: 1..4, jumlah, baris, alasan}`;
hanya boleh turun — jumlah yang turun/hilang = MERAH sampai barisnya disesuaikan.

Pakai:  python3 scripts/guardrails/verify_cash_single_door.py
        python3 scripts/guardrails/verify_cash_single_door.py --self-test
        python3 scripts/guardrails/verify_cash_single_door.py --lapor     # cetak temuan sekarang (JSON), tanpa menilai
"""
from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(__file__))
from _common import Guard, ROOT, G, R, X  # noqa: E402

INV = "INV-CASH-01"
BASELINE_REL = Path("scripts/guardrails/baselines/cash_single_door.json")
SKIP_DIRS = ("tests", "tests_mem", "scripts", "__pycache__", "node_modules")
WRITE_METHODS = {"insert_one", "insert_many", "replace_one"}
UPSERT_METHODS = {"update_one", "update_many", "find_one_and_update"}
LEGACY_POSTERS = {"post_cash_transaction", "_post_cash_transaction"}
#: aturan → berkas yang dikecualikan (relatif terhadap backend/)
ALLOWED = {
    1: {"services/cash_ledger.py"},
    2: {"services/gl_service.py"},
    3: {"services/cash_ledger.py", "services/posting_registry.py"},
    4: set(),
}
RULE_TEXT = {
    1: "menyisipkan `cash_transactions` langsung — buat kas lewat `cash_ledger.create_cash(...)`",
    2: "memanggil pintu jurnal kas lama `post_cash_transaction` — pakai `cash_ledger.create_cash` / `ensure_posted`",
    3: "memanggil `post_cash_durable` di luar pembuat kas — pakai `cash_ledger.create_cash` / `ensure_posted`",
    4: "mendefinisikan `_next_cash_number` salinan — pakai `cash_ledger.next_cash_number`",
}


def _skipped(rel: str) -> bool:
    parts = rel.split("/")
    if parts[0] in SKIP_DIRS:
        return True
    name = parts[-1]
    return len(parts) == 1 and (name == "bootstrap.py" or name.startswith("seed_") or name.startswith("test_"))


def _is_cash_coll(node: ast.AST) -> bool:
    """`db.cash_transactions`, `self.db.cash_transactions`, `db["cash_transactions"]`."""
    if isinstance(node, ast.Attribute):
        return node.attr == "cash_transactions"
    if isinstance(node, ast.Subscript):
        sl = node.slice
        return isinstance(sl, ast.Constant) and sl.value == "cash_transactions"
    return False


def _upsert_true(c: ast.Call) -> bool:
    return any(kw.arg == "upsert" and isinstance(kw.value, ast.Constant) and kw.value.value is True
               for kw in c.keywords)


def _call_name(c: ast.Call) -> Optional[str]:
    f = c.func
    return f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)


def scan(root: Path, stats: Optional[Dict[str, int]] = None) -> Dict[Tuple[str, int], int]:
    """→ {("berkas:fungsi", aturan): jumlah} untuk semua temuan di luar berkas yang dikecualikan.
    `stats["berkas"]` (opsional) = jumlah berkas yang diperiksa."""
    found: Dict[Tuple[str, int], int] = {}
    base = root / "backend"
    for f in sorted(base.rglob("*.py")):
        rel = str(f.relative_to(base)).replace("\\", "/")
        if _skipped(rel):
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        if stats is not None:
            stats["berkas"] = stats.get("berkas", 0) + 1

        def hit(fn: str, rule: int) -> None:
            if rel in ALLOWED[rule]:
                return
            key = (f"{rel}:{fn or '<modul>'}", rule)
            found[key] = found.get(key, 0) + 1

        def walk(node: ast.AST, fn: str) -> None:
            for ch in ast.iter_child_nodes(node):
                nfn = fn
                if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    nfn = f"{fn}.{ch.name}" if fn else ch.name
                    if ch.name == "_next_cash_number":
                        hit(nfn, 4)
                if isinstance(ch, ast.Call):
                    nm = _call_name(ch)
                    if isinstance(ch.func, ast.Attribute) and _is_cash_coll(ch.func.value):
                        if nm in WRITE_METHODS or (nm in UPSERT_METHODS and _upsert_true(ch)):
                            hit(fn, 1)
                    if nm in LEGACY_POSTERS:
                        hit(fn, 2)
                    if nm == "post_cash_durable":
                        hit(fn, 3)
                walk(ch, nfn)
        walk(tree, "")
    return found


def load_baseline(root: Path) -> List[Dict[str, Any]]:
    p = root / BASELINE_REL
    if not p.exists():
        return []
    return list(json.loads(p.read_text(encoding="utf-8")).get("baris") or [])


def check(root: Path = ROOT) -> Guard:
    g = Guard(INV, "kas hanya lahir dari satu pembuat (`cash_ledger.create_cash`)")
    stats: Dict[str, int] = {}
    found = scan(root, stats)
    g.bump(stats.get("berkas", 0))   # satu cek per berkas backend yang dipindai
    base: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for row in load_baseline(root):
        key = (row.get("lokasi", ""), int(row.get("aturan", 0) or 0))
        base[key] = row
        if not row.get("alasan"):
            g.add(f"garis dasar {key[0]} [aturan {key[1]}] tanpa kolom `alasan`")
    for key, n in sorted(found.items()):
        row = base.get(key)
        lim = int((row or {}).get("jumlah", 0) or 0)
        if not row:
            g.add(f"[{key[1]}] {key[0]}: {RULE_TEXT[key[1]]}")
        elif n > lim:
            g.add(f"[{key[1]}] {key[0]}: {n} temuan > garis dasar {lim} — {RULE_TEXT[key[1]]}")
    for key, row in sorted(base.items()):
        n = found.get(key, 0)
        if n < int(row.get("jumlah", 0) or 0):
            g.add(f"garis dasar {key[0]} [aturan {key[1]}]: kini {n} < {row.get('jumlah')} — kencangkan/hapus barisnya")
    return g


def lapor(root: Path = ROOT) -> List[Dict[str, Any]]:
    return [{"lokasi": k[0], "aturan": k[1], "jumlah": n} for k, n in sorted(scan(root).items())]


# ── Bukti-merah ──────────────────────────────────────────────────────────────────────────────────────────────────────
_BERSIH = '''
from services import cash_ledger
async def bayar(doc):
    return await cash_ledger.create_cash(entity_id=doc["entity_id"], direction="out", amount=doc["amount"],
                                         ref_type="contoh", ref_id=doc["id"])
async def baca(db):
    return await db.cash_transactions.find_one({"id": "x"})
async def tandai(db):
    await db.cash_transactions.update_one({"id": "x"}, {"$set": {"note": "y"}})
'''
_LEDGER = '''
async def create_cash(**kw):
    await db.cash_transactions.update_one({"id": "x"}, {"$setOnInsert": kw}, upsert=True)
    await gl_service.post_cash_durable(kw)
'''


def _mini(files: Dict[str, str], baseline: Optional[List[Dict[str, Any]]] = None) -> Guard:
    with tempfile.TemporaryDirectory() as d:
        r = Path(d)
        for rel, src in files.items():
            p = r / "backend" / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(src, encoding="utf-8")
        if baseline is not None:
            (r / BASELINE_REL).parent.mkdir(parents=True, exist_ok=True)
            (r / BASELINE_REL).write_text(json.dumps({"baris": baseline}), encoding="utf-8")
        return check(r)


def self_test() -> int:
    fails = 0

    def case(name: str, g: Guard, expect_red: bool) -> None:
        nonlocal fails
        red = bool(g.violations)
        ok = red == expect_red
        fails += 0 if ok else 1
        print(f"  [{G if ok else R}{'PASS' if ok else 'FAIL'}{X}] {name} → {'MERAH' if red else 'hijau'}")
        if not ok:
            for v in g.violations:
                print(f"      · {v}")

    ok_files = {"services/cash_ledger.py": _LEDGER, "services/contoh_service.py": _BERSIH}
    case("lewat create_cash; baca & $set biasa → hijau", _mini(ok_files), False)
    sisip = "async def bayar(db, doc):\n    await db.cash_transactions.insert_one(doc)\n"
    case("U13 — sisipan langsung `cash_transactions.insert_one` di berkas contoh → MERAH",
         _mini({**ok_files, "routers/contoh.py": sisip}), True)
    case("`db[\"cash_transactions\"].insert_many` → MERAH",
         _mini({**ok_files, "services/a.py": "async def f(db):\n    await db['cash_transactions'].insert_many([])\n"}),
         True)
    case("`update_one(..., upsert=True)` di luar pembuat → MERAH",
         _mini({**ok_files, "services/a.py": "async def f(db):\n    await db.cash_transactions.update_one("
                "{'id': 1}, {'$set': {}}, upsert=True)\n"}), True)
    case("`replace_one` → MERAH",
         _mini({**ok_files, "services/a.py": "async def f(db):\n    await db.cash_transactions.replace_one({}, {})\n"}),
         True)
    case("pemanggilan `post_cash_transaction` di luar gl_service → MERAH",
         _mini({**ok_files, "services/a.py": "async def f(gl, t):\n    await gl.post_cash_transaction(t)\n"}), True)
    case("`_post_cash_transaction` di gl_service sendiri → hijau",
         _mini({**ok_files, "services/gl_service.py": "async def post_cash_durable(t):\n"
                "    return await _post_cash_transaction(t)\nasync def _post_cash_transaction(t): ...\n"}), False)
    case("`post_cash_durable` di luar pembuat & registri → MERAH",
         _mini({**ok_files, "routers/b.py": "async def f(gl, t):\n    await gl.post_cash_durable(t)\n"}), True)
    case("`post_cash_durable` di posting_registry → hijau",
         _mini({**ok_files, "services/posting_registry.py": "async def r(gl, t):\n    await gl.post_cash_durable(t)\n"}),
         False)
    case("definisi `_next_cash_number` (bahkan di cash_ledger) → MERAH",
         _mini({**ok_files, "services/cash_ledger.py": _LEDGER + "async def _next_cash_number(e=''): ...\n"}), True)
    case("tests/, tests_mem/, scripts/, bootstrap.py, seed_*.py, test_*.py dikecualikan → hijau",
         _mini({**ok_files, "tests/test_x.py": sisip, "tests_mem/test_y.py": sisip, "scripts/z.py": sisip,
                "bootstrap.py": sisip, "seed_realistic.py": sisip, "test_poc.py": sisip}), False)
    bl = [{"lokasi": "routers/contoh.py:bayar", "aturan": 1, "jumlah": 1, "baris": "13", "alasan": "uji"}]
    case("temuan terdaftar di garis dasar → hijau", _mini({**ok_files, "routers/contoh.py": sisip}, bl), False)
    case("garis dasar tanpa alasan → MERAH",
         _mini({**ok_files, "routers/contoh.py": sisip}, [{**bl[0], "alasan": ""}]), True)
    case("temuan bertambah melebihi garis dasar → MERAH",
         _mini({**ok_files, "routers/contoh.py": sisip + "    await db.cash_transactions.insert_one(doc)\n"}, bl), True)
    case("garis dasar basi (pemanggil sudah dialihkan) → MERAH", _mini(ok_files, bl), True)
    real = check()
    ok = not real.violations
    fails += 0 if ok else 1
    print(f"  [{G if ok else R}{'PASS' if ok else 'FAIL'}{X}] kode nyata saat ini HIJAU ({len(real.violations)} pelanggaran)")
    for v in real.violations[:20]:
        print(f"    ✗ {v[:180]}")
    print(f"{G if not fails else R}  SELF-TEST {'HIJAU' if not fails else 'MERAH'} ({fails} gagal).{X}")
    return 1 if fails else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    if "--lapor" in sys.argv:
        print(json.dumps(lapor(), ensure_ascii=False, indent=1))
        return 0
    return check().finish()


if __name__ == "__main__":
    sys.exit(main())
