#!/usr/bin/env python3
"""INV-POST-01 (PK-18 · GL-02, IV-04) — setiap jurnal dokumen lewat pintu tahan-gagal dan jenisnya terdaftar.

Statik (AST), tanpa mengimpor aplikasi. Empat pemeriksaan:

  [1] Tiap fungsi `post_*`, `reverse_*`, `pay_payroll_run` di `backend/services/gl_service.py` harus disebut di
      `posters` salah satu jenis `backend/services/posting_registry.py::KINDS`, atau di `TANPA_DOKUMEN` di bawah
      (jurnal tanpa dokumen sumber, beralasan), atau di garis dasar bagian `fungsi` (ber-pemilik).
  [2] Tiap PEMANGGILAN fungsi itu (kecuali `TANPA_DOKUMEN`) di `backend/routers/` dan `backend/services/` (selain `gl_service.py` dan
      `posting_registry.py`) harus berada di dalam argumen `post_durable(...)` / `post_cash_durable(...)`, atau
      pasangan `berkas:fungsi → fungsi_gl` terdaftar di garis dasar bagian `panggilan` dengan jumlah yang tidak
      naik. Panggilan `dry_run=True` (langkah PERIKSA, tanpa tulisan) tidak dihitung.
  [3] Pemanggilan `_insert_entry` dari luar `gl_service.py` (cakupan yang sama): jumlah per berkas tidak boleh naik
      dari garis dasar bagian `insert_entry`.
  [4] Tiap jenis registri: `collection` dikenal `scripts/verify_contract.py` (`CANONICAL_COLLECTIONS`), dan `retry`
      menunjuk fungsi yang didefinisikan di `posting_registry.py`.

Garis dasar `scripts/guardrails/baselines/posting_coverage.json` — tiap baris WAJIB berkolom `pemilik` (ID unit, atau
"belum ada"). Hanya boleh turun: baris yang jumlahnya turun/hilang = MERAH sampai barisnya disesuaikan (unit pemilik
menghapus barisnya saat pemanggilnya dialihkan ke `post_durable`).

Pakai:  python3 scripts/guardrails/verify_posting_coverage.py
        python3 scripts/guardrails/verify_posting_coverage.py --self-test
        python3 scripts/guardrails/verify_posting_coverage.py --lapor      # cetak keadaan sekarang (JSON), tanpa menilai
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(__file__))
from _common import Guard, ROOT, G, R, X  # noqa: E402

INV = "INV-POST-01"
DOORS = {"post_durable", "post_cash_durable"}
RX_POSTER = re.compile(r"^(post_|reverse_)|^pay_payroll_run$")
GL_REL = "services/gl_service.py"
REG_REL = "services/posting_registry.py"
SCAN_DIRS = ("routers", "services")
BASELINE_REL = Path("scripts/guardrails/baselines/posting_coverage.json")

#: Fungsi jurnal TANPA dokumen sumber — tidak butuh penanda di dokumen mana pun. Tiap butir beralasan.
TANPA_DOKUMEN: Dict[str, str] = {
    "reverse_entry": "pembalikan jurnal manual dari layar Jurnal: sumbernya jurnal itu sendiri, bukan dokumen",
    "post_inventory_opening_balance": "saldo awal persediaan (sekali per PT): tidak ada dokumen sumber",
}


# ── Pembaca ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def gl_functions(root: Path) -> List[str]:
    t = ast.parse((root / "backend" / GL_REL).read_text(encoding="utf-8"))
    return sorted(n.name for n in t.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and RX_POSTER.search(n.name) and n.name not in DOORS)


def registry(root: Path) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """→ ({kind: {collection, posters, retry, retry_ok}}, galat bentuk)."""
    src = (root / "backend" / REG_REL).read_text(encoding="utf-8")
    t = ast.parse(src)
    funcs = {n.name for n in t.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    kinds: Dict[str, Dict[str, Any]] = {}
    errs: List[str] = []
    node = next((n for n in t.body if isinstance(n, (ast.Assign, ast.AnnAssign))
                 and any(getattr(x, "id", "") == "KINDS" for x in (n.targets if isinstance(n, ast.Assign) else [n.target]))),
                None)
    if node is None or not isinstance(node.value, ast.Dict):
        return {}, [f"{REG_REL}: `KINDS` tidak ditemukan sebagai literal dict"]
    for k, v in zip(node.value.keys, node.value.values):
        kind = k.value if isinstance(k, ast.Constant) else None
        if not isinstance(kind, str) or not isinstance(v, ast.Dict):
            errs.append(f"{REG_REL}: butir KINDS baris {getattr(k, 'lineno', '?')} bukan `\"jenis\": {{…}}`")
            continue
        spec: Dict[str, Any] = {"collection": None, "posters": [], "retry": None, "retry_ok": False}
        for fk, fv in zip(v.keys, v.values):
            name = fk.value if isinstance(fk, ast.Constant) else None
            if name == "collection" and isinstance(fv, ast.Constant):
                spec["collection"] = fv.value
            elif name == "posters":
                try:
                    spec["posters"] = list(ast.literal_eval(fv))
                except ValueError:
                    errs.append(f"{REG_REL}: `{kind}.posters` bukan daftar literal")
            elif name == "retry":
                spec["retry"] = getattr(fv, "id", None) or ast.unparse(fv)
                spec["retry_ok"] = isinstance(fv, ast.Name) and fv.id in funcs
        kinds[kind] = spec
    return kinds, errs


def canonical_collections(root: Path) -> set:
    t = ast.parse((root / "scripts" / "verify_contract.py").read_text(encoding="utf-8"))
    for n in t.body:
        if isinstance(n, ast.Assign) and any(getattr(x, "id", "") == "CANONICAL_COLLECTIONS" for x in n.targets):
            return set(ast.literal_eval(n.value))
    return set()


def _call_name(c: ast.Call) -> Optional[str]:
    f = c.func
    return f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)


def _dry_run(c: ast.Call) -> bool:
    return any(kw.arg == "dry_run" and isinstance(kw.value, ast.Constant) and kw.value.value is True
               for kw in c.keywords)


def scan_calls(root: Path, posters: set) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    """→ ({(berkas:fungsi, fungsi_gl): jumlah panggilan telanjang}, {berkas: jumlah `_insert_entry`})."""
    bare: Dict[Tuple[str, str], int] = {}
    ins: Dict[str, int] = {}
    base = root / "backend"
    for d in SCAN_DIRS:
        for f in sorted((base / d).rglob("*.py")):
            rel = str(f.relative_to(base)).replace("\\", "/")
            if rel in (GL_REL, REG_REL):
                continue
            try:
                t = ast.parse(f.read_text(encoding="utf-8"))
            except SyntaxError:
                continue

            def walk(node: ast.AST, fn: str, covered: bool) -> None:
                for ch in ast.iter_child_nodes(node):
                    nfn, ncov = fn, covered
                    if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        nfn = f"{fn}.{ch.name}" if fn else ch.name
                    if isinstance(ch, ast.Call):
                        nm = _call_name(ch)
                        if nm in posters and not covered and not _dry_run(ch):
                            key = (f"{rel}:{fn or '<modul>'}", nm)
                            bare[key] = bare.get(key, 0) + 1
                        if nm == "_insert_entry":
                            ins[rel] = ins.get(rel, 0) + 1
                        if nm in DOORS:
                            ncov = True
                    walk(ch, nfn, ncov)
            walk(t, "", False)
    return bare, ins


def load_baseline(root: Path) -> Dict[str, Any]:
    p = root / BASELINE_REL
    if not p.exists():
        return {"fungsi": {}, "panggilan": [], "insert_entry": {}}
    return json.loads(p.read_text(encoding="utf-8"))


# ── Penilai ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def check(root: Path = ROOT) -> Guard:
    g = Guard(INV, "jurnal dokumen lewat pintu tahan-gagal & jenisnya terdaftar di registri posting")
    base = load_baseline(root)
    kinds, errs = registry(root)
    for e in errs:
        g.add(e)
    fns = gl_functions(root)
    covered = {p for s in kinds.values() for p in s["posters"]}
    b_fungsi: Dict[str, Dict[str, Any]] = base.get("fungsi") or {}
    # [1]
    for fn in fns:
        g.bump()
        if fn in covered or fn in TANPA_DOKUMEN:
            continue
        if fn in b_fungsi:
            continue
        g.add(f"[1] gl_service.{fn}: tidak ada di `posters` jenis registri mana pun, tidak di TANPA_DOKUMEN, dan tidak "
              f"di garis dasar `fungsi` — daftarkan jenis dokumennya di posting_registry.KINDS")
    for fn, row in sorted(b_fungsi.items()):
        if not (row or {}).get("pemilik"):
            g.add(f"[1] garis dasar `fungsi.{fn}` tanpa kolom `pemilik`")
        if fn not in fns:
            g.add(f"[1] garis dasar `fungsi.{fn}`: fungsi tidak ada lagi di gl_service — hapus barisnya")
        elif fn in covered:
            g.add(f"[1] garis dasar `fungsi.{fn}`: sudah dicakup jenis registri — hapus barisnya")
    for fn in sorted(set(covered) - set(fns)):
        g.add(f"[1] posting_registry: `{fn}` disebut di `posters` tetapi tidak ada di gl_service")
    # [2] — fungsi TANPA_DOKUMEN tidak punya dokumen untuk ditandai: pemanggilnya tidak diperiksa
    bare, ins = scan_calls(root, set(fns) - set(TANPA_DOKUMEN))
    b_call: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in base.get("panggilan") or []:
        key = (row.get("lokasi", ""), row.get("fungsi_gl", ""))
        b_call[key] = row
        if not row.get("pemilik"):
            g.add(f"[2] garis dasar `panggilan` {key[0]} → {key[1]} tanpa kolom `pemilik`")
    for key, n in sorted(bare.items()):
        g.bump()
        row = b_call.get(key)
        lim = int((row or {}).get("jumlah", 0) or 0)
        if not row:
            g.add(f"[2] {key[0]} memanggil gl_service.{key[1]} telanjang (di luar post_durable) — bungkus dengan "
                  f"`gl_service.post_durable(koleksi, id, lambda: …, source_type=…, source_id=…)`")
        elif n > lim:
            g.add(f"[2] {key[0]} → {key[1]}: {n} panggilan telanjang > garis dasar {lim}")
    for key, row in sorted(b_call.items()):
        n = bare.get(key, 0)
        lim = int(row.get("jumlah", 0) or 0)
        if n < lim:
            g.add(f"[2] garis dasar {key[0]} → {key[1]}: kini {n} < {lim} — kencangkan/hapus barisnya "
                  f"(pemilik {row.get('pemilik')})")
    # [3]
    b_ins: Dict[str, Dict[str, Any]] = base.get("insert_entry") or {}
    for rel, row in sorted(b_ins.items()):
        if not (row or {}).get("pemilik"):
            g.add(f"[3] garis dasar `insert_entry.{rel}` tanpa kolom `pemilik`")
    for rel, n in sorted(ins.items()):
        g.bump()
        lim = int((b_ins.get(rel) or {}).get("jumlah", 0) or 0)
        if n > lim:
            g.add(f"[3] {rel}: {n} pemanggilan `_insert_entry` dari luar gl_service > garis dasar {lim} — pakai fungsi "
                  f"`post_*` di gl_service lewat post_durable")
    for rel, row in sorted(b_ins.items()):
        if ins.get(rel, 0) < int(row.get("jumlah", 0) or 0):
            g.add(f"[3] garis dasar insert_entry {rel}: kini {ins.get(rel, 0)} < {row.get('jumlah')} — kencangkan barisnya")
    # [4]
    known = canonical_collections(root)
    for kind, spec in sorted(kinds.items()):
        g.bump()
        if spec["collection"] not in known:
            g.add(f"[4] posting_registry.KINDS[{kind!r}].collection {spec['collection']!r} tidak dikenal "
                  f"scripts/verify_contract.py (CANONICAL_COLLECTIONS)")
        if not spec["retry_ok"]:
            g.add(f"[4] posting_registry.KINDS[{kind!r}].retry {spec['retry']!r} bukan fungsi di posting_registry.py")
    return g


def lapor(root: Path = ROOT) -> Dict[str, Any]:
    kinds, _ = registry(root)
    fns = gl_functions(root)
    covered = {p for s in kinds.values() for p in s["posters"]}
    bare, ins = scan_calls(root, set(fns) - set(TANPA_DOKUMEN))
    return {"fungsi_tanpa_jenis": [f for f in fns if f not in covered and f not in TANPA_DOKUMEN],
            "panggilan": [{"lokasi": k[0], "fungsi_gl": k[1], "jumlah": n} for k, n in sorted(bare.items())],
            "insert_entry": dict(sorted(ins.items()))}


# ── Bukti-merah ──────────────────────────────────────────────────────────────────────────────────────────────────────
_GL = '''
async def _insert_entry(**kw): ...
async def post_durable(c, i, post, **kw): ...
async def post_cash_durable(txn): ...
async def post_vendor_bill(bill): ...
async def post_cash_transaction(txn): ...
async def reverse_entry(je_id): ...
'''
_REG = '''
async def _retry_vb(doc, actor): ...
KINDS = {
    "vendor_bill": {"collection": "vendor_bills", "posters": ("post_vendor_bill",), "retry": _retry_vb},
    "cash_transaction": {"collection": "cash_transactions", "posters": ("post_cash_transaction",), "retry": _retry_vb},
}
'''
_CONTRACT = 'CANONICAL_COLLECTIONS = {"vendor_bills", "cash_transactions"}\n'
_BERSIH = '''
from services import gl_service as gl
async def approve(bill):
    await gl.post_durable("vendor_bills", bill["id"], lambda: gl.post_vendor_bill(bill),
                          source_type="vendor_bill", source_id=bill["id"])
    await gl.post_cash_durable(bill)
'''


def _mini(sample: str, *, gl: str = _GL, reg: str = _REG, contract: str = _CONTRACT,
          baseline: Optional[Dict[str, Any]] = None) -> Guard:
    with tempfile.TemporaryDirectory() as d:
        r = Path(d)
        (r / "backend" / "services").mkdir(parents=True)
        (r / "backend" / "routers").mkdir(parents=True)
        (r / "scripts" / "guardrails" / "baselines").mkdir(parents=True)
        (r / "backend" / GL_REL).write_text(gl, encoding="utf-8")
        (r / "backend" / REG_REL).write_text(reg, encoding="utf-8")
        (r / "backend" / "services" / "contoh_service.py").write_text(sample, encoding="utf-8")
        (r / "scripts" / "verify_contract.py").write_text(contract, encoding="utf-8")
        if baseline is not None:
            (r / BASELINE_REL).write_text(json.dumps(baseline), encoding="utf-8")
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

    telanjang = "from services import gl_service as gl\nasync def approve(bill):\n    await gl.post_vendor_bill(bill)\n"
    case("panggilan dibungkus post_durable / post_cash_durable → hijau", _mini(_BERSIH), False)
    case("U14 — pemanggilan post_vendor_bill telanjang di berkas contoh → MERAH", _mini(telanjang), True)
    bl = {"panggilan": [{"lokasi": "services/contoh_service.py:approve", "fungsi_gl": "post_vendor_bill",
                         "jumlah": 1, "pemilik": "PK-99"}]}
    case("panggilan telanjang terdaftar di garis dasar (ber-pemilik) → hijau", _mini(telanjang, baseline=bl), False)
    case("garis dasar tanpa pemilik → MERAH", _mini(telanjang, baseline={"panggilan": [
        {"lokasi": "services/contoh_service.py:approve", "fungsi_gl": "post_vendor_bill", "jumlah": 1}]}), True)
    case("panggilan telanjang bertambah melebihi garis dasar → MERAH",
         _mini(telanjang + "    await gl.post_vendor_bill(bill)\n", baseline=bl), True)
    case("garis dasar basi (pemanggil sudah dibungkus) → MERAH (hapus barisnya)", _mini(_BERSIH, baseline=bl), True)
    case("langkah PERIKSA `dry_run=True` tidak dihitung → hijau",
         _mini("from services import gl_service as gl\nasync def cek(b):\n    await gl.post_vendor_bill(b, dry_run=True)\n"),
         False)
    case("fungsi post_* baru di gl_service tanpa jenis registri → MERAH",
         _mini(_BERSIH, gl=_GL + "async def post_hal_baru(x): ...\n"), True)
    case("fungsi baru terdaftar di garis dasar `fungsi` ber-pemilik → hijau",
         _mini(_BERSIH, gl=_GL + "async def post_hal_baru(x): ...\n",
               baseline={"fungsi": {"post_hal_baru": {"pemilik": "belum ada", "alasan": "uji"}}}), False)
    case("_insert_entry dipanggil dari luar gl_service tanpa garis dasar → MERAH",
         _mini(_BERSIH + "async def sisip():\n    await gl._insert_entry(lines=[])\n"), True)
    case("_insert_entry sesuai garis dasar → hijau",
         _mini(_BERSIH + "async def sisip():\n    await gl._insert_entry(lines=[])\n",
               baseline={"insert_entry": {"services/contoh_service.py": {"jumlah": 1, "pemilik": "PK-06"}}}), False)
    case("koleksi jenis registri tidak dikenal verify_contract → MERAH",
         _mini(_BERSIH, contract='CANONICAL_COLLECTIONS = {"vendor_bills"}\n'), True)
    case("retry jenis registri bukan fungsi → MERAH",
         _mini(_BERSIH, reg=_REG.replace('"retry": _retry_vb}', '"retry": "teks"}', 1)), True)
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
