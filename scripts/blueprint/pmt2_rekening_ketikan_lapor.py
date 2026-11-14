"""PM-T2 — LAPOR SAJA: templat cetak (`pdf_templates`) yang naskahnya memuat calon nomor rekening KETIKAN.

    python scripts/blueprint/pmt2_rekening_ketikan_lapor.py            # lapor (satu-satunya mode)
    python scripts/blueprint/pmt2_rekening_ketikan_lapor.py --pt ent_ksc

Sejak PM-T2 dokumen Konfirmasi Pesanan & Faktur mencetak kotak "Instruksi Pembayaran" dari rekening tujuan pesanan
(master rekening PM-T1). Templat yang naskah pembuka, penutup, atau footer-nya masih memuat nomor rekening yang dulu
diketik akan tampil BERDAMPINGAN dengan kotak baru — dua nomor rekening di satu dokumen. Skrip ini mencari naskah berisi
delapan digit atau lebih (berurutan, atau dipisah satu spasi / tanda hubung / titik, mis. `123-456-7890`) supaya pemilik
membersihkannya lewat layar Pengaturan › Dokumen & Cetak › Template Dokumen. Skrip TIDAK mengubah apa pun (data nyata =
titik henti H3; unit ini tidak mengubah isi templat). Nomor telepon panjang ikut terlapor — calon, bukan kepastian.

Kueri setara (mongosh, baca saja):
    db.pdf_templates.find({$or: [{"config.intro_text": {$regex: "\\d(?:[ .-]?\\d){7,}"}},
                                 {"config.closing_note": {$regex: "\\d(?:[ .-]?\\d){7,}"}},
                                 {"config.footer_text": {$regex: "\\d(?:[ .-]?\\d){7,}"}}]},
                          {_id: 0, doc_type: 1, entity_id: 1, "config.intro_text": 1, "config.closing_note": 1,
                           "config.footer_text": 1})
Dijalankan di dalam container backend seperti skrip lain (butuh `backend/.env`).
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

NASKAH = (("intro_text", "Teks pembuka"), ("closing_note", "Teks penutup"), ("footer_text", "Teks footer"))
POLA = re.compile(r"\d(?:[ .\-]?\d){7,}")


def temuan_baris(row: dict) -> list:
    """[(label naskah, potongan angka)] untuk satu baris `pdf_templates`."""
    cfg = row.get("config") or {}
    out = []
    for kunci, label in NASKAH:
        for m in POLA.finditer(str(cfg.get(kunci) or "")):
            out.append((label, m.group(0)))
    return out


async def jalankan(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Lapor calon nomor rekening ketikan di naskah templat cetak (PM-T2).")
    ap.add_argument("--pt", default="", help="batasi ke satu PT (entity_id); 'all' = lapisan semua PT")
    args = ap.parse_args(argv)
    from db import db
    saring = {"$or": [{f"config.{k}": {"$regex": POLA.pattern}} for k, _ in NASKAH]}
    if args.pt:
        saring["entity_id"] = args.pt
    n = 0
    async for row in db.pdf_templates.find(saring, {"_id": 0, "doc_type": 1, "entity_id": 1, "config": 1}):
        hasil = temuan_baris(row)
        if not hasil:
            continue
        n += 1
        lapisan = row.get("entity_id") or "all"
        print(f"{row.get('doc_type')} · lapisan {lapisan}:")
        for label, angka in hasil:
            print(f"  {label}: {angka}")
    print(f"Mode lapor: {n} templat berisi calon nomor rekening ketikan, tidak ada yang diubah. Bersihkan lewat "
          "Pengaturan › Dokumen & Cetak › Template Dokumen (keputusan pemilik).")
    return 0


def main(argv=None) -> int:
    return asyncio.run(jalankan(argv))


if __name__ == "__main__":
    sys.exit(main())
