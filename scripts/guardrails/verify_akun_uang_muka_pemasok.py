#!/usr/bin/env python3
"""INV-UMP-01 (Kas & Bank bagian 4, C8 §5.3) — akun uang muka pemasok di jalur pemasok hanya dari SATU pembantu
`gl_service.akun_uang_muka_pemasok`.

Sebelum PT memindah saldo uang muka pemasoknya, jalur pemasok membukukan 1-1400 persis seperti dulu; sesudahnya akun
pemetaan PT `hutang.uang_muka_pemasok` (bawaan 1-1410). Jalur yang menulis akunnya langsung tidak ikut penanda PT
(`supplier_advance_mode`): uang muka lama dipakai/dikembalikan di akun yang salah (saldo negatif di satu akun, lebih di
akun lain), atau PT yang belum pindah tiba-tiba menulis 1-1410.

Statik (`ast`) atas `CAKUPAN` — jalur uang muka pemasok:
  * MODUL (seluruh isi berkas): bayar hutang, selisih bayar, kasus keuangan, kontrabon, hutang per pemasok;
  * FUNGSI di `gl_service`: potongan kontrabon dan lawan kas keluar;
  * CABANG `ref_type == "ap_advance"` di `gl_service._cash_out_contra` (cabang lain fungsi itu — mis. pencairan PD
    `cash_advance` — memang uang muka karyawan 1-1400).
MERAH bila di cakupan itu:
  [1] string harfiah TEPAT "1-1400" atau "1-1410" (teks panjang yang menyebut kode, mis. pesan / docstring, tidak);
  [2] nama `ACC_UANG_MUKA` / `ACC_UANG_MUKA_PEMASOK` dibaca (`gl.ACC_UANG_MUKA`, nama polos);
  [3] kunci pemetaan TEPAT "kas_bank.uang_muka_karyawan" / "hutang.uang_muka_pemasok" (`account_for` / `account_key`
      melewati penanda PT).
Juga MERAH: lokasi `CAKUPAN` yang tidak ditemukan lagi (berkas/fungsi diganti nama, cabang `ap_advance` hilang) —
penjaga tidak boleh buta diam-diam; daftar cakupan ikut kode.

Pakai:  python3 scripts/guardrails/verify_akun_uang_muka_pemasok.py
        python3 scripts/guardrails/verify_akun_uang_muka_pemasok.py --self-test
        python3 scripts/guardrails/verify_akun_uang_muka_pemasok.py --lapor     # temuan sekarang (JSON), tanpa menilai
"""
from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(__file__))
from _common import Guard, ROOT, G, R, X  # noqa: E402

INV = "INV-UMP-01"
KODE_UM = {"1-1400", "1-1410"}
NAMA_UM = {"ACC_UANG_MUKA", "ACC_UANG_MUKA_PEMASOK"}
KUNCI_UM = {"kas_bank.uang_muka_karyawan", "hutang.uang_muka_pemasok"}

#: Jalur uang muka pemasok: (berkas di bawah `backend/`, fungsi atau "" = seluruh modul, nilai `ref_type` cabang atau
#: "" = seluruh fungsi).
CAKUPAN: Tuple[Tuple[str, str, str], ...] = (
    ("services/ap_payment_service.py", "", ""),        # bayar tagihan / kontrabon, kelebihan bayar `ap_advance`
    ("services/payment_variance_service.py", "", ""),  # keputusan selisih bayar pemasok
    ("services/finance_case_actions.py", "", ""),      # kasus "lebih bayar pemasok": uang muka & pengembalian dana
    ("services/contra_bon_service.py", "", ""),        # potongan uang muka di kontrabon
    ("services/ap_party_service.py", "", ""),          # hutang per pemasok: potongan belum dipakai
    ("services/gl_service.py", "post_contra_bon_deduction", ""),
    ("services/gl_service.py", "_lawan_kas_keluar", ""),
    ("services/gl_service.py", "_cash_out_contra", "ap_advance"),
)
RULE_TEXT = {
    1: "kode uang muka harfiah \"1-1400\"/\"1-1410\" di jalur pemasok — pakai `gl_service.akun_uang_muka_pemasok`",
    2: "`ACC_UANG_MUKA`/`ACC_UANG_MUKA_PEMASOK` dipakai di jalur pemasok — pakai `gl_service.akun_uang_muka_pemasok`",
    3: "kunci pemetaan uang muka (`kas_bank.uang_muka_karyawan`/`hutang.uang_muka_pemasok`) dipakai di jalur pemasok — "
       "pakai `gl_service.akun_uang_muka_pemasok`",
}


def _lokasi(item: Tuple[str, str, str]) -> str:
    berkas, fungsi, cabang = item
    return f"{berkas}:{fungsi or '<modul>'}" + (f"[{cabang}]" if cabang else "")


def _fungsi(tree: ast.AST, nama: str) -> List[ast.AST]:
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nama]


def _menyebut(node: ast.AST, nilai: str) -> bool:
    return any(isinstance(n, ast.Constant) and n.value == nilai for n in ast.walk(node))


def _cabang(fn: ast.AST, nilai: str) -> List[ast.stmt]:
    """Badan tiap `if`/`elif` di `fn` yang syaratnya menyebut `nilai` (mis. `ref_type == "ap_advance"`)."""
    badan: List[ast.stmt] = []
    for n in ast.walk(fn):
        if isinstance(n, ast.If) and _menyebut(n.test, nilai):
            badan.extend(n.body)
    return badan


def _temuan(nodes: Iterable[ast.AST], awal: str) -> Dict[str, Dict[int, List[int]]]:
    """→ {"<awal>[.fungsi bersarang]": {aturan: [baris]}} untuk semua simpul di `nodes` (rekursif)."""
    found: Dict[str, Dict[int, List[int]]] = {}

    def hit(fn: str, rule: int, line: int) -> None:
        found.setdefault(fn, {}).setdefault(rule, []).append(line)

    def walk(node: ast.AST, fn: str) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in KODE_UM:
                hit(fn, 1, node.lineno)
            elif node.value in KUNCI_UM:
                hit(fn, 3, node.lineno)
        elif isinstance(node, ast.Name) and node.id in NAMA_UM and isinstance(node.ctx, ast.Load):
            hit(fn, 2, node.lineno)
        elif isinstance(node, ast.Attribute) and node.attr in NAMA_UM and isinstance(node.ctx, ast.Load):
            hit(fn, 2, node.lineno)
        for ch in ast.iter_child_nodes(node):
            nfn = fn
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nfn = f"{fn}.{ch.name}" if fn and not fn.endswith(">") else ch.name
            walk(ch, nfn)

    for n in nodes:
        walk(n, awal)
    return found


def scan(root: Path, cakupan: Iterable[Tuple[str, str, str]] = CAKUPAN
         ) -> Tuple[Dict[str, Dict[int, List[int]]], List[str], int]:
    """→ (temuan {"berkas:fungsi": {aturan: [baris]}}, lokasi cakupan yang tidak ditemukan, jumlah lokasi diperiksa)."""
    found: Dict[str, Dict[int, List[int]]] = {}
    hilang: List[str] = []
    n = 0
    trees: Dict[str, Optional[ast.AST]] = {}
    for item in cakupan:
        berkas, fungsi, cabang = item
        if berkas not in trees:
            p = root / "backend" / berkas
            try:
                trees[berkas] = ast.parse(p.read_text(encoding="utf-8")) if p.exists() else None
            except (SyntaxError, UnicodeDecodeError):
                trees[berkas] = None
        tree = trees[berkas]
        if tree is None:
            hilang.append(_lokasi(item))
            continue
        if not fungsi:
            nodes: List[ast.AST] = [tree]
            awal = "<modul>"
        else:
            fns = _fungsi(tree, fungsi)
            nodes = [st for fn in fns for st in (_cabang(fn, cabang) if cabang else [fn])]
            awal = fungsi + (f"[{cabang}]" if cabang else "")
            if not nodes:
                hilang.append(_lokasi(item))
                continue
            if not cabang:   # `walk` menamai fungsi itu sendiri; mulai dari badannya supaya namanya tidak berulang
                nodes = [st for fn in fns for st in fn.body]
        n += 1
        for fn, aturan in _temuan(nodes, awal).items():
            lok = f"{berkas}:{fn}"
            for rule, baris in aturan.items():
                found.setdefault(lok, {}).setdefault(rule, []).extend(baris)
    return found, hilang, n


def check(root: Path = ROOT, cakupan: Iterable[Tuple[str, str, str]] = CAKUPAN) -> Guard:
    g = Guard(INV, "akun uang muka pemasok jalur pemasok lewat satu pembantu `gl_service.akun_uang_muka_pemasok`")
    found, hilang, n = scan(root, cakupan)
    g.bump(n)   # satu cek per lokasi cakupan yang dipindai
    for lok in hilang:
        g.add(f"cakupan {lok} tidak ditemukan (berkas/fungsi/cabang diganti?) — perbarui CAKUPAN penjaga ini")
    for lok, aturan in sorted(found.items()):
        for rule, baris in sorted(aturan.items()):
            g.add(f"[{rule}] {lok} baris {', '.join(map(str, sorted(baris)))}: {RULE_TEXT[rule]}")
    return g


def lapor(root: Path = ROOT) -> Dict[str, Any]:
    found, hilang, _ = scan(root)
    return {"temuan": {k: {str(r): b for r, b in v.items()} for k, v in sorted(found.items())}, "hilang": hilang}


# ── Bukti-merah ──────────────────────────────────────────────────────────────────────────────────────────────────────
_GL = '''
ACC_UANG_MUKA = "1-1400"
ACC_UANG_MUKA_PEMASOK = "1-1410"
DEFAULT_COA = [("1-1400", "Uang Muka"), ("1-1410", "Uang Muka Pemasok")]
async def akun_uang_muka_pemasok(entity_id):
    if await aktif(entity_id):
        return await account_for("hutang.uang_muka_pemasok", entity_id)
    return ACC_UANG_MUKA
def _cash_out_contra(txn, um=""):
    ref_type = txn.get("ref_type") or ""
    if ref_type == "vendor_bill":
        contra = "2-1100"
    elif ref_type == "ap_advance":
        contra = um
    elif ref_type == "cash_advance":
        contra = ACC_UANG_MUKA
    return contra
async def _lawan_kas_keluar(txn, entity_id):
    um = await akun_uang_muka_pemasok(entity_id) if txn.get("ref_type") == "ap_advance" else ""
    return _cash_out_contra(txn, um)
async def post_contra_bon_deduction(*, kind, entity_id, amount):
    """Potongan uang muka: Dr 2-1100 / Cr 1-1400 sampai PT pindah, sesudahnya 1-1410."""
    credit = await akun_uang_muka_pemasok(entity_id) if kind == "supplier_advance" else "4-9300"
    return [("2-1100", amount, 0), (credit, 0, amount)]
async def post_petty_cash_settlement(stl):
    return [(ACC_UANG_MUKA, 0, stl["total"])]
'''
_PAKAI = '''
from services import gl_service as gl
async def jurnal(case, n):
    """Kelebihan bayar → uang muka (Dr 1-1400 / Cr 2-1100)."""
    akun = await gl.akun_uang_muka_pemasok(case["entity_id"])
    return {"debit_acc": akun, "credit_acc": gl.ACC_HUTANG, "label": f"Jurnal Dr {akun} Uang Muka", "amount": n}
'''


def contoh_bersih() -> Dict[str, str]:
    """Repo mini yang HIJAU: semua lokasi cakupan ada dan memakai pembantu (dipakai self-test dan uji)."""
    files = {berkas: _PAKAI for berkas, _f, _c in CAKUPAN if berkas != "services/gl_service.py"}
    files["services/gl_service.py"] = _GL
    files["services/cash_advance_service.py"] = "from services import gl_service as gl\nAKUN = gl.ACC_UANG_MUKA\n"
    return files


def _mini(files: Dict[str, str], cakupan: Iterable[Tuple[str, str, str]] = CAKUPAN) -> Guard:
    with tempfile.TemporaryDirectory() as d:
        r = Path(d)
        for rel, src in files.items():
            p = r / "backend" / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(src, encoding="utf-8")
        return check(r, cakupan)


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

    ok = contoh_bersih()
    tambah = "\ndef lain():\n    return {}\n"

    def ganti(berkas: str, src: str) -> Dict[str, str]:
        return {**ok, berkas: src}

    case("jalur pemasok lewat pembantu; docstring/pesan menyebut 1-1400; PD tetap ACC_UANG_MUKA → hijau",
         _mini(ok), False)
    case("\"1-1400\" harfiah di bayar hutang (ap_payment_service) → MERAH",
         _mini(ganti("services/ap_payment_service.py", _PAKAI + "def akun():\n    return '1-1400'\n")), True)
    case("`gl.ACC_UANG_MUKA` di kasus keuangan (lebih bayar pemasok) → MERAH",
         _mini(ganti("services/finance_case_actions.py",
                     _PAKAI + "def j(e, n):\n    return _j(e, gl.ACC_UANG_MUKA, gl.ACC_HUTANG, n)\n")), True)
    case("`gl.ACC_UANG_MUKA_PEMASOK` langsung di selisih bayar (melewati penanda PT) → MERAH",
         _mini(ganti("services/payment_variance_service.py",
                     _PAKAI + "def efek(n):\n    return {'account': gl.ACC_UANG_MUKA_PEMASOK}\n")), True)
    case("\"1-1410\" harfiah di kontrabon → MERAH",
         _mini(ganti("services/contra_bon_service.py", _PAKAI + "KODE = '1-1410'\n")), True)
    case("`account_for(\"hutang.uang_muka_pemasok\")` di hutang per pemasok → MERAH",
         _mini(ganti("services/ap_party_service.py",
                     _PAKAI + "async def akun(e):\n    return await gl.account_for('hutang.uang_muka_pemasok', e)\n")),
         True)
    case("`account_key: \"kas_bank.uang_muka_karyawan\"` di kasus keuangan → MERAH",
         _mini(ganti("services/finance_case_actions.py",
                     _PAKAI + "def baris(n):\n    return [{'account_key': 'kas_bank.uang_muka_karyawan', 'debit': n}]\n")),
         True)
    case("`ACC_UANG_MUKA` di potongan kontrabon gl_service → MERAH",
         _mini(ganti("services/gl_service.py", _GL.replace(
             'credit = await akun_uang_muka_pemasok(entity_id) if kind == "supplier_advance" else "4-9300"',
             'credit = ACC_UANG_MUKA if kind == "supplier_advance" else "4-9300"'))), True)
    case("`ACC_UANG_MUKA` di cabang `ap_advance` `_cash_out_contra` → MERAH",
         _mini(ganti("services/gl_service.py", _GL.replace("        contra = um\n",
                                                           "        contra = ACC_UANG_MUKA\n"))), True)
    case("fungsi bersarang di potongan kontrabon memakai \"1-1400\" → MERAH",
         _mini(ganti("services/gl_service.py", _GL.replace(
             '    """Potongan uang muka',
             '    def lama():\n        return "1-1400"\n    """Potongan uang muka'))), True)
    case("`ACC_UANG_MUKA` di luar cakupan (pencairan PD, LPJ, layanan PD) → hijau",
         _mini(ganti("services/cash_advance_service.py", "from services import gl_service as gl\n"
                     "def baris(n):\n    return [{'account_code': gl.ACC_UANG_MUKA, 'debit': n}, "
                     "{'account_code': '1-1400', 'credit': n}]\n")), False)
    case("berkas cakupan hilang (diganti nama) → MERAH",
         _mini({k: v for k, v in ok.items() if k != "services/contra_bon_service.py"}), True)
    case("fungsi cakupan hilang (`post_contra_bon_deduction` diganti nama) → MERAH",
         _mini(ganti("services/gl_service.py", _GL.replace("def post_contra_bon_deduction", "def potong_kontrabon"))),
         True)
    case("cabang `ap_advance` hilang dari `_cash_out_contra` → MERAH",
         _mini(ganti("services/gl_service.py", _GL.replace('ref_type == "ap_advance"', 'ref_type == "uang_muka"'))),
         True)
    case("modul cakupan tanpa uang muka sama sekali → hijau",
         _mini(ganti("services/ap_party_service.py", "def kosong():\n    return 0\n" + tambah)), False)
    real = check()
    hijau = not real.violations
    fails += 0 if hijau else 1
    print(f"  [{G if hijau else R}{'PASS' if hijau else 'FAIL'}{X}] kode nyata saat ini HIJAU "
          f"({len(real.violations)} pelanggaran)")
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
