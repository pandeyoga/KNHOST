"""Kas & Bank bagian 4 (C8) — penanda per PT: uang muka pemasok memakai akunnya sendiri.

Rancangan: `docs/superpowers/specs/2026-11-28-kas-bank-4-uang-muka-design.md` §5.3–§5.4 dan §7.9.6.

* Penanda di `system_settings{scope: "__uang_muka_pemasok_per_pt__"}`: kunci = id PT, nilai = `{"sejak": <ISO>, "oleh":
  <nama>}`. Ditulis SEKALI (`nyalakan`) — oleh persetujuan pindah saldo uang muka pemasok PT itu (Tugas 3, jurnal reklas
  Dr akun pemasok / Cr 1-1400 lebih dulu); tidak ada migrasi saat aplikasi menyala dan tidak ada jalan mematikannya.
* Pemakai: `gl_service.akun_uang_muka_pemasok` (satu pembantu akun uang muka pemasok jurnal). Selama PT belum aktif semua
  jalur uang muka pemasoknya membukukan 1-1400 persis seperti sebelumnya; sesudahnya akun pemetaan PT
  `hutang.uang_muka_pemasok` (bawaan 1-1410). Satu saat pindah per PT → tidak ada uang muka yang dibuat di satu akun lalu
  dipakai di akun lain.

Penyimpanan, tulis-sekali, dan penggabungan penanda kembar: satu pembantu `services/penanda_per_pt.py` (sama dengan
`cash_account_mode`, Kas & Bank 1); modul ini hanya memberi scope-nya.
"""
from typing import Any, Optional

from services import penanda_per_pt as _penanda

SCOPE = "__uang_muka_pemasok_per_pt__"


async def aktif_sejak(entity_id: Optional[str]) -> str:
    """Waktu PT `entity_id` mulai memakai akun uang muka pemasok sendiri (ISO), kosong bila belum."""
    return await _penanda.aktif_sejak(SCOPE, entity_id)


async def aktif(entity_id: Optional[str]) -> bool:
    """Apakah jurnal uang muka pemasok PT `entity_id` memakai akun pemetaan `hutang.uang_muka_pemasok`."""
    return await _penanda.aktif(SCOPE, entity_id)


async def nyalakan(entity_id: str, oleh: Any) -> str:
    """Nyalakan akun uang muka pemasok sendiri untuk PT `entity_id` — SEKALI. → `aktif_sejak` PT itu. Panggilan berikutnya
    tidak menulis dan tidak menggeser waktu & pelakunya (`penanda_per_pt.nyalakan`)."""
    return await _penanda.nyalakan(SCOPE, entity_id, oleh, "akun uang muka pemasok")
