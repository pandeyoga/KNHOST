#!/usr/bin/env python3
"""B3a — ubah profile.json (keluaran b3a_field_profile.js) menjadi tabel markdown per koleksi.
Pakai: python scripts/audit/b3a_profile_md.py profile.json koleksi1,koleksi2 [kedalaman=1] > lampiran.md"""
import json
import re
import sys

prof = json.load(open(sys.argv[1], encoding="utf-8"))
colls = sys.argv[2].split(",")
depth = int(sys.argv[3]) if len(sys.argv) > 3 else 1
for c in colls:
    p = prof.get(c)
    if not p:
        continue
    n = p["n"]
    print(f"### `{c}` — {n} dokumen diprofil, {len(p['fields'])} path\n")
    print("| path | ada % | terisi % | tipe | contoh nilai |")
    print("|---|---:|---:|---|---|")
    for path, e in sorted(p["fields"].items()):
        if path.count(".") > depth or re.search(r"\.roll_(results|actuals)\.roll_", path):
            continue
        types = ", ".join(f"{k}:{v}" for k, v in e["types"].items())
        smp = " · ".join(s.replace("|", "/").replace("\n", " ")[:28] for s in e["samples"][:3])
        print(f"| `{path}` | {100.0 * e['n'] / n:.1f} | {100.0 * e['filled'] / n:.1f} | {types} | {smp} |")
    print()
