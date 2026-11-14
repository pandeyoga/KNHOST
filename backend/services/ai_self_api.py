"""AG-T2 (AG-03) — asisten membaca data lewat pintu aplikasi sendiri, dengan sesi pengguna yang bertanya.

Alat asisten keuangan (`services/ai_finance_tools.py`) tidak menyusun cakupan sendiri dan tidak membaca database:
mereka memanggil endpoint yang sama dengan layar, di dalam proses (`httpx.ASGITransport`), memakai token sesi dan
PT aktif permintaan asal. Akibatnya izin, PT, cakupan data, dan saringan bidang = persis layar; angka = persis layar.

    api = SelfApi.from_request(request)              # sesi & PT dari permintaan pengguna
    try:
        laba = await api.call("GET", "/api/finance/income-statement", params={"start": "2026-11-01", "end": "2026-11-30"})
    except SelfApiError as e:                         # 403 izin, 404, 400 … → pesan endpoint apa adanya
        ...
    finally:
        await api.aclose()

Aturan `call` (urutan tetap): jalur harus `/api/…` dan bukan `/api/ai/…` maupun `/api/auth/…` (400) → baca-saja dan
metode bukan GET → 403 tanpa memanggil aplikasi → `params`/`json` memuat kunci `entity_id` → 400 (PT dari sesi, N1) →
kirim dengan `Authorization: Bearer <token>`, `X-Entity-Id: <header asal, termasuk "all">`, `X-Via: asisten` →
jawaban ≥ 400 → `SelfApiError(status, detail endpoint)`.

Jadwal laporan (tanpa permintaan HTTP) memakai `for_user`: dokumen `sessions` berumur 10 menit bertanda
`purpose: "ai_schedule"`, dihapus oleh `aclose`.
"""
from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Dict, Optional

import httpx

READ_ONLY_MESSAGE = ("Asisten hanya boleh membaca. Perubahan dilakukan lewat kartu tindakan yang Anda setujui.")
#: AG-T3 — mode tulis (kartu tindakan yang disetujui) hanya menerima pintu yang terdaftar di `ai_cards`.
WRITE_PATH_MESSAGE = "Asisten hanya boleh menulis lewat pintu kartu tindakan yang terdaftar."
#: AG-T3 — header id kartu; dibaca `ai_card_context.AiCardMiddleware` (hanya kartu `running` milik sesi).
CARD_HEADER = "X-Asisten-Kartu"
ENTITY_MESSAGE = "PT diambil dari sesi, bukan dari permintaan."
PATH_MESSAGE = "Asisten hanya boleh memanggil endpoint data aplikasi."
#: Umur sesi sementara jadwal laporan (batas teknis, bukan aturan bisnis).
SCHEDULE_SESSION_MINUTES = 10
SCHEDULE_PURPOSE = "ai_schedule"
_BLOCKED_PREFIXES = ("/api/ai/", "/api/auth/")

_APP: Any = None
_CURRENT: ContextVar[Optional["SelfApi"]] = ContextVar("kn_ai_self_api", default=None)


def set_app(app: Any) -> None:
    """Dipanggil sekali di lifespan server: aplikasi yang dipanggil `SelfApi`."""
    global _APP
    _APP = app


class SelfApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = int(status)
        self.message = str(message)


def _has_entity_key(obj: Any) -> bool:
    if isinstance(obj, dict):
        return any(k == "entity_id" or _has_entity_key(v) for k, v in obj.items())
    if isinstance(obj, (list, tuple)):
        return any(_has_entity_key(v) for v in obj)
    return False


def _detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return (resp.text or "").strip()[:300] or f"Permintaan ditolak ({resp.status_code})."
    d = body.get("detail") if isinstance(body, dict) else body
    if isinstance(d, str):
        return d
    if isinstance(d, list):   # galat validasi FastAPI → kalimat singkat, tanpa struktur teknis
        locs = [".".join(str(x) for x in (it.get("loc") or [])[1:]) for it in d if isinstance(it, dict)]
        return "Isian alat tidak sah: " + ", ".join(x for x in locs if x) if any(locs) else "Isian alat tidak sah."
    return str(d)[:300]


class SelfApi:
    def __init__(self, app: Any, *, token: str, entity_header: str, read_only: bool = True, card_id: str = "") -> None:
        self.app = app if app is not None else _APP
        self.token = token or ""
        self.entity_header = (entity_header or "").strip()
        self.read_only = bool(read_only)
        self.card_id = card_id or ""
        self._client: Optional[httpx.AsyncClient] = None
        self._temp_token = ""
        self.last_status = 0

    @classmethod
    def from_request(cls, request: Any, *, read_only: bool = True, card_id: str = "") -> "SelfApi":
        from dependencies import extract_token
        return cls(_APP or getattr(request, "app", None), token=extract_token(request),
                   entity_header=request.headers.get("X-Entity-Id", ""), read_only=read_only, card_id=card_id)

    @classmethod
    async def for_user(cls, user: Dict[str, Any], entity_id: str, *, read_only: bool = True) -> "SelfApi":
        """Jadwal laporan: sesi sementara 10 menit atas nama pemilik jadwal (izinnya sendiri, PT jadwal)."""
        from db import db
        token = "aisch_" + secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        await db.sessions.insert_one({"token": token, "user_id": user["id"], "created_at": now,
                                      "expires_at": now + timedelta(minutes=SCHEDULE_SESSION_MINUTES),
                                      "purpose": SCHEDULE_PURPOSE, "fixed_expiry": True})
        api = cls(_APP, token=token, entity_header=entity_id, read_only=read_only)
        api._temp_token = token
        return api

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            if self.app is None:
                raise SelfApiError(503, "Pintu data asisten belum siap.")
            self._client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://kn-asisten",
                                             timeout=120)
        return self._client

    async def call(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, json: Any = None,
                   idempotency_key: str = "") -> Any:
        method = (method or "").upper()
        path = path or ""
        if (not path.startswith("/api/") or any(path.startswith(p) for p in _BLOCKED_PREFIXES)
                or path.rstrip("/") in ("/api/ai", "/api/auth") or ".." in path or "?" in path or "#" in path):
            raise SelfApiError(400, PATH_MESSAGE)
        if self.read_only and method != "GET":
            raise SelfApiError(403, READ_ONLY_MESSAGE)
        if not self.read_only:
            from services.ai_cards import write_allowed   # AG-T3 — hanya `write_path` tindakan terdaftar
            if not write_allowed(method, path):
                raise SelfApiError(403, WRITE_PATH_MESSAGE)
        if _has_entity_key(params) or _has_entity_key(json):
            raise SelfApiError(400, ENTITY_MESSAGE)
        headers = {"Authorization": f"Bearer {self.token}", "X-Via": "asisten"}
        if self.entity_header:
            headers["X-Entity-Id"] = self.entity_header
        if self.card_id:
            headers[CARD_HEADER] = self.card_id
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        clean = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        resp = await self._http().request(method, path, params=clean, json=json, headers=headers)
        self.last_status = resp.status_code
        if resp.status_code >= 400:
            raise SelfApiError(resp.status_code, _detail(resp))
        try:
            return resp.json()
        except ValueError:
            return resp.text

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        if self._temp_token:
            from db import db
            await db.sessions.delete_one({"token": self._temp_token, "purpose": SCHEDULE_PURPOSE})
            self._temp_token = ""


# ── pintu yang sedang berlaku untuk permintaan ini (dipasang router; jadwal membuat sesi sementara) ─────────────────
def current() -> Optional[SelfApi]:
    return _CURRENT.get()


def bind(api: Optional[SelfApi]):
    return _CURRENT.set(api)


def unbind(token) -> None:
    try:
        _CURRENT.reset(token)
    except ValueError:   # token dari konteks lain (generator SSE) — cukup kosongkan
        _CURRENT.set(None)


def entity_header_of(ctx: Any) -> str:
    """Header PT untuk sesi sementara: "all" pada mode gabungan, selain itu PT aktif."""
    return "all" if getattr(ctx, "view_all", False) else (getattr(ctx, "active_entity_id", "") or "")


@asynccontextmanager
async def for_scope(user: Dict[str, Any], ctx: Any, *, read_only: bool = True) -> AsyncIterator[SelfApi]:
    """Pintu permintaan ini bila router memasangnya; selain itu (jadwal, skrip) sesi sementara atas nama `user`."""
    api = _CURRENT.get()
    if api is not None:
        yield api
        return
    api = await SelfApi.for_user(user, entity_header_of(ctx), read_only=read_only)
    try:
        yield api
    finally:
        await api.aclose()
