"""GRN Fase 2 — Kedatangan Barang (satu surat jalan · satu mitra): buat, berkas, kepala SJ, baris, hitung.

Rekonsiliasi, penyelesaian selisih, penutupan & pembatalan ada di `goods_receipt_close_service`.
Stok/HPP/GL TIDAK ditulis di sini: roll hitung lahir `receiving` lewat `receiving_roll_service`, posting
hanya lewat `inbound_complete_service.complete_task` (dan `receive_step` untuk makloon) saat penutupan.
"""
import hashlib
import io
import re
from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from core_utils import new_id, next_doc_number, now_iso, safe_doc
from db import db
from dependencies import audit, has_permission
from entity_scope import EntityContext, assert_active_entity_access
from services.config_resolver import value_of

COLL = "goods_receipts"
ACTIVE_TASK = ["waiting_goods", "receiving", "qc_check", "put_away"]
OPEN_GRN = ["draft", "reading", "review", "counting", "reconcile", "closing"]
_UNIT = {"m": "meter", "mtr": "meter", "meter": "meter", "yd": "yard", "yds": "yard", "yard": "yard",
         "kg": "kg", "kgs": "kg"}
HIDDEN_LINE = ("declared", "read", "converted", "recon", "checks")


def norm_unit(u: Optional[str]) -> str:
    u = (u or "").strip().lower()
    return _UNIT.get(u, u)


def norm_dn(s: Optional[str]) -> str:
    return re.sub(r"[\s./\-]", "", (s or "").upper())


def active_key_of(grn: Dict[str, Any]) -> str:
    dn = grn.get("dn") or {}
    year = (dn.get("date") or grn.get("created_at") or "")[:4]
    return f"{grn['entity_id']}|{grn['partner_id']}|{norm_dn(dn.get('number'))}|{year}"


def state_changed() -> HTTPException:
    return HTTPException(status_code=409, detail={
        "code": "STATE_CHANGED", "message": "Kedatangan barang ini sudah diubah orang lain. Muat ulang layar."})


def require_status(grn: Dict[str, Any], statuses: List[str], what: str) -> None:
    if grn.get("status") not in statuses:
        raise HTTPException(status_code=409, detail={
            "code": "BAD_STATUS",
            "message": f"{what} hanya bisa saat status {', '.join(statuses)} (sekarang: {grn.get('status')})."})


async def load(grn_id: str, ctx: EntityContext) -> Dict[str, Any]:
    grn = await db.goods_receipts.find_one({"id": grn_id}, {"_id": 0})
    if not grn:
        raise HTTPException(status_code=404, detail="Kedatangan barang tidak ditemukan")
    assert_active_entity_access(grn, COLL, ctx)
    return grn


async def cas(grn: Dict[str, Any], statuses: List[str], expected_version: Optional[int],
              set_: Optional[Dict[str, Any]] = None, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Tulis berprasyarat status (+ versi bila diberikan); versi selalu naik. Kalah → 409 STATE_CHANGED."""
    flt: Dict[str, Any] = {"id": grn["id"], "status": {"$in": statuses}}
    if expected_version is not None:
        flt["version"] = expected_version
    ops: Dict[str, Any] = {"$set": {**(set_ or {}), "updated_at": now_iso()}, "$inc": {"version": 1}}
    for k, v in (extra or {}).items():
        ops[k] = {**ops.get(k, {}), **v}
    doc = await db.goods_receipts.find_one_and_update(flt, ops, projection={"_id": 0},
                                                      return_document=ReturnDocument.AFTER)
    if not doc:
        raise state_changed()
    return doc


async def is_blind_for(grn: Dict[str, Any], user: Dict[str, Any]) -> bool:
    blind = bool(await value_of("receiving.blind_count", {"entity_id": grn.get("entity_id") or ""}))
    return blind and not await has_permission(user, "goods_receipt", "review")


async def public_view(grn: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    """Hitung buta ditegakkan DI API: tanpa hak `review`, angka SJ, bacaan, konversi, selisih & foto dibuang."""
    out = safe_doc(dict(grn))
    out.pop("active_key", None)
    out.pop("saga_lock", None)
    out["blind"] = await is_blind_for(grn, user)
    out["ocr_enabled"] = bool(await value_of("receiving.ocr_enabled", {"entity_id": grn.get("entity_id") or ""}))
    if out["blind"]:
        out["lines"] = [{k: v for k, v in ln.items() if k not in HIDDEN_LINE} for ln in out.get("lines") or []]
        out["dn"] = {"number": (out.get("dn") or {}).get("number", "")}
        for k in ("files", "discrepancies", "extraction"):
            out.pop(k, None)
    return out


async def guard_legacy_receiving(task: Dict[str, Any]) -> None:
    """Jalur lama (scan-receive/scan-label/complete): tolak tugas milik GRN aktif & entitas mode `grn`."""
    if not task:
        return
    if task.get("grn_active_id"):
        raise HTTPException(status_code=409, detail={
            "code": "GRN_MANAGED",
            "message": (f"Tugas ini sedang dihitung di Kedatangan Barang {task.get('grn_active_number') or ''}. "
                        "Lanjutkan dari layar Kedatangan Barang.")})
    mode = await value_of("receiving.mode", {"entity_id": task.get("entity_id") or ""})
    if mode != "grn" or task.get("legacy_in_flight"):
        return
    if task.get("status") in ("receiving", "qc_check", "put_away") or float(task.get("received_qty") or 0) > 0:
        await db.wms_tasks.update_one({"id": task["id"]}, {"$set": {"legacy_in_flight": True}})
        return
    raise HTTPException(status_code=409, detail={
        "code": "GRN_MODE",
        "message": "Penerimaan di entitas ini memakai GRN. Buat Kedatangan Barang dari menu Gudang."})


# ── pembuatan ────────────────────────────────────────────────────────────────
async def open_pos(entity_id: str, supplier_id: str) -> List[Dict[str, Any]]:
    from routers.purchase_orders import TERMINAL_PO_STATUSES
    pos = await db.purchase_orders.find(
        {"entity_id": entity_id, "supplier_id": supplier_id, "status": {"$nin": list(TERMINAL_PO_STATUSES)}},
        {"_id": 0, "id": 1, "po_number": 1}).to_list(500)
    if not pos:
        return []
    live = set(await db.wms_tasks.distinct("po_id", {"po_id": {"$in": [p["id"] for p in pos]},
                                                     "flow_type": "inbound", "status": {"$in": ACTIVE_TASK}}))
    return [p for p in pos if p["id"] in live]


async def open_mkos(entity_id: str, makloon_id: str) -> List[Dict[str, Any]]:
    return await db.makloon_orders.find(
        {"entity_id": entity_id, "status": {"$nin": ["completed", "cancelled"]},
         "steps": {"$elemMatch": {"makloon_id": makloon_id, "status": "issued"}}},
        {"_id": 0, "id": 1, "mko_number": 1}).to_list(500)


async def create_grn(body: Any, actor: Dict[str, Any], ctx: EntityContext) -> Dict[str, Any]:
    ent = ctx.active_entity_id
    if ctx.view_all or not ent or ent == "all":
        raise HTTPException(status_code=400, detail="Pilih satu badan usaha aktif sebelum mencatat kedatangan barang.")
    if not await db.warehouses.find_one({"id": body.warehouse_id}, {"_id": 1}):
        raise HTTPException(status_code=400, detail="Gudang tidak ditemukan.")
    coll = "suppliers" if body.partner_type == "supplier" else "makloons"
    partner = await db[coll].find_one({"id": body.partner_id}, {"_id": 0, "id": 1, "name": 1})
    if not partner:
        raise HTTPException(status_code=404, detail="Mitra (supplier/makloon) tidak ditemukan.")
    if body.partner_type == "supplier":
        docs, req, label = await open_pos(ent, body.partner_id), body.po_ids, "PO"
    else:
        docs, req, label = await open_mkos(ent, body.partner_id), body.mko_ids, "MKO"
    if not docs:
        raise HTTPException(status_code=400, detail=(
            f"{partner['name']} tidak punya {label} terbuka yang menunggu barang di badan usaha aktif."))
    open_ids = {d["id"] for d in docs}
    bad = [x for x in req if x not in open_ids]
    if bad:
        raise HTTPException(status_code=400, detail=f"{label} {', '.join(bad)} bukan {label} terbuka milik mitra ini.")
    gid = new_id("grn")
    doc = {
        "id": gid, "entity_id": ent,
        "number": await next_doc_number(COLL, "number", "GRN-", entity_id=ent),
        "status": "draft", "version": 1,
        "partner_type": body.partner_type, "partner_id": body.partner_id, "partner_name": partner.get("name", ""),
        "warehouse_id": body.warehouse_id,
        "source": {"opened_from": ("po" if body.po_ids else "mko" if body.mko_ids else "list"),
                   "po_ids": list(body.po_ids), "mko_ids": list(body.mko_ids)},
        "dn": {"number": "", "number_norm": "", "date": "", "date_text": "", "supplier_name_printed": "",
               "recipient_name": "", "po_refs": [], "other_refs": [], "vehicle_plate": "", "annotations": [],
               "source": "manual", "edited_fields": []},
        "files": [], "extraction": {"read_failed": False, "error_code": "", "text_layer_used": False, "runs": []},
        "lines": [], "discrepancies": [],
        "created_by": actor["name"], "created_at": now_iso(), "counted_by": [],
        "closed_by": "", "closed_at": "", "reject_reason": "", "cancel_reason": "", "updated_at": now_iso(),
    }
    await db.goods_receipts.insert_one(dict(doc))
    from services import doc_refs_service as _refs
    for po_id in body.po_ids:
        await _refs.safe_link(("goods_receipt", gid), ("purchase_order", po_id), "parent")
    for mko_id in body.mko_ids:
        await _refs.safe_link(("goods_receipt", gid), ("makloon_order", mko_id), "parent")
    await audit(actor["name"], "grn_created", "goods_receipt", gid,
                {"number": doc["number"], "partner_id": body.partner_id}, scope_entity_id=ent)
    return doc


# ── berkas foto/PDF surat jalan ───────────────────────────────────────────────
async def add_file(grn_id: str, filename: str, content_type: str, data: bytes, expected_version: Optional[int],
                   actor: Dict[str, Any], ctx: EntityContext) -> Dict[str, Any]:
    from services import storage_service as st
    grn = await load(grn_id, ctx)
    require_status(grn, ["draft", "review"], "Unggah foto surat jalan")
    try:
        ct = st.validate_upload(filename, content_type, len(data))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    width = height = 0
    if ct.startswith("image/"):
        try:
            from PIL import Image
            with Image.open(io.BytesIO(data)) as im:
                width, height = im.size
        except Exception:  # noqa: BLE001 — gambar rusak tetap disimpan, dimensi 0
            pass
    sha = hashlib.sha256(data).hexdigest()
    path = st.build_path(f"grn/{grn_id}", st.ext_of(filename))
    await st.put_object(path, data, ct)
    entry = {"page": len(grn.get("files") or []) + 1, "path": path, "content_type": ct, "bytes": len(data),
             "sha256_original": sha, "sha256_processed": "", "width": width, "height": height,
             "quality_warnings": (["small_photo"] if width and min(width, height) < int(
                 await value_of("receiving.min_photo_short_side_px", {}) or 0) else []), "uploaded_at": now_iso(), "uploaded_by": actor["name"]}
    doc = await cas(grn, ["draft", "review"], expected_version, extra={"$push": {"files": entry}})
    dup = await db.goods_receipts.find_one(
        {"entity_id": grn["entity_id"], "id": {"$ne": grn_id}, "status": {"$in": OPEN_GRN},
         "files.sha256_original": sha}, {"_id": 0, "number": 1})
    await audit(actor["name"], "grn_file_added", "goods_receipt", grn_id, {"page": entry["page"], "sha256": sha},
                scope_entity_id=grn["entity_id"])
    return {"grn": doc, "file": entry,
            "warnings": ([f"Foto yang sama sudah dipakai di kedatangan {dup['number']}. Pastikan ini bukan SJ ganda."]
                         if dup else [])}


async def delete_file(grn_id: str, page: int, expected_version: int, actor: Dict[str, Any],
                      ctx: EntityContext) -> Dict[str, Any]:
    grn = await load(grn_id, ctx)
    require_status(grn, ["draft", "review"], "Hapus halaman")
    files = [f for f in grn.get("files") or [] if f["page"] != page]
    if len(files) == len(grn.get("files") or []):
        raise HTTPException(status_code=404, detail=f"Halaman {page} tidak ada.")
    for i, f in enumerate(files, 1):
        f["page"] = i
    doc = await cas(grn, ["draft", "review"], expected_version, {"files": files})
    await audit(actor["name"], "grn_file_deleted", "goods_receipt", grn_id, {"page": page},
                scope_entity_id=grn["entity_id"])
    return doc


async def get_file(grn_id: str, page: int, user: Dict[str, Any], ctx: EntityContext):
    from services import storage_service as st
    grn = await load(grn_id, ctx)
    if await is_blind_for(grn, user):
        raise HTTPException(status_code=403, detail="Hitung buta aktif — foto surat jalan hanya untuk peninjau.")
    f = next((x for x in grn.get("files") or [] if x["page"] == page), None)
    if not f:
        raise HTTPException(status_code=404, detail=f"Halaman {page} tidak ada.")
    try:
        data, _ = await st.get_object(f["path"])
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Berkas halaman hilang dari penyimpanan.") from exc
    return data, f["content_type"]


# ── kepala SJ ─────────────────────────────────────────────────────────────────
async def manual_entry(grn_id: str, expected_version: int, actor: Dict[str, Any], ctx: EntityContext):
    grn = await load(grn_id, ctx)
    require_status(grn, ["draft"], "Isi manual")
    doc = await cas(grn, ["draft"], expected_version, {"status": "review", "dn.source": "manual"})
    await audit(actor["name"], "grn_manual_entry", "goods_receipt", grn_id, {"status": "review"},
                scope_entity_id=grn["entity_id"])
    return doc


async def patch_dn(grn_id: str, body: Any, actor: Dict[str, Any], ctx: EntityContext) -> Dict[str, Any]:
    grn = await load(grn_id, ctx)
    require_status(grn, ["draft", "review"], "Ubah kepala surat jalan")
    fields = body.model_dump(exclude_unset=True, exclude={"expected_version"})
    if not fields:
        raise HTTPException(status_code=400, detail="Tidak ada field yang diubah.")
    set_ = {f"dn.{k}": (v.strip() if isinstance(v, str) else v) for k, v in fields.items()}
    if "number" in fields:
        set_["dn.number_norm"] = norm_dn(fields["number"])
    doc = await cas(grn, ["draft", "review"], body.expected_version, set_,
                    extra={"$addToSet": {"dn.edited_fields": {"$each": list(fields)}}})
    await audit(actor["name"], "grn_dn_updated", "goods_receipt", grn_id, fields, scope_entity_id=grn["entity_id"])
    return doc


# ── baris SJ ──────────────────────────────────────────────────────────────────
async def resolve_target(grn: Dict[str, Any], t: Any) -> Dict[str, Any]:
    if t.type == "po_task":
        if grn["partner_type"] != "supplier":
            raise HTTPException(status_code=400, detail="Mitra makloon memakai target langkah MKO, bukan tugas PO.")
        task = await db.wms_tasks.find_one({"id": t.task_id}, {"_id": 0})
        if not task or task.get("flow_type") != "inbound" or task.get("entity_id") != grn["entity_id"]:
            raise HTTPException(status_code=400, detail="Tugas penerimaan tidak ditemukan di badan usaha ini.")
        if task.get("status") not in ACTIVE_TASK:
            raise HTTPException(status_code=400, detail=f"Tugas {task.get('po_number')} sudah {task.get('status')}.")
        po = await db.purchase_orders.find_one({"id": task.get("po_id")}, {"_id": 0, "supplier_id": 1}) or {}
        if po.get("supplier_id") != grn["partner_id"]:
            raise HTTPException(status_code=400, detail=f"PO {task.get('po_number')} bukan milik {grn['partner_name']}.")
        if task.get("grn_active_id") not in (None, "", grn["id"]):
            raise HTTPException(status_code=409, detail={
                "code": "TASK_IN_OTHER_GRN",
                "message": f"Tugas ini sedang dihitung di kedatangan {task.get('grn_active_number')}."})
        return {"type": "po_task", "po_id": task.get("po_id", ""), "po_number": task.get("po_number", ""),
                "task_id": task["id"], "product_id": task["product_id"], "product_name": task.get("product_name", ""),
                "sku": task.get("sku", ""), "unit": task.get("unit") or "meter", "mko_id": "", "step_seq": None}
    if grn["partner_type"] != "makloon":
        raise HTTPException(status_code=400, detail="Mitra supplier memakai target tugas PO, bukan langkah MKO.")
    order = await db.makloon_orders.find_one({"id": t.mko_id}, {"_id": 0})
    if not order or order.get("entity_id") != grn["entity_id"]:
        raise HTTPException(status_code=400, detail="MKO tidak ditemukan di badan usaha ini.")
    step = next((s for s in order.get("steps") or [] if s.get("seq") == t.step_seq), None)
    if not step or step.get("makloon_id") != grn["partner_id"] or step.get("status") != "issued":
        raise HTTPException(status_code=400, detail=(
            f"Langkah {t.step_seq} MKO {order.get('mko_number')} tidak sedang dikerjakan {grn['partner_name']}."))
    return {"type": "mko_step", "po_id": "", "po_number": "", "task_id": "", "mko_id": order["id"],
            "mko_number": order.get("mko_number", ""), "step_seq": t.step_seq,
            "product_id": step.get("output_product_id", ""), "product_name": step.get("output_name", ""),
            "sku": step.get("output_sku", ""), "unit": step.get("output_unit") or "meter"}


async def _convert(line: Dict[str, Any]) -> None:
    """Qty SJ → satuan target (`converted`) + `checks.uom` (ok | uom_unknown | empty)."""
    d, tgt = line["declared"], line.get("target")
    line["converted"], line["checks"]["uom_message"] = None, ""
    if not d.get("qty") or not tgt:
        line["checks"]["uom"] = "empty"
        return
    unit, tunit = norm_unit(d.get("unit")), norm_unit(tgt.get("unit"))
    if unit and unit == tunit:
        line["converted"], line["checks"]["uom"] = {"qty": d["qty"], "unit": tgt["unit"], "trail": None}, "ok"
        return
    line["checks"]["uom"] = "uom_unknown"
    if not unit:
        line["checks"]["uom_message"] = "Satuan surat jalan belum diisi."
        return
    if tgt["type"] != "po_task":
        line["checks"]["uom_message"] = f"Satuan '{d.get('unit')}' berbeda dari satuan output MKO '{tgt['unit']}'."
        return
    from services.receiving_uom_service import ReceivingUomError, convert_doc_qty
    task = await db.wms_tasks.find_one({"id": tgt["task_id"]}, {"_id": 0}) or {}
    try:
        trail = await convert_doc_qty(task, d.get("unit"), d["qty"])
    except ReceivingUomError as exc:
        line["checks"]["uom_message"] = str(exc)
        return
    line["converted"] = {"qty": trail["task_qty"], "unit": tgt["unit"], "trail": trail}
    line["checks"]["uom"] = "ok"


def _default_decision(line: Dict[str, Any]) -> str:
    return "accept" if (line.get("is_non_stock") or line.get("target")) else "pending"


async def _finish_line(line: Dict[str, Any]) -> Dict[str, Any]:
    if line["declared"].get("grade"):
        import domain_registry as _dr
        line["declared"]["grade"] = _dr.normalize_grade(line["declared"]["grade"]) or line["declared"]["grade"]
    line["match"] = ({"status": "manual", "method": "manual", "score": 1.0, "candidates": []} if line.get("target")
                     else {"status": "none", "method": "", "score": 0.0, "candidates": []})
    await _convert(line)
    return line


async def add_line(grn_id: str, body: Any, actor: Dict[str, Any], ctx: EntityContext) -> Dict[str, Any]:
    grn = await load(grn_id, ctx)
    require_status(grn, ["review"], "Tambah baris")
    lines = list(grn.get("lines") or [])
    line = {
        "line_no": max([ln["line_no"] for ln in lines] or [0]) + 1, "page": 1,
        "is_non_stock": body.is_non_stock,
        "read": {"item_code": body.item_code, "description": body.description, "po_ref": body.po_ref,
                 "source": "manual"},
        "declared": {**body.declared.model_dump(), "source": "manual"},
        "checks": {"qty_parse": "ok", "totals_ok": None, "second_reader_diff": []},
        "target": await resolve_target(grn, body.target) if body.target else None,
        "counted": {"qty": 0, "rolls": 0, "weight_kg": 0, "roll_ids": [], "makloon_rolls": []},
        "recon": None, "posted": {"status": "pending", "at": "", "error": "", "result_ref": ""},
    }
    line["decision"] = body.decision or _default_decision(line)
    lines.append(await _finish_line(line))
    doc = await cas(grn, ["review"], body.expected_version, {"lines": lines})
    await audit(actor["name"], "grn_line_added", "goods_receipt", grn_id, {"line_no": line["line_no"]},
                scope_entity_id=grn["entity_id"])
    return doc


def _find_line(grn: Dict[str, Any], line_no: int) -> Dict[str, Any]:
    ln = next((x for x in grn.get("lines") or [] if x["line_no"] == line_no), None)
    if not ln:
        raise HTTPException(status_code=404, detail=f"Baris {line_no} tidak ada.")
    return ln


async def patch_line(grn_id: str, line_no: int, body: Any, actor: Dict[str, Any], ctx: EntityContext):
    grn = await load(grn_id, ctx)
    require_status(grn, ["review"], "Ubah baris")
    lines = list(grn.get("lines") or [])
    line = _find_line(grn, line_no)
    fields = body.model_dump(exclude_unset=True, exclude={"expected_version"})
    if body.declared is not None:
        line["declared"] = {**body.declared.model_dump(), "source": "manual"}
        line["checks"]["qty_parse"] = "ok"   # dicentang manusia
    if body.is_non_stock is not None:
        line["is_non_stock"] = body.is_non_stock
    for k in ("item_code", "description", "po_ref"):
        if getattr(body, k) is not None:
            line["read"][k] = getattr(body, k)
    if body.clear_target:
        line["target"] = None
    elif body.target is not None:
        line["target"] = await resolve_target(grn, body.target)
    line["decision"] = body.decision or (line["decision"] if line["decision"] != "pending" else _default_decision(line))
    await _finish_line(line)
    doc = await cas(grn, ["review"], body.expected_version, {"lines": lines})
    await audit(actor["name"], "grn_line_updated", "goods_receipt", grn_id, {"line_no": line_no, **{
        k: v for k, v in fields.items() if k != "declared"}}, scope_entity_id=grn["entity_id"])
    return doc


async def delete_line(grn_id: str, line_no: int, expected_version: int, actor: Dict[str, Any], ctx: EntityContext):
    grn = await load(grn_id, ctx)
    require_status(grn, ["review"], "Hapus baris")
    _find_line(grn, line_no)
    lines = [x for x in grn["lines"] if x["line_no"] != line_no]
    doc = await cas(grn, ["review"], expected_version, {"lines": lines})
    await audit(actor["name"], "grn_line_deleted", "goods_receipt", grn_id, {"line_no": line_no},
                scope_entity_id=grn["entity_id"])
    return doc


async def list_targets(grn_id: str, ctx: EntityContext) -> List[Dict[str, Any]]:
    """Kandidat target: tugas inbound terbuka (supplier) atau langkah MKO `issued` (makloon) milik mitra ini."""
    grn = await load(grn_id, ctx)
    out: List[Dict[str, Any]] = []
    if grn["partner_type"] == "supplier":
        pos = await open_pos(grn["entity_id"], grn["partner_id"])
        tasks = await db.wms_tasks.find(
            {"po_id": {"$in": [p["id"] for p in pos]}, "flow_type": "inbound", "status": {"$in": ACTIVE_TASK}},
            {"_id": 0}).to_list(500)
        for t in tasks:
            out.append({"type": "po_task", "task_id": t["id"], "po_id": t.get("po_id"), "po_number": t.get("po_number"),
                        "product_id": t["product_id"], "product_name": t.get("product_name", ""),
                        "sku": t.get("sku", ""), "supplier_sku": t.get("supplier_sku", ""),
                        "unit": t.get("unit"), "expected_qty": t.get("expected_qty"),
                        "received_qty": t.get("received_qty"), "status": t.get("status"),
                        "grn_active_number": t.get("grn_active_number", "")})
        return out
    for o in await db.makloon_orders.find(
            {"id": {"$in": [m["id"] for m in await open_mkos(grn["entity_id"], grn["partner_id"])]}},
            {"_id": 0}).to_list(500):
        for s in o.get("steps") or []:
            if s.get("makloon_id") == grn["partner_id"] and s.get("status") == "issued":
                out.append({"type": "mko_step", "mko_id": o["id"], "mko_number": o.get("mko_number"),
                            "step_seq": s.get("seq"), "product_id": s.get("output_product_id"),
                            "product_name": s.get("output_name", ""), "unit": s.get("output_unit"),
                            "expected_qty": s.get("expected_output_qty")})
    return out


# ── mulai hitung ──────────────────────────────────────────────────────────────
async def release_tasks(grn_id: str) -> None:
    await db.wms_tasks.update_many({"grn_active_id": grn_id},
                                   {"$unset": {"grn_active_id": "", "grn_active_number": ""}})


async def start_count(grn_id: str, expected_version: int, actor: Dict[str, Any], ctx: EntityContext):
    grn = await load(grn_id, ctx)
    require_status(grn, ["review"], "Mulai hitung")
    errors: List[str] = []
    if not (grn.get("dn") or {}).get("number"):
        errors.append("Nomor surat jalan wajib diisi.")
    stock = [ln for ln in grn.get("lines") or [] if not ln.get("is_non_stock")]
    if not stock:
        errors.append("Belum ada baris barang dari surat jalan.")
    task_ids: List[str] = []
    for ln in stock:
        if ln.get("decision") == "reject_line":
            continue
        if not ln.get("target"):
            errors.append(f"Baris {ln['line_no']}: pilih target (tugas PO / langkah MKO) atau tolak baris.")
            continue
        if (ln.get("checks") or {}).get("qty_parse") in ("ambiguous", "mismatch"):
            errors.append(f"Baris {ln['line_no']}: angka SJ ragu ({ln['checks']['qty_parse']}) — periksa & simpan ulang qty.")
        if (ln.get("checks") or {}).get("uom") == "uom_unknown":
            errors.append(f"Baris {ln['line_no']}: satuan tidak bisa dikonversi — "
                          f"{ln['checks'].get('uom_message') or 'perbaiki satuan'}.")
        if ln["target"]["type"] == "po_task" and ln["target"]["task_id"] not in task_ids:
            task_ids.append(ln["target"]["task_id"])
    for tid in task_ids:
        t = await db.wms_tasks.find_one({"id": tid}, {"_id": 0}) or {}
        if t.get("status") not in ACTIVE_TASK:
            errors.append(f"Tugas {t.get('po_number')} / {t.get('sku')} sudah {t.get('status')}.")
        elif t.get("grn_active_id") not in (None, "", grn_id):
            errors.append(f"Tugas {t.get('po_number')} / {t.get('sku')} sedang dihitung di {t.get('grn_active_number')}.")
        elif float(t.get("received_qty") or 0) > 0 or await db.inventory_rolls.count_documents(
                {"grn_task_id": tid, "status": "receiving", "grn_id": {"$ne": grn_id}}):
            errors.append(f"Tugas {t.get('po_number')} / {t.get('sku')} sudah setengah jalan lewat penerimaan lama — "
                          "selesaikan dulu di layar Barang Masuk.")
    if errors:
        raise HTTPException(status_code=400, detail={"code": "NOT_READY", "message": " ".join(errors),
                                                     "errors": errors})
    key = active_key_of(grn)
    try:
        doc = await cas(grn, ["review"], expected_version,
                        {"status": "counting", "active_key": key, "count_started_at": now_iso(),
                         "count_started_by": actor["name"]})
    except DuplicateKeyError:
        other = await db.goods_receipts.find_one({"active_key": key}, {"_id": 0, "number": 1, "status": 1}) or {}
        raise HTTPException(status_code=409, detail={
            "code": "DN_DUPLICATE", "existing_number": other.get("number", ""),
            "message": (f"Surat jalan {grn['dn']['number']} dari {grn['partner_name']} sudah dicatat di "
                        f"kedatangan {other.get('number', '?')} ({other.get('status', '?')}).")})
    claimed: List[str] = []
    for tid in task_ids:
        t = await db.wms_tasks.find_one_and_update(
            {"id": tid, "status": {"$in": ACTIVE_TASK},
             "$or": [{"grn_active_id": {"$exists": False}}, {"grn_active_id": {"$in": ["", None, grn_id]}}]},
            {"$set": {"grn_active_id": grn_id, "grn_active_number": grn["number"], "updated_at": now_iso()},
             "$addToSet": {"grn_ids": grn_id}}, projection={"_id": 0, "id": 1})
        if not t:
            await release_tasks(grn_id)
            await db.goods_receipts.update_one({"id": grn_id}, {"$set": {"status": "review"},
                                                                "$unset": {"active_key": ""}, "$inc": {"version": 1}})
            raise HTTPException(status_code=409, detail={
                "code": "STATE_CHANGED", "message": "Salah satu tugas baru saja diambil proses lain. Muat ulang layar."})
        claimed.append(tid)
    from services import doc_refs_service as _refs
    for ln in stock:
        tgt = ln.get("target") or {}
        if tgt.get("po_id"):
            await _refs.safe_link(("goods_receipt", grn_id), ("purchase_order", tgt["po_id"]), "parent")
        if tgt.get("mko_id"):
            await _refs.safe_link(("goods_receipt", grn_id), ("makloon_order", tgt["mko_id"]), "parent")
    await audit(actor["name"], "grn_count_started", "goods_receipt", grn_id, {"tasks": claimed},
                scope_entity_id=grn["entity_id"])
    return doc


# ── hitung fisik ──────────────────────────────────────────────────────────────
def _count_target(grn: Dict[str, Any], line_no: int) -> Dict[str, Any]:
    require_status(grn, ["counting"], "Hitung roll")
    ln = _find_line(grn, line_no)
    if ln.get("is_non_stock") or ln.get("decision") != "accept" or not ln.get("target"):
        raise HTTPException(status_code=400, detail=f"Baris {line_no} tidak dihitung (non-stok / ditolak / tanpa target).")
    return ln


async def refresh_counted(grn: Dict[str, Any], actor_name: str, expected_version: Optional[int] = None,
                          mutate: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
                          statuses: Optional[List[str]] = None) -> Dict[str, Any]:
    """`counted` = TURUNAN roll `receiving` ber-`grn_id` (+ roll makloon tersimpan), bukan angka ketikan."""
    lines = [dict(x) for x in grn.get("lines") or []]
    if mutate:
        mutate(lines)
    rolls = await db.inventory_rolls.find({"grn_id": grn["id"], "status": "receiving"}, {"_id": 0}).to_list(2000)
    for ln in lines:
        c = dict(ln.get("counted") or {})
        mk = list(c.get("makloon_rolls") or [])
        if (ln.get("target") or {}).get("type") == "mko_step":
            qty, n, wt, ids = sum(r["length"] for r in mk), len(mk), sum(r.get("weight_kg") or 0 for r in mk), [r["id"] for r in mk]
        else:
            mine = [r for r in rolls if r.get("grn_line_no") == ln["line_no"]]
            qty = sum(float(r["actual_task_qty"] if r.get("actual_task_qty") is not None
                            else r.get("declared_task_qty") or 0) for r in mine)
            n, wt, ids = len(mine), sum(float(r.get("weight_kg") or 0) for r in mine), [r["id"] for r in mine]
        ln["counted"] = {"qty": round(qty, 2), "rolls": n, "weight_kg": round(wt, 3), "roll_ids": ids,
                         "makloon_rolls": mk}
    return await cas(grn, statuses or ["counting"], expected_version, {"lines": lines},
                     extra={"$addToSet": {"counted_by": actor_name}})


def _check_version(grn: Dict[str, Any], expected_version: Optional[int]) -> None:
    if expected_version is not None and expected_version != grn.get("version"):
        raise state_changed()


async def scan_label(grn_id: str, line_no: int, body: Any, actor: Dict[str, Any], ctx: EntityContext):
    from services.receiving_roll_service import create_label_roll, resolve_label_input, undo_receiving_roll
    grn = await load(grn_id, ctx)
    ln = _count_target(grn, line_no)
    _check_version(grn, body.expected_version)
    if ln["target"]["type"] != "po_task":
        raise HTTPException(status_code=400, detail="Scan label hanya untuk baris PO. Roll makloon dicatat manual.")
    task = await db.wms_tasks.find_one({"id": ln["target"]["task_id"]}, {"_id": 0})
    li = await resolve_label_input(task, body.raw, body.manual)
    res = await create_label_roll(task=task, decoded=li["decoded"], sitem=li["sitem"], product=li["product"],
                                  po=li["po"], sup=li["sup"], supplier_id=li["supplier_id"],
                                  owner_entity_id=li["owner_entity_id"], actor=actor, manual=body.manual,
                                  grn_fields={"grn_id": grn_id, "grn_line_no": line_no}, enforce_over_po=False)
    try:
        doc = await refresh_counted(grn, actor["name"])
    except HTTPException:
        await undo_receiving_roll(res["roll"], res["task"])
        raise
    return {"roll": safe_doc(res["roll"]), "grn": doc}


async def add_counted_roll(grn_id: str, line_no: int, body: Any, actor: Dict[str, Any], ctx: EntityContext):
    from services.inbound_complete_service import grade_or_400
    from services.receiving_roll_service import create_counted_roll, undo_receiving_roll
    grn = await load(grn_id, ctx)
    ln = _count_target(grn, line_no)
    _check_version(grn, body.expected_version)
    grade = grade_or_400(body.grade or "A", "A")
    if body.length <= 0 and body.weight_kg <= 0:
        raise HTTPException(status_code=400, detail="Isi panjang atau berat roll yang dihitung.")
    if ln["target"]["type"] == "mko_step":
        if not body.lot.strip() or body.length <= 0:
            raise HTTPException(status_code=400, detail="Roll makloon wajib punya LOT dan panjang.")
        roll = {"id": new_id("mkr"), "lot": body.lot.strip(), "length": round(body.length, 2),
                "weight_kg": round(body.weight_kg, 3), "grade": grade, "dye_lot": body.lot.strip(),
                "by": actor["name"], "at": now_iso()}

        def _push(lines: List[Dict[str, Any]]) -> None:
            tgt = next(x for x in lines if x["line_no"] == line_no)
            tgt["counted"] = {**tgt["counted"], "makloon_rolls": [*tgt["counted"].get("makloon_rolls", []), roll]}
        return {"roll": roll, "grn": await refresh_counted(grn, actor["name"], mutate=_push)}
    task = await db.wms_tasks.find_one({"id": ln["target"]["task_id"]}, {"_id": 0})
    po = await db.purchase_orders.find_one({"id": task.get("po_id")}, {"_id": 0, "entity_id": 1, "supplier_id": 1,
                                                                       "supplier_name": 1}) or {}
    product = safe_doc(await db.products.find_one({"id": task["product_id"]}, {"_id": 0})) or {}
    res = await create_counted_roll(
        task=task, product=product, owner_entity_id=po.get("entity_id") or task.get("entity_id"), actor=actor,
        length=body.length, weight_kg=body.weight_kg, lot=body.lot.strip(), grade=grade,
        supplier_id=po.get("supplier_id", ""), supplier_name=po.get("supplier_name", ""),
        extra={"grn_id": grn_id, "grn_line_no": line_no})
    try:
        doc = await refresh_counted(grn, actor["name"])
    except HTTPException:
        await undo_receiving_roll(res["roll"], res["task"])
        raise
    return {"roll": safe_doc(res["roll"]), "grn": doc}


async def delete_roll(grn_id: str, roll_id: str, actor: Dict[str, Any], ctx: EntityContext):
    from services.receiving_roll_service import undo_receiving_roll
    grn = await load(grn_id, ctx)
    require_status(grn, ["counting"], "Batalkan roll")
    roll = await db.inventory_rolls.find_one({"id": roll_id, "grn_id": grn_id}, {"_id": 0})
    if roll:
        if roll.get("status") != "receiving":
            raise HTTPException(status_code=400, detail="Roll sudah masuk stok — tidak bisa dibatalkan di sini.")
        task = await db.wms_tasks.find_one({"id": roll["grn_task_id"]}, {"_id": 0}) or {}
        await undo_receiving_roll(roll, task)
        doc = await refresh_counted(grn, actor["name"])
    else:
        hit = [ln for ln in grn.get("lines") or []
               if any(r["id"] == roll_id for r in (ln.get("counted") or {}).get("makloon_rolls") or [])]
        if not hit:
            raise HTTPException(status_code=404, detail="Roll tidak ditemukan di kedatangan ini.")

        def _pull(lines: List[Dict[str, Any]]) -> None:
            for x in lines:
                c = x.get("counted") or {}
                c["makloon_rolls"] = [r for r in c.get("makloon_rolls") or [] if r["id"] != roll_id]
        doc = await refresh_counted(grn, actor["name"], mutate=_pull)
    await audit(actor["name"], "grn_roll_removed", "goods_receipt", grn_id, {"roll_id": roll_id},
                scope_entity_id=grn["entity_id"])
    return doc


# ── pendukung layar (Fase 3) ─────────────────────────────────────────────────
async def list_partners(partner_type: str, ctx: EntityContext) -> List[Dict[str, Any]]:
    """Mitra yang punya PO/MKO terbuka menunggu barang di badan usaha aktif (langkah 1 wizard)."""
    from routers.purchase_orders import TERMINAL_PO_STATUSES
    ent = ctx.active_entity_id
    out: Dict[str, Dict[str, Any]] = {}
    if partner_type == "makloon":
        for o in await db.makloon_orders.find({"entity_id": ent, "status": {"$nin": ["completed", "cancelled"]}},
                                              {"_id": 0, "id": 1, "mko_number": 1, "steps": 1,
                                               "target_warehouse_id": 1}).to_list(1000):
            for s in o.get("steps") or []:
                if s.get("status") == "issued" and s.get("makloon_id"):
                    p = out.setdefault(s["makloon_id"], {"partner_id": s["makloon_id"],
                                                         "partner_name": s.get("makloon_name", ""), "open_docs": []})
                    if not any(d["id"] == o["id"] for d in p["open_docs"]):
                        p["open_docs"].append({"id": o["id"], "number": o.get("mko_number", ""),
                                               "warehouse_id": o.get("target_warehouse_id", "")})
        return sorted(out.values(), key=lambda x: x["partner_name"])
    po_ids = await db.wms_tasks.distinct("po_id", {"entity_id": ent, "flow_type": "inbound",
                                                   "status": {"$in": ACTIVE_TASK}, "po_id": {"$gt": ""}})
    for po in await db.purchase_orders.find(
            {"id": {"$in": po_ids}, "status": {"$nin": list(TERMINAL_PO_STATUSES)}},
            {"_id": 0, "id": 1, "po_number": 1, "supplier_id": 1, "supplier_name": 1, "warehouse_id": 1}).to_list(1000):
        p = out.setdefault(po["supplier_id"], {"partner_id": po["supplier_id"],
                                               "partner_name": po.get("supplier_name", ""), "open_docs": []})
        p["open_docs"].append({"id": po["id"], "number": po.get("po_number", ""),
                               "warehouse_id": po.get("warehouse_id", "")})
    return sorted(out.values(), key=lambda x: x["partner_name"])


async def list_rolls(grn_id: str, ctx: EntityContext) -> List[Dict[str, Any]]:
    """Roll yang sudah dihitung di GRN ini (angka hitung fisik — boleh dilihat penghitung)."""
    grn = await load(grn_id, ctx)
    rows = await db.inventory_rolls.find(
        {"grn_id": grn_id}, {"_id": 0, "id": 1, "roll_no": 1, "grn_line_no": 1, "length_initial": 1, "unit": 1,
                             "weight_kg": 1, "lot": 1, "dye_lot": 1, "grade": 1, "status": 1, "scan_source": 1,
                             "supplier_roll_no": 1, "actual_task_qty": 1, "declared_task_qty": 1,
                             "created_at": 1}).sort("created_at", 1).to_list(2000)
    for ln in grn.get("lines") or []:
        for r in (ln.get("counted") or {}).get("makloon_rolls") or []:
            rows.append({"id": r["id"], "roll_no": "", "grn_line_no": ln["line_no"], "length_initial": r["length"],
                         "unit": (ln.get("target") or {}).get("unit", ""), "weight_kg": r.get("weight_kg"),
                         "lot": r["lot"], "dye_lot": r.get("dye_lot", ""), "grade": r["grade"], "status": "makloon",
                         "scan_source": "count", "created_at": r.get("at", "")})
    return rows


async def supplier_variance(ctx: EntityContext, since: str = "") -> List[Dict[str, Any]]:
    """Ringkasan selisih per mitra dari GRN yang DITUTUP: siapa yang sering kirim kurang / diklaim."""
    ents = ctx.allowed_entity_ids if ctx.view_all else [ctx.active_entity_id]
    flt: Dict[str, Any] = {"entity_id": {"$in": ents}, "status": "closed"}
    if since:
        flt["closed_at"] = {"$gte": since}
    agg: Dict[str, Dict[str, Any]] = {}
    for g in await db.goods_receipts.find(flt, {"_id": 0}).sort("closed_at", -1).to_list(5000):
        a = agg.setdefault(g["partner_id"], {
            "partner_id": g["partner_id"], "partner_name": g["partner_name"], "partner_type": g["partner_type"],
            "grn_count": 0, "lines": 0, "short_lines": 0, "short_qty": 0.0, "rolls_mismatch": 0, "not_arrived": 0,
            "over_remaining": 0, "claims": 0, "grn_with_issue": 0, "last_closed_at": "", "recent": []})
        a["grn_count"] += 1
        a["last_closed_at"] = a["last_closed_at"] or g.get("closed_at", "")
        kinds: List[str] = []
        for ln in g.get("lines") or []:
            if ln.get("is_non_stock"):
                continue
            a["lines"] += 1
            cls = (ln.get("recon") or {}).get("classes") or []
            if "short_vs_dn" in cls or "not_arrived" in cls:
                a["short_lines"] += 1
                a["short_qty"] = round(a["short_qty"] - min(0.0, float((ln.get("recon") or {}).get("diff_qty") or 0)), 2)
            a["rolls_mismatch"] += int("rolls_mismatch" in cls)
            a["not_arrived"] += int("not_arrived" in cls)
            a["over_remaining"] += int("over_remaining" in cls)
            a["claims"] += int(bool(ln.get("claim")))
            kinds += [c for c in cls if c not in ("match", "non_stock", "rejected")]
        if kinds:
            a["grn_with_issue"] += 1
            if len(a["recent"]) < 5:
                a["recent"].append({"id": g["id"], "number": g["number"], "dn_number": (g.get("dn") or {}).get("number", ""),
                                    "closed_at": g.get("closed_at", ""), "kinds": sorted(set(kinds))})
    rows = list(agg.values())
    for r in rows:
        r["issue_rate_pct"] = round(r["grn_with_issue"] / r["grn_count"] * 100, 1) if r["grn_count"] else 0.0
    return sorted(rows, key=lambda r: (-r["issue_rate_pct"], -r["short_qty"]))
