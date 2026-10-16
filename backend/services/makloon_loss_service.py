"""L01 (keputusan owner 2026-10-16) — SUSUT / HILANG BAHAN DI MITRA untuk MKO batal.

Bahan yang tidak kembali dari mitra dicatat per roll:
  * Dalam toleransi wajar → beban perusahaan otomatis: Dr 5-9500 / Cr 1-1350 WIP.
  * Di atas toleransi → WAJIB persetujuan; sesudah disetujui kelebihannya jadi klaim ke
    mitra (Dr 1-1260 Piutang Klaim Mitra) dan bagian dalam toleransi tetap beban.
Toleransi = `step.tolerance_pct` (kontrak mitra × jenis proses → fallback pengaturan kontrak).
Hak terpisah: `makloon_order.record_loss` (catat) dan `makloon_order.approve_loss` (setujui);
pencatat tidak boleh menyetujui catatannya sendiri.
"""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core_utils import new_id, now_iso, safe_doc
from db import db
from services import atomic_claim as _claim
from services import gl_service as gl
from services import stock_bucket_service as sb

EPS = 1e-6


def _find_step(order: Dict[str, Any], seq: int) -> Dict[str, Any]:
    for s in order.get("steps", []):
        if int(s.get("seq", 0)) == int(seq):
            return s
    raise HTTPException(status_code=404, detail=f"Step {seq} tidak ada pada order")


def _posted_value(step: Dict[str, Any]) -> float:
    rets = sum(float(r.get("value") or 0) for r in step.get("material_returns") or [])
    loss = sum(float(x.get("value") or 0) for x in step.get("material_losses") or [] if x["status"] == "posted")
    return rets + loss


def _tol_used(step: Dict[str, Any]) -> float:
    return sum(float(x.get("within_qty") or 0) for x in step.get("material_losses") or []
               if x["status"] in ("posted", "pending_approval"))


async def _locked(mko_id: str, actor: str, fn):
    order = await _claim.claim("makloon_orders", mko_id, "material_loss", precondition={"status": "cancelled"},
                               actor=actor)
    token = (order.pop(_claim.LOCK, None) or {}).get("token", "")
    try:
        return await fn(order)
    finally:
        await _claim.release("makloon_orders", mko_id, token)


def _issued_total(step: Dict[str, Any], at_partner: float) -> float:
    lost = sum(float(x.get("qty") or 0) for x in step.get("material_losses") or [] if x["status"] == "posted")
    return float(step.get("returned_qty") or 0) + at_partner + lost


async def deductible_bills(mko_id: str, seq: int) -> List[Dict[str, Any]]:
    """Tagihan jasa mitra yang masih terbuka (badan usaha sama) — bisa dipotong klaim susut."""
    order = await db.makloon_orders.find_one({"id": mko_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order makloon tidak ditemukan.")
    step = _find_step(order, seq)
    rows = await db.vendor_bills.find(
        {"makloon_id": step.get("makloon_id") or "__none__", "entity_id": order.get("entity_id"),
         "status": {"$in": ["posted", "approved"]}},
        {"_id": 0, "id": 1, "bill_number": 1, "grand_total": 1, "amount_paid": 1, "status": 1, "mko_id": 1}
    ).sort("created_at", -1).to_list(100)
    out = []
    for b in rows:
        b["remaining"] = round(float(b.get("grand_total") or 0) - float(b.get("amount_paid") or 0), 2)
        if b["remaining"] > EPS:
            out.append(b)
    return out


async def _deduct(bill_id: str, amount: float, actor: str, reason: str, mko_id: str, seq: int, loss_id: str) -> None:
    ok = await db.vendor_bills.find_one_and_update(
        {"id": bill_id, "status": {"$in": ["posted", "approved"]},
         "$expr": {"$lte": [{"$add": [{"$ifNull": ["$amount_paid", 0]}, amount]},
                            {"$add": [{"$ifNull": ["$grand_total", 0]}, 0.01]}]}},
        {"$inc": {"net_amount": -amount, "grand_total": -amount, "claim_deduction": amount},
         "$set": {"updated_at": now_iso()},
         "$push": {"deductions": {"at": now_iso(), "amount": amount, "by": actor, "reason": reason,
                                  "mko_id": mko_id, "step_seq": seq, "loss_id": loss_id}}})
    if ok and ok.get("outstanding") is not None:
        await db.vendor_bills.update_one({"id": bill_id}, {"$inc": {"outstanding": -amount}})
    if not ok:
        raise HTTPException(status_code=409, detail="Sisa tagihan jasa tidak cukup untuk dipotong (atau baru "
                                                    "berubah). Pilih tagihan lain atau tagih ganti rugi.")


async def _undeduct(bill_id: str, amount: float, loss_id: str) -> None:
    if amount > EPS:
        await db.vendor_bills.update_one({"id": bill_id, "outstanding": {"$exists": True}},
                                         {"$inc": {"outstanding": amount}})
        await db.vendor_bills.update_one({"id": bill_id}, {
            "$inc": {"net_amount": amount, "grand_total": amount, "claim_deduction": -amount},
            "$set": {"updated_at": now_iso()},
            "$push": {"deductions": {"at": now_iso(), "amount": -amount, "loss_id": loss_id,
                                     "reason": "koreksi potongan susut (qty aktual lebih kecil)"}}})


async def _execute(order: Dict[str, Any], step: Dict[str, Any], loss: Dict[str, Any], actor: str,
                   settle: str = "tagih_ganti", bill_id: str = "") -> None:
    remaining_qty = await sb.subcon_qty_by_ref(step["issue_ref"])
    remaining_value = round(float(step.get("material_value") or 0) - _posted_value(step), 2)
    est_value = remaining_value if loss["qty"] >= remaining_qty - EPS else (
        round(remaining_value * float(loss["qty"]) / remaining_qty, 2) if remaining_qty else 0.0)
    est_claim = round(est_value * float(loss["over_qty"]) / float(loss["qty"]), 2) if loss["qty"] else 0.0
    if settle == "potong_bon":   # potong DULU (batas atas), dikoreksi sesudah qty aktual diketahui
        await _deduct(bill_id, est_claim, actor, loss.get("reason", ""), order["id"], int(step["seq"]), loss["id"])
    moved = await sb.consume_subcon_by_ref(step["issue_ref"], "subcon_loss", roll_ids=loss["roll_ids"])
    qty = float(moved.get("consumed_qty") or 0)
    if qty <= EPS:
        if settle == "potong_bon":
            await _undeduct(bill_id, est_claim, loss["id"])
        raise HTTPException(status_code=409, detail="Roll yang dicatat hilang sudah tidak berada di mitra "
                                                    "(mungkin sudah diretur). Catat ulang.")
    left = await sb.subcon_qty_by_ref(step["issue_ref"])
    value = remaining_value if left <= EPS else round(remaining_value * qty / remaining_qty, 2)
    within_qty = min(float(loss["within_qty"]), qty)
    within_value = round(value * within_qty / qty, 2)
    claim_value = round(value - within_value, 2)
    if settle == "potong_bon":
        if claim_value > est_claim + 0.01:   # pembulatan — jangan pernah memotong melebihi yang diklaim
            claim_value, within_value = est_claim, round(value - est_claim, 2)
        await _undeduct(bill_id, round(est_claim - claim_value, 2), loss["id"])
    je = await gl.post_makloon_material_loss(
        mko_id=order["id"], step_seq=int(step["seq"]), part=loss["id"], entity_id=order["entity_id"],
        expense=within_value, claim=claim_value, label=f"{order.get('mko_number')} step{step['seq']}",
        claim_account=gl.ACC_HUTANG if settle == "potong_bon" else "")
    loss.update({"settle": settle if claim_value > EPS else "", "bill_id": bill_id if settle == "potong_bon" else ""})
    step["material_value_open"] = round(remaining_value - value, 2)
    loss.update({"status": "posted", "qty": round(qty, 2), "within_qty": round(within_qty, 2),
                 "over_qty": round(qty - within_qty, 2), "value": value, "expense_value": within_value,
                 "claim_value": claim_value, "consumed_roll_ids": moved.get("roll_ids", []),
                 "journal_id": (je or {}).get("id", ""), "posted_at": now_iso(), "posted_by": actor})
    if left <= EPS:
        step.update({"status": "returned", "awaiting_return": False, "returned_at": now_iso(),
                     "return_reason": "ditutup dengan susut/hilang di mitra", "returned_by": actor})
    order["material_at_partner"] = any(s.get("awaiting_return") for s in order.get("steps", []))
    order.setdefault("timeline", []).append({
        "at": now_iso(), "event": "material_loss",
        "note": f"Step {step['seq']}: susut/hilang {round(qty, 2)} {step.get('input_unit') or ''} di "
                f"{step.get('makloon_name') or 'mitra'} — beban {within_value:,.0f}, "
                + (f"potong tagihan jasa {bill_id} {claim_value:,.0f}" if settle == "potong_bon" else f"klaim mitra {claim_value:,.0f}")})


async def _split_partial_losses(step: Dict[str, Any], partial: List[Dict[str, Any]], pending: set) -> List[str]:
    """L04 (keputusan owner 2026-10-16) — susut SEBAGIAN panjang roll: potong jadi roll anak yang tetap di mitra
    (bucket sama), lalu roll anak itulah yang dicatat susut. Validasi semua dulu sebelum memecah."""
    plan = []
    for p in partial:
        rid, q = str(p.get("roll_id") or ""), round(float(p.get("qty") or 0), 2)
        r = await db.inventory_rolls.find_one({"id": rid, "bucket_ref.id": step["issue_ref"], "status": "subcon"},
                                              {"_id": 0, "length_remaining": 1})
        if not r or rid in pending:
            raise HTTPException(status_code=409, detail="Roll yang dipilih tidak (lagi) berada di mitra atau sedang menunggu persetujuan.")
        if q <= 0 or q > float(r["length_remaining"]) + EPS:
            raise HTTPException(status_code=400, detail=f"Qty susut sebagian harus > 0 dan ≤ sisa roll {r['length_remaining']:g}.")
        plan.append((rid, q, q >= float(r["length_remaining"]) - EPS))
    out = []
    for rid, q, whole in plan:
        if whole:
            out.append(rid)
            continue
        child = await sb.split_off_from_ref(step["issue_ref"], rid, q, movement_type="subcon_split", keep_in_bucket=True)
        if not child:
            raise HTTPException(status_code=409, detail="Roll berubah bersamaan — muat ulang lalu coba lagi.")
        out.append(child["id"])
    return out


async def record_loss(mko_id: str, seq: int, *, roll_ids: Optional[List[str]], reason: str,
                      actor: Dict[str, Any], partial: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    if len((reason or "").strip()) < 5:
        raise HTTPException(status_code=400, detail="Keterangan susut/hilang wajib (min. 5 karakter).")
    name = actor.get("name", "")

    async def run(order):
        step = _find_step(order, seq)
        if step.get("status") != "issued" or not step.get("awaiting_return"):
            raise HTTPException(status_code=409, detail=f"Langkah {seq} tidak punya bahan yang masih di mitra.")
        pending = {r for x in step.get("material_losses") or [] if x["status"] == "pending_approval" for r in x["roll_ids"]}
        q: Dict[str, Any] = {"bucket_ref.id": step["issue_ref"], "status": "subcon"}
        ids = list(roll_ids) if roll_ids is not None else None
        if partial is not None:
            pids = [str(p.get("roll_id") or "") for p in partial]
            if len(set(pids + (ids or []))) != len(pids) + len(ids or []):
                raise HTTPException(status_code=400, detail="Satu roll hanya boleh muncul sekali (pilih utuh ATAU sebagian).")
            ids = (ids or []) + await _split_partial_losses(step, partial, pending)
        if ids is not None:
            if not ids:
                raise HTTPException(status_code=400, detail="Pilih minimal satu roll yang susut/hilang.")
            q["id"] = {"$in": ids}
        rolls = [r for r in await db.inventory_rolls.find(q, {"_id": 0, "id": 1, "length_remaining": 1}).to_list(5000)
                 if r["id"] not in pending]
        if not rolls:
            raise HTTPException(status_code=409, detail="Roll yang dipilih tidak (lagi) berada di mitra atau sedang menunggu persetujuan.")
        qty = round(sum(float(r.get("length_remaining") or 0) for r in rolls), 2)
        at_partner = await sb.subcon_qty_by_ref(step["issue_ref"])
        pct = float(step.get("tolerance_pct") or 0)
        tol_total = _issued_total(step, at_partner) * pct / 100.0
        within = round(max(0.0, min(qty, tol_total - _tol_used(step))), 2)
        loss = {"id": new_id("mloss"), "roll_ids": [r["id"] for r in rolls], "qty": qty, "within_qty": within,
                "over_qty": round(qty - within, 2), "tolerance_pct": pct, "reason": reason.strip(),
                "recorded_by": name, "recorded_by_id": actor.get("id", ""), "recorded_at": now_iso(),
                "status": "pending_approval" if qty - within > EPS else "auto"}
        step.setdefault("material_losses", []).append(loss)
        if loss["status"] == "auto":
            await _execute(order, step, loss, name)
        else:
            order.setdefault("timeline", []).append({
                "at": now_iso(), "event": "material_loss_pending",
                "note": f"Step {seq}: susut/hilang {qty} (di atas toleransi {pct}% sebesar {loss['over_qty']}) "
                        f"menunggu persetujuan — {reason.strip()}"})
        order["updated_at"] = now_iso()
        await db.makloon_orders.replace_one({"id": mko_id}, order)
        return safe_doc(order)
    return await _locked(mko_id, name, run)


async def decide_loss(mko_id: str, seq: int, loss_id: str, *, approve: bool, note: str,
                      actor: Dict[str, Any], settle: str = "tagih_ganti", bill_id: str = "") -> Dict[str, Any]:
    name = actor.get("name", "")
    if settle not in ("tagih_ganti", "potong_bon"):
        raise HTTPException(status_code=400, detail="Cara penyelesaian: tagih_ganti atau potong_bon.")
    if approve and settle == "potong_bon" and not bill_id:
        raise HTTPException(status_code=400, detail="Pilih tagihan jasa mitra yang akan dipotong.")

    async def run(order):
        step = _find_step(order, seq)
        loss = next((x for x in step.get("material_losses") or [] if x["id"] == loss_id), None)
        if not loss:
            raise HTTPException(status_code=404, detail="Catatan susut tidak ditemukan.")
        if loss["status"] != "pending_approval":
            raise HTTPException(status_code=409, detail="Catatan susut ini sudah diputuskan.")
        if loss.get("recorded_by_id") and loss["recorded_by_id"] == actor.get("id"):
            raise HTTPException(status_code=403, detail="Pencatat tidak boleh menyetujui catatan susutnya sendiri.")
        loss.update({"decided_by": name, "decided_at": now_iso(), "decision_note": (note or "").strip()})
        if approve:
            if settle == "potong_bon":
                ok = {b["id"] for b in await deductible_bills(mko_id, seq)}
                if bill_id not in ok:
                    raise HTTPException(status_code=400, detail="Tagihan bukan milik mitra ini / sudah lunas.")
            await _execute(order, step, loss, name, settle=settle, bill_id=bill_id)
        else:
            if len((note or "").strip()) < 5:
                raise HTTPException(status_code=400, detail="Alasan menolak wajib (min. 5 karakter).")
            loss["status"] = "rejected"
        order["updated_at"] = now_iso()
        await db.makloon_orders.replace_one({"id": mko_id}, order)
        return safe_doc(order)
    return await _locked(mko_id, name, run)
