#!/usr/bin/env python3
"""INV-CASH-02 (Kas & Bank bagian 1, §5.1) — akun kas di baris jurnal hanya dari SATU pembantu `gl_service.akun_kas`.

Sejak PT bisa memakai akun buku besar per rekening (sub-akun `1-1100-NN` / `1-1110-NN`), kode kas `1-1100` / `1-1110`
yang ditulis langsung di baris jurnal membuat kas rekening masuk akun lama: saldo sub-akun ≠ buku kas rekening. Semua
jalur jurnal yang menyentuh kas memakai `gl_service.akun_kas` (atau pembungkusnya: `akun_kas_tanpa_rekening`,
`cash_ledger.akun_refund`, `interco_money_service.akun_kas_bank`).

Statik (`ast`) atas `backend/` kecuali `tests/`, `tests_mem/`, `scripts/`, `bootstrap.py`, `seed_*.py` dan berkas
uji/POC di akar `backend/` (`test_*.py`) — sama dengan INV-CASH-01. MERAH bila, di luar `PENGECUALIAN`:

  [1] string harfiah TEPAT "1-1100" atau "1-1110" (teks panjang yang menyebut kode, mis. pesan / docstring, tidak);
  [2] nama `ACC_KAS_BESAR` / `ACC_KAS_KECIL` dibaca (`gl_service.ACC_KAS_BESAR`, `gl.ACC_KAS_KECIL`, nama polos);
  [3] kunci pemetaan kas TEPAT "kas_bank.kas_besar" / "kas_bank.kas_kecil" (baris `account_key` / `account_for` akan
      menulis akun kas lama tanpa melihat rekening).

`PENGECUALIAN` = {"berkas:fungsi": alasan satu baris mengapa itu BUKAN baris jurnal}. Pengecualian yang tidak lagi
punya temuan = MERAH juga (basi — hapus barisnya), supaya daftar hanya bisa menyempit.

Pakai:  python3 scripts/guardrails/verify_akun_kas_satu_pintu.py
        python3 scripts/guardrails/verify_akun_kas_satu_pintu.py --self-test
        python3 scripts/guardrails/verify_akun_kas_satu_pintu.py --lapor     # temuan sekarang (JSON), tanpa menilai
"""
from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(__file__))
from _common import Guard, ROOT, G, R, X  # noqa: E402

INV = "INV-CASH-02"
SKIP_DIRS = ("tests", "tests_mem", "scripts", "__pycache__", "node_modules")
KODE_KAS = {"1-1100", "1-1110"}
NAMA_KAS = {"ACC_KAS_BESAR", "ACC_KAS_KECIL"}
KUNCI_KAS = {"kas_bank.kas_besar", "kas_bank.kas_kecil"}

#: Lokasi yang BOLEH memuat kode kas — masing-masing BUKAN baris jurnal (alasan satu baris).
PENGECUALIAN: Dict[str, str] = {
    # satu pembantu itu sendiri
    "services/gl_service.py:akun_kas": "SATU pembantu akun kas jurnal (akun jenis kas lama bila tanpa sub-akun)",
    # bagan akun & konstanta
    "services/gl_service.py:<modul>": "bagan akun bawaan `DEFAULT_COA` + konstanta `ACC_KAS_BESAR`/`ACC_KAS_KECIL`",
    "services/cash_account_mode.py:<modul>": "`INDUK` — akun induk (`parent_code`) sub-akun rekening",
    # katalog pemetaan
    "services/gl_mapping_registry.py:<modul>": "katalog Pemetaan Akun: kode bawaan kebutuhan (`kas_bank.*`, ongkir)",
    "services/report_basis.py:kode_kas": "pembaca: kumpulan akun kas laporan (`known_codes` kunci `kas_bank.*`)",
    "services/ar_aging_service.py:recognized_by_order": "pembaca: piutang lahir per pesanan (Dr kas jual tunai lama)",
    # pembaca & pemilih
    "services/gl_service.py:_kas_jual_tunai": "pembaca: Σ Dr kas jurnal penjualan tunai (`order_revenue_recognized`)",
    "services/cash_flow_service.py:<modul>": "`CASH_CODES` — pembaca saldo kas (Arus Kas), bukan baris jurnal",
    "services/cash_ledger.py:<modul>": "`KAS_KECIL_CODE` — `cash_type_for` membaca JENIS kas dari kode pemilih",
    "routers/gl.py:list_cash_accounts": "pemilih refund: daftar cadangan akun templat (dibaca sebagai jenis kas, R5)",
    # bukan kode aplikasi
    "tools/ai_eval/build_questions_keuangan.py:<modul>": "teks pertanyaan uji asisten keuangan, bukan baris jurnal",
}
RULE_TEXT = {
    1: "kode kas harfiah \"1-1100\"/\"1-1110\" — akun kas jurnal lewat `gl_service.akun_kas` (sub-akun rekening)",
    2: "`ACC_KAS_BESAR`/`ACC_KAS_KECIL` dipakai — akun kas jurnal lewat `gl_service.akun_kas` (sub-akun rekening)",
    3: "kunci pemetaan `kas_bank.kas_besar`/`kas_bank.kas_kecil` dipakai — akun kas jurnal lewat `gl_service.akun_kas`",
}


def _skipped(rel: str) -> bool:
    parts = rel.split("/")
    if parts[0] in SKIP_DIRS:
        return True
    name = parts[-1]
    return len(parts) == 1 and (name == "bootstrap.py" or name.startswith("seed_") or name.startswith("test_"))


def scan(root: Path, stats: Optional[Dict[str, int]] = None) -> Dict[str, Dict[int, List[int]]]:
    """→ {"berkas:fungsi": {aturan: [nomor baris, …]}} untuk SEMUA temuan (pengecualian belum diterapkan)."""
    found: Dict[str, Dict[int, List[int]]] = {}
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

        def hit(fn: str, rule: int, line: int) -> None:
            found.setdefault(f"{rel}:{fn or '<modul>'}", {}).setdefault(rule, []).append(line)

        def walk(node: ast.AST, fn: str) -> None:
            for ch in ast.iter_child_nodes(node):
                nfn = fn
                if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    nfn = f"{fn}.{ch.name}" if fn else ch.name
                if isinstance(ch, ast.Constant) and isinstance(ch.value, str) and ch.value in KODE_KAS:
                    hit(fn, 1, ch.lineno)
                elif isinstance(ch, ast.Constant) and isinstance(ch.value, str) and ch.value in KUNCI_KAS:
                    hit(fn, 3, ch.lineno)
                elif isinstance(ch, ast.Name) and ch.id in NAMA_KAS and isinstance(ch.ctx, ast.Load):
                    hit(fn, 2, ch.lineno)
                elif isinstance(ch, ast.Attribute) and ch.attr in NAMA_KAS and isinstance(ch.ctx, ast.Load):
                    hit(fn, 2, ch.lineno)
                walk(ch, nfn)
        walk(tree, "")
    return found


def check(root: Path = ROOT, pengecualian: Optional[Dict[str, str]] = None) -> Guard:
    g = Guard(INV, "akun kas baris jurnal hanya dari satu pembantu `gl_service.akun_kas`")
    boleh = PENGECUALIAN if pengecualian is None else pengecualian
    stats: Dict[str, int] = {}
    found = scan(root, stats)
    g.bump(stats.get("berkas", 0))   # satu cek per berkas backend yang dipindai
    for lokasi, alasan in sorted(boleh.items()):
        if not (alasan or "").strip():
            g.add(f"pengecualian {lokasi} tanpa alasan")
        if lokasi not in found:
            g.add(f"pengecualian {lokasi} basi (tidak ada kode kas lagi) — hapus barisnya dari PENGECUALIAN")
    for lokasi, aturan in sorted(found.items()):
        if lokasi in boleh:
            continue
        for rule, baris in sorted(aturan.items()):
            g.add(f"[{rule}] {lokasi} baris {', '.join(map(str, baris))}: {RULE_TEXT[rule]}")
    return g


def lapor(root: Path = ROOT) -> List[Dict[str, Any]]:
    return [{"lokasi": k, "aturan": {str(r): b for r, b in v.items()}, "dikecualikan": k in PENGECUALIAN}
            for k, v in sorted(scan(root).items())]


# ── Bukti-merah ──────────────────────────────────────────────────────────────────────────────────────────────────────
_GL = '''
ACC_KAS_BESAR = "1-1100"
ACC_KAS_KECIL = "1-1110"
DEFAULT_COA = [("1-1100", "Kas Besar / Bank"), ("1-1110", "Kas Kecil")]
async def akun_kas(entity_id, account_id, cash_type, *, akun_lama=""):
    return akun_lama or (ACC_KAS_KECIL if cash_type == "kas_kecil" else ACC_KAS_BESAR)
'''
_BERSIH = '''
from services import gl_service
async def bayar(doc):
    kas = await gl_service.akun_kas(doc["entity_id"], doc["account_id"], "kas_besar")
    return [{"account_code": "2-1250", "debit": 1, "credit": 0}, {"account_code": kas, "debit": 0, "credit": 1}]
def pesan():
    """Uang antar-PT dibukukan di Bank (1-1100), sub-akun 1-1100-01."""
    return f"Rekening Kas Kecil; uang antar-PT dibukukan di Bank (1-1100). Pilih rekening Bank."
'''
_BOLEH = {"services/gl_service.py:akun_kas": "pembantu", "services/gl_service.py:<modul>": "bagan akun & konstanta"}


def _mini(files: Dict[str, str], pengecualian: Optional[Dict[str, str]] = None) -> Guard:
    with tempfile.TemporaryDirectory() as d:
        r = Path(d)
        for rel, src in files.items():
            p = r / "backend" / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(src, encoding="utf-8")
        return check(r, _BOLEH if pengecualian is None else pengecualian)


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

    ok_files = {"services/gl_service.py": _GL, "services/contoh_service.py": _BERSIH}
    case("akun kas lewat akun_kas; pesan/docstring menyebut kode; sub-akun 1-1100-01 → hijau", _mini(ok_files), False)
    case("baris jurnal ber-\"1-1100\" harfiah di layanan → MERAH",
         _mini({**ok_files, "services/a.py": "def baris(n):\n    return [{'account_code': '1-1100', 'debit': n}]\n"}),
         True)
    case("\"1-1110\" harfiah sebagai cadangan (`kode or \"1-1110\"`) → MERAH",
         _mini({**ok_files, "services/a.py": "def akun(k):\n    return k or \"1-1110\"\n"}), True)
    case("`gl_service.ACC_KAS_BESAR` di baris jurnal kembar → MERAH",
         _mini({**ok_files, "services/a.py": "from services import gl_service\n"
                "def sisi(n):\n    return pair_line(gl_service.ACC_IC_AR, gl_service.ACC_KAS_BESAR, n, 'x')\n"}), True)
    case("nama polos `ACC_KAS_KECIL` di fungsi lain gl_service → MERAH",
         _mini({**ok_files, "services/gl_service.py": _GL + "def denda(t):\n    return ACC_KAS_KECIL if t else 'x'\n"}),
         True)
    case("baris `account_key: \"kas_bank.kas_besar\"` (akun kas lama lewat pemetaan) → MERAH",
         _mini({**ok_files, "services/a.py": "def baris(n):\n    return [{'account_key': 'kas_bank.kas_besar', "
                "'debit': n}]\n"}), True)
    case("`account_for(\"kas_bank.kas_kecil\")` → MERAH",
         _mini({**ok_files, "services/a.py": "async def akun(gl, e):\n    return await gl.account_for("
                "'kas_bank.kas_kecil', e)\n"}), True)
    case("router memakai kode kas harfiah → MERAH",
         _mini({**ok_files, "routers/r.py": "async def f():\n    return {'account_code': '1-1100'}\n"}), True)
    case("tests/, tests_mem/, scripts/, bootstrap.py, seed_*.py, test_*.py dikecualikan → hijau",
         _mini({**ok_files, **{p: "X = '1-1100'\n" for p in ("tests/t.py", "tests_mem/test_y.py", "scripts/z.py",
                                                             "bootstrap.py", "seed_realistic.py", "test_poc.py")}}),
         False)
    case("lokasi terdaftar di PENGECUALIAN (pembaca) → hijau",
         _mini({**ok_files, "services/laporan.py": "def kas():\n    return {'1-1100', '1-1110'}\n"},
               {**_BOLEH, "services/laporan.py:kas": "pembaca saldo kas"}), False)
    case("pengecualian basi (lokasinya tidak memuat kode kas lagi) → MERAH",
         _mini(ok_files, {**_BOLEH, "services/contoh_service.py:bayar": "dulu menulis 1-1100"}), True)
    case("pengecualian tanpa alasan → MERAH",
         _mini({**ok_files, "services/laporan.py": "def kas():\n    return '1-1100'\n"},
               {**_BOLEH, "services/laporan.py:kas": " "}), True)
    case("fungsi bersarang dinamai `luar.dalam` (pengecualian `luar` tidak menutupinya) → MERAH",
         _mini({**ok_files, "services/laporan.py": "def luar():\n    def dalam():\n        return '1-1100'\n"
                "    return '1-1110'\n"}, {**_BOLEH, "services/laporan.py:luar": "pembaca"}), True)
    real = check()
    ok = not real.violations
    fails += 0 if ok else 1
    print(f"  [{G if ok else R}{'PASS' if ok else 'FAIL'}{X}] kode nyata saat ini HIJAU "
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
