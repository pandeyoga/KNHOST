#!/usr/bin/env python3
"""KP-T7 — buang sisa `interval_hours` yang tersimpan pada job penjadwal bersatuan menit.

    python scripts/migrate_kpt7_jadwal.py              # bawaan (= --dry-run): hanya lapor, tidak menulis
    python scripts/migrate_kpt7_jadwal.py --dry-run
    python scripts/migrate_kpt7_jadwal.py --apply      # buang field `interval_hours` pada job bersatuan menit

Dijalankan di dalam container backend seperti skrip lain (butuh `backend/.env`). Menjalankan skrip ini di DATA NYATA
(termasuk mode lapor) = titik henti H3: keputusan pemilik.

Latar (docs/blueprint/unit/KP-T7.md, bagian Data): sebelum KP-T7 layar Penjadwal mengirim `interval_hours` untuk SEMUA
job berselang, termasuk job yang bawaannya `interval_minutes`. Pemicu selalu memakai `interval_minutes` lebih dulu, jadi
nilai jam itu tersimpan di `system_settings{scope:"alerts"}.jobs.<id>.interval_hours` tetapi TIDAK PERNAH dipakai.
Sejak KP-T7 job bersatuan menit menolak `interval_hours`; skrip ini membuang sisa lama tersebut. Jadwal yang berjalan
tidak berubah (nilai yang dibuang memang tidak pernah dibaca pemicu).

Yang dikerjakan:
1. Lapor: tiap job bersatuan menit yang menyimpan `interval_hours` (id, label, jam tersimpan, selang menit yang dipakai).
2. `--apply`: `$unset jobs.<id>.interval_hours` untuk job tersebut — satu-satunya tulisan skrip ini.
3. Job tak dikenal / bersatuan jam / harian tidak disentuh.

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

SCOPE = "alerts"


async def rencana() -> Dict[str, Any]:
    """Isi laporan tanpa menulis apa pun."""
    from db import db
    from services import scheduler_service as sched

    doc = await db.system_settings.find_one({"scope": SCOPE}, {"_id": 0, "jobs": 1}) or {}
    saved = doc.get("jobs") or {}
    sisa: List[Dict[str, Any]] = []
    for jid in sorted(saved):
        job = sched.JOB_MAP.get(jid)
        cfg = saved.get(jid) or {}
        if not job or sched.interval_unit(job) != "menit" or "interval_hours" not in cfg:
            continue
        efektif = {**sched.job_defaults(job), **cfg}
        sisa.append({"job_id": jid, "label": job["label"], "interval_hours": cfg.get("interval_hours"),
                     "interval_minutes_dipakai": sched.interval_value(job, efektif)})
    return {"jumlah_job_tersimpan": len(saved), "sisa_interval_hours": sisa}


async def jalankan(tulis: bool = False) -> Dict[str, Any]:
    from db import db

    hasil = await rencana()
    ditulis = 0
    if tulis and hasil["sisa_interval_hours"]:
        unset = {f"jobs.{s['job_id']}.interval_hours": "" for s in hasil["sisa_interval_hours"]}
        res = await db.system_settings.update_one({"scope": SCOPE}, {"$unset": unset})
        ditulis = len(unset) if res.modified_count else 0
    hasil.update(mode="tulis" if tulis else "lapor", ditulis=ditulis)
    return hasil


def _cetak(hasil: Dict[str, Any], tulis: Optional[Callable[[str], None]] = None) -> None:
    out = tulis or print
    out(f"== KP-T7 jadwal penjadwal — mode {hasil['mode']} ({hasil['jumlah_job_tersimpan']} job tersimpan) ==")
    catatan = "" if hasil["mode"] == "tulis" else " (belum dibuang — mode lapor)"
    out(f"Job bersatuan menit yang menyimpan selang jam (tidak pernah dipakai): "
        f"{len(hasil['sisa_interval_hours'])}{catatan}")
    for s in hasil["sisa_interval_hours"]:
        out(f"  - {s['job_id']} ({s['label']}): tersimpan {s['interval_hours']} jam; pemicu memakai "
            f"{s['interval_minutes_dipakai']} menit (tidak berubah)")
    if hasil["mode"] == "tulis":
        out(f"Dibuang: {hasil['ditulis']}")
    else:
        out("(mode lapor; jalankan dengan --apply untuk membuang sisa selang jam)")


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
