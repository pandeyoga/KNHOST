"""PM-T1 — pengisian awal field baru rekening kas/bank LAMA (atas nama, peruntukan, cara bayar, bawaan, tampil di dokumen).

    python scripts/blueprint/pmt1_isi_rekening.py              # lapor saja (bawaan): tidak menulis apa pun
    python scripts/blueprint/pmt1_isi_rekening.py --terapkan   # isi field yang belum ada (data nyata = titik henti H3)
    python scripts/blueprint/pmt1_isi_rekening.py --pt ent_ksc # hanya satu PT

Nilai awal = spesifikasi `docs/blueprint/unit/PM-T1.md` (sama dengan nilai yang BERLAKU bila field belum ada,
`bank_service.bidang_efektif`): empat peruntukan; cara bayar rekening bank `transfer, giro, qris`, kas `cash`; bawaan
penerimaan `["transfer"]` / `["cash"]` HANYA untuk rekening aktif satu-satunya di PT untuk jenisnya (selain itu `[]`);
atas nama kosong; tidak tampil di dokumen. Hanya field yang belum ada yang diisi (aman diulang; putaran kedua 0
perubahan). Rekening yang sudah pernah disimpan lewat layar sesudah PM-T1 tidak tersentuh.

Aplikasi tetap benar TANPA skrip ini: field yang belum ada dibaca dengan nilai yang sama, dan setiap simpan rekening
mengisi field rekening PT itu lebih dulu. Skrip ini hanya membuat nilainya tersimpan (mis. sebelum laporan langsung ke
database). Dijalankan di dalam container backend seperti skrip lain (butuh `backend/.env`).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


async def jalankan(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Pengisian awal field rekening PM-T1 (lapor bawaan).")
    ap.add_argument("--terapkan", action="store_true", help="tulis field yang belum ada (data nyata = H3)")
    ap.add_argument("--pt", default="", help="batasi ke satu PT (entity_id)")
    args = ap.parse_args(argv)
    from services.bank_service import isi_awal_bidang_rekening
    hasil = await isi_awal_bidang_rekening(tulis=args.terapkan, entity_id=args.pt)
    per_pt: dict = {}
    for r in hasil["rincian"]:
        per_pt.setdefault(r["entity_id"] or "(tanpa PT)", []).append(r)
    for pt, rows in sorted(per_pt.items()):
        print(f"{pt}: {len(rows)} rekening perlu diisi")
        for r in rows:
            isi = ", ".join(f"{k}={v}" for k, v in r["isi"].items())
            print(f"  {r['name'] or r['account_id']}: {isi}")
    if not args.terapkan:
        print(f"Mode lapor: {hasil['diperiksa']} rekening perlu diisi, tidak ada yang diubah. "
              "Pakai --terapkan untuk menulis (data nyata = keputusan pemilik).")
    else:
        print(f"Selesai: {hasil['diubah']} rekening diisi.")
    return 0


def main(argv=None) -> int:
    return asyncio.run(jalankan(argv))


if __name__ == "__main__":
    sys.exit(main())
