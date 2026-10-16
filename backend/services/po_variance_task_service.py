"""W2-REQ-06 — tugas keputusan MD atas selisih penerimaan PO (tunggu / amendment / short-close).

Nilai PO, tagihan dan DP TIDAK diubah otomatis; keputusan dicatat dengan alasan & jejak.
"""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
from dependencies import audit
from core_utils import new_id, now_iso, safe_doc

DECISIONS = ("wait", "amend", "short_close")
DECISION_LABEL = {"wait": "Tunggu sisa kiriman", "amend": "Amendment ke qty aktual",
                  "short_close": "Tutup-kurang (short-close)"}


async def _responsible_user(po: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    uid = po.get("md_owner_id") or po.get("created_by_id")
    q = {"id": uid} if uid else {"name": po.get("created_by") or "__none__"}
    return await db.users.find_one(q, {"_id": 0, "id": 1, "name": 1, "role": 1})


def _has_finance_trail(po: Dict[str, Any]) -> bool:
    return bool(float(po.get("amount_paid") or 0) > 0 or int(po.get("bill_count") or 0) > 0
                or po.get("payments") or float(po.get("dp_amount") or 0) > 0)


async def _tolerance_pct(entity_id: str) -> float:
    from services.config_service import get_effective_settings
    return float(((await get_effective_settings(entity_id)).get("purchasing", {}) or {})
                 .get("receive_tolerance_percent", 2.0) or 0)


async def ensure_for_po(po_id: str, source_ref: str = "", actor_name: str = "Sistem") -> List[Dict[str, Any]]:
    """Buat (idempoten) satu tugas terbuka per baris PO yang kurang terima di luar toleransi."""
    from routers.purchase_orders import TERMINAL_PO_STATUSES
    from services import notification_service as notif
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    if not po or po.get("status") in TERMINAL_PO_STATUSES:
        return []
    tol = await _tolerance_pct(po.get("entity_id") or "")
    owner = await _responsible_user(po)
    created: List[Dict[str, Any]] = []
    for idx, it in enumerate(po.get("items") or []):
        ordered = float(it.get("quantity") or 0)
        received = float(it.get("received_qty") or 0)
        short = round(ordered - received, 2)
        # G3 V3-PO-01 — identitas tugas = BARIS PO (line_id / indeks), bukan product_id; dua baris
        # legacy produk sama memberi dua tugas. Tugas terbuka DIPERBARUI saat penerimaan berubah.
        line_key = it.get("line_id") or f"{it.get('product_id')}#{idx}"
        open_q = {"po_id": po_id, "status": "open",
                  "$or": [{"line_key": line_key},
                          {"line_key": {"$exists": False}, "product_id": it.get("product_id")}]}
        within = received <= 0 or short <= ordered * tol / 100 + 1e-6
        existing = await db.po_variance_tasks.find_one(open_q, {"_id": 0, "id": 1})
        if existing:
            upd = ({"status": "obsolete", "closed_reason": "selisih tertutup penerimaan berikutnya",
                    "received_qty": received, "short_qty": max(short, 0.0), "updated_at": now_iso()} if within else
                   {"line_key": line_key, "ordered_qty": ordered, "received_qty": received, "short_qty": short,
                    "suggested_qty": received, "updated_at": now_iso()})
            await db.po_variance_tasks.update_one({"id": existing["id"], "status": "open"}, {"$set": upd})
            continue
        if within:
            continue
        key = {"po_id": po_id, "product_id": it.get("product_id"), "line_key": line_key, "status": "open"}
        task = {
            "id": new_id("pvt"), **key, "entity_id": po.get("entity_id"),
            "po_number": po.get("po_number"), "supplier_name": po.get("supplier_name"),
            "product_name": it.get("product_name") or it.get("name") or "", "unit": it.get("unit", ""),
            "ordered_qty": ordered, "received_qty": received, "short_qty": short, "tolerance_pct": tol,
            "unit_price": float(it.get("unit_price") or it.get("price") or 0),
            "assignee_id": (owner or {}).get("id", ""), "assignee_name": (owner or {}).get("name", po.get("created_by", "")),
            "finance_notified": _has_finance_trail(po), "source_ref": source_ref,
            "created_at": now_iso(), "created_by": actor_name,
        }
        res = await db.po_variance_tasks.update_one(key, {"$setOnInsert": dict(task)}, upsert=True)
        if not res.upserted_id:
            continue
        created.append(task)
        body = (f"{po.get('po_number')} · {task['product_name']}: diterima {received:g} dari {ordered:g} {task['unit']} "
                f"(kurang {short:g}). Putuskan: tunggu sisa / amendment / short-close.")
        link = f"?view=purchase-orders&po={po_id}"
        if task["assignee_id"]:
            await notif.create_notification(notif_type="po_variance_decision", title="Keputusan selisih penerimaan PO",
                                            body=body, severity="warning", link=link, entity_id=po.get("entity_id"),
                                            recipient_role="", recipient_user=task["assignee_id"], ref=task["id"])
        else:
            await notif.create_notification(notif_type="po_variance_decision", title="Keputusan selisih penerimaan PO",
                                            body=body, severity="warning", link=link, entity_id=po.get("entity_id"),
                                            recipient_role="md", ref=task["id"])
        if task["finance_notified"]:
            await notif.create_notification(notif_type="po_variance_finance", title="Selisih terima pada PO ber-DP/tagihan",
                                            body=body + " PO sudah punya DP/pembayaran/tagihan — nilai tidak diubah otomatis.",
                                            severity="warning", link=link, entity_id=po.get("entity_id"),
                                            recipient_role="finance", ref=task["id"])
        await audit(actor_name, "po_variance_task_created", "purchase_order", po_id,
                    {"task_id": task["id"], "product_id": task["product_id"], "short_qty": short},
                    scope_entity_id=po.get("entity_id") or "")
    return created


async def ensure_for_grn(grn: Dict[str, Any], actor_name: str) -> int:
    task_ids = {(ln.get("target") or {}).get("task_id") for ln in grn.get("lines") or []
                if (ln.get("target") or {}).get("type") == "po_task"}
    po_ids = {t["po_id"] for t in await db.wms_tasks.find(
        {"id": {"$in": [t for t in task_ids if t]}}, {"_id": 0, "po_id": 1}).to_list(500) if t.get("po_id")}
    n = 0
    for pid in po_ids:
        n += len(await ensure_for_po(pid, grn.get("id", ""), actor_name))
    return n


async def list_tasks(scope_ids: List[str], status: str = "open", po_id: str = "") -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"entity_id": {"$in": scope_ids}}
    if status:
        q["status"] = status
    if po_id:
        q["po_id"] = po_id
    return [safe_doc(d) for d in await db.po_variance_tasks.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)]


async def decide(task_id: str, decision: str, reason: str, actor: Dict[str, Any], scope_ids: List[str],
                 short_close) -> Dict[str, Any]:
    if decision not in DECISIONS:
        raise HTTPException(status_code=422, detail="Keputusan harus wait | amend | short_close")
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise HTTPException(status_code=422, detail="Alasan keputusan wajib (min. 5 karakter).")
    task = await db.po_variance_tasks.find_one({"id": task_id}, {"_id": 0})
    if not task or task.get("entity_id") not in scope_ids:
        raise HTTPException(status_code=404, detail="Tugas selisih tidak ditemukan")
    if task["status"] != "open":
        if task.get("decision") == decision:
            return safe_doc(task)   # retry idempoten
        raise HTTPException(status_code=409, detail=f"Tugas sudah diputuskan: {task.get('decision')}")
    po = await db.purchase_orders.find_one({"id": task["po_id"]}, {"_id": 0})
    before = {k: (po or {}).get(k) for k in ("status", "grand_total", "amount_paid", "billed_total", "unbilled_total")}
    claim = await db.po_variance_tasks.find_one_and_update(
        {"id": task_id, "status": "open"},
        {"$set": {"status": "deciding", "decision": decision, "updated_at": now_iso()}})
    if not claim:
        raise HTTPException(status_code=409, detail="Tugas sedang diputuskan proses lain.")
    try:
        if decision == "wait":
            from services.goods_receipt_close_service import ensure_remainder_task
            follow = await ensure_remainder_task(task["po_id"], task["product_id"], actor["name"])
        elif decision == "short_close":
            await short_close(task["po_id"], actor, f"Keputusan selisih {task_id}: {reason}")
            follow = {"po_status": "closed_short"}
        else:
            # Amendment memakai alur amandemen PO + re-approval yang sudah ada; nilai tidak diubah di sini.
            # G3 V3-PO-01 — saran qty dari PO TERKINI (bukan snapshot tugas yang bisa basi)
            items = (po or {}).get("items") or []
            live = next((i for n, i in enumerate(items)
                         if (i.get("line_id") or f"{i.get('product_id')}#{n}") == task.get("line_key")), None) \
                or next((i for i in items if i.get("product_id") == task.get("product_id")), {})
            follow = {"next": "amend", "suggested_qty": float(live.get("received_qty") or task["received_qty"]),
                      "link": f"?view=purchase-orders&po={task['po_id']}&amend=1"}
    except HTTPException:
        await db.po_variance_tasks.update_one({"id": task_id}, {"$set": {"status": "open"}, "$unset": {"decision": ""}})
        raise
    status = "pending_amendment" if decision == "amend" else "decided"
    await db.po_variance_tasks.update_one({"id": task_id}, {"$set": {
        "status": status, "decision": decision, "decision_label": DECISION_LABEL[decision], "reason": reason,
        "decided_by": actor["name"], "decided_at": now_iso(), "before": before, "follow_up": follow}})
    await audit(actor["name"], "po_variance_decided", "purchase_order", task["po_id"],
                {"task_id": task_id, "decision": decision, "before": before}, reason=reason,
                scope_entity_id=task.get("entity_id") or "")
    return safe_doc(await db.po_variance_tasks.find_one({"id": task_id}, {"_id": 0}))


async def close_amendment_tasks(po_id: str, actor_name: str) -> int:
    """G3 V3-PO-03 — tugas `pending_amendment` selesai HANYA bila PO sudah disetujui (bukan
    menunggu approval) DAN qty baris tugas itu kini = qty diterima (selisih benar-benar ditutup).
    Amandemen catatan saja / baris lain tidak menutup tugas."""
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0, "status": 1, "items": 1})
    if not po or po.get("status") in ("waiting_approval", "draft", "rejected"):
        return 0
    closed = 0
    async for t in db.po_variance_tasks.find({"po_id": po_id, "status": "pending_amendment"}, {"_id": 0}):
        items = po.get("items") or []
        it = next((i for n, i in enumerate(items)
                   if (i.get("line_id") or f"{i.get('product_id')}#{n}") == t.get("line_key")), None) \
            or (None if t.get("line_key") else next((i for i in items if i.get("product_id") == t.get("product_id")), None))
        if not it or float(it.get("quantity") or 0) > float(it.get("received_qty") or 0) + 0.001:
            continue
        res = await db.po_variance_tasks.update_one(
            {"id": t["id"], "status": "pending_amendment"},
            {"$set": {"status": "decided", "amended_at": now_iso(), "amended_by": actor_name,
                      "amended_qty": float(it.get("quantity") or 0)}})
        closed += res.modified_count
    return closed
