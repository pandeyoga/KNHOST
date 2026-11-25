"""Lapor Bayar CBD & DP — tahan bayar pesanan (kerangka LB-T1; isi tahan dilengkapi Tugas 2)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional


async def due_at(entity_id: Optional[str], start: Optional[datetime] = None) -> datetime:
    """Kapan tahan bayar pesanan di PT `entity_id` jatuh tempo: `start` (bawaan sekarang) + `sales.batas_bayar_hari`
    (per PT, bawaan 3 hari). Satu-satunya pembaca pengaturan itu — layar tidak menghitung sendiri."""
    from services.nilai_pengaturan import nilai
    hari = int(await nilai("sales.batas_bayar_hari", entity_id))
    return (start or datetime.now(timezone.utc)) + timedelta(days=hari)
