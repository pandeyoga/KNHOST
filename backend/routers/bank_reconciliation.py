"""FASE G-8 — Router **REKONSILIASI BANK** (parser multi-bank · skor · split · titipan).

Satu pintu untuk: template format bank, pratinjau impor, impor berkas, cocokkan otomatis
(3 pita: otomatis / usulan / manual), kandidat berperingkat, cocok manual 1:1, split 1:N,
gabung N:1, aturan hasil pembelajaran, dan **titipan dana belum teridentifikasi**.

RBAC: memakai modul izin `cash` yang SUDAH ADA (tidak menambah modul izin baru).
  * `cash:view`   → melihat mutasi, skor, usulan, ringkasan, aturan
  * `cash:create` → impor, cocokkan, titipkan, alokasikan titipan, memutus aturan
  * F1 — kwitansi dari mutasi: `cash:create` + `ar_receipt:create` (+ `payment_report:decide` bila menerima laporan
    bayar bersama mutasi); batal kwitansi mutasi: `ar_receipt:void` + `cash:create`.

F1 (kwitansi otomatis dari mutasi bank) — impor (`/import`, `/import-file`) dan "Cocokkan otomatis" menjalankan mesin
`bank_auto_receipt_service` sesudah jalur lama; responsnya bertambah `kwitansi_otomatis`, `kartu`, `nilai_otomatis`.
Galat mesin tidak menggagalkan impor/pencocokan (dicatat, jumlah 0).

ISOLASI ENTITAS: setiap endpoint menghitung `entity_ids` lewat `resolve_scope_ids(ctx)`
lalu meneruskannya ke service. Akun/baris/transaksi milik PT lain → **403**, termasuk bila
id-nya dikirim eksplisit. Sebelum FASE G-8 celah ini terbuka (lihat POC G-8 bukti-merah).

Respons OBJEK/ARRAY telanjang (konsisten dgn `bank.py`).
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from dependencies import audit, require_permission
from entity_scope import EntityContext, entity_ctx, resolve_scope_ids
from routers.ar_receipts import ReceiptPayload
from services import bank_auto_receipt_service as f1
from services import bank_recon_service as svc

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def _ids(ctx: EntityContext, entity_id: Optional[str] = None) -> List[str]:
    return resolve_scope_ids(ctx, entity_id)


def _actor_name(actor: Dict[str, Any]) -> str:
    return actor.get("name", actor.get("email", ""))


# ── Skema masukan ────────────────────────────────────────────────────────────
class StatementLineIn(BaseModel):
    stmt_date: str = ""
    amount: float = 0
    direction: str = "out"
    description: str = ""
    ref: Optional[str] = ""
    external_id: Optional[str] = ""


class StatementImportInput(BaseModel):
    bank_account_id: str
    entity_id: Optional[str] = ""
    lines: List[StatementLineIn] = Field(default_factory=list)


#: Berkas Excel dikirim base64 (≈ 4/3 ukuran berkas); batas parser 5 MB → teks base64 ≤ 7 jutaan karakter.
XLSX_B64_MAX = 7_100_000


class RawImportInput(BaseModel):
    bank_account_id: str
    raw: str = ""
    format_id: Optional[str] = ""
    fmt: Optional[Dict[str, Any]] = None
    year_hint: Optional[int] = 0
    file_name: Optional[str] = ""   # M38 — nama berkas yang diunggah (asal mutasi)
    file_b64: Optional[str] = Field("", max_length=XLSX_B64_MAX)   # berkas Excel .xlsx (base64) — menggantikan `raw`


class PreviewInput(BaseModel):
    raw: str = ""
    format_id: Optional[str] = ""
    fmt: Optional[Dict[str, Any]] = None
    year_hint: Optional[int] = 0
    file_b64: Optional[str] = Field("", max_length=XLSX_B64_MAX)


class AutoMatchInput(BaseModel):
    bank_account_id: str
    window_days: Optional[int] = None
    amount_tol: Optional[float] = None


class ManualMatchInput(BaseModel):
    txn_id: str


class SplitInput(BaseModel):
    allocations: List[Dict[str, Any]] = Field(default_factory=list)


class GroupInput(BaseModel):
    line_ids: List[str] = Field(default_factory=list)
    txn_id: str


class IgnoreInput(BaseModel):
    note: Optional[str] = ""


class BookChargeInput(BaseModel):
    """FASE G-8 — baris rekening koran yang memang tidak ada di buku.

    `kind`: `charge` (biaya administrasi/transfer bank, dana KELUAR) atau
    `interest` (bunga · jasa giro, dana MASUK).
    """
    kind: str = "charge"
    note: Optional[str] = ""


class HoldingInput(BaseModel):
    note: Optional[str] = ""


class HoldingAllocateInput(BaseModel):
    customer_id: Optional[str] = ""
    reason_code: str = ""
    note: Optional[str] = ""
    allocations: List[Dict[str, Any]] = Field(default_factory=list)


class RuleDecisionInput(BaseModel):
    action: str = "activate"      # activate | reject | suspend


class LineReceiptInput(ReceiptPayload):
    """F1 §5.5 — isian form "Terima pembayaran" + laporan bayar yang diterima BERSAMA mutasi ini (opsional). Rekening,
    tanggal, nominal kas, PT, dan sumber kwitansi diisi server dari baris mutasi."""
    payment_report_id: str = Field("", max_length=80)


class LineReceiptVoidInput(BaseModel):
    reason: Optional[str] = Field("", max_length=500)   # panjang minimum diperiksa layanan (400 berkalimat)


class FormatInput(BaseModel):
    id: Optional[str] = ""
    name: str = ""
    bank_code: Optional[str] = "generic"
    file_kind: Optional[str] = "csv"
    delimiter: Optional[str] = ","
    has_header: Optional[bool] = True
    skip_rows: Optional[int] = 0
    decimal_style: Optional[str] = "auto"
    date_format: Optional[str] = "auto"
    columns: Dict[str, Any] = Field(default_factory=dict)
    in_markers: List[str] = Field(default_factory=list)
    out_markers: List[str] = Field(default_factory=list)
    header_signature: List[str] = Field(default_factory=list)
    note: Optional[str] = ""
    active: Optional[bool] = True


#: F1 — jumlah respons impor / "Cocokkan otomatis" bila mesin gagal atau tidak ada baris (galat tidak menggagalkan).
F1_KOSONG = {"kwitansi_otomatis": 0, "kartu": 0, "nilai_otomatis": 0.0}


def _f1_jumlah(out: Dict[str, Any]) -> Dict[str, Any]:
    return {k: out.get(k, v) for k, v in F1_KOSONG.items()}


async def _f1_impor(import_batch: str, pemicu: str) -> Dict[str, Any]:
    """F1 §5.1 — baris baru batch impor diproses mesin kwitansi otomatis. Galat → dicatat, jumlah 0."""
    try:
        return _f1_jumlah(await f1.proses_impor(import_batch, pemicu))
    except Exception as exc:  # noqa: BLE001 — impor sudah sah; mesin F1 tidak boleh menggagalkannya
        logger.exception("[F1] mesin kwitansi otomatis gagal untuk impor %s: %s", import_batch, exc)
        return dict(F1_KOSONG)


def _bad(e: Exception):
    if isinstance(e, HTTPException):
        raise e
    # PK-15 — keadaan berubah / alokasi tertinggal / jurnal gagal / periode tertutup → 409 (bukan 400).
    from services import gl_service as _gl
    from services.bank_recon_service import HoldingConflict
    if isinstance(e, (HoldingConflict, _gl.ClosedPeriodError)):
        raise HTTPException(status_code=409, detail=str(e))
    raise HTTPException(status_code=400, detail=str(e))


# ═══════════════════════ TEMPLATE FORMAT BANK ════════════════════════════════
@router.get("/bank-reconciliation/formats")
async def list_formats(request: Request, ctx: EntityContext = Depends(entity_ctx),
                       entity_id: str = Query(None)) -> List[Dict[str, Any]]:
    actor = await require_permission(request, "cash", "view")
    return await svc.list_formats(_ids(ctx, entity_id), ctx.active_entity_id, _actor_name(actor))


@router.post("/bank-reconciliation/formats")
async def upsert_format(payload: FormatInput, request: Request,
                        ctx: EntityContext = Depends(entity_ctx)) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "create")
    try:
        res = await svc.upsert_format(payload.model_dump(exclude_none=True),
                                      ctx.active_entity_id, _actor_name(actor), _ids(ctx))
    except Exception as e:  # noqa: BLE001
        _bad(e)
    await audit(_actor_name(actor), "bank_format_saved", "bank_statement_format",
                res.get("id", ""), {"name": res.get("name", "")})
    return res


@router.delete("/bank-reconciliation/formats/{format_id}")
async def delete_format(format_id: str, request: Request,
                        ctx: EntityContext = Depends(entity_ctx)) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "create")
    try:
        await svc.delete_format(format_id, _ids(ctx))
    except Exception as e:  # noqa: BLE001
        _bad(e)
    await audit(_actor_name(actor), "bank_format_deleted", "bank_statement_format", format_id, {})
    return {"ok": True, "id": format_id}


@router.post("/bank-reconciliation/preview")
async def preview_statement(payload: PreviewInput, request: Request,
                            ctx: EntityContext = Depends(entity_ctx)) -> Dict[str, Any]:
    await require_permission(request, "cash", "view")
    try:
        return await svc.preview(payload.raw, payload.format_id or "", payload.fmt,
                                 _ids(ctx), ctx.active_entity_id, int(payload.year_hint or 0),
                                 file_b64=payload.file_b64 or "")
    except Exception as e:  # noqa: BLE001
        _bad(e)


# ═══════════════════════ IMPOR ═══════════════════════════════════════════════
@router.post("/bank-reconciliation/import")
async def import_statement(payload: StatementImportInput, request: Request,
                           ctx: EntityContext = Depends(entity_ctx)) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "create")
    try:
        res = await svc.import_lines(payload.bank_account_id, payload.entity_id or "",
                                     [l.model_dump() for l in payload.lines],
                                     _actor_name(actor), _ids(ctx), ctx.active_entity_id, source="tempel")
    except Exception as e:  # noqa: BLE001
        _bad(e)
    res.update(await _f1_impor(res.get("import_batch", ""), _actor_name(actor)))
    await audit(_actor_name(actor), "bank_statement_imported", "bank_account",
                payload.bank_account_id, {"imported": res["imported"], "skipped": res["skipped"],
                                          **_f1_jumlah(res)})
    return res


@router.post("/bank-reconciliation/import-file")
async def import_file(payload: RawImportInput, request: Request,
                      ctx: EntityContext = Depends(entity_ctx)) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "create")
    try:
        res = await svc.import_raw(payload.bank_account_id, payload.raw,
                                   payload.format_id or "", payload.fmt, _ids(ctx),
                                   ctx.active_entity_id, _actor_name(actor),
                                   int(payload.year_hint or 0), file_name=payload.file_name or "",
                                   file_b64=payload.file_b64 or "")
    except Exception as e:  # noqa: BLE001
        _bad(e)
    res.update(await _f1_impor(res.get("import_batch", ""), _actor_name(actor)))
    await audit(_actor_name(actor), "bank_statement_imported_file", "bank_account",
                payload.bank_account_id,
                {"imported": res["imported"], "skipped": res["skipped"],
                 "format": res.get("format_name", ""), "file_kind": (res.get("source") or {}).get("file_kind", ""),
                 "file_name": payload.file_name or "", **_f1_jumlah(res)})
    return res


# ═══════════════════════ PENCOCOKAN ══════════════════════════════════════════
@router.post("/bank-reconciliation/auto-match")
async def auto_match(payload: AutoMatchInput, request: Request,
                     ctx: EntityContext = Depends(entity_ctx)) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "create")
    try:
        res = await svc.auto_match(payload.bank_account_id, _ids(ctx), payload.window_days,
                                   payload.amount_tol, _actor_name(actor), ctx.active_entity_id)
    except Exception as e:  # noqa: BLE001
        _bad(e)
    # F1 §5.1 — sesudah pencocokan lama: baris berkode yang belum pernah diproses / berstatus kartu dinilai (ulang).
    try:
        out = await f1.proses_rekening(payload.bank_account_id, _ids(ctx),
                                       f"Cocokkan otomatis oleh {_actor_name(actor)}")
    except Exception as exc:  # noqa: BLE001 — pencocokan lama sudah sah; mesin F1 tidak boleh menggagalkannya
        logger.exception("[F1] mesin kwitansi otomatis gagal untuk rekening %s: %s", payload.bank_account_id, exc)
        out = {}
    res.update(_f1_jumlah(out))
    otomatis = [r for r in out.get("rincian") or [] if r.get("hasil") == "otomatis"]
    if otomatis and isinstance(res.get("unmatched_lines"), int):   # sisa sesudah mesin F1 (jalur A memakai kas lama)
        res["unmatched_lines"] = max(0, res["unmatched_lines"] - len(otomatis))
        res["unmatched_txns"] = max(0, int(res.get("unmatched_txns") or 0)
                                    - sum(1 for r in otomatis if r.get("jalur") == "A"))
    await audit(_actor_name(actor), "bank_auto_matched", "bank_account",
                payload.bank_account_id, res)
    return res


@router.get("/bank-reconciliation/lines")
async def list_lines(request: Request, ctx: EntityContext = Depends(entity_ctx),
                     bank_account_id: str = Query(...), status: str = Query(None),
                     start: str = Query(None), end: str = Query(None),
                     entity_id: str = Query(None)) -> List[Dict[str, Any]]:
    await require_permission(request, "cash", "view")
    try:
        return await svc.list_lines(bank_account_id, _ids(ctx, entity_id), status, start, end)
    except Exception as e:  # noqa: BLE001
        _bad(e)


@router.get("/bank-reconciliation/lines/{line_id}/candidates")
async def line_candidates(line_id: str, request: Request,
                          ctx: EntityContext = Depends(entity_ctx),
                          limit: int = Query(8, ge=1, le=100),
                          mode: str = Query("single", pattern="^(single|split|group)$"),
                          total: float = Query(0, ge=0)) -> Dict[str, Any]:
    # Uji rekonsiliasi 18 Nov — `mode` split (pecah 1:N) / group (gabung N:1, `total` = Σ mutasi terpilih).
    await require_permission(request, "cash", "view")
    try:
        return await svc.candidates(line_id, _ids(ctx), limit, mode, total)
    except Exception as e:  # noqa: BLE001
        _bad(e)


@router.get("/bank-reconciliation/summary")
async def recon_summary(request: Request, ctx: EntityContext = Depends(entity_ctx),
                        bank_account_id: str = Query(...), start: str = Query(None),
                        end: str = Query(None), entity_id: str = Query(None)) -> Dict[str, Any]:
    await require_permission(request, "cash", "view")
    try:
        return await svc.summary(bank_account_id, _ids(ctx, entity_id), start, end)
    except Exception as e:  # noqa: BLE001
        _bad(e)


@router.post("/bank-reconciliation/lines/{line_id}/match")
async def match_line(line_id: str, payload: ManualMatchInput, request: Request,
                     ctx: EntityContext = Depends(entity_ctx)) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "create")
    try:
        res = await svc.manual_match(line_id, payload.txn_id, _actor_name(actor), _ids(ctx))
    except Exception as e:  # noqa: BLE001
        _bad(e)
    await audit(_actor_name(actor), "bank_line_matched", "bank_statement_line", line_id,
                {"txn_id": payload.txn_id})
    return res


@router.post("/bank-reconciliation/lines/{line_id}/match-split")
async def match_split(line_id: str, payload: SplitInput, request: Request,
                      ctx: EntityContext = Depends(entity_ctx)) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "create")
    try:
        res = await svc.match_split(line_id, payload.allocations, _actor_name(actor), _ids(ctx))
    except Exception as e:  # noqa: BLE001
        _bad(e)
    await audit(_actor_name(actor), "bank_line_split_matched", "bank_statement_line", line_id,
                {"allocations": len(payload.allocations)})
    return res


@router.post("/bank-reconciliation/match-group")
async def match_group(payload: GroupInput, request: Request,
                      ctx: EntityContext = Depends(entity_ctx)) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "create")
    try:
        res = await svc.match_group(payload.line_ids, payload.txn_id, _actor_name(actor), _ids(ctx))
    except Exception as e:  # noqa: BLE001
        _bad(e)
    await audit(_actor_name(actor), "bank_lines_group_matched", "cash_transaction",
                payload.txn_id, {"lines": len(payload.line_ids)})
    return res


@router.post("/bank-reconciliation/lines/{line_id}/unmatch")
async def unmatch_line(line_id: str, request: Request,
                       ctx: EntityContext = Depends(entity_ctx)) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "create")
    try:
        res = await svc.unmatch(line_id, _actor_name(actor), _ids(ctx))
    except Exception as e:  # noqa: BLE001
        _bad(e)
    await audit(_actor_name(actor), "bank_line_unmatched", "bank_statement_line", line_id, {})
    return res


async def _perm_kwitansi_mutasi(request: Request) -> Dict[str, Any]:
    # Izin sebagai DEPENDENCY (pola T-10 `POST /ar-receipts`): pemanggil tak berwenang menerima 403, bukan 422.
    await require_permission(request, "cash", "create")
    return await require_permission(request, "ar_receipt", "create")


async def _perm_batal_kwitansi_mutasi(request: Request) -> Dict[str, Any]:
    await require_permission(request, "ar_receipt", "void")
    return await require_permission(request, "cash", "create")


@router.post("/bank-reconciliation/lines/{line_id}/receipt")
async def receipt_from_line(line_id: str, payload: LineReceiptInput, request: Request,
                            actor: Dict[str, Any] = Depends(_perm_kwitansi_mutasi)) -> Dict[str, Any]:
    """F1 §5.5 — "Kwitansi dari mutasi" dalam SATU permintaan: klaim baris → kwitansi (atau Terima laporan bayar
    bersama mutasi) → tautan. Tautan gagal → kwitansi dibatalkan + 409 (tidak ada kwitansi tanpa tautan).
    Pola `POST /ar-receipts`: izin = dependency (403 sebelum 422), cakupan PT `entity_ctx(request)` di badan rute."""
    ctx = await entity_ctx(request)
    body = payload.model_dump()
    if body.get("payment_report_id"):   # menerima laporan bayar = putusan Lapor Bayar (aturan yang ada)
        await require_permission(request, "payment_report", "decide")
    try:
        res = await f1.kwitansi_dari_mutasi(line_id, body, actor, _ids(ctx))
    except Exception as e:  # noqa: BLE001
        _bad(e)
    rc = res["receipt"]
    await audit(_actor_name(actor), "bank_line_receipt_created", "bank_statement_line", line_id, {
        "receipt_id": rc.get("id", ""), "receipt_number": rc.get("number", ""), "amount": rc.get("amount", 0),
        "order_ids": [a.get("order_id") for a in rc.get("allocations") or [] if a.get("order_id")],
        "payment_report_id": body.get("payment_report_id") or "", "released_order_ids": res["released_order_ids"]},
        scope_entity_id=rc.get("entity_id") or "")
    if body.get("payment_report_id"):   # jejak laporan sama dengan `POST /payment-reports/{id}/terima`
        oid = next((a.get("order_id") for a in rc.get("allocations") or [] if a.get("order_id")), "")
        await audit(_actor_name(actor), "payment_report_accepted", "payment_report", body["payment_report_id"], {
            "number": rc.get("payment_report_number", ""), "order_id": oid, "amount": rc.get("amount", 0),
            "receipt_number": rc.get("number", ""), "released": oid in res["released_order_ids"],
            "source": f1.SUMBER, "bank_line_id": line_id}, scope_entity_id=rc.get("entity_id") or "")
    # Sama dengan `POST /ar-receipts`: kirim WhatsApp kwitansi bila ada aturan aktif (efek samping, tidak menggagalkan).
    try:
        from services import delivery_service as _ds
        await _ds.dispatch_event("ar_receipt", rc.get("id", ""), "created", rc.get("entity_id") or None,
                                 _actor_name(actor))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[F1] kirim kwitansi %s gagal diabaikan: %s", rc.get("number"), exc)
    return res


@router.post("/bank-reconciliation/lines/{line_id}/void-receipt")
async def void_line_receipt(line_id: str, payload: LineReceiptVoidInput, request: Request,
                            actor: Dict[str, Any] = Depends(_perm_batal_kwitansi_mutasi)) -> Dict[str, Any]:
    """F1 §5.6 — "Batalkan kwitansi dari mutasi": lepas tautan + batal kwitansi dalam SATU permintaan; baris tidak
    diproses mesin lagi. Pesanan yang sudah dilepas ke gudang hanya diperingatkan (`peringatan`). Pola
    `POST /ar-receipts`: izin = dependency (403 sebelum 422), cakupan PT `entity_ctx(request)` di badan rute."""
    ctx = await entity_ctx(request)
    try:
        res = await f1.batal_kwitansi_mutasi(line_id, payload.reason or "", actor, _ids(ctx))
    except Exception as e:  # noqa: BLE001
        _bad(e)
    rc = res["receipt"]
    alasan = (payload.reason or "").strip()
    await audit(_actor_name(actor), "bank_line_receipt_voided", "bank_statement_line", line_id, {
        "receipt_id": rc.get("id", ""), "receipt_number": rc.get("number", ""), "amount": rc.get("amount", 0),
        "reason": alasan, "order_ids": res["order_ids"], "order_released": res["order_released"]},
        scope_entity_id=rc.get("entity_id") or "")
    # Jejak kwitansi sama dengan `POST /ar-receipts/{id}/void`.
    await audit(_actor_name(actor), "ar_receipt_voided", "ar_receipt", rc.get("id", ""), {
        "reason": alasan, "number": rc.get("number", ""), "amount": rc.get("amount", 0), "bank_line_id": line_id},
        scope_entity_id=rc.get("entity_id") or "")
    return res


@router.post("/bank-reconciliation/lines/{line_id}/ignore")
async def ignore_line(line_id: str, payload: IgnoreInput, request: Request,
                      ctx: EntityContext = Depends(entity_ctx)) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "create")
    try:
        res = await svc.ignore_line(line_id, _actor_name(actor), _ids(ctx), payload.note or "")
    except Exception as e:  # noqa: BLE001
        _bad(e)
    await audit(_actor_name(actor), "bank_line_ignored", "bank_statement_line", line_id,
                {"note": payload.note or ""})
    return res


@router.post("/bank-reconciliation/lines/{line_id}/unignore")
async def unignore_line(line_id: str, request: Request,
                        ctx: EntityContext = Depends(entity_ctx)) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "create")
    try:
        res = await svc.unignore_line(line_id, _actor_name(actor), _ids(ctx))
    except Exception as e:  # noqa: BLE001
        _bad(e)
    await audit(_actor_name(actor), "bank_line_unignored", "bank_statement_line", line_id, {})
    return res


# ═══════════════════════ BIAYA / BUNGA BANK ══════════════════════════════════
@router.post("/bank-reconciliation/lines/{line_id}/book-charge")
async def book_charge(line_id: str, payload: BookChargeInput, request: Request,
                      ctx: EntityContext = Depends(entity_ctx)) -> Dict[str, Any]:
    """Baris rekening koran tanpa pasangan di buku (biaya adm bank / bunga · jasa giro)
    dibukukan langsung: transaksi kas + jurnal terbit, lalu baris tertaut ke kas itu."""
    actor = await require_permission(request, "cash", "create")
    try:
        res = await svc.book_charge(line_id, payload.kind, payload.note or "",
                                    _actor_name(actor), _ids(ctx), ctx.active_entity_id)
    except Exception as e:  # noqa: BLE001
        _bad(e)
    await audit(_actor_name(actor), "bank_line_booked_charge", "bank_statement_line", line_id,
                {"kind": payload.kind, "account_code": res.get("account_code", ""),
                 "cash_number": res.get("cash_number", "")})
    return res


# ═══════════════════════ ATURAN PEMBELAJARAN ═════════════════════════════════
@router.get("/bank-reconciliation/rules")
async def list_rules(request: Request, ctx: EntityContext = Depends(entity_ctx),
                     bank_account_id: str = Query(None), status: str = Query(None),
                     entity_id: str = Query(None)) -> List[Dict[str, Any]]:
    await require_permission(request, "cash", "view")
    return await svc.list_rules(_ids(ctx, entity_id), bank_account_id or "", status or "")


@router.post("/bank-reconciliation/rules/{rule_id}/decide")
async def decide_rule(rule_id: str, payload: RuleDecisionInput, request: Request,
                      ctx: EntityContext = Depends(entity_ctx)) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "create")
    try:
        res = await svc.decide_rule(rule_id, payload.action, _actor_name(actor), _ids(ctx))
    except Exception as e:  # noqa: BLE001
        _bad(e)
    await audit(_actor_name(actor), "bank_rule_decided", "bank_match_rule", rule_id,
                {"action": payload.action})
    return res


# ═══════════════════════ TITIPAN DANA ════════════════════════════════════════
@router.get("/bank-reconciliation/holding")
async def holding_queue(request: Request, ctx: EntityContext = Depends(entity_ctx),
                        bank_account_id: str = Query(None),
                        entity_id: str = Query(None)) -> Dict[str, Any]:
    await require_permission(request, "cash", "view")
    return await svc.holding_summary(_ids(ctx, entity_id), bank_account_id or "")


@router.post("/bank-reconciliation/lines/{line_id}/holding")
async def to_holding(line_id: str, payload: HoldingInput, request: Request,
                     ctx: EntityContext = Depends(entity_ctx)) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "create")
    try:
        res = await svc.to_holding(line_id, payload.note or "", _actor_name(actor),
                                   _ids(ctx), ctx.active_entity_id)
    except Exception as e:  # noqa: BLE001
        _bad(e)
    await audit(_actor_name(actor), "bank_line_to_holding", "bank_statement_line", line_id,
                {"note": payload.note or ""})
    return res


@router.post("/bank-reconciliation/lines/{line_id}/holding/allocate")
async def allocate_holding(line_id: str, payload: HoldingAllocateInput, request: Request,
                           ctx: EntityContext = Depends(entity_ctx)) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "create")
    # LB-T4 (B3, R11) — titipan dana bank ke pesanan yang ditahan bayar hanya oleh pemegang `payment_report.decide`
    # (409 sebelum apa pun ditulis). Layanan menerima nama pelaku saja, jadi pagarnya di sini.
    from services import ar_receipt_service as _ars_b3
    await _ars_b3.pagar_lapor_bayar(actor, [a.get("order_id") for a in payload.allocations or [] if isinstance(a, dict)])
    try:
        res = await svc.allocate_holding(line_id, payload.allocations, payload.customer_id or "",
                                         payload.reason_code, payload.note or "",
                                         _actor_name(actor), _ids(ctx))
    except Exception as e:  # noqa: BLE001
        _bad(e)
    await audit(_actor_name(actor), "bank_holding_allocated", "bank_statement_line", line_id,
                {"allocated": res.get("allocated_now"), "reason_code": payload.reason_code})
    return res


@router.post("/bank-reconciliation/lines/{line_id}/holding/cancel")
async def cancel_holding(line_id: str, request: Request,
                         ctx: EntityContext = Depends(entity_ctx)) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "create")
    try:
        res = await svc.cancel_holding(line_id, _actor_name(actor), _ids(ctx))
    except Exception as e:  # noqa: BLE001
        _bad(e)
    await audit(_actor_name(actor), "bank_holding_cancelled", "bank_statement_line", line_id, {})
    return res
