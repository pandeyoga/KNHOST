"""PY-T2 (PY-09) router — riwayat kompensasi dan penugasan PT karyawan bertanggal berlaku.

Koleksi: `hr_compensation_history` (hcomp_, per karyawan), `hr_employee_assignments` (hasg_, ber-PT). Logika di
`services/hr_compensation_service.py`.

Izin (tanpa pasangan izin baru): lihat = `hr.view` + `hr.view_pii` (nilai gaji = data pribadi); usul = `hr.update`
(yang dulu boleh mengubah gaji di master); sahkan / tolak / batalkan = `payroll.approve` (PK-22). Semua endpoint ber-id
mengadu PT karyawan (dan PT tujuan penugasan) dengan cakupan pelaku (02 §3.4 N1, N2).
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request

from db import db
from dependencies import audit, require_permission
from entity_scope import assert_entity_access, entity_ctx
from schemas_hr import AssignmentCreate, CompensationCreate, HistoryDecision
from services import hr_compensation_service as _hc

router = APIRouter(prefix="/api")

PII_MASK = ["base_salary", "fixed_components"]
PT_DILUAR = ("Anda belum punya akses ke PT tujuan, jadi belum bisa memindahkan karyawan ke sana. Minta Admin "
             "menambahkan PT itu ke penugasan akun Anda.")


def _http(e: Exception) -> HTTPException:
    if isinstance(e, _hc.CompensationConflict):
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, LookupError):
        return HTTPException(status_code=404, detail=str(e))
    return HTTPException(status_code=400, detail=str(e))


async def _employee(employee_id: str, ctx) -> Dict[str, Any]:
    emp = await db.hr_employees.find_one({"id": employee_id}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
    assert_entity_access(emp, "hr_employees", ctx)
    return emp


async def _row_employee(coll: str, row_id: str, ctx) -> Dict[str, Any]:
    row = await _hc.get_row(coll, row_id)
    if not row:
        raise HTTPException(status_code=404, detail="Baris riwayat tidak ditemukan.")
    await _employee(row["employee_id"], ctx)
    if coll == _hc.ASG and row.get("entity_id") not in ctx.allowed_entity_ids:
        raise HTTPException(status_code=403, detail=PT_DILUAR)
    return row


@router.get("/hr/employees/{employee_id}/compensation")
async def get_compensation(employee_id: str, request: Request) -> Dict[str, Any]:
    """Riwayat kompensasi + penugasan PT karyawan (semua status, terbaru dulu) + pilihan komponen tetap PT-nya."""
    await require_permission(request, "hr", "view")
    await require_permission(request, "hr", "view_pii")   # nilai gaji = data pribadi → 403 Z6 tanpa izin ini
    ctx = await entity_ctx(request)
    emp = await _employee(employee_id, ctx)
    out = await _hc.history(employee_id)
    out["fixed_component_options"] = await _hc.fixed_component_options(emp.get("entity_id") or "")
    out["employee"] = {"id": emp["id"], "name": emp.get("name", ""), "code": emp.get("code", ""),
                       "entity_id": emp.get("entity_id", "")}
    return out


@router.post("/hr/employees/{employee_id}/compensation")
async def propose_compensation(employee_id: str, body: CompensationCreate, request: Request) -> Dict[str, Any]:
    """Usulkan perubahan gaji pokok / komponen tetap bertanggal berlaku → baris `pending`."""
    actor = await require_permission(request, "hr", "update")
    ctx = await entity_ctx(request)
    emp = await _employee(employee_id, ctx)
    try:
        row = await _hc.propose_compensation(emp, body.model_dump(), actor)
    except ValueError as e:
        raise _http(e)
    await audit(actor["name"], "hr_compensation_proposed", "hr_compensation_history", row["id"],
                {"employee_id": employee_id, "effective_from": row["effective_from"], "status": row["status"]},
                reason=row["reason"], masked_fields=PII_MASK, scope_entity_id=emp.get("entity_id", ""))
    return row


async def _decide_comp(actor: Dict[str, Any], row_id: str, action: str, body: Optional[HistoryDecision],
                       request: Request) -> Dict[str, Any]:
    body = body or HistoryDecision()
    ctx = await entity_ctx(request)
    await _row_employee(_hc.COMP, row_id, ctx)
    try:
        row = await _hc.decide_compensation(row_id, action, actor, body.reason)
    except (ValueError, LookupError) as e:
        raise _http(e)
    await audit(actor["name"], f"hr_compensation_{action}", "hr_compensation_history", row_id,
                {"employee_id": row["employee_id"], "effective_from": row["effective_from"], "status": row["status"]},
                reason=body.reason, masked_fields=PII_MASK)
    return row


@router.post("/hr/compensation/{row_id}/approve")
async def approve_compensation(row_id: str, request: Request, body: Optional[HistoryDecision] = None) -> Dict[str, Any]:
    """Sahkan baris kompensasi: master ikut bila sudah berlaku; periode yang sudah dibayar → masukan rapel `pending`."""
    actor = await require_permission(request, "payroll", "approve")
    return await _decide_comp(actor, row_id, "approve", body, request)


@router.post("/hr/compensation/{row_id}/reject")
async def reject_compensation(row_id: str, request: Request, body: Optional[HistoryDecision] = None) -> Dict[str, Any]:
    actor = await require_permission(request, "payroll", "approve")
    return await _decide_comp(actor, row_id, "reject", body, request)


@router.post("/hr/compensation/{row_id}/cancel")
async def cancel_compensation(row_id: str, request: Request, body: Optional[HistoryDecision] = None) -> Dict[str, Any]:
    actor = await require_permission(request, "payroll", "approve")
    return await _decide_comp(actor, row_id, "cancel", body, request)


@router.post("/hr/employees/{employee_id}/assignments")
async def propose_assignment(employee_id: str, body: AssignmentCreate, request: Request) -> Dict[str, Any]:
    """Usulkan penugasan PT bertanggal berlaku → baris `pending`. PT tujuan harus dalam cakupan pelaku (403)."""
    actor = await require_permission(request, "hr", "update")
    ctx = await entity_ctx(request)
    emp = await _employee(employee_id, ctx)
    if body.entity_id and body.entity_id not in ctx.allowed_entity_ids:
        raise HTTPException(status_code=403, detail=PT_DILUAR)
    try:
        row = await _hc.propose_assignment(emp, body.model_dump(), actor)
    except ValueError as e:
        raise _http(e)
    await audit(actor["name"], "hr_assignment_proposed", "hr_employee_assignments", row["id"],
                {"employee_id": employee_id, "entity_id": row["entity_id"], "effective_from": row["effective_from"]},
                reason=row["reason"], scope_entity_id=emp.get("entity_id", ""))
    return row


async def _decide_asg(actor: Dict[str, Any], row_id: str, action: str, body: Optional[HistoryDecision],
                      request: Request) -> Dict[str, Any]:
    body = body or HistoryDecision()
    ctx = await entity_ctx(request)
    await _row_employee(_hc.ASG, row_id, ctx)
    try:
        row = await _hc.decide_assignment(row_id, action, actor, body.reason)
    except (ValueError, LookupError) as e:
        raise _http(e)
    await audit(actor["name"], f"hr_assignment_{action}", "hr_employee_assignments", row_id,
                {"employee_id": row["employee_id"], "entity_id": row["entity_id"],
                 "effective_from": row["effective_from"], "status": row["status"]}, reason=body.reason)
    return row


@router.post("/hr/assignments/{row_id}/approve")
async def approve_assignment(row_id: str, request: Request, body: Optional[HistoryDecision] = None) -> Dict[str, Any]:
    """Sahkan penugasan PT: master `entity_id` (+ departemen/jabatan) ikut bila sudah berlaku."""
    actor = await require_permission(request, "payroll", "approve")
    return await _decide_asg(actor, row_id, "approve", body, request)


@router.post("/hr/assignments/{row_id}/reject")
async def reject_assignment(row_id: str, request: Request, body: Optional[HistoryDecision] = None) -> Dict[str, Any]:
    actor = await require_permission(request, "payroll", "approve")
    return await _decide_asg(actor, row_id, "reject", body, request)
