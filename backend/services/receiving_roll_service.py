"""Kelahiran roll `receiving` saat penerimaan (GRN Fase 1: dipindah dari `routers/inbound_scan_label.py`).

Dua masukan:
- **label** (`create_label_roll`) — angka DEKLARASI dari label supplier; aktual dikonfirmasi belakangan.
- **hitung manual** (`create_counted_roll`) — angka AKTUAL dari timbangan/meteran; deklarasi kosong
  (dipakai layar Hitung GRN, Fase 2).
Keduanya menempel ke tugas inbound lewat CAS yang sama (`attach_roll_to_task`) + kompensasi saga.
"""
import logging
from typing import Any, Dict, Optional

from fastapi import HTTPException
from pymongo import ReturnDocument

import domain_registry as _dr
from core_utils import DEFAULT_ENTITY_ID, new_id, now_iso, safe_doc
from db import db
from dependencies import audit

_LEN_FACTOR = {"meter": 1.0, "m": 1.0, "yard": 0.9144, "yd": 0.9144}


def to_meter(qty: float, unit: str) -> float:
    return float(qty or 0) * _LEN_FACTOR.get((unit or "meter").lower(), 1.0)


def from_meter(qty_m: float, unit: str) -> float:
    return float(qty_m or 0) / _LEN_FACTOR.get((unit or "meter").lower(), 1.0)


_to_meter, _from_meter = to_meter, from_meter


async def receiving_cfg(key: str, entity_id: str) -> Any:
    """Kunci `receiving.*` HANYA lewat resolver (GRN Fase 0.2)."""
    from services.config_resolver import value_of
    return await value_of(f"receiving.{key}", {"entity_id": entity_id or ""})


_receiving_cfg = receiving_cfg


async def build_receiving_roll(task: Dict[str, Any], product: Dict[str, Any], owner_entity_id: str,
                               actor: Dict[str, Any], *, length_base: float, weight_kg: float, lot: str,
                               supplier_lot: str, dye_lot: str, grade: str, supplier_id: str, supplier_name: str,
                               extra: Dict[str, Any]) -> Dict[str, Any]:
    """Susun + simpan roll `receiving` (+ RFID otomatis best-effort). `extra` = field khusus sumber."""
    from services.roll_service import next_roll_no
    task_id = task["id"]
    base_unit = product.get("base_unit") or "meter"
    roll_doc = {
        "id": new_id("roll"), "roll_no": await next_roll_no(),
        "product_id": task["product_id"], "owner_entity_id": owner_entity_id,
        "ownership_type": "internal", "consignor_ref": None,
        "warehouse_id": task["warehouse_id"], "bin_id": None, "bin_code": "",
        "lot": lot, "lot_id": "",
        "supplier_lot": supplier_lot, "dye_lot": dye_lot,
        "batch": task.get("batch") or "",
        "length_initial": length_base, "length_remaining": length_base, "unit": base_unit,
        "weight_kg": round(weight_kg, 3), "weight_unit": "kg",
        "secondary_measures": {"kg": round(weight_kg, 3)} if weight_kg > 0 else None,
        "grade": grade, "defects": [],
        **_dr.roll_domain_snapshot(product),
        "status": "receiving", "qc_task_id": None, "tracking_mode": "barcode",
        "earmarked_for": None, "location_type": "warehouse_bin", "reserved_ref": None,
        "unit_cost": None, "base_unit_cost": None, "landed_cost_total": 0.0, "landed_cost_refs": [],
        "acquired": {"via": "inbound", "ref_id": task.get("po_id") or task_id, "date": now_iso()},
        "supplier_id": supplier_id, "supplier_name": supplier_name,
        "po_id": task.get("po_id") or "", "po_number": task.get("po_number", ""),
        "grn_task_id": task_id, "received_date": now_iso(),
        "vendor_bill_id": "", "supplier_invoice_no": "", "rfid_tag_id": None, "is_remnant": False,
        **extra,
        "journey": {"stage": "receiving", "routing": "store", "updated_at": now_iso()},
        "created_at": now_iso(), "updated_at": now_iso(),
        "created_by": actor.get("id") or "system", "created_by_name": actor["name"],
    }
    await db.inventory_rolls.insert_one(dict(roll_doc))

    # FASE SL — RFID Auto-Tag: EPC lahir bersama roll (best-effort; gagal → petugas tag manual).
    roll_doc["rfid_epc"] = ""
    if bool(await receiving_cfg("auto_rfid_on_scan", owner_entity_id)):
        try:
            from services import rfid_service as _rfid
            _tag = await _rfid.encode_tag(roll_doc["id"], [owner_entity_id], actor_name=actor["name"])
            roll_doc["rfid_tag_id"], roll_doc["tracking_mode"], roll_doc["rfid_epc"] = _tag["id"], "rfid", _tag["epc"]
        except HTTPException as exc:
            logging.getLogger(__name__).warning("Auto-RFID roll %s gagal: %s", roll_doc["roll_no"], exc.detail)
    return roll_doc


async def attach_roll_to_task(task: Dict[str, Any], roll_doc: Dict[str, Any], *, task_qty: float, over: bool,
                              tol_close: float, supplier_lot: str, actor: Dict[str, Any],
                              scan_entry_extra: Dict[str, Any], audit_extra: Dict[str, Any]) -> Dict[str, Any]:
    """CAS tugas inbound (+$inc received_qty & qty_rolls_scanned); kalah → roll dihapus (kompensasi) + 409."""
    task_id = task["id"]
    expected = float(task.get("expected_qty") or 0)
    new_received = round(float(task.get("received_qty") or 0) + task_qty, 2)
    # INV-ATOMIC-01 — received_qty & qty_rolls_scanned di-$inc (bukan $set nilai yang dibaca
    # tadi) supaya dua pemindai pada satu tugas tidak saling menimpa; status berprasyarat hidup.
    upd: Dict[str, Any] = {
        "updated_at": now_iso(),
        "over_receipt": bool(over), "receive_within_tolerance": not over,
        "receive_mode": "scan_label",
    }
    _inc: Dict[str, Any] = {"received_qty": task_qty, "qty_rolls_scanned": 1}
    if not task.get("supplier_lot") and supplier_lot:
        upd["supplier_lot"] = supplier_lot
    if task["status"] == "waiting_goods":
        upd["status"] = "receiving"
    if expected > 0 and new_received >= expected * (1 - tol_close / 100):
        upd["status"] = "qc_check"
    scan_entry = {"id": new_id("scan"), "actual_qty": task_qty,
                  "lot": supplier_lot, "roll_id": roll_doc["id"], "roll_no": roll_doc["roll_no"],
                  **scan_entry_extra, "actor": actor["name"], "timestamp": now_iso()}
    updated = await db.wms_tasks.find_one_and_update(
        {"id": task_id, "status": {"$in": ["waiting_goods", "receiving", "qc_check"]}},
        {"$set": upd, "$inc": _inc, "$push": {"scan_log": scan_entry}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not updated:
        await db.inventory_rolls.delete_one({"id": roll_doc["id"]})   # kompensasi saga
        raise HTTPException(status_code=409, detail="Tugas penerimaan sudah selesai/berubah — pindaian dibatalkan. Muat ulang.")
    if updated.get("status") == "qc_check" and float(updated.get("quantity") or 0) != float(updated.get("received_qty") or 0):
        await db.wms_tasks.update_one({"id": task_id}, {"$set": {"quantity": updated.get("received_qty")}})
    await audit(actor["name"], "inbound_scan_label", "wms_task", task_id, {
        "roll_no": roll_doc["roll_no"], "supplier_lot": supplier_lot, "task_qty": task_qty, **audit_extra})
    return safe_doc(updated)


async def create_label_roll(*, task: Dict[str, Any], decoded: Dict[str, Any], sitem: Dict[str, Any],
                            product: Dict[str, Any], po: Dict[str, Any], sup: Dict[str, Any], supplier_id: str,
                            owner_entity_id: str, actor: Dict[str, Any], manual: Any = None,
                            grn_fields: Optional[Dict[str, Any]] = None,
                            enforce_over_po: bool = True) -> Dict[str, Any]:
    """Masukan LABEL: deklarasi dari label → roll `receiving` + tugas diperbarui. Return {roll, task}.

    GRN: `grn_fields` ({grn_id, grn_line_no}) ikut ke roll; `enforce_over_po=False` → lebih-PO jadi selisih GRN."""
    base_unit = product.get("base_unit") or "meter"
    task_unit = task.get("unit") or base_unit
    supplier_roll_no = (decoded.get("roll_no") or "").strip()
    if not supplier_roll_no:
        raise HTTPException(status_code=400, detail={
            "code": "NO_ROLL_NO",
            "message": "Label tidak memuat nomor roll supplier. Gunakan 'Label tidak terbaca' dan "
                       "masukkan nomor roll dari label fisik.", "decoded": decoded})
    dup = await db.inventory_rolls.find_one(
        {"supplier_id": supplier_id, "supplier_roll_no": supplier_roll_no}, {"_id": 0, "roll_no": 1, "status": 1})
    if dup:
        raise HTTPException(status_code=409, detail={
            "code": "DUPLICATE", "message": (f"Roll supplier {supplier_roll_no} sudah diterima sebagai "
                                            f"{dup.get('roll_no')} (status {dup.get('status')}).")})

    # ── qty deklarasi (label) → satuan task & base unit ────────────────────
    length_label = float(decoded.get("length") or 0)
    label_unit = decoded.get("length_unit") or "yard"
    weight_kg = float(decoded.get("weight_kg") or 0)
    from services.uom_service import kg_per_base_unit, load_fixed_factors
    factors = await load_fixed_factors()
    kgpb = kg_per_base_unit(product, factors)
    length_m = _to_meter(length_label, label_unit)
    if length_m <= 0 and weight_kg > 0 and kgpb > 0:
        length_m = _to_meter(weight_kg / kgpb, base_unit)
    if length_m <= 0 and weight_kg <= 0:
        conv = float(sitem.get("conv_factor") or 0)
        if conv > 0 and (sitem.get("supplier_uom") or "").lower() in ("roll", "rol", "rll", "gulung"):
            length_m = _to_meter(conv, base_unit)
    if length_m <= 0 and weight_kg <= 0:
        raise HTTPException(status_code=400, detail={
            "code": "NO_QTY", "message": "Label tidak memuat panjang/berat. Gunakan 'Label tidak terbaca' "
                                         "dan isi panjang dari label fisik.", "decoded": decoded})
    length_base = round(_from_meter(length_m, base_unit), 2)
    if weight_kg <= 0 and kgpb > 0:
        weight_kg = round(length_base * kgpb, 3)
    task_qty = round(weight_kg if task_unit.lower() == "kg" else _from_meter(length_m, task_unit), 2)

    # ── pagar PO: qty belum lewat (toleransi kedatangan) ───────────────────
    from services.config_service import get_effective_settings
    settings = await get_effective_settings(owner_entity_id)
    tol_recv = float((settings.get("purchasing", {}) or {}).get("receive_tolerance_percent", 2.0) or 0)
    block_over = bool(await _receiving_cfg("block_over_remaining", owner_entity_id))
    expected = float(task.get("expected_qty") or 0)
    new_received = round(float(task.get("received_qty") or 0) + task_qty, 2)
    over = expected > 0 and new_received > expected * (1 + tol_recv / 100)
    if over and block_over and enforce_over_po:
        raise HTTPException(status_code=400, detail={
            "code": "OVER_PO", "message": (f"Roll ini membuat total {new_received:g} {task_unit} melebihi PO "
                                          f"{expected:g} {task_unit} + toleransi {tol_recv:g}%. Eskalasi ke "
                                          f"manajer bila kiriman memang lebih."), "decoded": decoded})

    supplier_lot = (decoded.get("lot") or "").strip()
    roll_doc = await build_receiving_roll(
        task, product, owner_entity_id, actor, length_base=length_base, weight_kg=weight_kg,
        lot=supplier_lot or task.get("lot") or "", supplier_lot=supplier_lot,
        dye_lot=supplier_lot or task.get("dye_lot") or "", grade=sitem.get("expected_grade") or "A",
        supplier_id=supplier_id, supplier_name=po.get("supplier_name") or sup.get("name", ""),
        extra={
            # ── alias supplier (telusur balik dye lot / komplain warna) ───────────
            "supplier_roll_no": supplier_roll_no,
            "supplier_sku": sitem.get("supplier_sku") or decoded.get("supplier_sku") or "",
            "supplier_item_name": sitem.get("supplier_item_name") or "",
            "supplier_color_code": (decoded.get("color_code") or sitem.get("supplier_color_code") or ""),
            "supplier_item_id": sitem.get("id") or "",
            # ── deklarasi label vs aktual ───────────────────────────────────────────
            "declared_length": length_base, "declared_length_label": length_label or None,
            "declared_length_unit": label_unit, "declared_weight_kg": round(weight_kg, 3),
            "declared_task_qty": task_qty, "actual_task_qty": None,
            "measure_confirmed": False, "label_variance": None,
            "scan_source": decoded.get("format", "manual"), "raw_label": decoded.get("raw", ""),
            "manual_override": ({"reason": manual.reason, "note": manual.reason_note, "by": actor["name"],
                                 "at": now_iso()} if manual else None),
            **(grn_fields or {}),
        })

    updated = await attach_roll_to_task(
        task, roll_doc, task_qty=task_qty, over=over, tol_close=tol_recv, supplier_lot=supplier_lot, actor=actor,
        scan_entry_extra={"scan_type": "label", "supplier_roll_no": supplier_roll_no,
                          "format": roll_doc["scan_source"], "manual": bool(manual)},
        audit_extra={"supplier_roll_no": supplier_roll_no, "format": roll_doc["scan_source"], "manual": bool(manual)})
    return {"roll": roll_doc, "task": updated}


async def create_counted_roll(*, task: Dict[str, Any], product: Dict[str, Any], owner_entity_id: str,
                              actor: Dict[str, Any], length: float = 0.0, weight_kg: float = 0.0,
                              lot: str = "", grade: str = "A", supplier_id: str = "", supplier_name: str = "",
                              extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Masukan HITUNG MANUAL: panjang (base unit) / berat AKTUAL dari gudang, deklarasi kosong.

    Belum dipanggil jalur mana pun (disiapkan untuk layar Hitung GRN, Fase 2). Return {roll, task}.
    """
    from services.uom_service import kg_per_base_unit, load_fixed_factors
    base_unit = product.get("base_unit") or "meter"
    task_unit = task.get("unit") or base_unit
    kgpb = kg_per_base_unit(product, await load_fixed_factors())
    length_base = round(float(length or 0), 2)
    if length_base <= 0 and weight_kg > 0 and kgpb > 0:
        length_base = round(weight_kg / kgpb, 2)
    if length_base <= 0 and weight_kg <= 0:
        raise HTTPException(status_code=400, detail="Isi panjang atau berat roll yang dihitung.")
    if weight_kg <= 0 and kgpb > 0:
        weight_kg = round(length_base * kgpb, 3)
    task_qty = round(weight_kg if task_unit.lower() == "kg" else from_meter(to_meter(length_base, base_unit), task_unit), 2)
    grade = _dr.require_grade(grade, "A")
    roll_doc = await build_receiving_roll(
        task, product, owner_entity_id, actor, length_base=length_base, weight_kg=weight_kg,
        lot=lot or task.get("lot") or "", supplier_lot=lot, dye_lot=lot or task.get("dye_lot") or "", grade=grade,
        supplier_id=supplier_id, supplier_name=supplier_name,
        extra={"declared_length": None, "declared_weight_kg": None, "declared_task_qty": None,
               "actual_task_qty": task_qty, "measure_confirmed": True, "label_variance": None,
               "scan_source": "count", **(extra or {})})
    updated = await attach_roll_to_task(
        task, roll_doc, task_qty=task_qty, over=False, tol_close=0.0, supplier_lot=lot, actor=actor,
        scan_entry_extra={"scan_type": "count", "format": "count", "manual": True},
        audit_extra={"format": "count", "manual": True})
    return {"roll": roll_doc, "task": updated}


async def resolve_label_input(task: Dict[str, Any], raw: str, manual: Any = None) -> Dict[str, Any]:
    """Decode label (atau fallback manual) → Barang Supplier yang sah untuk tugas ini; 400 bila tidak."""
    from services import label_decoder_service as ldec
    po = safe_doc(await db.purchase_orders.find_one({"id": task.get("po_id")}, {"_id": 0})) or {}
    supplier_id = po.get("supplier_id", "") or task.get("supplier_id", "")
    sup = safe_doc(await db.suppliers.find_one({"id": supplier_id}, {"_id": 0})) or {}
    product = safe_doc(await db.products.find_one({"id": task["product_id"]}, {"_id": 0})) or {}
    owner_entity_id = po.get("entity_id") or task.get("entity_id") or DEFAULT_ENTITY_ID

    from services import supplier_item_service as sis
    if manual:
        decoded = {"supplier_sku": "", "gtin": "", "lot": manual.lot.strip(),
                   "roll_no": manual.supplier_roll_no.strip(), "length": manual.declared_length or None,
                   "length_unit": "meter" if manual.length_unit.lower().startswith("m") else "yard",
                   "weight_kg": manual.declared_weight_kg or None, "color_code": manual.color_code.strip(),
                   "format": "manual", "raw": raw or ""}
        sitem = await sis.get_item(manual.supplier_item_id) if manual.supplier_item_id else None
        if sitem is None:
            sitem = await sis.resolve_for_product(supplier_id=supplier_id, product_id=task["product_id"],
                                                  entity_id=owner_entity_id) or {}
    else:
        # FASE SL — pola per Barang Supplier dicoba lebih dulu (supplier campur-label), lalu pola supplier.
        pattern_items = await sis.label_pattern_candidates(
            supplier_id=supplier_id, product_id=task["product_id"], entity_id=owner_entity_id)
        candidates = [(f"item:{it['supplier_sku']}", it["label_pattern"]) for it in pattern_items]
        candidates.append(("supplier", sup.get("label_pattern")))
        try:
            decoded = ldec.decode_first(raw, candidates)
        except ldec.LabelDecodeError as exc:
            raise HTTPException(status_code=400, detail={"code": "UNDECODABLE", "message": str(exc)}) from exc
        sitem = None
        if decoded.get("supplier_sku"):
            sitem = await sis.lookup(supplier_sku=decoded["supplier_sku"], supplier_id=supplier_id,
                                     entity_id=owner_entity_id)
        if sitem is None and decoded.get("gtin"):
            flt: Dict[str, Any] = {"barcode": decoded["gtin"]}
            if supplier_id:
                flt["supplier_id"] = supplier_id
            sitem = safe_doc(await db.supplier_items.find_one(flt, {"_id": 0}))
        if sitem is None and not decoded.get("supplier_sku") and not decoded.get("gtin") \
                and str(decoded.get("pattern_source", "")).startswith("item:"):
            # Label tanpa kode barang tetapi cocok pola khusus barang → barang tersirat dari polanya.
            sitem = next((it for it in pattern_items
                          if f"item:{it['supplier_sku']}" == decoded["pattern_source"]), None)
            if sitem:
                decoded["supplier_sku"] = sitem["supplier_sku"]
        if sitem is None:
            other = await sis.lookup(supplier_sku=decoded["supplier_sku"], entity_id=owner_entity_id) \
                if decoded.get("supplier_sku") else None
            if other:
                raise HTTPException(status_code=400, detail={
                    "code": "NOT_IN_TASK",
                    "message": (f"Kode '{decoded['supplier_sku']}' adalah barang '{other.get('supplier_item_name') or other.get('sku')}' "
                                f"dari supplier {other.get('supplier_name') or 'lain'} — bukan barang PO ini "
                                f"({task.get('sku')}). Pilih tugas penerimaan yang sesuai atau eskalasi."),
                    "decoded": decoded})
            raise HTTPException(status_code=400, detail={
                "code": "UNMAPPED",
                "message": (f"Barang '{decoded.get('supplier_sku') or decoded.get('gtin') or '?'}' tidak ada di PO / "
                            f"belum dipetakan ke produk kami. Eskalasi ke purchasing untuk memetakan "
                            f"kode supplier ini di master Barang Supplier."),
                "decoded": decoded})
    sitem = sitem or {}
    if sitem and sitem.get("product_id") != task["product_id"]:
        raise HTTPException(status_code=400, detail={
            "code": "NOT_IN_TASK",
            "message": (f"Label ini barang '{sitem.get('supplier_item_name') or sitem.get('supplier_sku')}' "
                        f"({sitem.get('sku')}), bukan barang tugas ini ({task.get('sku')}). "
                        f"Pilih tugas penerimaan yang sesuai atau eskalasi."),
            "decoded": decoded})
    return {"decoded": decoded, "sitem": sitem, "product": product, "po": po, "sup": sup,
            "supplier_id": supplier_id, "owner_entity_id": owner_entity_id}


async def undo_receiving_roll(roll: Dict[str, Any], task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Batalkan roll `receiving` (hapus + kurangi received_qty tugas). Return tugas terbaru."""
    qty = float(roll.get("actual_task_qty") if roll.get("actual_task_qty") is not None else roll.get("declared_task_qty") or 0)
    # INV-ATOMIC-01 — hapus berprasyarat status (dua "batalkan" bersamaan → satu yang menang
    # dan hanya satu yang mengurangi received_qty lewat $inc).
    _del = await db.inventory_rolls.delete_one({"id": roll["id"], "status": "receiving"})
    if _del.deleted_count == 0:
        raise HTTPException(status_code=409, detail="Roll sudah dibatalkan/berubah oleh proses lain.")
    new_recv = max(0.0, round(float(task.get("received_qty") or 0) - qty, 2))
    upd = {"updated_at": now_iso()}
    if task.get("status") == "qc_check" and new_recv < float(task.get("expected_qty") or 0):
        upd["status"] = "receiving"
    t = await db.wms_tasks.find_one_and_update(
        {"status": {"$in": ["waiting_goods", "receiving", "qc_check"]}, "id": task["id"]},
        {"$set": upd, "$inc": {"received_qty": -qty, "qty_rolls_scanned": -1}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if t and (float(t.get("received_qty") or 0) < 0 or int(t.get("qty_rolls_scanned") or 0) < 0):
        await db.wms_tasks.update_one({"id": task["id"]}, {"$set": {
            "received_qty": max(0.0, float(t.get("received_qty") or 0)),
            "qty_rolls_scanned": max(0, int(t.get("qty_rolls_scanned") or 0))}})
    return safe_doc(t)
