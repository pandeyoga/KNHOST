"""Halaman Biaya AI — pemakaian harian per fitur, per pengguna, per model (tanggal WIB)."""
from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from db import db
from services import ai_cost
from services.analytics_time import WIB, now_wib

FEATURE_LABELS = {"bi_chat": "Chat Tanya KN", "bi_template": "Ringkasan AI laporan",
                  "bi_prewarm": "Pemanasan cache", "bi_chat_eval": "Evaluasi model (admin)",
                  "ocr_dn": "Baca surat jalan (OCR)"}
BI_FEATURES = ai_cost.BI_FEATURES
TOP_USERS = 6


def _tokens(u: Optional[Dict[str, Any]]) -> int:
    u = u or {}
    return int(u.get("input_tokens") or u.get("input") or 0) + int(u.get("output_tokens") or u.get("output") or 0)


def _when(doc: Dict[str, Any]) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(doc.get("created_at") or doc.get("at") or "")
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(WIB)


def _user_key(r: Dict[str, Any]) -> str:
    return r["user_id"] or (f"actor:{r['actor']}" if r["actor"] else "system")


def _summary(rows: List[Dict[str, Any]], key: Callable, label: Callable, total_usd: float) -> List[Dict[str, Any]]:
    acc: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        k = key(r)
        a = acc.setdefault(k, {"key": k, "label": label(k), "usd": 0.0, "calls": 0, "tokens": 0})
        a["usd"] += r["usd"]
        a["calls"] += 1
        a["tokens"] += r["tokens"]
    out = sorted(acc.values(), key=lambda a: (-a["usd"], -a["calls"]))
    for a in out:
        a["usd"] = round(a["usd"], 6)
        a["share_pct"] = round(a["usd"] / total_usd * 100, 1) if total_usd else None
    return out


def _daily(rows: List[Dict[str, Any]], dates: List[str], key: Callable) -> List[Dict[str, Any]]:
    cell: Dict[str, Dict[str, Dict[str, float]]] = {d: defaultdict(lambda: {"usd": 0.0, "calls": 0, "tokens": 0}) for d in dates}
    for r in rows:
        c = cell[r["date"]][key(r)]
        c["usd"] += r["usd"]
        c["calls"] += 1
        c["tokens"] += r["tokens"]
    return [{"date": d, "values": {k: {**v, "usd": round(v["usd"], 6)} for k, v in cell[d].items()}} for d in dates]


async def _names(keys: List[str]) -> Dict[str, str]:
    ids = [k for k in keys if not k.startswith("actor:") and k != "system"]
    users = {u["id"]: u.get("name") or u.get("email") or u["id"]
             async for u in db.users.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "name": 1, "email": 1})}
    return {k: users.get(k) or (k[6:] if k.startswith("actor:") else "Sistem (otomatis)" if k == "system" else k) for k in keys}


async def daily_report(days: int, scope: str, only_user_id: Optional[str] = None) -> Dict[str, Any]:
    days = max(1, min(int(days or 30), 90))
    now = now_wib()
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    lower = (start - timedelta(days=1)).date().isoformat()
    q: Dict[str, Any] = {"$or": [{"created_at": {"$gte": lower}}, {"at": {"$gte": lower}}]}
    if scope != "all":
        q["feature"] = {"$in": BI_FEATURES}
    if only_user_id:
        q["user_id"] = only_user_id
    proj = {"_id": 0, "feature": 1, "model": 1, "user_id": 1, "actor": 1, "usage": 1, "cost_usd": 1, "created_at": 1, "at": 1, "demo": 1}
    dates = [(start + timedelta(days=i)).date().isoformat() for i in range(days)]
    rows = []
    async for d in db.ai_usage_log.find(q, proj):
        w = _when(d)
        if not w or w < start:
            continue
        rows.append({"date": w.date().isoformat(), "feature": d.get("feature") or "lainnya", "model": d.get("model") or "-",
                     "user_id": d.get("user_id") or "", "actor": d.get("actor") or "", "usd": float(d.get("cost_usd") or 0),
                     "tokens": _tokens(d.get("usage")), "demo": bool(d.get("demo"))})
    total_usd = sum(r["usd"] for r in rows)
    names = await _names(list({_user_key(r) for r in rows}))
    features = _summary(rows, lambda r: r["feature"], lambda k: FEATURE_LABELS.get(k, k), total_usd)
    users = _summary(rows, _user_key, lambda k: names.get(k, k), total_usd)
    top = {u["key"] for u in users[:TOP_USERS]}
    user_series = [{"key": u["key"], "label": u["label"]} for u in users[:TOP_USERS]]
    if len(users) > TOP_USERS:
        user_series.append({"key": "others", "label": "Lainnya"})
    budget = await ai_cost.budget_state()
    dim = calendar.monthrange(now.year, now.month)[1]
    return {
        "range": {"from": dates[0], "to": dates[-1], "days": days}, "scope": "all" if scope == "all" else "bi",
        "totals": {"usd": round(total_usd, 6), "calls": len(rows), "tokens": sum(r["tokens"] for r in rows),
                   "avg_usd_per_day": round(total_usd / days, 6)},
        "budget": {**budget, "used_pct": round(budget["spent_usd"] / budget["limit_usd"] * 100, 1) if budget["limit_usd"] else None,
                   "projected_usd": round(budget["spent_usd"] / now.day * dim, 4)},
        "features": features, "users": users,
        "models": _summary(rows, lambda r: r["model"], lambda k: k, total_usd),
        "feature_series": [{"key": f["key"], "label": f["label"]} for f in features],
        "user_series": user_series,
        "daily_feature": _daily(rows, dates, lambda r: r["feature"]),
        "daily_user": _daily(rows, dates, lambda r: _user_key(r) if _user_key(r) in top else "others"),
        "demo_rows": sum(1 for r in rows if r["demo"]),
    }
