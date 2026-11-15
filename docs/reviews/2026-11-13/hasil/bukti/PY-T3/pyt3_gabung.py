"""Gabung tiga arah berkas unit PY-T3 ke HEAD tujuan.

    python3 pyt3_gabung.py <sumber_dir> <daftar_berkas> <basis_sha> <head_sha> <keluaran_dir>

<sumber_dir> berisi berkas unit (pohon W atau files/ salinan keadaan). Basis dan HEAD dibaca lewat `git show` di repo
utama (baca saja). Untuk tiap berkas: sama di HEAD & basis → salin sumber; tidak ada di basis & HEAD → baru, salin;
beda → `git merge-file -p HEAD BASIS SUMBER` (bentrok dilaporkan, penanda bentrok ditulis apa adanya).
"""
import os
import subprocess
import sys
import tempfile

REPO = "/home/user/KNHOST"
src, daftar, basis, head, out = sys.argv[1:6]


def show(sha, path):
    r = subprocess.run(["git", "-C", REPO, "show", f"{sha}:{path}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


bentrok, salin, gabung, baru = [], [], [], []
for f in [x.strip() for x in open(daftar) if x.strip()]:
    sumber = open(os.path.join(src, f), "rb").read()
    b, h = show(basis, f), show(head, f)
    os.makedirs(os.path.dirname(os.path.join(out, f)) or ".", exist_ok=True)
    if b is None and h is None:
        hasil = sumber
        baru.append(f)
    elif b == h:
        hasil = sumber
        salin.append(f)
    elif b is None:
        bentrok.append(f + " (baru di unit DAN di HEAD)")
        hasil = sumber
    else:
        with tempfile.TemporaryDirectory() as d:
            ph, pb, ps = (os.path.join(d, n) for n in ("head", "basis", "sumber"))
            open(ph, "wb").write(h or b"")
            open(pb, "wb").write(b)
            open(ps, "wb").write(sumber)
            r = subprocess.run(["git", "merge-file", "-p", ph, pb, ps], capture_output=True)
            hasil = r.stdout
            (bentrok if r.returncode else gabung).append(f)
    open(os.path.join(out, f), "wb").write(hasil)
print(f"salin {len(salin)} · baru {len(baru)} · gabung bersih {len(gabung)} · BENTROK {len(bentrok)}")
for f in gabung:
    print("  gabung:", f)
for f in bentrok:
    print("  BENTROK:", f)
