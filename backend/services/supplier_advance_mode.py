"""Kas & Bank bagian 4 (C8) — penanda per PT: uang muka pemasok memakai akunnya sendiri.

Rancangan: `docs/superpowers/specs/2026-11-28-kas-bank-4-uang-muka-design.md` §5.3–§5.4 dan §7.9.6.

* Penanda di `system_settings{scope: "__uang_muka_pemasok_per_pt__"}`: kunci = id PT, nilai = `{"sejak": <ISO>, "oleh":
  <nama>}`. Ditulis SEKALI (`nyalakan`) — oleh persetujuan pindah saldo uang muka pemasok PT itu (Tugas 3, jurnal reklas
  Dr akun pemasok / Cr 1-1400 lebih dulu); tidak ada migrasi saat aplikasi menyala dan tidak ada jalan mematikannya.
* Pemakai: `gl_service.akun_uang_muka_pemasok` (satu pembantu akun uang muka pemasok jurnal). Selama PT belum aktif semua
  jalur uang muka pemasoknya membukukan 1-1400 persis seperti sebelumnya; sesudahnya akun pemetaan PT
  `hutang.uang_muka_pemasok` (bawaan 1-1410). Satu saat pindah per PT → tidak ada uang muka yang dibuat di satu akun lalu
  dipakai di akun lain.

Pola `cash_account_mode` (mode akun per rekening Kas & Bank 1). Batas: tidak ada indeks unik; dua `nyalakan` pertama yang
bersamaan bisa menulis dokumen penanda kembar — `aktif_sejak` menggabungkannya (yang paling awal berlaku).
"""
import re
from typing import Any, Optional

from core_utils import now_iso
from db import db

SCOPE = "__uang_muka_pemasok_per_pt__"
_KUNCI_SAH = re.compile(r"^[A-Za-z0-9_\-]+$")


def _kunci_sah(entity_id: Any) -> str:
    eid = str(entity_id or "").strip()
    return eid if eid and _KUNCI_SAH.match(eid) else ""


async def aktif_sejak(entity_id: Optional[str]) -> str:
    """Waktu PT `entity_id` mulai memakai akun uang muka pemasok sendiri (ISO), kosong bila belum."""
    eid = _kunci_sah(entity_id)
    if not eid:
        return ""
    sejak = [d[eid]["sejak"] async for d in db.system_settings.find({"scope": SCOPE}, {"_id": 0, eid: 1})
             if isinstance(d.get(eid), dict) and d[eid].get("sejak")]
    return min(sejak) if sejak else ""


async def aktif(entity_id: Optional[str]) -> bool:
    """Apakah jurnal uang muka pemasok PT `entity_id` memakai akun pemetaan `hutang.uang_muka_pemasok`."""
    return bool(await aktif_sejak(entity_id))


async def nyalakan(entity_id: str, oleh: Any) -> str:
    """Nyalakan akun uang muka pemasok sendiri untuk PT `entity_id` — SEKALI. → `aktif_sejak` PT itu. Panggilan berikutnya
    tidak menimpa waktu & pelakunya. Dibaca dulu, lalu ditulis bersyarat kuncinya belum ada (pola
    `cash_account_mode.nyalakan`)."""
    eid = _kunci_sah(entity_id)
    if not eid:
        raise ValueError(f"Id PT tidak sah untuk penanda akun uang muka pemasok: {entity_id!r}.")
    sejak = await aktif_sejak(eid)
    if sejak:
        return sejak
    nama = (oleh.get("name") if isinstance(oleh, dict) else oleh) or "system"
    nilai = {"sejak": now_iso(), "oleh": str(nama)}
    syarat = {"scope": SCOPE, eid: {"$exists": False}}
    if await db.system_settings.find_one({"scope": SCOPE}, {"_id": 0, "scope": 1}) is None:
        await db.system_settings.update_one(syarat, {"$set": {eid: nilai}}, upsert=True)
    else:   # tanpa upsert: dokumen penanda tetap satu
        await db.system_settings.update_one(syarat, {"$set": {eid: nilai}})
    return await aktif_sejak(eid)
