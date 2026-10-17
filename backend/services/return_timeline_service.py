"""L08 LN-081 — satu timeline kasus retur dengan jalur terpisah: izin · perjalanan masuk ·
QC per roll · disposisi stok · penyelesaian uang · pengiriman pengganti (jalur keluar, tidak
dicampur dengan kedatangan retur). Ringkasan qty dipisah per satuan; uang memakai basis nilai."""
from typing import Any, Dict, List

from db import db

LANES = {
    "approval": "Pengajuan & izin",
    "inbound": "Perjalanan masuk",
    "qc": "QC per roll",
    "disposition": "Disposisi stok",
    "settlement": "Penyelesaian uang",
    "replacement": "Pengiriman pengganti",
}
OUTCOME_LABEL = {"refund": "Refund", "store_credit": "Store credit", "nego": "Nego (diskon)", "reject": "Ditolak"}
ROLL_STATUS_LABEL = {"quarantine": "Karantina", "available": "Tersedia", "scrapped": "Dibuang/BS",
                     "delivered": "Di pelanggan", "reserved": "Dipesan"}


def _ev(lane: str, at: str, title: str, by: str = "", detail: str = "", doc_no: str = "") -> Dict[str, Any]:
    return {"lane": lane, "at": at or "", "title": title, "by": by or "", "detail": detail, "doc_no": doc_no}


def _approval_events(ret: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = [_ev("approval", ret.get("created_at"), "Retur dibuat", ret.get("created_by"),
               doc_no=ret.get("number", ""))]
    if ret.get("submitted_at"):
        out.append(_ev("approval", ret["submitted_at"], "Diajukan untuk persetujuan", ret.get("submitted_by")))
    if ret.get("approved_at"):
        out.append(_ev("approval", ret["approved_at"], "Disetujui (izin retur)", ret.get("approved_by")))
    if ret.get("rejected_at"):
        out.append(_ev("approval", ret["rejected_at"], "Ditolak", ret.get("rejected_by"), ret.get("reject_reason", "")))
    return out


def _inbound_events(ret: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for m in ret.get("milestones") or []:
        if m.get("milestone") in ("shipped_to_store", "goods_arrived"):
            out.append(_ev("inbound", m.get("at"), m.get("label", ""), m.get("by"), m.get("note", "")))
    for e in ret.get("journey_events") or []:
        where = (f"{e.get('warehouse_name')} → {e.get('to_warehouse_name')}" if e["stage"] == "dispatched"
                 else e.get("warehouse_name", ""))
        extra = " · ".join(x for x in (where, f"{len(e.get('roll_ids') or [])} roll",
                                         e.get("carrier", ""), e.get("note", "")) if x)
        out.append(_ev("inbound", e.get("at"), e.get("label", ""), e.get("by"), extra, e.get("doc_no", "")))
    return out


def _replacement_events(ret: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [_ev("replacement", m.get("at"), m.get("label", "Kirim ke pelanggan"), m.get("by"), m.get("note", ""))
            for m in ret.get("milestones") or [] if m.get("milestone") == "shipped_to_customer"]


def _location_text(loc: Dict[str, Any]) -> str:
    if not loc:
        return "Di pelanggan (belum diterima)"
    if loc.get("stage") == "in_transit":
        return f"Dalam perjalanan {loc.get('from_warehouse_name')} → {loc.get('to_warehouse_name')}"
    return ("Area QC · " if loc.get("is_qc_area") else "") + (loc.get("warehouse_name") or "")


async def _roll_rows(ret: Dict[str, Any]) -> List[Dict[str, Any]]:
    ids = [r for it in ret.get("items", []) for r in (it.get("roll_ids") or [])]
    docs = {r["id"]: r async for r in db.inventory_rolls.find(
        {"$or": [{"id": {"$in": ids}}, {"return_id": ret["id"]}]}, {"_id": 0})}
    whs = {w["id"]: w.get("name", "") async for w in db.warehouses.find({}, {"_id": 0, "id": 1, "name": 1})}
    locs = ret.get("roll_locations") or {}
    rows = []
    for it in ret.get("items", []):
        insp = it.get("inspection") or {}
        actuals = insp.get("roll_actuals") or {}
        for rid in it.get("roll_ids") or []:
            orig = docs.get(rid, {})
            # Disposisi: roll asli yang diaktifkan lagi, atau child potongan retur dari roll ini.
            disp = orig if orig.get("return_id") == ret["id"] else next(
                (d for d in docs.values() if d.get("return_id") == ret["id"] and d.get("parent_roll_id") == rid), {})
            claimed = float((it.get("roll_qtys") or {}).get(rid) or 0)
            rows.append({
                "roll_id": rid, "roll_no": orig.get("roll_no", rid), "product_name": it.get("product_name", ""),
                "unit": it.get("unit") or orig.get("unit", ""), "qty_claimed": round(claimed, 2),
                "location": _location_text(locs.get(rid) or {}), "location_stage": (locs.get(rid) or {}).get("stage", ""),
                "location_doc": (locs.get(rid) or {}).get("doc_no", ""),
                "qc_done": bool(insp), "qc_grade": insp.get("grade", ""),
                "qc_actual": (round(float(actuals[rid]), 2) if rid in actuals
                              else (round(claimed, 2) if insp else None)),
                "qc_disposition": insp.get("disposition", ""),
                "stock_roll_no": disp.get("roll_no", ""),
                "stock_status": ROLL_STATUS_LABEL.get(disp.get("status"), disp.get("status", "")),
                "stock_warehouse": whs.get(disp.get("warehouse_id"), ""),
            })
    return rows


def _summary(ret: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_unit: Dict[str, Dict[str, float]] = {}
    for it in ret.get("items", []):
        u = it.get("unit") or "-"
        g = by_unit.setdefault(u, {"unit": u, "claimed": 0.0, "accepted": 0.0, "settled": 0.0, "rolls": 0})
        g["claimed"] = round(g["claimed"] + float(it.get("quantity_returned") or 0), 2)
        insp = it.get("inspection") or {}
        if insp:
            acc = insp.get("accepted_qty")
            g["accepted"] = round(g["accepted"] + float(it.get("quantity_returned") if acc in (None, -1) else acc), 2)
        g["settled"] = round(g["settled"] + float(it.get("settled_qty") or 0), 2)
        g["rolls"] += len(it.get("roll_ids") or [])
    return {"per_unit": list(by_unit.values()),
            "value_basis": "Rupiah dari harga SO × qty per baris (bukan menjumlah satuan berbeda)"}


async def _settlement_events(ret: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    if ret.get("settled_at"):
        cn = await db.credit_notes.find_one({"id": ret.get("credit_note_id")}, {"_id": 0}) if ret.get("credit_note_id") else None
        amt = float((cn or {}).get("gross_amount") or 0)
        detail = OUTCOME_LABEL.get(ret.get("outcome"), ret.get("outcome", ""))
        if cn:
            detail += f" · Nota Kredit Rp {amt:,.0f}".replace(",", ".")
        dec = ret.get("decision") or {}
        if dec.get("note"):
            detail += f" · Bukti keputusan: {dec['note']}"
        out.append(_ev("settlement", ret["settled_at"], "Diselesaikan", ret.get("settled_by"), detail,
                       ret.get("credit_note_number", "")))
    if ret.get("reversed_at"):
        out.append(_ev("settlement", ret["reversed_at"], "Penyelesaian dibalik", ret.get("reversed_by"),
                       ret.get("reversal_reason", "")))
    return out


async def timeline(ret: Dict[str, Any]) -> Dict[str, Any]:
    rows = await _roll_rows(ret)
    events = _approval_events(ret) + _inbound_events(ret) + _replacement_events(ret)
    if ret.get("inspected_at"):
        events.append(_ev("qc", ret["inspected_at"], "QC selesai", ret.get("inspected_by"),
                          f"{sum(1 for r in rows if r['qc_done'])} roll diperiksa",
                          ret.get("inspection_number", "")))
    for r in rows:
        if r["stock_roll_no"] and ret.get("settled_at"):
            events.append(_ev("disposition", ret["settled_at"], f"Roll {r['stock_roll_no']} masuk stok",
                              ret.get("settled_by"), f"{r['stock_status']} · {r['stock_warehouse']}"))
    if ret.get("quarantine_released_at"):
        events.append(_ev("disposition", ret["quarantine_released_at"], "Karantina dilepas",
                          ret.get("quarantine_released_by"), ret.get("quarantine_release_notes", "")))
    events += await _settlement_events(ret)
    events.sort(key=lambda e: e["at"] or "")
    return {"lanes": LANES, "events": events, "rolls": rows, "summary": _summary(ret, rows),
            "status": ret.get("status")}
