"""PK-27 (IV-02) — migrasi roll scrap retur LAMA: biaya roll yang sudah dihapus-buku dinolkan.

    python scripts/migrasi_pk27_biaya_roll_scrap.py           # baca-saja (bawaan): cetak, tidak menulis apa pun
    python scripts/migrasi_pk27_biaya_roll_scrap.py --apply   # simpan biaya lama, nolkan biaya, catat riwayat biaya

Sebelum PK-27, pelepasan karantina retur dengan aksi "scrap" menerbitkan jurnal hapus-buku (Dr 5-9500 / Cr 1-1300)
tetapi roll tetap berstatus `damaged` dengan panjang dan biaya utuh. Status `damaged` ikut dinilai rekonsiliasi
persediaan, jadi nilai roll lebih besar dari saldo 1-1300 sebesar hapus-buku itu. Sejak PK-27 scrap menolkan biaya
roll (`return_service.release_quarantine`) dan batal scrap memulihkannya dari `writeoff_unit_cost`.

Sasaran: roll `damaged` ber-`writeoff_je_id` yang belum dibalik (`writeoff_reversed` bukan benar) dan masih bernilai
(`length_remaining × (unit_cost | base_unit_cost)` > 0). Mode baca-saja mencetak nomor roll, PT, dan nilainya.
`--apply` menulis `writeoff_unit_cost`/`writeoff_base_unit_cost` (biaya sebelum dinolkan, dipakai batal scrap), menyetel
`unit_cost = base_unit_cost = 0`, dan mencatat riwayat biaya alasan `scrap_writeoff`. Aman diulang: jalan kedua tidak
menemukan sasaran. Tidak ada jurnal: hapus-bukunya sudah terbit. Menjalankannya pada data nyata = titik henti H3
(keputusan pemilik; ambil cadangan `inventory_rolls` lebih dulu). Dijalankan di dalam container backend (butuh
`backend/.env`).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

SASARAN: Dict[str, Any] = {"status": "damaged", "writeoff_je_id": {"$nin": [None, ""]},
                           "writeoff_reversed": {"$ne": True}}


def angka(x: float) -> str:
    """Rupiah tanpa awalan, pemisah ribuan titik: 960.000 · 0."""
    v = round(float(x or 0))
    return f"{v:,.0f}".replace(",", ".") if v else "0"


async def kumpulkan(db) -> List[Dict[str, Any]]:
    from services.roll_service import roll_value_cents
    out: List[Dict[str, Any]] = []
    async for r in db.inventory_rolls.find(SASARAN, {"_id": 0}).sort([("roll_no", 1), ("id", 1)]):
        sen = roll_value_cents(r)
        if sen > 0:
            out.append({**r, "_nilai": sen / 100})
    return out


async def terapkan(db, rolls: List[Dict[str, Any]]) -> int:
    from core_utils import now_iso
    from services.roll_cost_history import COLLECTION, build_entry
    n = 0
    for r in rolls:
        res = await db.inventory_rolls.update_one({**SASARAN, "id": r["id"], "writeoff_unit_cost": {"$exists": False}}, {
            "$set": {"writeoff_unit_cost": float(r.get("unit_cost") or 0),
                     "writeoff_base_unit_cost": float(r.get("base_unit_cost") or 0),
                     "unit_cost": 0.0, "base_unit_cost": 0.0, "updated_at": now_iso()}})
        if not res.modified_count:
            continue
        n += 1
        entry = build_entry(r, 0.0, "scrap_writeoff", actor="sistem (migrasi PK-27)", ref_type="sales_return",
                            ref_id=r.get("return_id", ""), note=f"jurnal hapus-buku {r.get('writeoff_je_number') or ''}".strip())
        if entry:
            await db[COLLECTION].insert_one(dict(entry))
    return n


async def jalankan(argv=None, db=None) -> int:
    ap = argparse.ArgumentParser(description="Roll scrap retur lama: nolkan biaya yang sudah dihapus-buku (PK-27).")
    ap.add_argument("--apply", action="store_true",
                    help="simpan biaya lama, nolkan biaya roll, catat riwayat biaya (data nyata = H3)")
    args = ap.parse_args(argv)
    if db is None:
        from db import db as _db
        db = _db
    rolls = await kumpulkan(db)
    for r in rolls:
        print(f"Roll {r.get('roll_no') or r['id']} · PT {r.get('owner_entity_id') or '—'} · "
              f"{r.get('length_remaining')} {r.get('unit') or ''} × {angka(r.get('unit_cost') or r.get('base_unit_cost'))}"
              f" · nilai {angka(r['_nilai'])} · jurnal hapus-buku {r.get('writeoff_je_number') or r.get('writeoff_je_id')}")
    total = sum(r["_nilai"] for r in rolls)
    print(f"Ringkasan: {len(rolls)} roll scrap masih bernilai · total {angka(total)}")
    if not args.apply:
        print("Mode baca-saja: tidak ada yang diubah. Pakai --apply untuk menerapkan (data nyata = keputusan pemilik).")
        return 0
    n = await terapkan(db, rolls)
    if not n:
        print("Tanpa perubahan: tidak ada roll scrap yang masih bernilai.")
        return 0
    print(f"Diterapkan: {n} roll dinolkan biayanya (biaya lama disimpan di writeoff_unit_cost).")
    return 0


def main(argv=None) -> int:
    return asyncio.run(jalankan(argv))


if __name__ == "__main__":
    sys.exit(main())
