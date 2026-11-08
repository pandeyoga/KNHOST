#!/usr/bin/env python3
"""B3a (audit 2026-11-09) — field data vs pemakaian kode (baca-saja, stdlib).

Masukan: profile.json (keluaran b3a_field_profile.js) + akar repo. Untuk setiap field TINGKAT ATAS koleksi terpilih:
  * jumlah dokumen yang memuat field (data),
  * jumlah SEBUTAN nama field di backend app (non-uji) dan frontend/src,
  * jumlah panggilan TULIS app yang menyebut field (dari calls.json b3a_db_writers.py).
Kelas: TULIS_TANPA_BACA (ditulis app, hampir tak disebut di tempat lain), DATA_TANPA_KODE (ada di data, tidak disebut
kode mana pun — sisa seed/migrasi), JARANG (≤2 sebutan selain penulis).
"""
import argparse
import json
import os
import re
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def load_sources():
    be, fe = [], []
    for base, dirs, files in os.walk(os.path.join(ROOT, "backend")):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "tests", "scripts")]
        for f in files:
            if f.endswith(".py") and not f.startswith(("test_", "backend_test", "poc_", "seed")) and not f.endswith("_test.py"):
                be.append((os.path.relpath(os.path.join(base, f), ROOT), open(os.path.join(base, f), encoding="utf-8", errors="ignore").read()))
    for base, dirs, files in os.walk(os.path.join(ROOT, "frontend", "src")):
        dirs[:] = [d for d in dirs if d not in ("__tests__", "node_modules")]
        for f in files:
            if f.endswith((".js", ".jsx", ".ts", ".tsx")) and ".test." not in f:
                fe.append((os.path.relpath(os.path.join(base, f), ROOT), open(os.path.join(base, f), encoding="utf-8", errors="ignore").read()))
    return be, fe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--calls", required=True)
    ap.add_argument("--colls", required=True)
    a = ap.parse_args()
    prof = json.load(open(a.profile, encoding="utf-8"))
    calls = json.load(open(a.calls, encoding="utf-8"))
    be, fe = load_sources()
    for coll in a.colls.split(","):
        p = prof[coll]
        n = p["n"]
        writes = defaultdict(set)
        for c in calls:
            if c["coll"] == coll and c["rw"] == "w" and c["kind"] == "app":
                for f in c.get("fields", []):
                    writes[f.split(".")[0]].add(f"{c['file']}:{c['line']}")
        print(f"### {coll} ({n} dok)")
        print("| field | dok berisi | sebutan BE | sebutan FE | panggilan tulis app | kelas |")
        print("|---|---:|---:|---:|---:|---|")
        tops = sorted({k.split(".")[0].split("[")[0] for k in p["fields"]})
        for f in tops:
            e = p["fields"].get(f) or {}
            have = e.get("filled", 0)
            pat = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(f) + r"(?![A-Za-z0-9_])")
            nbe = sum(len(pat.findall(s)) for _, s in be)
            nfe = sum(len(pat.findall(s)) for _, s in fe)
            nw = len(writes.get(f, ()))
            cls = ""
            if nbe + nfe == 0:
                cls = "DATA_TANPA_KODE"
            elif nw and (nbe - nw) <= 1 and nfe == 0:
                cls = "TULIS_TANPA_BACA (kandidat)"
            elif (nbe + nfe) <= 3:
                cls = "JARANG"
            print(f"| `{f}` | {have} | {nbe} | {nfe} | {nw} | {cls} |")
        print()


if __name__ == "__main__":
    main()
