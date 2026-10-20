#!/usr/bin/env python3
"""
repair_f09_superseded_rejections.py — F-09 (uji pra-UAT 2026-10-21).

SO terbuka yang terkunci sebelum perbaikan F-09: entri persetujuan harga khusus/kredit
DITOLAK, lalu sudah diajukan ulang (dan mungkin sudah disetujui), tetapi entri lama tetap
`rejected` sehingga `POST /sales-orders/{id}/approve` selalu 409 APPROVAL_REJECTED
(contoh data acuan lokal: KSC/SO-00039, KSC/SO-00083).

Skrip menandai entri ditolak yang SUDAH diikuti pengajuan berkunci sama (harga khusus:
tipe + produk; kredit: tipe) sebagai `superseded` (superseded_by = entri berikutnya,
keputusan lama tetap tersimpan). Penolakan tanpa pengajuan ulang TIDAK disentuh.
SO tidak dinaikkan otomatis — Manajer tetap menekan Setujui.

Bawaan: hanya laporan (dry-run). Idempoten.

Jalankan (di container backend):
  cd /app/backend && python scripts/repair_f09_superseded_rejections.py          # laporan
  cd /app/backend && python scripts/repair_f09_superseded_rejections.py --apply  # tulis
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def _run(apply: bool) -> int:
    from services.so_approvals import backfill_resubmitted_rejections
    from db import db

    res = await backfill_resubmitted_rejections(db, apply=apply)
    for o in res["orders"]:
        sisa = f" — masih {o['still_rejected']} ditolak tanpa pengajuan ulang" if o["still_rejected"] else ""
        print(f"   {o['number']}: {o['superseded']} entri ditolak → superseded{sisa}")
    mode = "DITULIS" if apply else "dry-run (tambahkan --apply untuk menulis)"
    print(f"✅ {len(res['orders'])} SO terdampak — {mode}.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_run("--apply" in sys.argv[1:])))
