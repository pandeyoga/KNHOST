"""PK-32 (FX-15, K-14) — nota debit amandemen LAMA yang berhenti di `awaiting_billing_rule` ditagihkan lewat mesin nota.

    python scripts/migrasi_pk32_nota_debit_menunggu.py           # baca-saja (bawaan): cetak, tidak menulis apa pun
    python scripts/migrasi_pk32_nota_debit_menunggu.py --apply   # tagihkan lewat `credit_note_service`

Sebelum PK-32, amandemen yang MENAIKKAN nilai pesanan yang sudah terbit menerbitkan nota debit tanpa jurnal dan tanpa
tagihan (`billing_status="awaiting_billing_rule"`, `open_amount` = nilai yang belum ditutup nota kredit). Sejak PK-32
nota debit langsung menjadi baris tagihan tambahan pesanan (`sales_orders.extra_billing_lines[]`) dan bagian yang
barangnya sudah terkirim dijurnal (`amendment_debit_note`: Dr 1-1200 / Cr 4-1000 / Cr 2-1200).

Mode baca-saja mencetak nomor nota, pesanan, PT, dan `open_amount`. `--apply` memanggil
`credit_note_service.bill_legacy_debit_note` per nota: `open_amount` menjadi tagihan tambahan (jatuh tempo = tanggal
migrasi + hari termin pesanan), jurnal bagian yang terkirim lewat `post_durable`, status `posted`, `billing_status`
`billed`. Aman diulang: jalan berikutnya tidak menemukan sasaran. Menjalankannya pada data nyata = titik henti H3
(keputusan pemilik; ambil cadangan `credit_notes` dan `sales_orders` lebih dulu). Dijalankan di dalam container backend
(butuh `backend/.env`).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

AKTOR = {"id": "sistem", "name": "sistem (migrasi PK-32)"}


def angka(x: float) -> str:
    """Rupiah tanpa awalan, pemisah ribuan titik: 100.000 · 0."""
    v = round(float(x or 0))
    return f"{v:,.0f}".replace(",", ".") if v else "0"


async def kumpulkan(db) -> List[Dict[str, Any]]:
    return await db.credit_notes.find({"kind": "debit_note", "billing_status": "awaiting_billing_rule"},
                                      {"_id": 0}).sort([("created_at", 1), ("id", 1)]).to_list(5000)


async def jalankan(argv=None, db=None) -> int:
    ap = argparse.ArgumentParser(description="Nota debit amandemen lama yang menunggu aturan tagih → tagihan (PK-32).")
    ap.add_argument("--apply", action="store_true", help="tagihkan lewat mesin nota (data nyata = H3)")
    args = ap.parse_args(argv)
    if db is None:
        from db import db as _db
        db = _db
    notes = await kumpulkan(db)
    for n in notes:
        print(f"Nota debit {n.get('number') or n['id']} · pesanan {n.get('order_number') or n.get('order_id')} · "
              f"PT {n.get('entity_id') or '—'} · open_amount {angka(n.get('open_amount', n.get('gross_amount')))}")
    total = sum(float(n.get("open_amount", n.get("gross_amount")) or 0) for n in notes)
    print(f"Ringkasan: {len(notes)} nota debit menunggu ditagih · total {angka(total)}")
    if not args.apply:
        print("Mode baca-saja: tidak ada yang diubah. Pakai --apply untuk menagihkan (data nyata = keputusan pemilik).")
        return 0
    if not notes:
        print("Tanpa perubahan: tidak ada nota debit yang menunggu ditagih.")
        return 0
    from services import credit_note_service as cns
    gagal = 0
    for n in notes:
        hasil = await cns.bill_legacy_debit_note(n["id"], AKTOR)
        jurnal = hasil.get("gl_status") or "—"
        print(f"  {n.get('number') or n['id']}: status {hasil.get('status')} · tagihan {hasil.get('billing_status')} · "
              f"jurnal {jurnal}")
        if jurnal == "failed":
            gagal += 1
    print(f"Diterapkan: {len(notes)} nota debit ditagihkan"
          + (f"; {gagal} jurnal gagal — ulang dari Keuangan › Posting Gagal." if gagal else "."))
    return 0


def main(argv=None) -> int:
    return asyncio.run(jalankan(argv))


if __name__ == "__main__":
    sys.exit(main())
