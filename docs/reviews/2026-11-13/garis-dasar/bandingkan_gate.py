#!/usr/bin/env python3
"""Bandingkan kuitansi gate terbaru dengan garis dasar PK-01: aturan "tidak boleh lebih merah".

    python docs/reviews/2026-11-13/garis-dasar/bandingkan_gate.py [kuitansi.md] [--dasar quick|ci]

Tanpa argumen: membaca memory/GATE_RECEIPT.md dan memilih garis dasar menurut mode di kuitansi itu.
Keluar 1 bila ada gate yang di garis dasar PASS (atau tidak ada) tetapi kini FAIL.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def baca(p: Path):
    t = p.read_text(encoding="utf-8")
    mode = (re.search(r"\*\*Mode:\*\* `(\w+)`", t) or [None, "?"])[1]
    return mode, dict(re.findall(r"^\| (.+?) \| (PASS|FAIL|SKIP)[^|]*\|", t, re.M))


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    baru_p = Path(args[0]) if args else ROOT / "memory/GATE_RECEIPT.md"
    mode, baru = baca(baru_p)
    dasar_mode = sys.argv[sys.argv.index("--dasar") + 1] if "--dasar" in sys.argv else ("quick" if mode == "quick" else "ci")
    _, dasar = baca(HERE / f"GATE_RECEIPT.{dasar_mode}.md")
    lebih_merah = sorted(g for g, h in baru.items() if h == "FAIL" and dasar.get(g) != "FAIL")
    hijau_baru = sorted(g for g, h in baru.items() if h == "PASS" and dasar.get(g) == "FAIL")
    hilang = sorted(g for g in dasar if g not in baru)
    print(f"kuitansi: {baru_p} (mode {mode}) · garis dasar: {dasar_mode}")
    print(f"FAIL sekarang {sum(1 for h in baru.values() if h == 'FAIL')} · garis dasar {sum(1 for h in dasar.values() if h == 'FAIL')}")
    for judul, d in (("LEBIH MERAH (PASS/baru → FAIL)", lebih_merah), ("Menjadi hijau", hijau_baru),
                     ("Gate garis dasar yang tidak dijalankan", hilang)):
        print(f"{judul}: {len(d)}")
        for g in d:
            print("  -", g)
    return 1 if lebih_merah else 0


if __name__ == "__main__":
    sys.exit(main())
