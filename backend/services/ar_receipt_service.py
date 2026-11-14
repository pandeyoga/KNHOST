"""AR Receipt service (EPIC3B) — Penerimaan pembayaran customer + aplikasi ke SO.

Mencatat penerimaan kas dari customer lalu meng-apply-nya ke sales_orders
(`payments[]`, `paid_total`, `payment_status`). Karena credit gate &
Collection Worklist sudah membaca `payments[]`/`payment_status`, AR otomatis
ter-update tanpa perubahan lapisan lain (lihat customer_service.compute_customer_credit).

Integrasi tambahan (audit fix):
  - P0-1: setiap penerimaan KAS (amount > 0) di-posting ke `cash_transactions`
    (direction=in, ref_type=ar_receipt). Routing: tunai → kas_kecil (per entitas),
    transfer/giro/qris → kas_besar (bank gabungan).
  - P2-5: kelebihan bayar (unapplied) → `customers.deposit_balance`; deposit dapat
    dipakai mendanai alokasi via `use_deposit_amount`.
  - P2-6: void/reversal — membalik payments[], void cash, dan koreksi deposit.

Alokasi:
  - Eksplisit: payload.allocations = [{order_id, amount}].
  - Otomatis (default): FIFO ke order terbuka tertua sampai dana habis.

Idempotensi nomor: AR-##### via next_doc_number (deletion-safe).
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso, next_doc_number, safe_doc, DEFAULT_ENTITY_ID, rupiah

# Re-use kontrak AR yang sama dengan engine kredit (SSOT tunggal — hindari drift).
from services.customer_service import (
    _order_grand_total as order_grand_total,
    _order_paid as order_paid,
    order_payment_method,
    DEAD_STATUSES,
    NON_AR_METHODS,
)
from request_context import active_entity_or
from ai_card_context import card_field
logger = logging.getLogger(__name__)


EPS = 0.01


def _payment_status(grand_total: float, paid: float) -> str:
    if paid >= grand_total - EPS:
        return "paid"
    if paid > EPS:
        return "partial"
    return "unpaid"


# ─── Cash posting (P0-1) ─────────────────────────────────────────────────────
async def _cash_routing(method: str, entity_id: str = "") -> tuple:
    """(cash_type, force_all_entity) berdasar metode pembayaran (P0-1/P3-9).

    Tunai (cara bayar ber-rekening kas, `payment_method_service.is_cash` — PM-T1; kata lama `tunai`/`kontan` ikut
    lewat alias) → kas_kecil (per entitas). Transfer/giro/qris → kas_besar (bank).

    FASE E-7 (E7.4): elemen kedua **selalu False** sekarang. `kas_besar` berarti
    "buku bank", BUKAN "milik grup" — uangnya tetap milik badan usaha penerbit
    kwitansi. Sebelum ini penerimaan `KSC/AR-0000x` tercatat `entity_id="all"`
    sehingga kas PT Kain Suka Cita terlihat kosong padahal uangnya masuk.
    """
    from services.payment_method_service import is_cash
    if await is_cash(entity_id, method):
        return "kas_kecil", False
    return "kas_besar", False


async def _post_cash_in(receipt: Dict[str, Any], actor: Dict[str, Any]) -> Optional[str]:
    """Kas masuk penerimaan AR lewat pembuat kas satu pintu (PK-20). Mengembalikan id cash_transaction.

    Rekening = `receipt.account_id` (sudah diperiksa `create_receipt` sebelum tulisan; kosong = rekening tunggal PT untuk
    jenis kas cara bayarnya). FN-10 — kegagalan jurnal TIDAK disembunyikan: kas (`create_cash`) & kwitansi ditandai
    `gl_status=failed` (terlihat, bisa diulang lewat POST /ar-receipts/{id}/repost atau panel Posting Gagal)."""
    amt = round(float(receipt.get("amount", 0) or 0), 2)
    if amt <= EPS:
        return None
    cash_type, force_all = await _cash_routing(receipt.get("method", ""), receipt.get("entity_id") or "")
    # E7.4 — pemilik uang = badan usaha kwitansinya (tidak ada lagi kas grup).
    from services.cash_entity_service import resolve_owner
    entity_id = resolve_owner(receipt.get("entity_id"), DEFAULT_ENTITY_ID,
                              what="Kas masuk kwitansi")
    from services import cash_ledger
    try:
        cdoc = await cash_ledger.create_cash(
            entity_id=entity_id, direction="in", amount=amt, ref_type="ar_receipt", ref_id=receipt["id"],
            account_id=receipt.get("account_id") or "", cash_type=cash_type,
            txn_date=receipt.get("receipt_date") or now_iso(), category="penagihan",
            description=f"Penerimaan {receipt.get('number')} — {receipt.get('customer_name', '')}",
            actor=actor.get("name", "system"))
        # KN-G3: jurnal kas diposting SEKARANG (bukan menunggu backfill) supaya saldo Piutang & Uang Muka Pelanggan
        # langsung benar — penting sejak keputusan selisih pembayaran (FASE G-3) bisa menjurnal di detik yang sama.
        await db.ar_receipts.update_one({"id": receipt["id"]}, {"$set": {"gl_status": "posted", "gl_error": ""}})
    except cash_ledger.CashPostingError as exc:
        logger.error("[_post_cash_in] jurnal kwitansi %s gagal: %s", receipt.get("number"), exc.error)
        cdoc = exc.txn
        await db.ar_receipts.update_one({"id": receipt["id"]}, {"$set": {
            "gl_status": "failed", "gl_error": exc.error[:300], "updated_at": now_iso()}})
    return cdoc.get("id")


async def _post_deposit_gl(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """W2-015 — jurnal reklas kwitansi murni deposit; gagal → gl_status=failed (bisa repost)."""
    from services import gl_service as _gl
    try:
        await _gl.post_deposit_only_receipt(doc, created_by=actor.get("name", "system"))
        await db.ar_receipts.update_one({"id": doc["id"]}, {"$set": {"gl_status": "posted", "gl_error": ""}})
    except Exception as exc:  # noqa: BLE001
        logger.error("[deposit_gl] jurnal kwitansi %s gagal: %s", doc.get("number"), exc)
        await db.ar_receipts.update_one({"id": doc["id"]}, {"$set": {
            "gl_status": "failed", "gl_error": str(exc)[:300], "updated_at": now_iso()}})


async def repost_receipt(receipt_id: str) -> Dict[str, Any]:
    """FN-10 — ulangi jurnal kas kwitansi yang gagal (idempotent per cash_transaction)."""
    rc = await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0})
    if not rc:
        raise HTTPException(status_code=404, detail="Kwitansi tidak ditemukan")
    if not rc.get("cash_txn_id") and float(rc.get("used_deposit") or 0) > EPS:
        await _post_deposit_gl(rc, {"name": "repost"})
        fresh = await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0})
        if fresh.get("gl_status") == "failed":
            raise HTTPException(status_code=409, detail=f"Jurnal masih gagal: {fresh.get('gl_error')}")
        return safe_doc(fresh)
    txn = await db.cash_transactions.find_one({"id": rc.get("cash_txn_id") or "__none__"}, {"_id": 0})
    if not txn:
        raise HTTPException(status_code=409, detail="Kwitansi tanpa transaksi kas — tidak ada jurnal untuk diulang")
    from services import cash_ledger   # PK-20 — jurnal kas lewat pembuat kas (pintu tahan-gagal di dalamnya)
    try:
        await cash_ledger.ensure_posted(txn["id"])
    except cash_ledger.CashPostingError as exc:
        await db.ar_receipts.update_one({"id": receipt_id}, {"$set": {"gl_status": "failed", "gl_error": exc.error[:300]}})
        raise HTTPException(status_code=409, detail=f"Jurnal masih gagal: {exc.error}")
    await db.ar_receipts.update_one({"id": receipt_id}, {"$set": {"gl_status": "posted", "gl_error": "",
                                                                  "updated_at": now_iso()}})
    return safe_doc(await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0}))


# ─── Deposit (P2-5) ──────────────────────────────────────────────────────────
async def get_deposit_balance(customer_id: str) -> float:
    c = await db.customers.find_one({"id": customer_id}, {"_id": 0, "deposit_balance": 1})
    return round(float((c or {}).get("deposit_balance", 0) or 0), 2)


async def _adjust_deposit(customer_id: str, delta: float) -> None:
    if abs(delta) < EPS:
        return
    pred: Dict[str, Any] = {"id": customer_id}
    if delta < 0:
        # KN-B08 — pemakaian deposit berprasyarat saldo cukup (CAS): dua pemakaian
        # bersamaan tidak bisa membuat deposit negatif.
        pred["deposit_balance"] = {"$gte": round(-delta, 2) - EPS}
    res = await db.customers.update_one(
        pred, {"$inc": {"deposit_balance": round(delta, 2)}, "$set": {"updated_at": now_iso()}})
    if res.matched_count == 0 and delta < 0:
        raise HTTPException(status_code=409, detail="Deposit pelanggan tidak cukup (baru saja terpakai proses lain).")


async def adjust_deposit(customer_id: str, delta: float) -> None:
    """FASE G-3 — penyesuaian deposit dari keputusan selisih pembayaran (publik)."""
    await _adjust_deposit(customer_id, delta)


async def list_open_orders(customer_id: str, entity_id: Any = None) -> List[Dict[str, Any]]:
    """Order AR terbuka (ada outstanding) untuk customer, tertua dulu (FIFO).
    `entity_id` str atau list scope (CX-02 — alokasi/daftar tidak lintas badan usaha)."""
    q: Dict[str, Any] = {"customer_id": customer_id}
    if isinstance(entity_id, list):
        q["entity_id"] = {"$in": entity_id}
    elif entity_id and entity_id != "all":
        q["entity_id"] = entity_id
    orders = await db.sales_orders.find(q, {"_id": 0}).to_list(2000)
    # Cek UI UAT v3 (S3) — pesanan TUNAI yang keluar lewat Surat Jalan dijurnal Dr Piutang per SJ (gl_service.
    # post_shipment_revenue), jadi pembayarannya dicatat lewat kwitansi seperti biasa. Hanya tunai TANPA SJ
    # (jurnal lama Dr Kas saat jual) yang tetap bukan piutang.
    cash_ids = [o["id"] for o in orders if order_payment_method(o) in NON_AR_METHODS]
    cash_with_sj = set(await db.shipments.distinct(
        "order_id", {"order_id": {"$in": cash_ids}, "status": {"$nin": ["cancelled", "void", "voided"]}})) if cash_ids else set()
    rows = []
    for o in orders:
        if o.get("status") in DEAD_STATUSES:
            continue
        if order_payment_method(o) in NON_AR_METHODS and o["id"] not in cash_with_sj:
            continue
        gt = order_grand_total(o)
        paid = order_paid(o)
        outstanding = round(gt - paid, 2)
        if outstanding <= EPS:
            continue
        rows.append({
            "order_id": o["id"],
            "entity_id": o.get("entity_id", ""),
            "number": o.get("number", o["id"]),
            "grand_total": round(gt, 2),
            "paid_total": round(paid, 2),
            "outstanding": outstanding,
            "payment_status": o.get("payment_status") or _payment_status(gt, paid),
            "created_at": o.get("created_at"),
        })
    rows.sort(key=lambda r: str(r.get("created_at") or ""))
    return rows


async def create_receipt(payload: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    customer = await db.customers.find_one({"id": payload.get("customer_id")}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")

    amount = round(float(payload.get("amount", 0) or 0), 2)              # kas baru diterima
    use_deposit_amount = round(float(payload.get("use_deposit_amount", 0) or 0), 2)  # dana dari deposit (P2-5)
    if amount < 0 or use_deposit_amount < 0:
        raise HTTPException(status_code=400, detail="Jumlah pembayaran tidak valid")

    deposit_avail = await get_deposit_balance(customer["id"])
    if use_deposit_amount > deposit_avail + EPS:
        raise HTTPException(
            status_code=400,
            detail=f"Deposit tidak cukup (tersedia {rupiah(deposit_avail)})")

    total_funds = round(amount + use_deposit_amount, 2)
    if total_funds <= EPS:
        raise HTTPException(status_code=400, detail="Jumlah pembayaran harus > 0")

    receipt_date = payload.get("receipt_date") or now_iso()
    # FASE E-1 (E1.10) — kwitansi milik badan usaha pelanggan/konteks, bukan default.
    entity_id = (payload.get("entity_id") or customer.get("entity_id")
                 or active_entity_or(DEFAULT_ENTITY_ID))
    # PM-T1 — cara bayar dari daftar induk (kata lama → kode kanonik; tak dikenal / nonaktif di PT ini → 400)
    # SEBELUM apa pun ditulis.
    from services.payment_method_service import kode_400
    method = await kode_400(entity_id, payload.get("method") or "transfer", arah="masuk")
    # FN-10 — periode tertutup ditolak SEBELUM kwitansi/alokasi/deposit dimutasi.
    from services import gl_service as _glp
    try:
        await _glp.preflight_posting(entity_id, receipt_date)
    except _glp.ClosedPeriodError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    # PK-20 — rekening penerima diperiksa SEBELUM kwitansi/alokasi/deposit (kas baru saja; deposit bukan kas baru).
    if amount > EPS:
        from services import cash_ledger
        from services.cash_entity_service import resolve_owner
        cash_type = (await _cash_routing(method, entity_id or ""))[0]
        payload["account_id"] = (await cash_ledger.periksa_rekening(
            resolve_owner(entity_id, DEFAULT_ENTITY_ID, what="Kas masuk kwitansi"), payload.get("account_id") or "",
            cash_type))["account_id"]
    # PK-19 (SL-08, FX-05) — SEMUA target eksplisit diperiksa satu pemeriksa (pelanggan, PT, status pesanan, sisa
    # tagihan) SEBELUM deposit direservasi; tolak di sini = tidak ada kwitansi, kas, deposit, maupun baris.
    explicit = payload.get("allocations") or []
    if explicit:
        total_alloc = round(sum(float(a.get("amount", 0) or 0) for a in explicit), 2)
        if total_alloc > total_funds + EPS:
            raise HTTPException(status_code=400, detail="Total alokasi melebihi dana (kas + deposit)")
        from services import ar_allocation_service as _aas
        await _aas.validate_targets(
            "kas" if amount > EPS else "deposit",
            [{"order_id": a.get("order_id"), "amount": a.get("amount")} for a in explicit
             if round(float(a.get("amount", 0) or 0), 2) > 0],
            customer_id=customer["id"], entity_id=entity_id)

    receipt_id = new_id("arc")
    number = await next_doc_number("ar_receipts", "number", "AR-", entity_id=entity_id)
    # W2-017 — dana deposit DIRESERVASI (CAS) sebelum alokasi SO; gagal → 409 tanpa efek apa pun.
    await _adjust_deposit(customer["id"], -use_deposit_amount)
    try:
        return await _create_receipt_after_reserve(payload, actor, customer, amount, use_deposit_amount,
                                                   total_funds, method, receipt_date, entity_id,
                                                   receipt_id, number)
    except BaseException:
        # G3 V3-AR-01 — kwitansi yang efeknya belum tuntas (atau belum lahir) dibatalkan SELURUHNYA:
        # alokasi SO dicari dari data (payments.receipt_id), bukan daftar di memori.
        r = await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0})
        if not r or r.get("effects_done") is False:
            await _rollback_unfinished_receipt(receipt_id, r, customer["id"], use_deposit_amount)
        raise


async def _rollback_unfinished_receipt(receipt_id: str, r: Optional[Dict[str, Any]], customer_id: str,
                                       use_deposit_amount: float) -> None:
    # PK-19 — kwitansi yang gagal lahir tidak pernah sah: barisnya DICABUT (bukan dibalik) lewat modul alokasi.
    from services import ar_allocation_service as _aas
    await _aas.remove_unborn(receipt_id)
    from services import gl_service as _gl
    async for c in db.cash_transactions.find({"ref_type": "ar_receipt", "ref_id": receipt_id,
                                              "status": {"$ne": "void"}}, {"_id": 0, "id": 1}):
        await db.cash_transactions.update_one({"id": c["id"]}, {"$set": {"status": "void", "updated_at": now_iso()}})
        try:
            await _gl.post_cash_void(c["id"], label=f"rollback {receipt_id}", created_by="system")
        except Exception as exc:  # noqa: BLE001
            logger.error("[create_receipt] rollback jurnal kas %s gagal: %s", c["id"], exc)
    if r:
        try:
            await _gl.reverse_deposit_only_receipt(receipt_id, label=f"rollback {r.get('number', '')}",
                                                   created_by="system")
        except Exception as exc:  # noqa: BLE001
            logger.error("[create_receipt] rollback reklas deposit %s gagal: %s", receipt_id, exc)
        if r.get("deposit_credited"):
            await _adjust_deposit(customer_id, -float(r.get("unapplied_amount") or 0))
        await db.ar_receipt_failures.insert_one({**r, "failed_at": now_iso()})
        await db.ar_receipts.delete_one({"id": receipt_id, "effects_done": False})
    await _adjust_deposit(customer_id, use_deposit_amount)   # kompensasi reservasi


async def _create_receipt_after_reserve(payload, actor, customer, amount, use_deposit_amount, total_funds,
                                       method, receipt_date, entity_id, receipt_id, number) -> Dict[str, Any]:

    # FASE G-3 — hitung SELISIH PEMBAYARAN sebelum alokasi mengubah outstanding.
    # `expected` selalu dihitung server-side dari tagihan yang jatuh tempo, sehingga
    # sisi klien tidak bisa mengarang angka "seharusnya".
    from services import payment_variance_service as pvs
    explicit = payload.get("allocations") or []
    assessment = await pvs.pre_assess(customer["id"], total_funds, explicit,
                                      as_of=receipt_date, entity_id=entity_id)

    # Tentukan alokasi (dibatasi total dana = kas baru + deposit dipakai). PK-19 — tiap alokasi lewat SATU fungsi
    # alokasi (`ar_allocation_service.allocate`) dan dipecah menurut sumber dananya: kas baru dipakai lebih dulu, lalu
    # deposit, menurut urutan alokasi (ASUMSI unit: baris `kas` = uang yang benar-benar masuk). Galat di tengah →
    # kompensasi `_rollback_unfinished_receipt` (kwitansi belum lahir → barisnya dicabut).
    from services import ar_allocation_service as _aas
    dana = {"kas": amount, "deposit": use_deposit_amount}

    async def _alokasikan(i: int, oid: str, amt: float, line_seq: int = 0) -> Dict[str, Any]:
        parts: List[Dict[str, Any]] = []
        res: Dict[str, Any] = {}
        for kind in ("kas", "deposit"):
            take = round(min(dana[kind], amt - sum(p["amount"] for p in parts)), 2)
            if take <= EPS:
                continue
            res = await _aas.allocate(
                kind=kind, order_id=oid, amount=take, source_id=receipt_id, source_number=number,
                customer_id=customer["id"], entity_id=entity_id, date=receipt_date, actor=actor,
                method=method if kind == "kas" else "deposit", plan_line_seq=line_seq, seq=str(i))
            dana[kind] = round(dana[kind] - take, 2)
            parts.append({"kind": kind, "amount": take, "payment_id": res["payment_id"]})
        return {"order_id": oid, "order_number": res.get("order_number", oid), "applied": round(amt, 2),
                "outstanding_after": res.get("outstanding_after"), "payment_status": res.get("payment_status"),
                "entity_id": res.get("entity_id", ""), "plan_line_seq": int(line_seq or 0), "parts": parts}

    allocations: List[Dict[str, Any]] = []
    if explicit:
        planned = [(a["order_id"], round(float(a.get("amount", 0) or 0), 2),
                    int(a.get("plan_line_seq") or 0)) for a in explicit
                   if round(float(a.get("amount", 0) or 0), 2) > 0]
        for i, (oid, amt, seq) in enumerate(planned):
            allocations.append(await _alokasikan(i, oid, amt, seq))
    else:
        remaining = total_funds
        for oo in await list_open_orders(customer["id"], entity_id=entity_id):
            if remaining <= EPS:
                break
            take = round(min(remaining, oo["outstanding"]), 2)
            if take <= EPS:
                continue
            allocations.append(await _alokasikan(len(allocations), oo["order_id"], take))
            remaining = round(remaining - take, 2)

    applied_total = round(sum(a["applied"] for a in allocations), 2)
    unapplied = round(total_funds - applied_total, 2)
    # Perubahan deposit: deposit terpakai berkurang, sisa tak teralokasi masuk deposit (P2-5).
    deposit_delta = round(unapplied - use_deposit_amount, 2)

    doc = {
        "id": receipt_id,
        "number": number,
        "customer_id": customer["id"],
        "customer_name": customer.get("name", ""),
        "entity_id": entity_id,
        "receipt_date": receipt_date,
        "method": method,
        "amount": amount,
        "used_deposit": use_deposit_amount,
        "total_funds": total_funds,
        "applied_total": applied_total,
        "unapplied_amount": unapplied,
        "deposit_delta": deposit_delta,
        "allocations": allocations,
        "account_id": payload.get("account_id") or "",   # PK-20 — rekening penerima kas (kosong = tanpa kas baru)
        "notes": payload.get("notes", ""),
        "status": "posted",
        "effects_done": False,   # G3 V3-AR-01 — True hanya setelah kas/GL/deposit tuntas
        # FASE G-3 — catatan selisih pembayaran (bahan antrean keputusan & INV-VAR).
        "variance": pvs.variance_block(assessment),
        "created_by": actor.get("id"),
        "created_by_name": actor.get("name", ""),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        # AG-T3 — kwitansi dari kartu tindakan asisten yang disetujui (hanya kartu `running` milik sesi ini).
        **card_field(),
    }
    await db.ar_receipts.insert_one(doc)
    # FASE G-4 — kwitansi menaut ke SETIAP pesanan yang dilunasinya (dua arah).
    from services import doc_refs_service as _refs
    for _al in allocations or []:
        if _al.get("order_id"):
            await _refs.safe_link(("ar_receipt", receipt_id), ("sales_order", _al["order_id"]),
                                  "settles", note="pembayaran dialokasikan ke pesanan")
            # FASE G-2 — jadwal pembayaran (rencana) sudah dihitung ulang oleh `allocate` (PK-19).

    # P0-1 — posting kas masuk (hanya untuk kas baru; deposit bukan kas baru).
    cash_txn_id = await _post_cash_in(doc, actor)
    if cash_txn_id:
        doc["cash_txn_id"] = cash_txn_id
        await db.ar_receipts.update_one({"id": receipt_id}, {"$set": {"cash_txn_id": cash_txn_id}})
    elif use_deposit_amount > EPS:
        await _post_deposit_gl(doc, actor)   # W2-015 — reklas nonkas, bukan kas fiktif

    # F-01 (audit 2026-09-02) — order yang menjadi berpendapatan karena pembayaran ini
    # (kebijakan `_revenue_eligible`) dijurnal SEKARANG, bukan menunggu restart.
    for _al in allocations or []:
        try:
            from services import gl_service as _gl
            await _gl.post_order_revenue_and_cogs(_al["order_id"])
        except Exception as exc:  # noqa: BLE001
            import logging
            logging.getLogger("ar_receipt").error(
                "GL pendapatan order %s gagal setelah kwitansi %s: %s",
                _al.get("order_id"), number, exc)

    # P2-5 — sesuaikan saldo deposit customer (pemakaian sudah direservasi di awal — W2-017).
    await _adjust_deposit(customer["id"], unapplied)
    await db.ar_receipts.update_one({"id": receipt_id}, {"$set": {"deposit_credited": True, "effects_done": True}})

    # ── FASE G-3 — selesaikan selisih pembayaran ────────────────────────────
    # Di dalam toleransi → diputus OTOMATIS (tetap berlabel, tetap bisa diaudit).
    # Di luar toleransi → keputusan eksplisit bila petugas sudah memilih di dialog,
    # kalau belum: kwitansi masuk antrean "Selisih Bayar" (tidak ada yang senyap).
    decision = None
    v = doc.get("variance") or {}
    try:
        if v.get("direction") == pvs.DIR_ROUNDING:
            decision = await pvs.auto_resolve_receipt(doc, actor)
        elif v.get("needs_decision") and (payload.get("variance") or {}).get("kind"):
            decision = await pvs.decide_receipt(receipt_id, payload["variance"], actor)
    except pvs.VarianceError as exc:
        # Keputusan gagal (mis. wewenang kurang) TIDAK boleh membatalkan uang yang sudah
        # masuk — kwitansi tetap sah dan selisihnya menunggu di antrean, lengkap dg sebab.
        await db.ar_receipts.update_one({"id": receipt_id}, {"$set": {
            "variance.decision_error": str(exc), "updated_at": now_iso()}})
    fresh = await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0})
    out = safe_doc(fresh or doc)
    if decision:
        out["variance_decision"] = decision
    return out


def _pesan_deposit_terpakai(r: Dict[str, Any], dep_delta: float) -> str:
    return (f"Kelebihan bayar {rupiah(dep_delta)} dari kwitansi {r.get('number', '')} sudah dipakai sebagai deposit. "
            "Batalkan dulu kwitansi yang memakai deposit tersebut, lalu batalkan kwitansi ini.")


async def _void_step(receipt_id: str, update: Dict[str, Any]) -> None:
    """PK-19 — tulis penanda satu langkah EFEK pembatalan (`void_intent.steps.*`) sesudah langkahnya jadi."""
    await db.ar_receipts.update_one({"id": receipt_id}, {**update, "$set": {
        **(update.get("$set") or {}), "updated_at": now_iso()}})


async def void_receipt(receipt_id: str, actor: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
    """Batalkan penerimaan AR (P2-6) dengan urutan `02_STANDAR.md` §1 (PK-19, SL-06).

    PERIKSA status + periode buku hari ini (tanggal pembalik) → NIAT: klaim + `void_intent.status="pending"` → EFEK,
    tiap langkah memeriksa penandanya di `void_intent.steps` lalu menulisnya sesudah jadi: (1) kelebihan bayar ditarik
    dari deposit (CAS), (2) keputusan selisih dibatalkan, (3) baris pembayaran tiap pesanan DIBALIK lewat
    `ar_allocation_service.reverse` (baris pembalik bertanggal hari ini, baris asal tetap), (4) kas kwitansi di-void,
    (5) deposit yang dipakai dikembalikan → JURNAL pembalik (kas, reklas deposit, reklas uang muka) lewat
    `post_durable` (`void_gl_status`) → SELESAI `status="void"`, `void_intent.status="done"`. Kunci dilepas di
    `finally`: galat di tengah tidak meninggalkan kunci, dan panggilan ulang meneruskan dari langkah yang belum
    bertanda. `reason` (FASE P5) disimpan sebagai `voided_reason`."""
    r = await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0})
    if not r:
        raise HTTPException(status_code=404, detail="Receipt tidak ditemukan")
    if r.get("status") == "void":
        raise HTTPException(status_code=409, detail="Receipt sudah di-void")
    # PERIKSA — periode buku hari ini (tanggal jurnal pembalik) sebelum apa pun dibalik (`02` §1 P2).
    from services.book_date import periksa_periode_dokumen_409
    await periksa_periode_dokumen_409(r.get("entity_id") or "", None, jenis="pembatalan kwitansi")
    dep_delta = round(float(r.get("deposit_delta", 0) or 0), 2)
    if dep_delta > EPS and not ((r.get("void_intent") or {}).get("steps") or {}).get("deposit_pulled") \
            and await get_deposit_balance(r.get("customer_id") or "") < dep_delta - EPS:
        raise HTTPException(status_code=409, detail=_pesan_deposit_terpakai(r, dep_delta))
    # PK-19 — pembalik baris pembayaran tidak boleh membuat terbayar negatif (sudah dipindah lewat kasus) → 409 di sini,
    # sebelum niat dan efek apa pun.
    from services import ar_allocation_service as _aas
    await _aas.reverse_check(receipt_id, [a.get("order_id") for a in r.get("allocations") or [] if a.get("order_id")])

    # NIAT — INV-ATOMIC-01: klaim kwitansi SEBELUM uang dibalik (dua batal bersamaan → satu 409).
    from services import atomic_claim as _saga
    lk = await _saga.claim("ar_receipts", receipt_id, "ar_receipt_void",
                           precondition={"status": {"$ne": "void"}}, actor=actor.get("name", ""))
    token = (lk.get(_saga.LOCK) or {}).get("token", "")
    try:
        intent = dict(lk.get("void_intent") or {})
        if intent.get("status") != "pending":
            intent = {"status": "pending", "reason": (reason or "").strip(), "by": actor.get("name", ""),
                      "at": now_iso(), "steps": {"deposit_pulled": False, "decision_reversed": False, "orders": [],
                                                 "cash": [], "deposit_restored": False}}
            await _void_step(receipt_id, {"$set": {"void_intent": intent}})
        reason = (reason or "").strip() or intent.get("reason", "")
        steps = intent.get("steps") or {}
        label = f"kwitansi {r.get('number', '')} dibatalkan"

        # EFEK 1 — P20 APAR-02 / W2-016: kelebihan bayar kwitansi ini ditarik atomik (CAS) lebih dulu.
        if dep_delta > EPS and not steps.get("deposit_pulled"):
            try:
                await _adjust_deposit(r["customer_id"], -dep_delta)
            except HTTPException:
                raise HTTPException(status_code=409, detail=_pesan_deposit_terpakai(r, dep_delta))
            await _void_step(receipt_id, {"$set": {"void_intent.steps.deposit_pulled": True}})

        # EFEK 2 — FASE G-3: keputusan selisih yang sudah dijalankan dibalik lebih dulu (jejaknya tetap).
        decision_id = ((r.get("variance") or {}).get("decision_id") or "").strip()
        if decision_id and not steps.get("decision_reversed"):
            from services import payment_variance_service as _pvs
            try:
                await _pvs.reverse_decision(decision_id, label, actor)
            except _pvs.VarianceError as exc:
                raise HTTPException(status_code=int(getattr(exc, "status_code", 400) or 400), detail=str(exc)) from exc
            await _void_step(receipt_id, {"$set": {"void_intent.steps.decision_reversed": True}})

        # EFEK 3 — baris pembayaran tiap pesanan dibalik (tidak dihapus); periode lalu tidak berubah mundur.
        from services import ar_allocation_service as _aas
        hari_ini = now_iso()
        done_orders = set(steps.get("orders") or [])
        for alloc in r.get("allocations") or []:
            oid = alloc.get("order_id")
            if not oid or oid in done_orders:
                continue
            hasil = await _aas.reverse(source_id=receipt_id, date=hari_ini, actor=actor, reason=reason or label,
                                       order_id=oid)
            ringkas = next((h for h in hasil if h["order_id"] == oid), {})
            await _void_step(receipt_id, {
                "$addToSet": {"void_intent.steps.orders": oid},
                "$push": {"reversed_orders": {"order_id": oid, "reversed": ringkas.get("reversed", 0.0),
                                              "outstanding_after": ringkas.get("outstanding_after"),
                                              "payment_status": ringkas.get("payment_status")}}})
            done_orders.add(oid)

        # EFEK 4 — kas kwitansi di-void (saldo kas tak lagi menghitungnya); jurnal pembalik di langkah JURNAL.
        async for c in db.cash_transactions.find({"ref_type": "ar_receipt", "ref_id": receipt_id,
                                                  "status": {"$ne": "void"}}, {"_id": 0, "id": 1}):
            await db.cash_transactions.update_one({"id": c["id"], "status": {"$ne": "void"}},
                                                  {"$set": {"status": "void", "updated_at": now_iso()}})
            await _void_step(receipt_id, {"$addToSet": {"void_intent.steps.cash": c["id"]}})

        # EFEK 5 — deposit yang dipakai kwitansi ini dikembalikan (porsi kelebihan sudah ditarik di langkah 1).
        if dep_delta < -EPS and not steps.get("deposit_restored"):
            await _adjust_deposit(r["customer_id"], -dep_delta)
            await _void_step(receipt_id, {"$set": {"void_intent.steps.deposit_restored": True}})

        # JURNAL — PK-18 (GL-02): pembalik kas, reklas deposit, dan reklas uang muka lewat pintu tahan-gagal
        # (`void_gl_status`/`void_gl_error`; ulang dari panel Posting Gagal).
        await _void_step(receipt_id, {"$set": {"void_gl_status": "pending"}})
        from services import posting_registry as _preg
        await _preg.durable_receipt_void(r, actor.get("name", "system"))

        # SELESAI
        await db.ar_receipts.update_one({"id": receipt_id}, _saga.finish_set({
            "status": "void", "voided_by": actor.get("name", ""), "voided_at": now_iso(), "voided_reason": reason,
            "variance.needs_decision": False, "variance.resolved": True,
            "void_intent.status": "done", "void_intent.done_at": now_iso(), "updated_at": now_iso()}))
    finally:
        await _saga.release("ar_receipts", receipt_id, token)
    return safe_doc(await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0}))


#: PK-42 (UX-12) — urutan daftar kwitansi: terbaru dulu, DI KUERI. Dulu 2.000 baris diambil tanpa urutan lalu diurutkan
#: di memori, jadi kwitansi terbaru bisa terbuang begitu baris lebih dari 2.000. `id` = pemecah seri (halaman stabil).
RECEIPT_SORT = [("created_at", -1), ("id", -1)]
#: Batas daftar tanpa halaman (bentuk jawaban lama, larik telanjang) — tetap 2.000, kini sesudah pengurutan.
RECEIPT_UNPAGED_LIMIT = 2000
#: PK-42 — kotak cari riwayat kwitansi (`q`): nomor kwitansi dan nama pelanggan.
RECEIPT_SEARCH_FIELDS = ("number", "customer_name")


def _receipt_query(customer_id: Optional[str], scope: Optional[Dict[str, Any]], q: str = "") -> Dict[str, Any]:
    from pagination import build_search, merge_query
    query: Dict[str, Any] = dict(scope or {})
    if customer_id:
        query["customer_id"] = customer_id
    return merge_query(query, build_search(q, RECEIPT_SEARCH_FIELDS))


async def list_receipts(customer_id: Optional[str] = None,
                        scope: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    rows = await db.ar_receipts.find(_receipt_query(customer_id, scope), {"_id": 0}) \
        .sort(RECEIPT_SORT).to_list(RECEIPT_UNPAGED_LIMIT)
    return [safe_doc(r) for r in rows]


async def list_receipts_page(customer_id: Optional[str], scope: Optional[Dict[str, Any]], *, page: int,
                             page_size: int, q: str = "") -> Dict[str, Any]:
    """PK-42 (UX-12) — satu halaman riwayat kwitansi + jumlah total (kontrak `pagination.envelope`)."""
    from pagination import envelope
    query = _receipt_query(customer_id, scope, q)
    total = await db.ar_receipts.count_documents(query)
    rows = await db.ar_receipts.find(query, {"_id": 0}).sort(RECEIPT_SORT) \
        .skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    return envelope([safe_doc(r) for r in rows], total, page, page_size)


async def get_receipt(receipt_id: str) -> Optional[Dict[str, Any]]:
    return safe_doc(await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0}))
