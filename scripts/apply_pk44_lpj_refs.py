#!/usr/bin/env python3
"""PK-44 (IA-10) — tautkan Pertanggungjawaban Dana (LPJ) lama ke Pengajuan Dana (PD)-nya di Jejak Dokumen.

Unit PK-44 mendaftarkan LPJ (`cash_advance_settlements`) sebagai jenis dokumen `cash_settlement` yang WAJIB berinduk
PD (`cash_advance_id`). LPJ baru ditaut saat lahir (`cash_advance_service.create_settlement`). LPJ yang sudah ada
belum punya relasi tersimpan (`refs[]`), sehingga di Jejak Dokumen LPJ tampak tanpa asal dan invarian INV-REF-01
(`scripts/verify_data_integrity.py`) melaporkannya sebagai dokumen turunan tanpa induk. Skrip ini menautkannya
(dua arah, idempotent — `doc_refs_service.link`), atas keputusan pemilik (H3).

    python scripts/apply_pk44_lpj_refs.py            # baca saja (bawaan): LPJ yang akan ditaut + yang tidak bisa
    python scripts/apply_pk44_lpj_refs.py --apply    # tautkan + jejak audit `doc_refs_pk44_lpj`

Di kontainer backend (repo = /app): `python /app/scripts/apply_pk44_lpj_refs.py`.

Aturan:
  * hanya LPJ ber-`cash_advance_id` yang PD-nya ADA yang ditaut (relasi `parent`, catatan `doc_refs_service.LPJ_NOTE`);
  * LPJ yang PD-nya tidak ada (terhapus/salah id) TIDAK diubah — dilaporkan untuk diperiksa manusia;
  * menjalankan ulang aman: LPJ yang sudah bertaut dilewati (`_push_ref` tidak menggandakan).
"""
import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

AKSI_AUDIT = "doc_refs_pk44_lpj"
PELAKU = "Sistem (relasi dokumen PK-44)"


async def rencana(db) -> Dict[str, Any]:
    """LPJ yang akan ditaut, yang sudah bertaut, dan yang PD-nya tidak ada. Tidak menulis apa pun."""
    taut: List[Dict[str, Any]] = []
    sudah: List[Dict[str, Any]] = []
    yatim: List[Dict[str, Any]] = []
    tanpa_pd: List[Dict[str, Any]] = []
    async for row in db.cash_advance_settlements.find(
            {}, {"_id": 0, "id": 1, "number": 1, "entity_id": 1, "cash_advance_id": 1, "refs": 1}):
        item = {"id": row["id"], "number": row.get("number") or row["id"], "entity_id": row.get("entity_id", ""),
                "cash_advance_id": row.get("cash_advance_id") or ""}
        if not item["cash_advance_id"]:
            tanpa_pd.append(item)
            continue
        if any(r.get("doc_type") == "cash_advance" and r.get("doc_id") == item["cash_advance_id"]
               for r in row.get("refs") or []):
            sudah.append(item)
            continue
        pd = await db.cash_advances.find_one({"id": item["cash_advance_id"]}, {"_id": 0, "number": 1})
        if not pd:
            yatim.append(item)
            continue
        taut.append({**item, "pd_number": pd.get("number") or item["cash_advance_id"]})
    return {"taut": taut, "sudah": sudah, "yatim": yatim, "tanpa_pd": tanpa_pd}


async def terapkan(db) -> Dict[str, Any]:
    """Tautkan `rencana()["taut"]` (dua arah) dan catat jejak audit."""
    from dependencies import audit
    from services import doc_refs_service as refs

    plan = await rencana(db)
    ditaut: List[Dict[str, Any]] = []
    for x in plan["taut"]:
        res = await refs.link(("cash_settlement", x["id"]), ("cash_advance", x["cash_advance_id"]), "parent",
                              note=refs.LPJ_NOTE, force=True)
        if res.get("linked"):
            ditaut.append(x)
    if ditaut:
        await audit(PELAKU, AKSI_AUDIT, "cash_advance_settlements", "refs",
                    {"ditaut": [{"lpj": x["number"], "pd": x["pd_number"]} for x in ditaut]},
                    reason="PK-44 — LPJ lama ditautkan ke PD-nya (Jejak Dokumen, INV-REF-01)",
                    source="scripts/apply_pk44_lpj_refs.py")
    return {**plan, "ditaut": ditaut, "pesan": f"{len(ditaut)} LPJ ditautkan ke PD-nya."}


def tulis(plan: Dict[str, Any], apply: bool) -> str:
    baris = [f"PK-44 — relasi LPJ → PD di Jejak Dokumen ({'TERAPKAN' if apply else 'laporan, baca saja'})"]
    isi = plan.get("ditaut") if apply else plan["taut"]
    baris.append(f"{'LPJ yang ditautkan' if apply else 'LPJ yang akan ditautkan'}: {len(isi or [])}")
    for x in isi or []:
        baris.append(f"  {x['number']:<24} → {x['pd_number']:<24} ({x['entity_id'] or '—'})")
    baris.append(f"Sudah bertaut (dilewati): {len(plan['sudah'])}")
    baris.append(f"PD tidak ditemukan (tidak diubah; periksa manual): {len(plan['yatim'])}")
    for x in plan["yatim"]:
        baris.append(f"  {x['number']:<24} cash_advance_id={x['cash_advance_id']}")
    baris.append(f"Tanpa PD (tidak diubah): {len(plan['tanpa_pd'])}")
    if not apply:
        baris.append("(mode laporan; jalankan --apply untuk menautkan — keputusan pemilik)")
    elif plan.get("pesan"):
        baris.append(plan["pesan"])
    return "\n".join(baris)


async def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="tautkan LPJ ke PD-nya (tanpa ini: laporan baca saja)")
    args = ap.parse_args(argv)
    from db import db

    plan = await (terapkan(db) if args.apply else rencana(db))
    print(tulis(plan, args.apply))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
