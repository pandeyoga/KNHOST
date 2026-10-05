"""QC-06 — Tahan (HOLD) & Lepas (RELEASE) manual satu roll.

HOLD: roll `available`/`quarantine` → `blocked` (bucket blocked_qty: fisik di gudang,
tidak masuk ATP, tidak bisa dialokasikan/dijual, keputusan QC task-nya tertahan).
RELEASE: `blocked` → status sebelum ditahan. Juga melepas tahanan inspeksi
(`inspection.hold.held`, selisih warna/handfeel) yang dibaca pagar putaway.
Semua perubahan di level roll + rebuild_balance (SSOT) + `hold_history` untuk jejak.
"""
from typing import Any, Dict
from db import db
from core_utils import now_iso, safe_doc
from services.roll_service import rebuild_balance

HOLDABLE_STATUSES = ("available", "quarantine")
HOLD_STATUS = "blocked"


def _entry(action: str, reason: str, actor: Dict[str, Any], status_from: str, status_to: str) -> Dict[str, Any]:
    return {"action": action, "reason": reason, "by": actor.get("name", ""), "by_id": actor.get("id", ""),
            "at": now_iso(), "status_from": status_from, "status_to": status_to}


async def hold_roll(roll: Dict[str, Any], reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise ValueError("Alasan tahan wajib diisi (min. 3 karakter).")
    status = roll.get("status")
    if status not in HOLDABLE_STATUSES:
        raise ValueError(f"Roll berstatus '{status}' tidak dapat ditahan (hanya Tersedia/Karantina).")
    if roll.get("earmarked_for"):
        raise ValueError("Roll sedang di-peg untuk pelanggan — lepas peg dulu sebelum ditahan.")
    now = now_iso()
    hold = {"held": True, "reason": reason, "by": actor.get("name", ""), "at": now, "prev_status": status}
    res = await db.inventory_rolls.update_one(
        {"id": roll["id"], "status": status},
        {"$set": {"status": HOLD_STATUS, "hold": hold, "updated_at": now},
         "$push": {"hold_history": _entry("hold", reason, actor, status, HOLD_STATUS)}})
    if not res.modified_count:
        raise ValueError("Status roll berubah bersamaan — muat ulang lalu coba lagi.")
    await rebuild_balance(roll["product_id"], roll["warehouse_id"], roll.get("owner_entity_id"))
    return safe_doc(await db.inventory_rolls.find_one({"id": roll["id"]}, {"_id": 0}))


async def release_roll(roll: Dict[str, Any], note: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    note = (note or "").strip()
    if len(note) < 3:
        raise ValueError("Catatan pelepasan wajib diisi (min. 3 karakter).")
    insp_hold = ((roll.get("inspection") or {}).get("hold") or {})
    now = now_iso()
    if roll.get("status") == HOLD_STATUS and (roll.get("hold") or {}).get("held"):
        prev = roll["hold"].get("prev_status") or "available"
        upd = {"$set": {"status": prev, "hold": {**roll["hold"], "held": False, "released_by": actor.get("name", ""),
                                                 "released_at": now, "release_note": note},
                        "updated_at": now},
               "$push": {"hold_history": _entry("release", note, actor, HOLD_STATUS, prev)}}
        if insp_hold.get("held"):
            upd["$set"]["inspection.hold.held"] = False
        res = await db.inventory_rolls.update_one({"id": roll["id"], "status": HOLD_STATUS}, upd)
        if not res.modified_count:
            raise ValueError("Status roll berubah bersamaan — muat ulang lalu coba lagi.")
        await rebuild_balance(roll["product_id"], roll["warehouse_id"], roll.get("owner_entity_id"))
    elif insp_hold.get("held"):
        st = roll.get("status", "")
        await db.inventory_rolls.update_one(
            {"id": roll["id"]},
            {"$set": {"inspection.hold.held": False, "inspection.hold.released_by": actor.get("name", ""),
                      "inspection.hold.released_at": now, "updated_at": now},
             "$push": {"hold_history": _entry("release_inspection_hold", note, actor, st, st)}})
    else:
        raise ValueError("Roll tidak sedang ditahan.")
    return safe_doc(await db.inventory_rolls.find_one({"id": roll["id"]}, {"_id": 0}))


async def held_rolls_for_task(task_id: str) -> list:
    return await db.inventory_rolls.find({"qc_task_id": task_id, "status": HOLD_STATUS},
                                         {"_id": 0, "id": 1, "roll_no": 1}).to_list(None)
