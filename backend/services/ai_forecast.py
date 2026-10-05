"""Tanya KN — perkiraan: kebutuhan stok 4–8 minggu + saran reorder, risiko pelanggan berhenti order."""
from __future__ import annotations

import statistics
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from db import db
from services.analytics_time import now_wib

WEEKS_HISTORY = 12
OPEN_PO = ["pending", "approved", "receiving", "partially_received", "sent", "waiting_approval"]
_QTY = {"$multiply": ["$qty_base", {"$ifNull": ["$split", 1]}]}


async def _incoming(entity_ids: List[str]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    async for po in db.purchase_orders.find({"entity_id": {"$in": entity_ids}, "status": {"$in": OPEN_PO}},
                                            {"_id": 0, "items": 1}):
        for it in po.get("items") or []:
            rem = float(it.get("quantity") or 0) - float(it.get("received_qty") or 0)
            if rem > 0:
                out[it["product_id"]] = out.get(it["product_id"], 0.0) + rem
    return out


async def _first_supplier(product_ids: List[str]) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    async for si in db.supplier_items.find({"product_id": {"$in": product_ids}}, {"_id": 0, "product_id": 1, "supplier_id": 1}):
        out.setdefault(si["product_id"], {"supplier_id": si.get("supplier_id") or ""})
    names = {s["id"]: s.get("name", "") async for s in db.suppliers.find(
        {"id": {"$in": [v["supplier_id"] for v in out.values()]}}, {"_id": 0, "id": 1, "name": 1})}
    for v in out.values():
        v["supplier"] = names.get(v["supplier_id"], "")
    return out


async def demand_rows(entity_ids: List[str], line_q: Dict[str, Any], horizon_weeks: int = 6,
                      product_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Rata-rata mingguan 12 minggu (bobot 60% ke 4 minggu terakhir) → perkiraan & saran pesan ulang."""
    horizon_weeks = max(1, min(int(horizon_weeks or 6), 12))
    today = now_wib().date()
    start, recent = (today - timedelta(weeks=WEEKS_HISTORY)).isoformat(), (today - timedelta(weeks=4)).isoformat()
    match: Dict[str, Any] = {"entity_id": {"$in": entity_ids}, "is_live": True, "is_sample": False,
                             "date_wib": {"$gte": start}, **line_q}
    if product_ids:
        match["product_id"] = {"$in": product_ids}
    agg = [r async for r in db.fact_sales_lines.aggregate([
        {"$match": match},
        {"$group": {"_id": "$product_id", "name": {"$first": "$product_name"}, "unit": {"$first": "$base_unit"},
                    "qty": {"$sum": _QTY},
                    "recent": {"$sum": {"$cond": [{"$gte": ["$date_wib", recent]}, _QTY, 0]}}}}])]
    if not agg:
        return []
    pids = [a["_id"] for a in agg]
    avail = {b["_id"]: b["v"] async for b in db.inventory_balances.aggregate([
        {"$match": {"owner_entity_id": {"$in": entity_ids}, "product_id": {"$in": pids}}},
        {"$group": {"_id": "$product_id", "v": {"$sum": "$available_qty"}}}])}
    incoming, sup = await _incoming(entity_ids), await _first_supplier(pids)
    rows = []
    for a in agg:
        base_w, rec_w = a["qty"] / WEEKS_HISTORY, a["recent"] / 4
        weekly = 0.6 * rec_w + 0.4 * base_w
        if weekly <= 0:
            continue
        av, inc = float(avail.get(a["_id"], 0.0)), float(incoming.get(a["_id"], 0.0))
        fc = weekly * horizon_weeks
        prior_w = (a["qty"] - a["recent"]) / (WEEKS_HISTORY - 4)
        rows.append({
            "product_id": a["_id"], "product": a.get("name") or a["_id"], "unit": a.get("unit") or "",
            "avg_weekly": round(weekly, 1), "trend_pct": round((rec_w - prior_w) / prior_w * 100, 1) if prior_w > 0 else None,
            "available": round(av, 1), "incoming": round(inc, 1), "forecast": round(fc, 1),
            "suggested_qty": round(max(0.0, fc + weekly - av - inc), 1),
            "days_cover": round(av / (weekly / 7), 1),
            "supplier": (sup.get(a["_id"]) or {}).get("supplier", ""),
            "supplier_id": (sup.get(a["_id"]) or {}).get("supplier_id", "")})
    rows.sort(key=lambda r: (-r["suggested_qty"], r["days_cover"]))
    return rows


def _risk(ratio: float) -> Dict[str, Any]:
    score = int(min(95, max(5, round(100 * (ratio - 0.5) / 2.5))))
    return {"risk_score": score, "risk": "tinggi" if ratio >= 2 else "sedang" if ratio >= 1.3 else "rendah"}


async def churn_rows(entity_ids: List[str], customer_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Jarak antar-pesanan tiap pelanggan (≥3 pesanan, 12 bulan) vs hari sejak pesanan terakhir."""
    today = now_wib().date()
    match: Dict[str, Any] = {"entity_id": {"$in": entity_ids}, "is_live": True, "is_sample": False,
                             "date_wib": {"$gte": (today - timedelta(days=365)).isoformat()}}
    if customer_ids is not None:
        match["customer_id"] = {"$in": customer_ids}
    per: Dict[str, Dict[str, Any]] = {}
    async for r in db.fact_sales_lines.aggregate([
        {"$match": match},
        {"$group": {"_id": {"c": "$customer_id", "so": "$so_id"}, "name": {"$first": "$customer_name"},
                    "d": {"$min": "$date_wib"}, "v": {"$sum": {"$multiply": ["$net_alloc", {"$ifNull": ["$split", 1]}]}}}}]):
        c = per.setdefault(r["_id"]["c"], {"name": r.get("name"), "dates": [], "value": 0.0})
        c["dates"].append(r["d"])
        c["value"] += float(r.get("v") or 0)
    rows = []
    for cid, c in per.items():
        ds = sorted({date.fromisoformat(d) for d in c["dates"]})
        if len(ds) < 3:
            continue
        gap = statistics.median([(b - a).days for a, b in zip(ds, ds[1:])]) or 1
        since = (today - ds[-1]).days
        rows.append({"customer_id": cid, "customer": c["name"], "orders_12m": len(ds), "value_12m": round(c["value"], 2),
                     "median_gap_days": round(gap, 1), "days_since_last": since, "last_order": ds[-1].isoformat(),
                     **_risk(since / gap)})
    rows.sort(key=lambda r: (-r["risk_score"], -r["value_12m"]))
    return rows
