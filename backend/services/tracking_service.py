"""HRD H2 services — Live Field Tracking (WebSocket).

WS-upgrade lewat ingress publik (wss) sudah DIBUKTIKAN di H-POC (scripts/poc_hrd.py).
Manager (admin/manager) subscribe → Live Map; karyawan lapangan (sales) publish posisi.
Koleksi: hr_field_tracks (trk_). Posisi disimpan ter-throttle; cache 'posisi terkini'
untuk snapshot cepat + broadcast realtime.
"""
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set

from db import db
from core_utils import new_id, now_iso, safe_doc
logger = logging.getLogger(__name__)


WIB = timezone(timedelta(hours=7))
STORE_INTERVAL_SEC = 30          # tulis DB maksimum 1×/30 dtk/karyawan (cache tetap realtime)
ONLINE_WINDOW_SEC = 600          # dianggap online bila posisi terakhir < 10 menit

_LIVE_FIELDS = ("employee_id", "employee_name", "lat", "lon", "accuracy",
                "battery", "ts", "entity_id", "source")


class TrackManager:
    """In-memory: subscriber WS + cache posisi terkini per karyawan."""
    def __init__(self) -> None:
        self.subscribers: Dict[Any, Set[str]] = {}  # ws → entitas yang boleh dilihat
        self.latest: Dict[str, Dict[str, Any]] = {}
        self._store_lock = asyncio.Lock()
        self._last_store: Dict[str, datetime] = {}

    def add_subscriber(self, ws: Any, scope: Optional[List[str]] = None) -> None:
        self.subscribers[ws] = set(scope or [])

    def remove_subscriber(self, ws: Any) -> None:
        self.subscribers.pop(ws, None)

    def snapshot(self, scope: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        allowed = set(scope or [])
        return [p for p in self.latest.values() if p.get("entity_id") in allowed]

    async def broadcast(self, msg: Dict[str, Any]) -> None:
        dead = []
        ent = (msg.get("data") or {}).get("entity_id")
        for ws, allowed in list(self.subscribers.items()):
            if ent not in allowed:  # GN-02 — subscriber hanya menerima entitas penugasannya
                continue
            try:
                await ws.send_json(msg)
            except Exception:  # noqa: BLE001 — koneksi mati, bersihkan
                dead.append(ws)
        for ws in dead:
            self.subscribers.pop(ws, None)

    async def update_position(self, pos: Dict[str, Any]) -> None:
        self.latest[pos["employee_id"]] = pos
        await self.broadcast({"type": "position", "data": pos})


manager = TrackManager()


async def auth_ws_token(token: str) -> Optional[Dict[str, Any]]:
    """Validasi token sesi (query param) untuk WebSocket — kontrak expiry sama dengan HTTP (GN-02)."""
    if not token:
        return None
    session = await db.sessions.find_one({"token": token.strip()}, {"_id": 0})
    if not session:
        return None
    exp = session.get("expires_at")
    if isinstance(exp, datetime):
        exp = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
        if exp <= datetime.now(timezone.utc):
            return None
    user = await db.users.find_one(
        {"id": session["user_id"], "status": "active"}, {"_id": 0, "password_hash": 0})
    return safe_doc(user) if user else None


async def subscriber_scope(user: Dict[str, Any]) -> Optional[List[str]]:
    """GN-02 — hak berlangganan Live Map = izin hr.view (sama dengan HTTP), dibatasi entitas."""
    from dependencies import has_permission
    if not await has_permission(user, "hr", "view"):
        return None
    from entity_scope import allowed_entities_for
    return await allowed_entities_for(user)


async def employee_for_user(user_id: str) -> Optional[Dict[str, Any]]:
    return safe_doc(await db.hr_employees.find_one({"user_id": user_id}, {"_id": 0}))


async def store_track(emp: Dict[str, Any], lat: float, lon: float,
                      accuracy: float = 0, battery: Optional[float] = None,
                      source: str = "ws") -> Dict[str, Any]:
    """Update cache + broadcast (selalu) lalu tulis DB ter-throttle."""
    now = datetime.now(WIB)
    pos = {
        "employee_id": emp["id"], "employee_name": emp.get("name", ""),
        "lat": float(lat), "lon": float(lon), "accuracy": float(accuracy or 0),
        "battery": battery, "ts": now.isoformat(),
        "entity_id": emp.get("entity_id", ""), "source": source,
    }
    await manager.update_position(pos)
    last = manager._last_store.get(emp["id"])
    if not last or (now - last).total_seconds() >= STORE_INTERVAL_SEC:
        manager._last_store[emp["id"]] = now
        await db.hr_field_tracks.insert_one(
            {**pos, "id": new_id("trk"), "created_at": now_iso()})
    return pos


async def hydrate_latest() -> None:
    """Muat posisi terakhir per karyawan ke cache saat startup."""
    try:
        pipeline = [
            {"$sort": {"ts": -1}},
            {"$group": {"_id": "$employee_id", "doc": {"$first": "$$ROOT"}}},
        ]
        async for row in db.hr_field_tracks.aggregate(pipeline):
            d = safe_doc(row["doc"])
            manager.latest[d["employee_id"]] = {k: d.get(k) for k in _LIVE_FIELDS}
    except Exception as exc:  # noqa: BLE001 — jangan gagalkan startup
        logger.warning("[hydrate_latest] efek samping gagal diabaikan: %s", exc)  # KN-C10


def is_online(ts_iso: str) -> bool:
    try:
        ts = datetime.fromisoformat(ts_iso)
        return (datetime.now(WIB) - ts).total_seconds() <= ONLINE_WINDOW_SEC
    except (ValueError, TypeError):
        return False
