"""Bank/Cash Accounts service (EPIC7-B) — multi-akun kas & bank + rekonsiliasi.

Koleksi kanonik: `bank_accounts` (master akun). Mutasi tetap memakai
`cash_transactions` (SSOT kas) dengan field opsional `account_id` yang
menautkan transaksi ke akun. Saldo akun = opening_balance + Σ(in) − Σ(out)
transaksi posted (non-void) milik akun tsb.

Rekonsiliasi sederhana: field `reconciled` (bool) + `reconciled_at` pada
cash_transactions; saldo terekonsiliasi dihitung dari transaksi reconciled.
"""
from typing import Any, Dict, List, Optional

from db import db
from core_utils import new_id, now_iso, safe_doc, DEFAULT_ENTITY_ID

VALID_ACCOUNT_TYPES = {"bank", "cash"}


def _posted(txn: Dict[str, Any]) -> bool:
    return txn.get("status") != "void"


async def _txns_for(account_id: str) -> List[Dict[str, Any]]:
    return await db.cash_transactions.find(
        {"account_id": account_id, "status": {"$ne": "void"}}, {"_id": 0}
    ).sort("txn_date", -1).to_list(None)   # W2-021 — saldo rekening dari SELURUH mutasi (dulu cap 5.000)


def _balance(opening: float, txns: List[Dict[str, Any]], reconciled_only: bool = False) -> float:
    bal = float(opening or 0)
    for t in txns:
        if reconciled_only and not t.get("reconciled"):
            continue
        amt = float(t.get("amount", 0) or 0)
        bal += amt if t.get("direction") == "in" else -amt
    return round(bal, 2)


def _enrich(acc: Dict[str, Any], txns: List[Dict[str, Any]]) -> Dict[str, Any]:
    opening = float(acc.get("opening_balance", 0) or 0)
    inflow = round(sum(float(t.get("amount", 0) or 0) for t in txns if t.get("direction") == "in"), 2)
    outflow = round(sum(float(t.get("amount", 0) or 0) for t in txns if t.get("direction") == "out"), 2)
    reconciled = sum(1 for t in txns if t.get("reconciled"))
    return {
        **acc,
        "balance": _balance(opening, txns),
        "reconciled_balance": _balance(opening, txns, reconciled_only=True),
        "inflow": inflow,
        "outflow": outflow,
        "txn_count": len(txns),
        "unreconciled_count": len(txns) - reconciled,
    }


async def list_accounts(entity_id: Optional[str] = None,
                        scope: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = dict(scope) if scope is not None else {}
    if scope is None and entity_id and entity_id != "all":
        q["entity_id"] = entity_id
    accounts = await db.bank_accounts.find(q, {"_id": 0}).sort("created_at", 1).to_list(500)
    out = []
    for acc in accounts:
        txns = await _txns_for(acc["id"])
        out.append(_enrich(acc, txns))
    return out


async def create_account(payload, actor: Dict[str, Any]) -> Dict[str, Any]:
    if payload.account_type not in VALID_ACCOUNT_TYPES:
        raise ValueError("account_type harus 'bank' atau 'cash'")
    doc = {
        "id": new_id("bank"),
        "name": payload.name.strip(),
        "account_type": payload.account_type,
        "bank_name": (payload.bank_name or "").strip(),
        "account_number": (payload.account_number or "").strip(),
        "entity_id": payload.entity_id or DEFAULT_ENTITY_ID,
        "opening_balance": round(float(payload.opening_balance or 0), 2),
        "currency": payload.currency or "IDR",
        "note": (payload.note or "").strip(),
        "is_active": True,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    from services import gl_service as _gl
    if doc["opening_balance"]:
        await _gl.preflight_posting(doc["entity_id"], now_iso())
    await db.bank_accounts.insert_one(doc)
    try:
        je = await _post_opening(doc, doc["opening_balance"], "bank_opening_balance", doc["id"])
    except Exception:
        await db.bank_accounts.delete_one({"id": doc["id"]})  # FN-08 — rekening + jurnal pembukaan satu operasi
        raise
    if je:
        await db.bank_accounts.update_one({"id": doc["id"]}, {"$set": {"opening_je_id": je["id"]}})
        doc["opening_je_id"] = je["id"]
    return _enrich(safe_doc(doc), [])


OPENING_EQUITY_ACC = "3-2900"


async def _post_opening(acc: Dict[str, Any], amount: float, source_type: str, source_id: str):
    """FN-08 — saldo awal rekening terikat GL: Dr Kas/Bank ↔ Cr Ekuitas Saldo Awal (tanda dibalik bila negatif)."""
    from services import gl_service as _gl
    amt = round(float(amount or 0), 2)
    if abs(amt) <= 0.005:
        return None
    cash_acc = "1-1110" if acc.get("account_type") == "cash" else "1-1100"
    dr, cr = (cash_acc, OPENING_EQUITY_ACC) if amt > 0 else (OPENING_EQUITY_ACC, cash_acc)
    await _gl.seed_default_coa()
    return await _gl._insert_entry(
        lines=[{"account_code": dr, "debit": abs(amt), "credit": 0.0, "description": f"Saldo awal {acc['name']}"},
               {"account_code": cr, "debit": 0.0, "credit": abs(amt), "description": f"Saldo awal {acc['name']}"}],
        description=f"Saldo awal rekening {acc['name']}", date=now_iso(), source_type=source_type,
        source_id=source_id, entity_id=acc.get("entity_id") or DEFAULT_ENTITY_ID, created_by="system",
        source_label=acc["name"])


async def update_account(account_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    acc = await db.bank_accounts.find_one({"id": account_id}, {"_id": 0})
    if not acc:
        return None
    upd = {k: v for k, v in patch.items() if v is not None}
    if "opening_balance" in upd:
        upd["opening_balance"] = round(float(upd["opening_balance"]), 2)
        delta = round(upd["opening_balance"] - float(acc.get("opening_balance") or 0), 2)
        if abs(delta) > 0.005:
            # FN-08 — saldo awal terkunci pada jurnal; koreksi = jurnal penyesuaian selisih (bukan edit diam-diam).
            if not acc.get("opening_je_id") and float(acc.get("opening_balance") or 0):
                raise ValueError("Saldo awal lama rekening ini belum terjurnal — koreksi lewat jurnal manual "
                                 "(Dr/Cr Kas-Bank ↔ 3-2900) oleh Keuangan, bukan edit saldo awal.")
            from services import gl_service as _gl
            await _gl.preflight_posting(acc.get("entity_id") or DEFAULT_ENTITY_ID, now_iso())
            n = await db.journal_entries.count_documents({"source_type": "bank_opening_adjustment",
                                                          "source_id": {"$regex": f"^{account_id}:"}})
            je = await _post_opening({**acc, **upd}, delta, "bank_opening_adjustment", f"{account_id}:{n + 1}")
            if not acc.get("opening_je_id") and je:
                upd["opening_je_id"] = je["id"]
        else:
            upd.pop("opening_balance")
    if "name" in upd:
        upd["name"] = str(upd["name"]).strip()
    upd["updated_at"] = now_iso()
    await db.bank_accounts.update_one({"id": account_id}, {"$set": upd})
    acc = await db.bank_accounts.find_one({"id": account_id}, {"_id": 0})
    txns = await _txns_for(account_id)
    return _enrich(acc, txns)


async def account_ledger(account_id: str) -> Optional[Dict[str, Any]]:
    acc = await db.bank_accounts.find_one({"id": account_id}, {"_id": 0})
    if not acc:
        return None
    txns = await _txns_for(account_id)
    # running balance (kronologis menaik)
    chron = sorted(txns, key=lambda t: (t.get("txn_date") or "", t.get("number") or ""))
    running = float(acc.get("opening_balance", 0) or 0)
    for t in chron:
        amt = float(t.get("amount", 0) or 0)
        running += amt if t.get("direction") == "in" else -amt
        t["running_balance"] = round(running, 2)
    chron.reverse()  # tampilkan terbaru dulu
    return {**_enrich(acc, txns), "transactions": chron}


async def reconcile_txn(txn_id: str, reconciled: bool) -> Optional[Dict[str, Any]]:
    txn = await db.cash_transactions.find_one({"id": txn_id}, {"_id": 0})
    if not txn:
        return None
    await db.cash_transactions.update_one(
        {"id": txn_id},
        {"$set": {"reconciled": bool(reconciled),
                  "reconciled_at": now_iso() if reconciled else "",
                  "updated_at": now_iso()}},
    )
    return await db.cash_transactions.find_one({"id": txn_id}, {"_id": 0})
