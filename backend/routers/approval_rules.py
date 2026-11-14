"""Approval Rules Router — CRUD matriks ambang persetujuan (`approval_rules`).

Skema TUNGGAL = skema yang dibaca mesin (`config_service.evaluate_approval`):
{doc_type, entity_id, min_amount, max_amount, required_role, sort, active, is_percent}.

KP-T3 — hanya jenis dokumen yang dinilai mesin (`discount` dipensiunkan) dan hanya peran yang ada di registry;
`GET /approval-rules/effective` menampilkan jenjang yang sungguh berlaku per PT (fungsi pemilih yang sama dengan
mesin), dan jawaban simpan memuat `warnings` (celah, tumpang tindih, lebih longgar dari grup, peran tak dikenal).
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from db import db
from dependencies import require_permission, current_user
from entity_scope import assert_entity_access, entity_ctx, resolve_requested_entity, resolve_scope_ids
from role_registry import is_role
from services import approval_service
from services.config_service import APPROVAL_DOC_TYPES, effective_tiers, role_view

router = APIRouter(prefix="/api")

# KP-T3 — jenis dokumen = yang dinilai mesin; peran = registry peran (`VALID_ROLES` statis dihapus: `owner` tidak ada
# di registry dan selama ini diperlakukan sama dengan Manajer).
VALID_DOC_TYPES = list(APPROVAL_DOC_TYPES)
_MODUL = "'Pengaturan, Pengguna & Hak Akses'"
PESAN_LIHAT = f"Anda belum punya akses untuk melihat aturan persetujuan. Minta Admin menambahkan akses {_MODUL}."
PESAN_UBAH = f"Anda belum punya akses untuk mengubah aturan persetujuan. Minta Admin menambahkan akses {_MODUL}."
PESAN_DISKON = "Jenis aturan 'Diskon (%)' sudah tidak dipakai. Potongan harga diatur lewat Harga Khusus."
PESAN_JENIS = f"Jenis dokumen tidak dikenal. Pilihan: {', '.join(APPROVAL_DOC_TYPES.values())}."
PESAN_PERAN = "Peran penyetuju tidak dikenal. Pilih peran yang ada di Peran & Hak Akses."


class ApprovalRuleCreate(BaseModel):
    doc_type: str = Field(..., description="Jenis dokumen (sales_order, purchase_order, purchase_requisition)")
    min_amount: float = Field(0, ge=0, description="Batas bawah rentang (inklusif)")
    max_amount: Optional[float] = Field(None, description="Batas atas rentang (eksklusif); kosong = tanpa batas")
    required_role: str = Field("", description="Peran penyetuju; '' = tanpa persetujuan (lolos otomatis)")
    sort: int = Field(default=1, ge=1, description="Urutan evaluasi (kecil = lebih dulu)")
    active: bool = Field(default=True)
    description: str = Field(default="")
    entity_id: str = Field(default="all", description="'all' = berlaku semua entitas (warisan grup)")


class ApprovalRuleUpdate(BaseModel):
    doc_type: Optional[str] = None
    min_amount: Optional[float] = Field(None, ge=0)
    max_amount: Optional[float] = None
    required_role: Optional[str] = None
    sort: Optional[int] = Field(None, ge=1)
    active: Optional[bool] = None
    description: Optional[str] = None
    entity_id: Optional[str] = None


def _validate_doc_type(doc_type: Optional[str]) -> None:
    if doc_type is None or doc_type in VALID_DOC_TYPES:
        return
    raise HTTPException(status_code=400, detail=PESAN_DISKON if doc_type == "discount" else PESAN_JENIS)


def _validate(doc_type: Optional[str], required_role: Optional[str],
              min_amount: Optional[float], max_amount: Optional[float]):
    _validate_doc_type(doc_type)
    if required_role is not None and required_role != "" and not is_role(required_role):
        raise HTTPException(status_code=400, detail=PESAN_PERAN)
    if max_amount is not None and min_amount is not None and max_amount <= min_amount:
        raise HTTPException(status_code=400, detail="Nilai maksimal harus lebih besar dari nilai minimal.")


def _with_label(rule: Dict[str, Any]) -> Dict[str, Any]:
    return {**rule, **role_view(rule.get("required_role") or "")}


async def _with_warnings(rule: Dict[str, Any]) -> Dict[str, Any]:
    """KP-T3 — peringatan untuk pasangan (PT, jenis dokumen) aturan yang baru disimpan; tidak menolak simpan."""
    out = _with_label(rule)
    if rule.get("doc_type") in VALID_DOC_TYPES:
        out["warnings"] = (await effective_tiers(rule["doc_type"], rule.get("entity_id") or "all"))["warnings"]
    else:
        out["warnings"] = []
    return out


@router.get("/approval-rules")
async def list_approval_rules(
    request: Request,
    doc_type: Optional[str] = None,
    active: Optional[bool] = None
) -> List[Dict[str, Any]]:
    await require_permission(request, "settings", "view", PESAN_LIHAT)
    ctx = await entity_ctx(request)
    rows = await approval_service.get_approval_rules(
        doc_type=doc_type, active=active,
        entity_ids=resolve_scope_ids(ctx),
    )
    # KP-T3 — aturan jenis yang tidak dinilai mesin (`discount` lama) tidak ditampilkan; label peran dari registry.
    return [_with_label(r) for r in rows if r.get("doc_type") in VALID_DOC_TYPES]


@router.get("/approval-rules/effective")
async def effective_approval_tiers(request: Request, entity_id: str = "",
                                   doc_type: Optional[str] = None) -> Dict[str, Any]:
    """KP-T3 — jenjang persetujuan yang SUNGGUH berlaku untuk satu PT (per jenis dokumen), dengan peringatan."""
    await require_permission(request, "settings", "view", PESAN_LIHAT)
    ctx = await entity_ctx(request)
    if not (entity_id or "").strip() or entity_id.strip() == "all":
        raise HTTPException(status_code=400, detail="Pilih PT untuk melihat jenjang yang berlaku.")
    ent = resolve_requested_entity(ctx, entity_id)
    _validate_doc_type(doc_type)
    doc = await db.business_entities.find_one(
        {"id": ent}, {"_id": 0, "legal_name": 1, "short_name": 1, "name": 1}) or {}
    kinds = [doc_type] if doc_type else VALID_DOC_TYPES
    name = doc.get("legal_name") or doc.get("name") or doc.get("short_name") or ent
    return {"entity_id": ent, "entity_name": name,
            "doc_types": [await effective_tiers(k, ent) for k in kinds]}


def _assert_rule_entity_allowed(entity_id: Optional[str], ctx) -> None:
    """Aturan ber-cakupan entitas hanya boleh menunjuk entitas dalam wewenang pengguna."""
    if entity_id in (None, "", "all"):
        return
    if entity_id not in ctx.allowed_entity_ids:
        raise HTTPException(status_code=403, detail="Tidak berwenang atas entitas ini")


@router.post("/approval-rules")
async def create_approval_rule(payload: ApprovalRuleCreate, request: Request) -> Dict[str, Any]:
    await require_permission(request, "settings", "manage", PESAN_UBAH)
    user = await current_user(request)
    _validate(payload.doc_type, payload.required_role, payload.min_amount, payload.max_amount)
    _assert_rule_entity_allowed(payload.entity_id, await entity_ctx(request))
    rule = await approval_service.create_approval_rule(
        doc_type=payload.doc_type,
        min_amount=payload.min_amount,
        max_amount=payload.max_amount,
        required_role=payload.required_role,
        sort=payload.sort,
        active=payload.active,
        description=payload.description,
        created_by=user["email"],
        entity_id=payload.entity_id or "all",
        is_percent=False,   # KP-T3 — satu-satunya jenis persen (`discount`) dipensiunkan
    )
    return await _with_warnings(rule)


@router.get("/approval-rules/{rule_id}")
async def get_approval_rule(rule_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "settings", "view", PESAN_LIHAT)
    rule = await db.approval_rules.find_one({"id": rule_id}, {"_id": 0})
    if not rule:
        raise HTTPException(status_code=404, detail="Aturan persetujuan tidak ditemukan.")
    if rule.get("entity_id") not in (None, "", "all"):
        assert_entity_access(rule, "approval_rules", await entity_ctx(request))
    return _with_label(rule)


@router.patch("/approval-rules/{rule_id}")
async def update_approval_rule(rule_id: str, payload: ApprovalRuleUpdate, request: Request) -> Dict[str, Any]:
    await require_permission(request, "settings", "manage", PESAN_UBAH)
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="Tidak ada field untuk diubah")
    existing = await db.approval_rules.find_one({"id": rule_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Aturan persetujuan tidak ditemukan.")
    # Nilai efektif pasca-PATCH: field yang dikirim menang, sisanya dari dokumen lama.
    merged_min = updates.get("min_amount", existing.get("min_amount", 0))
    merged_max = updates["max_amount"] if "max_amount" in updates else existing.get("max_amount")
    # KP-T3 — jenis dokumen hasil gabungan diperiksa: aturan `discount` lama tidak bisa dihidupkan lagi.
    _validate(updates.get("doc_type", existing.get("doc_type")), updates.get("required_role"), merged_min, merged_max)
    if "entity_id" in updates:
        _assert_rule_entity_allowed(updates["entity_id"], await entity_ctx(request))
        updates["entity_id"] = updates["entity_id"] or "all"
    if "doc_type" in updates:
        updates["is_percent"] = False
    try:
        rule = await approval_service.update_approval_rule(rule_id, updates)
    except ValueError:
        raise HTTPException(status_code=404, detail="Aturan persetujuan tidak ditemukan.")
    return await _with_warnings(rule)


@router.delete("/approval-rules/{rule_id}")
async def delete_approval_rule(rule_id: str, request: Request) -> Dict[str, str]:
    """Soft delete (set active=False) — mesin approval berhenti membaca aturan ini."""
    await require_permission(request, "settings", "manage", PESAN_UBAH)
    success = await approval_service.delete_approval_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Aturan persetujuan tidak ditemukan.")
    return {"message": "Aturan persetujuan dinonaktifkan"}
