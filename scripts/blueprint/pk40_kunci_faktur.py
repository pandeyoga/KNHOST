"""PK-40 (SL-13) — isi field kunci `active_key` / `nsfp_key` faktur pajak LAMA, dan laporkan pasangan kembar.

    python scripts/blueprint/pk40_kunci_faktur.py              # baca-saja (bawaan): laporan, tidak menulis apa pun
    python scripts/blueprint/pk40_kunci_faktur.py --terapkan   # isi/cabut field kunci (data nyata = titik henti H3)

Sejak PK-40 keunikan faktur dijamin indeks unik parsial (`backend/indexes.py`, `REQUIRED_UNIQUE_INDEXES`):
  * `tax_invoices.uq_fkt_active` (`active_key` = `so:{order_id}` / `ic:{interco_pair_id}`, hanya faktur AKTIF: bukan
    `batal` dan belum diganti) dan `tax_invoices.uq_fkt_nsfp` (`nsfp_key` = digit NSFP faktur aktif);
  * `tax_invoices_in.uq_fpm_active` (`vb:{vendor_bill_id}` / `ic:{interco_pair_id}`, status `recorded`) dan
    `tax_invoices_in.uq_fpm_nsfp` (`nsfp_key` = `nsfp_digits`).
Faktur yang lahir sebelum PK-40 belum punya field itu, jadi indeksnya belum melindungi mereka.

Mode baca-saja mencetak, per koleksi: jumlah faktur yang field kuncinya perlu diisi/dicabut, dan setiap KELOMPOK
KEMBAR (dua faktur aktif atau lebih untuk kunci yang sama) beserta nomor fakturnya. Kelompok kembar = titik henti H6:
menggabung atau membatalkan faktur bukan wewenang skrip ini; serahkan daftarnya kepada pemilik data.

`--terapkan` menolak berjalan bila ada kelompok kembar (tidak ada yang diubah). Tanpa kembar: tiap faktur diberi field
kunci menurut keadaannya, dan field kunci pada faktur yang tidak aktif dicabut (aman diulang). Menjalankannya pada data
nyata = titik henti H3 (keputusan pemilik). Dijalankan di dalam container backend seperti skrip lain (butuh
`backend/.env`). Keluar 0 bila tanpa kembar, 1 bila ada kembar.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

KOLEKSI = ("tax_invoices", "tax_invoices_in")
FIELDS = ("active_key", "nsfp_key")


def kunci_seharusnya(koleksi: str, doc: Dict[str, Any]) -> Dict[str, str]:
    """Field kunci menurut keadaan faktur — fungsi yang SAMA dengan yang dipakai layanan saat menulis."""
    from services.input_tax_service import kunci_aktif_masukan
    from services.tax_invoice_service import kunci_aktif_keluaran
    return kunci_aktif_keluaran(doc) if koleksi == "tax_invoices" else kunci_aktif_masukan(doc)


async def kumpulkan(db) -> Dict[str, Dict[str, Any]]:
    """Per koleksi: daftar perubahan (id, $set, $unset) dan kelompok kembar per field kunci (baca-saja)."""
    hasil: Dict[str, Dict[str, Any]] = {}
    for koleksi in KOLEKSI:
        ubah: List[Dict[str, Any]] = []
        grup: Dict[Tuple[str, str], List[str]] = {}
        async for d in db[koleksi].find({}, {"_id": 0, "id": 1, "number": 1, "status": 1, "replaced_by_id": 1,
                                             "order_id": 1, "interco_pair_id": 1, "vendor_bill_id": 1, "nsfp": 1,
                                             "nsfp_digits": 1, "active_key": 1, "nsfp_key": 1,
                                             # TX-T2 — kosakata kunci sj:/retur: butuh asal & sumber dokumen
                                             "doc_kind": 1, "trigger": 1, "shipment_no": 1, "credit_note_id": 1}):
            k = kunci_seharusnya(koleksi, d)
            for f, v in k.items():
                grup.setdefault((f, v), []).append(d.get("number") or d.get("id"))
            setel = {f: v for f, v in k.items() if d.get(f) != v}
            cabut = [f for f in FIELDS if f not in k and f in d]
            if setel or cabut:
                ubah.append({"id": d["id"], "number": d.get("number", ""), "set": setel, "unset": cabut})
        kembar = [{"field": f, "kunci": v, "nomor": sorted(n)} for (f, v), n in sorted(grup.items()) if len(n) > 1]
        hasil[koleksi] = {"ubah": ubah, "kembar": kembar}
    return hasil


async def terapkan(db, hasil: Dict[str, Dict[str, Any]]) -> int:
    diubah = 0
    for koleksi, h in hasil.items():
        for u in h["ubah"]:
            ops: Dict[str, Any] = {}
            if u["set"]:
                ops["$set"] = u["set"]
            if u["unset"]:
                ops["$unset"] = {f: "" for f in u["unset"]}
            res = await db[koleksi].update_one({"id": u["id"]}, ops)
            diubah += int(res.modified_count)
    return diubah


async def jalankan(argv=None, db=None) -> int:
    ap = argparse.ArgumentParser(description="Field kunci faktur pajak lama + laporan kembar (PK-40).")
    ap.add_argument("--terapkan", action="store_true",
                    help="isi/cabut active_key & nsfp_key; ditolak bila ada kembar (H6). Data nyata = H3")
    args = ap.parse_args(argv)
    if db is None:
        from db import db as _db
        db = _db
    hasil = await kumpulkan(db)
    ada_kembar = False
    for koleksi, h in hasil.items():
        print(f"{koleksi}: {len(h['ubah'])} faktur perlu diisi/dicabut field kuncinya · "
              f"{len(h['kembar'])} kelompok kembar")
        for k in h["kembar"]:
            ada_kembar = True
            print(f"  KEMBAR {k['field']}={k['kunci']}: {', '.join(k['nomor'])}")
    if ada_kembar:
        print("Ada faktur aktif kembar (titik henti H6): serahkan daftar di atas kepada pemilik data. "
              "Tidak ada yang diubah.")
        return 1
    if not args.terapkan:
        print("Mode baca-saja: tidak ada yang diubah. Pakai --terapkan untuk mengisi (data nyata = keputusan pemilik).")
        return 0
    print(f"Selesai: {await terapkan(db, hasil)} faktur diubah.")
    return 0


def main(argv=None) -> int:
    return asyncio.run(jalankan(argv))


if __name__ == "__main__":
    sys.exit(main())
