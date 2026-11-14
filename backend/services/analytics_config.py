"""Tanya KN F0.5 — kebijakan data asisten analitik (keputusan klien §7) dari konfigurasi."""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.config_resolver import value_of

async def ai_policy(entity_id: Optional[str] = None) -> Dict[str, Any]:
    ctx = {"entity_id": entity_id} if entity_id else None
    return {
        "sales_definition": await value_of("ai.sales_definition", ctx) or "net_order",
        "sales_attribution": await value_of("ai.sales_attribution", ctx) or "team_split",
        # PR-T2 — margin & nilai persediaan kini izin `ai.view_margin` / `ai.view_stock_value` (Peran & Hak Akses),
        # diperiksa `analytics_engine._gate` lewat `Scope.allowed`; kunci `ai.*_roles` tidak dipakai lagi.
    }
