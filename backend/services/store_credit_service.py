"""R5.2 — Store Credit (Saldo Kredit Pelanggan) ledger service.

SSOT = koleksi `store_credit_ledger` (append-only, entri BERTANDA):
    amount > 0  → penambahan saldo (issue / adjust+)
    amount < 0  → pemakaian saldo (redeem / adjust-)
Saldo per (customer_id, entity_id) = Σ amount entri non-void.

Sisi GL (idempotent, via gl_service):
    issue  → Cr 2-1450 (di-posting oleh post_sales_return saat settle store_credit)
    redeem → Dr 2-1450 / Cr 1-1200 Piutang  (post_store_credit_redemption; pesanan belum dikirim → Cr 2-1400 uang muka)
    adjust → post_store_credit_adjust

Redeem meng-apply saldo ke Sales Order ber-AR terbuka (payments[].method='store_credit'),
sehingga outstanding order berkurang selaras penurunan Piutang di GL (anti-drift).
Titik pakai: POS (order hasil checkout) + Sales Order + Invoice — semua bermuara ke order AR.
"""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso, next_doc_number, safe_doc, DEFAULT_ENTITY_ID, rupiah
from services import gl_service
from services.ar_receipt_service import list_open_orders

EPS = 0.01


# ─── Saldo & Ledger ──────────────────────────────────────────────────────────
def _scope_clause(q: Dict[str, Any], entity_id: Optional[str],
                  scope_ids: Optional[List[str]]) -> Dict[str, Any]:
    """FASE E-9 — pagar badan usaha untuk saldo kredit pelanggan.

    `store_credit_ledger` adalah UANG milik pelanggan pada SATU badan usaha. Dulu
    seluruh endpoint store credit hanya memakai `entity_id` OPSIONAL dari query,
    tanpa pernah membandingkannya dengan wewenang pemanggil — jadi sales PT-B bisa
    membaca (dan menebus) saldo kredit pelanggan PT-A. Koleksinya kebetulan kosong
    di data demo, sehingga gate isolasi tidak pernah bisa memerah sampai rantai
    retur E-9 menerbitkan store credit pertama.
    """
    if entity_id:
        q["entity_id"] = entity_id
    elif scope_ids is not None:
        q["entity_id"] = {"$in": list(scope_ids)}
    return q


async def balance(customer_id: str, entity_id: Optional[str] = None,
                  scope_ids: Optional[List[str]] = None) -> float:
    q: Dict[str, Any] = {"customer_id": customer_id, "status": {"$ne": "void"}}
    _scope_clause(q, entity_id, scope_ids)
    total = 0.0
    async for e in db.store_credit_ledger.find(q, {"_id": 0, "amount": 1}):
        total += float(e.get("amount", 0) or 0)
    return round(total, 2)


async def balances_by_entity(customer_id: str,
                             scope_ids: Optional[List[str]] = None) -> Dict[str, float]:
    out: Dict[str, float] = {}
    _q = _scope_clause({"customer_id": customer_id, "status": {"$ne": "void"}}, None, scope_ids)
    async for e in db.store_credit_ledger.find(
            _q, {"_id": 0, "entity_id": 1, "amount": 1}):
        eid = e.get("entity_id", "") or ""
        out[eid] = round(out.get(eid, 0.0) + float(e.get("amount", 0) or 0), 2)
    return {k: v for k, v in out.items() if abs(v) > EPS}


async def ledger(customer_id: Optional[str] = None, entity_id: Optional[str] = None,
                 limit: int = 300, scope_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if customer_id:
        q["customer_id"] = customer_id
    _scope_clause(q, entity_id, scope_ids)
    rows = await db.store_credit_ledger.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return rows


async def summary(entity_id: Optional[str] = None,
                  scope_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Daftar pelanggan dgn saldo store credit != 0 (untuk halaman ledger)."""
    match: Dict[str, Any] = {"status": {"$ne": "void"}}
    _scope_clause(match, entity_id, scope_ids)
    pipeline = [
        {"$match": match},
        {"$group": {"_id": {"customer_id": "$customer_id", "entity_id": "$entity_id"},
                    "customer_name": {"$last": "$customer_name"},
                    "balance": {"$sum": "$amount"},
                    "last_at": {"$max": "$created_at"},
                    "entries": {"$sum": 1}}},
        {"$sort": {"last_at": -1}},
    ]
    rows: List[Dict[str, Any]] = []
    async for g in db.store_credit_ledger.aggregate(pipeline):
        bal = round(float(g.get("balance", 0) or 0), 2)
        if abs(bal) <= EPS:
            continue
        rows.append({
            "customer_id": g["_id"]["customer_id"],
            "entity_id": g["_id"].get("entity_id", ""),
            "customer_name": g.get("customer_name", ""),
            "balance": bal,
            "entries": g.get("entries", 0),
            "last_at": g.get("last_at"),
        })
    return rows


async def _append(*, customer_id: str, entity_id: str, kind: str, amount_signed: float,
                  ref_type: str, ref_id: str, ref_number: str = "", note: str = "",
                  actor: Any = None, je_id: str = "", customer_name: str = "") -> Dict[str, Any]:
    cur = await balance(customer_id, entity_id)
    new_bal = round(cur + round(amount_signed, 2), 2)
    by = actor.get("name") if isinstance(actor, dict) else (str(actor) if actor else "system")
    entry = {
        "id": new_id("scl"),
        "customer_id": customer_id,
        "customer_name": customer_name or "",
        "entity_id": entity_id or "",
        "type": kind,                      # issue | redeem | adjust
        "amount": round(amount_signed, 2),
        "balance_after": new_bal,
        "ref_type": ref_type,
        "ref_id": ref_id,
        "ref_number": ref_number,
        "note": note,
        "journal_entry_id": je_id,
        "status": "posted",
        "created_by": by,
        "created_at": now_iso(),
    }
    await db.store_credit_ledger.insert_one(dict(entry))
    from services import customer_balance_service as _cbs   # CR-T2 — saldo kredit di saldo tersimpan (turunan)
    await _cbs.refresh_safe(customer_id, entity_id or None)
    return entry


# ─── Issue (terbit saat settle store_credit) ─────────────────────────────────
async def issue(*, customer_id: str, entity_id: str, amount: float, ref_type: str, ref_id: str,
                ref_number: str = "", note: str = "", actor: Any = None,
                je_id: str = "", customer_name: str = "") -> Optional[Dict[str, Any]]:
    """Terbitkan store credit. Idempotent per (type=issue, ref_type, ref_id).
    GL sisi kredit (Cr 2-1450) di-posting oleh post_sales_return — issue di sini hanya
    mencatat ledger saldo pelanggan (SSOT), me-refer JE bila ada."""
    amount = round(float(amount or 0), 2)
    if not customer_id or amount <= EPS:
        return None
    existing = await db.store_credit_ledger.find_one(
        {"type": "issue", "ref_type": ref_type, "ref_id": ref_id, "status": {"$ne": "void"}}, {"_id": 0})
    if existing:
        return existing
    return await _append(customer_id=customer_id, entity_id=entity_id, kind="issue",
                         amount_signed=amount, ref_type=ref_type, ref_id=ref_id,
                         ref_number=ref_number, note=note or "Terbit dari retur (store credit)",
                         actor=actor, je_id=je_id, customer_name=customer_name)


# ─── Redeem (pakai saldo utk melunasi order AR) ──────────────────────────────
async def redeem(*, customer_id: str, entity_id: Optional[str], amount: float,
                 allocations: Optional[List[Dict[str, Any]]] = None, note: str = "",
                 actor: Any = None, ref_type: str = "redemption", ref_id: str = "",
                 ref_number: str = "") -> Dict[str, Any]:
    amount = round(float(amount or 0), 2)
    if amount <= EPS:
        raise HTTPException(status_code=400, detail="Jumlah pemakaian store credit harus > 0")
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    entity_id = entity_id or customer.get("entity_id") or DEFAULT_ENTITY_ID
    try:  # CX-03 — periode diperiksa sebelum satu pun order dimutasi
        await gl_service.preflight_posting(entity_id, now_iso())
    except gl_service.ClosedPeriodError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    # KN-B06 — ledger append-only tidak bisa di-CAS, maka pelanggan DIKUNCI atomik selama
    # penukaran (klaim saga pada dokumen customer): dua penukaran bersamaan → yang kedua 409,
    # dan saldo diperiksa SETELAH kunci dipegang sehingga tak bisa negatif.
    from services import atomic_claim as _saga
    await _saga.claim("customers", customer_id, "store_credit_redeem",
                      actor=(actor.get("name", "") if isinstance(actor, dict) else str(actor or "")))
    try:
        avail = await balance(customer_id, entity_id)
        if amount > avail + EPS:
            raise HTTPException(status_code=400,
                                detail=f"Saldo store credit tidak cukup (tersedia {rupiah(avail)})")
        return await _redeem_locked(customer_id=customer_id, entity_id=entity_id, amount=amount,
                                    allocations=allocations, note=note, actor=actor, ref_type=ref_type,
                                    ref_id=ref_id, ref_number=ref_number, customer=customer)
    finally:
        await _saga.release("customers", customer_id)


async def _redeem_locked(*, customer_id: str, entity_id: Optional[str], amount: float,
                         allocations: Optional[List[Dict[str, Any]]], note: str, actor: Any,
                         ref_type: str, ref_id: str, ref_number: str,
                         customer: Dict[str, Any]) -> Dict[str, Any]:
    redemption_id = new_id("scr")
    number = await next_doc_number("store_credit_redemptions", "number", "SCR-", entity_id=entity_id)
    now = now_iso()

    from services import ar_allocation_service as _aas   # PK-19 — satu fungsi alokasi
    applied: List[Dict[str, Any]] = []
    remaining = amount
    if allocations:
        # CX-02 — validasi SEMUA tujuan (pelanggan & badan usaha sama) sebelum satu pun order dimutasi
        # CX-01 — normalisasi: gabung order sama, nominal wajib > 0, Σ alokasi == amount diminta.
        merged: Dict[str, float] = {}
        for a in allocations:
            amt = round(float(a.get("amount", 0) or 0), 2)
            if amt <= 0:
                raise HTTPException(status_code=400, detail="Nominal alokasi store credit harus > 0")
            oid = a.get("order_id") or ""
            merged[oid] = round(merged.get(oid, 0.0) + amt, 2)
        alloc_total = round(sum(merged.values()), 2)
        if abs(alloc_total - amount) > EPS:
            raise HTTPException(status_code=400, detail=(
                f"Σ alokasi {rupiah(alloc_total)} harus sama dengan nominal penebusan {rupiah(amount)}"))
        # PK-19 — satu pemeriksa alokasi (pelanggan, PT, status pesanan, sisa tagihan, pesanan tunai tanpa piutang).
        planned = [(oid, amt) for oid, amt in merged.items()]
        await _aas.validate_targets("saldo_kredit", [{"order_id": oid, "amount": amt} for oid, amt in planned],
                                    customer_id=customer_id, entity_id=entity_id or "")
    else:
        planned = []
        for oo in await list_open_orders(customer_id, entity_id=entity_id):
            if remaining <= EPS:
                break
            take = round(min(remaining, oo["outstanding"]), 2)
            if take <= EPS:
                continue
            planned.append((oo["order_id"], take))
            remaining = round(remaining - take, 2)
    for i, (order_id, amt) in enumerate(planned):
        try:
            applied.append(await _aas.allocate(
                kind="saldo_kredit", order_id=order_id, amount=amt, source_id=redemption_id, source_number=number,
                customer_id=customer_id, entity_id=entity_id or "", date=now, actor=actor, method="store_credit",
                seq=str(i)))
        except HTTPException:
            await _aas.remove_unborn(redemption_id)   # penebusan belum lahir → barisnya dicabut
            raise

    applied_total = round(sum(a["applied"] for a in applied), 2)
    if applied_total <= EPS:
        raise HTTPException(status_code=400,
                            detail="Tidak ada order piutang terbuka untuk dialokasikan store credit")

    label = f"{number} — {customer.get('name', '')}"
    adv_orders: List[str] = []
    # CX-03 — jurnal gagal → alokasi AR yang sudah ditulis DIKOMPENSASI (tidak ada AR terbayar tanpa
    # kredit terpotong), lalu galat dilempar; retry memakai saldo yang masih utuh secara konsisten.
    try:
        # KEB-PDPT (gate INV-BAL-02, 18 Nov) — pesanan yang pendapatannya belum lahir (belum dikirim): bagian itu uang
        # muka (Cr 2-1400, baris bayar `gl_bucket=advance`, direklas saat surat jalan) — aturan sama dengan kwitansi kas
        # (`gl_service._receipt_lines`). Dulu selalu Cr 1-1200 → piutang buku besar minus untuk pesanan belum terkirim.
        advance = 0.0
        for a in applied:
            oid, amt_al = a.get("order_id"), round(float(a.get("applied") or 0), 2)
            if oid and amt_al > EPS and \
                    amt_al > (await gl_service.order_ar_room(oid, exclude_receipt_id=redemption_id)) + EPS:
                advance = round(advance + amt_al, 2)
                adv_orders.append(oid)
                await gl_service.tag_advance_payment(oid, redemption_id)
        je = await gl_service.post_store_credit_redemption(
            redemption_id=redemption_id, entity_id=entity_id, amount=applied_total,
            customer_label=label, date=now, advance=advance)
    except Exception as exc:
        await _aas.remove_unborn(redemption_id)   # PK-19 — penebusan tidak pernah sah → barisnya dicabut
        raise HTTPException(status_code=409, detail=f"Jurnal store credit gagal, penebusan dibatalkan: {exc}")

    entry = await _append(
        customer_id=customer_id, entity_id=entity_id, kind="redeem", amount_signed=-applied_total,
        ref_type=ref_type or "redemption", ref_id=ref_id or redemption_id,
        ref_number=ref_number or number, note=note or "Pemakaian store credit",
        actor=actor, je_id=(je or {}).get("id", ""), customer_name=customer.get("name", ""))

    by = actor.get("name") if isinstance(actor, dict) else (str(actor) if actor else "system")
    doc = {
        "id": redemption_id,
        "number": number,
        "customer_id": customer_id,
        "customer_name": customer.get("name", ""),
        "entity_id": entity_id,
        "requested_amount": amount,
        "applied_amount": applied_total,
        "unapplied_amount": round(amount - applied_total, 2),
        "allocations": applied,
        "note": note,
        "journal_entry_id": (je or {}).get("id", ""),
        "ledger_entry_id": entry["id"],
        "balance_after": entry["balance_after"],
        "status": "posted",
        "created_by": by,
        "created_at": now,
        "updated_at": now,
    }
    await db.store_credit_redemptions.insert_one(dict(doc))
    # Pesanan yang SUDAH sebagian berpendapatan: porsi uang muka yang piutangnya sudah lahir direklas ke piutang
    # sekarang (Dr 2-1400 / Cr 1-1200), bukan menunggu surat jalan berikutnya — pola kwitansi kas (`_post_cash_transaction`
    # sesudah `_receipt_lines`). Pesanan belum dikirim: tidak ada yang direklas. Gagal reklas tidak membatalkan
    # penebusan (penandanya di `reclass_gl_status`; surat jalan berikutnya menghitung ulang selisih reklasnya).
    for oid in dict.fromkeys(adv_orders):
        fresh = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
        if fresh:
            await gl_service.post_durable(
                "store_credit_redemptions", redemption_id,
                lambda fresh=fresh: gl_service.post_advance_reclass(fresh),
                source_type="advance_reclass", source_id=oid, field="reclass_gl_status")
    return safe_doc(await db.store_credit_redemptions.find_one({"id": redemption_id}, {"_id": 0}) or doc)


# ─── Adjust (koreksi manual admin) ───────────────────────────────────────────
async def adjust(*, customer_id: str, entity_id: Optional[str], amount_signed: float,
                 note: str = "", actor: Any = None) -> Dict[str, Any]:
    amt = round(float(amount_signed or 0), 2)
    if abs(amt) <= EPS:
        raise HTTPException(status_code=400, detail="Nilai penyesuaian harus != 0")
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    entity_id = entity_id or customer.get("entity_id") or DEFAULT_ENTITY_ID
    # PK-37 (K-03) — PERIKSA periode buku hari ini sebelum jurnal & buku saldo kredit ditulis.
    from services.book_date import periksa_periode_dokumen_409
    await periksa_periode_dokumen_409(entity_id, None, jenis="saldo kredit pelanggan")
    if amt < 0:
        avail = await balance(customer_id, entity_id)
        if -amt > avail + EPS:
            raise HTTPException(status_code=400,
                                detail=f"Saldo tidak cukup untuk dikurangi (tersedia {rupiah(avail)})")
    adjust_id = new_id("sca")
    label = f"{customer.get('name', '')} ({'+'if amt>0 else ''}{amt:,.0f})"
    je = await gl_service.post_store_credit_adjust(
        adjust_id=adjust_id, entity_id=entity_id, amount_signed=amt, customer_label=label)
    entry = await _append(
        customer_id=customer_id, entity_id=entity_id, kind="adjust", amount_signed=amt,
        ref_type="adjust", ref_id=adjust_id, ref_number="", note=note or "Penyesuaian manual",
        actor=actor, je_id=(je or {}).get("id", ""), customer_name=customer.get("name", ""))
    return safe_doc(entry)


# ─── Backfill (jaring pengaman: CN store_credit lama tanpa entri ledger) ─────
async def backfill_from_credit_notes() -> int:
    """Idempotent — buat entri ledger `issue` untuk CN store_credit yang GL-nya SUDAH
    mengkredit 2-1450 tetapi belum punya entri ledger (mis. issue() gagal setelah CN posted).
    Menjaga GL 2-1450 selaras ledger BY CONSTRUCTION (tanpa mengubah GL sama sekali).
    CN store_credit lama yang dulu mengkredit Piutang (pra-R5.2) sengaja DILEWATI —
    tak membuat ledger tanpa GL padanannya (hindari drift)."""
    created = 0
    async for cn in db.credit_notes.find({"settlement": "store_credit"}, {"_id": 0}):
        amt = round(float(cn.get("gross_amount", 0) or 0), 2)
        if amt <= EPS or not cn.get("customer_id"):
            continue
        exists = await db.store_credit_ledger.find_one(
            {"type": "issue", "ref_type": "sales_return", "ref_id": cn.get("return_id"),
             "status": {"$ne": "void"}}, {"_id": 0, "id": 1})
        if exists:
            continue
        je = await db.journal_entries.find_one(
            {"source_type": "sales_return", "source_id": cn.get("return_id"), "status": {"$ne": "void"}},
            {"_id": 0, "lines": 1})
        cr_sc = 0.0
        if je:
            cr_sc = round(sum(float(l.get("credit", 0) or 0)
                              for l in je.get("lines", []) if l.get("account_code") == "2-1450"), 2)
        if cr_sc <= EPS:
            continue  # CN lama tanpa GL 2-1450 → lewati (tak buat ledger tanpa padanan GL)
        await issue(customer_id=cn["customer_id"], entity_id=cn.get("entity_id", ""),
                    amount=amt, ref_type="sales_return", ref_id=cn.get("return_id"),
                    ref_number=cn.get("number", ""), note="Backfill store credit dari CN",
                    je_id=cn.get("journal_entry_id", ""), customer_name=cn.get("customer_name", ""))
        created += 1
    return created


# ─── R5.4 Reversals / Koreksi ────────────────────────────────────────────────
def _actor_name(actor: Any) -> str:
    return actor.get("name") if isinstance(actor, dict) else (str(actor) if actor else "system")


async def reverse_redemption(redemption_id: str, *, reason: str = "",
                             actor: Any = None) -> Dict[str, Any]:
    """Batalkan pemakaian (redeem) store credit: kembalikan outstanding order, balik GL redeem
    (Dr Piutang / Cr 2-1450), dan tambahkan kembali saldo ledger. Append-only & idempotent."""
    red = await db.store_credit_redemptions.find_one({"id": redemption_id}, {"_id": 0})
    if not red:
        raise HTTPException(status_code=404, detail="Data pemakaian store credit tidak ditemukan")
    if red.get("status") == "void":
        return safe_doc(red)   # idempotent

    applied_total = round(float(red.get("applied_amount", 0) or 0), 2)
    # Uang muka (pesanan belum berpendapatan saat ditebus) per pesanan — dibaca SEBELUM baris dibalik
    # (pola `posting_registry.post_receipt_void`).
    uang_muka: Dict[str, float] = {}
    for oid in dict.fromkeys(a.get("order_id") for a in red.get("allocations") or [] if a.get("order_id")):
        o = await db.sales_orders.find_one({"id": oid}, {"_id": 0, "payments": 1}) or {}
        adv = round(sum(float(p.get("amount") or 0) for p in o.get("payments") or []
                        if p.get("receipt_id") == redemption_id and p.get("gl_bucket") == gl_service.ADVANCE_BUCKET
                        and float(p.get("amount") or 0) > 0 and not p.get("reverses")), 2)
        if adv > EPS:
            uang_muka[oid] = adv
    # 1) Kembalikan outstanding tiap order yang sempat dilunasi via redemption ini. PK-19 (SL-06) — baris DIBALIK
    #    (baris pembalik bertanggal hari ini), tidak dihapus; periode lalu tidak berubah mundur.
    from services import ar_allocation_service as _aas
    await _aas.reverse(source_id=redemption_id, date=now_iso(), actor=_actor_name(actor),
                       reason=reason or "Pembatalan pemakaian store credit")

    # 2) Balik GL redeem (Dr 1-1200 / Dr 2-1400 uang muka / Cr 2-1450) — idempotent. Uang muka yang SUDAH direklas ke
    #    piutang saat surat jalan dikembalikan dulu ke piutang (Dr 1-1200 / Cr 2-1400), sama dengan batal kwitansi.
    for oid, adv in uang_muka.items():
        o = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
        if o:
            await gl_service.post_durable(
                "store_credit_redemptions", redemption_id,
                lambda o=o, adv=adv: gl_service.post_advance_reclass_reversal(
                    o, redemption_id, adv, label=f"batal {red.get('number', '')}"),
                source_type="advance_reclass_reversal", source_id=f"{oid}:{redemption_id}",
                field="reclass_void_gl_status", raise_on_fail=True)
    rev_jes = await gl_service.reverse_document(
        "store_credit_redeem", redemption_id, reason=reason or "Pembatalan pemakaian store credit",
        actor_name=_actor_name(actor))

    # 3) Tambahkan kembali saldo ledger (entri reversal +applied).
    entry = None
    existing_rev = await db.store_credit_ledger.find_one(
        {"type": "reversal", "ref_type": "redemption_reversal", "ref_id": redemption_id,
         "status": {"$ne": "void"}}, {"_id": 0})
    if existing_rev:
        entry = existing_rev
    elif applied_total > EPS:
        entry = await _append(
            customer_id=red["customer_id"], entity_id=red.get("entity_id", ""), kind="reversal",
            amount_signed=applied_total, ref_type="redemption_reversal", ref_id=redemption_id,
            ref_number=red.get("number", ""), note=reason or "Pembatalan pemakaian store credit",
            actor=actor, je_id=(rev_jes[0]["id"] if rev_jes else ""),
            customer_name=red.get("customer_name", ""))

    # 4) Tandai redemption + entri redeem asal sebagai dibatalkan (audit trail utuh).
    now = now_iso()
    await db.store_credit_redemptions.update_one(
        {"id": redemption_id},
        {"$set": {"status": "void", "reversed": True, "reversed_by": _actor_name(actor),
                  "reversed_at": now, "reversal_reason": reason,
                  "reversal_ledger_entry_id": (entry or {}).get("id", ""), "updated_at": now}})
    await db.store_credit_ledger.update_many(
        {"type": "redeem", "ref_id": redemption_id, "status": {"$ne": "void"}},
        {"$set": {"reversed": True, "reversed_at": now, "reversal_reason": reason,
                  "updated_at": now}})
    return safe_doc(await db.store_credit_redemptions.find_one({"id": redemption_id}, {"_id": 0}))


async def reverse_adjust(entry_id: str, *, reason: str = "", actor: Any = None) -> Dict[str, Any]:
    """Batalkan penyesuaian manual (adjust) store credit: balik GL adjust + entri ledger lawan.
    Guard: pembatalan tak boleh membuat saldo negatif (mis. saldo sudah dipakai). Idempotent."""
    e = await db.store_credit_ledger.find_one({"id": entry_id}, {"_id": 0})
    if not e:
        raise HTTPException(status_code=404, detail="Entri store credit tidak ditemukan")
    if e.get("type") != "adjust":
        raise HTTPException(status_code=400, detail="Hanya entri penyesuaian (adjust) yang didukung di sini")
    if e.get("status") == "void" or e.get("reversed"):
        return safe_doc(e)   # idempotent

    amt = round(float(e.get("amount", 0) or 0), 2)      # bertanda
    customer_id = e["customer_id"]
    entity_id = e.get("entity_id", "")
    # Guard saldo: setelah balik (−amt) saldo tak boleh < 0.
    cur = await balance(customer_id, entity_id)
    if round(cur - amt, 2) < -EPS:
        raise HTTPException(
            status_code=400,
            detail=(f"Tidak bisa membatalkan penyesuaian — saldo akan negatif "
                    f"(tersedia {rupiah(cur)}, perlu {rupiah(amt)}). Kemungkinan saldo sudah dipakai."))

    adjust_id = e.get("ref_id", "")
    rev_jes = await gl_service.reverse_document(
        "store_credit_adjust", adjust_id, reason=reason or "Pembatalan penyesuaian store credit",
        actor_name=_actor_name(actor)) if adjust_id else []

    rev_entry = None
    existing_rev = await db.store_credit_ledger.find_one(
        {"type": "reversal", "ref_type": "adjust_reversal", "ref_id": entry_id,
         "status": {"$ne": "void"}}, {"_id": 0})
    if existing_rev:
        rev_entry = existing_rev
    else:
        rev_entry = await _append(
            customer_id=customer_id, entity_id=entity_id, kind="reversal", amount_signed=-amt,
            ref_type="adjust_reversal", ref_id=entry_id, ref_number=e.get("ref_number", ""),
            note=reason or "Pembatalan penyesuaian store credit", actor=actor,
            je_id=(rev_jes[0]["id"] if rev_jes else ""), customer_name=e.get("customer_name", ""))

    now = now_iso()
    await db.store_credit_ledger.update_one(
        {"id": entry_id},
        {"$set": {"reversed": True, "reversed_at": now, "reversal_reason": reason,
                  "reversal_entry_id": (rev_entry or {}).get("id", ""), "updated_at": now}})
    return safe_doc(rev_entry or e)


async def void_issue_entry(*, return_id: str, reason: str = "", actor: Any = None) -> int:
    """Void entri ledger `issue` yang terbit dari sebuah sales_return (dipakai saat retur di-reversal).
    GL 2-1450 dibalik oleh reversal sales_return itu sendiri → ledger cukup di-void agar selaras.
    Return jumlah entri yang di-void (idempotent)."""
    now = now_iso()
    res = await db.store_credit_ledger.update_many(
        {"type": "issue", "ref_type": "sales_return", "ref_id": return_id, "status": {"$ne": "void"}},
        {"$set": {"status": "void", "reversed": True, "reversed_at": now,
                  "reversal_reason": reason or "Reversal retur sumber",
                  "reversed_by": _actor_name(actor), "updated_at": now}})
    return res.modified_count


async def issued_from_return(return_id: str) -> Dict[str, Any]:
    """Info store credit yang terbit dari sebuah retur (utk guard reversal): total terbit,
    apakah sudah ada pemakaian (saldo turun di bawah nilai terbit)."""
    issue_e = await db.store_credit_ledger.find_one(
        {"type": "issue", "ref_type": "sales_return", "ref_id": return_id, "status": {"$ne": "void"}},
        {"_id": 0})
    if not issue_e:
        return {"has_issue": False, "issued": 0.0, "balance": 0.0, "fully_available": True}
    issued = round(float(issue_e.get("amount", 0) or 0), 2)
    bal = await balance(issue_e["customer_id"], issue_e.get("entity_id", ""))
    return {"has_issue": True, "issued": issued, "balance": bal,
            "fully_available": bal + EPS >= issued, "entry_id": issue_e.get("id", "")}


async def get_entry(entry_id: str) -> Optional[Dict[str, Any]]:
    """Satu baris ledger (dipakai router untuk memeriksa kepemilikan badan usaha)."""
    return await db.store_credit_ledger.find_one({"id": entry_id}, {"_id": 0})


async def reverse_ledger_entry(entry_id: str, *, reason: str = "", actor: Any = None) -> Dict[str, Any]:
    """Dispatcher reversal dari 1 baris ledger (dipakai tombol UI 'Batalkan')."""
    e = await db.store_credit_ledger.find_one({"id": entry_id}, {"_id": 0})
    if not e:
        raise HTTPException(status_code=404, detail="Entri store credit tidak ditemukan")
    if e.get("status") == "void" or e.get("reversed"):
        raise HTTPException(status_code=400, detail="Entri sudah dibatalkan/di-reversal")
    t = e.get("type")
    if t == "adjust":
        return await reverse_adjust(entry_id, reason=reason, actor=actor)
    if t == "redeem":
        return await reverse_redemption(e.get("ref_id", ""), reason=reason, actor=actor)
    if t == "issue":
        raise HTTPException(
            status_code=400,
            detail="Store credit terbit dari retur. Batalkan lewat reversal Retur sumbernya.")
    raise HTTPException(status_code=400, detail=f"Jenis entri '{t}' tidak dapat dibalik.")
