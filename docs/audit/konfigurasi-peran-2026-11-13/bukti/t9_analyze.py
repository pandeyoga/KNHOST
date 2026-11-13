"""Analisis hasil T9: endpoint tulis yang dilewati akun tanpa izin.

    python t9_analyze.py <t9.json> [--md]
"""
import collections
import json
import re
import sys

d = json.load(open(sys.argv[1]))
MD = "--md" in sys.argv
inv = d["inv"]


def tmpl(k):
    m, p = k.split(" ", 1)
    return f"{m} {re.sub(r'{[^}]+}', '{}', p)}"


def kelas(st):
    if st in (401, 403):
        return "ditolak"
    if st == 422:
        return "tak_teruji"
    if st == -1 or st >= 500:
        return "galat"
    return "lolos"


ring = {}
for kode, res in d["hasil"].items():
    c = collections.Counter()
    for k, (st, det) in res.items():
        cat = (inv.get(tmpl(k)) or {}).get("cat", "?")
        c[(cat, kelas(st))] += 1
    ring[kode] = c

print("Ringkasan (kategori gerbang statik × hasil), per akun")
for kode, c in ring.items():
    print(f"\n[{kode}]  sesi akhir: {d.get('sesi_akhir', {}).get(kode)}")
    cats = sorted({k[0] for k in c})
    print(f"  {'kategori':<12} {'ditolak':>8} {'lolos':>7} {'422':>6} {'galat':>6}")
    for cat in cats:
        print(f"  {cat:<12} {c[(cat, 'ditolak')]:>8} {c[(cat, 'lolos')]:>7} {c[(cat, 'tak_teruji')]:>6} {c[(cat, 'galat')]:>6}")


def daftar(kode, cats, kls="lolos"):
    out = []
    for k, (st, det) in sorted(d["hasil"][kode].items()):
        e = inv.get(tmpl(k)) or {}
        if e.get("cat") in cats and kelas(st) == kls:
            g = "; ".join(f"{x['k']}({','.join(map(str, x['a']))})" for x in e.get("guards", [])
                          if x["k"] != "current_user")[:90]
            out.append((k, st, det, f"{e.get('file')}:{e.get('line')}", g))
    return out


for judul, kode, cats, kls in (
    ("A. Endpoint BERIZIN yang dilewati akun tanpa izin apa pun (kosong)", "kosong", ("IZIN", "IZIN_CABANG"), "lolos"),
    ("B. Endpoint bergerbang NAMA PERAN yang dilewati peran beracuan Manajer tanpa izin (mgr0)", "mgr0", ("PERAN",), "lolos"),
    ("C. Endpoint BERIZIN yang dilewati mgr0 tetapi ditolak untuk kosong", "mgr0", ("IZIN", "IZIN_CABANG"), "lolos"),
    ("D. Endpoint HANYA LOGIN yang dilewati akun kosong", "kosong", ("LOGIN",), "lolos"),
    ("E. Galat server (5xx) untuk akun kosong", "kosong", ("IZIN", "IZIN_CABANG", "PERAN", "LOGIN", "TANPA", "?"), "galat"),
):
    rows = daftar(kode, cats, kls)
    if judul.startswith("C."):
        tolak_kosong = {k for k, (st, _) in d["hasil"]["kosong"].items() if kelas(st) == "ditolak"}
        rows = [r for r in rows if r[0] in tolak_kosong]
    print(f"\n{judul}: {len(rows)}")
    for k, st, det, loc, g in rows:
        if MD:
            print(f"| `{k}` | {st} | {det[:70].replace('|', '/')} | `{loc}` | {g} |")
        else:
            print(f"  {st} {k:<70} {loc:<34} {det[:60]!r}  [{g}]")
