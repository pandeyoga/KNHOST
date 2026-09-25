"""GRN Fase 2 — rekonsiliasi (§4.4), penyelesaian selisih, penutupan (§4.5), sisa PO, tolak & batal.

Posting stok/HPP/GL HANYA lewat `inbound_complete_service.complete_task(..., via_grn=grn)` (tugas PO) dan
`makloon_order_service.receive_step` (langkah MKO). Update baris berprasyarat `posted.status != done` +
kunci saga → klik ganda `close` tidak memposting dua kali.
"""
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from core_utils import new_id, now_iso, safe_doc
from db import db
from dependencies import audit, has_permission
from entity_scope import EntityContext
from services.config_resolver import value_of
from services.goods_receipt_service import ACTIVE_TASK, cas, load, refresh_counted, release_tasks, require_status

BLOCKING = {"short_vs_dn", "rolls_mismatch", "not_arrived", "not_on_dn"}
NEEDS_APPROVE = {"over_remaining", "not_on_dn"}


def allowed_actions(kind: str, partner_type: str) -> List[str]:
    claim = "claim_supplier" if partner_type == "supplier" else "claim_makloon"
    if kind in ("short_vs_dn", "rolls_mismatch", "not_arrived"):
        return ["accept_note", claim]
    if kind in NEEDS_APPROVE:
        return ["accept_note", "reject_goods"]
    return []


async def _remaining_by_task(lines: List[Dict[str, Any]]) -> Dict[str, float]:
    """Sisa baris PO (pesanan − diterima yang SUDAH diposting) per tugas, dalam satuan tugas."""
    out: Dict[str, float] = {}
    for ln in lines:
        tgt = ln.get("target") or {}
        if tgt.get("type") != "po_task" or tgt["task_id"] in out:
            continue
        po = await db.purchase_orders.find_one({"id": tgt["po_id"]}, {"_id": 0, "items": 1}) or {}
        it = next((i for i in po.get("items") or [] if i.get("product_id") == tgt["product_id"]), {})
        out[tgt["task_id"]] = round(float(it.get("quantity") or 0) - float(it.get("received_qty") or 0), 2)
    return out


async def compute_recon(grn: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    ent = {"entity_id": grn["entity_id"]}
    pct = float(await value_of("receiving.line_qty_tolerance_pct", ent) or 0)
    block_over = bool(await value_of("receiving.block_over_remaining", ent))
    lines = [dict(x) for x in grn.get("lines") or []]
    remaining = await _remaining_by_task(lines)
    per_task: Dict[str, float] = {}
    for ln in lines:
        tid = (ln.get("target") or {}).get("task_id")
        if tid and ln.get("decision") == "accept" and not ln.get("is_non_stock"):
            per_task[tid] = per_task.get(tid, 0.0) + float((ln.get("counted") or {}).get("qty") or 0)
    seen_task: set = set()
    found: List[Dict[str, Any]] = []
    for ln in lines:
        n = ln["line_no"]
        if ln.get("is_non_stock"):
            ln["recon"] = {"classes": ["non_stock"]}
            continue
        if ln.get("decision") == "reject_line":
            ln["recon"] = {"classes": ["rejected"]}
            continue
        unit = (ln.get("target") or {}).get("unit", "")
        decl = float((ln.get("converted") or {}).get("qty") or 0)
        c = ln.get("counted") or {}
        cnt = float(c.get("qty") or 0)
        tol = round(max(0.5, decl * pct / 100), 2)
        cls: List[Tuple[str, str]] = []
        if decl <= 0:
            if cnt > 0:
                cls.append(("not_on_dn", f"Dihitung {cnt:g} {unit} padahal baris ini tidak punya qty di surat jalan."))
        elif cnt <= 0:
            cls.append(("not_arrived", f"Surat jalan {decl:g} {unit}, tidak ada roll yang dihitung."))
        elif cnt < decl - tol:
            cls.append(("short_vs_dn", f"Dihitung {cnt:g} {unit}, surat jalan {decl:g} {unit} "
                                       f"(kurang {decl - cnt:g}, toleransi ±{tol:g})."))
        elif cnt > decl + tol:
            cls.append(("over_vs_dn", f"Dihitung {cnt:g} {unit}, surat jalan {decl:g} {unit} (lebih {cnt - decl:g})."))
        d_rolls = (ln.get("declared") or {}).get("rolls")
        if d_rolls not in (None, 0) and cnt > 0 and int(d_rolls) != int(c.get("rolls") or 0):
            cls.append(("rolls_mismatch", f"Roll dihitung {c.get('rolls') or 0}, surat jalan {d_rolls}."))
        d_wt = float((ln.get("declared") or {}).get("weight_kg") or 0)
        c_wt = float(c.get("weight_kg") or 0)
        if d_wt > 0 and c_wt > 0 and (ln.get("declared") or {}).get("weight_basis") == "net" \
                and abs(c_wt - d_wt) > max(0.5, d_wt * pct / 100):
            cls.append(("weight_mismatch", f"Berat netto dihitung {c_wt:g} kg, surat jalan {d_wt:g} kg."))
        tid = (ln.get("target") or {}).get("task_id")
        vs_rem = None
        if tid:
            vs_rem = round(remaining.get(tid, 0.0) - per_task.get(tid, 0.0), 2)
            rem = remaining.get(tid, 0.0)
            if tid not in seen_task and per_task.get(tid, 0.0) > rem + max(0.5, rem * pct / 100):
                cls.append(("over_remaining", f"Total dihitung {per_task[tid]:g} {unit} melebihi sisa PO {rem:g} {unit}."))
            seen_task.add(tid)
        ln["recon"] = {"classes": [k for k, _ in cls] or ["match"], "diff_qty": round(cnt - decl, 2),
                       "diff_pct": round((cnt - decl) / decl * 100, 2) if decl else None,
                       "diff_rolls": (int(c.get("rolls") or 0) - int(d_rolls)) if d_rolls not in (None, 0) else None,
                       "vs_remaining": vs_rem, "tolerance": tol}
        for kind, detail in cls:
            blocking = kind in BLOCKING or (kind == "over_remaining" and block_over)
            found.append({"key": f"L{n}:{kind}", "line_no": n, "kind": kind, "blocking": blocking,
                          "detail": detail, "resolution": None})
    old = {d["key"]: d for d in grn.get("discrepancies") or []}
    for d in found:
        if (old.get(d["key"]) or {}).get("resolution"):
            d["resolution"] = old[d["key"]]["resolution"]
    keys = {d["key"] for d in found}
    for k, d in old.items():   # jejak penyelesaian lama tidak dibuang
        if k not in keys and d.get("resolution"):
            found.append({**d, "blocking": False, "superseded": True})
    return lines, found


def open_blockers(discrepancies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [d for d in discrepancies if d.get("blocking") and not d.get("resolution")]


async def finish_count(grn_id: str, expected_version: int, actor: Dict[str, Any], ctx: EntityContext):
    grn = await load(grn_id, ctx)
    require_status(grn, ["counting"], "Selesai hitung")
    bad = [ln["line_no"] for ln in grn.get("lines") or []
           if ln.get("decision") == "reject_line" and (ln.get("counted") or {}).get("rolls")]
    if bad:
        raise HTTPException(status_code=400, detail=f"Baris {bad} ditolak tetapi masih punya roll — batalkan rollnya dulu.")
    grn = await refresh_counted(grn, actor["name"], expected_version)
    lines, discs = await compute_recon(grn)
    doc = await cas(grn, ["counting"], grn["version"], {"status": "reconcile", "lines": lines,
                                                        "discrepancies": discs, "count_finished_at": now_iso()})
    await audit(actor["name"], "grn_count_finished", "goods_receipt", grn_id,
                {"discrepancies": [d["key"] for d in discs]}, scope_entity_id=grn["entity_id"])
    return doc


async def reopen_count(grn_id: str, expected_version: int, actor: Dict[str, Any], ctx: EntityContext):
    grn = await load(grn_id, ctx)
    require_status(grn, ["reconcile"], "Buka hitung ulang")
    doc = await cas(grn, ["reconcile"], expected_version, {"status": "counting"})
    await audit(actor["name"], "grn_count_reopened", "goods_receipt", grn_id, {}, scope_entity_id=grn["entity_id"])
    return doc


async def _undo_line_rolls(grn: Dict[str, Any], line_no: int) -> None:
    from services.receiving_roll_service import undo_receiving_roll
    for r in await db.inventory_rolls.find({"grn_id": grn["id"], "grn_line_no": line_no, "status": "receiving"},
                                           {"_id": 0}).to_list(2000):
        task = await db.wms_tasks.find_one({"id": r["grn_task_id"]}, {"_id": 0}) or {}
        await undo_receiving_roll(r, task)


async def resolve(grn_id: str, key: str, body: Any, actor: Dict[str, Any], ctx: EntityContext):
    grn = await load(grn_id, ctx)
    require_status(grn, ["reconcile"], "Selesaikan selisih")
    if body.expected_version != grn.get("version"):
        from services.goods_receipt_service import state_changed
        raise state_changed()
    d = next((x for x in grn.get("discrepancies") or [] if x["key"] == key and not x.get("superseded")), None)
    if not d:
        raise HTTPException(status_code=404, detail=f"Selisih {key} tidak ada.")
    if body.action not in allowed_actions(d["kind"], grn["partner_type"]):
        raise HTTPException(status_code=400, detail=(
            f"Aksi {body.action} tidak berlaku untuk selisih {d['kind']} "
            f"(pilihan: {', '.join(allowed_actions(d['kind'], grn['partner_type'])) or '-'})."))
    if d["kind"] in NEEDS_APPROVE and body.action == "accept_note" \
            and not await has_permission(actor, "goods_receipt", "approve"):
        raise HTTPException(status_code=403, detail="Menerima selisih ini butuh hak goods_receipt.approve.")
    resolution = {"action": body.action, "reason": body.reason.strip(), "by": actor["name"], "at": now_iso()}
    discs = [{**x, "resolution": resolution} if x["key"] == key and not x.get("superseded") else x
             for x in grn["discrepancies"]]
    lines = [dict(x) for x in grn["lines"]]
    if body.action in ("claim_supplier", "claim_makloon"):
        for ln in lines:
            if ln["line_no"] == d["line_no"]:
                ln["claim"] = {"kind": d["kind"], "action": body.action, "reason": resolution["reason"],
                               "by": actor["name"], "at": resolution["at"]}
        from services.notification_service import create_notification
        await create_notification(
            notif_type="grn_claim", severity="warning", entity_id=grn["entity_id"], recipient_role="manager",
            title=f"Klaim {grn['partner_name']} — {grn['number']}",
            body=f"Baris {d['line_no']}: {d['detail']} Alasan: {resolution['reason']}",
            link=f"/?view=goods-receipts&id={grn_id}", ref=f"{grn_id}:{key}")
    grn = await cas(grn, ["reconcile"], body.expected_version, {"discrepancies": discs, "lines": lines})
    if body.action == "reject_goods":
        await _undo_line_rolls(grn, d["line_no"])

        def _reject(ls: List[Dict[str, Any]]) -> None:
            for x in ls:
                if x["line_no"] == d["line_no"]:
                    x["decision"] = "reject_line"
                    x["counted"] = {**x["counted"], "makloon_rolls": []}
        grn = await refresh_counted(grn, actor["name"], mutate=_reject, statuses=["reconcile"])
        lines, discs = await compute_recon(grn)
        grn = await cas(grn, ["reconcile"], grn["version"], {"lines": lines, "discrepancies": discs})
    await audit(actor["name"], "grn_discrepancy_resolved", "goods_receipt", grn_id, {"key": key, **resolution},
                reason=resolution["reason"], scope_entity_id=grn["entity_id"])
    return grn


# ── sisa PO (kiriman parsial) ─────────────────────────────────────────────────
_RESET = {"received_qty": 0.0, "quantity": 0.0, "qty_rolls": None, "qty_rolls_scanned": 0, "status": "waiting_goods",
          "scan_log": [], "escalation": None, "grn_ids": [], "supplier_dn_numbers": [], "declared_qty_total": 0.0,
          "bin_id": "", "batch": "", "lot": "", "roll_id": "", "refs": []}
_DROP = ("lot_ids", "lot_numbers", "uom_trail", "conversion_variance", "needs_review", "qc_status", "quarantine_qty",
         "receipt_variance", "supplier_dn_number", "saga_lock", "grn_active_id", "grn_active_number",
         "legacy_in_flight", "over_receipt", "receive_within_tolerance", "receive_mode", "supplier_lot",
         "lot_warnings", "label_variance_flagged", "qc_decision", "qc_result")


async def ensure_remainder_task(po_id: str, product_id: str, actor_name: str = "Sistem",
                                source_task_id: str = "") -> Dict[str, Any]:
    """Tepat SATU tugas inbound aktif untuk sisa baris PO (idempoten).

    `_create_inbound_tasks_for_po` tidak dipakai: filternya hanya mengabaikan tugas `completed`/`cancelled`,
    sehingga tugas `qc_pending` dianggap "masih ada" (dan `expected_qty`-nya bahkan ditimpa qty penuh).
    """
    from routers.purchase_orders import TERMINAL_PO_STATUSES
    from services.config_service import get_effective_settings
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    if not po or po.get("status") in TERMINAL_PO_STATUSES:
        return {"created": False, "reason": "po_closed"}
    it = next((i for i in po.get("items") or [] if i.get("product_id") == product_id), None)
    if not it:
        return {"created": False, "reason": "no_line"}
    ordered = float(it.get("quantity") or 0)
    remaining = round(ordered - float(it.get("received_qty") or 0), 2)
    tol = float(((await get_effective_settings(po.get("entity_id"))).get("purchasing", {}) or {})
                .get("receive_tolerance_percent", 2.0) or 0)
    if remaining <= ordered * tol / 100 + 1e-6:
        return {"created": False, "reason": "fulfilled", "remaining": remaining}
    flt = {"po_id": po_id, "product_id": product_id, "flow_type": "inbound"}
    active = await db.wms_tasks.find_one({**flt, "status": {"$in": ACTIVE_TASK}}, {"_id": 0, "id": 1})
    if active:
        return {"created": False, "reason": "exists", "task_id": active["id"], "remaining": remaining}
    src = (await db.wms_tasks.find_one({**flt, "id": source_task_id}, {"_id": 0}) if source_task_id else None) \
        or await db.wms_tasks.find_one(flt, {"_id": 0}, sort=[("created_at", -1)])
    if not src:
        return {"created": False, "reason": "no_source_task"}
    new = {k: v for k, v in src.items() if k not in _DROP}
    new.update(_RESET)
    new.update({"id": new_id("wms"), "expected_qty": remaining, "remainder_of": src["id"],
                "created_by": actor_name, "created_at": now_iso(), "updated_at": now_iso()})
    await db.wms_tasks.insert_one(dict(new))
    from services import doc_refs_service as _refs
    await _refs.safe_link(("grn", new["id"]), ("purchase_order", po_id), "parent", note="sisa kiriman parsial")
    await audit(actor_name, "inbound_remainder_task_created", "wms_task", new["id"],
                {"po_id": po_id, "product_id": product_id, "expected_qty": remaining, "remainder_of": src["id"]},
                scope_entity_id=po.get("entity_id") or "")
    return {"created": True, "task_id": new["id"], "remaining": remaining}


# ── penutupan ─────────────────────────────────────────────────────────────────
async def _mark_lines(grn_id: str, nos: List[int], posted: Dict[str, Any]) -> None:
    await db.goods_receipts.update_one(
        {"id": grn_id}, {"$set": {"lines.$[l].posted": posted}},
        array_filters=[{"l.line_no": {"$in": nos}, "l.posted.status": {"$ne": "done"}}])


async def _post_task(grn: Dict[str, Any], task_id: str, lines: List[Dict[str, Any]],
                     actor: Dict[str, Any]) -> Dict[str, Any]:
    from schemas import GRCompletePayload
    from services.inbound_complete_service import complete_task
    task = await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}) or {}
    pending = await db.inventory_rolls.count_documents({"grn_id": grn["id"], "grn_task_id": task_id,
                                                        "status": "receiving"})
    if not (task.get("status") in ("qc_pending", "completed") and pending == 0):   # sudah terposting (ulang close)
        lot = next((ln["declared"].get("lot") for ln in lines if (ln.get("declared") or {}).get("lot")), "")
        await complete_task(task_id, GRCompletePayload(supplier_dn=grn["dn"]["number"], supplier_lot=lot or ""),
                            actor, via_grn=grn)
    await db.wms_tasks.update_one({"id": task_id}, {
        "$addToSet": {"supplier_dn_numbers": grn["dn"]["number"], "grn_ids": grn["id"]},
        "$inc": {"declared_qty_total": round(sum(float((ln.get("converted") or {}).get("qty") or 0) for ln in lines), 2)},
        "$unset": {"grn_active_id": "", "grn_active_number": ""}})
    return await ensure_remainder_task(task.get("po_id", ""), task.get("product_id", ""), actor["name"], task_id)


async def _post_mko(grn: Dict[str, Any], mko_id: str, seq: int, lines: List[Dict[str, Any]],
                    actor: Dict[str, Any]) -> None:
    from services.makloon_order_service import receive_step
    out_lines = [ln for ln in lines if ln.get("role") != "byproduct"]
    by_lines = [ln for ln in lines if ln.get("role") == "byproduct"]
    if not out_lines:
        raise HTTPException(status_code=400, detail="Barang sisa hanya bisa diterima bersama output langkah yang sama.")
    rolls = [{"lot": r["lot"], "length": r["length"], "grade": r["grade"], "dye_lot": r.get("dye_lot", ""),
              "weight_kg": r.get("weight_kg") or None}
             for ln in out_lines for r in (ln.get("counted") or {}).get("makloon_rolls") or []]
    by_rolls = [r for ln in by_lines for r in (ln.get("counted") or {}).get("makloon_rolls") or []]
    await receive_step(mko_id, seq, {
        "step_seq": seq, "actual_output_qty": round(sum(float(ln["counted"]["qty"]) for ln in out_lines), 2),
        "actual_byproduct_qty": round(sum(float(r["length"]) for r in by_rolls), 2),
        "byproduct_lot": by_rolls[0]["lot"] if by_rolls else "",
        "output_uom": "", "output_doc_qty": 0,
        "rolls": rolls, "supplier_invoice_no": "", "supplier_dn": (grn.get("dn") or {}).get("number", "")},
        actor_name=actor["name"])


async def close_grn(grn_id: str, expected_version: int, actor: Dict[str, Any], ctx: EntityContext):
    from services import atomic_claim as _saga
    grn = await load(grn_id, ctx)
    require_status(grn, ["reconcile", "closing"], "Tutup penerimaan")
    if expected_version != grn.get("version"):
        from services.goods_receipt_service import state_changed
        raise state_changed()
    if grn["status"] == "reconcile":
        lines, discs = await compute_recon(grn)
        blockers = open_blockers(discs)
        if blockers:
            raise HTTPException(status_code=400, detail={
                "code": "BLOCKERS_OPEN", "keys": [d["key"] for d in blockers],
                "message": f"{len(blockers)} selisih pemblokir belum diselesaikan: "
                           + "; ".join(f"baris {d['line_no']} {d['kind']}" for d in blockers) + "."})
        grn = await cas(grn, ["reconcile"], expected_version,
                        {"status": "closing", "lines": lines, "discrepancies": discs, "closing_started_at": now_iso()})
    grn = await _saga.claim("goods_receipts", grn_id, "grn_close", precondition={"status": "closing"},
                            actor=actor["name"])
    results: List[Dict[str, Any]] = []
    try:
        todo = [ln for ln in grn["lines"] if (ln.get("posted") or {}).get("status") != "done"]
        skip = [ln["line_no"] for ln in todo if ln.get("is_non_stock") or ln.get("decision") != "accept"
                or float((ln.get("counted") or {}).get("qty") or 0) <= 0]
        if skip:
            await _mark_lines(grn_id, skip, {"status": "skipped", "at": now_iso(), "error": "", "result_ref": ""})
        groups: Dict[Tuple, List[Dict[str, Any]]] = {}
        for ln in todo:
            if ln["line_no"] in skip:
                continue
            t = ln["target"]
            groups.setdefault(("po", t["task_id"]) if t["type"] == "po_task" else ("mko", t["mko_id"], t["step_seq"]),
                              []).append(ln)
        for gkey, lns in groups.items():
            nos = [x["line_no"] for x in lns]
            try:
                if gkey[0] == "po":
                    rem = await _post_task(grn, gkey[1], lns, actor)
                    ref = gkey[1]
                else:
                    await _post_mko(grn, gkey[1], gkey[2], lns, actor)
                    rem, ref = None, f"{gkey[1]}:{gkey[2]}"
                await _mark_lines(grn_id, nos, {"status": "done", "at": now_iso(), "error": "", "result_ref": ref})
                results.append({"lines": nos, "status": "done", "result_ref": ref, "remainder": rem})
            except HTTPException as exc:
                err = exc.detail if isinstance(exc.detail, str) else (exc.detail or {}).get("message", str(exc.detail))
                await _mark_lines(grn_id, nos, {"status": "failed", "at": now_iso(), "error": err, "result_ref": ""})
                results.append({"lines": nos, "status": "failed", "error": err})
    finally:
        await db.goods_receipts.update_one({"id": grn_id}, {"$unset": {_saga.LOCK: ""}})
    fresh = await db.goods_receipts.find_one({"id": grn_id}, {"_id": 0})
    if all((ln.get("posted") or {}).get("status") in ("done", "skipped") for ln in fresh["lines"]):
        fresh = await cas(fresh, ["closing"], None, {"status": "closed", "closed_by": actor["name"],
                                                     "closed_at": now_iso()})
        await release_tasks(grn_id)
        await _learn_profile(fresh)
    await audit(actor["name"], "grn_closed" if fresh["status"] == "closed" else "grn_close_partial",
                "goods_receipt", grn_id, {"results": results}, scope_entity_id=grn["entity_id"])
    return {"grn": fresh, "results": results}


async def _learn_profile(grn: Dict[str, Any]) -> None:
    from services.supplier_dn_profile_service import learn_from_grn
    await learn_from_grn(grn)


# ── tolak / batal ─────────────────────────────────────────────────────────────
async def reject_grn(grn_id: str, body: Any, actor: Dict[str, Any], ctx: EntityContext):
    grn = await load(grn_id, ctx)
    require_status(grn, ["review"], "Tolak kedatangan")
    doc = await cas(grn, ["review"], body.expected_version, {"status": "rejected", "reject_reason": body.reason.strip()},
                    extra={"$unset": {"active_key": ""}})
    await audit(actor["name"], "grn_rejected", "goods_receipt", grn_id, {}, reason=body.reason,
                scope_entity_id=grn["entity_id"])
    return doc


async def cancel_grn(grn_id: str, body: Any, actor: Dict[str, Any], ctx: EntityContext):
    grn = await load(grn_id, ctx)
    allowed = ["draft", "reading", "review", "counting"]
    require_status(grn, allowed, "Batalkan kedatangan")
    doc = await cas(grn, allowed, body.expected_version, {"status": "cancelled", "cancel_reason": body.reason.strip()},
                    extra={"$unset": {"active_key": ""}})
    for ln in grn.get("lines") or []:
        await _undo_line_rolls(grn, ln["line_no"])
    await release_tasks(grn_id)
    await audit(actor["name"], "grn_cancelled", "goods_receipt", grn_id, {}, reason=body.reason,
                scope_entity_id=grn["entity_id"])
    return safe_doc(doc)
