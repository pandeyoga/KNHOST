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
  GET   /api/incentive/achievement                             incentive.view       KM-T2 — Capaian per sales (margin: view_margin)
  GET   /api/incentive/achievement/sources                     incentive.view       KM-T2 — dokumen di balik satu sel
  GET   /api/incentive/achievement/export                      incentive.view       KM-T2 — .xlsx Definisi · Capaian · Dokumen
  GET   /api/incentive/sheets                                  view|prepare|approve KM-T3 — daftar lembar (tanpa potret)
  POST  /api/incentive/sheets                                  incentive.prepare    KM-T3 — lembar draf (+ baris dipotret)
  GET   /api/incentive/sheets/adjustable-lines?sales_id        incentive.prepare    KM-T3 — rujukan baris penyesuaian
  GET   /api/incentive/sheets/{id}                             view|prepare|approve KM-T3 — lembar + `drift`
  POST/PATCH/DELETE /api/incentive/sheets/{id}/lines[/{line}]  incentive.prepare    KM-T3 — baris (hanya draf)
  POST  /api/incentive/sheets/{id}/refresh · submit · cancel   incentive.prepare    KM-T3
  POST  /api/incentive/sheets/{id}/approve · return            incentive.approve    KM-T3 — kontrol dua orang K-25
  GET   /api/incentive/sheets/{id}/export                      view|prepare|approve KM-T3 — .xlsx Lembar · Potret

PT = PT konteks pengguna (`02_STANDAR.md` §3.4 N1); mode "Semua PT" hanya baca (tulis → 409 `assert_write_entity`, N3).
Logika di `services/incentive_targets.py`, `incentive_periods.py`, `incentive_definitions.py`, `incentive_facts.py`;
Capaian (KM-T2, hanya baca; "Semua PT" → 400) di `services/incentive_achievement.py`; Lembar Insentif (KM-T3) di
`services/incentive_sheet_service.py` (PT lembar = PT dokumen, diadu dengan cakupan pengguna lewat `guard_doc`).
"""
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from db import db
from dependencies import audit, has_permission, require_any_permission, require_permission
from entity_scope import assert_write_entity, entity_ctx, guard_doc, resolve_list_scope
from schemas_incentive import (IncentiveComponentCreate, IncentiveComponentUpdate, IncentiveFactRebuild,
                               IncentiveSheetApprove, IncentiveSheetCreate, IncentiveSheetLineAdd,
                               IncentiveSheetLinePatch, IncentiveSheetReason, IncentiveTargetCopy, IncentiveTargetSave)
from services import incentive_achievement as iach
from services import incentive_definitions as idef
from services import incentive_facts as ifacts
from services import incentive_periods as ip
from services import incentive_sheet_service as iss
from services import incentive_targets as itg

router = APIRouter(prefix="/api/incentive")

MODUL = "Kinerja & Insentif"
PESAN_LIHAT = f"Anda belum punya akses untuk melihat target dan aturan insentif. Minta Admin menambahkan akses '{MODUL}'."
PESAN_ATUR = f"Anda belum punya akses untuk mengatur target dan aturan insentif. Minta Admin menambahkan akses '{MODUL}'."
PESAN_CAPAIAN = f"Anda belum punya akses untuk melihat capaian insentif. Minta Admin menambahkan akses '{MODUL}'."
PESAN_LEMBAR_LIHAT = f"Anda belum punya akses untuk melihat lembar insentif. Minta Admin menambahkan akses '{MODUL}'."
PESAN_LEMBAR_SIAP = f"Anda belum punya akses untuk menyiapkan lembar insentif. Minta Admin menambahkan akses '{MODUL}'."
PESAN_LEMBAR_SAH = f"Anda belum punya akses untuk mengesahkan lembar insentif. Minta Admin menambahkan akses '{MODUL}'."


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


# ── KM-T2 — Capaian (hanya baca) ─────────────────────────────────────────────────────────────────────────────────────
async def _capaian_ctx(request: Request, period_type: str, period: str, date_from: str, date_to: str,
                       cumulative: bool):
    """Izin `incentive.view` (Z1) → PT konteks (Semua PT → 400) → periode → fakta segar → versi definisi PT."""
    actor = await require_permission(request, "incentive", "view", detail=PESAN_CAPAIAN)
    ctx = await entity_ctx(request)
    if _all_pt(ctx):
        raise HTTPException(status_code=400, detail=iach.PESAN_SEMUA_PT)
    eid = ctx.active_entity_id
    try:
        per = await iach.resolve_period(eid, period_type, period, date_from, date_to, cumulative)
    except iach.CapaianError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    synced = await ifacts.ensure_fresh(60)
    defn = await idef.current_definition(eid)
    if defn.get("dasar_omzet") in ("pesanan", "lunas"):
        from services import analytics_facts
        await analytics_facts.ensure_fresh(60)
    margin_ok = await has_permission(actor, "incentive", "view_margin")
    return actor, eid, per, defn, synced, margin_ok


def _flt(sales_ids: Optional[List[str]], customer_id: str, category: str, line_code: str, price_source: str):
    return iach.saringan(sales_ids, customer_id, category, line_code, price_source)


@router.get("/achievement")
async def get_achievement(request: Request, period_type: str = Query("month"), period: str = Query(""),
                          date_from: str = Query(""), date_to: str = Query(""), compare: str = Query("none"),
                          cumulative: bool = Query(False), group_by: str = Query("sales"),
                          sales_ids: Optional[List[str]] = Query(None, alias="sales_id[]"),
                          customer_id: str = Query(""), category: str = Query(""), line_code: str = Query(""),
                          price_source: str = Query("")) -> Dict[str, Any]:
    """Capaian per sales (atau per pelanggan/kategori/sumber harga) untuk satu PT dan satu periode."""
    _actor, eid, per, defn, synced, margin_ok = await _capaian_ctx(request, period_type, period, date_from, date_to,
                                                                   cumulative)
    flt = _flt(sales_ids, customer_id, category, line_code, price_source)
    try:
        cmp = await iach.compare_period(eid, per, compare)
        res = await iach.achievement(eid, per, defn, flt, (group_by or "sales").strip().lower(), margin_ok, cmp)
    except iach.CapaianError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"entity_id": eid, "period": per.out(), "definition": iach.definition_out(defn, per),
            "facts_as_of": synced, "reconciliation": await iach.reconciliation(eid, per), "group_by": group_by,
            "margin_visible": margin_ok, "piutang_as_of": iach.piutang_per(per), **res,
            "compare": res.get("compare") or {"label": "", "by_key": {}}}


@router.get("/achievement/sources")
async def get_achievement_sources(request: Request, metric: str = Query(...), sales_id: Optional[str] = Query(None),
                                  key: Optional[str] = Query(None), period_type: str = Query("month"),
                                  period: str = Query(""), date_from: str = Query(""), date_to: str = Query(""),
                                  cumulative: bool = Query(False), group_by: str = Query("sales"),
                                  customer_id: str = Query(""), category: str = Query(""),
                                  line_code: str = Query(""), price_source: str = Query(""),
                                  page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
    """Dokumen di balik satu angka (omzet · retur · uang masuk) satu sales — jumlahnya = angka sel."""
    _actor, eid, per, defn, _synced, _m = await _capaian_ctx(request, period_type, period, date_from, date_to,
                                                             cumulative)
    gb = (group_by or "sales").strip().lower()
    k = sales_id if gb == "sales" else key
    if k is None:
        raise HTTPException(status_code=400, detail=iach.PESAN_KUNCI)
    try:
        return {"period": per.out(), **await iach.sources(
            eid, per, defn, _flt(None, customer_id, category, line_code, price_source), metric=metric, key=k,
            group_by=gb, page=page, page_size=page_size)}
    except iach.CapaianError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/achievement/export")
async def get_achievement_export(request: Request, period_type: str = Query("month"), period: str = Query(""),
                                 date_from: str = Query(""), date_to: str = Query(""), cumulative: bool = Query(False),
                                 group_by: str = Query("sales"),
                                 sales_ids: Optional[List[str]] = Query(None, alias="sales_id[]"),
                                 customer_id: str = Query(""), category: str = Query(""), line_code: str = Query(""),
                                 price_source: str = Query(""), q: str = Query(""),
                                 only_numbers: bool = Query(False)) -> Response:
    """Berkas `capaian-<kode PT>-<periode>.xlsx`: Definisi · Capaian · Dokumen (kolom margin hanya `view_margin`)."""
    actor, eid, per, defn, _synced, margin_ok = await _capaian_ctx(request, period_type, period, date_from, date_to,
                                                                   cumulative)
    try:
        body, name = await iach.export_xlsx(eid, per, defn, _flt(sales_ids, customer_id, category, line_code,
                                                                 price_source),
                                            (group_by or "sales").strip().lower(), margin_ok, actor, q=q,
                                            only_numbers=only_numbers)
    except iach.CapaianError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Response(content=body, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ── KM-T3 — Lembar Insentif (dokumen keputusan; nominal diketik orang, angka dasar dipotret) ────────────────────────
#: Membaca lembar: pemegang `incentive.view`, juga penyiap (`prepare`) dan pemutus (`approve`) — keduanya bekerja di
#: lembar yang sama (penyiap bawaan Admin Sales tidak memegang `incentive.view`).
BACA_LEMBAR = [("incentive", "view"), ("incentive", "prepare"), ("incentive", "approve")]
SHEETS = "incentive_sheets"
PESAN_LEMBAR_404 = "Lembar insentif tidak ditemukan."


def _lembar_err(exc: iss.LembarError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=str(exc))


async def _lembar(request: Request, sheet_id: str) -> Dict[str, Any]:
    """Lembar ber-id → PT dokumen diadu dengan cakupan pengguna (N1/N2); tidak ada/PT lain → 404."""
    doc = await iss.get_sheet(sheet_id)
    await guard_doc(request, SHEETS, doc, not_found=PESAN_LEMBAR_404)
    return doc


async def _siap(request: Request, sheet_id: str, action: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    actor = await require_permission(request, "incentive", "prepare", detail=PESAN_LEMBAR_SIAP)
    assert_write_entity(await entity_ctx(request), action)
    return actor, await _lembar(request, sheet_id)


async def _sah(request: Request, sheet_id: str, action: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    actor = await require_permission(request, "incentive", "approve", detail=PESAN_LEMBAR_SAH)
    assert_write_entity(await entity_ctx(request), action)
    return actor, await _lembar(request, sheet_id)


async def _jejak(actor: Dict[str, Any], action: str, doc: Dict[str, Any], extra: Optional[Dict[str, Any]] = None,
                 reason: str = "") -> None:
    await audit(actor.get("name", ""), action, "incentive_sheet", doc.get("id", ""),
                {"number": doc.get("number"), "status": doc.get("status"), "totals": doc.get("totals"),
                 **(extra or {})}, reason=reason, scope_entity_id=doc.get("entity_id") or "")


@router.get("/sheets")
async def list_incentive_sheets(request: Request, pay_period: str = Query(""), status: str = Query(""),
                                q: str = Query(""), page: int = Query(1, ge=1),
                                page_size: int = Query(25, ge=1, le=100)) -> Dict[str, Any]:
    """Daftar lembar PT aktif (mode "Semua PT": semua PT yang ditugaskan, hanya baca) — tanpa potret baris. `q` = cari
    nomor atau judul (tanpa beda huruf besar)."""
    await require_any_permission(request, BACA_LEMBAR, detail=PESAN_LEMBAR_LIHAT)
    ctx = await entity_ctx(request)
    query: Dict[str, Any] = {}
    if pay_period.strip():
        query["pay_period"] = pay_period.strip()
    if status.strip():
        if status.strip() not in iss.STATUSES:
            raise HTTPException(status_code=400, detail="Status lembar tidak dikenal.")
        query["status"] = status.strip()
    if q.strip():
        import re
        rx = {"$regex": re.escape(q.strip()[:60]), "$options": "i"}
        query["$or"] = [{"number": rx}, {"title": rx}]
    out = await iss.list_sheets(resolve_list_scope(SHEETS, query, ctx), page=page, page_size=page_size)
    return {**out, "all_pt": _all_pt(ctx), "statuses": [{"value": k, "label": v} for k, v in iss.STATUS_LABEL.items()]}


@router.post("/sheets")
async def create_incentive_sheet(payload: IncentiveSheetCreate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "incentive", "prepare", detail=PESAN_LEMBAR_SIAP)
    eid = assert_write_entity(await entity_ctx(request), "membuat lembar insentif")
    try:
        doc = await iss.create_sheet(eid, payload.model_dump(), actor)
    except iss.LembarError as exc:
        raise _lembar_err(exc)
    await _jejak(actor, "incentive_sheet_created", doc, {"pay_period": doc.get("pay_period")})
    return iss.sheet_out(doc, await has_permission(actor, "incentive", "view_margin"))


@router.get("/sheets/options")
async def get_sheet_options(request: Request) -> Dict[str, Any]:
    """Pilihan isian baris lembar untuk PT aktif: daftar sales (`sales_roster`) dan komponen yang aktif."""
    await require_any_permission(request, BACA_LEMBAR, detail=PESAN_LEMBAR_LIHAT)
    ctx = await entity_ctx(request)
    if _all_pt(ctx):
        return {"all_pt": True, "sales": [], "components": []}
    eid = ctx.active_entity_id
    comps = [itg.component_labels(c) for c in await itg.list_components(eid) if c.get("is_active") is not False]
    return {"all_pt": False, "sales": [{"id": s["id"], "name": s["name"]} for s in await itg.sales_roster(eid)
                                       if s.get("active")],
            "components": [{k: c.get(k) for k in ("id", "code", "name", "basis_period_type", "basis_label")}
                           for c in comps]}


@router.get("/sheets/adjustable-lines")
async def get_adjustable_lines(request: Request, sales_id: str = Query(...)) -> Dict[str, Any]:
    await require_permission(request, "incentive", "prepare", detail=PESAN_LEMBAR_SIAP)
    ctx = await entity_ctx(request)
    if _all_pt(ctx):
        return {"items": [], "all_pt": True}
    return await iss.adjustable_lines(ctx.active_entity_id, sales_id)


@router.get("/sheets/{sheet_id}")
async def get_incentive_sheet(sheet_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_any_permission(request, BACA_LEMBAR, detail=PESAN_LEMBAR_LIHAT)
    doc = await _lembar(request, sheet_id)
    out = iss.sheet_out(doc, await has_permission(actor, "incentive", "view_margin"))
    out["drift"] = await iss.drift(doc)
    return out


@router.post("/sheets/{sheet_id}/lines")
async def add_incentive_sheet_line(sheet_id: str, payload: IncentiveSheetLineAdd, request: Request) -> Dict[str, Any]:
    actor, doc = await _siap(request, sheet_id, "mengubah lembar insentif")
    try:
        out = await iss.add_line(doc, payload.model_dump(), actor)
    except iss.LembarError as exc:
        raise _lembar_err(exc)
    await _jejak(actor, "incentive_sheet_line_added", out, {"line": (out.get("lines") or [{}])[-1].get("id")})
    return iss.sheet_out(out, await has_permission(actor, "incentive", "view_margin"))


@router.patch("/sheets/{sheet_id}/lines/{line_id}")
async def patch_incentive_sheet_line(sheet_id: str, line_id: str, payload: IncentiveSheetLinePatch,
                                     request: Request) -> Dict[str, Any]:
    actor, doc = await _siap(request, sheet_id, "mengubah lembar insentif")
    try:
        out = await iss.patch_line(doc, line_id, payload.model_dump(exclude_unset=True), actor)
    except iss.LembarError as exc:
        raise _lembar_err(exc)
    await _jejak(actor, "incentive_sheet_line_updated", out, {"line": line_id,
                                                              **payload.model_dump(exclude_unset=True)})
    return iss.sheet_out(out, await has_permission(actor, "incentive", "view_margin"))


@router.delete("/sheets/{sheet_id}/lines/{line_id}")
async def delete_incentive_sheet_line(sheet_id: str, line_id: str, request: Request) -> Dict[str, Any]:
    actor, doc = await _siap(request, sheet_id, "mengubah lembar insentif")
    try:
        out = await iss.delete_line(doc, line_id, actor)
    except iss.LembarError as exc:
        raise _lembar_err(exc)
    await _jejak(actor, "incentive_sheet_line_deleted", out, {"line": line_id})
    return iss.sheet_out(out, await has_permission(actor, "incentive", "view_margin"))


@router.post("/sheets/{sheet_id}/refresh")
async def refresh_incentive_sheet(sheet_id: str, request: Request) -> Dict[str, Any]:
    actor, doc = await _siap(request, sheet_id, "menyegarkan angka dasar lembar insentif")
    try:
        res = await iss.refresh_sheet(doc, actor)
    except iss.LembarError as exc:
        raise _lembar_err(exc)
    await _jejak(actor, "incentive_sheet_refreshed", res["sheet"], {"changed": res["changed"]})
    return {"changed": res["changed"],
            "sheet": iss.sheet_out(res["sheet"], await has_permission(actor, "incentive", "view_margin"))}


@router.post("/sheets/{sheet_id}/submit")
async def submit_incentive_sheet(sheet_id: str, request: Request) -> Dict[str, Any]:
    actor, doc = await _siap(request, sheet_id, "mengajukan lembar insentif")
    try:
        out = await iss.submit_sheet(doc, actor)
    except iss.LembarError as exc:
        raise _lembar_err(exc)
    await _jejak(actor, "incentive_sheet_submitted", out)
    return iss.sheet_out(out, await has_permission(actor, "incentive", "view_margin"))


@router.post("/sheets/{sheet_id}/approve")
async def approve_incentive_sheet(sheet_id: str, request: Request,
                                  payload: Optional[IncentiveSheetApprove] = None) -> Dict[str, Any]:
    actor, doc = await _sah(request, sheet_id, "mengesahkan lembar insentif")
    corr = [c.model_dump() for c in ((payload.corrections if payload else None) or [])]
    try:
        out = await iss.approve_sheet(doc, corr, actor)
    except iss.LembarError as exc:
        raise _lembar_err(exc)
    await _jejak(actor, "incentive_sheet_approved", out, {"corrections": corr})
    return iss.sheet_out(out, await has_permission(actor, "incentive", "view_margin"))


@router.post("/sheets/{sheet_id}/return")
async def return_incentive_sheet(sheet_id: str, payload: IncentiveSheetReason, request: Request) -> Dict[str, Any]:
    actor, doc = await _sah(request, sheet_id, "mengembalikan lembar insentif")
    try:
        out = await iss.return_sheet(doc, payload.reason, actor)
    except iss.LembarError as exc:
        raise _lembar_err(exc)
    await _jejak(actor, "incentive_sheet_returned", out, reason=out.get("return_reason") or "")
    return iss.sheet_out(out, await has_permission(actor, "incentive", "view_margin"))


@router.post("/sheets/{sheet_id}/cancel")
async def cancel_incentive_sheet(sheet_id: str, payload: IncentiveSheetReason, request: Request) -> Dict[str, Any]:
    actor, doc = await _siap(request, sheet_id, "membatalkan lembar insentif")
    try:
        out = await iss.cancel_sheet(doc, payload.reason, actor)
    except iss.LembarError as exc:
        raise _lembar_err(exc)
    await _jejak(actor, "incentive_sheet_cancelled", out, reason=out.get("cancel_reason") or "")
    return iss.sheet_out(out, await has_permission(actor, "incentive", "view_margin"))


@router.get("/sheets/{sheet_id}/export")
async def export_incentive_sheet(sheet_id: str, request: Request) -> Response:
    """Berkas `lembar-insentif-<nomor>.xlsx`: Lembar (kolom layar + total) · Potret (seluruh angka potret)."""
    actor = await require_any_permission(request, BACA_LEMBAR, detail=PESAN_LEMBAR_LIHAT)
    doc = await _lembar(request, sheet_id)
    body, name = await iss.export_xlsx(doc, await has_permission(actor, "incentive", "view_margin"))
    return Response(content=body, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
