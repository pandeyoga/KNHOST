"""Dasbor Pesanan HP sales — omzet, status, tren 8 minggu, pelanggan teratas & pesanan butuh tindakan (data milik sales sendiri)."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from db import db

DEAD = {"cancelled", "draft", "expired", "rejected"}
BUCKETS = {
    "waiting": {"waiting_approval", "pending_approval"},
    "processing": {"approved", "confirmed", "reserved", "partially_picked", "picked", "ready"},
    "shipped": {"partially_shipped", "shipped", "delivered"},
    "done": {"done", "completed"},
}
BUCKET_LABEL = {"waiting": "Menunggu persetujuan", "processing": "Diproses", "shipped": "Dikirim", "done": "Selesai"}


def _dt(s: Any) -> Optional[datetime]:
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _amount(o: Dict[str, Any]) -> float:
    return float(o.get("grand_total") or o.get("total_amount") or 0)


def _month_start(d: datetime) -> datetime:
    return d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def order_dashboard(sales_id: str, entity_id: Optional[str] = None) -> Dict[str, Any]:
    q: Dict[str, Any] = {"sales_id": sales_id}
    if entity_id and entity_id != "all":
        q["entity_id"] = entity_id
    orders = await db.sales_orders.find(q, {"_id": 0, "id": 1, "number": 1, "status": 1, "payment_status": 1,
                                            "grand_total": 1, "total_amount": 1, "created_at": 1, "customer_id": 1,
                                            "customer_name": 1, "rejection_reason": 1}).to_list(5000)
    now = datetime.now(timezone.utc)
    this_m = _month_start(now)
    last_m = _month_start(this_m - timedelta(days=1))
    week0 = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(weeks=7)
    rev_this = rev_last = 0.0
    counts = {k: 0 for k in BUCKETS}
    weeks = [{"week_start": (week0 + timedelta(weeks=i)).date().isoformat(), "amount": 0.0, "orders": 0} for i in range(8)]
    top: Dict[str, Dict[str, Any]] = {}
    action: List[Dict[str, Any]] = []
    for o in orders:
        st = o.get("status") or ""
        created = _dt(o.get("created_at"))
        amt = _amount(o)
        for k, sts in BUCKETS.items():
            if st in sts:
                counts[k] += 1
        if st == "rejected":
            action.append({**_brief(o), "reason": "Ditolak — perbaiki/ajukan ulang", "kind": "rejected"})
        elif st in BUCKETS["waiting"]:
            action.append({**_brief(o), "reason": "Menunggu persetujuan", "kind": "waiting"})
        elif st == "draft":
            action.append({**_brief(o), "reason": "Masih draf", "kind": "draft"})
        elif st in BUCKETS["shipped"] | BUCKETS["done"] and o.get("payment_status") != "paid":
            action.append({**_brief(o), "reason": "Belum lunas", "kind": "unpaid"})
        if st in DEAD or not created:
            continue
        if created >= this_m:
            rev_this += amt
        elif created >= last_m:
            rev_last += amt
        if created >= week0:
            i = min(7, (created - week0).days // 7)
            weeks[i]["amount"] += amt
            weeks[i]["orders"] += 1
        if created >= now - timedelta(days=90):
            t = top.setdefault(o.get("customer_id") or "-", {"customer_id": o.get("customer_id"), "customer_name": o.get("customer_name") or "-", "amount": 0.0, "orders": 0})
            t["amount"] += amt
            t["orders"] += 1
    order = {"rejected": 0, "waiting": 1, "draft": 2, "unpaid": 3}
    action.sort(key=lambda a: (order.get(a["kind"], 9), a.get("created_at") or ""))
    growth = ((rev_this - rev_last) / rev_last * 100) if rev_last else None
    return {
        "revenue_this_month": round(rev_this, 2), "revenue_last_month": round(rev_last, 2),
        "growth_pct": round(growth, 1) if growth is not None else None,
        "status_counts": [{"key": k, "label": BUCKET_LABEL[k], "count": counts[k]} for k in BUCKETS],
        "weekly": [{**w, "amount": round(w["amount"], 2)} for w in weeks],
        "top_customers": sorted(top.values(), key=lambda t: -t["amount"])[:5],
        "action_needed": action[:10], "action_total": len(action),
    }


def _brief(o: Dict[str, Any]) -> Dict[str, Any]:
    return {"order_id": o.get("id"), "number": o.get("number"), "customer_name": o.get("customer_name"),
            "status": o.get("status"), "amount": _amount(o), "created_at": o.get("created_at")}
