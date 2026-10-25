#!/usr/bin/env python3
"""INV-UI-12 — TAB MAKSIMAL 2 TINGKAT: tab/pil buatan sendiri HANYA BOLEH BERKURANG (ratchet, fase 3 · P1, L-01).

MASALAH YANG DICEGAH (audit UI tahap 2, L-01)
==============================================
Satu layar bisa punya bilah hub (pil hitam) → tab layar → pil/segmen → tombol-toggle, dengan EMPAT gaya berbeda.
Aturan fase 3 (§1.4): tingkat 1 = HubTabs (bilah hub), tingkat 2 = `components/PageTabs.jsx`; saringan =
`components/FilterChips.jsx` atau KNSelect, BUKAN tab; kebutuhan tingkat ke-3 → chip, seksi berjudul, atau pop-up.

Pola usang yang dihitung per berkas (komentar diabaikan):
  1. PIL HITAM — kelas aktif `bg-[#1C1C1E]` dipilih lewat ternary dengan `rounded-full` di className yang sama
     (gaya HubTabs lama & segmen buatan sendiri);
  2. TOMBOL-TOGGLE — `x ? "primary-button …" : "secondary-button …"` (tab dibuat dari tombol aksi);
  3. `TabBtn` buatan sendiri (definisi/pemakaian);
  4. `cfg-group-btn` (daftar grup Pusat Pengaturan sebagai tab vertikal).
Jumlah per berkas TIDAK BOLEH NAIK dari baseline; berkas BARU tidak boleh memakai pola itu. Turun = hijau.

Pakai:
    python scripts/guardrails/verify_page_tabs.py
    python scripts/guardrails/verify_page_tabs.py --self-test
    python scripts/guardrails/verify_page_tabs.py --update     # kencangkan baseline (hanya turun)
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import Guard, G, R, X  # noqa: E402
from _ratchet import (compare, iter_sources, load_baseline, strip_comments,  # noqa: E402
                      tightened, write_baseline)

NAME = "page_tabs"
STANDARD = {"components/PageTabs.jsx", "components/FilterChips.jsx", "components/HubTabs.jsx"}
PILL_ACTIVE = re.compile(r"\?\s*[\"'`][^\"'`]*?bg-\[#1C1C1E\]")
TOGGLE = re.compile(r"\?\s*[\"'`]primary-button[^\"'`]*[\"'`]\s*:\s*[\"'`]secondary-button")
TABBTN = re.compile(r"\bTabBtn\b")
CFG_GROUP = re.compile(r"(?<![\w-])cfg-group-btn(?![\w-])")
NOTE = ("Baseline ratchet INV-UI-12 (pil hitam · tombol-toggle primary/secondary · TabBtn · cfg-group-btn per berkas), "
        "dibuat fase 3 · P1 26 Okt 2026 sesudah HubTabs dibakukan. Hanya boleh TURUN; kencangkan dengan --update (P8).")


def count(text: str) -> int:
    code = strip_comments(text)
    pills = sum(1 for m in PILL_ACTIVE.finditer(code) if "rounded-full" in code[max(0, m.start() - 400):m.end() + 200])
    return pills + len(TOGGLE.findall(code)) + len(TABBTN.findall(code)) + len(CFG_GROUP.findall(code))


def current_counts() -> dict:
    out = {}
    for rel, text in iter_sources(lambda r: r in STANDARD):
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
    g = Guard("INV-UI-12", "tab maksimal 2 tingkat — tab/pil buatan sendiri hanya boleh berkurang")
    if not base:
        g.add("baseline scripts/guardrails/baselines/page_tabs.json tidak ada — jalankan dengan --init SEKALI.")
        return g.finish()
    g.bump(len(cur) + len(base))
    naik, baru, turun = compare(cur, base)
    for rel, n, b in naik:
        g.add(f"{rel} — tab/pil buatan sendiri NAIK {b} → {n}. Tingkat 2 = PageTabs; saringan = FilterChips/KNSelect.")
    for rel, n, _ in baru:
        g.add(f"{rel} — berkas BARU memakai tab/pil buatan sendiri ({n}×). Pakai components/PageTabs.jsx "
              "(tab) atau components/FilterChips.jsx (saringan).")
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

    pill = ('<button className={`px-3 py-1 rounded-full border ${on ? "bg-[#1C1C1E] text-white" : "bg-white"}`}>A</button>')
    cek("pil hitam aktif (rounded-full + ternary) terhitung", count(pill) == 1)
    cek("bg-[#1C1C1E] tanpa ternary (tombol gelap biasa) tidak dihitung",
        count('<button className="rounded-full bg-[#1C1C1E] text-white">Bayar</button>') == 0)
    cek("tombol-toggle primary/secondary terhitung",
        count('<button className={tab === k ? "primary-button !py-1.5" : "secondary-button !py-1.5"} />') == 1)
    cek("primary-button biasa tidak dihitung", count('<button className="primary-button !py-1.5">Simpan</button>') == 0)
    cek("TabBtn & cfg-group-btn terhitung", count('const TabBtn = () => <button className="cfg-group-btn" />;\n<TabBtn />') == 3)
    cek("komentar tidak dihitung", count('// dulu TabBtn + "cfg-group-btn"\n/* rounded-full ? "bg-[#1C1C1E]" */') == 0)
    naik, baru, turun = compare({"a.jsx": 2, "n.jsx": 1}, {"a.jsx": 1, "b.jsx": 3})
    cek("naik + berkas baru → merah; turun dicatat", naik == [("a.jsx", 2, 1)] and baru == [("n.jsx", 1, 0)] and turun == [("b.jsx", 0, 3)])
    print(f"{G if not gagal else R}  SELF-TEST {'HIJAU' if not gagal else 'MERAH'} ({gagal} gagal){X}")
    return gagal


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(1 if self_test() else 0)
    raise SystemExit(main())
