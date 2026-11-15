#!/usr/bin/env python3
"""Bandingkan gate per PELANGGARAN, bukan per status gate (kebijakan uji hemat, `03_LINGKUNGAN_UJI.md` §6).

Masalah yang ditutup: pembanding lama (`bandingkan_gate.py`) hanya melihat apakah sebuah gate berubah HIJAU → MERAH.
Gate yang sudah merah di garis dasar (mis. `guard:approval_queues` 3 pelanggaran) bisa bertambah pelanggaran baru tanpa
terlihat "lebih merah". Pada 15 Nov 2026 ditemukan 13 pelanggaran baru yang lolos dengan cara itu.

Pemakaian (hanya membaca log; tidak menjalankan gate):
    python3 scripts/blueprint/bandingkan_pelanggaran_gate.py <log_garis_dasar> <log_gate_baru>
    # contoh garis dasar sebelum blueprint: docs/reviews/2026-11-13/garis-dasar/08_gate_ci.log

Keluar 1 bila ada pelanggaran baru (baris "✗ …" di bagian gate yang tidak ada di garis dasar), 0 bila tidak.
Nomor baris dan angka dinormalkan supaya pergeseran baris atau jumlah data tidak dianggap pelanggaran baru.
"""
import re
import sys

ANSI = re.compile(r"\x1b\[[0-9;]*m")
BISING = ("FAIL (rc", "ADA GATE MERAH", "pelanggaran", "MERAH —", "VERDICT")


def _norm(baris: str) -> str:
    s = re.sub(r":\d+", "", baris)            # nomor baris berkas
    s = re.sub(r"\b\d+(?:[.,]\d+)?\b", "#", s)  # angka (jumlah dokumen, durasi)
    return re.sub(r"\s+", " ", s).strip()[:160]


def pelanggaran(path: str) -> dict:
    teks = ANSI.sub("", open(path, encoding="utf-8", errors="replace").read())
    hasil = {}
    for bagian in re.split(r"\n▶ ", teks)[1:]:
        judul = bagian.split("\n", 1)[0].strip()
        if "SELF-TEST" in judul:   # uji-diri sengaja mencetak "✗" (bukti penjaga bisa memerah), bukan pelanggaran kode
            continue
        nama = judul.split(" (")[0].strip()   # gate yang berganti keterangan (mis. guard:page_tabs) tetap satu kunci
        daftar = hasil.get(nama, set())
        for baris in bagian.splitlines()[1:]:
            b = baris.strip()
            if b.startswith("✗") and not any(x in b for x in BISING):
                daftar.add(_norm(b[1:]))
        if daftar:
            hasil[nama] = daftar
    return hasil


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    lama, baru = pelanggaran(sys.argv[1]), pelanggaran(sys.argv[2])
    ada_baru = False
    for gate in sorted(set(lama) | set(baru)):
        tambah = sorted(baru.get(gate, set()) - lama.get(gate, set()))
        hilang = lama.get(gate, set()) - baru.get(gate, set())
        if not tambah and not hilang:
            continue
        print(f"== {gate}: garis dasar {len(lama.get(gate, ()))} · sekarang {len(baru.get(gate, ()))} · "
              f"baru {len(tambah)} · hilang {len(hilang)}")
        for t in tambah:
            print(f"   + {t}")
        ada_baru = ada_baru or bool(tambah)
    print("HASIL:", "ADA PELANGGARAN BARU" if ada_baru else "tidak ada pelanggaran baru")
    return 1 if ada_baru else 0


if __name__ == "__main__":
    sys.exit(main())
