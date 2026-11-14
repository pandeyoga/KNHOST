"""HRD H4 router — Payroll & Payslip.

Koleksi kanonik (entity-scoped): hr_payroll_runs (prun_), hr_payslips (slip_).
RBAC: read run/payslip = hr.view (PII gaji → pemilik view juga punya view_pii).
       PK-22 (FY-09, K-41) — siapkan (buat/hitung ulang/ajukan/batal draf) = payroll.create; sahkan/kembalikan/batal
       yang diajukan = payroll.approve; posting = payroll.post; void = payroll.void; bayar & setor kewajiban =
       payroll.pay. Pengaturan gaji tetap hr.manage_payroll.
       /payslips/me + /pdf milik sendiri = autentikasi + karyawan ter-link.
Lihat memory/PLAN_HRD.md §6 H4 + §4.3/§4.4 (integrasi komisi & GL).
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse

from db import db
from services import approval_policy_service as _aps   # KP-T4 — satu tabel kebijakan persetujuan
from dependencies import require_permission, require_any_permission, current_user, audit
from entity_scope import entity_ctx, resolve_list_scope, assert_entity_access, guard_doc
from services import hr_payroll_service as pay
from services import hr_service
from services.hr_payroll_pdf import payslip_pdf_bytes
from schemas_hr_payroll import (PayrollRunInput, PayRunInput, HrSettingsUpdate,
                               PayrollRejectInput, PayrollReasonInput, RemittanceInput,
                               PayComponentCreate, PayComponentPatch, PayInputCreate, PayInputCancel)
from services import gl_service as _gl
from services import hr_remittance_service as _rem
from services import hr_pay_components as _pcomp   # PY-T1 — komponen gaji per PT
from services import hr_pay_inputs as _pinp        # PY-T1 — antrean masukan komponen

router = APIRouter(prefix="/api")


def _http(e: Exception) -> HTTPException:
    """PK-22 — periode tertutup & status yang salah = 409 (pesan apa adanya); galat isian lain = 400."""
    if isinstance(e, (_gl.ClosedPeriodError, pay.PayrollConflict)):
        return HTTPException(status_code=409, detail=str(e))
    return HTTPException(status_code=400, detail=str(e))

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
    await require_permission(request, "payroll", "create")   # PK-22
    from entity_scope import resolve_requested_entity
    # PK-45 (PY-10) — sama dengan proses buat: PT dari penugasan, bukan isi permintaan mentah (kosong → PT aktif).
    body.entity_id = resolve_requested_entity(await entity_ctx(request), body.entity_id)
    try:
        from services import periodic_posting
        periodic_posting.assert_period_started(body.period)   # PK-22 (FY-02)
        return await pay.preview_run(body.entity_id, body.period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/hr/payroll/runs")
async def create_payroll_run(request: Request, body: PayrollRunInput):
    actor = await require_permission(request, "payroll", "create")   # PK-22
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
    actor = await require_permission(request, "payroll", "create")   # PK-22
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
    actor = await require_permission(request, "payroll", "approve")   # PK-22
    await guard_doc(request, "hr_payroll_runs", await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}),
                    not_found="Payroll run tidak ditemukan")  # KN-B30
    try:
        run = await pay.reject_run(run_id, actor, body.reason)
    except ValueError as e:
        raise _http(e)
    await audit(actor["name"], "hr.payroll.run_reject", "hr_payroll_runs", run_id,
                {"period": run.get("period")}, reason=body.reason)
    return run


@router.post("/hr/payroll/runs/{run_id}/approve")
async def approve_payroll_run(request: Request, run_id: str):
    actor = await require_permission(request, "payroll", "approve")   # PK-22
    await guard_doc(request, "hr_payroll_runs", await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}),
                    not_found="Payroll run tidak ditemukan")  # KN-B30
    await _aps.guard_door("hr_payroll", actor, collection="hr_payroll_runs", doc_id=run_id)   # KP-T4
    try:
        run = await pay.approve_run(run_id, actor)
    except ValueError as e:
        raise _http(e)
    await audit(actor["name"], "hr.payroll.run_approve", "hr_payroll_runs", run_id, {})
    return run


@router.post("/hr/payroll/runs/{run_id}/recalculate")
async def recalculate_payroll_run(request: Request, run_id: str):
    """PK-22 (FY-06) — hitung ulang proses draf (slip diperbarui di tempat, id & nomor tetap)."""
    actor = await require_permission(request, "payroll", "create")
    await guard_doc(request, "hr_payroll_runs", await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}),
                    not_found="Payroll run tidak ditemukan")
    try:
        run = await pay.recalculate_run(run_id, actor)
    except ValueError as e:
        raise _http(e)
    await audit(actor["name"], "hr.payroll.run_recalculate", "hr_payroll_runs", run_id,
                {"period": run.get("period"), "recalc_count": run.get("recalc_count"), "totals": run.get("totals")})
    return run


@router.post("/hr/payroll/runs/{run_id}/cancel")
async def cancel_payroll_run(request: Request, run_id: str, body: PayrollReasonInput):
    """PK-22 (FY-06) — batalkan proses draf (`payroll.create`) atau yang sudah diajukan/disahkan (`payroll.approve`)."""
    actor = await require_any_permission(request, [("payroll", "create"), ("payroll", "approve")])
    doc = await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0})
    await guard_doc(request, "hr_payroll_runs", doc, not_found="Payroll run tidak ditemukan")
    if doc.get("status") in ("pending_approval", "approved"):
        await require_permission(request, "payroll", "approve")
    else:
        await require_permission(request, "payroll", "create")
    try:
        run = await pay.cancel_run(run_id, actor, body.reason)
    except ValueError as e:
        raise _http(e)
    await audit(actor["name"], "hr.payroll.run_cancel", "hr_payroll_runs", run_id,
                {"period": run.get("period"), "from_status": run.get("cancelled_from")}, reason=body.reason)
    return run


@router.post("/hr/payroll/runs/{run_id}/post-gl")
async def post_payroll_run_gl(request: Request, run_id: str):
    actor = await require_permission(request, "payroll", "post")   # PK-22
    await guard_doc(request, "hr_payroll_runs", await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}),
                    not_found="Payroll run tidak ditemukan")  # KN-B30
    try:
        run = await pay.post_run_gl(run_id, actor)
    except ValueError as e:
        raise _http(e)
    await audit(actor["name"], "hr.payroll.run_post_gl", "hr_payroll_runs", run_id,
                {"journal_number": run.get("journal_number"), "journal_date": run.get("journal_date"),
                 "gl_status": run.get("gl_status")})
    return run


@router.post("/hr/payroll/runs/{run_id}/void")
async def void_payroll_run(request: Request, run_id: str, body: PayrollReasonInput):
    """PK-22 (FY-06) — void gaji yang sudah diposting: jurnal gaji dibalik bertanggal buku jurnal asal."""
    actor = await require_permission(request, "payroll", "void")
    await guard_doc(request, "hr_payroll_runs", await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}),
                    not_found="Payroll run tidak ditemukan")
    try:
        run = await pay.void_run(run_id, actor, body.reason)
    except ValueError as e:
        raise _http(e)
    await audit(actor["name"], "hr.payroll.run_void", "hr_payroll_runs", run_id,
                {"period": run.get("period"), "void_journal_number": run.get("void_journal_number")},
                reason=body.reason)
    return run


@router.post("/hr/payroll/runs/{run_id}/pay")
async def pay_payroll_run(request: Request, run_id: str, body: PayRunInput):
    actor = await require_permission(request, "payroll", "pay")   # PK-22
    await guard_doc(request, "hr_payroll_runs", await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}),
                    not_found="Payroll run tidak ditemukan")  # KN-B30
    try:
        run = await pay.pay_run(run_id, actor, body.cash_account, account_id=body.account_id)
    except ValueError as e:
        raise _http(e)
    await audit(actor["name"], "hr.payroll.run_pay", "hr_payroll_runs", run_id,
                {"paid_journal_number": run.get("paid_journal_number")})
    return run


# ───────────────────────── PK-22 — Setoran kewajiban (BPJS, PPh 21) ─────────────────────────
@router.get("/hr/payroll/remittances")
async def list_remittances(request: Request, period: Optional[str] = Query(None), kind: Optional[str] = Query(None),
                           entity_id: Optional[str] = Query(None), page: int = Query(1, ge=1),
                           page_size: int = Query(50, ge=1, le=200)):
    """Riwayat setoran berhalaman (+ `total`), dicakup PT pengguna."""
    await require_permission(request, "hr", "view")
    ctx = await entity_ctx(request)
    scope = resolve_list_scope("hr_statutory_remittances", {}, ctx, entity_id)
    try:
        return await _rem.list_remittances(scope, period=period or "", kind=kind or "", page=page,
                                           page_size=page_size)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/hr/payroll/remittances/outstanding")
async def remittance_outstanding(request: Request, period: str = Query(...)):
    """Per jenis (BPJS, PPh 21): kewajiban masa itu, sudah disetor, sisa — untuk PT aktif."""
    await require_permission(request, "hr", "view")
    ctx = await entity_ctx(request)
    if ctx.view_all or not ctx.active_entity_id or ctx.active_entity_id == "all":
        raise HTTPException(status_code=400, detail="Pilih satu PT dulu untuk melihat kewajiban setoran.")
    try:
        return await _rem.outstanding(ctx.active_entity_id, period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/hr/payroll/remittances")
async def create_remittance(request: Request, body: RemittanceInput):
    """PK-22 (FY-07) — catat setoran: satu kas keluar Dr hutang BPJS/PPh 21 / Cr kas (pembuat kas PK-20)."""
    actor = await require_permission(request, "payroll", "pay")
    ctx = await entity_ctx(request)
    if ctx.view_all or not ctx.active_entity_id or ctx.active_entity_id == "all":
        raise HTTPException(status_code=400, detail="Pilih satu PT dulu untuk mencatat setoran.")
    from idempotency import HEADER as _IDEM
    try:
        doc = await _rem.create_remittance(ctx.active_entity_id, body.model_dump(), actor,
                                           idem_key=(request.headers.get(_IDEM) or "").strip())
    except _gl.ClosedPeriodError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "hr.payroll.remittance_create", "hr_statutory_remittances", doc["id"],
                {"number": doc.get("number"), "kind": doc.get("kind"), "period": doc.get("period"),
                 "amount": doc.get("amount"), "cash_txn_id": doc.get("cash_txn_id")})
    return doc


# ───────────────────────── PY-T1 — Komponen gaji & antrean masukan ─────────────────────────
def _pyt1_http(e: Exception) -> HTTPException:
    if isinstance(e, (_pcomp.ComponentConflict, _pinp.InputConflict)):
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, LookupError):
        return HTTPException(status_code=404, detail=str(e))
    return HTTPException(status_code=400, detail=str(e))


def _pt_aktif(ctx, verb: str) -> str:
    if ctx.view_all or not ctx.active_entity_id or ctx.active_entity_id == "all":
        raise HTTPException(status_code=400, detail=f"Pilih satu PT dulu untuk {verb}.")
    return ctx.active_entity_id


@router.get("/hr/payroll/components")
async def list_pay_components(request: Request):
    """Daftar komponen gaji PT aktif (isi awal dijamin)."""
    await require_permission(request, "hr", "view")
    ctx = await entity_ctx(request)
    eid = _pt_aktif(ctx, "melihat komponen gaji")
    return {"items": await _pcomp.list_components(eid), "entity_id": eid}


@router.post("/hr/payroll/components")
async def create_pay_component(request: Request, body: PayComponentCreate):
    actor = await require_permission(request, "hr", "manage_payroll")
    ctx = await entity_ctx(request)
    eid = _pt_aktif(ctx, "menambah komponen gaji")
    data = body.model_dump()
    if data.get("taxable") is None:
        data.pop("taxable")
    try:
        doc = await _pcomp.create_component(eid, data, actor)
    except ValueError as e:
        raise _pyt1_http(e)
    await audit(actor["name"], "hr.payroll.component_create", "hr_pay_components", doc["id"],
                {"entity_id": eid, "code": doc["code"], "kind": doc["kind"], "bucket": doc["bucket"],
                 "account_code": doc.get("account_code", "")})
    return doc


@router.patch("/hr/payroll/components/{comp_id}")
async def update_pay_component(request: Request, comp_id: str, body: PayComponentPatch):
    actor = await require_permission(request, "hr", "manage_payroll")
    doc = await db.hr_pay_components.find_one({"id": comp_id}, {"_id": 0})
    await guard_doc(request, "hr_pay_components", doc, not_found="Komponen gaji tidak ditemukan")
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        out = await _pcomp.update_component(comp_id, doc["entity_id"], data, actor)
    except (ValueError, LookupError) as e:
        raise _pyt1_http(e)
    await audit(actor["name"], "hr.payroll.component_update", "hr_pay_components", comp_id,
                {"code": doc.get("code"), "changes": data})
    return out


@router.get("/hr/payroll/inputs")
async def list_pay_inputs(request: Request, pay_period: Optional[str] = Query(None),
                          status: Optional[str] = Query(None), employee_id: Optional[str] = Query(None),
                          entity_id: Optional[str] = Query(None), page: int = Query(1, ge=1),
                          page_size: int = Query(50, ge=1, le=200)):
    """Antrean masukan berhalaman (+ `total`), dicakup PT pengguna."""
    await require_permission(request, "hr", "view")
    ctx = await entity_ctx(request)
    scope = resolve_list_scope("hr_pay_inputs", {}, ctx, entity_id)
    try:
        return await _pinp.list_inputs(scope, pay_period=pay_period or "", status=status or "",
                                       employee_id=employee_id or "", page=page, page_size=page_size)
    except ValueError as e:
        raise _pyt1_http(e)


@router.post("/hr/payroll/inputs")
async def create_pay_input(request: Request, body: PayInputCreate):
    """Masukan manual → `pending` (menunggu disahkan pemegang `payroll.approve`)."""
    actor = await require_permission(request, "payroll", "create")
    ctx = await entity_ctx(request)
    eid = _pt_aktif(ctx, "menambah masukan gaji")
    try:
        doc = await _pinp.create_manual_input(eid, body.model_dump(), actor)
    except ValueError as e:
        raise _pyt1_http(e)
    await audit(actor["name"], "hr.payroll.input_create", "hr_pay_inputs", doc["id"],
                {"entity_id": eid, "employee_id": doc["employee_id"], "component_code": doc["component_code"],
                 "pay_period": doc["pay_period"], "amount": doc["amount"]}, reason=doc.get("reason", ""))
    return doc


@router.post("/hr/payroll/inputs/{input_id}/approve")
async def approve_pay_input(request: Request, input_id: str):
    actor = await require_permission(request, "payroll", "approve")
    await guard_doc(request, "hr_pay_inputs", await db.hr_pay_inputs.find_one({"id": input_id}, {"_id": 0}),
                    not_found="Masukan tidak ditemukan")
    try:
        doc = await _pinp.approve_input(input_id, actor)
    except (ValueError, LookupError) as e:
        raise _pyt1_http(e)
    await audit(actor["name"], "hr.payroll.input_approve", "hr_pay_inputs", input_id,
                {"amount": doc.get("amount"), "pay_period": doc.get("pay_period")})
    return doc


@router.post("/hr/payroll/inputs/{input_id}/cancel")
async def cancel_pay_input(request: Request, input_id: str, body: PayInputCancel):
    actor = await require_permission(request, "payroll", "approve")
    await guard_doc(request, "hr_pay_inputs", await db.hr_pay_inputs.find_one({"id": input_id}, {"_id": 0}),
                    not_found="Masukan tidak ditemukan")
    try:
        doc = await _pinp.cancel_input_by_id(input_id, actor=actor, reason=body.reason)
    except (ValueError, LookupError) as e:
        raise _pyt1_http(e)
    await audit(actor["name"], "hr.payroll.input_cancel", "hr_pay_inputs", input_id,
                {"amount": doc.get("amount"), "pay_period": doc.get("pay_period"),
                 "cancelled_from": doc.get("cancelled_from")}, reason=body.reason)
    return doc


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
