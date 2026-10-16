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
    return {r["_id"]: _r(r["total"]) for r in rows}


async def list_costs(campaign: Dict[str, Any]) -> Dict[str, Any]:
    rows = await db[COLL].find({"campaign_id": campaign["id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)
    realized = _r(sum(r["amount"] for r in rows if r.get("status") == "posted"))
    budget = _r(campaign.get("budget"))
    return {"campaign_id": campaign["id"], "budget": budget, "realized": realized,
            "remaining": _r(budget - realized), "over_budget": budget > 0 and realized > budget, "costs": rows}


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
