"""FINANCE — Tutup Buku (Period Closing) router.

Akses: permission module "accounting". Close butuh action "manage"; reopen
admin-only. Respons OBJEK/ARRAY telanjang (kontrak KN3). Per-entitas (F0-E).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core_utils import now_iso
from db import db
from dependencies import has_permission, require_permission, audit
from entity_scope import entity_ctx
from services import closing_service as cs

router = APIRouter(prefix="/api")


class CloseRequest(BaseModel):
    period_type: str            # "month" | "year"
    period_key: str             # "YYYY-MM" atau "YYYY"
    entity_id: Optional[str] = None
    note: Optional[str] = ""
    # K-15 — alasan admin menembus blokir Suspense ≠ 0 (≥ 5 huruf; tercatat di record & audit).
    suspense_override_reason: Optional[str] = ""


async def _resolve_entity(request: Request, entity_id: Optional[str]) -> str:
    """Tentukan entitas KONKRET untuk operasi closing (tolak mode 'all')."""
    ctx = await entity_ctx(request)
    target = entity_id or ctx.active_entity_id
    if not target or target == "all":
        raise HTTPException(status_code=400,
                            detail="Pilih entitas (PT) spesifik untuk tutup buku.")
    if target not in ctx.allowed_entity_ids:
        raise HTTPException(status_code=403, detail="Tidak memiliki akses ke entitas ini.")
    return target


@router.get("/finance/closing")
async def list_closings(request: Request, entity_id: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """Daftar periode yang pernah ditutup (per entitas)."""
    await require_permission(request, "accounting", "view")
    eid = await _resolve_entity(request, entity_id)
    return await cs.list_closings(eid)


@router.get("/finance/closing/preview")
async def preview_closing(
    request: Request,
    period_type: str = Query(..., description="month | year"),
    period_key: str = Query(..., description="YYYY-MM atau YYYY"),
    entity_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Pratinjau jurnal penutup & laba/rugi periode sebelum benar-benar ditutup."""
    await require_permission(request, "accounting", "view")
    eid = await _resolve_entity(request, entity_id)
    return await cs.preview(period_type, period_key, eid)


@router.get("/finance/closing/status")
async def closing_status(
    request: Request,
    date: str = Query(..., description="Tanggal (YYYY-MM-DD)"),
    entity_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Cek apakah tanggal berada dalam periode tertutup (untuk peringatan soft)."""
    await require_permission(request, "accounting", "view")
    eid = await _resolve_entity(request, entity_id)
    return await cs.status_for_date(date, eid)


@router.post("/finance/closing/close")
async def close_period(payload: CloseRequest, request: Request) -> Dict[str, Any]:
    """Tutup buku periode: buat jurnal penutup otomatis + tandai tertutup."""
    actor = await require_permission(request, "accounting", "manage")
    eid = await _resolve_entity(request, payload.entity_id)
    # K-15 — menembus blokir Suspense = izin yang sama dengan Reopen (`accounting.reopen`, PR-T2; dulu nama peran admin).
    is_admin = await has_permission(actor, "accounting", "reopen")
    try:
        rec = await cs.close_period(payload.period_type, payload.period_key, actor, eid, payload.note or "",
                                    suspense_override_reason=payload.suspense_override_reason or "",
                                    can_override_suspense=is_admin)
    except cs.SuspenseNotZero as e:
        raise HTTPException(status_code=409, detail=str(e))
    except cs.SuspenseOverrideForbidden as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    details = {"period": rec["period_key"], "type": rec["period_type"], "net_income": rec["net_income"]}
    ovr = rec.get("suspense_override")
    if ovr:
        details.update({"suspense_override_reason": ovr.get("reason"),
                        "suspense_balance": ovr.get("suspense_balance")})
    await audit(actor["name"], "period_closed", "period_closing", rec["id"], details)
    if ovr:
        # Jejak terpisah supaya tembus blokir mudah dicari di Jejak Audit (bukan hanya rincian "period_closed").
        await audit(actor["name"], "period_close_suspense_override", "period_closing", rec["id"],
                    {"period": rec["period_key"], "reason": ovr.get("reason"),
                     "suspense_balance": ovr.get("suspense_balance")}, reason=ovr.get("reason") or "")
    return rec


@router.post("/finance/closing/{closing_id}/reopen")
async def reopen_period(closing_id: str, request: Request) -> Any:
    """Buka kembali periode (izin `accounting.reopen`, bawaan admin): void jurnal penutup + status reopened.

    KF-T6 (GL-06) — bila `kontrol.buka_kembali_tutup_buku.min_orang` PT itu = 2: panggilan pertama hanya MENCATAT
    pengajuan (`reopen_request`) dan menjawab 202; pengaju yang sama → 403; orang lain yang berwenang → dijalankan."""
    actor = await require_permission(request, "accounting", "manage")
    if not await has_permission(actor, "accounting", "reopen"):   # PR-T2 — dulu nama peran admin
        raise HTTPException(status_code=403, detail=(
            "Anda belum punya akses untuk membuka kembali periode. Minta Admin menambahkan akses 'Akuntansi & Tutup Buku'."))
    pending = await _reopen_dua_orang(closing_id, actor)
    if pending is not None:
        return pending
    try:
        rec = await cs.reopen_period(closing_id, actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if rec is None:
        raise HTTPException(status_code=404, detail="Data penutupan tidak ditemukan.")
    if rec.get("reopen_request"):   # KF-T6 — pengajuan selesai dijalankan orang kedua
        await db.period_closings.update_one({"id": closing_id}, {"$unset": {"reopen_request": ""}})
        rec.pop("reopen_request", None)
    await audit(actor["name"], "period_reopened", "period_closing", closing_id,
                {"period": rec.get("period_key")})
    return rec


async def _reopen_dua_orang(closing_id: str, actor: Dict[str, Any]) -> Optional[JSONResponse]:
    """KF-T6 — langkah "ajukan lalu dijalankan orang kedua" untuk buka kembali tutup buku.

    `None` = lanjut membuka kembali sekarang. Pengecualian Admin tidak berlaku di sini (`kecualikan_admin=False`):
    titik ini memang hanya untuk Admin, jadi pengecualian itu akan membuat aturan dua orang tidak pernah berlaku."""
    from services import dual_control as _dc
    rec = await db.period_closings.find_one({"id": closing_id}, {"_id": 0})
    if not rec or rec.get("status") != "closed":
        return None   # status lain → penolakan baku layanan (400/404)
    if not await _dc.butuh_orang_kedua("buka_kembali_tutup_buku", rec.get("entity_id", "")):
        return None
    req = rec.get("reopen_request") or {}
    if not req.get("by_id"):
        req = {"by_id": actor.get("id", ""), "by": actor.get("name", ""), "at": now_iso()}
        await db.period_closings.update_one({"id": closing_id, "status": "closed"},
                                            {"$set": {"reopen_request": req, "updated_at": now_iso()}})
        await audit(actor["name"], "period_reopen_requested", "period_closing", closing_id,
                    {"period": rec.get("period_key")})
        return JSONResponse(status_code=202, content={"status": "menunggu_orang_kedua", "requested_by": req["by"]})
    await _dc.tolak_bila_pelaku_sama("buka_kembali_tutup_buku", {**rec, "number": rec.get("period_label", "")},
                                     actor, rec.get("entity_id", ""), pengaju=[req.get("by_id")],
                                     kecualikan_admin=False)
    return None


@router.post("/finance/closing/{closing_id}/reclose")
async def reclose_period(closing_id: str, request: Request) -> Dict[str, Any]:
    """F-9b — Tutup Ulang periode STALE: hitung ulang jurnal penutup (residual) setelah
    ada posting/void backdate ke periode tertutup."""
    actor = await require_permission(request, "accounting", "manage")
    try:
        rec = await cs.reclose_period(closing_id, actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if rec is None:
        raise HTTPException(status_code=404, detail="Data penutupan tidak ditemukan.")
    await audit(actor["name"], "period_reclosed", "period_closing", closing_id,
                {"period": rec.get("period_key"), "net_income": rec.get("net_income")})
    return rec
