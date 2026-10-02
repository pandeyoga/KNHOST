"""P09 — SATU evaluator gate (ingest perangkat, simulator, kiosk). Keputusan berbasis MOVEMENT aktif
(PA / transfer gudang / surat jalan SO) yang memuat roll, bukan status roll semata.

Hasil: {result green|red|info, code, reason, movement?}. Tidak ada fallback hijau: dokumen hilang,
status tidak aktif, gudang salah, roll bukan anggota manifest, atau keluar ulang → MERAH + kode.
"""
from typing import Any, Dict, Optional

from db import db

SHIPMENT_ACTIVE = {"dispatched", "in_transit", "partially_shipped"}
SO_DEAD = {"cancelled", "void", "rejected"}


# Saran tindakan untuk satpam per kode alasan (bahasa lapangan, satu kalimat).
ACTIONS = {
    "MOVEMENT_OUT": "Loloskan — cocokkan jumlah roll dengan surat jalan.",
    "MOVEMENT_IN": "Terima — arahkan ke area bongkar/putaway.",
    "LOCAL_ROLL": "Tidak perlu tindakan — roll milik gudang ini.",
    "INVENTORY": "Tidak perlu tindakan.",
    "NO_DOCUMENT": "Tahan barang — minta surat jalan / dokumen keluar ke admin gudang.",
    "DOC_MISSING": "Tahan barang — panggil supervisor, dokumen di sistem tidak ditemukan.",
    "NOT_RELEASED": "Tahan barang — minta admin gudang menyelesaikan dispatch di sistem dulu.",
    "NOT_IN_MANIFEST": "Tahan roll ini — tidak ada di surat jalan; cocokkan ulang muatan dengan checker.",
    "WRONG_WAREHOUSE": "Tahan barang — dokumen untuk gudang lain; panggil supervisor.",
    "WRONG_DESTINATION": "Tolak bongkar — barang untuk gudang lain; hubungi pengirim/supervisor.",
    "MOVEMENT_NOT_ACTIVE": "Tahan — dokumen belum dikirim di sistem; hubungi admin gudang asal.",
    "SO_CANCELLED": "Tahan barang — pesanan dibatalkan; kembalikan ke gudang & lapor supervisor.",
    "ALREADY_OUT": "Tahan & panggil supervisor — roll tercatat sudah keluar/habis.",
    "REPLAY_EXIT": "Tahan & panggil supervisor — roll sudah pernah keluar dengan dokumen ini.",
    "QUARANTINE": "Tahan barang — roll karantina QC; kembalikan ke area karantina.",
    "SALES_TRANSIT_NOT_INBOUND": "Tolak bongkar — barang kiriman pelanggan; minta dokumen retur.",
    "UNKNOWN_EPC": "Tahan barang — tag tidak dikenal; panggil supervisor untuk cek fisik.",
}


def action_for(code: Optional[str]) -> str:
    return ACTIONS.get(code or "", "Tahan & panggil supervisor.")


def _v(result: str, code: str, reason: str, mv: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out = {"result": result, "code": code, "reason": reason, "action": action_for(code)}
    if mv:
        out["movement"] = {k: mv.get(k) for k in ("type", "id", "number", "source_wh", "dest_wh")}
    return out


async def resolve_movement(roll: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Movement aktif yang memuat roll: {type, id, number, status, active, source_wh, dest_wh, member}."""
    am = roll.get("active_movement") or {}
    pa_id = am.get("id") if am.get("type") == "putaway" else (roll.get("journey") or {}).get("putaway_order_id")
    if pa_id:
        pa = await db.putaway_orders.find_one({"id": pa_id}, {"_id": 0, "pa_number": 1, "status": 1,
                                                              "from_warehouse_id": 1, "to_warehouse_id": 1, "items.roll_id": 1})
        if pa and pa.get("status") in ("open", "in_transit"):
            return {"type": "putaway", "id": pa_id, "number": pa.get("pa_number"), "status": pa["status"],
                    "active": pa["status"] == "in_transit", "source_wh": pa.get("from_warehouse_id"),
                    "dest_wh": pa.get("to_warehouse_id"),
                    "member": roll["id"] in {i.get("roll_id") for i in pa.get("items") or []}}
    ref = roll.get("reserved_ref") or {}
    if not isinstance(ref, dict) or not ref.get("id"):
        return None
    if ref.get("type") == "wh_transfer":
        tr = await db.warehouse_transfers.find_one({"id": ref["id"]}, {"_id": 0, "code": 1, "status": 1,
                                                                       "source_warehouse_id": 1, "dest_warehouse_id": 1})
        if not tr:
            return {"type": "wh_transfer", "id": ref["id"], "missing": True}
        return {"type": "wh_transfer", "id": ref["id"], "number": tr.get("code"), "status": tr.get("status"),
                "active": tr.get("status") == "dispatched" and roll.get("status") == "in_transit_transfer",
                "source_wh": tr.get("source_warehouse_id"), "dest_wh": tr.get("dest_warehouse_id"), "member": True}
    if ref.get("type") == "sales_order":
        so = await db.sales_orders.find_one({"id": ref["id"]}, {"_id": 0, "number": 1, "status": 1})
        if not so:
            return {"type": "sales_order", "id": ref["id"], "missing": True}
        shp = await db.shipments.find_one({"order_id": ref["id"], "rolls.roll_id": roll["id"]},
                                          {"_id": 0, "id": 1, "shipment_no": 1, "status": 1, "warehouse_id": 1},
                                          sort=[("created_at", -1)])
        return {"type": "sales_order", "id": ref["id"], "number": so.get("number"), "status": so.get("status"),
                "so_dead": so.get("status") in SO_DEAD, "shipment": shp,
                "active": bool(shp and shp.get("status") in SHIPMENT_ACTIVE and roll.get("status") == "in_transit_sales"),
                "source_wh": (shp or {}).get("warehouse_id") or roll.get("warehouse_id"), "dest_wh": None,
                "member": bool(shp)}
    return None


async def evaluate(direction: str, warehouse_id: Optional[str], roll: Dict[str, Any]) -> Dict[str, Any]:
    status = roll.get("status", "?")
    mv = await resolve_movement(roll)
    if mv and mv.get("missing"):
        return _v("red", "DOC_MISSING", f"Dokumen {mv['type']} {mv['id']} tidak ditemukan — exception, cek manual.")
    if direction == "in":
        if status == "in_transit_sales":
            return _v("red", "SALES_TRANSIT_NOT_INBOUND", "Roll dalam pengiriman penjualan — bukan transfer internal ke gudang ini.", mv)
        if mv and mv["type"] in ("putaway", "wh_transfer"):
            if mv.get("dest_wh") != warehouse_id:
                return _v("red", "WRONG_DESTINATION", f"SALAH GUDANG — {mv.get('number')} menuju gudang lain, bukan gudang ini.", mv)
            if not mv.get("active") or not mv.get("member"):
                return _v("red", "MOVEMENT_NOT_ACTIVE", f"{mv.get('number')} belum dikirim / roll bukan anggota dokumen.", mv)
            return _v("green", "MOVEMENT_IN", f"Sesuai {mv.get('number')} — tujuan gudang ini.", mv)
        if status == "in_transit_transfer":
            return _v("red", "DOC_MISSING", "Roll transit tanpa dokumen tujuan yang aktif — exception.")
        if roll.get("warehouse_id") == warehouse_id:
            return _v("info", "LOCAL_ROLL", "Roll milik gudang ini terbaca di gate masuk.")
        return _v("red", "NO_DOCUMENT", "Tidak ada dokumen tujuan (PA/transfer) ke gudang ini.")

    # OUT
    if status == "quarantine":
        return _v("red", "QUARANTINE", "Roll KARANTINA (QC hold) — dilarang keluar.")
    if status in ("delivered", "consumed"):
        return _v("red", "ALREADY_OUT", f"Roll berstatus {status} — tidak boleh keluar lagi.")
    passed = roll.get("gate_exit") or {}
    if mv and passed.get("movement_id") == mv.get("id"):
        return _v("red", "REPLAY_EXIT", f"Roll sudah keluar untuk {mv.get('number')} ({passed.get('at')}) — keluar ulang ditahan.", mv)
    if not mv:
        if status == "available":
            return _v("red", "NO_DOCUMENT", "Roll masih AVAILABLE — tidak ada dokumen keluar (SO/transfer/PA). Keluar tak sah.")
        return _v("red", "NO_DOCUMENT", f"Status {status} tanpa dokumen keluar aktif — keluar tak sah.")
    if mv["type"] == "sales_order" and mv.get("so_dead"):
        return _v("red", "SO_CANCELLED", f"SO {mv.get('number')} berstatus {mv.get('status')} — keluar ditahan.", mv)
    if mv.get("source_wh") != warehouse_id:
        return _v("red", "WRONG_WAREHOUSE", f"{mv.get('number')} berangkat dari gudang lain, bukan gudang ini.", mv)
    if not mv.get("member"):
        return _v("red", "NOT_IN_MANIFEST", f"Roll tidak tercantum di surat jalan/dokumen {mv.get('number')}.", mv)
    if not mv.get("active"):
        return _v("red", "NOT_RELEASED", f"{mv.get('number')} belum di-dispatch di sistem (status {status}) — tahan.", mv)
    return _v("green", "MOVEMENT_OUT", f"Keluar ter-otorisasi untuk {mv.get('number')}.", mv)


async def stamp_exit(roll_id: str, decision: Dict[str, Any], device: Dict[str, Any], at: str) -> None:
    """Gate-out hijau dicatat di roll → pembacaan keluar berikutnya untuk movement yang sama = REPLAY_EXIT."""
    mv = decision.get("movement") or {}
    if decision.get("result") == "green" and decision.get("code") == "MOVEMENT_OUT" and mv.get("id"):
        await db.inventory_rolls.update_one({"id": roll_id}, {"$set": {"gate_exit": {
            "movement_id": mv["id"], "device_id": device["id"], "at": at}}})
