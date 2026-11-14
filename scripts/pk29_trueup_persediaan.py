"""PK-29 (IV-05, IV-09, K-06) — rekonsiliasi persediaan per PT (baca-saja) dan true-up SATU PT (`--apply`).

    python scripts/pk29_trueup_persediaan.py                         # baca-saja (bawaan): semua PT
    python scripts/pk29_trueup_persediaan.py --pt ent_ksc            # baca-saja satu PT
    python scripts/pk29_trueup_persediaan.py --apply --pt ent_ksc --alasan "stok awal gudang utama"

Baca-saja mencetak per PT angka yang SAMA dengan layar Buku Besar › Rekonsiliasi Persediaan
(`gl_service.inventory_reconciliation`): nilai roll, saldo buku besar dari akun persediaan hasil pemetaan PT itu, selisih,
sinkron/tidak, dan apakah true-up boleh menurut aturan K-06 (`inventory.trueup_hanya_saldo_awal`). Ia juga mendaftar
TRUE-UP LAMA — jurnal `inventory_opening` yang terbit pada/sesudah tanggal jurnal persediaan operasional pertama PT itu:
kandidat true-up yang menutupi selisih operasional (sebelum PK-29 tombol true-up bisa dipakai kapan pun, untuk semua PT
sekaligus). Skrip ini TIDAK membalik apa pun; membalik true-up lama = perbaikan data, keputusan pemilik (H3).

`--apply` (wajib `--pt` dan `--alasan` ≥ 5 huruf): periksa periode terbuka (`preflight_posting(PT, hari ini)`) lalu
`post_inventory_opening_balance(entity_ids=[PT])` — Dr/Cr akun persediaan PT vs 3-2900 Ekuitas Saldo Awal sebesar
selisihnya, alasan menempel di jurnal. PT yang sudah bertransaksi (aturan K-06 menolak tombol layar) hanya diproses bila
`--abaikan-aturan-saldo-awal` ikut ditulis — keputusan sadar pemilik. Selisih dihitung ulang tiap jalan, jadi jalan
kedua tidak menerbitkan jurnal. Menjalankan `--apply` pada data nyata = titik henti H3 (ambil cadangan
`journal_entries` lebih dulu). Dijalankan di dalam container backend (butuh `backend/.env`).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def angka(x: float) -> str:
    """Rupiah tanpa awalan, pemisah ribuan titik, tanda minus dipertahankan: 5.000 · -5.000 · 0."""
    v = round(float(x or 0))
    return (f"{v:,.0f}".replace(",", ".")) if v else "0"


async def true_up_lama(entity_id: str, codes: List[str]) -> List[Dict[str, Any]]:
    """Jurnal `inventory_opening` PT ini yang bertanggal pada/sesudah jurnal persediaan operasional pertamanya."""
    from db import db
    from services import gl_service as gl
    if not codes:
        return []
    pertama = await db.journal_entries.find_one(
        {"entity_id": entity_id, "status": {"$ne": "void"}, "lines.account_code": {"$in": codes},
         "source_type": {"$nin": list(gl.OPENING_SOURCES) + ["reversal"]}},
        {"_id": 0, "date": 1, "number": 1}, sort=[("date", 1), ("number", 1)])
    if not pertama:
        return []
    out: List[Dict[str, Any]] = []
    async for je in db.journal_entries.find(
            {"entity_id": entity_id, "status": {"$ne": "void"}, "source_type": "inventory_opening",
             "date": {"$gte": pertama.get("date") or ""}},
            {"_id": 0, "number": 1, "date": 1, "total_debit": 1, "reason": 1}).sort([("date", 1), ("number", 1)]):
        out.append({**je, "sejak": pertama.get("number") or "", "sejak_tanggal": pertama.get("date") or ""})
    return out


async def jalankan(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Rekonsiliasi persediaan per PT; true-up satu PT dengan --apply (PK-29).")
    ap.add_argument("--pt", default="", help="id PT (mis. ent_ksc); kosong = semua PT (hanya baca-saja)")
    ap.add_argument("--apply", action="store_true", help="true-up PT --pt (data nyata = H3)")
    ap.add_argument("--alasan", default="", help="dasar true-up, minimal 5 huruf (wajib dengan --apply)")
    ap.add_argument("--abaikan-aturan-saldo-awal", action="store_true", dest="abaikan",
                    help="izinkan --apply pada PT yang sudah bertransaksi (keputusan pemilik)")
    args = ap.parse_args(argv)
    from services import gl_service as gl

    recon = await gl.inventory_reconciliation([args.pt] if args.pt else None)
    if args.pt and not recon["rows"]:
        print(f"PT {args.pt} tidak ditemukan.")
        return 2
    kandidat = 0
    for r in recon["rows"]:
        status = "sinkron" if r["reconciled"] else "TIDAK sinkron"
        boleh = "boleh true-up" if r["trueup_allowed"] else "true-up ditolak aturan saldo awal"
        print(f"{gl._pt_text(r['entity_name'])} ({r['entity_id']}) · nilai roll {angka(r['subledger_value'])} · buku besar "
              f"{angka(r['gl_balance'])} (akun {', '.join(r['inventory_accounts'])}) · selisih {angka(r['difference'])} · "
              f"{status} · {boleh}")
        for je in await true_up_lama(r["entity_id"], r["inventory_accounts"]):
            kandidat += 1
            print(f"  True-up lama {je.get('number')} {str(je.get('date') or '')[:10]} · {angka(je.get('total_debit'))} "
                  f"· sesudah jurnal persediaan operasional {je['sejak']} ({str(je['sejak_tanggal'])[:10]}) · dasar: "
                  f"{je.get('reason') or 'tidak tercatat'}")
    print(f"Ringkasan: {len(recon['rows'])} PT · {recon['rows_out_of_sync']} belum sinkron · total selisih mutlak "
          f"{angka(recon['total_abs_difference'])} · {kandidat} true-up lama sesudah transaksi")
    if not args.apply:
        print("Mode baca-saja: tidak ada yang diubah. True-up satu PT: --apply --pt <id> --alasan \"…\" "
              "(data nyata = keputusan pemilik).")
        return 0
    if not args.pt:
        print("--apply wajib menyebut satu PT (--pt).")
        return 2
    alasan = (args.alasan or "").strip()
    if len(alasan) < 5:
        print("Alasan true-up wajib diisi (minimal 5 huruf): --alasan \"…\".")
        return 2
    row = recon["rows"][0]
    if not row["trueup_allowed"] and not args.abaikan:
        print(f"Ditolak: {row['trueup_blocked_reason']} Tulis --abaikan-aturan-saldo-awal bila pemilik memutuskan "
              "true-up tetap dijalankan.")
        return 2
    try:
        await gl.preflight_posting(args.pt)
    except gl.ClosedPeriodError as exc:
        print(f"Ditolak: {exc}")
        return 2
    hasil = await gl.post_inventory_opening_balance(actor_name="skrip PK-29", reason=alasan, entity_ids=[args.pt])
    if not hasil["count"]:
        print("Tanpa perubahan: selisih PT ini sudah 0 (atau hanya pembulatan sen).")
        return 0
    for p in hasil["posted"]:
        print(f"Diterapkan: jurnal {p['journal_number']} · {angka(p['amount'])} · dasar: {p['reason']}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    return asyncio.run(jalankan(argv))


if __name__ == "__main__":
    sys.exit(main())
