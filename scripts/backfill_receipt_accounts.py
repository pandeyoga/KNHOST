"""PM-T3 — isi rekening kas kwitansi LAMA (tanpa `account_id`, sebelum PK-20) dan kwitansinya.

    python scripts/backfill_receipt_accounts.py               # lapor saja (bawaan, sama dengan --dry-run)
    python scripts/backfill_receipt_accounts.py --dry-run     # lapor saja: tidak menulis apa pun
    python scripts/backfill_receipt_accounts.py --terapkan    # tulis (data nyata = titik henti H3, keputusan pemilik)
    python scripts/backfill_receipt_accounts.py --pt ent_ksc  # hanya satu PT

Aturan (`docs/blueprint/unit/PM-T3.md` §Data): `account_id` diisi HANYA bila PT kas itu punya tepat satu rekening aktif
untuk jenis kasnya (`bank_service.sole_account_id`, aturan yang sama dengan saldo rekening). Kas di PT berekening ganda
TIDAK diubah dan dicantumkan di keluaran sebagai daftar kerja: sejak PM-T3 (b) kas seperti itu tidak lagi muncul sebagai
kandidat rekonsiliasi rekening mana pun, jadi pemilik memutus rekeningnya sebelum (b) dipasang ke PT nyata. Aman diulang
(syarat tulis = field masih kosong). Dijalankan di dalam container backend seperti skrip lain (butuh `backend/.env`).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


async def jalankan(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Isi rekening kas kwitansi lama (PM-T3; lapor bawaan).")
    ap.add_argument("--dry-run", action="store_true", help="lapor saja (bawaan)")
    ap.add_argument("--terapkan", action="store_true", help="tulis rekening yang bisa ditentukan (data nyata = H3)")
    ap.add_argument("--pt", default="", help="batasi ke satu PT (entity_id)")
    args = ap.parse_args(argv)
    tulis = bool(args.terapkan and not args.dry_run)
    from core_utils import rupiah
    from services.ar_receipt_service import isi_rekening_kwitansi_lama
    hasil = await isi_rekening_kwitansi_lama(tulis=tulis, entity_id=args.pt)
    print(f"Bisa diisi otomatis (PT berekening tunggal): {len(hasil['diisi'])} kas")
    for r in hasil["diisi"]:
        print(f"  {r['entity_id']} · {r['cash_number'] or r['cash_id']} ({r['receipt_number'] or r['receipt_id']}) "
              f"{rupiah(r['amount'])} → {r['account_name'] or r['account_id']}")
    print(f"Perlu diputus orang: {len(hasil['diputus_orang'])} kas")
    for r in hasil["diputus_orang"]:
        print(f"  {r['entity_id']} · {r['cash_number'] or r['cash_id']} ({r['receipt_number'] or r['receipt_id']}) "
              f"{rupiah(r['amount'])} · {r['alasan']}")
    if tulis:
        print(f"Selesai: {hasil['diubah']} kas diisi rekeningnya.")
    else:
        print("Mode lapor: tidak ada yang diubah. Pakai --terapkan untuk menulis (data nyata = keputusan pemilik).")
    return 0


def main(argv=None) -> int:
    return asyncio.run(jalankan(argv))


if __name__ == "__main__":
    sys.exit(main())
