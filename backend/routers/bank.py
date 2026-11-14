"""Bank/Cash Accounts router (EPIC7-B) — multi-akun kas & bank + rekonsiliasi.

Akses: permission module "cash" (admin/manager). Respons OBJEK/ARRAY telanjang.
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import JSONResponse

from dependencies import require_any_permission, require_permission, audit
from entity_scope import entity_ctx, resolve_scope_ids
from schemas import BankAccountCreate, BankAccountUpdate
from schemas_finance import BankAccountChangeDecision
from services import bank_service
from role_registry import CROSS_ENTITY_ROLES   # PR-T6 — lintas PT dari pengaturan per peran (himpunan hidup)

router = APIRouter(prefix="/api")

#: PK-17 (standar Z6) — membuat/mengubah rekening = izin `cash.configure` (bukan `cash.create` pencatat transaksi).
PESAN_KELOLA_REKENING = ("Anda belum punya akses untuk mengelola rekening kas dan bank. Minta Admin menambahkan "
                         "akses 'Kas, Bank & Kasus Keuangan'.")
#: PM-T1 (Z6) — menyetujui perubahan rekening = `cash.approve`; daftar rekening penerima = salah satu dari tiga izin.
PESAN_SETUJUI_REKENING = ("Anda belum punya akses untuk menyetujui perubahan rekening kas dan bank. Minta Admin "
                          "menambahkan akses 'Kas, Bank & Kasus Keuangan'.")
PESAN_REKENING_PENERIMA = ("Anda belum punya akses untuk melihat rekening penerima pembayaran. Minta Admin menambahkan "
                           "akses 'Pesanan Penjualan' atau 'Kas, Bank & Kasus Keuangan'.")


@router.get("/bank-accounts")
async def list_bank_accounts(request: Request, entity_id: str = Query(None)) -> List[Dict[str, Any]]:
    """Daftar akun kas/bank + saldo terhitung.

    FASE E-7 (E7.4): akun tingkat grup (`entity_id="all"`) sudah TIDAK sah lagi —
    setiap rekening wajib milik satu badan usaha. Akun grup LAMA masih ditampilkan
    (agar bisa dipetakan, bukan hilang diam-diam) tetapi hanya untuk peran
    lintas-entitas, dan layar Kas & Bank menegur agar dimigrasikan.
    """
    actor = await require_permission(request, "cash", "view")
    ctx = await entity_ctx(request)
    entities = resolve_scope_ids(ctx, entity_id)
    or_clauses: List[Dict[str, Any]] = [{"entity_id": {"$in": entities}}]
    if (actor or {}).get("role") in CROSS_ENTITY_ROLES:
        or_clauses.append({"entity_id": {"$in": ["all", "", None]}})
    scope = {"$or": or_clauses}
    return await bank_service.list_accounts(scope=scope)


@router.get("/bank-accounts/position")
async def bank_cash_position(request: Request, entity_id: str = Query(None)) -> Dict[str, Any]:
    """K-02 (26 Okt) — angka utama "Kas & Bank" = saldo buku besar akun kas+bank (sama dengan Dasbor Keuangan),
    plus transaksi kas yang belum tertaut ke rekening (penjelas selisih terhadap Σ saldo rekening)."""
    await require_permission(request, "cash", "view")
    ctx = await entity_ctx(request)
    return await bank_service.cash_position(resolve_scope_ids(ctx, entity_id))


@router.get("/bank-accounts/receiving")
async def receiving_bank_accounts(request: Request, entity_id: str = Query(None),
                                  method: str = Query("transfer")) -> List[Dict[str, Any]]:
    """PM-T1 — rekening penerima uang pelanggan untuk satu PT dan cara bayar (`[{id, name, bank_name, account_number,
    holder_name, is_default}]`, tanpa saldo). Bahan instruksi bayar dan kwitansi ber-rekening."""
    await require_any_permission(request, [("order", "create"), ("ar_receipt", "create"), ("cash", "view")],
                                 detail=PESAN_REKENING_PENERIMA)
    ctx = await entity_ctx(request)
    from entity_scope import resolve_requested_entity
    from services import bank_account_change_service as bacs
    return await bacs.daftar_penerima(resolve_requested_entity(ctx, entity_id), method)


def _jawab(status: int, body: Dict[str, Any]):
    """202 = perubahan disimpan sebagai pengajuan (kontrol dua orang `ubah_rekening`)."""
    return JSONResponse(status_code=202, content=body) if status == 202 else body


@router.post("/bank-accounts")
async def create_bank_account(payload: BankAccountCreate, request: Request) -> Dict[str, Any]:
    """Buat akun kas/bank baru (PM-T1: langsung, atau 202 + pengajuan bila butuh orang kedua)."""
    actor = await require_permission(request, "cash", "configure", detail=PESAN_KELOLA_REKENING)
    ctx = await entity_ctx(request)
    # FASE E-7 (E7.4) — rekening tingkat grup DIHAPUS: setiap rekening wajib milik
    # satu badan usaha, kalau tidak neraca & arus kas per PT tidak pernah utuh.
    from services.cash_entity_service import assert_owned
    from entity_scope import resolve_requested_entity
    payload.entity_id = resolve_requested_entity(ctx, assert_owned(payload.entity_id or ctx.active_entity_id,
                                                                   what="Rekening kas/bank"))
    from services import bank_account_change_service as bacs
    status, body = await bacs.buat(payload, actor)
    if status == 202:
        await audit(actor["name"], "bank_account_change_requested", "bank_account", body["change"]["id"],
                    {"name": payload.name, "action": "buat"})
    else:
        await audit(actor["name"], "bank_account_created", "bank_account", body["id"],
                    {"name": body["name"], "type": body["account_type"]})
    return _jawab(status, body)


@router.patch("/bank-accounts/{account_id}")
async def patch_bank_account(account_id: str, payload: BankAccountUpdate, request: Request) -> Dict[str, Any]:
    """Ubah / nonaktifkan akun kas/bank (PM-T1: field peka + dua orang → 202 + pengajuan)."""
    actor = await require_permission(request, "cash", "configure", detail=PESAN_KELOLA_REKENING)
    data = payload.model_dump()
    # KN-B34 — rekening yang diubah wajib milik entitas aktif (dulu assert_owned hanya menolak nilai tingkat grup →
    # rekening PT lain bisa "dipindahkan"). Pindah PT tidak lewat PATCH: skema ubah tidak memuat `entity_id`.
    from entity_scope import guard_doc
    from db import db as _db
    prev = await _db.bank_accounts.find_one({"id": account_id}, {"_id": 0})
    await guard_doc(request, "bank_accounts", prev, not_found="Akun tidak ditemukan")
    from services import bank_account_change_service as bacs
    status, body = await bacs.ubah(prev, data, actor, reason=data.get("reason") or "")
    changed = {k: v for k, v in data.items() if v is not None and k != "reason"}
    if status == 202:
        await audit(actor["name"], "bank_account_change_requested", "bank_account", account_id,
                    {"change_id": body["change"]["id"], "fields": sorted(changed)})
    else:
        await audit(actor["name"], "bank_account_updated", "bank_account", account_id,
                    {k: body.get(k) for k in changed}, before={k: (prev or {}).get(k) for k in changed})
    return _jawab(status, body)


@router.get("/bank-account-changes")
async def list_bank_account_changes(request: Request, status: str = Query(""), entity_id: str = Query(None),
                                    page: int = Query(1, ge=1),
                                    page_size: int = Query(25, ge=1, le=100)) -> Dict[str, Any]:
    """PM-T1 — perubahan rekening per PT (menunggu persetujuan / diterapkan / ditolak), berhalaman."""
    actor = await require_permission(request, "cash", "view")
    ctx = await entity_ctx(request)
    from entity_scope import resolve_list_scope
    from services import bank_account_change_service as bacs
    return await bacs.daftar(resolve_list_scope(bacs.COLL, {}, ctx, entity_id), status, page, page_size, actor)


@router.post("/bank-account-changes/{change_id}/decision")
async def decide_bank_account_change(change_id: str, payload: BankAccountChangeDecision,
                                     request: Request) -> Dict[str, Any]:
    """PM-T1 — setujui (terapkan bila nilai lama masih sama) atau tolak perubahan rekening; pengaju ≠ pemutus bila
    `kontrol.ubah_rekening.min_orang` = 2."""
    actor = await require_permission(request, "cash", "approve", detail=PESAN_SETUJUI_REKENING)
    from entity_scope import guard_doc
    from db import db as _db
    from services import bank_account_change_service as bacs
    ch = await _db[bacs.COLL].find_one({"id": change_id}, {"_id": 0})
    await guard_doc(request, bacs.COLL, ch, not_found="Perubahan rekening tidak ditemukan")
    res = await bacs.putuskan(ch, payload.decision, payload.note, actor)
    await audit(actor["name"], f"bank_account_change_{payload.decision}", "bank_account",
                ch.get("account_id") or change_id, {"change_id": change_id, "note": payload.note})
    return res


@router.get("/bank-accounts/{account_id}/ledger")
async def bank_account_ledger(account_id: str, request: Request) -> Dict[str, Any]:
    """Buku besar (ledger) akun: transaksi + running balance."""
    actor = await require_permission(request, "cash", "view")
    from db import db as _db
    await _guard_cash_doc(request, actor, "bank_accounts",
                          await _db.bank_accounts.find_one({"id": account_id}, {"_id": 0}), "Akun tidak ditemukan")
    led = await bank_service.account_ledger(account_id)
    if led is None:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    return led


async def _guard_cash_doc(request: Request, actor: Dict[str, Any], collection: str,
                          doc: Dict[str, Any], not_found: str) -> None:
    """GN-03 — dokumen kas/bank lewat ID wajib milik entitas aktif; record grup lama hanya admin/manager."""
    if not doc:
        raise HTTPException(status_code=404, detail=not_found)
    if doc.get("entity_id") in ("all", "", None):
        if (actor or {}).get("role") not in CROSS_ENTITY_ROLES:
            raise HTTPException(status_code=404, detail=not_found)
        return
    from entity_scope import guard_doc
    await guard_doc(request, collection, doc, not_found=not_found)


#: PK-21 (SL-10) — tanda rekonsiliasi manual dimatikan: status "terekonsiliasi" hanya dari pencocokan mutasi bank.
PESAN_TANDA_MANUAL_MATI = ("Tanda rekonsiliasi manual sudah tidak dipakai. Cocokkan transaksi dengan mutasi bank di "
                           "Keuangan › Rekonsiliasi Bank.")


@router.post("/cash-transactions/{txn_id}/reconcile")
async def reconcile_cash_transaction(txn_id: str, request: Request) -> Dict[str, Any]:
    """PK-21 — dulu menandai transaksi kas terekonsiliasi ya/tidak tanpa mutasi bank (angka kedua yang tidak sejalan
    dengan `reconciled_amount`). Kini selalu 410 sesudah pemeriksaan izin dan entitas; tidak menulis apa pun."""
    actor = await require_permission(request, "cash", "create")
    from db import db as _db
    await _guard_cash_doc(request, actor, "cash_transactions",
                          await _db.cash_transactions.find_one({"id": txn_id}, {"_id": 0}), "Transaksi tidak ditemukan")
    raise HTTPException(status_code=410, detail=PESAN_TANDA_MANUAL_MATI)
