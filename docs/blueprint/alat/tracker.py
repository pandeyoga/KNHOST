#!/usr/bin/env python3
"""Perbarui baris temuan paket 2026-11-13 di docs/reviews/TRACKER.md tanpa menyunting tabel dengan tangan.

    python docs/blueprint/alat/tracker.py --status implemented_pending_review --berlaku "ya — dijalankan" \
        --commit abc1234 --laporan "[PK-05](2026-11-13/hasil/PK-05.md)" SL-01 SL-02 ...

Status yang boleh ditulis implementer: in_progress, implemented_pending_review, pending_decision.
`verified` dan `reopened` ditolak (hanya reviewer).
"""
import argparse
import re
import sys
from pathlib import Path

P = Path(__file__).resolve().parents[2] / "reviews" / "TRACKER.md"
BOLEH = {"in_progress", "implemented_pending_review", "pending_decision"}
BAGIAN = ("Audit keuangan — paket 2026-11-13", "Temuan tambahan riset modul — paket 2026-11-13",
          "Audit konfigurasi dan peran — paket 2026-11-13")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--status", required=True)
    ap.add_argument("--berlaku", default="")
    ap.add_argument("--commit", default="")
    ap.add_argument("--laporan", default="")
    a = ap.parse_args()
    if a.status not in BOLEH:
        print(f"status tidak boleh ditulis implementer: {a.status}")
        return 2
    lines = P.read_text(encoding="utf-8").split("\n")
    bagian, sisa = "", set(a.ids)
    for i, ln in enumerate(lines):
        if ln.startswith("## "):
            bagian = ln[3:].strip()
        if bagian not in BAGIAN:
            continue
        m = re.match(r"^\| ([A-Z]{2}-(?:UX|\d+)) \|", ln)
        if not m or m.group(1) not in sisa:
            continue
        c = ln.split("|")
        c[5] = f" {a.status} "
        if a.berlaku:
            c[6] = f" {a.berlaku} "
        if a.commit:
            c[7] = f" {a.commit} "
        if a.laporan:
            c[8] = f" {a.laporan} "
        lines[i] = "|".join(c)
        sisa.discard(m.group(1))
    P.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"diperbarui: {len(a.ids) - len(sisa)}" + (f" · tidak ditemukan: {sorted(sisa)}" if sisa else ""))
    return 1 if sisa else 0


if __name__ == "__main__":
    sys.exit(main())
