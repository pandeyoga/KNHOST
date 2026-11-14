"""Tanya KN F2.5 — biaya per panggilan model + rem anggaran bulanan (`ai.monthly_budget_usd`)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from db import db
from services.ai_provider import PRICE_VERSION
from services.analytics_time import now_wib
from services.config_resolver import value_of


def cost_usd(model: str, usage: Dict[str, Any], price: Optional[Dict[str, float]]) -> float:
    """AG-T1 — harga per model milik pelaksana penyedia (`ModelProvider.price_of`); tanpa harga (mode uji, tiruan) = 0."""
    if str(model).startswith("mock") or not price:
        return 0.0
    p = price
    inp, cached = int(usage.get("input_tokens") or 0), int(usage.get("cached_tokens") or 0)
    out = int(usage.get("output_tokens") or 0)
    return round(((inp - cached) * p["input"] + cached * p["cached_input"] + out * p["output"]) / 1_000_000, 6)


BI_FEATURES = ["bi_chat", "bi_template", "bi_prewarm", "bi_chat_eval"]


async def month_spend() -> float:
    start = now_wib().replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    rows = await db.ai_usage_log.aggregate([
        {"$match": {"feature": {"$in": BI_FEATURES}, "created_at": {"$gte": start},
                    "demo": {"$ne": True}}},
        {"$group": {"_id": None, "usd": {"$sum": {"$ifNull": ["$cost_usd", 0]}}}}]).to_list(1)
    return round(float(rows[0]["usd"]) if rows else 0.0, 4)


async def budget_state() -> Dict[str, Any]:
    limit = float(await value_of("ai.monthly_budget_usd") or 0)
    spent = await month_spend()
    return {"limit_usd": limit, "spent_usd": spent, "exceeded": spent >= limit, "price_version": PRICE_VERSION}
