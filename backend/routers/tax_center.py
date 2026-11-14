"""EPIC 7 — Pusat Pajak (PPN + PPh) router.

Read-mostly, ENTITY-AWARE. Permission modul `accounting` (admin+manager; sales DITOLAK).
- GET  /api/tax/summary           → rekap PPN (SPT Masa) + PPh (configurable) per periode/entitas
- GET  /api/tax/pph-records       → daftar rekaman PPh manual
- POST /api/tax/pph-records       → rekam DPP PPh manual (butir basis=manual)
- DELETE /api/tax/pph-records/{id}→ hapus rekaman
- GET  /api/tax/periods           → daftar masa + keadaan dilaporkan (PK-40)
- POST /api/tax/periods/{p}/lock  → tandai masa sudah dilaporkan (PK-40)
- POST /api/tax/periods/{p}/unlock→ buka lagi masa pajak, wajib alasan (PK-40)

Config pajak (tarif PPN, butir PPh) dikelola lewat GET/PUT /api/settings (config_service).
PKP/non-PKP mengikuti business_entities.default_tax_mode (via config_service).
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request

from dependencies import require_permission, audit
from entity_scope import entity_ctx, guard_doc, resolve_scope_ids, resolve_write_entity
from schemas_finance import PphRecordInput, TaxPeriodLockInput, TaxPeriodUnlockInput
from services import tax_center_service as svc

router = APIRouter(prefix="/api")


@router.get("/tax/summary")
async def get_tax_summary(request: Request, period: str = None,
                          entity_id: str = None) -> Dict[str, Any]:
    """Rekap Pusat Pajak: PPN (keluaran−masukan) + PPh (butir configurable)."""
    await require_permission(request, "accounting", "view")
    ids = resolve_scope_ids(await entity_ctx(request), entity_id)   # PK-09 E25 — kueri di luar penugasan → 403
    if len(ids) == 1:
        return await svc.tax_summary(ids[0], period)
    return await svc.tax_summary("all", period, entity_ids=ids)


@router.get("/tax/pph-records")
async def list_pph_records(request: Request, period: str = None,
                           code: str = None, entity_id: str = None) -> List[Dict[str, Any]]:
    await require_permission(request, "accounting", "view")
    ids = resolve_scope_ids(await entity_ctx(request), entity_id)   # PK-09 E26
    return await svc.list_pph_records("", period, code, entity_ids=ids)


@router.post("/tax/pph-records")
async def create_pph_record(payload: PphRecordInput, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "accounting", "manage")
    eid = resolve_write_entity(await entity_ctx(request), payload.entity_id)   # PK-09 E27
    try:
        doc = await svc.record_pph(
            entity_id=eid, period=payload.period, code=payload.code,
            name=payload.name, rate=payload.rate, dpp=payload.dpp, note=payload.note,
            actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await audit(actor["name"], "pph_record_created", "tax_pph_records", doc["id"], doc)
    return doc


@router.delete("/tax/pph-records/{record_id}")
async def delete_pph_record(record_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "accounting", "manage")
    from db import db
    await guard_doc(request, "tax_pph_records", await db.tax_pph_records.find_one({"id": record_id}, {"_id": 0}),
                    not_found="Rekaman PPh tidak ditemukan")   # PK-09 E28
    ok = await svc.delete_pph_record(record_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Rekaman PPh tidak ditemukan")
    await audit(actor["name"], "pph_record_deleted", "tax_pph_records", record_id, {})
    return {"deleted": True, "id": record_id}


# ── PK-40 (SL-13) — masa pajak dilaporkan / terkunci ─────────────────────────
@router.get("/tax/periods")
async def list_tax_periods(request: Request, entity_id: str = None) -> List[Dict[str, Any]]:
    """Daftar masa pajak (pemilih masa Pusat Pajak) + `locked`, `reported_at`, `reported_by`."""
    await require_permission(request, "accounting", "view")
    ids = resolve_scope_ids(await entity_ctx(request), entity_id)
    return await svc.list_period_locks(ids)


@router.post("/tax/periods/{period}/lock")
async def lock_tax_period(period: str, payload: TaxPeriodLockInput, request: Request) -> Dict[str, Any]:
    """Tandai masa pajak satu PT sudah dilaporkan: faktur & rekaman PPh masa itu tidak bisa diubah lagi."""
    actor = await require_permission(request, "accounting", "manage")
    eid = resolve_write_entity(await entity_ctx(request), payload.entity_id)
    doc = await svc.lock_period(eid, period, payload.note, actor)
    await audit(actor["name"], "tax_period_locked", "tax_period_locks", doc["id"],
                {"entity_id": eid, "period": doc["period"], "snapshot": doc.get("snapshot"), "note": doc.get("note")},
                scope_entity_id=eid)
    return doc


@router.post("/tax/periods/{period}/unlock")
async def unlock_tax_period(period: str, payload: TaxPeriodUnlockInput, request: Request) -> Dict[str, Any]:
    """Buka lagi masa pajak yang sudah ditandai dilaporkan (wajib alasan)."""
    actor = await require_permission(request, "accounting", "manage")
    eid = resolve_write_entity(await entity_ctx(request), payload.entity_id)
    doc = await svc.unlock_period(eid, period, payload.reason, actor)
    await audit(actor["name"], "tax_period_reopened", "tax_period_locks", doc["id"],
                {"entity_id": eid, "period": doc["period"]}, reason=doc.get("reopen_reason", ""),
                scope_entity_id=eid)
    return doc
