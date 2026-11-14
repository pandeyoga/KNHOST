"""KF-T6 — baca aturan kontrol "harus dua orang" per lapisan (tab Pengaturan › Persetujuan › Kontrol dua orang).

  GET /api/kontrol/aturan?entity_id=   izin `settings.view`

Menyimpan TIDAK lewat sini: layar mengirim banyak butir `kontrol.*` sekaligus ke `PUT /api/config/values` (satu
alasan), sehingga validasi nilai, wajib-alasan, lapisan PT, riwayat, dan jejak audit sama dengan Pusat Pengaturan.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Request

from dependencies import has_permission, require_permission
from entity_scope import entity_ctx, resolve_requested_entity
from services import dual_control

router = APIRouter(prefix="/api/kontrol", tags=["kontrol"])

_TOLAK_LIHAT = ("Anda belum punya akses untuk melihat aturan kontrol dua orang. Minta Admin menambahkan akses "
                "'Pengaturan, Pengguna & Hak Akses'.")


@router.get("/aturan")
async def baca_aturan(request: Request, entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    actor = await require_permission(request, "settings", "view", detail=_TOLAK_LIHAT)
    eid = (entity_id or "").strip()
    if eid and eid != "all":
        eid = resolve_requested_entity(await entity_ctx(request), eid)   # N1 — PT harus dalam penugasan
    out = await dual_control.aturan(eid)
    # Tombol simpan aktif = server memang mengizinkan `PUT /api/config/values` untuk kunci `kontrol.*`
    # (izinnya `settings.manage`; lapisan "Semua PT" hanya untuk peran lintas PT — aturan sama dengan Pusat Pengaturan).
    can_edit = await has_permission(actor, "settings", "manage")
    if can_edit and not eid:
        can_edit = (await entity_ctx(request)).is_cross_entity
    out["can_edit"] = bool(can_edit)
    return out
