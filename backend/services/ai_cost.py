"""Tanya KN F2.5 — biaya per panggilan model + rem anggaran bulanan (`ai.monthly_budget_usd`)."""
from __future__ import annotations

from typing import Any, Dict

from db import db
from services.analytics_time import now_wib
from services.config_resolver import value_of

PRICE_VERSION = "2026-06-perkiraan"
# USD per 1 juta token. Harga luna = perkiraan; perbarui setelah tagihan OpenAI pertama.
PRICES: Dict[str, Dict[str, float]] = {
    "gpt-6-sol": {"input": 2.50, "cached_input": 0.25, "output": 10.00},
    "gpt-6-luna": {"input": 0.50, "cached_input": 0.05, "output": 2.00},
}


def cost_usd(model: str, usage: Dict[str, Any]) -> float:
    if str(model).startswith("mock"):
        return 0.0
    p = PRICES.get(model) or PRICES["gpt-6-sol"]
    inp, cached = int(usage.get("input_tokens") or 0), int(usage.get("cached_tokens") or 0)
    out = int(usage.get("output_tokens") or 0)
    return round(((inp - cached) * p["input"] + cached * p["cached_input"] + out * p["output"]) / 1_000_000, 6)


async def month_spend() -> float:
    start = now_wib().replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    rows = await db.ai_usage_log.aggregate([
        {"$match": {"feature": {"$in": ["bi_chat", "bi_template", "bi_prewarm"]}, "created_at": {"$gte": start},
                    "demo": {"$ne": True}}},
        {"$group": {"_id": None, "usd": {"$sum": {"$ifNull": ["$cost_usd", 0]}}}}]).to_list(1)
    return round(float(rows[0]["usd"]) if rows else 0.0, 4)


async def budget_state() -> Dict[str, Any]:
    limit = float(await value_of("ai.monthly_budget_usd") or 0)
    spent = await month_spend()
    return {"limit_usd": limit, "spent_usd": spent, "exceeded": spent >= limit, "price_version": PRICE_VERSION}
