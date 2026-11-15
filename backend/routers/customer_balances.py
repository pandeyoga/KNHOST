"""CR-T2 — jadwal tagihan dan saldo piutang tersimpan per pelanggan per PT (`docs/blueprint/unit/CR-T2.md`).

  GET  /api/customers/{id}/billing-schedule?entity_id=   payment_plan.view + can_access_customer
  GET  /api/customers/{id}/balance?entity_id=            salah satu: payment_plan.view, credit_profile.view (+ can_view_credit)
  POST /api/ar/balances/rebuild                          accounting.manage — pembangun ulang saldo (PT dari konteks)

PT selalu lewat `resolve_requested_entity` (N1): di luar penugasan → 403. Logika di `services/billing_schedule_service.py`
dan `services/customer_balance_service.py`.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from core_utils import safe_doc
from db import db
from dependencies import audit, require_any_permission, require_permission
from entity_scope import entity_ctx, resolve_requested_entity
from services import billing_schedule_service as bss
from services import customer_balance_service as cbs
from services.customer_service import can_access_customer, can_view_credit

router = APIRouter(prefix="/api")

MODUL = "Uang Masuk, Piutang & Faktur Pajak"
PESAN_JADWAL = f"Anda belum punya akses untuk melihat jadwal tagihan pelanggan. Minta Admin menambahkan akses '{MODUL}'."
PESAN_SALDO = f"Anda belum punya akses untuk melihat saldo piutang pelanggan. Minta Admin menambahkan akses '{MODUL}'."
PESAN_BANGUN = ("Anda belum punya akses untuk membangun ulang saldo piutang. Minta Admin menambahkan akses "
                "'Akuntansi & Buku Besar'.")
LUAR_CAKUPAN = "Pelanggan ini di luar cakupan Anda."
#: Label jenis baris jadwal tagihan untuk layar (kode mentah tidak tampil).
KIND_LABEL = {"shipment": "Surat jalan", "dp": "Uang muka", "debit_note": "Nota debit", "installment": "Cicilan",
              "milestone": "Tahap", "retention": "Retensi"}


async def _pelanggan(customer_id: str) -> Dict[str, Any]:
    c = safe_doc(await db.customers.find_one({"id": customer_id}, {"_id": 0}))
    if not c:
        raise HTTPException(status_code=404, detail="Pelanggan tidak ditemukan.")
    return c


@router.get("/customers/{customer_id}/billing-schedule")
async def billing_schedule(customer_id: str, request: Request, entity_id: Optional[str] = None,
                           status: str = Query("open", pattern="^(open|all)$"), page: int = Query(1, ge=1),
                           page_size: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
    """Baris jadwal tagihan pelanggan di satu PT (terbuka dulu, jatuh tempo tertua dulu), berhalaman. `status=all`
    ikut baris yang sudah lunas."""
    actor = await require_permission(request, "payment_plan", "view", detail=PESAN_JADWAL)
    customer = await _pelanggan(customer_id)
    if not await can_access_customer(actor, customer):
        raise HTTPException(status_code=403, detail=LUAR_CAKUPAN)
    eid = resolve_requested_entity(await entity_ctx(request), entity_id)
    from services.customer_service import DEAD_STATUSES
    q: Dict[str, Any] = {"customer_id": customer_id, "entity_id": eid, "status": {"$nin": sorted(DEAD_STATUSES)},
                         "order_type": {"$ne": "sample"}}
    if status == "open":
        q["payment_status"] = {"$ne": "paid"}
    orders = [o async for o in db.sales_orders.find(q, {"_id": 0})]
    per = await bss.lines_for_orders(orders, {customer_id: customer})
    rows = [r for v in per.values() for r in v["rows"] if status == "all" or r["outstanding"] > 0.0049]
    rows.sort(key=lambda r: (r["outstanding"] <= 0.0049, r["due_date"] or "9999-12-31", r["order_number"], r["seq"]))
    for r in rows:
        r["kind_label"] = KIND_LABEL.get(r["kind"], "Tagihan")
    total = len(rows)
    start = (page - 1) * page_size
    return {"customer": {"id": customer["id"], "name": customer.get("name", "")}, "entity_id": eid,
            "items": rows[start:start + page_size], "total": total, "page": page, "page_size": page_size,
            "totals": {"amount": round(sum(r["amount"] for r in rows), 2),
                       "paid_amount": round(sum(r["paid_amount"] for r in rows), 2),
                       "outstanding": round(sum(r["outstanding"] for r in rows), 2)},
            "note": "Umur dihitung per tagihan: surat jalan, uang muka, atau baris rencana."}


@router.get("/customers/{customer_id}/balance")
async def customer_balance(customer_id: str, request: Request, entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Saldo piutang tersimpan (pelanggan, PT) + `days_overdue` (dihitung saat baca)."""
    actor = await require_any_permission(request, [("payment_plan", "view"), ("credit_profile", "view")],
                                         detail=PESAN_SALDO)
    customer = await _pelanggan(customer_id)
    if not can_view_credit(actor, customer):
        raise HTTPException(status_code=403, detail=LUAR_CAKUPAN)
    eid = resolve_requested_entity(await entity_ctx(request), entity_id)
    return await cbs.get(customer_id, eid)


@router.post("/ar/balances/rebuild")
async def rebuild_balances(request: Request, entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Bangun ulang saldo piutang tersimpan semua pelanggan satu PT (hitung ulang penuh; hanya yang berbeda ditulis)."""
    actor = await require_permission(request, "accounting", "manage", detail=PESAN_BANGUN)
    eid = resolve_requested_entity(await entity_ctx(request), entity_id)
    res = await cbs.rebuild_all(eid)
    await audit(actor.get("name", ""), "customer_balances_rebuilt", "customer_balances", eid,
                {"pairs": res["pairs"], "changed": res["changed"]})
    return {"entity_id": eid, "pairs": res["pairs"], "changed": res["changed"], "seconds": res["seconds"]}
