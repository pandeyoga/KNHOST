"""KF-T7 — pembaca SATU nilai pengaturan untuk mesin; galat baca = bawaan registry (`02_STANDAR.md` §2.2, KF-06).

Dipakai pemakai kunci yang dulu konstanta di kode (`config_catalog_nilai.py`): hari telat yang memblokir pelanggan,
masa reservasi, batas salah sandi, umur sesi, dan lain-lain. Pemakai tetap MENYEBUT kuncinya sendiri di badan
fungsinya (pemeriksa kesehatan Pengaturan, `services/config_health.py`, mencocokkan nama kunci di fungsi pemakai).

    hari = int(await nilai("ar.overdue_block_days", entity_id))
"""
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def nilai(key: str, entity_id: Optional[str] = "") -> Any:
    """Nilai efektif kunci `key` untuk PT `entity_id` (""/"all" = aturan grup). Kosong atau galat → bawaan registry."""
    from config_registry import default_of
    from services.config_resolver import value_of
    ent = "" if entity_id in (None, "", "all") else str(entity_id)
    try:
        val = await value_of(key, {"entity_id": ent})
    except Exception as exc:  # noqa: BLE001 — mesin tidak boleh berhenti karena pengaturan gagal dibaca
        logger.warning("[KF-T7] pengaturan %s gagal dibaca (%s) — memakai bawaan registry", key, exc)
        return default_of(key)
    return default_of(key) if val is None else val
