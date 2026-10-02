"""Shared auth/permission dependencies and audit helper."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, Request
from db import db
from core_utils import safe_doc, now_iso, new_id, SESSION_TTL_HOURS
from permissions_config import DEFAULT_PERMISSIONS

SESSION_COOKIE = "session_token"

# FASE E-1 (E1.6) — metode yang MENGUBAH data; dipakai penjaga kunci-tulis entitas.
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def session_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)


def _as_utc(dt: Any) -> Optional[datetime]:
    if isinstance(dt, datetime):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def extract_token(request: Request) -> str:
    """SEC-2 — HttpOnly cookie diutamakan; fallback header Bearer (kompat)."""
    token = request.cookies.get(SESSION_COOKIE) or ""
    if not token:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            token = header.replace("Bearer ", "").strip()
    return token


async def current_user(request: Request) -> Dict[str, Any]:
    token = extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Login diperlukan")
    session = await db.sessions.find_one({"token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Session tidak valid")
    now = datetime.now(timezone.utc)
    expires_at = _as_utc(session.get("expires_at"))
    if expires_at is None:
        # sesi pra-TTL: beri masa berlaku agar ikut kebijakan kedaluwarsa
        await db.sessions.update_one({"token": token}, {"$set": {"expires_at": session_expiry()}})
    elif expires_at <= now:
        await db.sessions.delete_one({"token": token})
        raise HTTPException(status_code=401, detail="Session kedaluwarsa — silakan login ulang")
    elif (expires_at - now) < timedelta(hours=SESSION_TTL_HOURS / 2):
        # sliding renewal: perpanjang saat sisa < setengah TTL
        await db.sessions.update_one({"token": token}, {"$set": {"expires_at": session_expiry()}})
    user = safe_doc(await db.users.find_one({"id": session["user_id"], "status": "active"}, {"_id": 0, "password_hash": 0}))
    if not user:
        raise HTTPException(status_code=401, detail="User tidak aktif")
    # FASE E-0 (E0.3) — isi ContextVar supaya `audit()` bisa menstempel entitas tanpa
    # mengubah 62 pemanggilnya satu-satu.
    from request_context import resolve_from_user, set_active_entity, set_actor
    set_actor(user)
    # FASE E-1 (E1.5) — konteks entitas yang diminta WAJIB sah untuk SEMUA metode.
    # Dipasang sebelum resolusi supaya tidak ada lagi "jatuh diam-diam ke HOME".
    from services.entity_lifecycle_service import assert_requested_entity_allowed
    await assert_requested_entity_allowed(request, user)
    active_entity = resolve_from_user(user, request.headers.get("X-Entity-Id", ""))
    set_active_entity(active_entity)
    # FASE E-1 (E1.6) — KUNCI-TULIS badan usaha terarsip, dipasang di SATU choke point.
    # Semua endpoint terautentikasi lewat sini, jadi tidak ada jalur tulis yang lupa
    # dipagari. Baca tetap diizinkan supaya data lama bisa diaudit/dilaporkan.
    if request.method in MUTATING_METHODS and active_entity:
        from services.entity_lifecycle_service import assert_entity_writable_cached
        await assert_entity_writable_cached(active_entity)
    # FASE E-1 (E1.10) — PAGAR TULIS LINTAS BADAN USAHA. Body yang menyebut
    # `entity_id`/`owner_entity_id` di luar penugasan user ditolak 403 di sini,
    # sekali untuk semua endpoint (temuan POC E-1: sisi TULIS belum terpagari).
    if request.method in MUTATING_METHODS:
        from services.entity_lifecycle_service import assert_body_entity_allowed
        await assert_body_entity_allowed(request, user)
    return user


async def require_role(request: Request, allowed_roles: List[str]) -> Dict[str, Any]:
    import role_registry as reg
    user = await current_user(request)
    if user.get("role") == "admin" or reg.role_in(user.get("role"), allowed_roles):
        return user
    raise HTTPException(status_code=403, detail="Role Anda tidak memiliki izin untuk aksi ini")


async def permission_matrix() -> Dict[str, Dict[str, List[str]]]:
    record = safe_doc(await db.permission_settings.find_one({"id": "default"}, {"_id": 0}))
    return record.get("matrix", DEFAULT_PERMISSIONS) if record else DEFAULT_PERMISSIONS


async def has_permission(user: Dict[str, Any], module: str, action: str) -> bool:
    """Cek izin tanpa melempar (untuk cabang "boleh override?")."""
    allowed = (await permission_matrix()).get(user.get("role"), {}).get(module, [])
    return action in allowed or "*" in allowed


async def require_permission(request: Request, module: str, action: str) -> Dict[str, Any]:
    user = await current_user(request)
    if await has_permission(user, module, action):
        return user
    raise HTTPException(status_code=403, detail=f"Permission ditolak: {module}.{action}")


async def require_any_permission(request: Request,
                                 options: List[tuple]) -> Dict[str, Any]:
    """Izin "SALAH SATU dari" — untuk layar yang menyatukan beberapa domain.

    FASE E-9 (E9.6): satu rantai retur memuat tiga dokumen milik tiga domain
    berbeda (retur pelanggan · retur antar-PT · retur beli). Kalau izinnya dipaksa
    hanya `sales_return.view`, orang gudang/pembelian yang sedang membuka
    **retur belinya sendiri** justru ditolak 403 — layar rantai jadi jalan buntu
    tepat di dokumen miliknya. Aturannya: cukup berhak atas SALAH SATU domain
    dalam rantai; pembatasan isi per badan usaha dikerjakan lapisan scope.
    """
    user = await current_user(request)
    matrix = await permission_matrix()
    role_perms = matrix.get(user.get("role"), {})
    for module, action in options:
        allowed = role_perms.get(module, [])
        if action in allowed or "*" in allowed:
            return user
    opts = " / ".join(f"{m}.{a}" for m, a in options)
    raise HTTPException(status_code=403,
                        detail=f"Permission ditolak: butuh salah satu dari {opts}")


_SECRET_KEY_HINTS = ("password", "passwd", "secret", "token", "api_key", "apikey", "private_key",
                     "hash", "otp", "session", "credential", "pin")
_REDACTED = "[REDACTED]"


def _redact(v: Any) -> Any:
    """GN-14 — jejak audit tidak boleh memuat secret: kunci bernuansa rahasia diganti penanda."""
    if isinstance(v, dict):
        return {k: (_REDACTED if any(h in str(k).lower() for h in _SECRET_KEY_HINTS) and v[k] not in (None, "")
                    else _redact(v[k])) for k in v}
    if isinstance(v, list):
        return [_redact(x) for x in v]
    return v


def audit_diff(before: Any, after: Any) -> List[Dict[str, Any]]:
    """Field yang berubah (level atas) dari before → after; after parsial hanya membandingkan kuncinya."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        return []
    skip = {"updated_at", "_id"}
    return [{"field": k, "from": before.get(k), "to": after.get(k)}
            for k in after if k not in skip and before.get(k) != after.get(k)]


async def audit(
    actor: str, action: str, entity_type: str, entity_id: str, after: Any, reason: str = "",
    scope_entity_id: str = "", before: Any = None, source: str = "",
    masked_fields: Optional[List[str]] = None,
) -> None:
    """Tulis satu baris jejak audit.

    CATATAN PENTING: `entity_type`/`entity_id` di sini adalah **sumber daya** yang
    diubah (mis. `sales_orders` / `so_001`) — BUKAN badan usaha. Badan usaha disimpan
    pada `scope_entity_id` (FASE E-0 / L7) supaya jejak bisa disaring per entitas
    tanpa memutus arti kolom lama.

    `scope_entity_id` diisi otomatis dari `request_context` (diset oleh
    `current_user`); parameter eksplisit hanya untuk job/skrip di luar request.
    """
    # Clean after data to remove any MongoDB ObjectIds recursively
    clean_after = _redact(safe_doc(after)) if after is not None else None
    clean_before = _redact(safe_doc(before)) if before is not None else None
    # P14 — field sensitif (gaji, rekening): perubahan dicatat, nilainya disamarkan.
    masked = list(masked_fields or [])
    if masked:
        clean_before = {**(clean_before or {}), **{f: _REDACTED for f in masked}}
        clean_after = {**(clean_after or {}), **{f: _REDACTED for f in masked}}
    scope = scope_entity_id
    if not scope:
        try:
            from request_context import get_active_entity
            scope = get_active_entity() or ""
        except Exception:  # noqa: BLE001 — audit tidak boleh menggagalkan aksi bisnis
            scope = ""
    role, actor_id = "system/demo", ""
    try:
        from request_context import get_actor
        _a = get_actor() or {}
        role = _a.get("role") or role
        actor_id = _a.get("id") or ""
    except Exception:  # noqa: BLE001
        pass
    row = {
        "id": new_id("audit"),
        "actor": actor,
        "actor_id": actor_id,
        "role": role,
        "action": action,
        "source": source or action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "scope_entity_id": scope or None,
        "before": clean_before,
        "after": clean_after,
        "diff": audit_diff(clean_before, clean_after)
        + [{"field": f, "from": _REDACTED, "to": _REDACTED, "masked": True} for f in masked],
        "masked_fields": masked,
        "reason": reason,
        "timestamp": now_iso(),
    }
    # GN-14 — sidik isi (tamper-evident): perubahan baris audit sesudahnya terdeteksi saat verifikasi.
    import hashlib
    import json as _json
    row["content_hash"] = hashlib.sha256(
        _json.dumps(row, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()
    await db.audit_logs.insert_one(row)
    # Notifikasi "giliran Anda" (2026-09): fire-and-forget; tidak pernah menggagalkan aksi bisnis.
    try:
        from services.turn_notification_service import after_audit
        after_audit(entity_type, entity_id)
    except Exception:  # noqa: BLE001
        pass
