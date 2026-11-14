"""Cash Management router (Fase 3 — Pengelolaan Kas).

Koleksi kanonik: `cash_transactions` (prefix cash_).
- kas_kecil : kas operasional per ENTITAS (entity_id spesifik)
- kas_besar : kas gabungan grup (entity_id = "all")
direction: in (masuk) | out (keluar). Saldo = Σ(in) − Σ(out).
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, HTTPException, Request
from pymongo import ReturnDocument
from db import db
from dependencies import require_permission, audit
from core_utils import new_id, now_iso, safe_doc
from entity_scope import entity_ctx, resolve_scope_ids, guard_doc, resolve_requested_entity, scope_meta
from schemas import CashTransactionCreate
from pagination import build_search, envelope, get_page_params, is_paged, merge_query
from services import cash_entity_service
from role_registry import CROSS_ENTITY_ROLES   # PR-T6 — lintas PT dari pengaturan per peran (himpunan hidup)

router = APIRouter(prefix="/api")

VALID_TYPES = {"kas_kecil", "kas_besar"}
VALID_DIRECTIONS = {"in", "out"}


#: PK-42 (UX-12) — kotak cari daftar kas (`q`) dan urutan halaman (terbaru dulu; `created_at`/`id` = pemecah seri
#: supaya baris tidak meloncat antar-halaman saat tanggalnya sama).
CASH_SEARCH_FIELDS = ("number", "description", "category")
CASH_SORT = [("txn_date", -1), ("created_at", -1), ("id", -1)]
#: Batas daftar tanpa halaman (bentuk jawaban lama) — tidak berubah.
CASH_UNPAGED_LIMIT = 500


def _cash_list_query(actor: Dict[str, Any], ctx, entity_id: Optional[str]) -> Dict[str, Any]:
    """Cakupan daftar kas (tanpa saringan jenis/arah) — dipakai daftar DAN hitungan tab `summary.counts`, supaya
    angka lencana tab sama dengan jumlah baris yang bisa dibuka di daftar (PK-42)."""
    entities = resolve_scope_ids(ctx, entity_id)
    or_clauses: List[Dict[str, Any]] = [{"entity_id": {"$in": entities}}]
    if (actor or {}).get("role") in CROSS_ENTITY_ROLES:
        or_clauses.append({"entity_id": {"$in": ["all", "", None]}})
    return {"status": {"$ne": "void"}, "$or": or_clauses}


@router.get("/cash-transactions")
async def list_cash_transactions(
    request: Request, entity_id: str = None, cash_type: str = None, direction: str = None
) -> Any:
    """List transaksi kas (filter entitas/jenis/arah).

    FASE E-7 (E7.4): kas tingkat grup DIHAPUS, jadi tidak ada lagi klausa "kas_besar
    selalu tampil lintas-entitas" — itu justru yang membuat uang satu PT terbaca PT
    lain. Sisa data lama ber-`entity_id="all"` tetap TERLIHAT (jangan hilang diam-diam)
    tetapi hanya untuk peran lintas-entitas, dan layar menegur agar dimigrasikan.

    PK-42 (UX-12): `page`/`page_size` → `{items, total, page, page_size, has_more}` (`q` = nomor / keterangan /
    kategori); tanpa keduanya → larik seperti sebelumnya (batas 500).
    """
    actor = await require_permission(request, "cash", "view")
    ctx = await entity_ctx(request)
    query = _cash_list_query(actor, ctx, entity_id)
    if cash_type:
        query["cash_type"] = cash_type
    if direction:
        query["direction"] = direction
    if is_paged(request):
        page, page_size, q, _sort = get_page_params(request)
        query = merge_query(query, build_search(q, CASH_SEARCH_FIELDS))
        total = await db.cash_transactions.count_documents(query)
        items = await db.cash_transactions.find(query, {"_id": 0}).sort(CASH_SORT) \
            .skip((page - 1) * page_size).limit(page_size).to_list(page_size)
        return envelope(items, total, page, page_size)
    rows = await db.cash_transactions.find(query, {"_id": 0}).sort("txn_date", -1).to_list(CASH_UNPAGED_LIMIT)
    return rows


@router.get("/cash-transactions/summary")
async def cash_summary(request: Request, entity_id: str = None) -> Dict[str, Any]:
    """Ringkasan saldo kas kecil & kas besar/bank — KEDUANYA ter-scope badan usaha.

    FASE E-7 (E7.4): dulu `kas_besar` dijumlahkan lintas grup tanpa filter apa pun,
    sehingga kartu "Kas Besar" di layar PT Kain Suka Cita memperlihatkan uang CV Kanda
    Suka. Sekarang keduanya memakai scope yang sama, dan sisa data tingkat grup
    dilaporkan TERPISAH (`group_cash_pending`) agar bisa ditegur, bukan disembunyikan.
    """
    actor = await require_permission(request, "cash", "view")
    ctx = await entity_ctx(request)
    entities = resolve_scope_ids(ctx, entity_id)

    def _agg(rows: List[Dict[str, Any]], opening: float = 0.0) -> Dict[str, float]:
        cin = sum(float(r.get("amount", 0) or 0) for r in rows if r.get("direction") == "in")
        cout = sum(float(r.get("amount", 0) or 0) for r in rows if r.get("direction") == "out")
        return {"opening": round(opening, 2), "in": round(cin, 2), "out": round(cout, 2),
                "balance": round(opening + cin - cout, 2), "count": len(rows)}

    # GN-12 — total kas dari SELURUH transaksi entitas dalam scope (bukan 2.000 pertama lintas grup)
    all_rows = await db.cash_transactions.find({"status": {"$ne": "void"}, "entity_id": {"$in": list(entities)}},
                                               {"_id": 0}).to_list(None)
    kecil_q = [r for r in all_rows if r.get("cash_type") == "kas_kecil"
               and r.get("entity_id") in entities]
    besar_q = [r for r in all_rows if r.get("cash_type") == "kas_besar"
               and r.get("entity_id") in entities]

    # breakdown kas kecil per entitas (untuk konteks "all")
    per_entity: Dict[str, Dict[str, float]] = {}
    for r in all_rows:
        if r.get("cash_type") != "kas_kecil":
            continue
        eid = r.get("entity_id", "")
        if eid not in entities:
            continue
        per_entity.setdefault(eid, {"in": 0.0, "out": 0.0})
        per_entity[eid]["in" if r.get("direction") == "in" else "out"] += float(r.get("amount", 0) or 0)
    for eid, v in per_entity.items():
        v["balance"] = round(v["in"] - v["out"], 2)
        v["in"] = round(v["in"], 2)
        v["out"] = round(v["out"], 2)

    # Saldo = saldo awal rekening + masuk − keluar (dulu saldo awal diabaikan).
    # G3 D4-CASH-01 — jenis saldo awal dari master rekening (`cash_type`), bukan dari transaksi aktif.
    from services.bank_service import account_cash_type
    accounts = await db.bank_accounts.find(
        {"entity_id": {"$in": list(entities)}},
        {"_id": 0, "id": 1, "entity_id": 1, "opening_balance": 1, "cash_type": 1, "account_type": 1}).to_list(None)
    kecil_accs = [a for a in accounts if account_cash_type(a) == "kas_kecil"]
    open_kecil = sum(float(a.get("opening_balance") or 0) for a in kecil_accs)
    open_besar = sum(float(a.get("opening_balance") or 0) for a in accounts if account_cash_type(a) == "kas_besar")
    for a in kecil_accs:
        ob = float(a.get("opening_balance") or 0)
        if abs(ob) > 0.005:
            v = per_entity.setdefault(a["entity_id"], {"in": 0.0, "out": 0.0, "balance": 0.0})
            v["balance"] = round(v["balance"] + ob, 2)
    return {
        "scope": entity_id or ("all" if ctx.view_all else ctx.active_entity_id),
        "kas_kecil": _agg(kecil_q, open_kecil),
        "kas_besar": _agg(besar_q, open_besar),
        "kas_kecil_per_entity": per_entity,
        # E7.4 — sisa data kas tingkat grup (harus nol setelah migrasi dijalankan).
        "group_cash_pending": await cash_entity_service.group_cash_pending(db),
        "scope_meta": await scope_meta(ctx, entity_id),   # PK-16
        # PK-42 (UX-12) — lencana tab daftar: jumlah transaksi non-anulir pada cakupan DAFTAR (bukan baris yang termuat
        # di layar; dulu dihitung dari ≤ 500 baris pertama).
        "counts": await _cash_counts(_cash_list_query(actor, ctx, entity_id)),
    }


async def _cash_counts(query: Dict[str, Any]) -> Dict[str, int]:
    out = {"all": await db.cash_transactions.count_documents(query)}
    for t in sorted(VALID_TYPES):
        out[t] = await db.cash_transactions.count_documents({**query, "cash_type": t})
    return out


@router.post("/cash-transactions")
async def create_cash_transaction(payload: CashTransactionCreate, request: Request) -> Dict[str, Any]:
    """Catat transaksi kas masuk/keluar."""
    actor = await require_permission(request, "cash", "create")
    ctx = await entity_ctx(request)
    if payload.cash_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail="cash_type harus kas_kecil atau kas_besar")
    if payload.direction not in VALID_DIRECTIONS:
        raise HTTPException(status_code=400, detail="direction harus in atau out")
    if float(payload.amount or 0) <= 0:
        raise HTTPException(status_code=400, detail="Nominal harus lebih dari 0")

    # FASE E-7 (E7.4) — kas tingkat grup DIHAPUS: `kas_besar` tetap berarti
    # "buku bank/transfer", tetapi uangnya WAJIB milik satu badan usaha. Sebelum ini
    # kode di sini memaksa `entity_id="all"` sehingga penerimaan piutang KSC tidak
    # pernah muncul di kas KSC (13 dari 19 transaksi demo terkena).
    from services.cash_entity_service import assert_owned
    # PK-09 E8 — PT dari penugasan (isi permintaan di luar penugasan → 403), tetap wajib satu PT (bukan grup).
    entity_id = assert_owned(resolve_requested_entity(ctx, payload.entity_id) if payload.entity_id
                             else ctx.active_entity_id, what="Transaksi kas")
    # Kas MANUAL tidak boleh menunjuk dokumen lain (pembayaran dokumen dicatat dari dokumennya, bukan dari sini).
    if (payload.ref_type or "") not in ("", "manual") or (payload.ref_id or ""):
        raise HTTPException(status_code=400, detail=(
            "Transaksi kas manual tidak boleh menunjuk dokumen lain. Catat pembayaran dari dokumennya."))
    # PK-20 — PERIKSA rekening & periode lebih dulu (urutan lama: rekening → periode → anggaran), tanpa tulisan.
    from services import cash_ledger
    from services import gl_service as _gl
    rek = await cash_ledger.periksa_rekening(entity_id, getattr(payload, "account_id", "") or "", payload.cash_type)
    try:  # FN-07 — periode diperiksa sebelum kas tercatat
        await _gl.preflight_posting(entity_id, payload.txn_date or now_iso())
    except _gl.ClosedPeriodError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    # PK-39 (K-12) — kas KELUAR manual: PERIKSA anggaran akun lawannya (bila akun beban) sebelum kas disimpan.
    budget_check = None
    if payload.direction == "out":
        from services import budget_service as _bs
        _niat = {"direction": "out", "ref_type": "", "category": payload.category.strip(), "entity_id": entity_id,
                 "amount": round(float(payload.amount), 2), "cash_type": rek["cash_type"]}
        try:
            budget_check = await _bs.enforce_budget(entity_id, await _bs.cash_budget_targets(_niat), when="cash_out",
                                                    date=payload.txn_date or "", actor=actor)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    # PK-20 (SL-11) — kas lahir lewat SATU pembuat: rekening wajib (atau rekening tunggal PT untuk jenis kasnya),
    # periode diperiksa sebelum tulisan, id tetap dari kunci idempotensi (`ref_type="manual"`, `ref_id` = kunci;
    # tanpa kunci → id baru). Jurnal gagal → kas TETAP tersimpan `failed` (tampil di Posting Gagal), bukan dihapus.
    ref_id = (request.headers.get("Idempotency-Key") or "").strip()[:120] or new_id("kasm")
    try:
        doc = await cash_ledger.create_cash(
            entity_id=entity_id, direction=payload.direction, amount=float(payload.amount), ref_type="manual",
            ref_id=ref_id, account_id=rek["account_id"], cash_type=payload.cash_type,
            txn_date=payload.txn_date or "", category=payload.category.strip(), description=payload.description.strip(),
            actor=actor.get("name", ""),   # PK-09 — nilai klien `created_by` diabaikan
            extra={"budget_check": budget_check} if budget_check is not None else None)
    except cash_ledger.CashPostingError as exc:
        await audit(actor["name"], "cash_transaction_created", "cash_transaction", exc.txn.get("id", ""), {
            "number": exc.txn.get("number", ""), "cash_type": exc.txn.get("cash_type", ""),
            "direction": payload.direction, "amount": exc.txn.get("amount"), "entity_id": entity_id,
            "gl_status": "failed"})
        raise HTTPException(status_code=409, detail=(
            f"Jurnal kas gagal: {exc.error}. Transaksi tersimpan dan bisa diulang dari Posting Gagal."))
    je = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": doc["id"],
                                            "status": {"$ne": "void"}}, {"_id": 0, "number": 1})
    doc["journal_entry_number"] = (je or {}).get("number", "")
    number = doc.get("number", "")
    await audit(actor["name"], "cash_transaction_created", "cash_transaction", doc["id"], {
        "number": number, "cash_type": doc["cash_type"], "direction": doc["direction"],
        "amount": doc["amount"], "entity_id": entity_id,
    })
    return safe_doc(doc)


@router.post("/cash-transactions/{txn_id}/void")
async def void_cash_transaction(txn_id: str, request: Request,
                                payload: Optional[Dict[str, Any]] = Body(None)) -> Dict[str, Any]:
    """Batalkan/void transaksi kas (saldo tidak lagi dihitung).

    UAT 24 Okt (audit UI tahap 2) — G1-20: alasan anulir (`{"reason": "..."}`) dicatat di dokumen & jejak audit.
    Opsional demi klien lama; layar Transaksi Kas selalu mengirimnya (wajib di dialog)."""
    actor = await require_permission(request, "cash", "delete")
    reason = str((payload or {}).get("reason") or "").strip()[:500]
    txn = await db.cash_transactions.find_one({"id": txn_id}, {"_id": 0})
    # KN-A03 — void kas dijaga entitas (dulu tanpa penjaga: saldo PT lain bisa diturunkan).
    await guard_doc(request, "cash_transactions", txn, not_found="Transaksi kas tidak ditemukan")
    if txn.get("status") == "void":
        raise HTTPException(status_code=409, detail="Transaksi sudah di-void")
    # FN-07 — kas turunan dokumen (kwitansi, uang muka, retur, AP, dll.) hanya dibatalkan lewat
    # dokumen asalnya supaya subledger sumber ikut di-unwind.
    # PK-20 — kas manual kini ber-`ref_type="manual"` (ref_id = kunci permintaan): tetap kas manual, bukan turunan dokumen.
    if (txn.get("ref_type") or "") != "manual" and (txn.get("ref_type") or txn.get("ref_id")) \
            or txn.get("gl_posted") is True:
        from services.cash_ledger import REF_LABEL
        asal = REF_LABEL.get(txn.get("ref_type") or "", "lain")
        raise HTTPException(status_code=409, detail=(
            f"Transaksi kas ini berasal dari dokumen {asal} — batalkan lewat dokumen asalnya."))
    # PK-21 — yang menahan hanya pencocokan nyata (`reconciled_amount`); tanda manual lama tidak bisa dilepas lagi.
    if float(txn.get("reconciled_amount") or 0) > 0:
        raise HTTPException(status_code=409, detail="Transaksi sudah dicocokkan dengan mutasi bank — lepaskan dulu.")
    from services import gl_service as _gl
    try:
        await _gl.preflight_posting(txn.get("entity_id", ""), now_iso())
        claimed = await db.cash_transactions.find_one_and_update(
            {"id": txn_id, "status": {"$ne": "void"}, "voiding": {"$ne": True}},
            {"$set": {"voiding": True}}, projection={"_id": 0})
        if not claimed:
            raise HTTPException(status_code=409, detail="Transaksi sedang/sudah di-void")
        # Pastikan jurnal asli ada (kas lama pra-FN-07 / jurnal gagal) lalu balik — pembalik idempotent.
        from services import cash_ledger
        try:
            await cash_ledger.ensure_posted(claimed["id"])
        except cash_ledger.CashPostingError as exc:   # bukan HTTPException biasa: penanda `voiding` harus dilepas
            raise RuntimeError(f"jurnal asal kas belum bisa diterbitkan ({exc.error})") from exc
        # PK-20 — pembalik lewat pintu tahan-gagal: hasilnya ditulis ke `void_gl_status` kas; gagal tetap dilempar
        # (kas TIDAK di-void, penanda `voiding` dilepas di bawah).
        res = await _gl.post_durable(
            "cash_transactions", txn_id,
            lambda: _gl.post_cash_void(txn_id, label=txn.get("number", ""), created_by=actor["name"]),
            source_type="cash_transaction_void", source_id=txn_id, field="void_gl_status", raise_on_fail=True)
        rev = res.get("journal") or ({"id": res["journal_entry_id"]} if res.get("journal_entry_id") else None)
    except _gl.ClosedPeriodError as exc:
        await db.cash_transactions.update_one({"id": txn_id}, {"$unset": {"voiding": ""}})
        raise HTTPException(status_code=409, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        await db.cash_transactions.update_one({"id": txn_id}, {"$unset": {"voiding": ""}})
        raise HTTPException(status_code=409, detail=f"Jurnal pembalik gagal, kas tidak di-void: {exc}")
    updated = await db.cash_transactions.find_one_and_update(
        {"id": txn_id}, {"$set": {"status": "void", "updated_at": now_iso(),
                                  "void_journal_entry_id": (rev or {}).get("id", ""),
                                  "void_reason": reason, "voided_by": actor.get("name", ""),
                                  "voided_at": now_iso()},
                         "$unset": {"voiding": ""}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER,
    )
    await audit(actor["name"], "cash_transaction_voided", "cash_transaction", txn_id,
                {"reversal_je": (rev or {}).get("number", ""), "reason": reason})
    return safe_doc(updated)
