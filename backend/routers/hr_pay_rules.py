"""PY-T3 router — kalender libur PT, saldo awal pajak karyawan, dan dampak sumber lembur.

Koleksi: `hr_holidays` (hhol_, per PT; `services/hr_work_calendar.py`), `hr_tax_opening_balances` (htob_, per PT;
`services/hr_pay_rules.py`). Tanpa pasangan izin baru (02 §3.2): hari libur dilihat `hr.view`, diubah
`hr.manage_attendance` (pemelihara shift & lokasi absen); saldo awal pajak dilihat `hr.view` + `hr.view_pii` (nominal
pajak karyawan = data pribadi), diubah `hr.manage_payroll`; dampak lembur `hr.manage_payroll`.

PT selalu dari konteks (02 §3.4 N1): tulis memakai PT aktif (`assert_write_entity` → 409 saat "Semua PT"); dokumen ber-id
memakai PT dokumennya, diadu dengan cakupan pelaku.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from db import db
from dependencies import audit, require_permission
from entity_scope import assert_entity_access, assert_write_entity, entity_ctx, resolve_requested_entity
from schemas_hr_payroll import HolidayCreate, TaxOpeningInput
from services import hr_pay_rules as _pr
from services import hr_work_calendar as _wc

router = APIRouter(prefix="/api")

PII_MASK = ["tax_gross", "pension_deduction", "pph21_withheld"]


def _http(e: Exception) -> HTTPException:
    if isinstance(e, (_wc.HolidayConflict, _pr.TaxOpeningConflict)):
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, LookupError):
        return HTTPException(status_code=404, detail=str(e))
    return HTTPException(status_code=400, detail=str(e))


def _year(year: Optional[int]) -> int:
    from services import book_date
    return int(year or int(book_date.tanggal_buku()[:4]))


# ── kalender libur ───────────────────────────────────────────────────────────────────────────────────────────────────
@router.get("/hr/holidays")
async def list_holidays(request: Request, year: Optional[int] = Query(None)) -> Dict[str, Any]:
    """Hari libur PT aktif untuk satu tahun (bawaan: tahun berjalan). "Semua PT": semua PT dalam cakupan."""
    await require_permission(request, "hr", "view")
    ctx = await entity_ctx(request)
    y = _year(year)
    ids = list(ctx.allowed_entity_ids) if getattr(ctx, "view_all", False) else [ctx.active_entity_id]
    rows = []
    for eid in ids:
        rows += await _wc.list_holidays(eid, y)
    rows.sort(key=lambda r: (r.get("date", ""), r.get("entity_id", "")))
    return {"year": y, "entity_id": "all" if getattr(ctx, "view_all", False) else ctx.active_entity_id,
            "rows": rows, "total": len(rows),
            "kinds": [{"value": k, "label": _wc.KIND_LABEL[k]} for k in _wc.KINDS]}


@router.post("/hr/holidays")
async def create_holiday(body: HolidayCreate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "hr", "manage_attendance")
    ctx = await entity_ctx(request)
    eid = assert_write_entity(ctx, "menambah hari libur")
    try:
        doc = await _wc.add_holiday(eid, body.model_dump(), actor)
    except ValueError as e:
        raise _http(e)
    await audit(actor["name"], "hr_holiday_created", "hr_holidays", doc["id"],
                {"date": doc["date"], "name": doc["name"], "kind": doc["kind"]}, scope_entity_id=eid)
    return doc


@router.delete("/hr/holidays/{holiday_id}")
async def delete_holiday(holiday_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "hr", "manage_attendance")
    ctx = await entity_ctx(request)
    assert_write_entity(ctx, "menghapus hari libur")
    doc = await db.hr_holidays.find_one({"id": holiday_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Hari libur tidak ditemukan.")
    assert_entity_access(doc, "hr_holidays", ctx)
    try:
        out = await _wc.delete_holiday(doc["entity_id"], holiday_id)
    except LookupError as e:
        raise _http(e)
    await audit(actor["name"], "hr_holiday_deleted", "hr_holidays", holiday_id,
                {"date": out.get("date"), "name": out.get("name")}, scope_entity_id=doc["entity_id"])
    return {"deleted": True, "id": holiday_id, "date": out.get("date")}


# ── saldo awal pajak ─────────────────────────────────────────────────────────────────────────────────────────────────
async def _employee(employee_id: str, ctx) -> Dict[str, Any]:
    emp = await db.hr_employees.find_one({"id": employee_id}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
    assert_entity_access(emp, "hr_employees", ctx)
    return emp


@router.get("/hr/employees/{employee_id}/tax-opening")
async def get_tax_opening(employee_id: str, request: Request, year: Optional[int] = Query(None)) -> Any:
    """Saldo awal pajak karyawan di PT aktif (mode "Semua PT": PT karyawan) untuk satu tahun; `null` bila belum diisi."""
    await require_permission(request, "hr", "view")
    await require_permission(request, "hr", "view_pii")
    ctx = await entity_ctx(request)
    emp = await _employee(employee_id, ctx)
    eid = emp.get("entity_id", "") if getattr(ctx, "view_all", False) else ctx.active_entity_id
    return await _pr.tax_opening(eid, employee_id, _year(year))


@router.put("/hr/employees/{employee_id}/tax-opening")
async def put_tax_opening(employee_id: str, body: TaxOpeningInput, request: Request) -> Dict[str, Any]:
    """Isi/ubah saldo awal pajak (PT aktif). 409 bila slip masa pajak terakhir tahun itu sudah diposting/dibayar."""
    actor = await require_permission(request, "hr", "manage_payroll")
    ctx = await entity_ctx(request)
    eid = assert_write_entity(ctx, "mengisi saldo awal pajak")
    emp = await _employee(employee_id, ctx)
    try:
        doc = await _pr.set_tax_opening(eid, emp, body.model_dump(), actor)
    except ValueError as e:
        raise _http(e)
    await audit(actor["name"], "hr_tax_opening_saved", "hr_tax_opening_balances", doc["id"],
                {"employee_id": employee_id, "year": doc["year"], "months": doc["months"],
                 "tax_gross": doc["tax_gross"], "pension_deduction": doc["pension_deduction"],
                 "pph21_withheld": doc["pph21_withheld"]},
                reason=doc.get("note", ""), masked_fields=PII_MASK, scope_entity_id=eid)
    return doc


# ── dampak sumber lembur ─────────────────────────────────────────────────────────────────────────────────────────────
@router.get("/hr/payroll/overtime-impact")
async def overtime_impact(request: Request, period: str = Query(...),
                          entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Per karyawan: menit lembur absensi tanpa pengajuan pada periode itu dan nilainya (bahan memutuskan
    "Lembur dibayar berdasarkan"). PT = PT yang diminta (wajib dalam cakupan) atau PT aktif."""
    await require_permission(request, "hr", "manage_payroll")
    ctx = await entity_ctx(request)
    eid = resolve_requested_entity(ctx, entity_id)
    if not eid or eid == "all" or (getattr(ctx, "view_all", False) and not entity_id):
        raise HTTPException(status_code=400, detail="Pilih satu PT dulu untuk melihat dampak lembur.")
    from services import hr_payroll_service as pay
    try:
        return await pay.overtime_impact(eid, period)
    except ValueError as e:
        raise _http(e)
