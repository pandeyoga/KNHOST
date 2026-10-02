"""HRD H4 router — Payroll & Payslip.

Koleksi kanonik (entity-scoped): hr_payroll_runs (prun_), hr_payslips (slip_).
RBAC: read run/payslip = hr.view (PII gaji → pemilik view juga punya view_pii).
       create/approve/post-gl/pay + settings = hr.manage_payroll.
       /payslips/me + /pdf milik sendiri = autentikasi + karyawan ter-link.
Lihat memory/PLAN_HRD.md §6 H4 + §4.3/§4.4 (integrasi komisi & GL).
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse

from db import db
from dependencies import require_permission, current_user, audit
from entity_scope import entity_ctx, resolve_list_scope, assert_entity_access, guard_doc
from services import hr_payroll_service as pay
from services import hr_service
from services.hr_payroll_pdf import payslip_pdf_bytes
from schemas_hr_payroll import (PayrollRunInput, PayRunInput, HrSettingsUpdate,
                               PayrollRejectInput)

router = APIRouter(prefix="/api")

# Subset config statutory yang relevan untuk UI Setup.
SETTINGS_KEYS = ("bpjs", "jkk_classes", "ptkp_table", "ter_enabled", "overtime",
                 "payroll_commission_mode", "feature_toggles")


# ───────────────────────── Settings (statutory) ─────────────────────────
@router.get("/hr/payroll/settings")
async def get_payroll_settings(request: Request):
    """FASE E-4 (E4.5) — setelan statutory yang BERLAKU untuk badan usaha aktif."""
    await require_permission(request, "hr", "view")
    ctx = await entity_ctx(request)
    cfg = await hr_service.get_hr_settings(ctx.active_entity_id)
    return {k: cfg.get(k) for k in SETTINGS_KEYS + ("entity_id", "entity_overrides")}


@router.put("/hr/payroll/settings")
async def update_payroll_settings(request: Request, body: HrSettingsUpdate):
    """IX-06 — tulis lewat resolver kanonik ke lapisan yang DIPILIH (entitas aktif / global)."""
    actor = await require_permission(request, "hr", "manage_payroll")
    import config_registry as registry
    from services import config_resolver as resolver
    ctx = await entity_ctx(request)
    patch = {k: v for k, v in (body.settings or {}).items() if k in SETTINGS_KEYS}
    if not patch:
        raise HTTPException(status_code=400, detail="Tidak ada field statutory yang valid untuk diperbarui.")
    if body.scope == "global":
        if not ctx.is_cross_entity:
            raise HTTPException(status_code=403, detail="Nilai grup (global) hanya dapat diubah peran lintas badan usaha.")
        scope_type, scope_id = "global", ""
    elif body.scope == "entity":
        if ctx.view_all or not ctx.active_entity_id:
            raise HTTPException(status_code=400, detail="Pilih satu badan usaha aktif untuk menyimpan nilai khususnya.")
        scope_type, scope_id = "entity", ctx.active_entity_id
    else:
        raise HTTPException(status_code=400, detail="scope harus 'entity' atau 'global'.")
    items: list = []

    def walk(prefix: str, val):
        key = f"hr.{prefix}"
        if registry.get(key):
            items.append((key, val))
        elif isinstance(val, dict) and val:
            for k, v in val.items():
                walk(f"{prefix}.{k}", v)
        else:
            raise HTTPException(status_code=400, detail=f"Field '{prefix}' tidak dikenal di Pusat Pengaturan.")
    for k, v in patch.items():
        walk(k, v)
    for key, val in items:
        entry = registry.get(key)
        if scope_type not in (entry.get("scopes") or []):
            raise HTTPException(status_code=400, detail=f"'{key}' tidak bisa diatur pada level {scope_type}.")
        try:
            registry.coerce(entry, val)  # validasi semua sebelum satu pun ditulis
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"{entry['label']}: {exc}") from exc
    saved = []
    for key, val in items:
        try:
            row = await resolver.set_value(key, val, scope_type=scope_type, scope_id=scope_id,
                                           actor=actor.get("name", ""), actor_id=actor.get("id", ""),
                                           reason=body.reason or "Setelan payroll")
        except resolver.ConfigWriteError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        saved.append({"key": key, "value": row["value"]})
    await audit(actor["name"], "hr.payroll.settings_update", "config_values", scope_id or "global",
                {"scope": f"{scope_type}:{scope_id or '-'}", "saved": saved})
    cfg = await hr_service.get_hr_settings(ctx.active_entity_id)
    return {**{k: cfg.get(k) for k in SETTINGS_KEYS + ("entity_id", "entity_overrides")},
            "saved_scope": {"scope_type": scope_type, "scope_id": scope_id}}


# ───────────────────────── Payroll Runs ─────────────────────────
@router.get("/hr/payroll/runs")
async def list_payroll_runs(request: Request, entity_id: Optional[str] = Query(None),
                            status: Optional[str] = Query(None)):
    await require_permission(request, "hr", "view")
    ctx = await entity_ctx(request)
    scope = resolve_list_scope("hr_payroll_runs", {}, ctx, entity_id)
    return await pay.list_runs(scope, status)


@router.post("/hr/payroll/runs/preview")
async def preview_payroll_run(request: Request, body: PayrollRunInput):
    await require_permission(request, "hr", "manage_payroll")
    try:
        return await pay.preview_run(body.entity_id, body.period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/hr/payroll/runs")
async def create_payroll_run(request: Request, body: PayrollRunInput):
    actor = await require_permission(request, "hr", "manage_payroll")
    from entity_scope import resolve_requested_entity
    body.entity_id = resolve_requested_entity(await entity_ctx(request), body.entity_id)  # KN-B30
    try:
        run = await pay.create_run(body.entity_id, body.period, actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "hr.payroll.run_create", "hr_payroll_runs", run["id"],
                {"entity_id": body.entity_id, "period": body.period})
    return run


@router.get("/hr/payroll/runs/{run_id}")
async def get_payroll_run(request: Request, run_id: str):
    await require_permission(request, "hr", "view")
    ctx = await entity_ctx(request)
    run = await pay.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run tidak ditemukan.")
    assert_entity_access(run, "hr_payroll_runs", ctx)
    return run


@router.post("/hr/payroll/runs/{run_id}/submit")
async def submit_payroll_run(request: Request, run_id: str):
    """UTANG ALUR F-6.7 — draf payroll DIAJUKAN dulu, baru bisa disahkan."""
    actor = await require_permission(request, "hr", "manage_payroll")
    await guard_doc(request, "hr_payroll_runs", await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}),
                    not_found="Payroll run tidak ditemukan")  # KN-B30
    try:
        run = await pay.submit_run(run_id, actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "hr.payroll.run_submit", "hr_payroll_runs", run_id,
                {"period": run.get("period")})
    return run


@router.post("/hr/payroll/runs/{run_id}/reject")
async def reject_payroll_run(request: Request, run_id: str, body: PayrollRejectInput):
    """Kembalikan payroll yang diajukan ke draf — ALASAN wajib & tersimpan."""
    actor = await require_permission(request, "hr", "manage_payroll")
    await guard_doc(request, "hr_payroll_runs", await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}),
                    not_found="Payroll run tidak ditemukan")  # KN-B30
    try:
        run = await pay.reject_run(run_id, actor, body.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "hr.payroll.run_reject", "hr_payroll_runs", run_id,
                {"period": run.get("period")}, reason=body.reason)
    return run


@router.post("/hr/payroll/runs/{run_id}/approve")
async def approve_payroll_run(request: Request, run_id: str):
    actor = await require_permission(request, "hr", "manage_payroll")
    await guard_doc(request, "hr_payroll_runs", await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}),
                    not_found="Payroll run tidak ditemukan")  # KN-B30
    try:
        run = await pay.approve_run(run_id, actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "hr.payroll.run_approve", "hr_payroll_runs", run_id, {})
    return run


@router.post("/hr/payroll/runs/{run_id}/post-gl")
async def post_payroll_run_gl(request: Request, run_id: str):
    actor = await require_permission(request, "hr", "manage_payroll")
    await guard_doc(request, "hr_payroll_runs", await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}),
                    not_found="Payroll run tidak ditemukan")  # KN-B30
    try:
        run = await pay.post_run_gl(run_id, actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "hr.payroll.run_post_gl", "hr_payroll_runs", run_id,
                {"journal_number": run.get("journal_number")})
    return run


@router.post("/hr/payroll/runs/{run_id}/pay")
async def pay_payroll_run(request: Request, run_id: str, body: PayRunInput):
    actor = await require_permission(request, "hr", "manage_payroll")
    await guard_doc(request, "hr_payroll_runs", await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}),
                    not_found="Payroll run tidak ditemukan")  # KN-B30
    try:
        run = await pay.pay_run(run_id, actor, body.cash_account)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "hr.payroll.run_pay", "hr_payroll_runs", run_id,
                {"paid_journal_number": run.get("paid_journal_number")})
    return run


# ───────────────────────── Payslips ─────────────────────────
@router.get("/hr/payslips")
async def list_payslips(request: Request, entity_id: Optional[str] = Query(None),
                        period: Optional[str] = Query(None),
                        employee_id: Optional[str] = Query(None)):
    await require_permission(request, "hr", "view")
    ctx = await entity_ctx(request)
    scope = resolve_list_scope("hr_payslips", {}, ctx, entity_id)
    return await pay.list_payslips(scope, period, employee_id)


@router.get("/hr/payslips/me")
async def my_payslips(request: Request, period: Optional[str] = Query(None)):
    user = await current_user(request)
    return await pay.my_payslips(user, period)


@router.get("/hr/payslips/{slip_id}")
async def get_payslip(request: Request, slip_id: str):
    user = await current_user(request)
    slip = await pay.get_payslip(slip_id)
    if not slip:
        raise HTTPException(status_code=404, detail="Slip gaji tidak ditemukan.")
    if not await _can_view_slip(request, user, slip):
        raise HTTPException(status_code=403, detail="Tidak berwenang melihat slip ini.")
    return slip


@router.get("/hr/payslips/{slip_id}/pdf")
async def payslip_pdf(request: Request, slip_id: str):
    user = await current_user(request)
    slip = await pay.get_payslip(slip_id)
    if not slip:
        raise HTTPException(status_code=404, detail="Slip gaji tidak ditemukan.")
    if not await _can_view_slip(request, user, slip):
        raise HTTPException(status_code=403, detail="Tidak berwenang melihat slip ini.")
    ent = await db.business_entities.find_one({"id": slip.get("entity_id")}, {"_id": 0, "name": 1})
    pdf = payslip_pdf_bytes(slip, (ent or {}).get("name", "Kain Nusantara"))
    fname = f"slip-{slip.get('number', slip_id)}.pdf"
    return StreamingResponse(iter([pdf]), media_type="application/pdf",
                             headers={"Content-Disposition": f"inline; filename={fname}"})


async def _can_view_slip(request: Request, user, slip) -> bool:
    """Pemilik slip (karyawan ter-link) ATAU pemegang hr.view."""
    emp = await db.hr_employees.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    if emp and emp["id"] == slip.get("employee_id"):
        return True
    try:
        await require_permission(request, "hr", "view")
        return True
    except HTTPException:
        return False
