"""L08 LN-081 — perjalanan fisik barang retur per roll (terima → kirim/dalam perjalanan → tiba),
terpisah dari izin, QC, disposisi stok dan penyelesaian uang. Lokasi berubah hanya lewat scan
berdokumen; tidak ada tombol "ubah gudang" instan."""
from typing import Any, Dict, List, Optional

from core_utils import new_id, now_iso
from db import db

STAGE_LABEL = {"received": "Diterima di gudang", "dispatched": "Dikirim · dalam perjalanan",
               "arrived": "Tiba di gudang tujuan"}
DOC_PREFIX = {"received": "TRM", "dispatched": "SJ", "arrived": "TBA"}
OPEN_STATES = {"pending_approval", "approved", "inspecting", "inspected"}
QC_ROLES = {"return", "qc"}


class JourneyConflict(Exception):
    pass


def _claimed_rolls(ret: Dict[str, Any]) -> List[str]:
    return [r for it in ret.get("items", []) for r in (it.get("roll_ids") or [])]


async def _resolve_codes(ret: Dict[str, Any], codes: List[str]) -> List[str]:
    """Kode hasil scan → roll_id milik retur ini (id, nomor roll, atau tag RFID/EPC)."""
    claimed = _claimed_rolls(ret)
    rolls = await db.inventory_rolls.find({"id": {"$in": claimed}},
                                          {"_id": 0, "id": 1, "roll_no": 1, "rfid_tag_id": 1}).to_list(500)
    index: Dict[str, str] = {}
    for r in rolls:
        for k in (r["id"], r.get("roll_no"), r.get("rfid_tag_id")):
            if k:
                index[str(k).strip().upper()] = r["id"]
    tags = await db.rfid_tags.find({"roll_id": {"$in": claimed}}, {"_id": 0, "roll_id": 1, "epc": 1, "id": 1}).to_list(500)
    for t in tags:
        for k in (t.get("epc"), t.get("id")):
            if k:
                index[str(k).strip().upper()] = t["roll_id"]
    out, unknown = [], []
    for c in codes:
        rid = index.get(str(c or "").strip().upper())
        (out if rid else unknown).append(rid or c)
    if unknown:
        raise ValueError(f"Kode tidak termasuk roll retur ini: {', '.join(map(str, unknown))}.")
    return list(dict.fromkeys(out))


async def _wh(wid: str) -> Dict[str, Any]:
    w = await db.warehouses.find_one({"id": wid}, {"_id": 0, "id": 1, "name": 1, "roles": 1})
    if not w:
        raise ValueError("Gudang tidak ditemukan.")
    return w


def _transition(stage: str, cur: Optional[Dict[str, Any]], wid: str, to_wid: str, no: str) -> None:
    where = (cur or {}).get("stage")
    if stage == "received" and where is not None:
        raise ValueError(f"Roll {no} sudah diterima ({STAGE_LABEL.get(where, where)}). "
                         "Pindah gudang dilakukan lewat scan kirim → tiba.")
    if stage == "dispatched":
        if where not in ("received", "arrived"):
            raise ValueError(f"Roll {no} belum berada di gudang (scan terima dulu).")
        if to_wid == cur.get("warehouse_id"):
            raise ValueError(f"Gudang tujuan roll {no} sama dengan lokasinya sekarang.")
    if stage == "arrived":
        if where != "in_transit":
            raise ValueError(f"Roll {no} tidak sedang dalam perjalanan.")
        if wid != cur.get("to_warehouse_id"):
            raise ValueError(f"Roll {no} dikirim ke {cur.get('to_warehouse_name')}, bukan ke gudang ini.")


async def scan(return_id: str, stage: str, codes: List[str], warehouse_id: str, actor: str,
               to_warehouse_id: str = "", carrier: str = "", note: str = "") -> Dict[str, Any]:
    if stage not in STAGE_LABEL:
        raise ValueError(f"Tahap scan tidak dikenal: {stage}.")
    ret = await db.sales_returns.find_one({"id": return_id}, {"_id": 0})
    if not ret:
        raise LookupError("Retur tidak ditemukan")
    if ret.get("status") not in OPEN_STATES:
        raise ValueError("Scan perjalanan hanya untuk retur yang sudah diajukan dan belum diselesaikan. "
                         "Sesudah penyelesaian, pindahkan roll lewat Transfer Gudang.")
    if not codes:
        raise ValueError("Scan minimal satu roll.")
    rids = await _resolve_codes(ret, codes)
    wh = await _wh(warehouse_id)
    to = await _wh(to_warehouse_id) if stage == "dispatched" else None
    locs = dict(ret.get("roll_locations") or {})
    nos = {r["id"]: r.get("roll_no") or r["id"] async for r in db.inventory_rolls.find(
        {"id": {"$in": rids}}, {"_id": 0, "id": 1, "roll_no": 1})}
    for rid in rids:
        _transition(stage, locs.get(rid), warehouse_id, to_warehouse_id, nos.get(rid, rid))
    rev = int(ret.get("journey_rev") or 0)
    n = sum(1 for e in (ret.get("journey_events") or []) if e.get("stage") == stage) + 1
    now = now_iso()
    doc_no = f"{ret.get('number', return_id)}/{DOC_PREFIX[stage]}-{n}"
    event = {"id": new_id("rjev"), "stage": stage, "label": STAGE_LABEL[stage], "doc_no": doc_no,
             "roll_ids": rids, "roll_nos": [nos.get(r, r) for r in rids],
             "warehouse_id": warehouse_id, "warehouse_name": wh.get("name", ""),
             "to_warehouse_id": to_warehouse_id if to else "", "to_warehouse_name": (to or {}).get("name", ""),
             "carrier": (carrier or "").strip(), "note": (note or "").strip(), "by": actor, "at": now}
    for rid in rids:
        if stage == "dispatched":
            locs[rid] = {"stage": "in_transit", "from_warehouse_id": warehouse_id,
                         "from_warehouse_name": wh.get("name", ""), "to_warehouse_id": to_warehouse_id,
                         "to_warehouse_name": to.get("name", ""), "doc_no": doc_no, "at": now}
        else:
            locs[rid] = {"stage": stage, "warehouse_id": warehouse_id, "warehouse_name": wh.get("name", ""),
                         "is_qc_area": bool(QC_ROLES & set(wh.get("roles") or [])), "doc_no": doc_no, "at": now}
    upd: Dict[str, Any] = {"roll_locations": locs, "updated_at": now}
    if stage in ("received", "arrived") and not ret.get("goods_arrived_at"):
        upd["goods_arrived_at"] = now
    res = await db.sales_returns.find_one_and_update(
        {"id": return_id, "status": ret["status"],
         "journey_rev": ret.get("journey_rev") if "journey_rev" in ret else {"$exists": False}},
        {"$set": {**upd, "journey_rev": rev + 1}, "$push": {"journey_events": event}},
        projection={"_id": 0}, return_document=True)
    if not res:
        raise JourneyConflict("Retur ini baru saja discan oleh pengguna lain. Muat ulang lalu ulangi scan.")
    return {"event": event, "roll_locations": res.get("roll_locations", {})}


def assert_ready_for_qc(ret: Dict[str, Any]) -> None:
    """QC tidak boleh mendahului barang: bila perjalanan sudah discan, semua roll harus di gudang."""
    locs = ret.get("roll_locations") or {}
    if not locs:
        return
    bad = [rid for rid in _claimed_rolls(ret) if (locs.get(rid) or {}).get("stage") in (None, "in_transit")]
    if bad:
        raise ValueError(f"{len(bad)} roll belum berada di gudang (belum diterima atau masih dalam perjalanan). "
                         "Scan terima/tiba dulu sebelum QC.")


def physical_warehouse(ret: Dict[str, Any], roll_id: str) -> str:
    loc = (ret.get("roll_locations") or {}).get(roll_id) or {}
    return loc.get("warehouse_id", "") if loc.get("stage") in ("received", "arrived") else ""


def assert_settle_location(ret: Dict[str, Any], requested_wh: str) -> None:
    """Penyelesaian memasukkan stok di lokasi FISIK hasil scan, bukan gudang pilihan bebas."""
    locs = ret.get("roll_locations") or {}
    if not locs:
        return
    assert_ready_for_qc(ret)
    whs = {physical_warehouse(ret, r) for r in _claimed_rolls(ret)}
    if requested_wh and whs != {requested_wh}:
        raise ValueError("Gudang penerimaan mengikuti lokasi fisik hasil scan. Untuk memindah barang, "
                         "scan kirim → tiba di gudang tujuan (tidak bisa lewat pilihan gudang).")
