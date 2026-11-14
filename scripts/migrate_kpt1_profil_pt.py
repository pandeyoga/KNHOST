#!/usr/bin/env python3
"""KP-T1 — rapikan profil PT: isi persen kepemilikan, laporkan isian lama yang berbeda dari mesin.

    python scripts/migrate_kpt1_profil_pt.py              # bawaan (= --dry-run): hanya lapor, tidak menulis
    python scripts/migrate_kpt1_profil_pt.py --dry-run
    python scripts/migrate_kpt1_profil_pt.py --apply      # isi `ownership_pct: 100` pada PT yang belum punya

Dijalankan di dalam container backend seperti skrip lain (butuh `backend/.env`). Menjalankan skrip ini di DATA NYATA
(termasuk mode lapor) = titik henti H3: keputusan pemilik.

Yang dikerjakan (docs/blueprint/unit/KP-T1.md, bagian Data › Migrasi):

1. `--apply` mengisi `ownership_pct: 100` (K-10) pada PT yang belum punya. Satu-satunya tulisan skrip ini.
2. TIDAK menyalin `fiscal_year_start` maupun `currency` ke registry: mesin hari ini sudah membaca registry
   (`finance.fiscal_year_end_month`, `finance.base_currency`), jadi menyalin akan mengubah perilaku. Skrip hanya
   MELAPORKAN PT yang isinya berbeda: bulan akhir tersirat dari `fiscal_year_start` (`MM` − 1; `01` → 12) ≠ nilai efektif
   `finance.fiscal_year_end_month` PT itu, atau `currency` ≠ nilai efektif `finance.base_currency`. Isian
   `fiscal_year_start` yang tidak terbaca (mis. "13-45", dulu lolos validasi) dilaporkan terpisah.
3. Melaporkan PT yang NPWP-nya terisi tetapi bukan 15 atau 16 digit (setelah titik, strip, dan spasi dibuang).
4. Field lama di dokumen PT tidak dihapus (`00_ATURAN_EKSEKUSI.md` §7 butir 2); sejak KP-T1 hanya tidak lagi dibaca,
   ditulis, atau dikirim.

Jalan kedua `--apply` tanpa perubahan. Argumen tidak dikenal/bertentangan → keluar 2 sebelum menyentuh basis data.
"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

KEPEMILIKAN_BAWAAN = 100.0


def bulan_akhir_tersirat(fiscal_year_start: Any) -> Optional[int]:
    """"MM-DD" → bulan akhir tahun buku (`MM` − 1; `01` → 12). None bila tidak terbaca (bulan bukan 1–12)."""
    m = re.fullmatch(r"\s*(\d{1,2})-(\d{1,2})\s*", str(fiscal_year_start or ""))
    if not m or not 1 <= int(m.group(1)) <= 12:
        return None
    awal = int(m.group(1))
    return 12 if awal == 1 else awal - 1


async def rencana() -> Dict[str, Any]:
    """Isi laporan tanpa menulis apa pun."""
    from db import db
    from services import config_resolver
    from services.entity_lifecycle_service import npwp_valid

    rows = await db.business_entities.find(
        {}, {"_id": 0, "id": 1, "legal_name": 1, "short_name": 1, "ownership_pct": 1, "fiscal_year_start": 1,
             "currency": 1, "npwp": 1}).sort("id", 1).to_list(None)
    isi, beda_tb, tak_terbaca, beda_mu, npwp_salah = [], [], [], [], []
    for e in rows:
        eid = e["id"]
        nama = e.get("legal_name") or e.get("short_name") or eid
        if "ownership_pct" not in e:
            isi.append(eid)
        if e.get("fiscal_year_start"):
            tersirat = bulan_akhir_tersirat(e["fiscal_year_start"])
            efektif = int(await config_resolver.value_of("finance.fiscal_year_end_month", {"entity_id": eid}) or 12)
            if tersirat is None:
                tak_terbaca.append({"entity_id": eid, "nama": nama, "fiscal_year_start": e["fiscal_year_start"],
                                    "bulan_registry": efektif})
            elif tersirat != efektif:
                beda_tb.append({"entity_id": eid, "nama": nama, "fiscal_year_start": e["fiscal_year_start"],
                                "bulan_tersirat": tersirat, "bulan_registry": efektif})
        if e.get("currency"):
            efektif_mu = str(await config_resolver.value_of("finance.base_currency", {"entity_id": eid}) or "")
            if str(e["currency"]).strip().upper() != efektif_mu.upper():
                beda_mu.append({"entity_id": eid, "nama": nama, "currency": e["currency"], "base_currency": efektif_mu})
        if str(e.get("npwp") or "").strip() and not npwp_valid(e.get("npwp")):
            npwp_salah.append({"entity_id": eid, "nama": nama, "npwp": e["npwp"]})
    return {"jumlah_pt": len(rows), "isi_kepemilikan": isi, "tahun_buku_beda": beda_tb,
            "tahun_buku_tak_terbaca": tak_terbaca, "mata_uang_beda": beda_mu, "npwp_salah": npwp_salah}


async def jalankan(tulis: bool = False) -> Dict[str, Any]:
    from db import db
    from core_utils import now_iso

    hasil = await rencana()
    ditulis = 0
    if tulis:
        for eid in hasil["isi_kepemilikan"]:
            res = await db.business_entities.update_one(
                {"id": eid, "ownership_pct": {"$exists": False}},
                {"$set": {"ownership_pct": KEPEMILIKAN_BAWAAN, "updated_at": now_iso()}})
            ditulis += res.modified_count
    hasil.update(mode="tulis" if tulis else "lapor", ditulis=ditulis)
    return hasil


def _cetak(hasil: Dict[str, Any], tulis: Optional[Callable[[str], None]] = None) -> None:
    out = tulis or print
    out(f"== KP-T1 profil PT — mode {hasil['mode']} ({hasil['jumlah_pt']} PT) ==")
    catatan = "" if hasil["mode"] == "tulis" else " (belum ditulis — mode lapor)"
    out(f"Persen kepemilikan diisi 100: {len(hasil['isi_kepemilikan'])} PT{catatan}")
    for eid in hasil["isi_kepemilikan"]:
        out(f"  - {eid}")
    out(f"Tahun buku master ≠ registry: {len(hasil['tahun_buku_beda'])} PT (tidak diubah; mesin memakai registry)")
    for t in hasil["tahun_buku_beda"]:
        out(f"  - {t['entity_id']} ({t['nama']}): awal {t['fiscal_year_start']} → akhir bulan {t['bulan_tersirat']}, "
            f"registry bulan {t['bulan_registry']}")
    out(f"Tahun buku master tidak terbaca: {len(hasil['tahun_buku_tak_terbaca'])} PT")
    for t in hasil["tahun_buku_tak_terbaca"]:
        out(f"  - {t['entity_id']} ({t['nama']}): '{t['fiscal_year_start']}', registry bulan {t['bulan_registry']}")
    out(f"Mata uang master ≠ registry: {len(hasil['mata_uang_beda'])} PT (tidak diubah; mesin memakai registry)")
    for m in hasil["mata_uang_beda"]:
        out(f"  - {m['entity_id']} ({m['nama']}): master {m['currency']}, registry {m['base_currency']}")
    out(f"NPWP bukan 15/16 digit: {len(hasil['npwp_salah'])} PT (perbaiki lewat layar detail PT)")
    for n in hasil["npwp_salah"]:
        out(f"  - {n['entity_id']} ({n['nama']}): '{n['npwp']}'")
    if hasil["mode"] == "tulis":
        out(f"Ditulis: {hasil['ditulis']}")
    else:
        out("(mode lapor; jalankan dengan --apply untuk mengisi persen kepemilikan)")


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
