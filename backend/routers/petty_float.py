"""Kas & Bank bagian 3 (C2, Tugas 2) — dana tetap kas kecil: posisi per rekening dan isi ulang terkunci. Logika di
`services/petty_float_service.py`; layar Kas Kecil › chip Dana tetap dan aksi Isi ulang di Rekening & Saldo (Tugas 4).

Izin (spesifikasi §5.2, §6 — tanpa izin baru): lihat `cash.view`, isi ulang `cash.create`; Setujui / Batal isi ulang
yang menunggu lewat rute Pindah Dana (`cash.approve` / `cash.delete`). Cakupan PT: rekening hanya bisa dibaca / diisi
ulang dalam cakupan PT pengguna (`guard_doc`); `entity_id` daftar di luar penugasan → 403.

  GET  /api/kas-kecil/dana-tetap                          daftar posisi rekening kas kecil berdana tetap (`entity_id`)
  GET  /api/kas-kecil/dana-tetap/{account_id}             posisi satu rekening kas kecil
  POST /api/kas-kecil/dana-tetap/{account_id}/isi-ulang   `{sumber_account_id, catatan?, tanggal?, nominal_dilihat?}`
                                                          → Pindah Dana sekali jalan bertanda `isi_ulang_kas_kecil`
                                                          (nominal = usulan server; isian `nominal` ditolak 400;
                                                          `nominal_dilihat` ≠ usulan server → 409). Di bawah awalan
                                                          idempotensi `/api/kas-kecil/` (kirim `Idempotency-Key`)
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from dependencies import audit, require_permission
from entity_scope import entity_ctx, guard_doc, resolve_scope_ids
from services import petty_float_service as pfs

router = APIRouter(prefix="/api/kas-kecil/dana-tetap")


class IsiUlangKasKecil(BaseModel):
    """Isi ulang dana tetap: rekening sumber (bank / kas besar PT yang sama), catatan, tanggal (`YYYY-MM-DD`, kosong =
    hari ini). `nominal` TIDAK diisi klien — hanya diterima supaya kiriman yang memuatnya ditolak dengan kalimat.
    `nominal_dilihat` (opsional, tinjauan akhir Minor 5) = usulan yang ditampilkan layar saat dikonfirmasi; berbeda dari
    hitungan ulang server → 409 "Usulan berubah, muat ulang"."""
    sumber_account_id: str = ""
    catatan: str = ""
    tanggal: str = ""
    nominal: Optional[float] = Field(None, ge=0)
    nominal_dilihat: Optional[float] = Field(None, ge=0)


async def _rekening(request: Request, account_id: str, *, tulis: bool) -> Dict[str, Any]:
    from db import db
    acc = await db.bank_accounts.find_one({"id": account_id}, {"_id": 0})
    await guard_doc(request, "bank_accounts", acc, strict=tulis, not_found=pfs.PESAN_TIDAK_ADA)
    return acc


@router.get("")
async def list_dana_tetap(request: Request, entity_id: str = Query(None)) -> Dict[str, Any]:
    await require_permission(request, "cash", "view")
    return await pfs.daftar(resolve_scope_ids(await entity_ctx(request), entity_id))


@router.get("/{account_id}")
async def get_dana_tetap(account_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "cash", "view")
    await _rekening(request, account_id, tulis=False)
    return await pfs.posisi(account_id)


@router.post("/{account_id}/isi-ulang")
async def isi_ulang_dana_tetap(account_id: str, payload: IsiUlangKasKecil, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "create")
    await _rekening(request, account_id, tulis=True)
    res = await pfs.isi_ulang(account_id, payload.sumber_account_id, actor, catatan=payload.catatan,
                              tanggal=payload.tanggal, nominal=payload.nominal,
                              nominal_dilihat=payload.nominal_dilihat)
    await audit(actor["name"], "petty_float_refilled", "fund_transfer", res["id"],
                {k: res.get(k) for k in ("number", "status", "nominal", "rekening_asal_id", "rekening_tujuan_id",
                                         "tanggal_kirim", "kas_ids", "jenis")},
                scope_entity_id=res.get("entity_id", ""))
    return res
