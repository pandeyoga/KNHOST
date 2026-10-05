"""Tanya KN F4 (dasar) — template laporan `tpl-v1`: resep dijalankan server TANPA model."""
from __future__ import annotations

import copy
import difflib
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from db import db
from services import ai_tools
from services.ai_narrative import auto_summary
from services.analytics_catalog import CATALOG_VERSION
from services.analytics_time import now_wib
from services.config_resolver import value_of

_DATA = Path(__file__).resolve().parents[1] / "data" / "ai"
TEMPLATES: Dict[str, Any] = json.loads((_DATA / "templates_laporan_v1.json").read_text(encoding="utf-8"))
BY_ID = {t["id"]: t for t in TEMPLATES["templates"]}
GROUP_ORDER = ["Harian", "Penjualan", "Keuangan", "Stok", "Pembelian", "Eksekutif", "SDM"]
PERIOD_PRESETS = ["today", "this_week", "mtd", "last_month", "last_90d", "ytd"]


def for_role(role: str) -> List[Dict[str, Any]]:
    out = []
    for t in TEMPLATES["templates"]:
        if role == "admin" or role in t["roles"]:
            out.append({k: t[k] for k in ("id", "title", "group", "prompt", "params", "narrative")}
                       | {"has_period": any("period" in s["args"] and s["args"]["period"] for s in t["steps"])})
    return sorted(out, key=lambda t: GROUP_ORDER.index(t["group"]) if t["group"] in GROUP_ORDER else 99)


def suggest(question: str, role: str, n: int = 3) -> List[Dict[str, Any]]:
    q = question.lower()
    scored = [(difflib.SequenceMatcher(None, q, (t["prompt"] + " " + t["title"]).lower()).ratio(), t) for t in for_role(role)]
    return [t for s, t in sorted(scored, key=lambda x: -x[0])[:n]]


def _similar(a: str, b: str) -> float:
    """Kemiripan ketat: min(rasio karakter, Jaccard kata) — beda satu kata kunci ("baru" vs "terbesar") tidak lolos."""
    ta, tb = set(a.split()), set(b.split())
    return min(difflib.SequenceMatcher(None, a, b).ratio(), len(ta & tb) / len(ta | tb) if ta | tb else 0.0)


def route(question: str, role: str, threshold_pct: int) -> Optional[Dict[str, Any]]:
    """F5 — pertanyaan yang hampir sama dengan template (≥ ambang) dijalankan sebagai template."""
    q = question.lower().strip(" ?.!")
    best, score = None, 0.0
    for t in for_role(role):
        if any(p.get("required") for p in t["params"]):
            continue
        s = max(_similar(q, x.lower().strip(" ?.!")) for x in (t["prompt"], t["title"]))
        if s > score:
            best, score = t, s
    return {**best, "score": round(score, 3)} if best and score * 100 >= threshold_pct else None


CLOSED_PERIODS = {"last_month", "last_week", "last_year", "yesterday"}
_cache_ready = False


def _cache_key(template_id: str, params: Dict[str, Any], user, ctx) -> str:
    raw = [user.get("id"), user.get("role"), ctx.active_entity_id, sorted(ctx.allowed_entity_ids), bool(getattr(ctx, "view_all", False)),
           template_id, params, CATALOG_VERSION, now_wib().date().isoformat()]
    return hashlib.sha256(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()


async def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    hit = await db.ai_result_cache.find_one({"key": key, "expires_at": {"$gt": datetime.now(timezone.utc)}}, {"_id": 0, "out": 1})
    return {**json.loads(hit["out"]), "cached": True} if hit else None


async def _cache_put(key: str, out: Dict[str, Any], minutes: int, closed: bool) -> None:
    global _cache_ready
    if not _cache_ready:
        await db.ai_result_cache.create_index("expires_at", expireAfterSeconds=0)
        await db.ai_result_cache.create_index("key", unique=True)
        _cache_ready = True
    exp = datetime.now(timezone.utc) + (timedelta(hours=24) if closed else timedelta(minutes=minutes))
    await db.ai_result_cache.update_one({"key": key}, {"$set": {"out": json.dumps(out, default=str), "expires_at": exp}}, upsert=True)


def _apply_params(args: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    a = copy.deepcopy(args)
    if params.get("period") and isinstance(a.get("period"), dict):
        a["period"] = {"preset": params["period"], "from": None, "to": None}
    for k in ("days", "days_ahead"):
        if params.get(k):
            a[k] = int(params[k])
    if params.get("product"):
        a["filters"] = [f for f in a.get("filters") or [] if f.get("dimension") != "product"] + [
            {"dimension": "product", "op": "in", "values": [params["product"]]}]
    return a


def _resolve(ref: str, results: List[Dict[str, Any]]) -> Optional[str]:
    step, _, section = ref.partition(".")
    idx = int(step[1:]) - 1
    if idx >= len(results) or not results[idx]:
        return None
    res = results[idx]
    if section:
        res = (res.get("sections") or {}).get(section) or {}
    elif "sections" in res:
        res = next(iter(res["sections"].values()), {})
    return res.get("result_id")


async def run(template_id: str, params: Dict[str, Any], user, ctx, session_id: Optional[str] = None,
              use_cache: bool = True) -> Dict[str, Any]:
    t = BY_ID.get(template_id)
    if not t or (user.get("role") != "admin" and user.get("role") not in t["roles"]):
        raise ai_tools.engine.AnalyticsError("Template tidak ditemukan untuk peran Anda.")
    for p in t["params"]:
        if p.get("required") and not params.get(p["name"]):
            raise ai_tools.engine.AnalyticsError(f"Parameter '{p['name']}' wajib diisi.")
    minutes = int(await value_of("ai.template_cache_minutes") or 0)
    key = _cache_key(template_id, params, user, ctx)
    if use_cache and minutes and not session_id:
        hit = await _cache_get(key)
        if hit:
            return hit
    results, warnings, index = [], [], {}
    for step in t["steps"]:
        res = await ai_tools.execute(step["tool"], _apply_params(step["args"], params), user, ctx, session_id)
        if res.get("error"):
            warnings.append(res["error"])
            res = {}
        results.append(res)
        warnings += res.get("warnings") or []
        for r in [res] + list((res.get("sections") or {}).values()):
            if r.get("result_id"):
                index[r["result_id"]] = r
    blocks = []
    for b in t["blocks"]:
        rid = _resolve(b["from"], results)
        if rid:
            blocks.append({**{k: v for k, v in b.items() if k != "from"}, "result_id": rid})
    shown = [index[r] for r in dict.fromkeys(b["result_id"] for b in blocks)]
    out = {"template": {k: t[k] for k in ("id", "title", "group", "prompt", "narrative")}, "params": params,
           "blocks": blocks, "results": index, "warnings": list(dict.fromkeys(warnings)),
           "narrative": auto_summary(shown) if t["narrative"] != "none" else None, "narrative_source": "auto", "cached": False}
    if minutes and not session_id:
        await _cache_put(key, out, minutes, params.get("period") in CLOSED_PERIODS)
    return out
