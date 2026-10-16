"""COMM-04 (keputusan PG04) — realisasi biaya kampanye marketing → jurnal Beban Pemasaran.

Biaya diakui saat uang BENAR-BENAR keluar: Dr Beban Pemasaran / Cr Kas-Bank lewat
`cash_transactions` (ref_type `mkt_campaign_cost`) sehingga buku kas & GL sejalan.
Anggaran kampanye TIDAK dijurnal. Batal = jurnal pembalik di periode berjalan (sekali).
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import HTTPException

from core_utils import new_id, next_doc_number, now_iso
from db import db
from services import atomic_claim as _saga
from services import gl_service as gl

COLL = "mkt_campaign_costs"
REF_TYPE = "mkt_campaign_cost"
CASH_TYPES = ("kas_besar", "kas_kecil")


def _r(v: Any) -> float:
    return round(float(v or 0), 2)


async def _expense_account(code: str, entity_id: str) -> str:
    code = (code or "").strip() or gl.ACC_BEBAN_PEMASARAN
    await gl.seed_default_coa()
    acc = (await gl.effective_accounts([code], entity_id)).get(code)
    if not acc or acc.get("type") != "expense" or acc.get("is_postable") is False or acc.get("is_active") is False:
        raise HTTPException(status_code=400, detail=f"Akun {code} bukan akun beban aktif yang boleh diposting.")
    return code


async def realized_by_campaign(campaign_ids: List[str]) -> Dict[str, float]:
    rows = await db[COLL].aggregate([
        {"$match": {"campaign_id": {"$in": campaign_ids}, "status": "posted"}},
        {"$group": {"_id": "$campaign_id", "total": {"$sum": "$amount"}}}]).to_list(len(campaign_ids) or 1)
    out = {r["_id"]: _r(r["total"]) for r in rows}
    for cid, v in (await bills_realized_by_campaign(campaign_ids)).items():
        out[cid] = _r(out.get(cid, 0) + v)
    return out


async def list_costs(campaign: Dict[str, Any]) -> Dict[str, Any]:
    rows = await db[COLL].find({"campaign_id": campaign["id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)
    bills = await campaign_bills(campaign["id"])
    direct = _r(sum(r["amount"] for r in rows if r.get("status") == "posted"))
    billed = _r(sum(bill_expense(b) for b in bills if b.get("status") in ("posted", "paid")))
    pending = _r(sum(bill_expense(b) for b in bills if b.get("status") == "pending_approval"))
    realized, budget = _r(direct + billed), _r(campaign.get("budget"))
    return {"campaign_id": campaign["id"], "budget": budget, "realized": realized, "realized_direct": direct,
            "realized_bills": billed, "pending_bills": pending, "remaining": _r(budget - realized),
            "over_budget": budget > 0 and realized > budget, "costs": rows, "bills": bills}


async def record_cost(campaign: Dict[str, Any], payload: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    entity_id = campaign.get("entity_id", "")
    amount = _r(payload.get("amount"))
    desc = (payload.get("description") or "").strip()
    date = (payload.get("date") or now_iso())[:10]
    cash_type = payload.get("cash_type") or "kas_besar"
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Nominal biaya harus lebih dari 0.")
    if len(desc) < 3:
        raise HTTPException(status_code=400, detail="Uraian biaya wajib diisi (min. 3 karakter).")
    if cash_type not in CASH_TYPES:
        raise HTTPException(status_code=400, detail="Sumber dana harus kas_besar (bank) atau kas_kecil.")
    expense_acc = await _expense_account(payload.get("expense_account_code", ""), entity_id)
    try:
        await gl.preflight_posting(entity_id, date)
    except gl.ClosedPeriodError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    now = now_iso()
    cost = {
        "id": new_id("mcc"), "number": await next_doc_number(COLL, "number", "MCC-", entity_id=entity_id),
        "entity_id": entity_id, "campaign_id": campaign["id"], "campaign_name": campaign.get("name", ""),
        "date": date, "description": desc, "amount": amount, "source": "direct", "cash_type": cash_type,
        "expense_account_code": expense_acc, "vendor_name": (payload.get("vendor_name") or "").strip(),
        "status": "posting", "created_by": actor.get("name", ""), "created_at": now, "updated_at": now,
    }
    await db[COLL].insert_one(dict(cost))
    txn = {
        "id": new_id("cash"),
        "number": await next_doc_number("cash_transactions", "number", "CASH-", entity_id=entity_id or None),
        "cash_type": cash_type, "direction": "out", "amount": amount, "category": "beban pemasaran",
        "description": f"Biaya kampanye {campaign.get('name', '')} — {desc}", "entity_id": entity_id,
        "ref_type": REF_TYPE, "ref_id": cost["id"], "contra_account_code": expense_acc,
        "txn_date": f"{date}T00:00:00", "account_id": "", "reconciled": False, "status": "posted",
        "created_by": actor.get("name", ""), "created_at": now, "updated_at": now,
    }
    await db.cash_transactions.insert_one(dict(txn))
    try:
        je = await gl.post_cash_durable(txn)
    except Exception as exc:  # noqa: BLE001 — kompensasi: kas & biaya dibatalkan, tak ada jurnal setengah
        await db.cash_transactions.update_one({"id": txn["id"]}, {"$set": {"status": "void", "updated_at": now_iso()}})
        await db[COLL].delete_one({"id": cost["id"]})
        raise HTTPException(status_code=409, detail=f"Jurnal biaya gagal, biaya tidak disimpan: {exc}") from exc
    sets = {"status": "posted", "cash_txn_id": txn["id"], "cash_txn_number": txn["number"],
            "journal_entry_id": (je or {}).get("id", ""), "journal_entry_number": (je or {}).get("number", ""),
            "updated_at": now_iso()}
    await db[COLL].update_one({"id": cost["id"]}, {"$set": sets})
    return {**cost, **sets}


async def void_cost(cost: Dict[str, Any], reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="Alasan pembatalan wajib diisi (min. 5 karakter).")
    if cost.get("status") != "posted":
        raise HTTPException(status_code=409, detail="Hanya biaya berstatus terposting yang bisa dibatalkan.")
    txn = await db.cash_transactions.find_one({"id": cost.get("cash_txn_id")}, {"_id": 0}) or {}
    if txn.get("reconciled") or float(txn.get("reconciled_amount") or 0) > 0:
        raise HTTPException(status_code=409, detail="Kas biaya ini sudah dicocokkan dengan mutasi bank — lepaskan dulu.")
    try:
        await gl.preflight_posting(cost.get("entity_id", ""), now_iso())
    except gl.ClosedPeriodError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await _saga.claim(COLL, cost["id"], "mkt_cost_void", precondition={"status": "posted"}, actor=actor.get("name", ""))
    try:
        rev = await gl.post_cash_void(cost["cash_txn_id"], label=cost.get("number", ""), created_by=actor.get("name", ""))
        rev = rev or await db.journal_entries.find_one(
            {"source_type": "cash_transaction_void", "source_id": cost["cash_txn_id"]}, {"_id": 0, "id": 1, "number": 1})
        await db.cash_transactions.update_one({"id": cost["cash_txn_id"]}, {"$set": {
            "status": "void", "void_journal_entry_id": (rev or {}).get("id", ""), "updated_at": now_iso()}})
    except Exception as exc:  # noqa: BLE001
        await _saga.mark_failed(COLL, cost["id"], str(exc))
        raise HTTPException(status_code=409, detail=f"Jurnal pembalik gagal: {exc}") from exc
    sets = {"status": "void", "void_reason": reason, "voided_by": actor.get("name", ""), "voided_at": now_iso(),
            "void_journal_entry_id": (rev or {}).get("id", ""), "void_journal_entry_number": (rev or {}).get("number", ""),
            "updated_at": now_iso()}
    await db[COLL].update_one({"id": cost["id"]}, _saga.finish_set(sets))
    return {**cost, **sets}


# ─── Tagihan vendor kampanye (tanpa PO) — keputusan owner 2026-10-16 ─────────────────────────
# Diakui saat DISETUJUI: Dr Beban Pemasaran (+PPN Masukan) / Cr Hutang Usaha; dibayar lewat alur
# Vendor Bill biasa (Dr Hutang / Cr Kas). Dibuat Marketing/Admin, disetujui Finance/Manager (SoD).
BILL_TYPE = "campaign_expense"
BILL_APPROVER_ROLES = ("finance", "manager", "admin")


async def campaign_bills(campaign_id: str) -> List[Dict[str, Any]]:
    keep = {"_id": 0, "id": 1, "bill_number": 1, "supplier_name": 1, "supplier_invoice_no": 1, "bill_date": 1,
            "due_date": 1, "status": 1, "grand_total": 1, "ppn_amount": 1, "amount_paid": 1, "notes": 1,
            "created_by": 1, "created_by_id": 1, "approved_by": 1, "rejection_reason": 1, "cancel_reason": 1}
    return await db.vendor_bills.find({"campaign_id": campaign_id, "bill_type": BILL_TYPE}, keep) \
        .sort("created_at", -1).to_list(500)


def bill_expense(b: Dict[str, Any]) -> float:
    return _r(float(b.get("grand_total") or 0) - float(b.get("ppn_amount") or 0))


async def bills_realized_by_campaign(campaign_ids: List[str]) -> Dict[str, float]:
    rows = await db.vendor_bills.aggregate([
        {"$match": {"campaign_id": {"$in": campaign_ids}, "bill_type": BILL_TYPE, "status": {"$in": ["posted", "paid"]}}},
        {"$group": {"_id": "$campaign_id", "total": {"$sum": {"$subtract": [
            {"$ifNull": ["$grand_total", 0]}, {"$ifNull": ["$ppn_amount", 0]}]}}}}]).to_list(len(campaign_ids) or 1)
    return {r["_id"]: _r(r["total"]) for r in rows}


async def create_campaign_bill(campaign: Dict[str, Any], payload: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    from core_utils import timeline_entry
    from services.vendor_bill_service import ACTIVE_BILL_STATUSES, next_bill_number
    entity_id = campaign.get("entity_id", "")
    amount, ppn = _r(payload.get("amount")), _r(payload.get("ppn_amount"))
    desc = (payload.get("description") or "").strip()
    inv_no = (payload.get("supplier_invoice_no") or "").strip()
    if amount <= 0 or ppn < 0:
        raise HTTPException(status_code=400, detail="Nominal tagihan harus lebih dari 0 (PPN tidak boleh negatif).")
    if len(desc) < 3:
        raise HTTPException(status_code=400, detail="Uraian tagihan wajib diisi (min. 3 karakter).")
    sup = await db.suppliers.find_one({"id": payload.get("supplier_id") or "",
                                       "entity_id": {"$in": [entity_id, "all", "", None]}}, {"_id": 0})
    if not sup:
        raise HTTPException(status_code=400, detail="Pilih vendor (supplier) yang terdaftar.")
    from services import group_partner_service as _grp
    await _grp.assert_supplier_not_group_entity(sup, doc_label="Tagihan vendor kampanye")
    if inv_no and await db.vendor_bills.find_one({"supplier_id": sup["id"], "supplier_invoice_no": inv_no,
                                                  "status": {"$in": list(ACTIVE_BILL_STATUSES)}}, {"_id": 1}):
        raise HTTPException(status_code=409, detail=f"No. invoice vendor '{inv_no}' sudah pernah ditagihkan.")
    expense_acc = await _expense_account(payload.get("expense_account_code", ""), entity_id)
    num, now, grand = await next_bill_number(), now_iso(), _r(amount + ppn)
    bill = {
        "id": new_id("vbill"), "bill_number": num, "bill_type": BILL_TYPE, "supplier_invoice_no": inv_no,
        "po_id": "", "po_number": "", "supplier_id": sup["id"], "supplier_name": sup.get("name", ""),
        "supplier_npwp": sup.get("npwp", ""), "entity_id": entity_id,
        "campaign_id": campaign["id"], "campaign_name": campaign.get("name", ""), "expense_account_code": expense_acc,
        "bill_date": payload.get("bill_date") or now, "due_date": payload.get("due_date") or "",
        "items": [{"product_id": "", "product_name": desc, "quantity": 1, "billed_qty": 1, "unit": "jasa",
                   "price": amount, "subtotal": amount}],
        "total_amount": amount, "net_subtotal": amount, "dpp": amount, "ppn_amount": ppn, "grand_total": grand,
        "discount_total": 0.0, "match_status": "not_applicable", "match_exceptions": [],
        "status": "pending_approval", "approval_required": True, "required_approval_role": "finance",
        "approval_status": "pending", "approved_by": "", "approved_at": "",
        "amount_paid": 0.0, "outstanding": grand, "payment_status": "unpaid", "payments": [],
        "notes": desc, "created_by": actor.get("name", ""), "created_by_id": actor.get("id", ""),
        "timeline": [timeline_entry("created", "Tagihan vendor kampanye dibuat", actor.get("name", ""),
                                    f"{campaign.get('name', '')} · Rp {grand:,.0f} · menunggu persetujuan Finance/Manager")],
        "created_at": now, "updated_at": now,
    }
    await db.vendor_bills.insert_one(dict(bill))
    from services.notification_service import create_notification
    await create_notification(
        notif_type="campaign_bill_approval", ref=f"mkt_bill:{bill['id']}", severity="warning",
        title=f"Tagihan kampanye menunggu persetujuan: {num}",
        body=(f"{campaign.get('name', '')} · {sup.get('name', '')} · Rp {grand:,.0f} — {desc}. "
              f"Diajukan {actor.get('name', '')}; setujui agar masuk Beban Pemasaran & Hutang."),
        link="mkt-campaigns", entity_id=entity_id, recipient_role="finance",
        action_type="vendor_bill_approve", action_id=bill["id"], action_role="finance")
    return bill


async def approve_campaign_bill(bill: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    from routers.vendor_bills import _post_bill
    from services import approval_matrix_service as _amx
    if actor.get("role") not in BILL_APPROVER_ROLES:
        raise HTTPException(status_code=403, detail="Persetujuan tagihan kampanye hanya Finance/Manager/Admin.")
    if bill.get("status") != "pending_approval":
        raise HTTPException(status_code=409, detail=f"Tagihan berstatus '{bill.get('status')}', tidak menunggu persetujuan.")
    if bill.get("created_by_id") == actor.get("id") and not await _amx.admin_override(
            "vendor_bill_approve", actor, bill, bill.get("entity_id", "")):
        raise HTTPException(status_code=403, detail="Pemisahan tugas (SoD): pembuat tagihan tidak boleh menyetujui sendiri.")
    try:
        await gl.preflight_posting(bill.get("entity_id", ""), bill.get("bill_date") or now_iso())
    except gl.ClosedPeriodError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.vendor_bills.update_one({"id": bill["id"], "status": "pending_approval"}, {"$set": {
        "approval_status": "approved", "approved_by": actor.get("name", ""), "approved_at": now_iso()}})
    out = await _post_bill(bill["id"], actor, note=f"disetujui oleh {actor.get('role')}")
    await db.notifications.update_many({"ref": f"mkt_bill:{bill['id']}", "read": {"$ne": True}},
                                       {"$set": {"read": True, "read_at": now_iso()}})
    if not await db.journal_entries.find_one({"source_type": "vendor_bill", "source_id": bill["id"]}, {"_id": 1}):
        await gl.post_vendor_bill(out)   # _post_bill best-effort → pastikan jurnal ada (idempoten)
    return out


async def reject_campaign_bill(bill: Dict[str, Any], reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    from core_utils import timeline_entry
    if actor.get("role") not in BILL_APPROVER_ROLES:
        raise HTTPException(status_code=403, detail="Penolakan tagihan kampanye hanya Finance/Manager/Admin.")
    if len((reason or "").strip()) < 5:
        raise HTTPException(status_code=400, detail="Alasan penolakan wajib diisi (min. 5 karakter).")
    out = await db.vendor_bills.find_one_and_update(
        {"id": bill["id"], "status": "pending_approval"},
        {"$set": {"status": "cancelled", "approval_status": "rejected", "rejected_by": actor.get("name", ""),
                  "rejection_reason": reason.strip(), "rejected_at": now_iso(), "updated_at": now_iso()},
         "$push": {"timeline": timeline_entry("rejected", "Tagihan ditolak", actor.get("name", ""), reason.strip())}},
        projection={"_id": 0}, return_document=True)
    if not out:
        raise HTTPException(status_code=409, detail="Tagihan sudah diproses orang lain. Muat ulang.")
    await db.notifications.update_many({"ref": f"mkt_bill:{bill['id']}", "read": {"$ne": True}},
                                       {"$set": {"read": True, "read_at": now_iso()}})
    return out


# ─── Grafik anggaran vs realisasi per bulan + peringatan hampir habis ───────────────────────
NEAR_PCT = 80.0


def _months_between(start: str, end: str) -> List[str]:
    if not start:
        return []
    y, m = int(start[:4]), int(start[5:7])
    ey, em = (int(end[:4]), int(end[5:7])) if end else (y, m)
    out = []
    while (y, m) <= (ey, em) and len(out) < 36:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


async def budget_summary(campaigns: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Anggaran dibagi rata ke bulan periode kampanye; realisasi per bulan dari tanggal kas keluar / tagihan."""
    ids = [c["id"] for c in campaigns]
    months: Dict[str, Dict[str, float]] = {}

    def bump(month: str, key: str, v: float) -> None:
        row = months.setdefault(month, {"budget": 0.0, "realized": 0.0})
        row[key] = _r(row[key] + v)
    for c in campaigns:
        span = _months_between(c.get("start_date") or (c.get("created_at") or "")[:10], c.get("end_date") or "")
        for mo in span:
            bump(mo, "budget", float(c.get("budget") or 0) / len(span))
    async for x in db[COLL].find({"campaign_id": {"$in": ids}, "status": "posted"}, {"_id": 0, "date": 1, "amount": 1}):
        bump((x.get("date") or "")[:7], "realized", float(x.get("amount") or 0))
    bills = await db.vendor_bills.find({"campaign_id": {"$in": ids}, "bill_type": BILL_TYPE, "status": {"$in": ["posted", "paid"]}},
                                       {"_id": 0, "bill_date": 1, "grand_total": 1, "ppn_amount": 1}).to_list(5000)
    for b in bills:
        bump((b.get("bill_date") or "")[:7], "realized", bill_expense(b))
    realized = await realized_by_campaign(ids)
    alerts = []
    for c in campaigns:
        budget, used = float(c.get("budget") or 0), realized.get(c["id"], 0.0)
        if budget <= 0:
            continue
        pct = round(used / budget * 100, 1)
        if pct >= NEAR_PCT:
            alerts.append({"campaign_id": c["id"], "name": c.get("name", ""), "budget": _r(budget), "realized": used,
                           "pct": pct, "level": "over" if pct > 100 else "near",
                           "remaining": _r(budget - used)})
    alerts.sort(key=lambda a: -a["pct"])
    rows = [{"month": k, **v} for k, v in sorted(months.items()) if k]
    return {"months": rows, "alerts": alerts, "near_pct": NEAR_PCT,
            "total_budget": _r(sum(float(c.get("budget") or 0) for c in campaigns)),
            "total_realized": _r(sum(realized.values()))}
