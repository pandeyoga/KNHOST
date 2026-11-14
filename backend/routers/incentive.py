"""KM-T1 — Meja Insentif: Target & Aturan, definisi angka, pencocokan angka, bangun ulang fakta.

  GET   /api/incentive/targets?period_type&period&sales_id     incentive.view       target PT aktif (+ daftar sales)
  PUT   /api/incentive/targets                                 incentive.configure  simpan menurut kunci unik
  POST  /api/incentive/targets/copy                            incentive.configure  salin dari periode lain
  GET   /api/incentive/components                              incentive.view
  POST  /api/incentive/components                              incentive.configure  409 kode kembar
  PATCH /api/incentive/components/{id}                         incentive.configure
  GET   /api/incentive/definitions/current                     incentive.view       versi berlaku + label
  GET   /api/incentive/reconciliation?period=YYYY-MM           incentive.view       INV-KM-1 (omzet) + INV-KM-2 (pencairan)
  POST  /api/incentive/facts/rebuild                           incentive.configure  {rows_shipment, rows_collection}

PT = PT konteks pengguna (`02_STANDAR.md` §3.4 N1); mode "Semua PT" hanya baca (tulis → 409 `assert_write_entity`, N3).
Logika di `services/incentive_targets.py`, `incentive_periods.py`, `incentive_definitions.py`, `incentive_facts.py`.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from db import db
from dependencies import audit, require_permission
from entity_scope import assert_write_entity, entity_ctx, guard_doc
from schemas_incentive import (IncentiveComponentCreate, IncentiveComponentUpdate, IncentiveFactRebuild,
                               IncentiveTargetCopy, IncentiveTargetSave)
from services import incentive_definitions as idef
from services import incentive_facts as ifacts
from services import incentive_periods as ip
from services import incentive_targets as itg

router = APIRouter(prefix="/api/incentive")

MODUL = "Kinerja & Insentif"
PESAN_LIHAT = f"Anda belum punya akses untuk melihat target dan aturan insentif. Minta Admin menambahkan akses '{MODUL}'."
PESAN_ATUR = f"Anda belum punya akses untuk mengatur target dan aturan insentif. Minta Admin menambahkan akses '{MODUL}'."


def _err(exc: Exception) -> HTTPException:
    return HTTPException(status_code=getattr(exc, "status", 400), detail=str(exc))


async def _view(request: Request):
    actor = await require_permission(request, "incentive", "view", detail=PESAN_LIHAT)
    return actor, await entity_ctx(request)


async def _configure(request: Request, action: str):
    actor = await require_permission(request, "incentive", "configure", detail=PESAN_ATUR)
    ctx = await entity_ctx(request)
    return actor, assert_write_entity(ctx, action)


def _all_pt(ctx) -> bool:
    return bool(getattr(ctx, "view_all", False))


# ── Target ───────────────────────────────────────────────────────────────────────────────────────────────────────────
@router.get("/targets")
async def get_targets(request: Request, period_type: str = Query("month"), period: str = Query(""),
                      sales_id: str = Query("")) -> Dict[str, Any]:
    """Target satu jenis periode dan satu periode. Mode "Semua PT": target semua PT yang ditugaskan (hanya baca)."""
    _actor, ctx = await _view(request)
    eid = ctx.active_entity_id
    try:
        pt = str(period_type or "month").strip().lower()
        p = period or await ip.current_period(pt, eid)
        pt, p = ip.normalize(pt, p)
        start, end = await ip.period_bounds(pt, p, eid)
    except ip.PeriodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if _all_pt(ctx):
        items = []
        for e in ctx.allowed_entity_ids:
            items += await itg.list_targets(e, pt, p, sales_id)
        roster = []
    else:
        items = await itg.list_targets(eid, pt, p, sales_id)
        roster = await itg.sales_roster(eid, pt, p)
    return {"period_type": pt, "period": p, "period_label": ip.period_label(pt, p),
            "previous_period": ip.previous_period(pt, p), "bounds": {"start": start, "end": end},
            "entity_id": "" if _all_pt(ctx) else eid, "all_pt": _all_pt(ctx), "items": items, "roster": roster,
            "period_types": [{"value": k, "label": v} for k, v in ip.PERIOD_TYPE_LABEL.items()]}


@router.put("/targets")
async def put_target(payload: IncentiveTargetSave, request: Request) -> Dict[str, Any]:
    actor, eid = await _configure(request, "mengatur target")
    try:
        doc = await itg.save_target(eid, payload.model_dump(), actor)
    except itg.InsentifError as exc:
        raise _err(exc)
    await audit(actor.get("name", ""), "incentive_target_saved", "sales_target", doc.get("id", ""),
                {k: doc.get(k) for k in ("entity_id", "sales_id", "period_type", "period", "target_sales_amount",
                                         "target_collection_amount", "target_new_customers")})
    return doc


@router.post("/targets/copy")
async def copy_targets(payload: IncentiveTargetCopy, request: Request) -> Dict[str, int]:
    actor, eid = await _configure(request, "menyalin target")
    try:
        res = await itg.copy_targets(eid, payload.period_type, payload.from_period, payload.to_period, actor)
    except itg.InsentifError as exc:
        raise _err(exc)
    await audit(actor.get("name", ""), "incentive_targets_copied", "sales_target", eid,
                {**payload.model_dump(), **res})
    return res


# ── Komponen ─────────────────────────────────────────────────────────────────────────────────────────────────────────
@router.get("/components")
async def get_components(request: Request) -> Dict[str, Any]:
    _actor, ctx = await _view(request)
    ids = list(ctx.allowed_entity_ids) if _all_pt(ctx) else [ctx.active_entity_id]
    items = []
    for e in ids:
        items += [itg.component_labels(c) for c in await itg.list_components(e)]
    return {"items": items, "all_pt": _all_pt(ctx),
            "basis_options": [{"value": k, "label": v} for k, v in itg.COMPONENT_BASIS_LABEL.items()],
            "column_options": [{"value": k, "label": v} for k, v in itg.COMPONENT_COLUMN_LABEL.items()]}


@router.post("/components")
async def post_component(payload: IncentiveComponentCreate, request: Request) -> Dict[str, Any]:
    actor, eid = await _configure(request, "menambah komponen insentif")
    try:
        doc = await itg.create_component(eid, payload.model_dump(), actor)
    except itg.InsentifError as exc:
        raise _err(exc)
    await audit(actor.get("name", ""), "incentive_component_created", "incentive_component", doc["id"],
                {k: doc.get(k) for k in ("entity_id", "code", "name", "basis_period_type", "columns")})
    return itg.component_labels(doc)


@router.patch("/components/{component_id}")
async def patch_component(component_id: str, payload: IncentiveComponentUpdate, request: Request) -> Dict[str, Any]:
    actor, _eid = await _configure(request, "mengubah komponen insentif")
    doc = await db[itg.COMPONENTS].find_one({"id": component_id}, {"_id": 0})
    await guard_doc(request, itg.COMPONENTS, doc, not_found="Komponen insentif tidak ditemukan.")
    try:
        out = await itg.update_component(doc, payload.model_dump(exclude_unset=True), actor)
    except itg.InsentifError as exc:
        raise _err(exc)
    await audit(actor.get("name", ""), "incentive_component_updated", "incentive_component", component_id,
                payload.model_dump(exclude_unset=True))
    return itg.component_labels(out)


# ── Definisi angka & pencocokan ──────────────────────────────────────────────────────────────────────────────────────
@router.get("/definitions/current")
async def get_definition(request: Request) -> Dict[str, Any]:
    _actor, ctx = await _view(request)
    if _all_pt(ctx):
        return {"all_pt": True, "items": []}
    d = await idef.current_definition(ctx.active_entity_id)
    return {"all_pt": False, "entity_id": d["entity_id"], "version": d["version"],
            "effective_from": d["effective_from"], "items": idef.labels(d)}


@router.get("/reconciliation")
async def get_reconciliation(request: Request, period: str = Query("")) -> Dict[str, Any]:
    _actor, ctx = await _view(request)
    if _all_pt(ctx):
        return {"all_pt": True}
    eid = ctx.active_entity_id
    try:
        p = period or await ip.current_period("month", eid)
        ip.normalize("month", p)
    except ip.PeriodeError:
        raise HTTPException(status_code=400, detail="Periode pencocokan harus satu bulan, contoh: 2026-10.")
    synced = await ifacts.ensure_fresh(60)
    return {"all_pt": False, **await ifacts.reconcile(eid, p), "facts_synced_at": synced}


@router.post("/facts/rebuild")
async def post_rebuild(payload: Optional[IncentiveFactRebuild], request: Request) -> Dict[str, Any]:
    actor, eid = await _configure(request, "membangun ulang angka insentif")
    date_from = ((payload.date_from if payload else None) or "").strip() or None
    if date_from:
        try:
            ip.bounds_with("month", date_from[:7], 12)
            if len(date_from) != 10:
                raise ip.PeriodeError("")
        except (ip.PeriodeError, ValueError):
            raise HTTPException(status_code=400, detail="Tanggal mulai harus berbentuk tanggal, contoh: 2026-10-01.")
    try:
        res = await ifacts.rebuild(date_from, eid)
    except ifacts.FaktaSibuk as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    await audit(actor.get("name", ""), "incentive_facts_rebuilt", "incentive_facts", eid, res)
    return {"rows_shipment": res["rows_shipment"], "rows_collection": res["rows_collection"],
            "orders": res["orders"], "date_from": res["from"]}
