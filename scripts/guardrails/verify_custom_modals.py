#!/usr/bin/env python3
"""INV-UI-11 — POP-UP BUATAN SENDIRI HANYA BOLEH BERKURANG (ratchet, fase 3 · P1, aturan L-03).

MASALAH YANG DICEGAH (audit UI tahap 2, L-03)
==============================================
Buat/Ubah wajib `FormModal`, rincian wajib `DetailModal` (framed). Kenyataannya ±160 berkas masih merakit pop-up
sendiri: `.modal-card` polos, `div fixed inset-0`, panel tetap — masing-masing dengan perilaku Esc, klik-latar,
kunci gulir, dan rupa HP yang berbeda. Akibatnya di HP 390 px sebagian pop-up terpotong, tombol Simpan di luar
layar, dan form layar penuh (fase 3 · P1) tidak berlaku untuknya.

Fase 3 mengonversi berkas-berkas itu bertahap (P2–P6). Penjaga ini memastikan arahnya hanya satu:
  · jumlah pola `modal-card` + `fixed inset-0` per berkas TIDAK BOLEH NAIK dari baseline;
  · berkas BARU tidak boleh memakai pola itu (pakai FormModal/DetailModal/ConfirmModal);
  · jumlah turun = hijau (baseline dikencangkan P8 dengan `--update`).
Cangkang baku (`components/FormModal.jsx`, `DetailModal.jsx`, `ConfirmModal.jsx`) dan `components/ui/**`
dikecualikan — di sanalah lapisan pop-up memang hidup.

Pakai:
    python scripts/guardrails/verify_custom_modals.py
    python scripts/guardrails/verify_custom_modals.py --self-test
    python scripts/guardrails/verify_custom_modals.py --update     # kencangkan baseline (hanya turun)
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import Guard, G, R, X  # noqa: E402
from _ratchet import (compare, iter_sources, load_baseline, strip_comments,  # noqa: E402
                      tightened, write_baseline)

NAME = "custom_modals"
SHELLS = {"components/FormModal.jsx", "components/DetailModal.jsx", "components/ConfirmModal.jsx"}
PATTERNS = [
    re.compile(r"(?<![\w-])modal-card(?![\w-])"),
    re.compile(r"(?<![\w.-])fixed\s+inset-0(?![\w-])"),
]
NOTE = ("Baseline ratchet INV-UI-11 (pop-up buatan sendiri: `modal-card` + `fixed inset-0` per berkas), dibuat fase 3 · P1 "
        "26 Okt 2026. Hanya boleh TURUN; kencangkan dengan --update (P8).")


def count(text: str) -> int:
    code = strip_comments(text)
    return sum(len(p.findall(code)) for p in PATTERNS)


def current_counts() -> dict:
    out = {}
    for rel, text in iter_sources(lambda r: r in SHELLS):
        n = count(text)
        if n:
            out[rel] = n
    return out


def main() -> int:
    cur = current_counts()
    if "--init" in sys.argv:
        p = write_baseline(NAME, cur, NOTE)
        print(f"baseline ditulis: {p} ({len(cur)} berkas, {sum(cur.values())} pola)")
        return 0
    base = load_baseline(NAME)
    g = Guard("INV-UI-11", "pop-up buatan sendiri hanya boleh berkurang (pakai FormModal/DetailModal)")
    if not base:
        g.add("baseline scripts/guardrails/baselines/custom_modals.json tidak ada — jalankan dengan --init SEKALI.")
        return g.finish()
    g.bump(len(cur) + len(base))
    naik, baru, turun = compare(cur, base)
    for rel, n, b in naik:
        g.add(f"{rel} — pola pop-up buatan sendiri NAIK {b} → {n}. Pakai FormModal (Buat/Ubah) / DetailModal (rincian).")
    for rel, n, _ in baru:
        g.add(f"{rel} — berkas BARU merakit pop-up sendiri ({n}× `modal-card`/`fixed inset-0`). "
              "Pakai components/FormModal.jsx atau DetailModal.jsx.")
    print(f"  berkas berpola: {len(cur)} (baseline {len(base)}) · pola: {sum(cur.values())} (baseline {sum(base.values())})")
    if turun:
        print(f"  turun di {len(turun)} berkas (ratchet bisa dikencangkan dengan --update):")
        for rel, n, b in turun[:12]:
            print(f"    ↓ {rel}: {b} → {n}")
    if "--update" in sys.argv and not naik and not baru:
        p = write_baseline(NAME, tightened(cur, base), NOTE)
        print(f"  baseline dikencangkan: {p}")
    return g.finish()


def self_test() -> int:
    gagal = 0

    def cek(nama, ok):
        nonlocal gagal
        print(f"  {'✓' if ok else '✗'} {nama}")
        gagal += 0 if ok else 1

    cek("modal-card di className terhitung", count('<div className="modal-card p-4">') == 1)
    cek("fixed inset-0 di className terhitung", count('<div className="fixed inset-0 z-50 bg-black/40">') == 1)
    cek("komentar tidak dihitung", count("// dulu: <div className=\"modal-card\">\n/* fixed inset-0 */") == 0)
    cek("kelas mirip tidak dihitung", count('<div className="modal-card-body m-shell-modal-cardish">') == 0)
    cek("selektor .fixed.inset-0 (overlayStack) tidak dihitung", count('const SEL = ".modal-overlay, .fixed.inset-0";') == 0)
    naik, baru, turun = compare({"a.jsx": 3, "b.jsx": 1, "c.jsx": 1}, {"a.jsx": 2, "c.jsx": 2})
    cek("naik terdeteksi", naik == [("a.jsx", 3, 2)])
    cek("berkas baru terdeteksi", baru == [("b.jsx", 1, 0)])
    cek("turun = hijau + dicatat", turun == [("c.jsx", 1, 2)])
    cek("--update hanya menurunkan", tightened({"a.jsx": 5, "c.jsx": 1}, {"a.jsx": 2, "c.jsx": 2, "d.jsx": 1}) == {"a.jsx": 2, "c.jsx": 1})
    print(f"{G if not gagal else R}  SELF-TEST {'HIJAU' if not gagal else 'MERAH'} ({gagal} gagal){X}")
    return gagal


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(1 if self_test() else 0)
    raise SystemExit(main())
