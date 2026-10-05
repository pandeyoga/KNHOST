"""Klien API dalam-proses (ASGI) untuk skrip demo: memanggil endpoint resmi FastAPI tanpa server terpisah,
sehingga semua aturan bisnis, jurnal, saldo, dan audit berjalan persis seperti dari layar."""
import sys
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

DEMO_PASSWORD = "demo1234"
BATCH = "DEMO_LENGKAP_KN"


class ApiError(RuntimeError):
    def __init__(self, method: str, path: str, status: int, detail: Any):
        super().__init__(f"{method} {path} → {status}: {str(detail)[:600]}")
        self.status, self.detail = status, detail


class Session:
    def __init__(self, client: httpx.AsyncClient, token: str, user: Dict[str, Any]):
        self.client, self.token, self.user = client, token, user

    async def call(self, method: str, path: str, json: Any = None, entity: str = "",
                   params: Optional[Dict[str, Any]] = None) -> Any:
        headers = {"Authorization": f"Bearer {self.token}"}
        if entity:
            headers["X-Entity-Id"] = entity
        r = await self.client.request(method, f"/api{path}", json=json, params=params, headers=headers)
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail")
            except Exception:  # noqa: BLE001
                detail = r.text
            raise ApiError(method, path, r.status_code, detail)
        return r.json() if r.content else {}

    async def get(self, path: str, entity: str = "", **params: Any) -> Any:
        return await self.call("GET", path, entity=entity, params=params or None)

    async def post(self, path: str, json: Any = None, entity: str = "") -> Any:
        return await self.call("POST", path, json=json or {}, entity=entity)

    async def patch(self, path: str, json: Any = None, entity: str = "") -> Any:
        return await self.call("PATCH", path, json=json or {}, entity=entity)

    async def put(self, path: str, json: Any = None, entity: str = "") -> Any:
        return await self.call("PUT", path, json=json or {}, entity=entity)


class Api:
    def __init__(self) -> None:
        from server import app
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 50000)),
                                        base_url="http://demo.local", timeout=600)
        self._sessions: Dict[str, Session] = {}

    async def as_user(self, email: str, password: str = DEMO_PASSWORD) -> Session:
        if email in self._sessions:
            return self._sessions[email]
        r = await self.client.post("/api/auth/login", json={"email": email, "password": password})
        if r.status_code != 200:
            raise ApiError("POST", "/auth/login", r.status_code, f"{email}: {r.text[:300]}")
        body = r.json()
        self._sessions[email] = Session(self.client, body["token"], body["user"])
        return self._sessions[email]

    async def system_admin(self) -> Session:
        """Sesi admin internal sementara (tanpa sandi admin asli) — dihapus di `close()`."""
        import secrets
        from core_utils import new_id, now_iso
        from db import db
        if "__sys__" in self._sessions:
            return self._sessions["__sys__"]
        admin = await db.users.find_one({"role": "admin", "status": "active"}, {"_id": 0, "password_hash": 0},
                                        sort=[("created_at", 1)])
        if not admin:
            raise RuntimeError("Tidak ada akun admin aktif.")
        token = secrets.token_urlsafe(32)
        from datetime import datetime, timedelta, timezone
        await db.sessions.insert_one({"id": new_id("session"), "token": token, "user_id": admin["id"],
                                      "created_at": now_iso(), "demo_seed": True,
                                      "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()})
        self._sessions["__sys__"] = Session(self.client, token, admin)
        return self._sessions["__sys__"]

    async def close(self) -> None:
        from db import db
        await db.sessions.delete_many({"demo_seed": True})
        for s in self._sessions.values():
            if s.token:
                try:
                    await self.client.post("/api/auth/logout", headers={"Authorization": f"Bearer {s.token}"})
                except Exception:  # noqa: BLE001
                    pass
        await self.client.aclose()
