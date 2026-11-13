#!/usr/bin/env python3
"""Ubah papan STATUS.md tanpa menyunting tabel dengan tangan.

    python docs/blueprint/alat/status.py set <ID> <status> [--commit SHA] [--laporan PATH] [--catatan TEKS]
    python docs/blueprint/alat/status.py lepas          # menunggu → siap bila semua prasyarat selesai/tervalidasi
    python docs/blueprint/alat/status.py berikut        # cetak ID unit `siap` teratas (kosong bila tidak ada)
    python docs/blueprint/alat/status.py ringkas        # jumlah per status

Status sah: menunggu, siap, tahan, dikerjakan, selesai. `tervalidasi` hanya oleh reviewer (ditolak di sini).
Prasyarat berbentuk "gelombang N tervalidasi" hanya terpenuhi oleh status `tervalidasi`.
"""
import collections
import re
import sys
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "STATUS.md"
RX_ID = r"(?:PK-\d+[a-z]?|(?:PR|KF|KP|MN|KM|CR|PM|TX|PY|AG)-T\d+[a-z]?)"
SAH = {"menunggu", "siap", "tahan", "dikerjakan", "selesai"}


def baca():
    baris = P.read_text(encoding="utf-8").split("\n")
    idx = {}
    for i, b in enumerate(baris):
        c = b.split("|")
        if len(c) >= 10 and re.fullmatch(RX_ID, c[2].strip()):
            idx[c[2].strip()] = i
    return baris, idx


def sel(b):
    return [x.strip() for x in b.split("|")]


def tulis(baris):
    P.write_text("\n".join(baris), encoding="utf-8", newline="\n")


def set_baris(baris, i, status=None, commit=None, laporan=None, catatan=None):
    c = baris[i].split("|")
    if status:
        c[5] = f" {status} "
    if commit:
        c[6] = f" {commit} "
    if laporan:
        c[7] = f" {laporan} "
    if catatan is not None:
        c[8] = f" {catatan} "
    baris[i] = "|".join(c)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    baris, idx = baca()
    st = {k: sel(baris[i])[5] for k, i in idx.items()}
    if cmd == "set":
        uid, status = sys.argv[2], sys.argv[3]
        if status not in SAH:
            print(f"status tidak sah: {status}")
            return 2
        opt = {k: sys.argv[sys.argv.index(f"--{k}") + 1] for k in ("commit", "laporan", "catatan") if f"--{k}" in sys.argv}
        if uid not in idx:
            print(f"ID tidak ada di STATUS.md: {uid}")
            return 2
        set_baris(baris, idx[uid], status, opt.get("commit"), opt.get("laporan"), opt.get("catatan"))
        tulis(baris)
        print(f"{uid} → {status}")
        return 0
    if cmd == "lepas":
        lepas = []
        for k, i in idx.items():
            if st[k] != "menunggu":
                continue
            pr_txt = sel(baris[i])[4]
            prs = re.findall(RX_ID, pr_txt)
            butuh_valid = "tervalidasi" in pr_txt
            ok = all(st.get(p) in (("tervalidasi",) if butuh_valid else ("selesai", "tervalidasi")) for p in prs)
            if ok and prs:
                set_baris(baris, i, "siap")
                lepas.append(k)
        tulis(baris)
        print("dilepas menjadi siap:", ", ".join(lepas) or "—")
        return 0
    if cmd == "berikut":
        for k, i in idx.items():
            if st[k] == "siap":
                print(k)
                return 0
        return 0
    if cmd == "ringkas":
        print(dict(collections.Counter(st.values())))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
