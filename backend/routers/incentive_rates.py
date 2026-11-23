"""Incentive Rates router (EPIC4) — matriks rate insentif (entity × category).

Akses: izin `sales_force` (PR-T2; bawaan admin + manager). Respons ARRAY/OBJEK
telanjang (kontrak KN3). PATCH pakai GenericPatch (`{data:{...}}`).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, Request, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from db import db
from dependencies import require_permission, audit
from core_utils import new_id, now_iso, safe_doc
from entity_scope import entity_ctx, resolve_list_scope_inherit, resolve_write_entity
from services import commission_rate_service as crs
from services.commission_rate_service import cek_kembar, kembar, selesaikan

router = APIRouter(prefix="/api")


class RatePayload(BaseModel):
    """KM-T4 (KM-07) — `incentive_unit` tidak lagi diterima: mesin komisi memakai jumlah satuan dasar baris
    (`sales_force_service`, `base_qty`). Isian tambahan di permintaan diabaikan (Pydantic bawaan)."""
    entity_id: str = "all"
    category: str = ""                        # wajib hanya untuk baris kategori; baris artikel/varian dipotret dari katalog
    template_id: str = ""                     # KA-2 — tarif per artikel (`product_templates.id`)
    product_id: str = ""                      # KA-2 — pengecualian per varian (`products.id`)
    price_bands: Optional[List[Dict[str, Any]]] = None          # None = ikut pita PT (`commission.price_bands`)
    price_source_rules: Optional[List[Dict[str, Any]]] = None   # None = ikut aturan sumber harga PT
    per_unit_amount: float = 0.0
    discount_threshold_type: str = "pct"      # pct | rp_per_unit
    discount_threshold: float = 10.0
    discount_mechanic: str = "tier_factor"    # tier_factor | potong_rp | cutoff
    discount_factor: float = 0.5
    discount_potong_rp: float = 0.0
    margin_cap_pct: float = 50.0
    status: str = "active"


class GenericPatch(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)


_FIELDS = ["entity_id", "category", "template_id", "product_id", "price_bands", "price_source_rules", "per_unit_amount",
           "discount_threshold_type", "discount_threshold", "discount_mechanic",
           "discount_factor", "discount_potong_rp", "margin_cap_pct", "status"]


# KA-8 — validasi sasaran & deteksi kembar satu salinan di `commission_rate_service` (dipakai juga ubah banyak/Excel).
_selesaikan, _cek_kembar, _kembar = selesaikan, cek_kembar, kembar


def _out(doc: Dict[str, Any]) -> Dict[str, Any]:
    """KM-T4 (KM-07) — `incentive_unit` dokumen lama tidak dikirim (tidak dipakai mesin komisi)."""
    return {k: v for k, v in safe_doc(doc).items() if k != "incentive_unit"}


class DraftRate(BaseModel):
    template_id: str = ""
    product_id: str = ""
    category: str = ""
    per_unit_amount: float
    margin_cap_pct: Optional[float] = None


class BulkPayload(BaseModel):
    entity_id: str = ""
    template_ids: List[str] = Field(default_factory=list)
    per_unit_amount: float
    margin_cap_pct: Optional[float] = None
    reason: str = Field("", max_length=500)


class ImportRow(BaseModel):
    template_id: str = ""
    product_id: str = ""
    per_unit_amount: float
    margin_cap_pct: Optional[float] = None
    baris: Optional[int] = None               # nomor baris di Excel (dari pratinjau) — untuk pesan galat


class ImportApplyPayload(BaseModel):
    entity_id: str = ""
    rows: List[ImportRow] = Field(default_factory=list)
    reason: str = Field("", max_length=500)


class SimulatePayload(BaseModel):
    entity_id: str = ""
    sales_id: str = ""
    period: str = ""
    draft_rates: List[DraftRate] = Field(default_factory=list)


async def _pt_tunggal(request: Request, entity_id: Optional[str]) -> str:
    """Layar tarif bekerja per satu PT: kosong → PT aktif; "all"/di luar penugasan → 400/403."""
    return resolve_write_entity(await entity_ctx(request), entity_id)


@router.get("/incentive-rates/categories")
async def list_categories(request: Request, entity_id: Optional[str] = None) -> Dict[str, Any]:
    await require_permission(request, "sales_force", "view")
    return {"items": await crs.daftar_kategori(await _pt_tunggal(request, entity_id))}


@router.get("/incentive-rates/articles")
async def list_articles(request: Request, entity_id: Optional[str] = None, search: str = "", category: str = "",
                        page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
    await require_permission(request, "sales_force", "view")
    return await crs.daftar_artikel(await _pt_tunggal(request, entity_id), search=search, category=category,
                                    page=page, page_size=page_size)


@router.get("/incentive-rates/articles/{template_id}/variants")
async def list_variants(template_id: str, request: Request, entity_id: Optional[str] = None) -> Dict[str, Any]:
    await require_permission(request, "sales_force", "view")
    return {"items": await crs.daftar_varian(await _pt_tunggal(request, entity_id), template_id)}


@router.post("/incentive-rates/bulk")
async def bulk_rates(payload: BulkPayload, request: Request) -> Dict[str, int]:
    """Set tarif beberapa artikel sekaligus (buat bila belum ada, ubah bila sudah). Alasan tercatat di Jejak Audit."""
    actor = await require_permission(request, "sales_force", "update")
    ent = await _pt_tunggal(request, payload.entity_id)
    if not payload.template_ids:
        raise HTTPException(status_code=400, detail="Pilih minimal satu artikel.")
    sasaran = [{"template_id": t, "per_unit_amount": payload.per_unit_amount, "margin_cap_pct": payload.margin_cap_pct}
               for t in payload.template_ids]
    return await crs.terapkan_tarif(ent, sasaran, bawaan=crs.bawaan_tarif(), alasan=payload.reason.strip(),
                                    aktor=actor["name"])


@router.get("/incentive-rates/export")
async def export_rates(request: Request, entity_id: Optional[str] = None) -> Response:
    await require_permission(request, "sales_force", "view")
    ent = await _pt_tunggal(request, entity_id)
    isi = await crs.ekspor_xlsx(ent)
    return Response(content=isi, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="tarif-komisi-artikel-{ent}.xlsx"'})


@router.post("/incentive-rates/import/preview")
async def import_preview(request: Request, file: UploadFile = File(...), entity_id: str = Form("")) -> Dict[str, Any]:
    await require_permission(request, "sales_force", "update")
    ent = await _pt_tunggal(request, entity_id)
    isi = await file.read(crs.BATAS_BERKAS + 1)
    return {"rows": await crs.pratinjau_impor(ent, isi)}


@router.post("/incentive-rates/import/apply")
async def import_apply(payload: ImportApplyPayload, request: Request) -> Dict[str, int]:
    actor = await require_permission(request, "sales_force", "update")
    ent = await _pt_tunggal(request, payload.entity_id)
    if not payload.rows:
        raise HTTPException(status_code=400, detail="Tidak ada baris untuk diterapkan.")
    return await crs.terapkan_tarif(ent, [r.model_dump() for r in payload.rows], bawaan=crs.bawaan_tarif(),
                                    alasan=payload.reason.strip(), aktor=actor["name"])


@router.post("/incentive-rates/simulate")
async def simulate_rates(payload: SimulatePayload, request: Request) -> Dict[str, Any]:
    """Coba dulu: komisi sales pada satu periode dengan aturan sekarang vs aturan sekarang + tarif draf. Tidak menulis."""
    actor = await require_permission(request, "sales_force", "view")
    ent = await _pt_tunggal(request, payload.entity_id)
    from services.sales_force_service import boleh_lihat_komisi_sales
    if payload.sales_id and not await boleh_lihat_komisi_sales(actor, payload.sales_id):
        raise HTTPException(status_code=403, detail="Anda tidak berwenang melihat komisi sales ini.")
    if not payload.sales_id or not payload.period:
        raise HTTPException(status_code=400, detail="Pilih sales dan periode.")
    from services.sales_force_service import simulate_commission
    return await simulate_commission(payload.sales_id, payload.period, ent, [d.model_dump() for d in payload.draft_rates])


@router.get("/incentive-rates")
async def list_rates(request: Request, entity_id: Optional[str] = None) -> List[Dict[str, Any]]:
    await require_permission(request, "sales_force", "view")
    # FASE E-0 (L17) — ter-scope entitas, tetapi tarif bawaan grup (`entity_id="all"`)
    # tetap terlihat sebagai WARISAN (label asal ditampilkan UI di FASE E-4).
    ctx = await entity_ctx(request)
    query: Dict[str, Any] = resolve_list_scope_inherit("incentive_rates", {}, ctx, entity_id)
    rows = await db.incentive_rates.find(query, {"_id": 0}).to_list(1000)
    rows.sort(key=lambda r: (r.get("entity_id", ""), r.get("category", "")))
    return [_out(r) for r in rows]


@router.post("/incentive-rates")
async def create_rate(payload: RatePayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "sales_force", "update")
    doc = payload.model_dump()
    await _selesaikan(doc)
    await _cek_kembar(doc)
    doc.update({"id": new_id("irate"), "created_at": now_iso(), "updated_at": now_iso()})
    try:
        await db.incentive_rates.insert_one(doc)
    except DuplicateKeyError:
        raise _kembar(doc) from None
    await audit(actor["name"], "incentive_rate_created", "incentive_rate", doc["id"], doc)
    return _out(doc)


@router.patch("/incentive-rates/{rate_id}")
async def update_rate(rate_id: str, payload: GenericPatch, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "sales_force", "update")
    data = {k: v for k, v in payload.data.items() if k in _FIELDS}
    if not data:
        raise HTTPException(status_code=400, detail="Tidak ada field valid untuk diupdate")
    lama = await db.incentive_rates.find_one({"id": rate_id}, {"_id": 0})
    if not lama:
        raise HTTPException(status_code=404, detail="Rate tidak ditemukan")
    if any(k in data for k in ("entity_id", "category", "template_id", "product_id", "price_bands", "price_source_rules")):
        gabung = {**lama, **data}
        await _selesaikan(gabung)
        await _cek_kembar(gabung, rate_id)
        for k in ("category", "template_id", "product_id", "target_name", "target_code", "rate_key"):
            data[k] = gabung[k]
        for k in ("price_bands", "price_source_rules"):
            if k in data:
                data[k] = gabung[k]
    data["updated_at"] = now_iso()
    try:
        updated = await db.incentive_rates.find_one_and_update(
            {"id": rate_id}, {"$set": data}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    except DuplicateKeyError:
        raise _kembar({**lama, **data}) from None
    if not updated:
        raise HTTPException(status_code=404, detail="Rate tidak ditemukan")
    await audit(actor["name"], "incentive_rate_updated", "incentive_rate", rate_id, updated)
    return _out(updated)


@router.delete("/incentive-rates/{rate_id}")
async def delete_rate(rate_id: str, request: Request,
                      reason: str = Query("", max_length=500)) -> Dict[str, Any]:
    # FASE P5 — `reason` (opsional di API, WAJIB di layar): tarif insentif menentukan
    # komisi yang dibayar ke sales, jadi penghapusannya berdampak uang dan alasannya
    # ikut tersimpan di Jejak Audit.
    actor = await require_permission(request, "sales_force", "delete")
    existing = await db.incentive_rates.find_one({"id": rate_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Rate tidak ditemukan")
    await db.incentive_rates.delete_one({"id": rate_id})
    await audit(actor["name"], "incentive_rate_deleted", "incentive_rate", rate_id,
                {**existing, "reason": (reason or "").strip()})
    return {"id": rate_id, "deleted": True}
