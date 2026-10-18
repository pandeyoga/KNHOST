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
        rc = ln.get("roll_check") or {}
        if rc.get("missing") or rc.get("diffs"):
            parts = []
            if rc.get("missing"):
                parts.append(f"{len(rc['missing'])} roll belum diukur (#{', #'.join(str(x) for x in rc['missing'])})")
            if rc.get("diffs"):
                parts.append(f"{len(rc['diffs'])} roll beda panjang (" + ", ".join(
                    f"#{d['seq']} {d['measured']:g} vs {d['expected']:g}" for d in rc["diffs"][:5]) + ")")
            cls.append(("packing_list_mismatch", "Packing list: " + "; ".join(parts) + "."))
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
        prev = old.get(d["key"]) or {}
        # KN-E11 — persetujuan lama hanya terbawa bila ANGKA selisihnya sama persis.
        if prev.get("resolution") and prev.get("detail") == d["detail"]:
            d["resolution"] = prev["resolution"]
        elif prev.get("resolution"):
            d["previous_resolution"] = {**prev["resolution"], "detail": prev.get("detail")}
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
        try:
            await undo_receiving_roll(r, task)
        except HTTPException as exc:   # KN-E13 — roll sudah terhapus proses lain: lanjutkan sisanya
            if exc.status_code != 409:
                raise


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
    # W2-013 — baris baru 'done' hanya bila SELURUH roll task ini terfinalisasi (tanpa sisa receiving).
    left = await db.inventory_rolls.count_documents({"grn_id": grn["id"], "grn_task_id": task_id,
                                                     "status": "receiving"})
    if left:
        raise HTTPException(status_code=409, detail=f"{left} roll belum terfinalisasi pada penerimaan ini — tutup ulang GRN.")
    # KN-E19 — declared_qty_total hanya ditambah SEKALI per GRN (percobaan ulang close tidak menggandakan).
    await db.wms_tasks.update_one({"id": task_id, "declared_grn_ids": {"$ne": grn["id"]}}, {
        "$addToSet": {"declared_grn_ids": grn["id"]},
        "$inc": {"declared_qty_total": round(sum(float((ln.get("converted") or {}).get("qty") or 0) for ln in lines), 2)}})
    await _ensure_gr_posted(task_id)  # IX-14 — baris baru 'done' bila jurnal penerimaan ada
    await db.wms_tasks.update_one({"id": task_id}, {
        "$addToSet": {"supplier_dn_numbers": grn["dn"]["number"], "grn_ids": grn["id"]},
        "$unset": {"grn_active_id": "", "grn_active_number": ""}})
    return await ensure_remainder_task(task.get("po_id", ""), task.get("product_id", ""), actor["name"], task_id)


async def _ensure_gr_posted(task_id: str) -> None:
    """IX-14 — jurnal GR yang gagal diulang (idempotent per task); masih gagal → 409 sehingga baris
    GRN 'failed' dan GRN tetap `closing` (bisa ditutup ulang setelah penyebab dibereskan)."""
    task = await db.wms_tasks.find_one({"id": task_id}, {"_id": 0, "gl_posting": 1}) or {}
    glp = task.get("gl_posting") or {}
    if glp.get("status") != "failed":
        return
    from services import gl_service
    try:
        je = await gl_service.post_goods_receipt(task_id=task_id, entity_id=glp.get("entity_id", ""),
                                                 amount=float(glp.get("amount") or 0), label=glp.get("label", ""))
    except Exception as exc:  # noqa: BLE001
        await db.wms_tasks.update_one({"id": task_id}, {"$set": {"gl_posting.error": str(exc)[:300],
                                                                 "gl_posting.at": now_iso()}})
        raise HTTPException(status_code=409, detail=f"Stok diterima, tetapi jurnal penerimaan gagal: {exc}")
    await db.wms_tasks.update_one({"id": task_id}, {"$set": {
        "gl_posting.status": "posted", "gl_posting.error": "", "gl_posting.je_id": (je or {}).get("id", ""),
        "gl_posting.at": now_iso()}})


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
    # KN-E14 — samakan dengan layar lama: warna/repeat langkah (biaya) & gudang GRN sebagai gudang hasil.
    if grn.get("mko_partial"):
        # Terima bertahap — kiriman ini DITAHAN di langkah MKO; diposting bersama kiriman terakhir.
        entry = {"grn_id": grn["id"], "grn_number": grn.get("number", ""),
                 "dn_number": (grn.get("dn") or {}).get("number", ""),
                 "out_qty": round(sum(float(ln["counted"]["qty"]) for ln in out_lines), 2),
                 "by_qty": round(sum(float(r["length"]) for r in by_rolls), 2),
                 "byproduct_lot": by_rolls[0]["lot"] if by_rolls else "",
                 "rolls": rolls, "warehouse_id": grn.get("warehouse_id") or "",  # W2-003
                 "by": actor["name"], "by_id": actor.get("id", ""), "at": now_iso(), "posted": False}
        tl = {"at": now_iso(), "event": "partial_received",
              "note": f"Step {seq}: kiriman sebagian {entry['out_qty']} ({len(rolls)} roll) via "
                      f"{entry['grn_number']}{' / SJ ' + entry['dn_number'] if entry['dn_number'] else ''} "
                      "ditahan — diposting bersama kiriman terakhir."}
        res = await db.makloon_orders.update_one(
            {"id": mko_id, "saga_lock": {"$exists": False}, "steps": {"$elemMatch": {"seq": seq, "status": "issued",
                                                    "partial_receipts.grn_id": {"$ne": grn["id"]}}}},
            {"$push": {"steps.$.partial_receipts": entry, "timeline": tl}, "$set": {"updated_at": now_iso()}})
        if not res.modified_count:
            done = await db.makloon_orders.find_one(
                {"id": mko_id, "steps": {"$elemMatch": {"seq": seq, "partial_receipts.grn_id": grn["id"]}}}, {"_id": 1})
            if not done:   # bukan percobaan ulang → langkah sudah tidak issued
                raise HTTPException(status_code=409, detail=f"Langkah MKO #{seq} sudah tidak menunggu kiriman.")
        return
    mko = await db.makloon_orders.find_one({"id": mko_id}, {"_id": 0, "steps": 1}) or {}
    step = next((s for s in mko.get("steps") or [] if s.get("seq") == seq), {})
    await receive_step(mko_id, seq, {
        "colors": int(step.get("colors") or 0), "repeats": int(step.get("repeats") or 0),
        "output_warehouse_id": grn.get("warehouse_id") or "",
        "step_seq": seq, "actual_output_qty": round(sum(float(ln["counted"]["qty"]) for ln in out_lines), 2),
        "actual_byproduct_qty": round(sum(float(r["length"]) for r in by_rolls), 2),
        "byproduct_lot": by_rolls[0]["lot"] if by_rolls else "",
        "output_uom": "", "output_doc_qty": 0,
        "rolls": rolls, "supplier_invoice_no": "", "supplier_dn": (grn.get("dn") or {}).get("number", ""),
        "grn_id": grn["id"], "grn_number": grn.get("number", "")},
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
        pre = await _close_preflight(grn)
        if pre:   # KN-E06 — prasyarat posting diperiksa SEBELUM masuk `closing`
            raise HTTPException(status_code=400, detail={"code": "NOT_POSTABLE", "errors": pre,
                                                         "message": " ".join(pre)})
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
        from services import po_variance_task_service as _pvt
        await _pvt.ensure_for_grn(fresh, actor["name"])  # W2-REQ-06
    await audit(actor["name"], "grn_closed" if fresh["status"] == "closed" else "grn_close_partial",
                "goods_receipt", grn_id, {"results": results}, scope_entity_id=grn["entity_id"])
    return {"grn": fresh, "results": results}


async def _close_preflight(grn: Dict[str, Any]) -> List[str]:
    """KN-E06 — kegagalan pasti (tugas dibatalkan/dipegang lain, lot wajib, langkah MKO sudah diterima)."""
    from routers.purchase_orders import TERMINAL_PO_STATUSES
    from services import lot_service as _lots
    errs: List[str] = []
    try:  # IX-14 — periode tertutup = kegagalan pasti posting; tolak SEBELUM stok/PO dimutasi
        from services import gl_service
        await gl_service.preflight_posting(grn.get("entity_id") or "", now_iso())
    except Exception as exc:  # noqa: BLE001
        errs.append(str(exc))
    live = [ln for ln in grn.get("lines") or [] if not ln.get("is_non_stock") and ln.get("decision") == "accept"
            and float((ln.get("counted") or {}).get("qty") or 0) > 0 and (ln.get("posted") or {}).get("status") != "done"]
    for ln in live:
        t = ln.get("target") or {}
        if t.get("type") == "po_task":
            task = await db.wms_tasks.find_one({"id": t.get("task_id")}, {"_id": 0}) or {}
            if task.get("status") not in ACTIVE_TASK + ["qc_pending", "completed"]:
                errs.append(f"Baris {ln['line_no']}: tugas {task.get('po_number', '')} sudah {task.get('status') or 'hilang'}.")
                continue
            if task.get("grn_active_id") not in (None, "", grn["id"]):
                errs.append(f"Baris {ln['line_no']}: tugas dipegang kedatangan {task.get('grn_active_number')}.")
            po = await db.purchase_orders.find_one({"id": task.get("po_id")}, {"_id": 0, "status": 1}) or {}
            if po.get("status") in TERMINAL_PO_STATUSES:
                errs.append(f"Baris {ln['line_no']}: PO {task.get('po_number', '')} sudah {po.get('status')}.")
            st = await _lots.get_settings(str(task.get("entity_id") or ""))
            lot = ((ln.get("declared") or {}).get("lot") or task.get("supplier_lot") or "").strip()
            rolls = await db.inventory_rolls.find({"grn_id": grn["id"], "grn_line_no": ln["line_no"], "status": "receiving"},
                                                  {"_id": 0, "dye_lot": 1, "supplier_lot": 1}).to_list(2000)
            lot = lot or next((r.get("supplier_lot") for r in rolls if r.get("supplier_lot")), "")
            for dl in dict.fromkeys((r.get("dye_lot") or lot) for r in rolls) or [lot]:
                try:
                    await _lots.guard_capture(lot, dl, st)
                except _lots.LotError as exc:
                    errs.append(f"Baris {ln['line_no']}: {exc}")
                    break
        elif t.get("type") == "mko_step":
            mko = await db.makloon_orders.find_one({"id": t.get("mko_id")}, {"_id": 0, "steps": 1}) or {}
            step = next((s for s in mko.get("steps") or [] if s.get("seq") == t.get("step_seq")), {})
            if step.get("status") != "issued":
                errs.append(f"Baris {ln['line_no']}: langkah MKO #{t.get('step_seq')} sudah {step.get('status') or 'hilang'}.")
    return errs


async def set_mko_partial(grn_id: str, expected_version: int, partial: bool, actor: Dict[str, Any],
                          ctx: EntityContext):
    """Terima bertahap — tandai kedatangan makloon ini sebagai kiriman SEBAGIAN (bukan yang terakhir)."""
    grn = await load(grn_id, ctx)
    require_status(grn, ["counting", "reconcile"], "Ubah mode terima sebagian")
    if not any((ln.get("target") or {}).get("type") == "mko_step" for ln in grn.get("lines") or []):
        raise HTTPException(status_code=400, detail="Terima sebagian hanya untuk kedatangan hasil makloon.")
    doc = await cas(grn, ["counting", "reconcile"], expected_version, {"mko_partial": bool(partial)})
    await audit(actor["name"], "grn_mko_partial_set", "goods_receipt", grn_id, {"partial": bool(partial)},
                scope_entity_id=grn["entity_id"])
    return doc


async def return_to_reconcile(grn_id: str, expected_version: int, actor: Dict[str, Any], ctx: EntityContext):
    """KN-E06 — jalan keluar dari `closing` bila ada baris gagal posting (baris `done` tetap terposting)."""
    grn = await load(grn_id, ctx)
    require_status(grn, ["closing"], "Kembalikan ke rekonsiliasi")
    if grn.get("saga_lock"):
        raise HTTPException(status_code=409, detail="Penutupan sedang berjalan — tunggu selesai.")
    if not any((ln.get("posted") or {}).get("status") == "failed" for ln in grn.get("lines") or []):
        raise HTTPException(status_code=400, detail="Tidak ada baris yang gagal diposting.")
    doc = await cas(grn, ["closing"], expected_version, {"status": "reconcile"})
    await audit(actor["name"], "grn_returned_to_reconcile", "goods_receipt", grn_id, {},
                scope_entity_id=grn["entity_id"])
    return doc


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
    if grn.get("status") == "cancelled":
        # KN-E13 — batal yang sempat terhenti di tengah boleh diulang: hanya bereskan sisa roll & tugas.
        doc = grn
    else:
        require_status(grn, allowed, "Batalkan kedatangan")
        doc = await cas(grn, allowed, body.expected_version, {"status": "cancelled", "cancel_reason": body.reason.strip()},
                        extra={"$unset": {"active_key": ""}})
    try:
        for ln in grn.get("lines") or []:
            await _undo_line_rolls(grn, ln["line_no"])
    finally:
        await release_tasks(grn_id)
    await audit(actor["name"], "grn_cancelled", "goods_receipt", grn_id, {}, reason=body.reason,
                scope_entity_id=grn["entity_id"])
    return safe_doc(doc)


async def doc_variance(ctx: EntityContext, po_id: str = "", mko_id: str = "", step_seq: Optional[int] = None) -> Dict[str, Any]:
    """Pencocokan tagihan (baca-saja): qty surat jalan vs hitung fisik per baris PO / langkah MKO dari kedatangan
    yang sudah DITUTUP (stok & GL sudah terposting)."""
    if not po_id and not mko_id:
        raise HTTPException(status_code=400, detail="Isi po_id atau mko_id.")
    key = {"lines.target.po_id": po_id} if po_id else {"lines.target.mko_id": mko_id}
    flt = {"status": "closed", **key,
           "entity_id": {"$in": ctx.allowed_entity_ids} if ctx.view_all else ctx.active_entity_id}
    rows: List[Dict[str, Any]] = []
    for g in await db.goods_receipts.find(flt, {"_id": 0}).sort("closed_at", 1).to_list(500):
        res = {}
        for d in g.get("discrepancies") or []:
            if d.get("resolution"):
                res.setdefault(d["line_no"], []).append(d["resolution"].get("action"))
        for ln in g.get("lines") or []:
            t = ln.get("target") or {}
            if ln.get("is_non_stock") or ln.get("decision") == "reject_line":
                continue
            if (po_id and t.get("po_id") != po_id) or (mko_id and (t.get("mko_id") != mko_id or (
                    step_seq is not None and t.get("step_seq") != step_seq))):
                continue
            rc = ln.get("recon") or {}
            decl = (ln.get("converted") or {}).get("qty")
            cnt = float((ln.get("counted") or {}).get("qty") or 0)
            rows.append({"grn_id": g["id"], "grn_number": g["number"], "dn_number": (g.get("dn") or {}).get("number", ""),
                         "dn_date": (g.get("dn") or {}).get("date", ""), "closed_at": g.get("closed_at", ""),
                         "line_no": ln["line_no"], "product_id": t.get("product_id", ""),
                         "product_name": t.get("product_name", ""), "sku": t.get("sku", ""),
                         "unit": t.get("unit", "") if ln.get("role") != "byproduct" else (ln.get("converted") or {}).get("unit", ""),
                         "role": ln.get("role") or "output", "step_seq": t.get("step_seq"),
                         "supplier_text": " ".join(x for x in [(ln.get("read") or {}).get("description"),
                                                               (ln.get("read") or {}).get("color")] if x),
                         "declared_qty": decl, "counted_qty": round(cnt, 2),
                         "diff_qty": round(cnt - float(decl), 2) if decl is not None else None,
                         "diff_pct": rc.get("diff_pct"),
                         "declared_rolls": (ln.get("declared") or {}).get("rolls"),
                         "counted_rolls": (ln.get("counted") or {}).get("rolls"),
                         "classes": rc.get("classes") or [], "resolutions": res.get(ln["line_no"], [])})
    summary: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        k = f"{r['product_id']}|{r['role']}"
        s = summary.setdefault(k, {"product_id": r["product_id"], "product_name": r["product_name"], "sku": r["sku"],
                                   "unit": r["unit"], "role": r["role"], "declared_qty": 0.0, "counted_qty": 0.0,
                                   "grn_count": 0})
        s["declared_qty"] = round(s["declared_qty"] + float(r["declared_qty"] or 0), 2)
        s["counted_qty"] = round(s["counted_qty"] + r["counted_qty"], 2)
        s["grn_count"] += 1
    for s in summary.values():
        s["diff_qty"] = round(s["counted_qty"] - s["declared_qty"], 2)
    return {"rows": rows, "summary": list(summary.values()),
            "claims": sum(1 for r in rows if any(a in ("claim_supplier", "claim_makloon") for a in r["resolutions"]))}
