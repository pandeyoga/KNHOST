"""Kas & Bank bagian 1 (D4, Tugas 3) — alat pindah saldo kas per PT ke akun buku besar per rekening.

Semua rute: izin `accounting.manage` (spesifikasi §5.3, §7 butir 7 — tanpa izin baru). Logika di
`services/cash_account_cutover_service.py`; layar Kas & Bank › Akun per rekening (Tugas 6).

  GET  /api/kas-per-rekening/usulan                  daftar usulan (cakupan PT pengguna; `status`, berhalaman)
  GET  /api/kas-per-rekening/{entity_id}/pratinjau   hitungan pindah saldo (tanpa tulisan) + `sidik`
  POST /api/kas-per-rekening/{entity_id}/siapkan     `{pilihan_akun}` → akun rekening + usulan `menunggu`
  POST /api/kas-per-rekening/usulan/{id}/setujui     `{sidik, selisih_diperiksa}` — orang kedua; hitung ulang, jurnal,
                                                     PT menyala
  POST /api/kas-per-rekening/usulan/{id}/tolak       `{alasan}` (≥ 5 huruf)
"""
from typing import Any, Dict

from fastapi import APIRouter, Query, Request

from dependencies import audit, require_permission
from entity_scope import entity_ctx, guard_doc, resolve_list_scope, resolve_requested_entity
from schemas_finance import PindahSaldoSetujui, PindahSaldoSiapkan, PindahSaldoTolak
from services import approval_policy_service, cash_account_cutover_service as cut

router = APIRouter(prefix="/api/kas-per-rekening")

PESAN_IZIN = ("Anda belum punya akses untuk memindah saldo kas ke akun per rekening. Minta Admin menambahkan akses "
              "'Akuntansi' tingkat kelola.")


async def _pt(request: Request, entity_id: str) -> str:
    """PT di jalur: harus ada (404) dan dalam penugasan pengguna (403)."""
    from db import db
    if entity_id != "all" and not await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "id": 1}):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="PT tidak ditemukan.")
    return resolve_requested_entity(await entity_ctx(request), entity_id)


async def _usulan(request: Request, usulan_id: str) -> Dict[str, Any]:
    """Usulan untuk pintu TULIS (setujui/tolak): milik PT aktif kepala (`guard_doc` strict, konvensi jalur tulis — sama
    dengan Pindah Dana; tinjauan akhir Minor 4). Akun multi-PT yang berdiri di PT lain → 404."""
    from db import db
    doc = await db[cut.COLL].find_one({"id": usulan_id}, {"_id": 0})
    await guard_doc(request, cut.COLL, doc, strict=True, not_found=cut.PESAN_TIDAK_ADA)
    return doc


@router.get("/usulan")
async def list_usulan(request: Request, status: str = Query(""), entity_id: str = Query(None),
                      page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)) -> Dict[str, Any]:
    actor = await require_permission(request, "accounting", "manage", detail=PESAN_IZIN)
    scope = resolve_list_scope(cut.COLL, {}, await entity_ctx(request), entity_id)
    return await cut.daftar(scope, status, page, page_size, actor=actor)


@router.get("/{entity_id}/pratinjau")
async def pratinjau(entity_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "accounting", "manage", detail=PESAN_IZIN)
    return await cut.pratinjau(await _pt(request, entity_id))


@router.post("/{entity_id}/siapkan")
async def siapkan(entity_id: str, payload: PindahSaldoSiapkan, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "accounting", "manage", detail=PESAN_IZIN)
    eid = await _pt(request, entity_id)
    res = await cut.siapkan(eid, payload.pilihan_akun, actor)
    await audit(actor["name"], "cash_account_cutover_prepared", "cash_account_cutover", res["id"],
                {"total_dipindah": res.get("total_dipindah"), "pilihan_akun": res.get("pilihan_akun")},
                scope_entity_id=eid)
    return res


@router.post("/usulan/{usulan_id}/setujui")
async def setujui(usulan_id: str, payload: PindahSaldoSetujui, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "accounting", "manage", detail=PESAN_IZIN)
    u = await _usulan(request, usulan_id)
    # Kas & Bank 1 (Tugas 6) — Aturan Persetujuan jenis `pindah_saldo_kas` (bawaan: semua pemegang `accounting.manage`).
    await approval_policy_service.guard_door("pindah_saldo_kas", actor, doc=u)
    res = await cut.setujui(usulan_id, payload.sidik, actor, selisih_diperiksa=payload.selisih_diperiksa)
    await audit(actor["name"], "cash_account_cutover_approved", "cash_account_cutover", usulan_id,
                {"journal_number": res.get("journal_number"), "total_dipindah": res.get("total_dipindah"),
                 "kas_ditautkan": res.get("kas_ditautkan"), "sidik_disetujui": res.get("sidik_disetujui"),
                 "sidik_diposting": res.get("sidik_diposting"), "selisih_diperiksa": res.get("selisih_diperiksa"),
                 "selisih_disetujui": res.get("selisih_disetujui")}, scope_entity_id=u.get("entity_id", ""))
    return res


@router.post("/usulan/{usulan_id}/tolak")
async def tolak(usulan_id: str, payload: PindahSaldoTolak, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "accounting", "manage", detail=PESAN_IZIN)
    u = await _usulan(request, usulan_id)
    await approval_policy_service.guard_door("pindah_saldo_kas", actor, doc=u, action="reject")
    res = await cut.tolak(usulan_id, payload.alasan, actor)
    await audit(actor["name"], "cash_account_cutover_rejected", "cash_account_cutover", usulan_id,
                {"alasan": payload.alasan}, scope_entity_id=u.get("entity_id", ""))
    return res
