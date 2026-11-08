#!/usr/bin/env python3
"""Audit B3b (2026-11-09) — koleksi Mongo yang dipakai kode backend vs yang terdaftar di ENTITY_REGISTRY.md.

HANYA MEMBACA. Keluaran: tabel koleksi bertema WMS/RFID → jumlah berkas pemakai, terdaftar di registry?,
contoh berkas. Dipakai untuk butir 6 laporan B3b (koleksi/skema baru yang tidak perlu).

    python scripts/audit/b3b_collections.py [--all]
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BE = ROOT / "backend"
PAT = [
    re.compile(r"\bdb\.([a-z][a-z0-9_]{2,})\b"),
    re.compile(r"\bdb\[\s*['\"]([a-z][a-z0-9_]{2,})['\"]\s*\]"),
    re.compile(r"collection\(\s*['\"]([a-z][a-z0-9_]{2,})['\"]"),
    re.compile(r"get_collection\(\s*['\"]([a-z][a-z0-9_]{2,})['\"]"),
]
SKIP = {"command", "client", "list_collection_names", "get_collection", "create_collection", "name"}
THEME = re.compile(r"rfid|wms|inbound|outbound|putaway|goods_receipt|grn|ocr|scan|qc|inspect|warehouse|location|"
                   r"transfer|cycle|registration|cutting|sample|logistic|deliver|loading|repair|lot|makloon|return|"
                   r"gate|label|placement|stock|roll|bin|site|fleet|vehicle|print|dn_|supplier_dn|passage|latch|manifest",
                   re.I)


def main():
    show_all = "--all" in sys.argv
    used = defaultdict(set)
    for f in BE.rglob("*.py"):
        rel = f.relative_to(ROOT).as_posix()
        if "/tests/" in rel or rel.split("/")[-1].startswith(("test_", "backend_test")) or "/scripts/" in rel:
            continue
        try:
            s = f.read_text(encoding="utf-8")
        except Exception:
            continue
        for p in PAT:
            for m in p.finditer(s):
                n = m.group(1)
                if n not in SKIP:
                    used[n].add(rel)
    reg = (ROOT / "ENTITY_REGISTRY.md").read_text(encoding="utf-8")
    rows = []
    for n, files in sorted(used.items()):
        if not show_all and not THEME.search(n):
            continue
        in_reg = bool(re.search(r"(?<![a-z0-9_])" + re.escape(n) + r"(?![a-z0-9_])", reg))
        rows.append((n, len(files), in_reg, sorted(files)[:3]))
    print("| Koleksi | #berkas | Di ENTITY_REGISTRY | Contoh berkas |")
    print("|---|---|---|---|")
    for n, k, r, ex in rows:
        print(f"| `{n}` | {k} | {'ya' if r else '**TIDAK**'} | {', '.join(ex)} |")
    print(f"\nTotal koleksi bertema: {len(rows)} · tidak terdaftar: {sum(1 for r in rows if not r[2])}")


if __name__ == "__main__":
    main()
