"""Kunci saga (T-01 Opsi B) — daftar & lepas `saga_lock` yang menggantung (admin)."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, HTTPException, Request
from db import db
from dependencies import require_role, audit
from services.atomic_claim import LOCK

router = APIRouter(prefix="/api")

# Koleksi induk yang endpoint-nya memakai `atomic_claim.claim()` — sumber: INV-ATOMIC-01.
LOCKED_COLLECTIONS = ["wms_tasks", "sales_orders", "warehouse_transfers", "cycle_count_sessions",
                      "purchase_returns", "sales_returns", "putaway_orders",
                      "vendor_bills", "payment_variance_decisions", "ar_receipts", "sample_requests", "crm_leads", "period_closings",
                      "product_categories", "special_orders", "esign_requests", "tax_invoices_in", "landed_cost_vouchers",
                      "makloon_orders", "rfid_verify_sessions", "product_templates", "rfqs", "products", "business_entities", "md_specs",
                      "mfg_work_orders", "internal_requests",
                      # OPS-04 (P21) — koleksi ber-claim() yang dulu terlewat: kuncinya tak terlihat & tak bisa dilepas.
                      "goods_receipts", "purchase_orders", "purchase_requisitions", "customers", "bank_statement_lines"]


@router.get("/saga-locks")
async def list_saga_locks(request: Request) -> List[Dict[str, Any]]:
    await require_role(request, ["admin"])
    out: List[Dict[str, Any]] = []
    for coll in LOCKED_COLLECTIONS:
        async for d in db[coll].find({LOCK: {"$exists": True}}, {"_id": 0, "id": 1, "status": 1, LOCK: 1}):
            out.append({"collection": coll, **d})
    return out


LOCK_ACTIVE_SECONDS = 300
# GN-11 — efek hilir yang mungkin sudah terposting oleh saga yang mati: (koleksi, filter-field, field waktu)
EFFECT_SOURCES = [
    ("journal_entries", "source_id", "created_at"),
    ("inventory_movements", "source_document", "timestamp"),
    ("shipments", "task_id", "created_at"),
    ("cash_transactions", "source_id", "created_at"),
    ("inventory_rolls", "source_ref.id", "created_at"),
]


async def inspect_effects(collection: str, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Efek yang tercatat SESUDAH kunci diklaim dan merujuk dokumen ini (id atau nomor dokumen)."""
    lock = doc.get(LOCK) or {}
    since = lock.get("started_at") or ""
    keys = [k for k in {doc.get("id"), doc.get("number"), doc.get("task_number"), doc.get("order_number")} if k]
    out: List[Dict[str, Any]] = []
    for coll, field, tfield in EFFECT_SOURCES:
        q = {field: {"$in": keys}, tfield: {"$gte": since}}
        n = await db[coll].count_documents(q)
        if n:
            sample = await db[coll].find(q, {"_id": 0, "id": 1, "number": 1, "shipment_no": 1}).limit(5).to_list(5)
            out.append({"collection": coll, "count": n,
                        "samples": [x.get("number") or x.get("shipment_no") or x.get("id") for x in sample]})
    return out


def _lock_age_seconds(lock: Dict[str, Any]) -> float:
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(str(lock.get("started_at")).replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))).total_seconds()
    except ValueError:
        return 1e9


async def _locked_doc(collection: str, doc_id: str) -> Dict[str, Any]:
    if collection not in LOCKED_COLLECTIONS:
        raise HTTPException(status_code=404, detail="Koleksi tidak dikenal.")
    doc = await db[collection].find_one({"id": doc_id, LOCK: {"$exists": True}},
                                        {"_id": 0, "id": 1, "number": 1, "task_number": 1, "order_number": 1,
                                         "status": 1, LOCK: 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Tidak ada kunci saga pada dokumen ini.")
    return doc


@router.get("/saga-locks/{collection}/{doc_id}/inspect")
async def inspect_saga_lock(collection: str, doc_id: str, request: Request) -> Dict[str, Any]:
    """GN-11 — apa yang sudah terjadi sebelum saga mati (efek hilir) + apakah kunci masih aktif."""
    await require_role(request, ["admin"])
    doc = await _locked_doc(collection, doc_id)
    lock = doc[LOCK]
    return {"collection": collection, "id": doc_id, "status": doc.get("status"), "lock": lock,
            "active": _lock_age_seconds(lock) < LOCK_ACTIVE_SECONDS and not lock.get("failed_at"),
            "effects": await inspect_effects(collection, doc)}


@router.post("/saga-locks/{collection}/{doc_id}/release")
async def release_saga_lock(collection: str, doc_id: str, request: Request,
                            payload: Optional[Dict[str, Any]] = Body(None)) -> Dict[str, Any]:
    """GN-11 — lepas kunci hanya bila: tidak aktif (basi/ gagal), alasan tercatat, efek hilir yang sudah
    terposting diakui eksplisit, dan kunci yang dilepas = kunci yang diperiksa (fencing token/started_at)."""
    actor = await require_role(request, ["admin"])
    payload = payload or {}
    doc = await _locked_doc(collection, doc_id)
    lock = doc[LOCK]
    reason = str(payload.get("reason") or "").strip()
    if len(reason) < 10:
        raise HTTPException(status_code=400, detail="Alasan pelepasan kunci wajib (min. 10 karakter).")
    if _lock_age_seconds(lock) < LOCK_ACTIVE_SECONDS and not lock.get("failed_at"):
        raise HTTPException(status_code=409, detail=(
            f"Kunci masih aktif (diklaim {lock.get('started_at')}) — tunggu {LOCK_ACTIVE_SECONDS // 60} menit "
            "atau sampai proses tercatat gagal."))
    effects = await inspect_effects(collection, doc)
    if effects and not payload.get("acknowledge_effects"):
        raise HTTPException(status_code=409, detail={
            "code": "SAGA_EFFECTS_PRESENT",
            "message": "Sebagian efek sudah terposting — periksa sebelum menjalankan ulang (aksi ulang bisa menggandakan).",
            "effects": effects})
    expected = payload.get("lock_token") or lock.get("token")
    fence = {"id": doc_id, f"{LOCK}.started_at": lock.get("started_at")}
    if expected:
        fence[f"{LOCK}.token"] = expected
    res = await db[collection].update_one(fence, {"$unset": {LOCK: ""}})
    if res.modified_count != 1:
        raise HTTPException(status_code=409, detail="Kunci berubah sejak diperiksa (diklaim ulang) — muat ulang.")
    await audit(actor["name"], "saga_lock_released", collection, doc_id,
                {"lock": lock, "effects": effects, "acknowledged": bool(effects)}, reason=reason)
    return {"released": True, "collection": collection, "id": doc_id, "lock": lock, "effects": effects}
