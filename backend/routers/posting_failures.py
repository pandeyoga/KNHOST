"""Panel Posting Gagal — daftar dokumen dengan jurnal gagal (gl_status=failed) + ulang posting.

Sumber: kas, kwitansi AR, retur beli, tugas penerimaan (GR) dan surat jalan (pendapatan/HPP).
Ulang posting memakai jalur idempotent masing-masing modul (tidak menggandakan jurnal).
"""
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request

from db import db
from core_utils import now_iso
from dependencies import require_permission, audit
from entity_scope import entity_ctx, resolve_scope_ids

router = APIRouter(prefix="/api")

SOURCES = {
    "cash_transaction": ("cash_transactions", {"gl_status": "failed"}, "entity_id", "number"),
    "ar_receipt": ("ar_receipts", {"gl_status": "failed"}, "entity_id", "number"),
    "purchase_return": ("purchase_returns", {"gl_status": "failed"}, "entity_id", "number"),
    "goods_receipt": ("wms_tasks", {"gl_posting.status": "failed"}, "gl_posting.entity_id", "po_number"),
    "shipment": ("shipments", {"gl_status": "failed"}, "entity_id", "shipment_no"),
    "contra_bon": ("contra_bons", {"gl_status": "failed"}, "entity_id", "number"),   # PK-05 — jurnal potongan
    # PK-06 — jurnal kembar antar-PT, satu baris per SISI (PT) yang gagal
    "interco_transaction": ("interco_transactions", {"gl_status": "failed"}, "entity_id", "number"),
    "interco_return": ("interco_returns", {"gl_status": "failed"}, "entity_id", "number"),
    "interco_settlement_payer": ("interco_settlements", {"gl_status_payer": "failed"}, "payer_entity_id", "number"),
    "interco_settlement_payee": ("interco_settlements", {"gl_status_payee": "failed"}, "payee_entity_id", "number"),
    # PK-30 — jurnal penyesuaian panjang roll antar-PT, satu baris per sisi (PT) yang gagal
    "interco_adj": ("interco_transactions", {"gl_status_adj": "failed"}, "entity_id", "number"),
}
LABELS = {"cash_transaction": "Transaksi Kas", "ar_receipt": "Kwitansi AR", "purchase_return": "Retur Beli",
          "goods_receipt": "Penerimaan Barang (GR)", "shipment": "Surat Jalan",
          "contra_bon": "Kontrabon (jurnal potongan)", "interco_transaction": "Transaksi Antar-PT",
          "interco_return": "Retur Antar-PT", "interco_settlement_payer": "Pelunasan Antar-PT (pembayar)",
          "interco_settlement_payee": "Pelunasan Antar-PT (penerima)",
          "interco_adj": "Penyesuaian Panjang Antar-PT"}


def _pick(doc: Dict[str, Any], dotted: str) -> Any:
    for k in dotted.split("."):
        doc = (doc or {}).get(k) if isinstance(doc, dict) else None
    return doc


def _row(kind: str, d: Dict[str, Any]) -> Dict[str, Any]:
    _, _, ent_f, num_f = SOURCES[kind]
    glp = d.get("gl_posting") or {}
    if kind == "interco_adj":   # PK-30 — nominal & galat milik jurnal penyesuaian, bukan jurnal konfirmasi
        return {"kind": kind, "kind_label": LABELS[kind], "id": d["id"], "number": d.get(num_f) or d["id"],
                "entity_id": _pick(d, ent_f) or "",
                "amount": abs(float((d.get("length_adjustment") or {}).get("delta_total") or 0)),
                "error": d.get("gl_error_adj") or "", "updated_at": d.get("updated_at") or d.get("created_at") or ""}
    return {"kind": kind, "kind_label": LABELS[kind], "id": d["id"],
            "number": d.get(num_f) or d.get("number") or d["id"],
            "entity_id": _pick(d, ent_f) or "",
            "amount": d.get("amount") or d.get("grand_total") or d.get("total_applied") or glp.get("amount")
            or d.get("qty") or 0,
            "error": (d.get("gl_error_payer") if kind == "interco_settlement_payer" else
                      d.get("gl_error_payee") if kind == "interco_settlement_payee" else None)
            or d.get("gl_error") or glp.get("error") or "",
            "updated_at": d.get("updated_at") or glp.get("at") or d.get("created_at") or ""}


async def _scoped_find(kind: str, scope: List[str], extra: Dict[str, Any]) -> List[Dict[str, Any]]:
    coll, q, ent_f, _ = SOURCES[kind]
    return await db[coll].find({**q, **extra, ent_f: {"$in": scope}}, {"_id": 0}).sort(
        "updated_at", -1).to_list(500)


@router.get("/finance/posting-failures")
async def list_posting_failures(request: Request) -> Dict[str, Any]:
    await require_permission(request, "accounting", "view")
    scope = resolve_scope_ids(await entity_ctx(request))
    items: List[Dict[str, Any]] = []
    for kind in SOURCES:
        items += [_row(kind, d) for d in await _scoped_find(kind, scope, {})]
    items.sort(key=lambda r: str(r["updated_at"]), reverse=True)
    counts = {k: sum(1 for i in items if i["kind"] == k) for k in SOURCES}
    return {"items": items, "total": len(items), "counts": counts, "labels": LABELS}


async def _retry(kind: str, doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    from services import gl_service as gl
    if kind == "cash_transaction":
        await gl.post_cash_durable(doc)
        if doc.get("ref_type") == "ar_receipt" and doc.get("ref_id"):
            await db.ar_receipts.update_one({"id": doc["ref_id"]}, {"$set": {"gl_status": "posted", "gl_error": ""}})
        if doc.get("payment_intent_id"):   # PK-05 — ringkasan jurnal di niat bayar ikut diperbarui
            from services.ap_payment_service import refresh_gl_status
            await refresh_gl_status(doc["payment_intent_id"])
    elif kind == "contra_bon":
        from services.ap_payment_service import repost_contra_bon
        await repost_contra_bon(doc["id"])
    elif kind in ("interco_transaction", "interco_return", "interco_settlement_payer", "interco_settlement_payee",
                  "interco_adj"):
        if kind == "interco_transaction":
            from services.interco_service import repost_gl
            res = await repost_gl(doc["pair_id"], actor["name"])
        elif kind == "interco_adj":
            from services.interco_service import repost_length_adjustment
            res = await repost_length_adjustment(doc["pair_id"], actor["name"])
        elif kind == "interco_return":
            from services.interco_return_service import repost_gl
            res = await repost_gl(doc["return_pair_id"], actor["name"])
        else:
            from services.interco_service import repost_settlement_gl
            res = await repost_settlement_gl(doc["id"], actor["name"])
        gagal = [v.get("error") for v in (res or {}).values() if v.get("status") == "failed"]
        if gagal:
            raise RuntimeError("; ".join(gagal))
    elif kind == "ar_receipt":
        from services.ar_receipt_service import repost_receipt
        await repost_receipt(doc["id"])
    elif kind == "purchase_return":
        from services.purchase_return_service import approve_and_adjust_stock
        await approve_and_adjust_stock(doc["id"], approved_by=actor["name"])
    elif kind == "goods_receipt":
        from services.goods_receipt_close_service import _ensure_gr_posted
        await _ensure_gr_posted(doc["id"])
    elif kind == "shipment":
        await gl.post_order_revenue_and_cogs(doc["order_id"])
        await db.shipments.update_one({"id": doc["id"]}, {"$set": {"gl_status": "posted", "gl_error": "",
                                                                   "updated_at": now_iso()}})


@router.post("/finance/posting-failures/{kind}/{doc_id}/retry")
async def retry_posting_failure(kind: str, doc_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "accounting", "manage")
    if kind not in SOURCES:
        raise HTTPException(status_code=400, detail="Jenis dokumen tidak dikenal")
    scope = resolve_scope_ids(await entity_ctx(request))
    docs = await _scoped_find(kind, scope, {"id": doc_id})
    if not docs:
        raise HTTPException(status_code=404, detail="Dokumen gagal posting tidak ditemukan (atau sudah terposting)")
    try:
        await _retry(kind, docs[0], actor)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=409, detail=f"Posting masih gagal: {exc}")
    await audit(actor["name"], "posting_failure_retried", kind, doc_id, {})
    coll = SOURCES[kind][0]
    fresh = await db[coll].find_one({"id": doc_id}, {"_id": 0}) or {}
    status = (fresh.get("gl_posting") or {}).get("status") if kind == "goods_receipt" else \
        fresh.get("gl_status_payer") if kind == "interco_settlement_payer" else \
        fresh.get("gl_status_payee") if kind == "interco_settlement_payee" else \
        fresh.get("gl_status_adj") if kind == "interco_adj" else fresh.get("gl_status")
    return {"kind": kind, "id": doc_id, "gl_status": status}


@router.get("/finance/posting-failures/count")
async def count_posting_failures(request: Request) -> Dict[str, Any]:
    """Lencana menu Keuangan — jumlah dokumen dengan jurnal gagal (terbatas entitas pengguna)."""
    await require_permission(request, "accounting", "view")
    scope = resolve_scope_ids(await entity_ctx(request))
    total = 0
    for kind, (coll, q, ent_f, _) in SOURCES.items():
        total += await db[coll].count_documents({**q, ent_f: {"$in": scope}})
    return {"total": total}
