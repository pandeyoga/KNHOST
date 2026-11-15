#!/usr/bin/env python3
"""Peta cakupan audit: berkas backend/frontend yang belum pernah disebut dokumen audit atau spesifikasi blueprint dan
tidak diubah sejak basis blueprint. Hanya membaca repo. Dipakai `docs/blueprint/EVALUASI_EKSEKUSI_2026-11-15.md` §6.

    python3 scripts/blueprint/peta_cakupan_audit.py [BASIS]     # bawaan BASIS = fb6bc75 (awal eksekusi blueprint)

Catatan: "disebut/diubah" tidak sama dengan "diperiksa logikanya" — angka ini batas atas cakupan.
"""
import sys
import os, re, subprocess, glob, collections
BASE=sys.argv[1] if len(sys.argv) > 1 else "fb6bc754e3ed03d24990184c792f35daef253bd1"
changed=set(subprocess.run(["git","diff","--name-only",BASE,"HEAD"],capture_output=True,text=True).stdout.split())
docs=""
for pat in ["docs/finance/AUDIT_KEUANGAN_2026-11-13.md","docs/audit/konfigurasi-peran-2026-11-13/*.md","docs/rfid/AUDIT_MIDDLEWARE_RFID_2026-11-08.md","docs/blueprint/unit/*.md"]:
    for f in glob.glob(pat): docs+=open(f,errors="replace").read()
def loc(f):
    try: return sum(1 for _ in open(f,errors="replace"))
    except: return 0
def area(files, label):
    rows=[]
    for f in files:
        base=os.path.basename(f); stem=base.rsplit(".",1)[0]
        aud = (base in docs) or (stem in docs and len(stem)>5)
        rows.append((f, loc(f), aud, f in changed))
    tot=sum(r[1] for r in rows)
    none=[r for r in rows if not r[2] and not r[3]]
    print(f"== {label}: {len(rows)} berkas, {tot:,} baris")
    print(f"   diaudit/dibaca blueprint: {sum(1 for r in rows if r[2])} berkas · diubah blueprint: {sum(1 for r in rows if r[3])} · BELUM disentuh keduanya: {len(none)} berkas, {sum(r[1] for r in none):,} baris ({sum(r[1] for r in none)/tot*100:.0f}%)")
    return none
n1=area(sorted(glob.glob("backend/routers/*.py")),"backend/routers")
n2=area(sorted(glob.glob("backend/services/*.py")),"backend/services")
n3=area(sorted(f for f in glob.glob("frontend/src/features/**/*.jsx",recursive=True) if "__tests__" not in f),"frontend/src/features (.jsx)")
print("\n-- router terbesar yang belum disentuh:")
for f,l,_,_ in sorted(n1,key=lambda r:-r[1])[:25]: print(f"   {l:6} {f}")
print("\n-- service terbesar yang belum disentuh:")
for f,l,_,_ in sorted(n2,key=lambda r:-r[1])[:25]: print(f"   {l:6} {f}")
print("\n-- folder frontend yang belum disentuh (baris):")
c=collections.Counter()
for f,l,_,_ in n3: c[f.split("/")[3]]+=l
for k,v in c.most_common(15): print(f"   {v:7} {k}")
