"""PK-05 — Bayar hutang pemasok (faktur langsung atau kontrabon) lewat SATU pintu: niat bayar (`ap_payment_intents`).

Kontrak posting (docs/blueprint/02_STANDAR.md §1):
  0. Cari niat (id tetap dari kunci idempotensi) — selesai → kembalikan hasil tersimpan; menunggu → lanjutkan.
  1. PERIKSA tanpa menulis apa pun: status dokumen, pemegang kontrabon, nominal, rekening, akun & periode jurnal.
  2. NIAT: klaim dokumen sasaran (saga) → sisip niat `pending` berisi rencana alokasi.
  3. EFEK berurutan, tiap langkah idempoten: (a) faktur, (b) kas, (c) dokumen kontrabon.
  4. JURNAL sesudah semua buku pembantu; galat DITANGKAP → `gl_status: failed` (panel Posting Gagal).
  5. SELESAI: niat `done`, klaim dilepas, ringkasan PO disegarkan.
Pemeriksaan hak atas PT dilakukan pemanggil (router) sebelum memanggil layanan ini.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from core_utils import DEFAULT_ENTITY_ID, new_id, now_iso, rupiah, safe_doc, timeline_entry
from db import db

COLL = "ap_payment_intents"
KINDS: Dict[str, Tuple[str, str]] = {
    "vendor_bill": ("vendor_bills", "ap_pay_vendor_bill"),
    "contra_bon": ("contra_bons", "ap_pay_contra_bon"),
}
STEPS = ("intent", "bills", "cash", "document", "journal")
EPS = 0.01


class ApPaymentError(ValueError):
    """Galat bisnis bayar hutang dengan kalimat siap tampil. `status_code` 400 atau 409."""

    def __init__(self, message: str, status_code: int = 400, code: str = "", intent_id: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.intent_id = intent_id

    def detail(self) -> Any:
        if self.code:
            return {"code": self.code, "message": str(self), "intent_id": self.intent_id}
        return str(self)


def _r(v: Any) -> float:
    return round(float(v or 0), 2)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def intent_id_for(kind: str, target_id: str, key: str) -> str:
    return "apn_" + _sha(f"{kind}|{target_id}|{key}")[:24]


def _h(intent_id: str) -> str:
    return intent_id.split("_", 1)[1]


def _request_hash(amount: Optional[float], paid_at: str, bank_account_id: str, method: str) -> str:
    return _sha(json.dumps([None if amount is None else _r(amount), paid_at or "", bank_account_id or "",
                            method or ""]))


async def _entity_name(entity_id: str) -> str:
    e = await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "short_name": 1, "legal_name": 1,
                                                                "name": 1}) or {}
    return e.get("short_name") or e.get("legal_name") or e.get("name") or entity_id


async def _target(kind: str, target_id: str) -> Dict[str, Any]:
    coll = KINDS[kind][0]
    doc = await db[coll].find_one({"id": target_id}, {"_id": 0})
    if not doc:
        raise ApPaymentError("Tagihan tidak ditemukan." if kind == "vendor_bill" else "Kontrabon tidak ditemukan.", 404)
    return doc


# ═════════════════════════════════════════════════════════════════════════════
#  Bacaan pendukung layar
# ═════════════════════════════════════════════════════════════════════════════
async def pending_for(kind: str, target_id: str) -> Optional[Dict[str, Any]]:
    doc = await db[COLL].find_one({"kind": kind, "target_id": target_id, "status": "pending"}, {"_id": 0})
    return safe_doc(doc) if doc else None


async def payable_accounts(kind: str, target_id: str) -> List[Dict[str, Any]]:
    """Rekening kas/bank AKTIF milik PT dokumen (bukan PT aktif pengguna)."""
    from services.bank_service import account_cash_type
    doc = await _target(kind, target_id)
    ent = doc.get("entity_id") or DEFAULT_ENTITY_ID
    rows = await db.bank_accounts.find({"entity_id": ent, "is_active": {"$ne": False}}, {"_id": 0}).sort(
        "name", 1).to_list(200)
    return [{"id": a["id"], "name": a.get("name", ""), "bank_name": a.get("bank_name", ""),
             "account_number": a.get("account_number", ""), "cash_type": account_cash_type(a)} for a in rows]


# ═════════════════════════════════════════════════════════════════════════════
#  1. PERIKSA (tanpa tulisan)
# ═════════════════════════════════════════════════════════════════════════════
async def _check_account(bank_account_id: str, entity_id: str) -> Dict[str, Any]:
    if not bank_account_id:
        raise ApPaymentError("Pilih rekening atau kas sumber pembayaran.", 400)
    acc = await db.bank_accounts.find_one({"id": bank_account_id}, {"_id": 0})
    if not acc or acc.get("is_active") is False or (acc.get("entity_id") or "") != entity_id:
        raise ApPaymentError(f"Rekening itu bukan milik {await _entity_name(entity_id)} atau sudah nonaktif.", 400)
    return acc


async def _preflight(cash_docs: List[Dict[str, Any]], deductions: List[Dict[str, Any]], cb: Optional[Dict[str, Any]]):
    from services import gl_service as gl
    try:
        for c in cash_docs:
            await gl.preflight_cash(c)
        for d in deductions:
            if d.get("posts_gl"):
                await gl.post_contra_bon_deduction(
                    cb_id=cb["id"], deduction_id=d["deduction_id"], entity_id=cb.get("entity_id", ""),
                    kind=d["kind"], amount=d["amount"], dry_run=True)
    except gl.ClosedPeriodError as exc:
        raise ApPaymentError(str(exc), 409) from exc
    except gl.JournalValidationError as exc:
        raise ApPaymentError(f"Pembayaran belum bisa dicatat: {exc}. Tidak ada yang berubah.", 409) from exc


def _cash_doc(*, cid: str, number: str, ref_type: str, ref_id: str, ref_number: str, amount: float,
              entity_id: str, acc: Dict[str, Any], cash_type: str, paid_at: str, category: str, description: str,
              counterparty: str, intent_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": cid, "number": number, "cash_type": cash_type, "direction": "out", "amount": _r(amount),
            "category": category, "description": description, "entity_id": entity_id,
            "owner_entity_id": entity_id, "ref_type": ref_type, "ref_id": ref_id, "ref_number": ref_number,
            "account_id": acc.get("id", ""), "counterparty_name": counterparty, "payment_intent_id": intent_id,
            "txn_date": paid_at or now_iso(), "status": "posted", "created_by": actor.get("name", ""),
            "created_at": now_iso(), "updated_at": now_iso()}


async def _plan_vendor_bill(bill: Dict[str, Any], amount: Optional[float], paid_at: str, bank_account_id: str,
                            method: str, variance: Optional[Dict[str, Any]], iid: str,
                            actor: Dict[str, Any]) -> Dict[str, Any]:
    from services import contra_bon_service as cbs
    from services import payment_variance_service as pvs
    from services.bank_service import account_cash_type
    from services.vendor_bill_service import bill_financials
    if bill.get("status") != "posted":
        raise ApPaymentError(f"Bill status '{bill.get('status')}' belum bisa dibayar (harus posted).", 400)
    amount = _r(amount)
    if amount <= 0:
        raise ApPaymentError("Nominal pembayaran harus > 0", 400)
    holder = await cbs.active_holder_of(bill["id"])
    if holder:
        raise ApPaymentError(
            f"Tagihan {bill.get('bill_number')} sedang dipegang kontrabon {holder.get('number')} "
            f"({cbs.STATUS_LABEL.get(holder.get('status'), holder.get('status'))}). Bayar lewat kontrabon itu, "
            "atau batalkan kontrabonnya dulu.", 409)
    fin = bill_financials(bill)
    assessment = await pvs.assess_bill(bill, amount)
    over = _r(max(0.0, amount - fin["outstanding"]))
    if over > EPS:
        kind_ok = str((variance or {}).get("kind") or "") in ("ap_advance",)
        if assessment["direction"] != pvs.DIR_ROUNDING and not kind_ok:
            raise ApPaymentError(
                f"Pembayaran ({amount}) melebihi sisa hutang ({fin['outstanding']}). Bila memang ingin membayar "
                "lebih, pilih keputusan 'Kelebihan jadi uang muka supplier' (selisih pembayaran).", 400)
    applied = _r(min(amount, fin["outstanding"]))
    ent = bill.get("entity_id") or DEFAULT_ENTITY_ID
    acc = await _check_account(bank_account_id, ent)
    cash_type = account_cash_type(acc)
    h = _h(iid)
    cash = _cash_doc(cid=f"cash_{h}", number="", ref_type="vendor_bill", ref_id=bill["id"],
                     ref_number=bill.get("bill_number", ""), amount=applied, entity_id=ent, acc=acc,
                     cash_type=cash_type, paid_at=paid_at, category="pembelian",
                     description=f"Pembayaran {bill.get('bill_number')} — {bill.get('supplier_name', '')} ({method})",
                     counterparty=bill.get("supplier_name", ""), intent_id=iid, actor=actor)
    adv = None
    if over > EPS:
        adv = _cash_doc(cid=f"cash_{h}a", number="", ref_type="ap_advance", ref_id=bill["id"],
                        ref_number=bill.get("bill_number", ""), amount=over, entity_id=ent, acc=acc,
                        cash_type=cash_type, paid_at=paid_at, category="uang muka supplier",
                        description=(f"Kelebihan bayar {bill.get('bill_number')} — {bill.get('supplier_name', '')} "
                                     "menjadi uang muka"),
                        counterparty=bill.get("supplier_name", ""), intent_id=iid, actor=actor)
    await _preflight([c for c in (cash, adv) if c and c["amount"] > EPS], [], None)
    return {"entity_id": ent, "amount": applied, "advance_amount": over if adv else 0.0, "deduction_total": 0.0,
            "cash_type": cash_type, "acc": acc, "cash": cash if applied > EPS else None, "advance": adv,
            "allocations": [{"bill_id": bill["id"], "bill_number": bill.get("bill_number", ""), "amount": applied,
                             "source": "cash", "payment_entry_id": f"pay_{h}_1", "applied_at": None}]
            if applied > EPS else [],
            "deductions": [], "assessment": assessment, "target_number": bill.get("bill_number", ""),
            "precondition": {"status": "posted"}}


async def _plan_contra_bon(cb: Dict[str, Any], amount: Optional[float], paid_at: str, bank_account_id: str,
                           method: str, iid: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    from services import contra_bon_service as cbs
    from services.bank_service import account_cash_type
    pol = await cbs.policy(cb.get("entity_id", ""))
    allowed = ("approved", "scheduled_payment") if pol["block_pay_before_approval"] \
        else ("verified", "approved", "scheduled_payment")
    if cb["status"] not in allowed:
        raise ApPaymentError(
            f"Kontrabon berstatus '{cbs.STATUS_LABEL.get(cb['status'], cb['status'])}' belum bisa dibayar. "
            + ("Wajib disetujui lebih dulu (kebijakan Pusat Pengaturan)." if pol["block_pay_before_approval"]
               else "Verifikasi 3-way match dulu."), 400)
    stored_outstanding = (cb.get("totals") or {}).get("outstanding")
    cbs.recompute(cb)
    outstanding = cb["totals"]["outstanding"]
    amount = _r(amount) if amount not in (None, "") else outstanding
    if amount < 0:
        raise ApPaymentError("Nominal pembayaran tidak boleh negatif.", 400)
    if amount > outstanding + EPS:
        raise ApPaymentError(f"Nominal {rupiah(amount)} melebihi sisa bersih kontrabon ({rupiah(outstanding)}).", 400)
    if amount <= EPS and outstanding > EPS:
        raise ApPaymentError("Nominal pembayaran harus lebih besar dari nol.", 400)
    first = not (cb.get("payments") or []) and not any(d.get("applied_at") for d in (cb.get("deductions") or []))
    deductions = []
    ded_total = 0.0
    if first:
        for d in (cb.get("deductions") or []):
            amt = _r(d.get("amount"))
            ded_total = _r(ded_total + amt)
            deductions.append({"deduction_id": d["id"], "kind": d.get("kind", ""), "amount": amt,
                               "posts_gl": bool(d.get("posts_gl")), "journal_id": "",
                               "label": f"{cb.get('number')} · {d.get('ref_number') or d.get('label', '')}"})
    # Rencana alokasi: potongan dulu, lalu kas — urutan faktur seperti di dokumen (sama dengan perilaku lama).
    h = _h(iid)
    room = {b["bill_id"]: _r(_r(b.get("applied_amount")) - _r(b.get("settled_amount"))) for b in cb.get("bills", [])}
    allocations: List[Dict[str, Any]] = []
    bills_db = {b["id"]: b async for b in db.vendor_bills.find(
        {"id": {"$in": [b["bill_id"] for b in cb.get("bills", [])]}}, {"_id": 0})}
    extra_paid: Dict[str, float] = {}
    for source, total in (("deduction", ded_total), ("cash", amount)):
        left = _r(total)
        for b in cb.get("bills", []):
            if left <= EPS:
                break
            take = _r(min(room[b["bill_id"]], left))
            if take <= EPS:
                continue
            bill = bills_db.get(b["bill_id"])
            if not bill:
                raise ApPaymentError(f"Tagihan {b.get('bill_number')} di kontrabon ini tidak ditemukan.", 400)
            if bill.get("status") not in ("posted", "paid"):
                raise ApPaymentError(
                    f"Tagihan {bill.get('bill_number')} berstatus '{bill.get('status')}' — tidak bisa dilunasi lewat "
                    "kontrabon. Perbarui daftar faktur kontrabon.", 400)
            paid_after = _r(_r(bill.get("amount_paid")) + extra_paid.get(b["bill_id"], 0) + take)
            if paid_after > _r(bill.get("grand_total")) + EPS:
                raise ApPaymentError(
                    f"Pelunasan {bill.get('bill_number')} melebihi sisa hutang atau tagihan baru berubah. Muat ulang.", 409)
            extra_paid[b["bill_id"]] = _r(extra_paid.get(b["bill_id"], 0) + take)
            room[b["bill_id"]] = _r(room[b["bill_id"]] - take)
            left = _r(left - take)
            allocations.append({"bill_id": b["bill_id"], "bill_number": b.get("bill_number", ""), "amount": take,
                                "source": source, "payment_entry_id": f"pay_{h}_{len(allocations) + 1}",
                                "applied_at": None})
        if left > EPS:
            raise ApPaymentError(f"Sisa {rupiah(left)} tidak bisa dialokasikan — nilai yang dibayar melebihi sisa "
                                 "tagihan di kontrabon ini.", 400)
    ent = cb.get("entity_id") or DEFAULT_ENTITY_ID
    cash = acc = None
    cash_type = ""
    if amount > EPS:
        acc = await _check_account(bank_account_id, ent)
        cash_type = account_cash_type(acc)
        cash = _cash_doc(cid=f"cash_{h}", number="", ref_type="contra_bon", ref_id=cb["id"],
                         ref_number=cb.get("number", ""), amount=amount, entity_id=ent, acc=acc, cash_type=cash_type,
                         paid_at=paid_at, category="pembelian",
                         description=(f"Pembayaran kontrabon {cb.get('number')} — {cb.get('supplier_name', '')} "
                                      f"({len(cb.get('bills') or [])} faktur, {method or 'transfer'})"),
                         counterparty=cb.get("supplier_name", ""), intent_id=iid, actor=actor)
    await _preflight([cash] if cash else [], deductions, cb)
    pre = {"status": cb["status"]}
    if stored_outstanding is not None:
        pre["totals.outstanding"] = stored_outstanding
    return {"entity_id": ent, "amount": amount, "advance_amount": 0.0, "deduction_total": ded_total,
            "cash_type": cash_type, "acc": acc or {}, "cash": cash, "advance": None, "allocations": allocations,
            "deductions": deductions, "assessment": None, "target_number": cb.get("number", ""),
            "precondition": pre}


# ═════════════════════════════════════════════════════════════════════════════
#  Pintu utama
# ═════════════════════════════════════════════════════════════════════════════
async def pay_payable(*, kind: str, target_id: str, actor: Dict[str, Any], amount: Optional[float],
                      paid_at: str = "", bank_account_id: str = "", method: str = "transfer", notes: str = "",
                      idempotency_key: str = "", bank_line_id: str = "",
                      variance: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if kind not in KINDS:
        raise ApPaymentError(f"Jenis dokumen tidak dikenal: {kind}", 400)
    key = idempotency_key or (f"bank_line:{bank_line_id}" if bank_line_id else "") or new_id("acak")
    iid = intent_id_for(kind, target_id, key)
    req_hash = _request_hash(amount, paid_at, bank_account_id, method)
    existing = await db[COLL].find_one({"id": iid}, {"_id": 0})
    if existing:
        if existing.get("request_hash") != req_hash:
            raise ApPaymentError("Permintaan ini memakai kunci yang sama dengan pembayaran lain yang isinya berbeda. "
                                 "Muat ulang lalu ulangi.", 409)
        if existing["status"] == "done":
            return await _result(existing, replayed=True)
        if existing["status"] == "cancelled":
            raise ApPaymentError("Pembayaran dengan kunci ini sudah dibatalkan. Muat ulang lalu ulangi.", 409)
        return await _run(existing, actor)
    other = await pending_for(kind, target_id)
    if other:
        raise ApPaymentError(
            f"Masih ada pembayaran {rupiah(other.get('amount', 0))} untuk dokumen ini yang belum selesai diproses. "
            "Lanjutkan pembayaran itu dulu.", 409, code="AP_PAYMENT_PENDING", intent_id=other["id"])

    doc = await _target(kind, target_id)
    # PM-T1 — cara bayar dari daftar induk (kata lama → kode kanonik; tak dikenal / nonaktif → 400) sebelum niat lahir.
    from services import payment_method_service as _pms
    try:
        method = (await _pms.wajib(doc.get("entity_id") or "", method or "transfer", arah="keluar"))["code"]
    except _pms.CaraBayarError as exc:
        raise ApPaymentError(str(exc), 400) from exc
    if kind == "vendor_bill":
        plan = await _plan_vendor_bill(doc, amount, paid_at, bank_account_id, method, variance, iid, actor)
    else:
        plan = await _plan_contra_bon(doc, amount, paid_at, bank_account_id, method, iid, actor)

    # 2. NIAT — klaim dokumen sasaran lalu sisip niat
    from services import atomic_claim as _saga
    coll, action = KINDS[kind]
    try:
        claimed = await _saga.claim(coll, target_id, action, precondition=plan["precondition"],
                                   actor=actor.get("name", ""))
    except HTTPException as exc:
        msg = exc.detail.get("message") if isinstance(exc.detail, dict) else str(exc.detail)
        raise ApPaymentError(msg, 409) from exc
    token = claimed[_saga.LOCK]["token"]
    ent = plan["entity_id"]
    cash, adv = plan["cash"], plan["advance"]
    # AG-T5 — pembayaran dari kartu tindakan asisten: id kartu menempel di niat, kas, dan catatan bayar dokumen.
    from ai_card_context import card_field
    kartu = card_field()
    for c in (cash, adv):
        if c:
            c.update(kartu)
    from services import cash_ledger
    try:
        if cash:
            cash["number"] = await cash_ledger.next_cash_number(ent)   # PK-20 — satu pemberi nomor kas
        if adv:
            adv["number"] = await cash_ledger.next_cash_number(ent)
        intent = {
            "id": iid, "entity_id": ent, "kind": kind, "target_id": target_id, "target_number": plan["target_number"],
            "request_hash": req_hash, "idempotency_key": idempotency_key, "amount": plan["amount"],
            "advance_amount": plan["advance_amount"], "deduction_total": plan["deduction_total"],
            "paid_at": paid_at or now_iso(), "bank_account_id": bank_account_id, "cash_type": plan["cash_type"],
            "method": method or "transfer", "notes": notes, "bank_line_id": bank_line_id,
            "allocations": plan["allocations"], "deductions": plan["deductions"],
            "cash_txn_id": cash["id"] if cash else "", "cash_txn_number": cash["number"] if cash else "",
            "advance_cash_txn_id": adv["id"] if adv else "", "advance_cash_txn_number": adv["number"] if adv else "",
            "cash_doc": cash, "advance_cash_doc": adv, "assessment": plan["assessment"], "variance": variance or {},
            "status": "pending", "step": "intent", "gl_status": "pending", "gl_error": "", "lock_token": token,
            "error": "", "attempts": 0, "variance_decision_id": "", "created_by": actor.get("name", ""),
            "created_by_id": actor.get("id", ""), "created_at": now_iso(), "updated_at": now_iso(), "done_at": "",
            **kartu,
        }
        await db[COLL].insert_one(dict(intent))
    except Exception:
        await _saga.release(coll, target_id, token)
        raise
    return await _run(intent, actor)


async def resume(intent_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    from services import atomic_claim as _saga
    intent = await db[COLL].find_one({"id": intent_id}, {"_id": 0})
    if not intent:
        raise ApPaymentError("Pembayaran tidak ditemukan.", 404)
    if intent["status"] != "pending":
        raise ApPaymentError("Pembayaran ini tidak sedang menunggu (sudah selesai atau dibatalkan).", 409)
    coll, action = KINDS[intent["kind"]]
    tgt = await db[coll].find_one({"id": intent["target_id"]}, {"_id": 0, _saga.LOCK: 1}) or {}
    lock = tgt.get(_saga.LOCK)
    if not lock:   # dilepas admin lewat Kunci Saga → klaim ulang tanpa syarat sisa
        try:
            claimed = await _saga.claim(coll, intent["target_id"], action, actor=actor.get("name", ""))
        except HTTPException as exc:
            raise ApPaymentError("Dokumen sedang diproses aksi lain. Muat ulang lalu ulangi.", 409) from exc
        intent["lock_token"] = claimed[_saga.LOCK]["token"]
        await db[COLL].update_one({"id": intent_id}, {"$set": {"lock_token": intent["lock_token"]}})
    elif lock.get("token") != intent.get("lock_token"):
        raise ApPaymentError("Dokumen sedang diproses aksi lain. Muat ulang lalu ulangi.", 409)
    return await _run(intent, actor)


async def cancel(intent_id: str, actor: Dict[str, Any], reason: str) -> Dict[str, Any]:
    from services import atomic_claim as _saga
    if len((reason or "").strip()) < 5:
        raise ApPaymentError("Alasan pembatalan wajib (min. 5 karakter).", 400)
    intent = await db[COLL].find_one({"id": intent_id}, {"_id": 0})
    if not intent:
        raise ApPaymentError("Pembayaran tidak ditemukan.", 404)
    if intent["status"] != "pending" or intent.get("step") != "intent" \
            or any(a.get("applied_at") for a in intent.get("allocations", [])):
        raise ApPaymentError("Pembayaran ini sudah mengubah kas atau hutang, jadi tidak bisa dibatalkan. "
                             "Lanjutkan sampai selesai.", 409)
    await _cancel_intent(intent, f"dibatalkan {actor.get('name', '')}: {reason.strip()}")
    return safe_doc(await db[COLL].find_one({"id": intent_id}, {"_id": 0}))


async def _cancel_intent(intent: Dict[str, Any], why: str) -> None:
    from services import atomic_claim as _saga
    coll = KINDS[intent["kind"]][0]
    await db[COLL].update_one({"id": intent["id"], "status": "pending"}, {"$set": {
        "status": "cancelled", "error": why, "updated_at": now_iso(), "cancelled_at": now_iso()}})
    await _saga.release(coll, intent["target_id"], intent.get("lock_token", ""))


# ═════════════════════════════════════════════════════════════════════════════
#  3–5. Langkah efek, jurnal, selesai — tiap fungsi idempoten
# ═════════════════════════════════════════════════════════════════════════════
class _FirstAllocationRejected(Exception):
    pass


async def _set_step(intent: Dict[str, Any], step: str) -> None:
    intent["step"] = step
    await db[COLL].update_one({"id": intent["id"]}, {"$set": {"step": step, "error": "", "updated_at": now_iso()}})


async def _apply_allocations(intent: Dict[str, Any], actor: Dict[str, Any]) -> None:
    from pymongo import ReturnDocument
    statuses = ["posted"] if intent["kind"] == "vendor_bill" else ["posted", "paid"]
    applied_any = any(a.get("applied_at") for a in intent["allocations"])
    for idx, al in enumerate(intent["allocations"]):
        if al.get("applied_at"):
            continue
        pid, amt = al["payment_entry_id"], _r(al["amount"])
        via_cb = intent["kind"] == "contra_bon"
        entry = {"id": pid, "amount": amt,
                 "method": ("kontrabon" if al["source"] == "cash" else "kontrabon:deduction") if via_cb
                 else intent.get("method", "transfer"),
                 "cash_txn_id": intent.get("cash_txn_id", "") if al["source"] == "cash" else "",
                 "cash_txn_number": intent.get("cash_txn_number", "") if al["source"] == "cash" else "",
                 "cash_type": intent.get("cash_type", ""), "notes": intent.get("notes", ""),
                 "payment_intent_id": intent["id"], "paid_by": actor.get("name", ""), "paid_at": intent["paid_at"]}
        if intent.get("ai_card_id"):   # AG-T5
            entry["ai_card_id"] = intent["ai_card_id"]
        if via_cb:
            entry.update({"contra_bon_id": intent["target_id"], "contra_bon_number": intent["target_number"],
                          "notes": f"Pelunasan lewat kontrabon {intent['target_number']}"
                                   + ("" if al["source"] == "cash" else " (potongan non-kas)")})
        note = (f"{rupiah(amt)} · {intent['target_number']}" + ("" if al["source"] == "cash" else " (potongan)")) \
            if via_cb else f"{rupiah(amt)} via {intent.get('method')} ({intent.get('cash_type')})"
        res = await db.vendor_bills.find_one_and_update(
            {"id": al["bill_id"], "status": {"$in": statuses}, "payments.id": {"$ne": pid},
             "$expr": {"$lte": [{"$add": [{"$ifNull": ["$amount_paid", 0]}, amt]},
                                {"$add": [{"$ifNull": ["$grand_total", 0]}, EPS]}]}},
            {"$inc": {"amount_paid": amt}, "$set": {"updated_at": now_iso()},
             "$push": {"payments": entry, "timeline": timeline_entry(
                 "paid", "Pelunasan lewat kontrabon" if via_cb else "Pembayaran dicatat", actor.get("name", ""),
                 note)}},
            projection={"_id": 0}, return_document=ReturnDocument.AFTER)
        if not res:
            already = await db.vendor_bills.find_one({"id": al["bill_id"], "payments.id": pid}, {"_id": 0, "id": 1})
            if not already:
                if not applied_any:
                    raise _FirstAllocationRejected(al["bill_number"])
                raise ApPaymentError(f"Pelunasan {al['bill_number']} ditolak: sisa hutang berubah. "
                                     "Lanjutkan pembayaran ini sesudah memeriksa tagihannya.", 409)
        elif _r(res.get("amount_paid")) + EPS >= _r(res.get("grand_total")) and res.get("status") != "paid":
            await db.vendor_bills.update_one({"id": al["bill_id"]}, {"$set": {"status": "paid"}})
        al["applied_at"] = now_iso()
        applied_any = True
        await db[COLL].update_one({"id": intent["id"]}, {"$set": {f"allocations.{idx}.applied_at": al["applied_at"],
                                                                  "updated_at": now_iso()}})


async def _insert_cash(intent: Dict[str, Any]) -> None:
    """PK-20 — langkah sisip kas lewat pembuat kas satu pintu (`cash_ledger.create_cash`) dengan id turunan niat
    (`txn_id`) dan nomor yang sudah dipesan saat niat lahir. Pembuat kas langsung menjurnal kasnya (pintu tahan-gagal);
    jurnal gagal → kas tersimpan `failed`, langkah ini tetap selesai dan langkah jurnal mencatat peringatannya."""
    from services import cash_ledger
    for c in (intent.get("cash_doc"), intent.get("advance_cash_doc")):
        if not c or _r(c.get("amount")) <= EPS:
            continue
        tambahan = {k: c[k] for k in ("number", "ref_number", "counterparty_name", "payment_intent_id", "ai_card_id")
                    if c.get(k)}
        try:
            await cash_ledger.create_cash(
                entity_id=c["entity_id"], direction=c.get("direction") or "out", amount=_r(c["amount"]),
                ref_type=c["ref_type"], ref_id=c["ref_id"], account_id=c.get("account_id", ""),
                cash_type=c.get("cash_type", ""), txn_date=c.get("txn_date", ""), category=c.get("category", ""),
                description=c.get("description", ""), actor=c.get("created_by", "") or "system",
                owner_entity_id=c.get("owner_entity_id", ""), txn_id=c["id"], extra=tambahan)
        except cash_ledger.CashPostingError:
            intent.setdefault("_kas_gagal", set()).add(c["id"])   # jangan dicoba ulang di langkah jurnal putaran ini


async def _update_document(intent: Dict[str, Any], actor: Dict[str, Any]) -> None:
    if intent["kind"] != "contra_bon":
        return
    from services import contra_bon_service as cbs
    cb = await db.contra_bons.find_one({"id": intent["target_id"]}, {"_id": 0})
    if not cb:
        raise ApPaymentError("Kontrabon tidak ditemukan.", 404)
    pay_id = f"cbp_{_h(intent['id'])}"
    if any(p.get("id") == pay_id for p in (cb.get("payments") or [])):
        return
    ded_ids = {d["deduction_id"] for d in intent.get("deductions", [])}
    if intent["amount"] <= EPS and ded_ids and all(
            d.get("applied_at") for d in (cb.get("deductions") or []) if d.get("id") in ded_ids):
        return
    per_bill: Dict[str, float] = {}
    for al in intent["allocations"]:
        per_bill[al["bill_id"]] = _r(per_bill.get(al["bill_id"], 0) + al["amount"])
    for b in cb.get("bills", []):
        if b["bill_id"] in per_bill:
            b["settled_amount"] = _r(_r(b.get("settled_amount")) + per_bill[b["bill_id"]])
    for d in (cb.get("deductions") or []):
        if d.get("id") in ded_ids and not d.get("applied_at"):
            d["applied_at"] = now_iso()
            d["applied_by"] = actor.get("name", "")
    if intent["amount"] > EPS:
        cb.setdefault("payments", []).append({
            "id": pay_id, "amount": intent["amount"], "method": intent.get("method") or "transfer",
            "cash_type": intent.get("cash_type", ""), "cash_txn_id": intent.get("cash_txn_id", ""),
            "cash_txn_number": intent.get("cash_txn_number", ""), "bank_account_id": intent.get("bank_account_id", ""),
            "bank_line_id": intent.get("bank_line_id", ""), "notes": intent.get("notes", ""),
            "payment_intent_id": intent["id"], "paid_by": actor.get("name", ""), "paid_at": intent["paid_at"],
            "allocations": [{"bill_id": a["bill_id"], "bill_number": a["bill_number"], "amount": a["amount"],
                             "source": "cash"} for a in intent["allocations"] if a["source"] == "cash"],
            **({"ai_card_id": intent["ai_card_id"]} if intent.get("ai_card_id") else {})})
    cbs.recompute(cb)
    if cb["totals"]["outstanding"] <= EPS:
        cb["status"] = "paid"
        cb["paid_at"] = now_iso()
    ded_total = intent.get("deduction_total", 0)
    cb.setdefault("timeline", []).append(cbs._tl(
        "dibayar", "Pembayaran dicatat", actor.get("name", ""),
        f"{rupiah(intent['amount'])}" + (f" + potongan {rupiah(ded_total)}" if ded_total > EPS else "")
        + (f" · kas {intent['cash_txn_number']}" if intent.get("cash_txn_number") else " · tanpa kas (habis dipotong)")))
    fields = {k: cb[k] for k in ("bills", "deductions", "payments", "totals", "status", "timeline") if k in cb}
    if cb.get("paid_at"):
        fields["paid_at"] = cb["paid_at"]
    fields["updated_at"] = now_iso()
    res = await db.contra_bons.update_one(
        {"id": cb["id"], "saga_lock.token": intent.get("lock_token"), "payments.id": {"$ne": pay_id}},
        {"$set": fields, "$inc": {"version": 1}})
    if res.matched_count == 0:
        raise ApPaymentError("Kontrabon ini baru saja diubah orang lain. Muat ulang lalu ulangi.", 409)


async def _post_journals(intent: Dict[str, Any]) -> None:
    from services import gl_service as gl
    errors: List[str] = []
    if intent["kind"] == "contra_bon" and intent.get("deductions"):
        ded_err = ""
        for i, d in enumerate(intent["deductions"]):
            if not d.get("posts_gl"):
                continue
            try:
                je = await gl.post_contra_bon_deduction(
                    cb_id=intent["target_id"], deduction_id=d["deduction_id"], entity_id=intent["entity_id"],
                    kind=d["kind"], amount=d["amount"], label=d.get("label", ""))
                if je:
                    await db[COLL].update_one({"id": intent["id"]},
                                              {"$set": {f"deductions.{i}.journal_id": je.get("id", "")}})
            except Exception as exc:  # noqa: BLE001 — jurnal gagal tidak membatalkan pembayaran (§1 P4)
                ded_err = str(exc)[:300]
        await db.contra_bons.update_one({"id": intent["target_id"]}, {"$set": {
            "gl_status": "failed" if ded_err else "posted", "gl_error": ded_err, "updated_at": now_iso()}})
        if ded_err:
            errors.append(ded_err)
    from services import cash_ledger
    for cid in (intent.get("cash_txn_id"), intent.get("advance_cash_txn_id")):
        if not cid:
            continue
        cash = await db.cash_transactions.find_one({"id": cid}, {"_id": 0})
        if not cash:
            continue
        if cid in intent.get("_kas_gagal", ()):   # PK-20 — baru saja gagal di pembuat kas: penandanya sudah tertulis
            errors.append((cash.get("gl_error") or "jurnal kas gagal")[:300])
            continue
        try:
            await cash_ledger.ensure_posted(cid)
        except cash_ledger.CashPostingError as exc:  # kas sudah ditandai gagal oleh pintu tahan-gagal
            errors.append(exc.error[:300])
    intent.pop("_kas_gagal", None)
    await db[COLL].update_one({"id": intent["id"]}, {"$set": {
        "gl_status": "failed" if errors else "posted", "gl_error": "; ".join(errors)[:500], "updated_at": now_iso()}})


async def _finish(intent: Dict[str, Any]) -> None:
    from services import atomic_claim as _saga
    from services.vendor_bill_service import sync_po_billing
    coll = KINDS[intent["kind"]][0]
    await db[COLL].update_one({"id": intent["id"]}, {"$set": {"status": "done", "done_at": now_iso(),
                                                              "error": "", "updated_at": now_iso()}})
    await _saga.release(coll, intent["target_id"], intent.get("lock_token", ""))
    bill_ids = list({a["bill_id"] for a in intent["allocations"]})
    po_ids = {b.get("po_id") async for b in db.vendor_bills.find({"id": {"$in": bill_ids}}, {"_id": 0, "po_id": 1})}
    for pid in po_ids:
        if pid:
            await sync_po_billing(pid)
    if intent.get("cash_txn_id"):
        from services import doc_refs_service as refs
        await refs.safe_link((intent["kind"], intent["target_id"]), ("cash_transaction", intent["cash_txn_id"]),
                             "settles", note="pembayaran hutang")


async def _run(intent: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    from services import atomic_claim as _saga
    coll = KINDS[intent["kind"]][0]
    await db[COLL].update_one({"id": intent["id"]}, {"$inc": {"attempts": 1}})
    try:
        if intent["step"] == "intent":
            try:
                await _apply_allocations(intent, actor)
            except _FirstAllocationRejected:
                await _cancel_intent(intent, "alokasi pertama ditolak: sisa hutang tidak cukup")
                raise ApPaymentError("Pembayaran gagal — sisa hutang tidak cukup atau bill baru saja berubah "
                                     "(kemungkinan pembayaran paralel). Muat ulang lalu coba lagi.", 409)
            await _set_step(intent, "bills")
        if intent["step"] == "bills":
            await _insert_cash(intent)
            await _set_step(intent, "cash")
        if intent["step"] == "cash":
            await _update_document(intent, actor)
            await _set_step(intent, "document")
        if intent["step"] == "document":
            await _post_journals(intent)
            await _set_step(intent, "journal")
    except Exception as exc:
        fresh = await db[COLL].find_one({"id": intent["id"]}, {"_id": 0, "status": 1})
        if (fresh or {}).get("status") == "pending":
            await db[COLL].update_one({"id": intent["id"]}, {"$set": {"error": str(exc)[:500],
                                                                      "updated_at": now_iso()}})
            await _saga.mark_failed(coll, intent["target_id"], f"niat bayar {intent['id']}: {exc}")
        raise
    await _finish(intent)
    return await _result(await db[COLL].find_one({"id": intent["id"]}, {"_id": 0}), replayed=False)


async def _result(intent: Dict[str, Any], *, replayed: bool) -> Dict[str, Any]:
    cash = await db.cash_transactions.find_one({"id": intent.get("cash_txn_id")}, {"_id": 0}) \
        if intent.get("cash_txn_id") else None
    adv = await db.cash_transactions.find_one({"id": intent.get("advance_cash_txn_id")}, {"_id": 0}) \
        if intent.get("advance_cash_txn_id") else None
    warning = ""
    if intent.get("gl_status") == "failed":
        warning = (f"Pembayaran tercatat, tetapi jurnalnya belum terbit: {intent.get('gl_error') or 'galat'}. "
                   "Buka Keuangan › Posting Gagal untuk mengulang.")
    return {"intent": safe_doc(intent), "cash_transaction": safe_doc(cash) if cash else None,
            "advance_cash": safe_doc(adv) if adv else None, "replayed": replayed, "warning": warning}


def intent_summary(intent: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": intent.get("id"), "status": intent.get("status"), "step": intent.get("step"),
            "gl_status": intent.get("gl_status"), "cash_txn_number": intent.get("cash_txn_number", ""),
            "amount": intent.get("amount", 0)}


async def refresh_gl_status(intent_id: str) -> str:
    intent = await db[COLL].find_one({"id": intent_id}, {"_id": 0})
    if not intent:
        return ""
    ok = True
    for cid in (intent.get("cash_txn_id"), intent.get("advance_cash_txn_id")):
        if cid:
            c = await db.cash_transactions.find_one({"id": cid}, {"_id": 0, "gl_status": 1}) or {}
            ok = ok and c.get("gl_status") in ("posted", "not_required")
    if intent["kind"] == "contra_bon" and any(d.get("posts_gl") for d in intent.get("deductions", [])):
        cb = await db.contra_bons.find_one({"id": intent["target_id"]}, {"_id": 0, "gl_status": 1}) or {}
        ok = ok and cb.get("gl_status") == "posted"
    st = "posted" if ok else "failed"
    await db[COLL].update_one({"id": intent_id}, {"$set": {"gl_status": st, **({"gl_error": ""} if ok else {}),
                                                           "updated_at": now_iso()}})
    return st


async def repost_journals(intent_id: str) -> Dict[str, Any]:
    """Ulang HANYA jurnal yang kurang (idempoten). Dipakai panel Posting Gagal."""
    intent = await db[COLL].find_one({"id": intent_id}, {"_id": 0})
    if not intent:
        raise ApPaymentError("Pembayaran tidak ditemukan.", 404)
    await _post_journals(intent)
    await refresh_gl_status(intent_id)
    return safe_doc(await db[COLL].find_one({"id": intent_id}, {"_id": 0}))


async def repost_contra_bon(cb_id: str) -> None:
    """Panel Posting Gagal jenis `contra_bon`: ulang jurnal potongan lewat niat-niat kontrabon itu."""
    found = False
    async for it in db[COLL].find({"kind": "contra_bon", "target_id": cb_id, "status": "done"}, {"_id": 0, "id": 1}):
        found = True
        await repost_journals(it["id"])
    if not found:
        raise ApPaymentError("Tidak ada pembayaran kontrabon ini yang bisa diulang jurnalnya.", 404)
    cb = await db.contra_bons.find_one({"id": cb_id}, {"_id": 0, "gl_status": 1, "gl_error": 1}) or {}
    if cb.get("gl_status") == "failed":
        raise ApPaymentError(cb.get("gl_error") or "jurnal potongan masih gagal", 409)
