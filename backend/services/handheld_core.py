"""PREP-G — inti API handheld Chainway C72: identitas perangkat + sesi operator + cakupan lokasi + profil.

Dua identitas WAJIB untuk setiap pekerjaan (spesifikasi Kubus 02 §2.3/§5.1):
  * PERANGKAT — header ``X-Device-Key`` (per unit, `rfid_devices.type == "handheld"`, terikat gedung/site, bisa dicabut:
    `enabled=false` atau key dicabut). Memakai `rfid_ingest_service.authenticate` (hash SHA-256 yang sama dengan gate).
  * PENGGUNA — sesi ERP biasa (``Authorization: Bearer``) → izin per jenis tugas + cakupan lokasi pengguna
    (`location_scope.warehouse_ids_for`).
Cakupan gudang efektif = gudang perangkat (seluruh gudang di site perangkat, atau hanya gudangnya bila
`handheld_scope_level == "warehouse"`) ∩ lokasi kerja pengguna. Badan usaha: seluruh PT yang ditugaskan ke pengguna
(gedung dipakai bersama semua PT — K-GDG-07; tiap dokumen tetap dicek pemiliknya oleh layanan asal).

Sesi operator (`handheld_operator_sessions`) mencatat siapa memakai perangkat mana kapan. Login di perangkat menutup
sesi operator lama perangkat itu ("ganti operator"); bukti yang ditangkap operator lama tetap miliknya (batch membawa
`operator_session_id` + `user_id` dan ditolak bila token pengguna lain mengirimnya).
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request

from core_utils import new_id, now_iso
from db import db

API_VERSION = "1.0"
MIN_APP_VERSION = "0.1.0"
OPS = "handheld_operator_sessions"

# Jenis tugas (keputusan pemilik: dibedakan jelas). Izin = izin endpoint web asal yang dibungkus (tidak dilonggarkan).
KINDS: Dict[str, Dict[str, Any]] = {
    "putaway_in": {"label": "Masuk · Putaway", "hint": "Tiba Putaway Order per trip", "perm": ("wms", "update"),
                   "complete": False, "order": 1},
    "outbound_so": {"label": "Keluar · SO", "hint": "Final Loading Check per SO & gudang", "perm": ("wms", "update"),
                    "complete": True, "order": 2},
    "outbound_sample": {"label": "Keluar · Sampel", "hint": "Final Loading Check pesanan sampel", "perm": ("wms", "update"),
                        "complete": True, "order": 3},
    "transfer_in": {"label": "Transfer masuk", "hint": "Terima roll transfer gudang", "perm": ("transfer", "update"),
                    "complete": False, "order": 4},
    "cutting": {"label": "Potong sampel", "hint": "Pindai roll induk lalu potong", "perm": ("wms", "scan"),
                "complete": False, "order": 5},
    "cycle_count": {"label": "Stock Opname RFID", "hint": "Sapu RFID per gudang", "perm": ("wms", "scan"),
                    "complete": True, "order": 6},
    "print_verify": {"label": "Verifikasi cetak", "hint": "Cocokkan EPC label tercetak", "perm": ("wms", "scan"),
                     "complete": True, "order": 7},
    "registration": {"label": "Daftar Awal", "hint": "Pendaftaran ulang roll fisik + tulis tag", "perm": ("inventory", "cycle_count"),
                     "complete": False, "order": 8},
}
TAG_WRITE_PERM = ("wms", "scan")          # sama dengan /rfid/tags/encode & retire

# Profil bawaan perangkat. Nilai = TITIK AWAL uji meja (belum terbukti di C72); commissioning menetapkan nilai akhir.
DEFAULT_PROFILE: Dict[str, Any] = {
    "profile_id": "c72-bawaan",
    "commissioned": False,
    "rfid": {"power_dbm": 20, "write_power_dbm": 10, "locate_power_dbm": 26, "session": 0, "region_code": None,
             "max_power_dbm": 30, "min_power_dbm": 5},
    "trigger": {"keycodes": [139, 280, 291, 293, 294, 311, 312, 313, 315], "mode": "hold"},
    "batch": {"max_reads": 2000, "flush_ms": 4000, "max_labels": 500},
    "offline": {"allowed": True, "snapshot_max_age_hours": 12},
    "write": {"verify_reads": 2, "max_attempts": 3, "min_rssi_gap_db": 6.0, "scan_ms": 1500},
    "locate": {"enabled": True, "use_sdk_locate": True},
    "sync": {"interval_ms": 15000, "backoff_max_ms": 300000},
}
PROFILE_LIMITS = {"power_dbm": (5, 30), "write_power_dbm": (5, 30), "locate_power_dbm": (5, 30), "session": (0, 3)}


def err(status: int, code: str, message: str, retryable: bool = False, **details: Any) -> HTTPException:
    """Galat terstruktur (pola kontrak V2): {detail: {code, message, retryable, details}}."""
    return HTTPException(status_code=status, detail={"code": code, "message": message, "retryable": retryable,
                                                     "details": details or {}})


def digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ─── Perangkat ────────────────────────────────────────────────────────────────
async def device_from(request: Request) -> Dict[str, Any]:
    from services import rfid_ingest_service as ing
    key = request.headers.get("X-Device-Key")
    if not key:
        raise err(401, "DEVICE_KEY_REQUIRED", "Header X-Device-Key wajib — provisioning perangkat dulu.")
    try:
        dev = await ing.authenticate(key)
    except HTTPException as exc:
        if exc.status_code == 403:
            raise err(403, "DEVICE_DISABLED", "Perangkat ini dinonaktifkan/dicabut admin ERP — hubungi admin gudang.") from exc
        raise err(401, "DEVICE_KEY_INVALID", "Device key tidak dikenal — provisioning ulang perangkat.") from exc
    if dev.get("type") != "handheld":
        raise err(403, "DEVICE_NOT_HANDHELD", "Device key ini bukan milik perangkat handheld.")
    return dev


async def device_warehouses(device: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Gudang yang boleh dilayani perangkat: seluruh gudang di site gudang perangkat (bawaan) atau gudangnya saja."""
    wh = await db.warehouses.find_one({"id": device.get("warehouse_id")}, {"_id": 0, "id": 1, "code": 1, "name": 1, "site_id": 1})
    if not wh:
        return []
    if device.get("handheld_scope_level") == "warehouse" or not wh.get("site_id"):
        return [wh]
    return await db.warehouses.find({"site_id": wh["site_id"], "active": {"$ne": False}},
                                    {"_id": 0, "id": 1, "code": 1, "name": 1, "site_id": 1}).sort("code", 1).to_list(200)


def profile_of(device: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(DEFAULT_PROFILE)
    for k, v in (device.get("handheld_profile") or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def validate_profile(raw: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise err(400, "PROFILE_INVALID", "Profil harus objek JSON.")
    unknown = set(raw) - set(DEFAULT_PROFILE)
    if unknown:
        raise err(400, "PROFILE_INVALID", f"Kunci profil tidak dikenal: {sorted(unknown)}")
    rf = raw.get("rfid") or {}
    for k, (lo, hi) in PROFILE_LIMITS.items():
        if k in rf and rf[k] is not None and not (isinstance(rf[k], int) and lo <= rf[k] <= hi):
            raise err(400, "PROFILE_INVALID", f"rfid.{k} harus bilangan bulat {lo}–{hi}.")
    keys = (raw.get("trigger") or {}).get("keycodes")
    if keys is not None and (not isinstance(keys, list) or not all(isinstance(x, int) and 0 < x < 1000 for x in keys)):
        raise err(400, "PROFILE_INVALID", "trigger.keycodes harus daftar kode tombol (bilangan bulat).")
    mode = (raw.get("trigger") or {}).get("mode")
    if mode is not None and mode not in ("hold", "toggle"):
        raise err(400, "PROFILE_INVALID", "trigger.mode harus 'hold' atau 'toggle'.")
    return raw


async def touch_device(device: Dict[str, Any], app_version: str = "") -> None:
    upd: Dict[str, Any] = {"status": "online", "last_heartbeat": now_iso()}
    if app_version:
        upd["handheld_app_version"] = str(app_version)[:40]
    await db.rfid_devices.update_one({"id": device["id"], "enabled": {"$ne": False}}, {"$set": upd})


async def device_config(device: Dict[str, Any], app_version: str = "") -> Dict[str, Any]:
    await touch_device(device, app_version)
    whs = await device_warehouses(device)
    home = next((w for w in whs if w["id"] == device.get("warehouse_id")), {})
    site = await db.warehouse_sites.find_one({"id": home.get("site_id")}, {"_id": 0, "id": 1, "name": 1}) if home.get("site_id") else None
    prof = profile_of(device)
    return {"api_version": API_VERSION, "min_app_version": MIN_APP_VERSION, "server_time": now_iso(),
            "device": {"id": device["id"], "code": device.get("code"), "name": device.get("name"),
                       "warehouse_id": device.get("warehouse_id"), "warehouse_name": home.get("name"),
                       "site_id": home.get("site_id"), "site_name": (site or {}).get("name"),
                       "scope_level": device.get("handheld_scope_level") or "site",
                       "warehouses": [{"id": w["id"], "code": w.get("code"), "name": w.get("name")} for w in whs]},
            "profile": prof, "profile_version": digest(prof)[:16],
            "kinds": [{"code": k, "label": v["label"], "hint": v["hint"], "complete": v["complete"]}
                      for k, v in sorted(KINDS.items(), key=lambda kv: kv[1]["order"])],
            "limits": {"max_reads_per_batch": 2000, "max_labels_per_batch": 500, "max_lines_per_batch": 50,
                       "expected_page_max": 5000, "epc_pool_max": 200}}


# ─── Konteks kerja (perangkat + pengguna) ─────────────────────────────────────
class HandheldCtx:
    """Satu permintaan kerja: perangkat, pengguna, PT dalam cakupan, gudang efektif."""

    def __init__(self, device: Dict[str, Any], user: Dict[str, Any], entity_ids: List[str], warehouses: List[Dict[str, Any]],
                 user_warehouse_ids: Optional[List[str]]):
        self.device = device
        self.user = user
        self.entity_ids = entity_ids
        self.warehouses = warehouses
        self.warehouse_ids = [w["id"] for w in warehouses]
        self.user_warehouse_ids = user_warehouse_ids

    @property
    def actor_name(self) -> str:
        return self.user.get("name") or self.user.get("email") or "Operator handheld"

    @property
    def source(self) -> str:
        return f"handheld:{self.device.get('code') or self.device['id']}"

    def wh_name(self, wid: Optional[str]) -> str:
        return next((w.get("name") or w.get("code") or w["id"] for w in self.warehouses if w["id"] == wid), wid or "")

    def assert_warehouse(self, wid: Optional[str], what: str = "dokumen ini") -> None:
        if wid not in self.warehouse_ids:
            raise err(403, "SCOPE_DENIED", f"{what[:1].upper() + what[1:]} berada di gudang di luar cakupan perangkat & lokasi "
                                           "kerja Anda — kerjakan dengan perangkat gudang itu atau minta supervisor.",
                      warehouse_id=wid)


async def context(request: Request, perm: Optional[tuple] = None) -> HandheldCtx:
    from dependencies import current_user, has_permission
    from entity_scope import entity_ctx
    from services import location_scope
    device = await device_from(request)
    user = await current_user(request)
    if perm and not await has_permission(user, perm[0], perm[1]):
        raise err(403, "PERMISSION_DENIED", f"Izin {perm[0]}.{perm[1]} diperlukan untuk pekerjaan ini.")
    ectx = await entity_ctx(request)
    entity_ids = list(dict.fromkeys(ectx.allowed_entity_ids or [ectx.active_entity_id]))
    dev_whs = await device_warehouses(device)
    user_ids = await location_scope.warehouse_ids_for(user)
    whs = dev_whs if user_ids is None else [w for w in dev_whs if w["id"] in set(user_ids)]
    await touch_device(device)
    return HandheldCtx(device, user, entity_ids, whs, user_ids)


async def kind_context(request: Request, kind: str) -> HandheldCtx:
    spec = KINDS.get(kind)
    if not spec:
        raise err(404, "KIND_UNKNOWN", f"Jenis tugas '{kind}' tidak dikenal.", kinds=sorted(KINDS))
    return await context(request, spec["perm"])


async def allowed_kinds(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    from dependencies import has_permission
    out = []
    for k, v in sorted(KINDS.items(), key=lambda kv: kv[1]["order"]):
        out.append({"code": k, "label": v["label"], "hint": v["hint"], "complete": v["complete"],
                    "allowed": await has_permission(user, *v["perm"]), "permission": ".".join(v["perm"])})
    return out


# ─── Sesi operator ────────────────────────────────────────────────────────────
async def start_operator(ctx: HandheldCtx, app_version: str = "") -> Dict[str, Any]:
    now = now_iso()
    await db[OPS].update_many({"device_id": ctx.device["id"], "ended_at": None},
                              {"$set": {"ended_at": now, "end_reason": "ganti operator / login ulang"}})
    op = {"id": new_id("hos"), "device_id": ctx.device["id"], "device_code": ctx.device.get("code"),
          "user_id": ctx.user["id"], "user_name": ctx.actor_name, "user_email": ctx.user.get("email"),
          "warehouse_ids": ctx.warehouse_ids, "app_version": str(app_version or "")[:40],
          "started_at": now, "last_seen_at": now, "ended_at": None}
    await db[OPS].insert_one(dict(op))
    return op


async def end_operator(ctx: HandheldCtx, op_id: str, reason: str = "") -> Dict[str, Any]:
    res = await db[OPS].find_one_and_update(
        {"id": op_id, "device_id": ctx.device["id"], "user_id": ctx.user["id"]},
        {"$set": {"ended_at": now_iso(), "end_reason": (reason or "logout")[:200]}}, projection={"_id": 0})
    if not res:
        raise err(404, "OPERATOR_SESSION_UNKNOWN", "Sesi operator tidak ditemukan untuk perangkat & pengguna ini.")
    return res


async def assert_operator(ctx: HandheldCtx, op_id: Optional[str], claimed_user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Bukti milik operator yang menangkapnya: sesi operator harus milik perangkat + pengguna token ini."""
    if claimed_user_id and claimed_user_id != ctx.user["id"]:
        raise err(409, "OPERATOR_MISMATCH", "Antrean ini ditangkap operator lain — kirim dengan login operator tersebut.",
                  captured_by=claimed_user_id)
    if not op_id:
        return None
    op = await db[OPS].find_one({"id": op_id}, {"_id": 0})
    if not op or op.get("device_id") != ctx.device["id"] or op.get("user_id") != ctx.user["id"]:
        raise err(409, "OPERATOR_MISMATCH", "Sesi operator pada antrean bukan milik perangkat & pengguna ini.")
    await db[OPS].update_one({"id": op_id}, {"$set": {"last_seen_at": now_iso()}})
    return op


async def me(ctx: HandheldCtx, op: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    u = ctx.user
    return {"server_time": now_iso(), "operator_session": op,
            "user": {"id": u["id"], "name": ctx.actor_name, "email": u.get("email"), "role": u.get("role")},
            "device": {"id": ctx.device["id"], "code": ctx.device.get("code"), "name": ctx.device.get("name")},
            "warehouses": [{"id": w["id"], "code": w.get("code"), "name": w.get("name")} for w in ctx.warehouses],
            "location_restricted": ctx.user_warehouse_ids is not None, "entity_ids": ctx.entity_ids,
            "kinds": await allowed_kinds(u)}
