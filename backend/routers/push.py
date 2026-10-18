"""Langganan Web Push (PWA) per perangkat — dipakai aplikasi HP sales / Admin Sales.

GET  /push/public-key   → kunci VAPID publik (untuk `pushManager.subscribe`)
POST /push/subscribe    → simpan/perbarui langganan perangkat ini untuk pengguna login
POST /push/unsubscribe  → hapus langganan perangkat ini
GET  /push/status       → jumlah perangkat aktif milik saya
POST /push/test         → kirim push uji ke semua perangkat saya
"""
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core_utils import now_iso
from db import db
from dependencies import current_user
from services import web_push_service as wps

router = APIRouter(prefix="/api")


class SubKeys(BaseModel):
    p256dh: str
    auth: str


class SubscriptionIn(BaseModel):
    endpoint: str = Field(..., min_length=10)
    keys: SubKeys
    device_label: str = ""


class EndpointIn(BaseModel):
    endpoint: str


@router.get("/push/public-key")
async def public_key(request: Request) -> Dict[str, Any]:
    await current_user(request)
    key = wps.vapid_public_key()
    return {"public_key": key, "enabled": bool(key)}


@router.post("/push/subscribe")
async def subscribe(payload: SubscriptionIn, request: Request) -> Dict[str, Any]:
    user = await current_user(request)
    if not wps.vapid_public_key():
        raise HTTPException(status_code=503, detail="Notifikasi push belum dikonfigurasi di server.")
    ua = request.headers.get("user-agent", "")[:200]
    await db.push_subscriptions.update_one(
        {"endpoint": payload.endpoint},
        {"$set": {"endpoint": payload.endpoint, "keys": payload.keys.model_dump(), "user_id": user["id"],
                  "role": user.get("role", ""), "device_label": payload.device_label or ua[:80],
                  "user_agent": ua, "updated_at": now_iso()},
         "$setOnInsert": {"created_at": now_iso()}},
        upsert=True)
    count = await db.push_subscriptions.count_documents({"user_id": user["id"]})
    return {"ok": True, "devices": count}


@router.post("/push/unsubscribe")
async def unsubscribe(payload: EndpointIn, request: Request) -> Dict[str, Any]:
    user = await current_user(request)
    res = await db.push_subscriptions.delete_one({"endpoint": payload.endpoint, "user_id": user["id"]})
    return {"ok": True, "removed": res.deleted_count}


@router.get("/push/status")
async def status(request: Request) -> Dict[str, Any]:
    user = await current_user(request)
    count = await db.push_subscriptions.count_documents({"user_id": user["id"]})
    return {"enabled": bool(wps.vapid_public_key()), "devices": count}


@router.post("/push/test")
async def test_push(request: Request) -> Dict[str, Any]:
    user = await current_user(request)
    subs = await db.push_subscriptions.find({"user_id": user["id"]}, {"_id": 0}).to_list(20)
    if not subs:
        raise HTTPException(status_code=404, detail="Belum ada perangkat yang berlangganan notifikasi.")
    sent = 0
    for sub in subs:
        status_code = await wps.send_to_subscription(sub, {
            "title": "Notifikasi HP aktif", "body": f"Halo {user.get('name', '')}, pemberitahuan Kain Nusantara akan muncul di sini.",
            "tag": "kn-test", "link": "", "severity": "info"})
        sent += 1 if status_code == 201 else 0
    return {"ok": sent > 0, "sent": sent, "devices": len(subs)}
