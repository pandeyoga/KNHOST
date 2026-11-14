"""PK-37 (GL-05) — jurnal LAMA yang `date`-nya stempel waktu dan jatuh di bulan yang salah.

    python scripts/blueprint/pk37_tanggal_buku_lama.py              # baca-saja (bawaan): daftar, tidak menulis apa pun
    python scripts/blueprint/pk37_tanggal_buku_lama.py --terapkan   # ubah `date` → tanggal buku WIB (data nyata = H3)

Sebelum PK-37 tanggal jurnal disimpan apa adanya: sebagian `YYYY-MM-DD`, sebagian stempel ISO UTC. Laporan memotong 10
huruf pertama, sehingga transaksi pukul 00.00–06.59 WIB jatuh ke tanggal (dan pada tanggal 1, bulan) sebelumnya.
Jurnal baru sejak PK-37 selalu bertanggal buku WIB 10 huruf (`services/book_date.py:tanggal_buku`).

Mode baca-saja mencetak jurnal yang `date`-nya lebih dari 10 huruf **dan** tanggal WIB-nya berbeda dari 10 huruf
pertamanya, dikelompokkan per PT dan bulan asal → bulan seharusnya, dengan jumlah dan total debit. Jurnal yang tanggal
asal atau tanggal seharusnya berada di periode tertutup PT itu ditandai.

`--terapkan` mengubah `date` menjadi tanggal WIB dan menyimpan nilai lama di `date_asli` (bersyarat nilai lama, aman
diulang). Jurnal yang ditandai periode tertutup DILEWATI. Menjalankannya pada data nyata = titik henti H3 (keputusan
pemilik). Dijalankan di dalam container backend seperti skrip lain (butuh `backend/.env`). Keluar 0.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


def _rp(x: float) -> str:
    return f"Rp {x:,.0f}".replace(",", ".")


async def _periode_tertutup(db) -> Dict[str, List[Tuple[str, str]]]:
    out: Dict[str, List[Tuple[str, str]]] = {}
    async for c in db.period_closings.find({"status": "closed"}, {"_id": 0, "entity_id": 1, "start_date": 1,
                                                                  "end_date": 1}):
        out.setdefault(c.get("entity_id") or "", []).append((c.get("start_date") or "", c.get("end_date") or ""))
    return out


def _tertutup(tertutup: Dict[str, List[Tuple[str, str]]], eid: str, d: str) -> bool:
    return any(a <= d <= b for a, b in tertutup.get(eid, []))


async def kumpulkan(db) -> List[Dict[str, Any]]:
    """Jurnal yang tanggal bukunya berubah bila dihitung ulang dengan `tanggal_buku` (baca-saja)."""
    from services.book_date import tanggal_buku
    tertutup = await _periode_tertutup(db)
    rows: List[Dict[str, Any]] = []
    async for je in db.journal_entries.find({"date": {"$type": "string"}},
                                            {"_id": 0, "id": 1, "number": 1, "entity_id": 1, "date": 1,
                                             "total_debit": 1, "status": 1}):
        lama = je.get("date") or ""
        if len(lama) <= 10:
            continue
        try:
            baru = tanggal_buku(lama)
        except ValueError:
            continue   # bentuk tak dikenal: tidak disentuh skrip ini
        if baru == lama[:10]:
            continue
        eid = je.get("entity_id") or ""
        rows.append({"id": je["id"], "number": je.get("number", ""), "entity_id": eid, "date": lama, "baru": baru,
                     "bulan_asal": lama[:7], "bulan_seharusnya": baru[:7], "debit": float(je.get("total_debit") or 0),
                     "status": je.get("status", ""),
                     "periode_tertutup": _tertutup(tertutup, eid, lama[:10]) or _tertutup(tertutup, eid, baru)})
    rows.sort(key=lambda r: (r["entity_id"], r["bulan_asal"], r["bulan_seharusnya"], r["date"]))
    return rows


def kelompokkan(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grup: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for r in rows:
        k = (r["entity_id"], r["bulan_asal"], r["bulan_seharusnya"])
        g = grup.setdefault(k, {"entity_id": k[0], "bulan_asal": k[1], "bulan_seharusnya": k[2], "jumlah": 0,
                                "debit": 0.0, "tertutup": 0})
        g["jumlah"] += 1
        g["debit"] = round(g["debit"] + r["debit"], 2)
        g["tertutup"] += int(bool(r["periode_tertutup"]))
    return list(grup.values())


async def terapkan(db, rows: List[Dict[str, Any]]) -> Tuple[int, int]:
    """Ubah `date` → tanggal buku WIB; nilai lama ke `date_asli`. Periode tertutup dilewati. (diubah, dilewati)"""
    diubah = dilewati = 0
    for r in rows:
        if r["periode_tertutup"]:
            dilewati += 1
            continue
        res = await db.journal_entries.update_one({"id": r["id"], "date": r["date"]},
                                                  {"$set": {"date": r["baru"], "date_asli": r["date"]}})
        diubah += int(res.modified_count)
    return diubah, dilewati


async def jalankan(argv=None, db=None) -> int:
    ap = argparse.ArgumentParser(description="Jurnal lama bertanggal stempel UTC di bulan yang salah (PK-37).")
    ap.add_argument("--terapkan", action="store_true",
                    help="ubah date → tanggal buku WIB (simpan date_asli); periode tertutup dilewati. Data nyata = H3")
    args = ap.parse_args(argv)
    if db is None:
        from db import db as _db
        db = _db
    rows = await kumpulkan(db)
    grup = kelompokkan(rows)
    print(f"Jurnal bertanggal stempel waktu yang tanggal buku WIB-nya berbeda: {len(rows)}")
    for g in grup:
        tanda = f" · {g['tertutup']} di periode tertutup (tidak diubah)" if g["tertutup"] else ""
        print(f"  {g['entity_id'] or '(tanpa PT)'} · {g['bulan_asal']} → {g['bulan_seharusnya']} · "
              f"{g['jumlah']} jurnal · debit {_rp(g['debit'])}{tanda}")
    for r in rows:
        tanda = " [periode tertutup]" if r["periode_tertutup"] else ""
        print(f"    {r['number'] or r['id']}: {r['date']} → {r['baru']}{tanda}")
    if not args.terapkan:
        print("Mode baca-saja: tidak ada yang diubah. Pakai --terapkan untuk mengubah (data nyata = keputusan pemilik).")
        return 0
    diubah, dilewati = await terapkan(db, rows)
    print(f"Selesai: {diubah} jurnal diubah, {dilewati} dilewati (periode tertutup).")
    return 0


def main(argv=None) -> int:
    return asyncio.run(jalankan(argv))


if __name__ == "__main__":
    sys.exit(main())
