#!/usr/bin/env python3
"""Audit pola UI (docs/blueprint/04_POLA_UI.md §4 "Yang dilarang") — langkah 2 rencana pola UI 16 Nov.

Memindai `frontend/src/features/**/*.jsx` dan menghitung per berkas pola yang dilarang standar:
  chip   — deret chip/tombol/tab sebagai SARINGAN (`FilterChips`, `StatusTabs`, chip buatan `rounded-full … onClick=… setFilter`)
  info   — bilah penjelasan permanen (`notice-bar info` / `notice-bar` tanpa syarat di awal baris JSX)
  kartu  — kartu angka (`metric-card`/`stat-card`/`MetricRow`/`KpiCard`) di berkas yang tidak memberi `onClick` pada kartu
  buat   — tombol buat/tambah di kepala halaman (`view-header` … `primary-button` berdekatan)
Hasil: tabel Markdown diurut skor. Ini DAFTAR KANDIDAT (pemindai teks, bukan penilaian akhir): tiap baris diperiksa saat
gelombangnya dikerjakan. BACA SAJA; tidak mengubah kode.

Pakai: python3 scripts/guardrails/audit_pola_ui.py [--md keluaran.md]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "frontend" / "src" / "features"

PAT_CHIP = [re.compile(r"<FilterChips\b"), re.compile(r"<StatusTabs\b"),
            re.compile(r"rounded-full[^\"]*\"[^>]*onClick=\{\(\) => set\w*(Filter|Status|Tab|Kind|Type)\w*\(")]
PAT_INFO = re.compile(r"className=\"notice-bar(?: info)?\"")   # bilah info/polos (bukan success/danger/warning)
PAT_CARD = re.compile(r"metric-card|stat-card|<MetricRow\b|<KpiCard\b")
PAT_CARD_CLICK = re.compile(r"onClick")
PAT_HEADER = re.compile(r"className=\"view-header")
PAT_CREATE = re.compile(r"primary-button[^>]*>[^<]*(?:<\w+[^>]*/>\s*)?\s*(Buat|Tambah|Baru|\+)", re.I)


def scan(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    chip = sum(len(p.findall(text)) for p in PAT_CHIP)
    info = sum(1 for ln in lines if PAT_INFO.search(ln))
    cards = len(PAT_CARD.findall(text))
    card_bad = 0
    if cards:
        clickable = ("<MetricRow" in text and "onClick:" in text) or any(
            PAT_CARD_CLICK.search("\n".join(lines[max(0, i - 2):i + 6])) for i, ln in enumerate(lines) if PAT_CARD.search(ln))
        card_bad = 0 if clickable else cards
    create = 0
    for i, ln in enumerate(lines):
        if PAT_HEADER.search(ln):
            window = "\n".join(lines[i:i + 14])
            if PAT_CREATE.search(window):
                create += 1
        if "<PageHeader" in ln and "actions=" in "\n".join(lines[i:i + 4]) and PAT_CREATE.search("\n".join(lines[i:i + 8])):
            create += 1
    return {"chip": chip, "info": info, "kartu": card_bad, "buat": create}


def main() -> int:
    rows = []
    for p in sorted(SRC.rglob("*.jsx")):
        if "__tests__" in p.parts:
            continue
        r = scan(p)
        kinds = sum(1 for v in r.values() if v)
        if kinds:
            rows.append((kinds * 10 + sum(r.values()), p.relative_to(ROOT / "frontend" / "src").as_posix(), r))
    rows.sort(key=lambda x: (-x[0], x[1]))
    out = ["| Berkas | Chip/tab saringan | Bilah penjelasan | Kartu angka tanpa klik | Buat di kepala |",
           "|---|---|---|---|---|"]
    tot = {"chip": 0, "info": 0, "kartu": 0, "buat": 0}
    for _, name, r in rows:
        for k in tot:
            tot[k] += r[k]
        out.append(f"| `{name}` | {r['chip'] or ''} | {r['info'] or ''} | {r['kartu'] or ''} | {r['buat'] or ''} |")
    summary = (f"{len(rows)} berkas · chip/tab saringan {tot['chip']} · bilah penjelasan {tot['info']} · "
               f"kartu angka tanpa klik {tot['kartu']} · tombol buat di kepala {tot['buat']}")
    md = "\n".join([summary, "", *out])
    if "--md" in sys.argv:
        Path(sys.argv[sys.argv.index("--md") + 1]).write_text(md + "\n", encoding="utf-8")
    print(md if "--md" not in sys.argv else summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
