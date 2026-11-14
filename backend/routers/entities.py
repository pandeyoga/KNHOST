"""Router BADAN USAHA (fondasi multi-entitas — F0 + FASE E-1).

Master badan usaha legal grup Kain Nusantara (PT/CV/Perorangan/UD/Koperasi/
Yayasan). `entity_id` menjadi lapisan scope untuk data transaksi. Master katalog
tetap SHARED lintas badan usaha (lihat KN_14 §7).

FASE E-1 menambahkan:
  * E1.2 satu jalur validasi & keunikan (POST dan PATCH memakai
    `entity_provisioning_service.validate_entity_input`)
  * E1.3 kunci kode dokumen bila sudah menerbitkan dokumen
  * E1.4 invalidasi cache kode entitas saat dibuat/diubah
  * E1.5 filter status (default: hanya aktif untuk pemilih entitas)
  * E1.6 pagar deaktivasi + arsip + aktivasi ulang
  * E1.8 bentuk data seragam dengan `/auth/context`
  * E1.9 daftar kesiapan badan usaha

KP-T1 — jawaban PT memuat tahun buku & mata uang dari registry (`lifecycle.profile_settings`; `currency` =
`base_currency` supaya bentuk daftar tetap), dan tindakan "Ubah status PKP" bertanggal + beralasan
(`GET …/tax-status/preview`, `POST …/tax-status`, `DELETE …/tax-status/pending`).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pymongo import ReturnDocument

from db import db
from dependencies import has_permission, require_permission, audit, current_user
from core_utils import invalidate_entity_code, now_iso, safe_doc
from schemas import BusinessEntityCreate, EntityArchiveBody, EntityTaxStatusIn, GenericPatch
from services import entity_provisioning_service as provisioning
from services import entity_lifecycle_service as lifecycle
from services import entity_readiness_service as readiness_svc
from entity_scope import entity_ctx, resolve_list_scope_inherit

router = APIRouter(prefix="/api")

#: PR-T3 (S2) — kunci baris `GET /api/entities` bagi peran TANPA `entity.view`: pemilih PT dan nama PT lawan di banyak
#: layar. 11 kunci spesifikasi + `is_group` (pemilih PT Tutup Buku/Buka Periode/Suspense/Eliminasi), `write_locked` dan
#: `city` (pemilih badan usaha di kepala aplikasi: saringan & pencarian). Jumlah akun dan kesiapan tidak dikirim.
REFERENCE_FIELDS = ("id", "code", "name", "short_name", "legal_name", "type", "is_pkp", "currency", "status",
                    "doc_prefix", "logo_url", "is_group", "write_locked", "city")
_S5_DITOLAK = ("Anda belum punya akses untuk melihat rincian badan usaha. Minta Admin menambahkan akses "
               "'Pengaturan, Pengguna & Hak Akses'.")
_PKP_DITOLAK = ("Anda belum punya akses untuk mengubah status PKP badan usaha. Minta Admin menambahkan akses "
                "'Pengaturan, Pengguna & Hak Akses'.")


async def _with_profile(out: Dict[str, Any]) -> Dict[str, Any]:
    """KP-T1 — tempel nilai registry yang dipakai mesin; `currency` = mata uang pembukuan (bentuk daftar tetap)."""
    prof = await lifecycle.profile_settings(out["id"])
    return {**out, **prof, "currency": prof["base_currency"]}


async def _entity_out(entity: Dict[str, Any]) -> Dict[str, Any]:
    return await _with_profile(lifecycle.uniform_entity(entity))


async def _guard_tax_scope(request: Request, entity_id: str) -> None:
    """KP-T1 (N1) — PT sasaran wajib dalam penugasan pemanggil (PT terarsip yang terbaca → 409 di layanan)."""
    ctx = await entity_ctx(request)
    readable = set(ctx.allowed_entity_ids) | set(await lifecycle.archived_readable_ids(ctx.user))
    if entity_id not in readable:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan untuk badan usaha ini")


def _entity_query(status: str, type: str, q: str, include_test: bool) -> Dict[str, Any]:
    """PK-47 (KP-17) — SATU perakit saringan untuk daftar dan penghitung, supaya jumlah = banyak baris daftar."""
    query: Dict[str, Any] = {}
    # FIX-1 (B1 K-B1-10, UI-05) — "PT Uji Provisioning …" bertanda `is_test` (skrip penanda, bisa dibalik) tidak
    # ditawarkan di pengalih badan usaha; layar master meminta `include_test=true`.
    if not include_test:
        query["is_test"] = {"$ne": True}
    if status and status != "all":
        if status == "archived":
            query["status"] = {"$in": sorted(lifecycle.WRITE_LOCKED_STATUSES)}
        else:
            query["status"] = status
    if type:
        query["type"] = type
    if q:
        query["$or"] = [
            {"legal_name": {"$regex": q, "$options": "i"}},
            {"short_name": {"$regex": q, "$options": "i"}},
            {"doc_prefix": {"$regex": q, "$options": "i"}},
        ]
    return query


@router.get("/entities")
async def list_entities(
    request: Request,
    status: str = Query("active", description="active | archived | all"),
    type: str = Query("", description="filter jenis badan usaha"),
    q: str = Query("", description="cari nama legal / nama singkat / kode"),
    with_readiness: bool = Query(False, description="sertakan ringkasan kesiapan"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    include_test: bool = Query(False, description="FIX-1 — sertakan badan usaha bertanda data uji"),
) -> List[Dict[str, Any]]:
    """Daftar badan usaha — dipakai pemilih entitas, jadi semua user login boleh baca.

    E1.5: **default hanya yang aktif**. Sebelum FASE E-1 endpoint ini selalu
    mengembalikan semua status sehingga badan usaha nonaktif ikut muncul di
    pemilih entitas dan bisa dipilih — lalu tulisnya gagal jauh di belakang.

    PR-T3 (S2) — tetap untuk semua yang login (data rujukan), tetapi tanpa `entity.view` tiap baris hanya memuat
    `REFERENCE_FIELDS`; `user_count` dan `readiness` tidak dikirim dan `with_readiness` diabaikan.
    """
    user = await current_user(request)
    full = await has_permission(user, "entity", "view")
    query = _entity_query(status, type, q, include_test)
    rows = await db.business_entities.find(query, {"_id": 0}).sort(
        "created_at", 1).skip(offset).limit(limit).to_list(limit)
    out: List[Dict[str, Any]] = []
    for row in rows:
        item = await _entity_out(row)      # KP-T1 — `currency` dari registry; kunci S2 tetap 14
        if not full:
            out.append({k: item.get(k) for k in REFERENCE_FIELDS})
            continue
        item["user_count"] = await db.users.count_documents(
            {"home_entity_id": row["id"], "status": "active"})
        if with_readiness:
            item["readiness"] = await readiness_svc.readiness_summary(row["id"], row)
        out.append(item)
    return out


@router.get("/entities/count")
async def count_entities(
    request: Request,
    status: str = Query("active", description="active | archived | all"),
    type: str = Query("", description="filter jenis badan usaha"),
    q: str = Query("", description="cari nama legal / nama singkat / kode"),
    include_test: bool = Query(False, description="sertakan badan usaha bertanda data uji"),
) -> Dict[str, Any]:
    """Jumlah badan usaha (untuk paging daftar berskala puluhan entitas). Saringan = `GET /api/entities`."""
    await require_permission(request, "entity", "view", detail=_S5_DITOLAK)   # PR-T3 (S5)
    return {"count": await db.business_entities.count_documents(_entity_query(status, type, q, include_test))}


@router.get("/entities/{entity_id}")
async def get_entity(entity_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "entity", "view", detail=_S5_DITOLAK)   # PR-T3 (S5) — jumlah akun, kunci awalan
    entity = await lifecycle.get_entity_or_404(entity_id)
    out = await _entity_out(entity)
    out["prefix_lock"] = await lifecycle.prefix_lock_info(entity_id)
    out["user_count"] = await db.users.count_documents(
        {"home_entity_id": entity_id, "status": "active"})
    out["tax_status_history"] = entity.get("tax_status_history") or []   # KP-T1 — bagian Pajak di layar detail
    return out


@router.get("/entities/{entity_id}/readiness")
async def get_readiness(entity_id: str, request: Request) -> Dict[str, Any]:
    """E1.9 — daftar periksa kesiapan badan usaha (terhitung, bukan teks statis)."""
    await require_permission(request, "entity", "view", detail=_S5_DITOLAK)   # PR-T3 (S5)
    entity = await lifecycle.get_entity_or_404(entity_id)
    return await readiness_svc.readiness(entity_id, entity)


@router.get("/entities/{entity_id}/deactivation-impact")
async def get_deactivation_impact(entity_id: str, request: Request) -> Dict[str, Any]:
    """E1.6 — pratinjau dampak SEBELUM mengarsipkan (dipakai dialog konfirmasi)."""
    await require_permission(request, "entity", "update")
    return await lifecycle.deactivation_impact(entity_id)


@router.get("/entities/{entity_id}/audit")
async def get_entity_audit(entity_id: str, request: Request,
                           limit: int = Query(50, ge=1, le=200)) -> List[Dict[str, Any]]:
    """Riwayat perubahan badan usaha (dipakai drawer detail E-3).

    Ter-scope ganda: badan usaha yang diminta harus ∈ penugasan pemanggil, DAN
    barisnya disaring lewat `resolve_list_scope_inherit` (jejak lama pra-E0 belum
    ber-stempel, jadi harus memakai varian "inherit" supaya tidak hilang).
    """
    await require_permission(request, "audit", "view")
    ctx = await entity_ctx(request)
    if entity_id not in ctx.allowed_entity_ids:
        raise HTTPException(status_code=404,
                            detail="Data tidak ditemukan untuk badan usaha ini")
    # `entity_type`/`entity_id` di audit_logs = SUMBER DAYA (lihat dependencies.audit);
    # untuk jejak badan usaha, sumber dayanya memang badan usaha itu sendiri.
    query = resolve_list_scope_inherit(
        "audit_logs", {"entity_type": "business_entity", "entity_id": entity_id},
        ctx, entity_id_param=entity_id)
    rows = await db.audit_logs.find(query, {"_id": 0}).sort(
        "timestamp", -1).limit(limit).to_list(limit)
    return [safe_doc(r) for r in rows]


@router.post("/entities")
async def create_entity(payload: BusinessEntityCreate, request: Request) -> Dict[str, Any]:
    """F0-F — Provisioning badan usaha baru siap-pakai (CoA, numbering, config, PKP)."""
    actor = await require_permission(request, "entity", "create")
    result = await provisioning.provision_entity(payload.model_dump(), actor["name"])
    entity = result["entity"]
    await audit(actor["name"], "entity_provisioned", "business_entity", entity["id"],
                {**entity, "provisioning": result["provisioning"]},
                scope_entity_id=entity["id"])
    out = await _entity_out(entity)
    return {**out, "provisioning": result["provisioning"],
            "readiness": await readiness_svc.readiness(entity["id"], entity)}


@router.patch("/entities/{entity_id}")
async def update_entity(entity_id: str, payload: GenericPatch,
                        request: Request) -> Dict[str, Any]:
    """E1.2/E1.3 — PATCH memakai VALIDASI YANG SAMA dengan POST.

    `status` sengaja TIDAK bisa diubah lewat sini: pindah status harus lewat
    DELETE (arsip, dengan pratinjau dampak) atau `POST .../reactivate` supaya
    pagar E1.6 tidak bisa dilewati dengan patch biasa.
    """
    actor = await require_permission(request, "entity", "update")
    existing = await lifecycle.get_entity_or_404(entity_id)
    # KP-T1 — `default_tax_mode` ikut ke validasi supaya ditolak dengan petunjuk (bukan diabaikan diam-diam).
    raw = {k: v for k, v in (payload.data or {}).items()
           if k in lifecycle.EDITABLE_FIELDS or k == "default_tax_mode"}
    if not raw:
        raise HTTPException(
            status_code=400,
            detail="Tidak ada field yang bisa diubah. Status badan usaha diubah lewat "
                   "tombol Arsipkan / Aktifkan kembali, bukan lewat pembaruan biasa.")
    data = await provisioning.validate_entity_input(raw, entity_id=entity_id,
                                                    existing=existing)
    data["updated_at"] = now_iso()
    entity = await db.business_entities.find_one_and_update(
        {"id": entity_id}, {"$set": data},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not entity:
        raise HTTPException(status_code=404, detail="Badan usaha tidak ditemukan")
    invalidate_entity_code(entity_id)   # E1.4 — nomor dokumen berikutnya pakai kode baru
    await audit(actor["name"], "entity_updated", "business_entity", entity_id, data,
                scope_entity_id=entity_id)
    out = await _entity_out(entity)
    out["prefix_lock"] = await lifecycle.prefix_lock_info(entity_id)
    return out


@router.delete("/entities/{entity_id}")
async def archive_entity(entity_id: str, request: Request,
                         force: bool = Query(False),
                         reason: str = Query("")) -> Dict[str, Any]:
    """E1.6 — ARSIPKAN (bukan hapus). 409 + rincian bila masih terpakai.

    `force=true` hanya untuk admin dan wajib beralasan. Setelah diarsipkan:
    kunci-tulis (semua POST/PATCH ke badan usaha itu 409), data lama tetap
    terbaca admin, pengguna yang badan usaha utamanya ini diblokir masuk.
    """
    actor = await require_permission(request, "entity", "delete")
    result = await lifecycle.archive_entity(entity_id, actor, reason=reason, force=force)
    await audit(actor["name"], "entity_archived", "business_entity", entity_id,
                {"reason": reason, "forced": force,
                 "sessions_revoked": result.get("sessions_revoked", 0)},
                scope_entity_id=entity_id)
    out = await _entity_out(result)
    out["sessions_revoked"] = result.get("sessions_revoked", 0)
    out["impact"] = result.get("impact")
    return out


@router.post("/entities/{entity_id}/archive")
async def archive_entity_post(entity_id: str, body: EntityArchiveBody,
                              request: Request) -> Dict[str, Any]:
    """Varian POST dengan body (alasan panjang) — perilaku identik DELETE."""
    actor = await require_permission(request, "entity", "delete")
    result = await lifecycle.archive_entity(entity_id, actor, reason=body.reason,
                                            force=body.force)
    await audit(actor["name"], "entity_archived", "business_entity", entity_id,
                {"reason": body.reason, "forced": body.force,
                 "sessions_revoked": result.get("sessions_revoked", 0)},
                scope_entity_id=entity_id)
    out = await _entity_out(result)
    out["sessions_revoked"] = result.get("sessions_revoked", 0)
    return out


@router.post("/entities/{entity_id}/reactivate")
async def reactivate_entity(entity_id: str, request: Request) -> Dict[str, Any]:
    """E1.6 — aktifkan kembali badan usaha yang diarsipkan."""
    actor = await require_permission(request, "entity", "update")
    entity = await lifecycle.reactivate_entity(entity_id, actor)
    await audit(actor["name"], "entity_reactivated", "business_entity", entity_id,
                {"status": "active"}, scope_entity_id=entity_id)
    return await _entity_out(entity)


# ─── KP-T1 (KP-02) — ubah status PKP: alasan, tanggal berlaku, pratinjau dampak ──────────────────────────────────
@router.get("/entities/{entity_id}/tax-status/preview")
async def preview_tax_status(entity_id: str, request: Request,
                             to: str = Query("", description="ppn | non_ppn"),
                             effective_date: str = Query("", description="YYYY-MM-DD"),
                             npwp: str = Query("", description="NPWP yang akan diisi bila PT belum punya")
                             ) -> Dict[str, Any]:
    """Dampak sebelum status PKP diubah: dokumen berjalan, dokumen sejak tanggal berlaku, faktur, pengaturan pajak."""
    await require_permission(request, "entity", "update", detail=_PKP_DITOLAK)
    await _guard_tax_scope(request, entity_id)
    return await lifecycle.tax_status_preview(entity_id, to, effective_date, npwp)


@router.post("/entities/{entity_id}/tax-status")
async def change_tax_status(entity_id: str, body: EntityTaxStatusIn, request: Request) -> Dict[str, Any]:
    """Tanggal ≤ hari ini (WIB) → langsung berlaku + riwayat; tanggal maju → dijadwalkan (`tax_status_pending`)."""
    actor = await require_permission(request, "entity", "update", detail=_PKP_DITOLAK)
    await _guard_tax_scope(request, entity_id)
    doc, action, before = await lifecycle.change_tax_status(entity_id, body.model_dump(), actor)
    await audit(actor["name"], action, "business_entity", entity_id,
                {"from": before, "to": body.to.strip(), "effective_date": body.effective_date.strip()},
                reason=body.reason.strip(), scope_entity_id=entity_id)
    return {**(await _entity_out(doc)), "tax_status_history": doc.get("tax_status_history") or []}


@router.delete("/entities/{entity_id}/tax-status/pending")
async def cancel_tax_status(entity_id: str, request: Request) -> Dict[str, Any]:
    """Batalkan perubahan status PKP yang terjadwal. 404 bila tidak ada jadwal."""
    actor = await require_permission(request, "entity", "update", detail=_PKP_DITOLAK)
    await _guard_tax_scope(request, entity_id)
    doc, pending = await lifecycle.cancel_pending_tax_status(entity_id)
    await audit(actor["name"], "entity_tax_status_cancelled", "business_entity", entity_id,
                {"cancelled": pending}, scope_entity_id=entity_id)
    return {**(await _entity_out(doc)), "tax_status_history": doc.get("tax_status_history") or []}
