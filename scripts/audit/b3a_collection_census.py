#!/usr/bin/env python3
"""B3a (audit 2026-11-09) — sensus koleksi: KODE vs DB nyata vs ENTITY_REGISTRY.md (baca-saja, stdlib).

Masukan:
  --calls   JSON keluaran `b3a_db_writers.py --json` (daftar panggilan Mongo per koleksi)
  --db      TSV `nama<TAB>jumlah` (hasil `db.getCollectionNames()` + estimatedDocumentCount)
  --registry ENTITY_REGISTRY.md
Keluaran: tabel markdown ke stdout — per koleksi: dipakai kode (app r/w, script, test), jumlah dok di DB,
terdaftar di registry, dan kelas temuan:
  TAK_TERDAFTAR      dipakai kode app + ada di DB, tidak disebut registry
  TERDAFTAR_TAK_DIPAKAI  disebut registry sebagai koleksi, tidak dipakai kode app
  KOSONG             dipakai kode app, 0 dokumen di DB (fitur belum jalan / mati)
  HANYA_DB           ada di DB, tidak dipakai kode mana pun (sisa / yatim)
  HANYA_TULIS        kode app hanya menulis (tak pernah dibaca app)
  HANYA_BACA         kode app hanya membaca (penulis di luar app/ tak ada)
  NAMA_MIRIP         nama berjarak edit kecil / akar sama dengan koleksi lain
"""
import argparse
import difflib
import json
import re
from collections import defaultdict


def registry_collections(path):
    txt = open(path, encoding="utf-8").read()
    names = set()
    for m in re.finditer(r"Collection:\s+`?([a-z][a-z0-9_]+)`?", txt):
        names.add(m.group(1))
    for m in re.finditer(r"^#{3,4}\s+`?([a-z][a-z0-9_]+)`?", txt, re.M):
        names.add(m.group(1))
    for m in re.finditer(r"^#{3,4}\s+([a-z0-9_ +·`]+)\s*(\[|\(|\*|$)", txt, re.M):
        for part in re.split(r"[+·,]", m.group(1)):
            p = part.strip(" `")
            if re.fullmatch(r"[a-z][a-z0-9_]+", p):
                names.add(p)
    # sel tabel "| ... | `koleksi` | ..."
    for m in re.finditer(r"\|\s*`([a-z][a-z0-9_]+)`", txt):
        names.add(m.group(1))
    forbidden = set()
    sec = re.search(r"## 🚨 FORBIDDEN(.*?)\n## ", txt, re.S)
    if sec:
        forbidden = set(re.findall(r"`([a-z][a-z0-9_]+)`", sec.group(1)))
    return names, forbidden, txt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calls", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--registry", required=True)
    ap.add_argument("--root", default="", help="akar kode; dipakai menghitung SEBUTAN nama koleksi (akses dinamis)")
    a = ap.parse_args()
    mention = defaultdict(set)
    if a.root:
        import os
        pat = re.compile(r"[\"'.]([a-z][a-z0-9_]{2,})[\"'.]")
        for base, dirs, files in os.walk(os.path.join(a.root, "backend")):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "tests", "scripts")]
            for f in files:
                if not f.endswith(".py") or f.startswith(("test_", "backend_test", "seed", "poc_")) or f.endswith("_test.py"):
                    continue
                path = os.path.join(base, f)
                for m in pat.finditer(open(path, encoding="utf-8", errors="ignore").read()):
                    mention[m.group(1)].add(os.path.relpath(path, a.root))
    calls = json.load(open(a.calls, encoding="utf-8"))
    db = {}
    for line in open(a.db, encoding="utf-8"):
        parts = line.rstrip("\n").split("\t")
        if len(parts) == 2 and parts[0] != "TOTAL":
            db[parts[0]] = int(parts[1])
    reg, forbidden, regtxt = registry_collections(a.registry)
    use = defaultdict(lambda: {"app_r": 0, "app_w": 0, "script": 0, "test": 0, "files": set()})
    for c in calls:
        u = use[c["coll"]]
        if c["kind"] == "app":
            u["app_" + c["rw"]] += 1
            u["files"].add(c["file"])
        else:
            u[c["kind"]] += 1
    code_colls = {k for k, v in use.items() if (v["app_r"] or v["app_w"]) and k != "<dinamis>"}
    all_colls = sorted((set(db) | code_colls | {k for k in use if k != "<dinamis>"}))
    rows = []
    for c in all_colls:
        u = use.get(c, {"app_r": 0, "app_w": 0, "script": 0, "test": 0, "files": set()})
        in_db = c in db
        n = db.get(c)
        in_reg = c in reg or f"`{c}`" in regtxt
        flags = []
        app = u["app_r"] + u["app_w"]
        if app and in_db and not in_reg:
            flags.append("TAK_TERDAFTAR")
        if app and not in_db:
            flags.append("TAK_ADA_DI_DB")
        if app and in_db and n == 0:
            flags.append("KOSONG")
        ment = len(mention.get(c, ()))
        if in_db and not app and ment:
            flags.append(f"AKSES_DINAMIS({ment}_berkas)")
        elif in_db and not app and not u["script"] and not u["test"]:
            flags.append("HANYA_DB")
        elif in_db and not app:
            flags.append("TANPA_KODE_APP")
        if u["app_w"] and not u["app_r"]:
            flags.append("HANYA_TULIS")
        if u["app_r"] and not u["app_w"]:
            flags.append("HANYA_BACA")
        if c in forbidden:
            flags.append("NAMA_TERLARANG")
        rows.append((c, u, n, in_reg, flags))
    regonly = sorted(x for x in reg if x not in db and x not in use and "_" in x and not x.startswith("prefix"))
    names = [r[0] for r in rows if r[2] is not None or (r[1]["app_r"] + r[1]["app_w"])]
    similar = []
    for i, x in enumerate(names):
        for y in names[i + 1:]:
            if x.rstrip("s") == y.rstrip("s") or difflib.SequenceMatcher(None, x, y).ratio() > 0.88:
                similar.append((x, y))
    print("| koleksi | app baca | app tulis | script | test | dok DB | registry | kelas |")
    print("|---|---:|---:|---:|---:|---:|:---:|---|")
    for c, u, n, in_reg, flags in rows:
        print(f"| `{c}` | {u['app_r']} | {u['app_w']} | {u['script']} | {u['test']} | "
              f"{'—' if n is None else n} | {'ya' if in_reg else '**tidak**'} | {' '.join(flags)} |")
    print()
    print("Ringkasan:", {k: sum(1 for r in rows if any(f.startswith(k) for f in r[4])) for k in
                         ("TAK_TERDAFTAR", "TAK_ADA_DI_DB", "KOSONG", "AKSES_DINAMIS", "HANYA_DB", "TANPA_KODE_APP", "HANYA_TULIS",
                          "HANYA_BACA", "NAMA_TERLARANG")})
    print(f"Koleksi DB: {len(db)} · dipakai kode app: {len(code_colls)} · nama di registry (heuristik): {len(reg)}")
    print("Nama di registry tanpa koleksi di DB maupun kode (heuristik, termasuk rencana):", ", ".join(regonly[:80]))
    print("Pasangan nama mirip:", ", ".join(f"{x}~{y}" for x, y in similar))


if __name__ == "__main__":
    main()
