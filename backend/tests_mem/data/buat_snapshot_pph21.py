"""PK-46 — pembuat `pph21_snapshot_kode_lama.json`: perilaku PPh 21 KODE LAMA, dihasilkan mesin, bukan diketik.

Sumber angka: `backend/services/hr_payroll_service.py` pada commit sebelum unit PK-46 (bawaan: `ea0de78`), dibaca lewat
`git show`. Dari berkas itu hanya konstanta tarif (`TER_*`, `PTKP_*`, `PASAL17`, `BIAYA_JABATAN_*`, `INF`) dan fungsi
`pasal17_tax`, `annual_pph21`, `ter_rate` yang diambil (lewat AST) lalu dijalankan apa adanya di ruang nama terpisah.
Tidak ada angka tarif yang ditulis di skrip ini.

Isi snapshot:
- `titik_ter`: keluaran `ter_rate(kategori, bruto)` di tiap batas atas dan batas + 1 (kategori A, B, C; ditambah bruto 0),
  serta kategori tak dikenal "X" di titik-titik kategori A (perilaku hari ini: jatuh ke kategori A);
- `contoh_setahun`: tiga keluaran `annual_pph21(...)`. Masukannya (gaji, iuran pensiun, bulan, status) adalah data uji,
  bukan tarif: (1) biaya jabatan mentok batas, dua lapis pasal 17; (2) penghasilan besar, empat lapis; (3) biaya jabatan
  di bawah batas, status PTKP tak dikenal (jatuh ke TK0).

Pakai (dari root repo):
    python backend/tests_mem/data/buat_snapshot_pph21.py            # tulis ulang snapshot dari commit bawaan
    python backend/tests_mem/data/buat_snapshot_pph21.py --periksa  # cocokkan berkas yang ada dengan hasil hitung ulang
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

COMMIT_AWAL = "ea0de78ad85e993a9a397d3e8ac5584ae3b384cb"
BERKAS_SUMBER = "backend/services/hr_payroll_service.py"
ROOT = Path(__file__).resolve().parents[3]
KELUARAN = Path(__file__).resolve().parent / "pph21_snapshot_kode_lama.json"

NAMA_KONSTANTA = {"INF", "TER_A", "TER_B", "TER_C", "TER_TABLES", "PTKP_TO_TER", "PTKP_AMOUNT", "PASAL17",
                  "BIAYA_JABATAN_RATE", "BIAYA_JABATAN_MONTHLY_CAP"}
NAMA_FUNGSI = {"pasal17_tax", "annual_pph21", "ter_rate"}

# Masukan contoh setahun — data uji (penghasilan), bukan isi tabel peraturan.
CONTOH_SETAHUN = [
    {"tax_gross": 150_000_000, "pension_deduction": 3_600_000, "months": 12, "ptkp_status": "K1"},
    {"tax_gross": 1_250_000_000, "pension_deduction": 12_000_000, "months": 12, "ptkp_status": "TK0"},
    {"tax_gross": 60_000_000, "pension_deduction": 1_200_000, "months": 12, "ptkp_status": "ZZ"},
]


def _sumber(commit: str) -> str:
    return subprocess.run(["git", "show", f"{commit}:{BERKAS_SUMBER}"], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout


def _nama_target(node: ast.stmt) -> set:
    if isinstance(node, ast.Assign):
        out = set()
        for t in node.targets:
            for n in ast.walk(t):
                if isinstance(n, ast.Name):
                    out.add(n.id)
        return out
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return {node.target.id}
    return set()


def muat_kode_lama(commit: str = COMMIT_AWAL) -> dict:
    """Ruang nama berisi konstanta dan tiga fungsi PPh 21 persis seperti di commit `commit`."""
    pohon = ast.parse(_sumber(commit))
    ambil = []
    for node in pohon.body:
        if isinstance(node, ast.FunctionDef) and node.name in NAMA_FUNGSI:
            ambil.append(node)
        elif _nama_target(node) & NAMA_KONSTANTA:
            ambil.append(node)
    ditemukan = {n.name for n in ambil if isinstance(n, ast.FunctionDef)}
    for n in ambil:
        ditemukan |= _nama_target(n)
    hilang = (NAMA_KONSTANTA | NAMA_FUNGSI) - ditemukan
    if hilang:
        raise SystemExit(f"commit {commit}: tidak menemukan {sorted(hilang)} di {BERKAS_SUMBER}")
    modul = ast.Module(body=ambil, type_ignores=[])
    ns: dict = {}
    exec("from typing import Any, Dict, List, Optional, Tuple", ns)  # noqa: S102 — anotasi di kode lama
    exec(compile(modul, f"{commit[:7]}:{BERKAS_SUMBER}", "exec"), ns)  # noqa: S102
    return ns


def buat(commit: str = COMMIT_AWAL) -> dict:
    ns = muat_kode_lama(commit)
    inf = ns["INF"]
    titik = []
    for kat in sorted(ns["TER_TABLES"]):
        brutos = {0}
        for batas, _tarif in ns["TER_TABLES"][kat]:
            if batas != inf:
                brutos |= {int(batas), int(batas) + 1}
        for b in sorted(brutos):
            titik.append({"kategori": kat, "bruto": b, "tarif": ns["ter_rate"](kat, b)})
    for b in sorted({0} | {int(x) + d for x, _ in ns["TER_TABLES"]["A"] if x != inf for d in (0, 1)}):
        titik.append({"kategori": "X", "bruto": b, "tarif": ns["ter_rate"]("X", b)})
    contoh = [{"masukan": m, "keluaran": ns["annual_pph21"](**m)} for m in CONTOH_SETAHUN]
    return {
        "keterangan": "Perilaku PPh 21 kode lama (sebelum PK-46). Dihasilkan skrip, bukan diketik; "
                      "BUKAN tabel terverifikasi — hanya pembanding agar perilaku tidak berubah sebelum berkas pemilik dimuat.",
        "dibuat_dari": {"commit": commit, "berkas": BERKAS_SUMBER,
                        "skrip": "backend/tests_mem/data/buat_snapshot_pph21.py"},
        "titik_ter": titik,
        "contoh_setahun": contoh,
    }


def _teks(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--commit", default=COMMIT_AWAL)
    ap.add_argument("--periksa", action="store_true", help="bandingkan dengan berkas yang ada; keluar 1 bila beda")
    args = ap.parse_args(argv)
    teks = _teks(buat(args.commit))
    if args.periksa:
        sama = KELUARAN.exists() and KELUARAN.read_text(encoding="utf-8") == teks
        print("cocok" if sama else f"BEDA: {KELUARAN} tidak sama dengan hasil hitung ulang dari {args.commit}")
        return 0 if sama else 1
    KELUARAN.write_text(teks, encoding="utf-8")
    d = json.loads(teks)
    print(f"{KELUARAN.relative_to(ROOT)}: {len(d['titik_ter'])} titik TER, {len(d['contoh_setahun'])} contoh setahun "
          f"(commit {args.commit[:7]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
