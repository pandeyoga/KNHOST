"""L04 LN-042 — POTONG MD QUALITY (default 0,25 yard) sebagai MUTASI PEMAKAIAN tersendiri.

- Qty receiving (`length_initial`) tetap bruto; hanya `length_remaining` berkurang. Roll/EPC tidak berubah.
- Idempoten per baris inspeksi (`_id` = inspeksi:baris) — retry/kirim ulang tidak memotong dua kali.
- Basis kg: WAJIB berat aktual potongan (timbang) atau aturan `kg_per_yard_validated` produk;
  GSM/lebar hanya estimasi dan TIDAK dipakai mengurangi stok kg. Tanpa data → diblok dengan alasan.
- Nilai potongan → GL write-off (Dr 5-9500 / Cr 1-1300), idempoten per potongan.
"""
from typing import Any, Dict, Optional

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from core_utils import new_id, now_iso
from db import db
from services import gl_service as gl
from services.roll_service import rebuild_balance

YARD_TO_METER = 0.9144


def _ago(sec: int) -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(seconds=sec)).isoformat()
CUT_STATUSES = ("available", "quarantine", "qc_hold", "inspection")


async def cut(ins_id: str, line_id: str, *, cut_yard: float = 0.25, weight_kg: Optional[float] = None,
              reason: str = "", actor: Dict[str, Any]) -> Dict[str, Any]:
    if not (0 < float(cut_yard) <= 5):
        raise HTTPException(status_code=400, detail="Panjang potong MDQ harus > 0 dan ≤ 5 yard.")
    ins = await db.inspections.find_one({"id": ins_id}, {"_id": 0, "id": 1, "kind": 1, "lines": 1, "number": 1,
                                                          "entity_id": 1})
    if not ins:
        raise HTTPException(status_code=404, detail="Inspeksi tidak ditemukan.")
    full = await db.inspections.find_one({"id": ins_id}, {"_id": 0, "status": 1})
    if ins.get("kind") not in ("po_receipt", "makloon_output") or (full or {}).get("status") not in (
            "draft", "assigned", "in_progress"):
        raise HTTPException(status_code=409, detail="Potong uji MDQ hanya untuk inspeksi penerimaan/hasil makloon yang masih terbuka.")
    line = next((ln for ln in ins.get("lines") or [] if ln.get("id") == line_id), None)
    if not line or not line.get("roll_id"):
        raise HTTPException(status_code=404, detail="Baris inspeksi/roll tidak ditemukan.")
    key = f"{ins_id}:{line_id}"
    done = await db.mdq_cuts.find_one({"_id": key})
    if done and done.get("status") == "posted":
        return {**done, "_id": None, "replayed": True}
    if done and done.get("status") == "pending" and (done.get("at") or "") < _ago(60):
        applied = await db.inventory_rolls.count_documents({"id": done["roll_id"], "usage_history.ref": key})
        if applied:
            raise HTTPException(status_code=409, detail="Potong MDQ tercatat di roll tetapi belum dibukukan — hubungi admin untuk rekonsiliasi.")
        await db.mdq_cuts.delete_one({"_id": key, "status": "pending"})   # proses lama mati sebelum memotong
    roll = await db.inventory_rolls.find_one({"id": line["roll_id"]}, {"_id": 0})
    if not roll:
        raise HTTPException(status_code=404, detail="Roll tidak ditemukan.")
    unit = (roll.get("unit") or "").lower()
    if unit == "yard":
        qty = float(cut_yard)
    elif unit in ("meter", "m"):
        qty = round(float(cut_yard) * YARD_TO_METER, 4)
    elif unit == "kg":
        prod = await db.products.find_one({"id": roll["product_id"]}, {"_id": 0, "kg_per_yard_validated": 1})
        rule = (prod or {}).get("kg_per_yard_validated")
        if weight_kg is not None and float(weight_kg) > 0:
            qty, basis = float(weight_kg), "berat aktual ditimbang"
        elif rule:
            qty, basis = round(float(cut_yard) * float(rule), 4), f"aturan tervalidasi {rule} kg/yard"
        else:
            raise HTTPException(status_code=400, detail=(
                "Roll ini berbasis kg. Timbang potongan dan isi berat aktual (kg), atau minta MD menetapkan "
                "aturan kg/yard tervalidasi untuk produk ini. Stok kg TIDAK dikurangi dengan angka yard/GSM."))
    else:
        raise HTTPException(status_code=400, detail=f"Satuan roll '{unit}' belum didukung potong MDQ.")
    if unit != "kg":
        basis = f"{cut_yard} yard"
    doc = {"_id": key, "id": new_id("mdqc"), "inspection_id": ins_id, "line_id": line_id, "roll_id": roll["id"],
           "cut_yard": float(cut_yard), "qty": round(qty, 4), "unit": unit, "basis": basis,
           "weight_kg": weight_kg, "reason": (reason or "Potong uji MD Quality").strip()[:200],
           "status": "pending", "by": actor.get("name", ""), "at": now_iso()}
    try:
        await db.mdq_cuts.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Potong MDQ baris ini sedang/sudah diproses — muat ulang.")
    res = await db.inventory_rolls.update_one(
        {"id": roll["id"], "length_remaining": {"$gte": qty - 1e-9}, "status": {"$in": list(CUT_STATUSES)}},
        {"$inc": {"length_remaining": -qty},
         "$set": {"updated_at": now_iso()},
         "$push": {"usage_history": {"type": "mdq_cut", "qty": qty, "unit": unit, "ref": key, "at": now_iso()}}})
    if not res.modified_count:
        await db.mdq_cuts.delete_one({"_id": key, "status": "pending"})
        raise HTTPException(status_code=409, detail="Saldo/status roll tidak memungkinkan dipotong.")
    await db.inventory_movements.insert_one({
        "id": new_id("mov"), "product_id": roll["product_id"], "warehouse_id": roll["warehouse_id"],
        "owner_entity_id": roll.get("owner_entity_id"), "movement_type": "mdq_cut", "quantity": -round(qty, 4),
        "unit": unit, "lot": roll.get("lot", ""), "roll_id": roll["id"], "qty_rolls": None,
        "source_document": ins_id, "timestamp": now_iso()})
    await rebuild_balance(roll["product_id"], roll["warehouse_id"], roll.get("owner_entity_id"))
    value = round(qty * float(roll.get("base_unit_cost") or 0), 2)
    await gl.post_inventory_writeoff(roll_id=roll["id"], entity_id=roll.get("owner_entity_id") or ins.get("entity_id") or "",
                                     amount=value, reason="potong uji MD Quality (waste)",
                                     label=f"{ins.get('number') or ins_id} {roll.get('roll_no') or roll['id']}",
                                     source_id=f"mdq:{key}")
    await db.mdq_cuts.update_one({"_id": key}, {"$set": {"status": "posted", "value": value}})
    await db.inspections.update_one({"id": ins_id, "lines.id": line_id},
                                    {"$set": {"lines.$.mdq_cut": {"qty": round(qty, 4), "unit": unit, "basis": basis,
                                                                  "by": doc["by"], "at": doc["at"]}}})
    out = await db.mdq_cuts.find_one({"_id": key}, {"_id": 0})
    return {**out, "replayed": False}
