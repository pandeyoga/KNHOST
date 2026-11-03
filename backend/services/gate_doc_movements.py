"""Gate (P09) — dokumen keluar/masuk SELAIN putaway / transfer gudang / surat jalan SO: Order Makloon & Perbaikan.

Kasus klien: 20 roll Esmica Blue keluar gerbang menuju mitra celup. Roll itu berstatus `subcon` (bucket WIP-vendor,
`bucket_ref` menunjuk langkah MKO) — bukan `reserved_ref` — sehingga `gate_evaluator.resolve_movement` dulu tidak
menemukan dokumen apa pun dan gate OUT selalu MERAH `NO_DOCUMENT`, padahal pengirimannya sah. Hal yang sama untuk
roll yang dikirim ke Perbaikan (status `wip`, `repair_open` = RPR).

Movement yang dikembalikan berbentuk sama dengan movement lain (type/id/number/status/active/source_wh/dest_wh/
member) sehingga `evaluate` & `stamp_exit` memperlakukannya seragam. `id` movement:
  * makloon → `issue_ref` langkah (unik per langkah; keluar ulang roll yang sama untuk langkah yang sama =
    `REPLAY_EXIT`), `doc_id` = id MKO.
  * perbaikan → id RPR.
Tambahan: `cancelled` (dokumen dibatalkan → `DOC_CANCELLED`), `inactive_reason`, `return_wh` (gudang asal yang
sah untuk barang KEMBALI di gate IN), `returning` (barang memang dijadwalkan kembali).
"""
from typing import Any, Dict, Optional

from db import db

STEP_STATUS_LABEL = {"pending": "belum dikirim", "issued": "dikirim", "received": "sudah diterima",
                     "returned": "sudah diretur"}
RPR_STATUS_LABEL = {"draft": "Draf", "sent": "Dikirim", "done": "Selesai", "cancelled": "Dibatalkan"}


async def _makloon(roll: Dict[str, Any], br: Dict[str, Any]) -> Dict[str, Any]:
    order = await db.makloon_orders.find_one({"id": br["mko_id"]}, {"_id": 0, "id": 1, "mko_number": 1,
                                                                    "status": 1, "steps": 1})
    if not order:
        return {"type": "makloon_order", "id": br.get("id") or br["mko_id"], "missing": True}
    steps = order.get("steps") or []
    step = next((s for s in steps if s.get("issue_ref") == br.get("id")), None) \
        or next((s for s in steps if int(s.get("seq") or 0) == int(br.get("step") or 0)), None) or {}
    number = f"{order.get('mko_number') or order['id']} langkah {step.get('seq') or br.get('step') or '?'}"
    cancelled = order.get("status") == "cancelled"
    issued = step.get("status") == "issued" and roll.get("status") == "subcon"
    wh = step.get("from_warehouse_id") or roll.get("warehouse_id")
    return {"type": "makloon_order", "id": br.get("id") or order["id"], "doc_id": order["id"], "number": number,
            "status": step.get("status"), "active": issued and not cancelled, "cancelled": cancelled,
            "inactive_reason": (f"{number} {STEP_STATUS_LABEL.get(step.get('status'), step.get('status') or '-')} — "
                                "bukan pengiriman bahan yang aktif; tahan.") if not issued else "",
            "source_wh": wh, "dest_wh": None, "return_wh": wh,
            "returning": cancelled and issued and bool(step.get("awaiting_return")),
            "partner": step.get("makloon_name") or br.get("makloon_name") or "", "member": True}


async def _repair(roll: Dict[str, Any]) -> Dict[str, Any]:
    ro = await db.repair_orders.find_one({"id": roll["repair_open"]}, {"_id": 0, "id": 1, "number": 1, "status": 1,
                                                                        "lines": 1, "partner_name": 1})
    if not ro:
        return {"type": "repair_order", "id": roll["repair_open"], "missing": True}
    line = next((ln for ln in ro.get("lines") or [] if ln.get("roll_id") == roll.get("id")), None)
    wh = (line or {}).get("warehouse_id") or roll.get("warehouse_id")
    sent = ro.get("status") == "sent" and roll.get("status") == "wip"
    number = ro.get("number") or ro["id"]
    return {"type": "repair_order", "id": ro["id"], "doc_id": ro["id"], "number": number, "status": ro.get("status"),
            "active": sent, "cancelled": ro.get("status") == "cancelled",
            "inactive_reason": (f"Perbaikan {number} berstatus {RPR_STATUS_LABEL.get(ro.get('status'), ro.get('status'))} "
                                "— roll bukan kiriman perbaikan yang aktif; tahan.") if not sent else "",
            "source_wh": wh, "dest_wh": None, "return_wh": wh, "returning": sent,
            "partner": ro.get("partner_name") or "", "member": bool(line)}


async def doc_movement(roll: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Movement makloon/perbaikan yang memuat roll; None bila roll tidak dipegang dokumen itu."""
    br = roll.get("bucket_ref") or {}
    if roll.get("status") == "subcon" and isinstance(br, dict) and br.get("type") == "subcon" and br.get("mko_id"):
        return await _makloon(roll, br)
    if roll.get("repair_open"):
        return await _repair(roll)
    return None


def evaluate_in(mv: Dict[str, Any], warehouse_id: Optional[str]) -> Optional[tuple]:
    """Gate IN untuk barang yang KEMBALI: (result, code, reason) atau None (pakai aturan umum)."""
    if not mv.get("returning"):
        return None
    if mv.get("return_wh") != warehouse_id:
        return ("red", "WRONG_DESTINATION",
                f"SALAH GUDANG — {mv.get('number')} seharusnya kembali ke gudang asalnya, bukan gudang ini.")
    if mv["type"] == "repair_order":
        return ("green", "MOVEMENT_IN", f"Kembali dari perbaikan {mv.get('number')}"
                + (f" ({mv['partner']})" if mv.get("partner") else "")
                + " — terima, lalu catat hasilnya di dokumen Perbaikan.")
    return ("green", "MOVEMENT_IN", f"Bahan kembali dari mitra makloon ({mv.get('number')}, order DIBATALKAN) — "
                                    "terima, lalu catat Retur Bahan di Order Makloon.")
