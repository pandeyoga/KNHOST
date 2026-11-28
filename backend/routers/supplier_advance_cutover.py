"""Kas & Bank bagian 4 (C8, Tugas 3) — pindah saldo uang muka pemasok per PT ke akun uang muka pemasok sendiri, dan daftar
uang muka terbuka.

Logika di `services/supplier_advance_cutover_service.py` dan `services/supplier_advance_service.py`; layar menyusul
(Tugas 4b). Pindah saldo: izin `accounting.manage` (spesifikasi §5.4, pola Kas & Bank 1 `cash_account_cutover`). Uang
muka terbuka (baca saja): izin `cash.view` — izin baca layar Kas & Bank tempat alat pindah saldo Kas & Bank 1 dibuka.

  GET  /api/uang-muka-pemasok/pindah/{entity_id}/pratinjau   buku pembantu, penahan, sidik (tanpa tulisan) + usulan
  POST /api/uang-muka-pemasok/pindah/{entity_id}/siapkan     usulan `menunggu` (baris, total, sidik dibekukan)
  POST /api/uang-muka-pemasok/pindah/{id}/setujui            `{sidik}` — orang kedua; hitung ulang, jurnal, PT pindah
  POST /api/uang-muka-pemasok/pindah/{id}/tolak              `{alasan}` (≥ 5 huruf)
  GET  /api/uang-muka/terbuka?entity_id=                     uang muka karyawan & pemasok vs saldo akunnya
"""
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, Request

from dependencies import audit, require_permission
from entity_scope import entity_ctx, guard_doc, resolve_requested_entity
from schemas_finance import PindahSaldoSetujui, PindahSaldoTolak
from services import supplier_advance_cutover_service as cut
from services import supplier_advance_service as sas

router = APIRouter(prefix="/api")

PESAN_IZIN = ("Anda belum punya akses untuk memindah saldo uang muka pemasok. Minta Admin menambahkan akses "
              "'Akuntansi' tingkat kelola.")
PESAN_IZIN_LIHAT = "Anda belum punya akses untuk melihat uang muka terbuka. Minta Admin menambahkan akses 'Kas & Bank'."


async def _pt(request: Request, entity_id: str) -> str:
    """PT di jalur/kueri: satu PT (400), ada (404), dan dalam penugasan pengguna (403)."""
    from db import db
    if not entity_id or entity_id == "all":
        raise HTTPException(status_code=400, detail="Pilih satu PT.")
    if not await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "id": 1}):
        raise HTTPException(status_code=404, detail="PT tidak ditemukan.")
    return resolve_requested_entity(await entity_ctx(request), entity_id)


async def _usulan(request: Request, usulan_id: str) -> Dict[str, Any]:
    """Usulan untuk pintu TULIS (setujui/tolak): milik PT aktif kepala (`guard_doc` strict, pola Kas & Bank 1)."""
    from db import db
    doc = await db[cut.COLL].find_one({"id": usulan_id}, {"_id": 0})
    await guard_doc(request, cut.COLL, doc, strict=True, not_found=cut.PESAN_TIDAK_ADA)
    return doc


@router.get("/uang-muka-pemasok/pindah/{entity_id}/pratinjau")
async def pratinjau(entity_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "accounting", "manage", detail=PESAN_IZIN)
    return await cut.pratinjau(await _pt(request, entity_id), actor)


@router.post("/uang-muka-pemasok/pindah/{entity_id}/siapkan")
async def siapkan(entity_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "accounting", "manage", detail=PESAN_IZIN)
    eid = await _pt(request, entity_id)
    res = await cut.siapkan(eid, actor)
    await audit(actor["name"], "supplier_advance_cutover_prepared", "supplier_advance_cutover", res["id"],
                {"total": res.get("total"), "sidik": res.get("sidik")}, scope_entity_id=eid)
    return res


@router.post("/uang-muka-pemasok/pindah/{usulan_id}/setujui")
async def setujui(usulan_id: str, payload: PindahSaldoSetujui, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "accounting", "manage", detail=PESAN_IZIN)
    u = await _usulan(request, usulan_id)
    res = await cut.setujui(usulan_id, payload.sidik, actor)
    await audit(actor["name"], "supplier_advance_cutover_approved", "supplier_advance_cutover", usulan_id,
                {"journal_number": res.get("journal_number"), "susulan_journal_number": res.get("susulan_journal_number"),
                 "total_dipindah": res.get("total_dipindah")}, scope_entity_id=u.get("entity_id", ""))
    return res


@router.post("/uang-muka-pemasok/pindah/{usulan_id}/tolak")
async def tolak(usulan_id: str, payload: PindahSaldoTolak, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "accounting", "manage", detail=PESAN_IZIN)
    u = await _usulan(request, usulan_id)
    res = await cut.tolak(usulan_id, payload.alasan, actor)
    await audit(actor["name"], "supplier_advance_cutover_rejected", "supplier_advance_cutover", usulan_id,
                {"alasan": payload.alasan}, scope_entity_id=u.get("entity_id", ""))
    return res


@router.get("/uang-muka/terbuka")
async def uang_muka_terbuka(request: Request, entity_id: str = Query("")) -> Dict[str, Any]:
    await require_permission(request, "cash", "view", detail=PESAN_IZIN_LIHAT)
    ctx = await entity_ctx(request)
    return await sas.uang_muka_terbuka(await _pt(request, entity_id or ctx.active_entity_id))
