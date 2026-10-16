"""Service — Cash Advance (Form PD) + Pertanggungjawaban (Settlement) + Expense Categories.

Koleksi:
- cash_advances (prefix ca_) — Form Pengajuan Dana; state-machine approval berjenjang.
- cash_advance_settlements (prefix stl_) — Laporan Pertanggungjawaban petty cash → auto-post GL.
- expense_categories (prefix excat_, SHARED) — mapping kategori pengeluaran → akun COA (configurable).

Akuntansi (anti double-count, buku per-entitas seimbang):
- Disburse : cash_transaction(out, ref_type='cash_advance') → GL Dr 1-1400 Uang Muka / Cr Kas.
- Settlement approved : GL Dr [beban per kategori] / Cr 1-1400 Uang Muka (= total pengeluaran).

Rantai approval PD (default — ACC owner, configurable):
  Atasan Langsung=manager · Pimpinan=admin · Bagian Keuangan=admin(finance); admin override semua tahap.
"""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pymongo import ReturnDocument

from db import db
from core_utils import new_id, now_iso, next_doc_number, safe_doc
from dependencies import audit
from entity_scope import EntityContext, resolve_list_scope, assert_entity_access, assert_active_entity_access
from services import gl_service

CA_COLL = "cash_advances"
STL_COLL = "cash_advance_settlements"
EXCAT_COLL = "expense_categories"

VALID_PAYMENT = {"tunai", "transfer"}

# Rantai approval PD (configurable). status_from → boleh di-approve role tsb (admin override).
APPROVAL_STAGES = [
    {"stage": "atasan",   "status": "pending_atasan",   "roles": ["manager", "admin"],
     "next": "pending_pimpinan", "label": "Atasan Langsung"},
    {"stage": "pimpinan", "status": "pending_pimpinan", "roles": ["admin"],
     "next": "pending_finance",  "label": "Pimpinan"},
    {"stage": "finance",  "status": "pending_finance",  "roles": ["admin"],
     "next": "approved",         "label": "Bagian Keuangan"},
]
STAGE_BY_STATUS = {s["status"]: s for s in APPROVAL_STAGES}
FIRST_STATUS = APPROVAL_STAGES[0]["status"]
EDITABLE_STATUSES = {"draft", "rejected"}

# Kategori pengeluaran default (dari Excel Laporan Petty Cash) → akun beban COA.
DEFAULT_EXPENSE_CATEGORIES = [
    ("office_supplies", "Office Supplies", "6-4100", 1),
    ("atk", "ATK", "6-4100", 2),
    ("lunch_snack_entertainment", "Lunch / Snack / Entertainment", "6-4200", 3),
    ("fotocopy_printing_jilid_materai", "Fotokopi / Printing / Jilid / Materai", "6-4300", 4),
    ("utilitas_kantor", "Telepon / Listrik / Air / Internet / IPKL", "6-4400", 5),
    ("kirim_dokumen", "Kirim Dokumen", "6-4500", 6),
    ("transportasi", "Transportasi (Service Mobil/Taxi/BBM/Tol/Parkir)", "6-4600", 7),
    ("petty_cash_lain", "Petty Cash Lainnya", "6-4900", 8),
]
FALLBACK_ACCOUNT = "6-4900"


def _r(v: Any) -> float:
    return round(float(v or 0), 2)


# ═══ Expense Categories (mapping kategori → akun) ════════════════════════
async def seed_expense_categories() -> int:
    """Idempotent — hanya tambah kategori yang belum ada."""
    existing = {c["code"] for c in await db[EXCAT_COLL].find({}, {"_id": 0, "code": 1}).to_list(200)}
    to_add = []
    for code, label, acc, sort in DEFAULT_EXPENSE_CATEGORIES:
        if code in existing:
            continue
        to_add.append({
            "id": new_id("excat"), "entity_id": "all", "code": code, "label": label,
            "account_code": acc, "sort": sort, "active": True,
            "created_at": now_iso(), "updated_at": now_iso(),
        })
    if to_add:
        await db[EXCAT_COLL].insert_many(to_add)
    return len(to_add)


async def list_expense_categories(active_only: bool = False,
                                  entity_id: str = "") -> List[Dict[str, Any]]:
    """Kategori biaya EFEKTIF untuk satu badan usaha — global + override, tanpa kembar.

    FASE E-4 (E4.3). `entity_id` kosong = hanya lapisan global (perilaku lama).
    """
    from services import entity_master_service as ems
    rows = await ems.effective_rows("expense-categories", entity_id,
                                    include_inactive=not active_only)
    rows.sort(key=lambda c: c.get("sort", 999))
    return rows


async def update_expense_category(code: str, patch: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    cat = await db[EXCAT_COLL].find_one({"code": code}, {"_id": 0})
    if not cat:
        raise HTTPException(status_code=404, detail="Kategori tidak ditemukan")
    upd: Dict[str, Any] = {}
    if patch.get("label") is not None:
        upd["label"] = str(patch["label"]).strip()
    if patch.get("active") is not None:
        upd["active"] = bool(patch["active"])
    if patch.get("account_code") is not None:
        acc_code = str(patch["account_code"]).strip()
        acc = await db.gl_accounts.find_one({"code": acc_code, "entity_id": {"$in": [None, ""]}}, {"_id": 0})
        if not acc:
            raise HTTPException(status_code=400, detail=f"Akun '{acc_code}' tidak ditemukan")
        if not acc.get("is_postable", True):
            raise HTTPException(status_code=400, detail=f"Akun '{acc_code}' header — pilih akun detail")
        upd["account_code"] = acc_code
    upd["updated_at"] = now_iso()
    await db[EXCAT_COLL].update_one({"code": code}, {"$set": upd})
    await audit(actor.get("name", ""), "expense_category_updated", "expense_category", code, upd)
    return await db[EXCAT_COLL].find_one({"code": code}, {"_id": 0})


async def _category_account_map() -> Dict[str, str]:
    rows = await db[EXCAT_COLL].find({}, {"_id": 0, "code": 1, "account_code": 1}).to_list(200)
    return {r["code"]: r.get("account_code") or FALLBACK_ACCOUNT for r in rows}


# ═══ Cash Advance (Form PD) ════════════════════════════════════
def _compute_lines(raw_lines) -> (List[Dict[str, Any]], float):
    lines: List[Dict[str, Any]] = []
    total = 0.0
    for ln in (raw_lines or []):
        d = ln.model_dump() if hasattr(ln, "model_dump") else dict(ln)
        qty = _r(d.get("qty"))
        unit_price = _r(d.get("unit_price"))
        amount = _r(qty * unit_price)   # FIX: amount SELALU dari qty aktif × harga
        d["qty"] = qty
        d["unit_price"] = unit_price
        d["amount"] = amount
        total += amount
        lines.append(d)
    return lines, _r(total)


async def create_cash_advance(payload, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    if payload.payment_method not in VALID_PAYMENT:
        raise HTTPException(status_code=400, detail="payment_method harus 'tunai' atau 'transfer'")
    entity_id = payload.entity_id or ctx.active_entity_id
    if entity_id not in ctx.allowed_entity_ids:
        raise HTTPException(status_code=403, detail="Tidak berwenang atas entitas ini")
    lines, total = _compute_lines(payload.lines)
    if not lines:
        raise HTTPException(status_code=400, detail="Minimal 1 baris rincian dana")
    if total <= 0:
        raise HTTPException(status_code=400, detail="Total pengajuan harus lebih dari 0")
    number = await next_doc_number(CA_COLL, "number", "PD-", entity_id=entity_id)
    bank = payload.bank_detail.model_dump() if payload.bank_detail else {}
    doc = {
        "id": new_id("ca"),
        "number": number,
        "entity_id": entity_id,
        "divisi": (payload.divisi or "").strip(),
        "kegiatan": (payload.kegiatan or "").strip(),
        "period_from": payload.period_from or "",
        "period_to": payload.period_to or "",
        "tanggal_pengajuan": payload.tanggal_pengajuan or now_iso(),
        "account_label": (payload.account_label or "").strip(),
        "payment_method": payload.payment_method,
        "bank_detail": bank,
        "lines": lines,
        "total_amount": total,
        "status": "draft",
        "approvals": [],
        "disbursement": None,
        "rejected_reason": "",
        "catatan": (payload.catatan or "").strip(),
        "created_by": actor.get("name", ""),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db[CA_COLL].insert_one(doc)
    await audit(actor.get("name", ""), "cash_advance_created", "cash_advance", doc["id"],
                {"number": number, "total": total, "entity_id": entity_id})
    return safe_doc(doc)


async def list_cash_advances(ctx: EntityContext, entity_id: Optional[str] = None,
                             status: Optional[str] = None) -> List[Dict[str, Any]]:
    q = resolve_list_scope(CA_COLL, {}, ctx, entity_id)
    if status:
        q["status"] = status
    rows = await db[CA_COLL].find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return rows


async def get_cash_advance(ca_id: str, ctx: EntityContext) -> Dict[str, Any]:
    doc = await db[CA_COLL].find_one({"id": ca_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Pengajuan Dana tidak ditemukan")
    assert_active_entity_access(doc, CA_COLL, ctx)   # KN-B35 — penjaga KETAT (jalur tulis memakai loader ini)
    return safe_doc(doc)


async def update_cash_advance(ca_id: str, payload, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await get_cash_advance(ca_id, ctx)
    if doc["status"] not in EDITABLE_STATUSES:
        raise HTTPException(status_code=409, detail="Hanya PD draft/ditolak yang bisa diubah")
    upd: Dict[str, Any] = {}
    for f in ["divisi", "kegiatan", "period_from", "period_to", "tanggal_pengajuan",
              "account_label", "catatan"]:
        v = getattr(payload, f, None)
        if v is not None:
            upd[f] = v.strip() if isinstance(v, str) else v
    if payload.payment_method is not None:
        if payload.payment_method not in VALID_PAYMENT:
            raise HTTPException(status_code=400, detail="payment_method tidak valid")
        upd["payment_method"] = payload.payment_method
    if payload.bank_detail is not None:
        upd["bank_detail"] = payload.bank_detail.model_dump()
    if payload.lines is not None:
        lines, total = _compute_lines(payload.lines)
        if not lines or total <= 0:
            raise HTTPException(status_code=400, detail="Rincian dana tidak valid")
        upd["lines"] = lines
        upd["total_amount"] = total
    upd["updated_at"] = now_iso()
    updated = await db[CA_COLL].find_one_and_update(
        {"id": ca_id}, {"$set": upd}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    await audit(actor.get("name", ""), "cash_advance_updated", "cash_advance", ca_id, upd)
    return safe_doc(updated)


async def submit_cash_advance(ca_id: str, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await get_cash_advance(ca_id, ctx)
    if doc["status"] not in EDITABLE_STATUSES:
        raise HTTPException(status_code=409, detail="Hanya PD draft/ditolak yang bisa diajukan")
    updated = await db[CA_COLL].find_one_and_update(
        {"id": ca_id},
        {"$set": {"status": FIRST_STATUS, "rejected_reason": "", "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    await audit(actor.get("name", ""), "cash_advance_submitted", "cash_advance", ca_id,
                {"status": FIRST_STATUS})
    return safe_doc(updated)


async def approve_cash_advance(ca_id: str, note: str, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await get_cash_advance(ca_id, ctx)
    stage = STAGE_BY_STATUS.get(doc["status"])
    if not stage:
        raise HTTPException(status_code=409, detail="PD tidak dalam status menunggu persetujuan")
    role = actor.get("role", "")
    if role != "admin" and role not in stage["roles"]:
        raise HTTPException(status_code=403,
                            detail=f"Tahap '{stage['label']}' hanya untuk: {', '.join(stage['roles'])}")
    approval = {"stage": stage["stage"], "label": stage["label"], "decision": "approved",
                "by": actor.get("name", ""), "role": role, "note": (note or "").strip(),
                "at": now_iso()}
    updated = await db[CA_COLL].find_one_and_update(
        {"id": ca_id},
        {"$set": {"status": stage["next"], "updated_at": now_iso()},
         "$push": {"approvals": approval}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    await audit(actor.get("name", ""), "cash_advance_approved", "cash_advance", ca_id,
                {"stage": stage["stage"], "next": stage["next"]})
    return safe_doc(updated)


async def reject_cash_advance(ca_id: str, reason: str, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await get_cash_advance(ca_id, ctx)
    stage = STAGE_BY_STATUS.get(doc["status"])
    if not stage:
        raise HTTPException(status_code=409, detail="PD tidak dalam status menunggu persetujuan")
    role = actor.get("role", "")
    if role != "admin" and role not in stage["roles"]:
        raise HTTPException(status_code=403, detail="Anda tidak berwenang menolak pada tahap ini")
    approval = {"stage": stage["stage"], "label": stage["label"], "decision": "rejected",
                "by": actor.get("name", ""), "role": role, "note": (reason or "").strip(),
                "at": now_iso()}
    updated = await db[CA_COLL].find_one_and_update(
        {"id": ca_id},
        {"$set": {"status": "rejected", "rejected_reason": (reason or "").strip(), "updated_at": now_iso()},
         "$push": {"approvals": approval}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    await audit(actor.get("name", ""), "cash_advance_rejected", "cash_advance", ca_id, {"reason": reason})
    return safe_doc(updated)


async def _next_cash_number(entity_id: str = "") -> str:
    """Nomor kas ber-deret per badan usaha (E1.7) — kas grup sudah dihapus (E7.4)."""
    return await next_doc_number("cash_transactions", "number", "CASH-",
                                 entity_id=(entity_id or None))


async def disburse_cash_advance(ca_id: str, payload, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await get_cash_advance(ca_id, ctx)
    if doc["status"] != "approved":
        raise HTTPException(status_code=409, detail="Hanya PD berstatus 'approved' yang bisa dicairkan")
    cash_type = payload.cash_type if payload.cash_type in ("kas_kecil", "kas_besar") else "kas_kecil"
    entity_id = doc["entity_id"]
    try:
        await gl_service.preflight_posting(entity_id, payload.txn_date or now_iso())
    except gl_service.ClosedPeriodError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    # CX-04 — klaim atomik (satu pencairan per PD) + resume: kas lama dari percobaan gagal DIPAKAI ULANG.
    from services import atomic_claim as _saga
    await _saga.claim(CA_COLL, ca_id, "cash_advance_disburse", precondition={"status": "approved"},
                      actor=actor.get("name", ""))
    try:
        return await _disburse_locked(ca_id, doc, payload, cash_type, entity_id, actor)
    finally:
        await _saga.release(CA_COLL, ca_id)


async def _disburse_locked(ca_id: str, doc: Dict[str, Any], payload, cash_type: str, entity_id: str,
                           actor: Dict[str, Any]) -> Dict[str, Any]:
    existing = await db.cash_transactions.find_one(
        {"ref_type": "cash_advance", "ref_id": ca_id, "direction": "out", "status": "posted"}, {"_id": 0})
    if existing:
        je = await gl_service.post_cash_durable(existing)
        je = je or await db.journal_entries.find_one(
            {"source_type": "cash_transaction", "source_id": existing["id"], "status": {"$ne": "void"}},
            {"_id": 0, "id": 1, "number": 1})
        return await _finish_disburse(ca_id, doc, existing, je, cash_type, payload, actor)
    number = await _next_cash_number(entity_id)
    txn = {
        "id": new_id("cash"),
        "number": number,
        "cash_type": cash_type,
        "direction": "out",
        "amount": _r(doc["total_amount"]),
        "category": "cash_advance",
        "description": f"Pencairan {doc['number']} — {doc.get('kegiatan', '')}".strip(),
        # FASE E-7 (E7.4) — kas grup dihapus: pencairan uang muka karyawan tetap uang
        # badan usaha yang menugaskannya, walau ditransfer lewat bank (`kas_besar`).
        "entity_id": entity_id,
        "ref_type": "cash_advance",
        "ref_id": ca_id,
        "txn_date": payload.txn_date or now_iso(),
        "account_id": "",
        "reconciled": False,
        "status": "posted",
        "created_by": actor.get("name", ""),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.cash_transactions.insert_one(txn)
    await db[CA_COLL].update_one({"id": ca_id}, {"$set": {"disbursement_attempt": {
        "cash_txn_id": txn["id"], "at": now_iso(), "by": actor.get("name", "")}}})
    # GL: Dr 1-1400 Uang Muka / Cr Kas (idempotent by source cash_transaction). Gagal → PD tetap
    # 'approved' dengan kas tertaut; percobaan ulang melanjutkan kas yang sama (tanpa kas kedua).
    try:
        je = await gl_service.post_cash_durable(txn)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=409, detail=(
            f"Kas {number} tercatat tetapi jurnal gagal: {exc}. Ulangi pencairan untuk melanjutkan (tanpa kas ganda)."))
    return await _finish_disburse(ca_id, doc, txn, je, cash_type, payload, actor)


async def _finish_disburse(ca_id: str, doc: Dict[str, Any], txn: Dict[str, Any], je, cash_type: str,
                           payload, actor: Dict[str, Any]) -> Dict[str, Any]:
    number = txn.get("number", "")
    disb = {
        "cash_txn_id": txn["id"], "cash_txn_number": number,
        "je_id": (je or {}).get("id"), "je_number": (je or {}).get("number"),
        "cash_type": cash_type, "amount": _r(doc["total_amount"]),
        "disbursed_at": now_iso(), "disbursed_by": actor.get("name", ""),
        "note": (payload.note or "").strip(),
    }
    updated = await db[CA_COLL].find_one_and_update(
        {"id": ca_id, "status": "approved"},
        {"$set": {"status": "disbursed", "disbursement": disb, "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    await audit(actor.get("name", ""), "cash_advance_disbursed", "cash_advance", ca_id, disb)
    return safe_doc(updated)


# ═══ Settlement (Laporan Pertanggungjawaban) ══════════════════════════
def _compute_settlement(expense_lines, total_pettycash: float) -> Dict[str, Any]:
    lines: List[Dict[str, Any]] = []
    cat_totals: Dict[str, float] = {}
    total = 0.0
    for ln in (expense_lines or []):
        d = ln.model_dump() if hasattr(ln, "model_dump") else dict(ln)
        amt = _r(d.get("amount"))
        d["amount"] = amt
        cat = d.get("category") or "petty_cash_lain"
        cat_totals[cat] = _r(cat_totals.get(cat, 0.0) + amt)
        total += amt
        lines.append(d)
    total = _r(total)
    return {
        "expense_lines": lines,
        "category_totals": cat_totals,
        "total_pengeluaran": total,
        "total_pettycash": _r(total_pettycash),
        "sisa_kurang_dana": _r(total_pettycash - total),
    }


async def create_settlement(payload, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    ca = await get_cash_advance(payload.cash_advance_id, ctx)
    # CX-05 — kebijakan: SATU pertanggungjawaban per PD. PD settled / sudah punya LPJ aktif ditolak.
    if ca["status"] != "disbursed":
        raise HTTPException(status_code=409, detail="Pertanggungjawaban hanya untuk PD berstatus dicairkan (belum selesai)")
    other = await db[STL_COLL].find_one(
        {"cash_advance_id": ca["id"], "status": {"$in": ["draft", "submitted", "posted_to_gl"]}},
        {"_id": 0, "number": 1})
    if other:
        raise HTTPException(status_code=409, detail=f"PD ini sudah punya pertanggungjawaban {other['number']}")
    calc = _compute_settlement(payload.expense_lines, ca.get("total_amount", 0))
    if not calc["expense_lines"]:
        raise HTTPException(status_code=400, detail="Minimal 1 baris pengeluaran")
    number = await next_doc_number(STL_COLL, "number", "STL-", entity_id=ca["entity_id"])
    doc = {
        "id": new_id("stl"),
        "number": number,
        "entity_id": ca["entity_id"],
        "cash_advance_id": ca["id"],
        "cash_advance_number": ca["number"],
        "divisi": (payload.divisi or ca.get("divisi", "")).strip(),
        "periode": payload.periode or "",
        "dibuat_oleh": (payload.dibuat_oleh or actor.get("name", "")).strip(),
        "disetujui_oleh": "",
        "catatan": (payload.catatan or "").strip(),
        "status": "draft",
        "journal_entry_id": "",
        "created_by": actor.get("name", ""),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        **calc,
    }
    await db[STL_COLL].insert_one(doc)
    await audit(actor.get("name", ""), "settlement_created", "cash_advance_settlement", doc["id"],
                {"number": number, "total": calc["total_pengeluaran"]})
    return safe_doc(doc)


async def list_settlements(ctx: EntityContext, entity_id: Optional[str] = None,
                           cash_advance_id: Optional[str] = None,
                           status: Optional[str] = None) -> List[Dict[str, Any]]:
    q = resolve_list_scope(STL_COLL, {}, ctx, entity_id)
    if cash_advance_id:
        q["cash_advance_id"] = cash_advance_id
    if status:
        q["status"] = status
    return await db[STL_COLL].find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)


async def get_settlement(stl_id: str, ctx: EntityContext) -> Dict[str, Any]:
    doc = await db[STL_COLL].find_one({"id": stl_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Pertanggungjawaban tidak ditemukan")
    assert_active_entity_access(doc, STL_COLL, ctx)  # KN-B35
    return safe_doc(doc)


async def update_settlement(stl_id: str, payload, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await get_settlement(stl_id, ctx)
    if doc["status"] not in ("draft", "submitted"):
        raise HTTPException(status_code=409, detail="Hanya draft/submitted yang bisa diubah")
    upd: Dict[str, Any] = {}
    for f in ["divisi", "periode", "catatan"]:
        v = getattr(payload, f, None)
        if v is not None:
            upd[f] = v.strip() if isinstance(v, str) else v
    if payload.expense_lines is not None:
        calc = _compute_settlement(payload.expense_lines, doc.get("total_pettycash", 0))
        if not calc["expense_lines"]:
            raise HTTPException(status_code=400, detail="Minimal 1 baris pengeluaran")
        upd.update(calc)
    upd["updated_at"] = now_iso()
    updated = await db[STL_COLL].find_one_and_update(
        {"id": stl_id}, {"$set": upd}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    await audit(actor.get("name", ""), "settlement_updated", "cash_advance_settlement", stl_id, upd)
    return safe_doc(updated)


async def submit_settlement(stl_id: str, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await get_settlement(stl_id, ctx)
    if doc["status"] != "draft":
        raise HTTPException(status_code=409, detail="Hanya draft yang bisa diajukan")
    updated = await db[STL_COLL].find_one_and_update(
        {"id": stl_id}, {"$set": {"status": "submitted", "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    await audit(actor.get("name", ""), "settlement_submitted", "cash_advance_settlement", stl_id, {})
    return safe_doc(updated)


async def approve_settlement(stl_id: str, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await get_settlement(stl_id, ctx)
    if doc["status"] not in ("submitted", "draft"):
        raise HTTPException(status_code=409, detail="Hanya draft/submitted yang bisa disetujui")
    # CX-05 — tutup PD induk atomik LEBIH DULU (disbursed→settling): LPJ kedua tidak dapat memposting.
    try:
        await gl_service.preflight_posting(doc["entity_id"], now_iso())
    except gl_service.ClosedPeriodError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    parent = await db[CA_COLL].find_one_and_update(
        {"id": doc["cash_advance_id"], "status": "disbursed",
         "$or": [{"settling_stl_id": {"$exists": False}}, {"settling_stl_id": stl_id}]},
        {"$set": {"settling_stl_id": stl_id, "updated_at": now_iso()}}, projection={"_id": 0})
    if not parent:
        raise HTTPException(status_code=409, detail="PD induk sudah dipertanggungjawabkan / sedang diproses LPJ lain")
    cat_map = await _category_account_map()
    cat_lines = []
    for cat, amt in (doc.get("category_totals") or {}).items():
        if _r(amt) <= 0:
            continue
        cat_lines.append({"account_code": cat_map.get(cat, FALLBACK_ACCOUNT),
                          "amount": _r(amt), "desc": f"Beban {cat}"})
    try:
        if not cat_lines:
            raise HTTPException(status_code=400, detail="Tidak ada pengeluaran untuk diposting")
        je = await gl_service.post_petty_cash_settlement(
            settlement_id=stl_id, entity_id=doc["entity_id"], category_lines=cat_lines,
            actor_name=actor.get("name", ""), date=now_iso(),
            label=f"{doc['number']} · {doc.get('divisi', '')}".strip(),
            advance_amount=float(parent.get("total_amount") or 0))
    except Exception:
        await db[CA_COLL].update_one({"id": doc["cash_advance_id"], "settling_stl_id": stl_id,
                                      "status": "disbursed"}, {"$unset": {"settling_stl_id": ""}})
        raise
    excess = _r(max(float(doc.get("total_pengeluaran") or 0) - float(parent.get("total_amount") or 0), 0.0))
    updated = await db[STL_COLL].find_one_and_update(
        {"id": stl_id},
        {"$set": {"status": "posted_to_gl", "journal_entry_id": (je or {}).get("id", ""),
                  # CX-05 — kelebihan pengeluaran = Hutang Reimburse Karyawan (2-1650) yang harus dibayar
                  "hutang_reimburse": {"amount": excess, "status": "open" if excess > 0 else "none",
                                       "cash_txn_id": "", "paid_at": ""},
                  "journal_entry_number": (je or {}).get("number", ""),
                  "disetujui_oleh": actor.get("name", ""), "approved_at": now_iso(),
                  "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    # Tandai PD induk sebagai settled
    await db[CA_COLL].update_one({"id": doc["cash_advance_id"], "settling_stl_id": stl_id},
                                 {"$set": {"status": "settled", "settled_by_stl_id": stl_id,
                                           "updated_at": now_iso()}})
    await audit(actor.get("name", ""), "settlement_posted", "cash_advance_settlement", stl_id,
                {"je_id": (je or {}).get("id"), "total": doc.get("total_pengeluaran")})
    return safe_doc(updated)


async def pay_reimburse(stl_id: str, payload, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    """CX-05 — bayar kelebihan LPJ ke karyawan: kas keluar Dr 2-1650 / Cr Kas, menutup saldo hutang
    reimburse LPJ ini. Klaim atomik + resume (kas dari percobaan gagal dipakai ulang)."""
    doc = await get_settlement(stl_id, ctx)
    hr = doc.get("hutang_reimburse") or {}
    if doc.get("status") != "posted_to_gl" or hr.get("status") != "open" or float(hr.get("amount") or 0) <= 0:
        raise HTTPException(status_code=409, detail="LPJ ini tidak punya hutang reimburse terbuka")
    cash_type = getattr(payload, "cash_type", "") if getattr(payload, "cash_type", "") in ("kas_kecil", "kas_besar") else "kas_besar"
    txn_date = getattr(payload, "txn_date", None) or now_iso()
    try:
        await gl_service.preflight_posting(doc["entity_id"], txn_date)
    except gl_service.ClosedPeriodError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    from services import atomic_claim as _saga
    await _saga.claim(STL_COLL, stl_id, "reimburse_pay", precondition={"hutang_reimburse.status": "open"},
                      actor=actor.get("name", ""))
    try:
        txn = await db.cash_transactions.find_one(
            {"ref_type": "reimburse_payable", "ref_id": stl_id, "status": "posted"}, {"_id": 0})
        if not txn:
            txn = {
                "id": new_id("cash"), "number": await _next_cash_number(doc["entity_id"]),
                "cash_type": cash_type, "direction": "out", "amount": _r(hr["amount"]),
                "category": "reimburse karyawan", "description": f"Bayar kelebihan LPJ {doc.get('number', '')}",
                "entity_id": doc["entity_id"], "ref_type": "reimburse_payable", "ref_id": stl_id,
                "txn_date": txn_date, "status": "posted", "created_by": actor.get("name", ""),
                "created_at": now_iso(), "updated_at": now_iso()}
            await db.cash_transactions.insert_one(dict(txn))
        try:
            je = await gl_service.post_cash_durable(txn)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=409, detail=(
                f"Kas {txn['number']} tercatat tetapi jurnal gagal: {exc}. Ulangi untuk melanjutkan."))
        updated = await db[STL_COLL].find_one_and_update(
            {"id": stl_id},
            _saga.finish_set({"hutang_reimburse.status": "paid", "hutang_reimburse.cash_txn_id": txn["id"],
                              "hutang_reimburse.cash_txn_number": txn["number"],
                              "hutang_reimburse.journal_entry_number": (je or {}).get("number", ""),
                              "hutang_reimburse.paid_at": now_iso(), "hutang_reimburse.paid_by": actor.get("name", ""),
                              "updated_at": now_iso()}),
            projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    except Exception:
        await _saga.release(STL_COLL, stl_id)
        raise
    await audit(actor.get("name", ""), "reimburse_paid", "cash_advance_settlement", stl_id,
                {"amount": hr["amount"], "cash_txn_id": txn["id"]})
    return safe_doc(updated)


REIMBURSE_BUCKETS = (("0-7", 7), ("8-14", 14), ("15-30", 30), (">30", None))


def _reimburse_bucket(days: int) -> str:
    for label, upper in REIMBURSE_BUCKETS:
        if upper is None or days <= upper:
            return label
    return ">30"


async def reimburse_payables(ctx: EntityContext, entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Laporan Hutang Reimburse (2-1650) terbuka per karyawan + umur sejak LPJ disetujui."""
    from datetime import datetime, timezone
    q = resolve_list_scope(STL_COLL, {"status": "posted_to_gl", "hutang_reimburse.status": "open"}, ctx, entity_id)
    now = datetime.now(timezone.utc)
    blank = {label: 0.0 for label, _ in REIMBURSE_BUCKETS}
    by_emp: Dict[str, Dict[str, Any]] = {}
    rows: List[Dict[str, Any]] = []
    async for d in db[STL_COLL].find(q, {"_id": 0}):
        amt = _r((d.get("hutang_reimburse") or {}).get("amount") or 0)
        if amt <= 0:
            continue
        ref = d.get("approved_at") or d.get("updated_at") or d.get("created_at") or ""
        try:
            dt = datetime.fromisoformat(str(ref).replace("Z", "+00:00"))
            days = max((now - (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))).days, 0)
        except ValueError:
            days = 0
        bucket = _reimburse_bucket(days)
        emp = (d.get("dibuat_oleh") or d.get("created_by") or "—").strip() or "—"
        e = by_emp.setdefault(emp, {"employee": emp, "outstanding": 0.0, "count": 0, "oldest_days": 0,
                                     "aging": dict(blank)})
        e["outstanding"] = _r(e["outstanding"] + amt)
        e["count"] += 1
        e["oldest_days"] = max(e["oldest_days"], days)
        e["aging"][bucket] = _r(e["aging"][bucket] + amt)
        rows.append({"id": d["id"], "number": d.get("number"), "employee": emp,
                     "cash_advance_number": d.get("cash_advance_number", ""), "entity_id": d.get("entity_id"),
                     "divisi": d.get("divisi", ""), "approved_at": d.get("approved_at", ""),
                     "amount": amt, "days": days, "bucket": bucket})
    aging = dict(blank)
    for r in rows:
        aging[r["bucket"]] = _r(aging[r["bucket"]] + r["amount"])
    rows.sort(key=lambda r: (-r["days"], -r["amount"]))
    return {"total_outstanding": _r(sum(r["amount"] for r in rows)), "aging": aging,
            "buckets": [label for label, _ in REIMBURSE_BUCKETS],
            "by_employee": sorted(by_emp.values(), key=lambda e: (-e["oldest_days"], -e["outstanding"])),
            "items": rows}


async def reject_settlement(stl_id: str, reason: str, ctx: EntityContext, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await get_settlement(stl_id, ctx)
    if doc["status"] not in ("submitted", "draft"):
        raise HTTPException(status_code=409, detail="Hanya draft/submitted yang bisa ditolak")
    updated = await db[STL_COLL].find_one_and_update(
        {"id": stl_id},
        {"$set": {"status": "rejected", "rejected_reason": (reason or "").strip(), "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    await audit(actor.get("name", ""), "settlement_rejected", "cash_advance_settlement", stl_id,
                {"reason": reason})
    return safe_doc(updated)
