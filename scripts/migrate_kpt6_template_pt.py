#!/usr/bin/env python3
"""KP-T6 — beri `entity_id: "all"` pada baris `pdf_templates` lama (lapisan semua PT).

    python scripts/migrate_kpt6_template_pt.py              # bawaan (= --dry-run): hanya lapor, tidak menulis
    python scripts/migrate_kpt6_template_pt.py --dry-run
    python scripts/migrate_kpt6_template_pt.py --apply      # tulis `entity_id: "all"` + ganti indeks unik lama

Dijalankan di dalam container backend seperti skrip lain (butuh `backend/.env`). Menjalankan skrip ini di DATA NYATA
(termasuk mode lapor) = titik henti H3: keputusan pemilik.

Yang dikerjakan (docs/blueprint/unit/KP-T6.md, bagian Data):

1. `--apply` mengisi `entity_id: "all"` pada baris `pdf_templates` yang belum punya `entity_id` (atau kosong/null).
   Hasil cetak tidak berubah: sejak KP-T6 baris tanpa `entity_id` sudah dibaca sebagai lapisan semua PT.
2. Melaporkan jenis dokumen yang punya LEBIH DARI SATU baris lapisan semua PT (data kembar). Baris kembar TIDAK diubah
   dan tidak digabung (titik henti H6) — indeks unik (`doc_type`, `entity_id`) tidak bisa dibuat sebelum dibereskan.
3. Indeks unik lama pada `doc_type` saja (bila ada di basis data; `backend/indexes.py` tidak pernah membuatnya)
   dilaporkan; `--apply` menghapusnya supaya lapisan PT bisa disimpan. Indeks baru `uq_doctype_entity` dipasang saat
   aplikasi menyala (`indexes.REQUIRED_UNIQUE_INDEXES`).
4. Tidak menyentuh `config`, `version`, maupun `document_branding` (teks kop lama diselesaikan pemilik lewat layar).

Jalan kedua `--apply` tanpa perubahan. Argumen tidak dikenal/bertentangan → keluar 2 sebelum menyentuh basis data.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

TANPA_PT = {"$or": [{"entity_id": {"$exists": False}}, {"entity_id": None}, {"entity_id": ""}]}


def _indeks_lama(info: Dict[str, Any]) -> List[str]:
    """Nama indeks unik yang kuncinya HANYA `doc_type`."""
    return sorted(n for n, i in (info or {}).items()
                  if i.get("unique") and [k for k, _ in i.get("key", [])] == ["doc_type"])


async def rencana() -> Dict[str, Any]:
    """Isi laporan tanpa menulis apa pun."""
    from db import db
    rows = await db.pdf_templates.find({}, {"_id": 0, "doc_type": 1, "entity_id": 1}).to_list(None)
    tanpa = [r for r in rows if r.get("entity_id") in (None, "")]
    grup: Dict[str, int] = {}
    for r in rows:
        if r.get("entity_id") in (None, "", "all"):
            grup[r.get("doc_type") or ""] = grup.get(r.get("doc_type") or "", 0) + 1
    try:
        info = await db.pdf_templates.index_information()
    except Exception:  # noqa: BLE001 — koleksi belum ada
        info = {}
    return {"jumlah_baris": len(rows), "tanpa_entity_id": len(tanpa),
            "jenis_tanpa_entity_id": sorted({r.get("doc_type") or "" for r in tanpa}),
            "kembar": sorted(dt for dt, n in grup.items() if n > 1), "indeks_lama": _indeks_lama(info)}


async def jalankan(tulis: bool = False) -> Dict[str, Any]:
    from db import db
    hasil = await rencana()
    ditulis, dihapus = 0, []
    if tulis:
        # baris kembar tidak disentuh (H6): hanya jenis dokumen dengan tepat satu baris lapisan semua PT
        saring = {"$and": [TANPA_PT, {"doc_type": {"$nin": hasil["kembar"]}}]}
        res = await db.pdf_templates.update_many(saring, {"$set": {"entity_id": "all"}})
        ditulis = res.modified_count
        for nama in hasil["indeks_lama"]:
            await db.pdf_templates.drop_index(nama)
            dihapus.append(nama)
    hasil.update(mode="tulis" if tulis else "lapor", ditulis=ditulis, indeks_dihapus=dihapus)
    return hasil


def _cetak(hasil: Dict[str, Any], tulis: Optional[Callable[[str], None]] = None) -> None:
    out = tulis or print
    out(f"== KP-T6 lapisan template PT — mode {hasil['mode']} ({hasil['jumlah_baris']} baris pdf_templates) ==")
    catatan = "" if hasil["mode"] == "tulis" else " (belum ditulis — mode lapor)"
    out(f"Baris tanpa entity_id → \"all\": {hasil['tanpa_entity_id']}{catatan}")
    for dt in hasil["jenis_tanpa_entity_id"]:
        out(f"  - {dt}")
    out(f"Jenis dokumen dengan baris semua PT kembar: {len(hasil['kembar'])} (tidak diubah — H6, bereskan dulu)")
    for dt in hasil["kembar"]:
        out(f"  - {dt}")
    out(f"Indeks unik lama pada doc_type saja: {', '.join(hasil['indeks_lama']) or '-'}")
    if hasil["mode"] == "tulis":
        out(f"Ditulis: {hasil['ditulis']} · indeks dihapus: {', '.join(hasil['indeks_dihapus']) or '-'}")
    else:
        out("(mode lapor; jalankan dengan --apply untuk menulis)")


def main(argv: List[str]) -> int:
    if any(a in ("-h", "--help") for a in argv):
        print(__doc__)
        return 0
    asing = [a for a in argv if a not in ("--apply", "--dry-run")]
    if asing or {"--apply", "--dry-run"} <= set(argv):
        print(f"Argumen tidak dikenal atau bertentangan: {' '.join(argv)} "
              "(tanpa argumen / --dry-run untuk lapor, --apply untuk menulis)")
        return 2
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
    _cetak(asyncio.run(jalankan(tulis="--apply" in argv)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
