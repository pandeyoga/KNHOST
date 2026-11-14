"""AG-T3 — id kartu tindakan asisten di konteks permintaan (header `X-Asisten-Kartu`).

Kartu tindakan (`services/ai_cards.py`) menjalankan SATU panggilan tulis lewat pintu aplikasi sendiri dengan header
`X-Asisten-Kartu: <id kartu>`. Middleware kecil di sini menaruh id itu di konteks permintaan **hanya bila** kartunya
berstatus `running` dan milik pengguna sesi permintaan tersebut; di luar itu header diabaikan (U17 — header palsu dari
klien biasa tidak pernah menempel di dokumen). Layanan tujuan membaca `current_card_id()` lalu menulis `ai_card_id`:

    from ai_card_context import current_card_id
    doc = {..., **card_field()}        # {"ai_card_id": "aiact_…"} atau {} bila bukan dari kartu

Middleware ASGI murni (bukan `BaseHTTPMiddleware`): nilai ContextVar diset sebelum aplikasi dalam dipanggil sehingga
terbaca di handler maupun di task `call_next` middleware lain (konteks disalin saat task dibuat).
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Dict

HEADER = "x-asisten-kartu"
_CARD: ContextVar[str] = ContextVar("kn_ai_card_id", default="")


def current_card_id() -> str:
    """Id kartu `running` milik pengguna permintaan ini, atau "" bila permintaan bukan dari kartu tindakan."""
    return _CARD.get() or ""


def card_field() -> Dict[str, Any]:
    cid = current_card_id()
    return {"ai_card_id": cid} if cid else {}


async def _verified_card(scope: Dict[str, Any], card_id: str) -> str:
    from starlette.requests import Request
    from db import db
    from idempotency import _session_user_id
    if not card_id or len(card_id) > 64:
        return ""
    user_id = await _session_user_id(Request(scope))
    if not user_id:
        return ""
    card = await db.ai_action_proposals.find_one({"id": card_id, "status": "running", "user_id": user_id},
                                                 {"_id": 0, "id": 1})
    return card_id if card else ""


class AiCardMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)
        raw = ""
        for k, v in scope.get("headers") or []:
            if k.decode("latin-1").lower() == HEADER:
                raw = v.decode("latin-1").strip()
                break
        if not raw:
            # Permintaan biasa: konteks selalu kosong (tidak mewarisi nilai dari permintaan pemanggil di proses yang sama).
            token = _CARD.set("")
        else:
            token = _CARD.set(await _verified_card(scope, raw))
        try:
            return await self.app(scope, receive, send)
        finally:
            _CARD.reset(token)
