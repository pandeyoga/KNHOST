"""Status DIBACA per orang.

`read` (global) = notifikasi selesai/ditutup sistem (resolved, pribadi dibaca pemiliknya).
`read_by` = daftar user yang sudah membaca notifikasi siaran (peran / umum), sehingga satu
orang menandai dibaca tidak menghilangkan notifikasi itu dari lonceng penerima lain.
"""
from typing import Any, Dict

from core_utils import now_iso
from db import db


def unread_for(uid: str) -> Dict[str, Any]:
    return {"read": {"$ne": True}, "read_by": {"$ne": uid}}


def personalize(doc: Dict[str, Any], uid: str) -> Dict[str, Any]:
    out = dict(doc)
    out["read"] = bool(doc.get("read")) or uid in (doc.get("read_by") or [])
    out.pop("read_by", None)
    out.pop("read_at_by", None)
    return out


async def mark_read(query: Dict[str, Any], uid: str) -> int:
    """Tandai dibaca untuk `uid`. Notifikasi pribadi miliknya ikut ditutup global."""
    now = now_iso()
    base = {"$and": [query, unread_for(uid)]}
    own = await db.notifications.update_many(
        {"$and": [base, {"recipient_user": uid}]},
        {"$set": {"read": True, "read_at": now}, "$addToSet": {"read_by": uid}})
    shared = await db.notifications.update_many(
        {"$and": [base, {"recipient_user": {"$ne": uid}}]},
        {"$addToSet": {"read_by": uid}, "$set": {f"read_at_by.{uid}": now}})
    return int(own.modified_count or 0) + int(shared.modified_count or 0)
