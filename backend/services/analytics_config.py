"""Tanya KN F0.5 — kebijakan data asisten analitik (keputusan klien §7) dari konfigurasi."""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.config_resolver import value_of

COST_SAFE_DEFAULT = ("admin", "manager")


async def ai_policy(entity_id: Optional[str] = None) -> Dict[str, Any]:
    ctx = {"entity_id": entity_id} if entity_id else None
    return {
        "sales_definition": await value_of("ai.sales_definition", ctx) or "net_order",
        "sales_attribution": await value_of("ai.sales_attribution", ctx) or "team_split",
        "margin_roles": list(await value_of("ai.margin_roles", ctx) or COST_SAFE_DEFAULT),
        "stock_value_roles": list(await value_of("ai.stock_value_roles", ctx) or (*COST_SAFE_DEFAULT, "finance")),
    }


def role_may(policy: Dict[str, Any], key: str, role: Optional[str]) -> bool:
    return (role or "") in (policy.get(key) or [])
