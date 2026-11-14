"""Approval Rules Router — CRUD matriks ambang persetujuan (`approval_rules`).

Skema TUNGGAL = skema yang dibaca mesin (`config_service.evaluate_approval`):
{doc_type, entity_id, min_amount, max_amount, required_role, sort, active, is_percent}.

KP-T3 — hanya jenis dokumen yang dinilai mesin (`discount` dipensiunkan) dan hanya peran yang ada di registry;
`GET /approval-rules/effective` menampilkan jenjang dari baris lama ini per PT.

KP-T4 — POST/PATCH/DELETE dimatikan (410, pesan menunjuk layar baru). Siapa menyetujui apa kini SATU tabel per jenis
dokumen (`routers/approval_policies.py`, koleksi `approval_policies`); baris di sini hanya terbaca (riwayat, Master
per PT) dan membentuk aturan bawaan SO/PO/PR selama tabel kebijakan belum punya baris.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from db import db
from dependencies import require_permission
from entity_scope import assert_entity_access, entity_ctx, resolve_requested_entity, resolve_scope_ids
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
# KP-T4 — jalur tulis lama dimatikan (D8): siapa menyetujui apa kini satu tabel per jenis dokumen
# (`PUT /api/approval-policies/{doc_kind}`). Baris `approval_rules` tetap terbaca (riwayat, Master per PT) dan hanya
# membentuk aturan bawaan selama tabel kebijakan belum punya baris.
PESAN_PINDAH = ("Aturan Persetujuan kini diatur per jenis dokumen di Pengaturan › Persetujuan › Aturan Persetujuan "
                "(siapa menyetujui apa, mulai nominal berapa).")


def _pindah() -> HTTPException:
    return HTTPException(status_code=410, detail=PESAN_PINDAH)


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


def _with_label(rule: Dict[str, Any]) -> Dict[str, Any]:
    return {**rule, **role_view(rule.get("required_role") or "")}


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


@router.post("/approval-rules")
async def create_approval_rule(payload: ApprovalRuleCreate, request: Request) -> Dict[str, Any]:
    """KP-T4 — dimatikan (410): aturan baru dibuat di `PUT /api/approval-policies/{doc_kind}`."""
    await require_permission(request, "settings", "manage", PESAN_UBAH)
    raise _pindah()


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
    """KP-T4 — dimatikan (410): ubah aturan di `PUT /api/approval-policies/{doc_kind}`."""
    await require_permission(request, "settings", "manage", PESAN_UBAH)
    raise _pindah()


@router.delete("/approval-rules/{rule_id}")
async def delete_approval_rule(rule_id: str, request: Request) -> Dict[str, str]:
    """KP-T4 — dimatikan (410): hapus aturan khusus PT di `DELETE /api/approval-policies/{doc_kind}`."""
    await require_permission(request, "settings", "manage", PESAN_UBAH)
    raise _pindah()
