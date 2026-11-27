"""F1 — kwitansi otomatis dari mutasi bank: fondasi (konstanta, waktu aktif, pembaca pengaturan).

Rancangan `docs/superpowers/specs/2026-11-27-kwitansi-otomatis-mutasi-design.md` §5.3, §5.7. Penilai baris dan pelaksana
ditambahkan di tugas berikutnya pada modul ini; uang tetap lewat `ar_receipt_service.create_receipt` (satu pintu kas).
"""
from __future__ import annotations

from typing import Optional

from core_utils import now_iso
from db import db

SUMBER = "mutasi_bank"
# Pelaku sistem: satu-satunya yang dikecualikan dari B3 (`ar_receipt_service._pagar_lapor_bayar`), dan hanya bila
# kwitansinya juga bersumber `SUMBER`.
AKTOR_MUTASI = {"id": "", "name": "Sistem (mutasi bank)", "role": "system", "sistem": SUMBER}
PENANDA_AKTIF = "f1_kwitansi_mutasi_aktif_sejak"


async def ensure_aktif_sejak() -> str:
    """Tulis waktu aktif F1 sekali saja (saat backend pertama menyala); panggilan berikutnya tidak menimpa."""
    await db.system_settings.update_one(
        {"scope": "__migrations__", PENANDA_AKTIF: {"$exists": False}},
        {"$set": {PENANDA_AKTIF: now_iso()}}, upsert=True)
    return await aktif_sejak()


async def aktif_sejak() -> str:
    """Waktu aktif F1 (ISO); kosong bila belum pernah ditulis."""
    doc = await db.system_settings.find_one({"scope": "__migrations__"}, {"_id": 0, PENANDA_AKTIF: 1}) or {}
    return doc.get(PENANDA_AKTIF) or ""


async def menyala(entity_id: Optional[str]) -> bool:
    """Apakah PT `entity_id` memakai kwitansi otomatis dari mutasi bank (`bank.kwitansi_otomatis_mutasi`)."""
    from services.nilai_pengaturan import nilai
    return bool(await nilai("bank.kwitansi_otomatis_mutasi", entity_id))
