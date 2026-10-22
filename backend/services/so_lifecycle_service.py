"""Inti siklus SO yang dipakai bersama rute & `so_release_service` (Trial 22 Okt 2026, E8): **ajukan persetujuan**
(`submit_core`) dan **konfirmasi / lepas ke gudang** (`confirm_core`). Dipindah dari `routers/sales_orders_extra.py`
supaya "Periksa & lepas ke gudang" memakai logika yang SAMA dengan tombol lama (tanpa salinan)."""
import logging
from typing import Any, Dict

from fastapi import HTTPException

from core_utils import now_iso, rupiah, safe_doc, strip_cost_fields
from db import db
from dependencies import audit
from services import so_approvals
from services.config_service import evaluate_approval, get_effective_settings
from services.fulfillment_status import create_outbound_tasks_for_order, recompute_so_status
from services.roll_service import set_order_rolls_status
from services.sales_order_helpers import so_transition as _transition

logger = logging.getLogger(__name__)


async def submit_core(order: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Inti "Ajukan persetujuan" (dipakai rute & `so_release_service` — Trial 22 Okt E8: Periksa & lepas ke gudang)."""
    order_id = order["id"]
    # Fase 1B — re-evaluasi kebutuhan approval dari matriks (configurable) basis grand_total
    amount = float(order.get("grand_total", order.get("total_amount", 0)) or 0)
    appr = await evaluate_approval("sales_order", amount, order.get("entity_id"))
    settings_eff = await get_effective_settings(order.get("entity_id"))
    require_val = so_approvals.require_validation_default(settings_eff)
    summ = so_approvals.summarize(order)
    # F5/RBAC — SO WAJIB divalidasi admin/manager (default). Tidak ada auto-approve oleh sales.
    needs = bool(appr["requires_approval"] or summ["has_pending"] or require_val)
    req_role = appr["required_role"] or summ["required_role"] or ("manager" if require_val else "")
    # Pastikan ada entri 'nilai' sebagai penanda validasi bila belum ada approval spesifik.
    pa = list(order.get("pending_approvals") or [])
    if needs and not any(p.get("type") == "nilai" and p.get("status") == "pending" for p in pa) \
            and not any(p.get("type") in ("kredit", "special_price", "makloon") and p.get("status") == "pending" for p in pa):
        pa.append(so_approvals.make_approval(
            "nilai", required_role=req_role or "manager",
            reason="Validasi admin atas pesanan." if not appr["requires_approval"]
                   else f"Nilai order {rupiah(amount)} memerlukan persetujuan.",
            requested_by=actor["name"], requested_by_id=actor["id"], amount=amount,
        ))
    await db.sales_orders.update_one({"id": order_id}, {"$set": {
        "pending_approvals": pa,
        "approval_required": needs,
        "required_approval_role": req_role,
        "approval_amount": amount, "updated_at": now_iso(),
    }})
    if needs:
        return strip_cost_fields(
            await _transition(order_id, ["reserved", "waiting_stock"], "waiting_approval", actor["name"],
                              "order_submitted", {"required_approval_role": req_role}),
            actor.get("role"))
    # Validasi nonaktif & di bawah ambang → auto-approve + hard-commit roll
    result = await _transition(order_id, ["reserved"], "approved", actor["name"],
                               "order_auto_approved",
                               {"approval_note": "Auto-approve (validasi nonaktif, di bawah threshold)"})
    await set_order_rolls_status(order_id, "committed")
    return strip_cost_fields(result, actor.get("role"))


async def confirm_core(order_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Inti "Konfirmasi / lepas ke gudang" (dipakai rute & `so_release_service`)."""
    # FASE E-8 (E8.13) — gerbang VERIFIKASI ADMINISTRATIF (bawaan HIDUP sejak T1 2026-06).
    # Sengaja diperiksa SEBELUM transisi: kalau pesanan sudah jadi `confirmed`,
    # tugas gudang lahir dan penolakan sesudahnya tidak lagi menolong siapa pun.
    _pre = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0}))
    if _pre:
        # Urutan mengikuti dokumen training: verifikasi Admin Sales dulu (E8.13),
        # baru persetujuan manajer, baru konfirmasi.
        from services import so_verify_service as _verify
        await _verify.assert_ready_to_confirm(_pre)
        # T1 (audit training 2026-06) — persetujuan manajer TIDAK boleh dilompati:
        # pesanan yang masih menunggu keputusan (nilai/kredit/validasi) tidak boleh
        # langsung `confirmed` dari `reserved`/`waiting_approval`.
        if _pre.get("status") != "approved" and (
                _pre.get("approval_required") or not so_approvals.all_approved(_pre)):
            raise HTTPException(
                status_code=409,
                detail=(f"Pesanan {_pre.get('number')} belum disetujui manajer "
                        f"(status: {_pre.get('status')}). Ajukan/tunggu persetujuan "
                        "nilai & kredit dulu — konfirmasi hanya untuk pesanan berstatus "
                        "Disetujui."))
    result = await _transition(order_id, ["approved", "waiting_approval", "reserved"], "confirmed",
                               actor["name"], "order_confirmed")
    # Sub-fase 1.8 — otomatis buat task outbound saat confirmed (idempotent)
    tasks = await create_outbound_tasks_for_order(order_id, actor["name"])
    if tasks:
        await audit(actor["name"], "outbound_tasks_auto_created", "sales_order", order_id,
                    {"tasks_count": len(tasks)})
    await recompute_so_status(order_id)
    _final = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0}))
    # Fase 5 — auto-kirim WhatsApp bila ada aturan aktif (best-effort, non-blocking).
    try:
        from services import delivery_service as _ds
        await _ds.dispatch_event("sales_order", order_id, "confirmed",
                                 (_final or {}).get("entity_id"), actor["name"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("[confirm_order] efek samping gagal diabaikan: %s", exc)  # KN-C10
    return _final
