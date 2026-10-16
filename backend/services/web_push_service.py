"""Web Push (PWA) — kirim notifikasi lonceng ke HP walau aplikasi sedang ditutup.

Satu sumber kebenaran: notifikasi tetap lahir di `notification_service.create_notification`.
Layanan ini hanya MENERUSKAN notifikasi yang baru dibuat ke langganan push milik pengguna
yang memang berhak melihatnya — penyaring audiens SAMA dengan lonceng
(`notification_scope.relevance_filter` + `allowed_entity_ids`), jadi push tidak pernah
membocorkan pesan yang tidak tampil di lonceng orang itu.

Best-effort: kegagalan kirim tidak pernah menggagalkan pembuatan notifikasi. Langganan yang
sudah kedaluwarsa (HTTP 404/410 dari layanan push) dihapus otomatis.
"""
import asyncio
import json
import logging
import os
from typing import Any, Dict

from db import db
from core_utils import now_iso

logger = logging.getLogger(__name__)


def vapid_public_key() -> str:
    return os.environ.get("VAPID_PUBLIC_KEY", "")


def _enabled() -> bool:
    return bool(os.environ.get("VAPID_PUBLIC_KEY") and os.environ.get("VAPID_PRIVATE_KEY"))


def _send_sync(sub: Dict[str, Any], payload: str) -> int:
    """Kirim satu push (blocking — dijalankan di thread). Return status HTTP (0 = gagal jaringan)."""
    from pywebpush import webpush, WebPushException
    try:
        webpush(
            subscription_info={"endpoint": sub["endpoint"], "keys": sub.get("keys") or {}},
            data=payload,
            vapid_private_key=os.environ["VAPID_PRIVATE_KEY"],
            vapid_claims={"sub": os.environ.get("VAPID_SUBJECT", "mailto:admin@example.com")},
            ttl=60 * 60 * 12,
        )
        return 201
    except WebPushException as exc:  # noqa: BLE001
        return getattr(exc.response, "status_code", 0) or 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("[web_push] kirim gagal: %s", exc)
        return 0


async def send_to_subscription(sub: Dict[str, Any], message: Dict[str, Any]) -> int:
    status = await asyncio.to_thread(_send_sync, sub, json.dumps(message))
    if status in (404, 410):
        await db.push_subscriptions.delete_one({"endpoint": sub["endpoint"]})
    elif status == 201:
        await db.push_subscriptions.update_one({"endpoint": sub["endpoint"]}, {"$set": {"last_sent_at": now_iso()}})
    return status


async def _user_may_see(user: Dict[str, Any], note: Dict[str, Any]) -> bool:
    from services.notification_scope import relevance_filter
    ent = note.get("entity_id")
    if ent and ent not in (user.get("allowed_entity_ids") or [user.get("home_entity_id")]):
        return False
    audience = await relevance_filter(user)
    return bool(await db.notifications.count_documents({"$and": [{"id": note["id"]}, audience]}, limit=1))


async def _fanout(note: Dict[str, Any]) -> None:
    if not _enabled():
        return
    q: Dict[str, Any] = {}
    if note.get("recipient_user"):
        q = {"user_id": note["recipient_user"]}
    subs = await db.push_subscriptions.find(q, {"_id": 0}).to_list(500)
    if not subs:
        return
    users: Dict[str, Any] = {}
    message = {
        "title": note.get("title") or "Kain Nusantara",
        "body": note.get("body") or "",
        "tag": note.get("id"),
        "severity": note.get("severity") or "info",
        "link": note.get("link") or "",
        "notification_id": note.get("id"),
    }
    for sub in subs:
        uid = sub.get("user_id")
        if uid not in users:
            users[uid] = await db.users.find_one({"id": uid}, {"_id": 0, "password_hash": 0})
        user = users[uid]
        if not user or user.get("status") == "inactive":
            continue
        if not await _user_may_see(user, note):
            continue
        await send_to_subscription(sub, message)


async def push_notification(note: Dict[str, Any]) -> None:
    """Dipanggil setelah notifikasi dibuat. Tidak menunggu pengiriman selesai."""
    if not _enabled() or not note or not note.get("id"):
        return

    async def _run():
        try:
            await _fanout(note)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[web_push] fan-out gagal diabaikan: %s", exc)

    asyncio.create_task(_run())
