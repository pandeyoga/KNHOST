"""PREP-G — registri perangkat handheld C72 (admin): buat, terbitkan/rotasi key, cabut, aktifkan, profil, jejak pakai.

Memakai registri yang sudah ada (`rfid_devices`, `rfid_service.create_device`, `rfid_ingest_service.ensure_api_key`) —
key hanya tampil SEKALI (hash SHA-256 di DB). Field tambahan khusus handheld:
  `handheld_scope_level` ("site" bawaan = semua gudang di site gudang perangkat · "warehouse" = gudangnya saja),
  `handheld_profile` (penimpa profil bawaan, lihat `handheld_core.DEFAULT_PROFILE`), `revoked_at/by/reason`.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from core_utils import now_iso
from db import db
from services.handheld_core import OPS, err, profile_of, validate_profile, digest

SCOPE_LEVELS = ("site", "warehouse")


def _public(d: Dict[str, Any]) -> Dict[str, Any]:
    from services.rfid_service import public_device
    out = public_device(d)
    prof = profile_of(d)
    out.update({"scope_level": d.get("handheld_scope_level") or "site", "profile_version": digest(prof)[:16],
                "profile_overrides": d.get("handheld_profile") or {}, "app_version": d.get("handheld_app_version"),
                "revoked_at": d.get("revoked_at"), "revoked_reason": d.get("revoked_reason")})
    return out


async def _get(device_id: str) -> Dict[str, Any]:
    d = await db.rfid_devices.find_one({"id": device_id, "type": "handheld"}, {"_id": 0})
    if not d:
        raise err(404, "DEVICE_NOT_FOUND", "Perangkat handheld tidak ditemukan.")
    return d


def provisioning_payload(device: Dict[str, Any], key: str, base_url: str = "") -> Dict[str, Any]:
    """Isi QR provisioning (dipindai C72 di layar Provisioning). Berisi device key → tampilkan sekali, jangan disimpan."""
    url = (base_url or os.environ.get("PUBLIC_API_URL") or os.environ.get("PUBLIC_APP_URL") or "").rstrip("/")
    body = {"kn": "c72", "v": 1, "url": url, "device_id": device["id"], "code": device.get("code"), "key": key}
    return {"qr_text": json.dumps(body, separators=(",", ":")), "url_note": "Periksa alamat server (url) sebelum dipindai."}


async def list_devices(warehouse_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"type": "handheld"}
    if warehouse_ids is not None:
        q["warehouse_id"] = {"$in": warehouse_ids}
    rows = await db.rfid_devices.find(q, {"_id": 0}).sort("code", 1).to_list(500)
    out = []
    for d in rows:
        op = await db[OPS].find_one({"device_id": d["id"], "ended_at": None}, {"_id": 0, "user_name": 1, "started_at": 1})
        last = await db.handheld_requests.find_one({"device_id": d["id"], "scope": "batch"}, {"_id": 0, "created_at": 1},
                                                   sort=[("created_at", -1)])
        out.append({**_public(d), "operator": op, "last_batch_at": (last or {}).get("created_at")})
    return out


async def create(payload: Dict[str, Any], actor: str) -> Dict[str, Any]:
    from services import rfid_ingest_service as ing
    from services import rfid_service as rfid
    level = payload.get("scope_level") or "site"
    if level not in SCOPE_LEVELS:
        raise err(400, "SCOPE_LEVEL_INVALID", "scope_level harus 'site' atau 'warehouse'.")
    prof = validate_profile(payload.get("profile") or {})
    dev = await rfid.create_device({"code": payload.get("code"), "name": payload["name"], "type": "handheld",
                                    "warehouse_id": payload["warehouse_id"], "location": payload.get("location")}, actor)
    await db.rfid_devices.update_one({"id": dev["id"]}, {"$set": {"handheld_scope_level": level, "handheld_profile": prof,
                                                                  "enabled": True}})
    key = await ing.ensure_api_key(dev["id"])
    full = await _get(dev["id"])
    return {"device": _public(full), "api_key": key["api_key"], "shown_once": True,
            "provisioning": provisioning_payload(full, key["api_key"], payload.get("base_url") or "")}


async def rotate_key(device_id: str, base_url: str = "") -> Dict[str, Any]:
    from services import rfid_ingest_service as ing
    d = await _get(device_id)
    key = await ing.ensure_api_key(device_id, regenerate=True)
    await db.rfid_devices.update_one({"id": device_id}, {"$unset": {"revoked_at": "", "revoked_by": "", "revoked_reason": ""}})
    return {"device": _public(await _get(device_id)), "api_key": key["api_key"], "shown_once": True,
            "provisioning": provisioning_payload(d, key["api_key"], base_url)}


async def revoke(device_id: str, reason: str, actor: str) -> Dict[str, Any]:
    """Cabut: perangkat nonaktif + key dibuang (key lama tidak bisa dipakai lagi walau diaktifkan) + sesi operator ditutup."""
    if len((reason or "").strip()) < 5:
        raise err(400, "REASON_REQUIRED", "Alasan pencabutan minimal 5 karakter (mis. 'unit hilang').")
    await _get(device_id)
    now = now_iso()
    await db.rfid_devices.update_one({"id": device_id}, {"$set": {"enabled": False, "status": "offline", "disabled_at": now,
                                                                  "revoked_at": now, "revoked_by": actor,
                                                                  "revoked_reason": reason.strip()[:300]},
                                                         "$unset": {"api_key_hash": "", "api_key": ""}})
    await db[OPS].update_many({"device_id": device_id, "ended_at": None}, {"$set": {"ended_at": now, "end_reason": "perangkat dicabut"}})
    return _public(await _get(device_id))


async def enable(device_id: str) -> Dict[str, Any]:
    d = await _get(device_id)
    await db.rfid_devices.update_one({"id": device_id}, {"$set": {"enabled": True}, "$unset": {"disabled_at": ""}})
    out = _public(await _get(device_id))
    out["needs_new_key"] = not bool(d.get("api_key_hash"))
    return out


async def set_profile(device_id: str, profile: Optional[Dict[str, Any]], scope_level: Optional[str]) -> Dict[str, Any]:
    await _get(device_id)
    upd: Dict[str, Any] = {"updated_at": now_iso()}
    if profile is not None:
        upd["handheld_profile"] = validate_profile(profile)
    if scope_level is not None:
        if scope_level not in SCOPE_LEVELS:
            raise err(400, "SCOPE_LEVEL_INVALID", "scope_level harus 'site' atau 'warehouse'.")
        upd["handheld_scope_level"] = scope_level
    await db.rfid_devices.update_one({"id": device_id}, {"$set": upd})
    d = await _get(device_id)
    return {**_public(d), "profile": profile_of(d)}


async def activity(device_id: str, limit: int = 50) -> Dict[str, Any]:
    """Jejak siapa-perangkat-apa: sesi operator + permintaan (batch/selesai/tulis tag) terbaru."""
    d = await _get(device_id)
    n = max(1, min(int(limit or 50), 200))
    ops = await db[OPS].find({"device_id": device_id}, {"_id": 0}).sort("started_at", -1).to_list(n)
    reqs = await db.handheld_requests.find({"device_id": device_id}, {"_id": 0, "reads": 0, "result.items": 0}
                                           ).sort("created_at", -1).to_list(n)
    writes = await db.handheld_tag_writes.find({"device_id": device_id}, {"_id": 0}).sort("created_at", -1).to_list(n)
    return {"device": _public(d), "operator_sessions": ops, "requests": reqs, "tag_writes": writes}
