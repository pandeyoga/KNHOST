"""R6.2 — Fixed Assets & Depresiasi router. Akses: permission "fixed_asset" (admin/manager).

Respons OBJEK/ARRAY telanjang (konsisten dgn bank.py / bank_reconciliation.py).
Penyusutan straight-line + disposal gain/loss (self-balancing JE). GL-safe & idempotent.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, Query, HTTPException
from pydantic import BaseModel

from dependencies import require_permission, audit
from entity_scope import entity_ctx, resolve_scope_ids, guard_doc, resolve_requested_entity
from schemas_interco_loan import FixedAssetTransferIn, FixedAssetTransferSettleIn
from services import fixed_asset_service as svc
from services import fixed_asset_transfer_service as tsvc   # PK-23 — pindah antar-PT & pembayarannya
from services import gl_service

router = APIRouter(prefix="/api")


class FixedAssetIn(BaseModel):
    name: str
    category: str = "Peralatan & Mesin"
    acquisition_cost: float = 0
    acquisition_date: str = ""
    useful_life_months: int = 0
    salvage_value: float = 0
    entity_id: Optional[str] = ""
    gl_account_asset: Optional[str] = ""
    funding_account: Optional[str] = ""   # PK-23 — diabaikan: akun lawan diturunkan dari `funding_source`
    funding_source: Optional[str] = ""    # PK-23 (FY-03) — wajib: kas · hutang · saldo_awal
    account_id: Optional[str] = ""        # PK-23 — rekening kas/bank untuk sumber `kas`
    notes: Optional[str] = ""


class FixedAssetPatch(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None
    gl_account_asset: Optional[str] = None
    acquisition_cost: Optional[float] = None
    useful_life_months: Optional[int] = None
    salvage_value: Optional[float] = None
    acquisition_date: Optional[str] = None


class RunDepreciationIn(BaseModel):
    period: str                       # YYYY-MM
    asset_id: Optional[str] = ""
    entity_id: Optional[str] = ""


class DisposeIn(BaseModel):
    proceeds: float = 0
    date: Optional[str] = ""
    note: Optional[str] = ""


def _scope(ctx, entity_id: Optional[str]) -> Dict[str, Any]:
    ids = resolve_scope_ids(ctx, entity_id)
    return {"entity_id": {"$in": ids}}


def _galat(e: ValueError) -> HTTPException:
    """PK-23 — `AssetError` membawa kodenya sendiri (409/400/403); ValueError lain tetap 400."""
    return HTTPException(status_code=getattr(e, "status_code", 400), detail=str(e))


@router.get("/fixed-assets")
async def list_fixed_assets(request: Request, entity_id: str = Query(None)) -> List[Dict[str, Any]]:
    await require_permission(request, "fixed_asset", "view")
    ctx = await entity_ctx(request)
    return await svc.list_assets(scope=_scope(ctx, entity_id))


@router.get("/fixed-assets/meta")
async def fixed_asset_meta(request: Request, entity_id: str = Query(None)) -> Dict[str, Any]:
    """Kategori + akun GL aset yang bisa dipilih (postable di bawah 1-2000, kecuali akumulasi) + PK-23: pilihan sumber
    dana untuk PT itu (pilihan yang akun lawannya belum dipetakan tampil mati beralasan)."""
    await require_permission(request, "fixed_asset", "view")
    ctx = await entity_ctx(request)
    eid = entity_id if entity_id and entity_id != "all" else (
        ctx.active_entity_id if getattr(ctx, "active_entity_id", "") != "all" else None)
    return {
        "categories": svc.ASSET_CATEGORIES,
        "category_account": svc.CATEGORY_ACCOUNT,
        "asset_accounts": await svc.asset_accounts(eid),
        "acc_dep_account": gl_service.ACC_FA_ACCUM_DEP,
        "dep_expense_account": gl_service.ACC_DEP_EXPENSE,
        "funding_sources": await svc.funding_options(eid),
    }


@router.get("/fixed-assets/summary")
async def fixed_asset_summary(request: Request, entity_id: str = Query(None)) -> Dict[str, Any]:
    await require_permission(request, "fixed_asset", "view")
    ctx = await entity_ctx(request)
    return await svc.summary(scope=_scope(ctx, entity_id))


@router.post("/fixed-assets")
async def create_fixed_asset(payload: FixedAssetIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "fixed_asset", "create")
    # PK-23 (N1) — PT dari konteks pengguna (`resolve_requested_entity`: isian PT wajib ∈ PT yang ditugaskan → 403);
    # id aset dari kunci idempotensi bila dikirim (kirim ulang = aset yang sama, diteruskan).
    ent = resolve_requested_entity(await entity_ctx(request), payload.entity_id)
    try:
        asset = await svc.create_asset(payload.model_dump(), actor, entity_id=ent,
                                       idem_key=(request.headers.get("Idempotency-Key") or "").strip()[:120])
    except ValueError as e:
        raise _galat(e)
    await audit(actor.get("name", ""), "fixed_asset_created", "fixed_asset", asset["id"],
                {"number": asset["number"], "cost": asset["acquisition_cost"]})
    return asset


@router.post("/fixed-assets/run-depreciation")
async def run_depreciation(payload: RunDepreciationIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "fixed_asset", "run")
    ctx = await entity_ctx(request)
    try:
        res = await svc.run_depreciation(payload.period, actor,
                                         asset_id=payload.asset_id or None,
                                         scope=_scope(ctx, payload.entity_id))
    except ValueError as e:
        raise _galat(e)
    await audit(actor.get("name", ""), "fixed_asset_depreciation_run", "fixed_asset",
                payload.asset_id or "batch", {"period": res["period"], "posted": res["posted"],
                                              "total": res["total_amount"]})
    return res


@router.get("/fixed-assets/{asset_id}")
async def get_fixed_asset(asset_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "fixed_asset", "view")
    a = await svc.get_asset(asset_id)
    await guard_doc(request, "fin_fixed_assets", a, not_found="Aset tidak ditemukan")  # KN-B32
    return a


@router.patch("/fixed-assets/{asset_id}")
async def patch_fixed_asset(asset_id: str, payload: FixedAssetPatch, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "fixed_asset", "update")
    await guard_doc(request, "fin_fixed_assets", await svc.get_asset(asset_id), not_found="Aset tidak ditemukan")  # KN-B32
    try:
        a = await svc.update_asset(asset_id, payload.model_dump(exclude_none=True))
    except ValueError as e:
        raise _galat(e)
    if a is None:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await audit(actor.get("name", ""), "fixed_asset_updated", "fixed_asset", asset_id, {})
    return a


@router.post("/fixed-assets/{asset_id}/dispose")
async def dispose_fixed_asset(asset_id: str, payload: DisposeIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "fixed_asset", "dispose")
    await guard_doc(request, "fin_fixed_assets", await svc.get_asset(asset_id), not_found="Aset tidak ditemukan")  # KN-B32
    try:
        a = await svc.dispose_asset(asset_id, payload.proceeds, actor,
                                    date=payload.date or "", note=payload.note or "")
    except ValueError as e:
        raise _galat(e)
    await audit(actor.get("name", ""), "fixed_asset_disposed", "fixed_asset", asset_id,
                {"proceeds": payload.proceeds, "gain_loss": (a.get("disposal") or {}).get("gain_loss")})
    return a


# ── FASE E-7 (E7g) — PINDAH ASET TETAP ANTAR-PT ──────────────────────────────
@router.post("/fixed-assets/{asset_id}/transfer")
async def transfer_fixed_asset(asset_id: str, payload: FixedAssetTransferIn,
                               request: Request) -> Dict[str, Any]:
    """Pindahkan aset ke badan usaha lain di dalam grup (nilai buku + masa manfaat sisa).

    Bukan sekadar mengganti `entity_id`: aset lahir kembali di PT penerima, akumulasi
    penyusutan di PT pengirim dihapus lewat jurnal, dan laba pindah (bila harga di atas
    nilai buku) ikut dieliminasi di konsolidasi grup — karena pembelinya PT sendiri.
    """
    actor = await require_permission(request, "fixed_asset", "update")
    ctx = await entity_ctx(request)
    # KN-B32 — transfer memvalidasi entitas ASAL juga, bukan hanya tujuan.
    await guard_doc(request, "fin_fixed_assets", await svc.get_asset(asset_id), not_found="Aset tidak ditemukan")
    if payload.to_entity_id not in ctx.allowed_entity_ids:
        raise HTTPException(
            status_code=403,
            detail=("Anda tidak berwenang di badan usaha penerima — minta admin/manajer "
                    "yang ditugaskan di sana yang memindahkan asetnya."))
    try:
        res = await tsvc.transfer_to_entity(asset_id, payload.model_dump(), actor)
    except ValueError as e:
        raise _galat(e)
    await audit(actor.get("name", ""), "fixed_asset_transferred", "fixed_asset", asset_id,
                {"to_entity_id": payload.to_entity_id, "price": res["price"],
                 "book_value": res["book_value"], "gain": res["gain"],
                 "new_asset": res["new_asset"]["number"]})
    return res


@router.post("/fixed-assets/{asset_id}/transfer/settle")
async def settle_fixed_asset_transfer(asset_id: str, payload: FixedAssetTransferSettleIn,
                                      request: Request) -> Dict[str, Any]:
    """Catat pembayaran utang antar-PT atas aset yang dipindah (uang benar-benar pindah).

    PK-23 (FY-04) — pelaku wajib berwenang di PT PEMBAYAR (PT penerima aset); selain itu 403."""
    actor = await require_permission(request, "fixed_asset", "update")
    ctx = await entity_ctx(request)
    try:
        res = await tsvc.settle_transfer(asset_id, actor, payload.note or "",
                                         allowed_entity_ids=list(ctx.allowed_entity_ids))
    except ValueError as e:
        raise _galat(e)
    await audit(actor.get("name", ""), "fixed_asset_transfer_settled", "fixed_asset",
                asset_id, res)
    return res
