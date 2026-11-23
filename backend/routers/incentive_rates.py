"""Incentive Rates router (EPIC4) — matriks rate insentif (entity × category).

Akses: izin `sales_force` (PR-T2; bawaan admin + manager). Respons ARRAY/OBJEK
telanjang (kontrak KN3). PATCH pakai GenericPatch (`{data:{...}}`).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from db import db
from dependencies import require_permission, audit
from core_utils import new_id, now_iso, safe_doc
from entity_scope import entity_ctx, resolve_list_scope_inherit
from services.commission_rules import periksa_nilai, rate_key

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


_NAMA_PAKSA = {"price_bands": "commission.price_bands", "price_source_rules": "commission.price_source_rules"}


async def _selesaikan(doc: Dict[str, Any]) -> None:
    """Lengkapi `doc` di tempat: validasi sasaran (artikel/varian/kategori), potret nama/kode/kategori, pita khusus,
    lalu `rate_key`. `HTTPException` 400 berpesan Indonesia bila tidak sah."""
    tpl = (doc.get("template_id") or "").strip()
    prd = (doc.get("product_id") or "").strip()
    if tpl and prd:
        raise HTTPException(status_code=400, detail="Pilih artikel atau varian, bukan keduanya.")
    doc["template_id"], doc["product_id"] = tpl, prd
    if prd:
        p = await db.products.find_one({"id": prd}, {"_id": 0, "id": 1, "name": 1, "sku": 1, "category": 1})
        if not p:
            raise HTTPException(status_code=400, detail="Varian tidak ditemukan.")
        doc.update({"category": p.get("category") or "", "target_name": p.get("name") or "",
                    "target_code": p.get("sku") or ""})
    elif tpl:
        t = await db.product_templates.find_one({"id": tpl}, {"_id": 0, "id": 1, "name": 1, "sku_prefix": 1, "category": 1})
        if not t:
            raise HTTPException(status_code=400, detail="Artikel tidak ditemukan.")
        doc.update({"category": t.get("category") or "", "target_name": t.get("name") or "",
                    "target_code": t.get("sku_prefix") or ""})
    else:
        if not (doc.get("category") or "").strip():
            raise HTTPException(status_code=400, detail="Kategori wajib diisi")
        doc.update({"target_name": "", "target_code": ""})
    for f, kunci in _NAMA_PAKSA.items():
        if doc.get(f) is not None:
            try:
                doc[f] = periksa_nilai(kunci, doc[f])
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
    doc["rate_key"] = rate_key(doc)


async def _cek_kembar(doc: Dict[str, Any], kecuali_id: str = "") -> None:
    q: Dict[str, Any] = {"entity_id": doc["entity_id"], "rate_key": doc["rate_key"]}
    if kecuali_id:
        q["id"] = {"$ne": kecuali_id}
    if await db.incentive_rates.find_one(q, {"_id": 0, "id": 1}):
        raise _kembar(doc)


def _kembar(doc: Dict[str, Any]) -> HTTPException:
    nama = doc.get("target_name") or doc.get("category") or ""
    return HTTPException(status_code=409, detail=f"Tarif untuk {nama} di PT ini sudah ada.")


def _out(doc: Dict[str, Any]) -> Dict[str, Any]:
    """KM-T4 (KM-07) — `incentive_unit` dokumen lama tidak dikirim (tidak dipakai mesin komisi)."""
    return {k: v for k, v in safe_doc(doc).items() if k != "incentive_unit"}


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
        for k in _NAMA_PAKSA:
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
