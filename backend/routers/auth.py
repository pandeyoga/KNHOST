"""Auth router: login, logout, me, context (F0-A multi-entity identity).

Gelombang 3 SEC-1/SEC-2:
- bcrypt password hashing + migrasi transparan SHA256→bcrypt (rehash saat login sukses)
- session token 256-bit + TTL (index Mongo) + HttpOnly cookie (fallback Bearer tetap didukung)
- lockout brute-force: 5 percobaan gagal per IP+email → kunci 15 menit
"""
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request, Response
from pymongo import ReturnDocument
from db import db
from dependencies import current_user, audit, extract_token, session_expiry, SESSION_COOKIE, permission_matrix
from core_utils import hash_password, verify_password, is_legacy_hash, new_id, now_iso, safe_doc
from schemas import LoginRequest
from services.entity_context_service import build_entity_context
from role_registry import role_label

# T-02 (audit 2026-09) — flag cookie sesi dari env, aman secara bawaan (Secure=true).
# Dev lewat http://localhost wajib SESSION_COOKIE_SECURE=false di backend/.env.
COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "true").lower() not in ("false", "0", "no")
COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "lax")

router = APIRouter(prefix="/api")

# KF-T7 (#67) — batas salah sandi (dulu 5 kali) dan lama akun dikunci (dulu 15 menit) kini pengaturan
# `keamanan.maks_salah_sandi` / `keamanan.lama_kunci_menit` (kelompok "Keamanan akun & sesi"), dibaca `_register_failure`.


async def _my_permissions(user: Dict[str, Any]) -> Dict[str, Any]:
    """FASE E-8 (E8.1) — izin efektif MILIK pengguna ini + label perannya.

    KENAPA: layar dulu menebak wewenang dari literal peran
    (`["admin","manager"].includes(role)`), tersebar di ~81 tempat. Begitu ada peran
    baru, tombol yang seharusnya hidup untuk Admin Sales/Finance tetap mati padahal
    server mengizinkan — atau sebaliknya tombol hidup lalu ditolak 403 (UX terburuk:
    pengguna menyalahkan dirinya). Dengan mengirim matriks izin miliknya sendiri,
    layar bertanya `can(perms, "interco", "create")` — jawaban yang SAMA dengan
    penjaga di server, karena sumbernya satu.
    """
    matrix = await permission_matrix()
    role = user.get("role") or ""
    return {
        "role": role,
        "role_label": role_label(role),
        "role_label_long": role_label(role, long=True),
        "permissions": matrix.get(role, {}) or {},
    }


async def _my_nav(role: str) -> Dict[str, Any]:
    from access_modules import view_actions_index, view_resources_index
    from services.custom_role_service import hidden_views_of
    return {"hidden_views": [] if role == "admin" else await hidden_views_of(role),
            "view_resources": view_resources_index(),
            "view_actions": view_actions_index()}   # PR-T5 — menu yang butuh aksi tertentu (meja peran)


# PR-T7 — tautan karyawan dibaca dari SUMBER YANG SAMA dengan `GET /api/hr/employees/me` (`hr_employees.user_id`).
# `users.employee_id` tidak cukup: proses awal menautkan karyawan hanya dari sisi HR (data acuan: 14 dari 17 akun
# tertaut tanpa `users.employee_id`). Layar Profil Saya tidak memanggil `/hr/employees/me` bila nilainya kosong.
async def _employee_id_of(user: Dict[str, Any]) -> str:
    from services.hr_service import employee_id_of_user
    return await employee_id_of_user(user.get("id") or "")


async def _roles_list() -> list:
    """PR-T7 (PR-UX-41) — daftar peran berbentuk `GET /api/roles`, supaya peran kustom terdaftar di layar SEBELUM
    layar pertama digambar (dulu beranda sementara = beranda Sales sampai `/roles` dijawab)."""
    from role_registry import public_list
    from services.custom_role_service import sync_registry
    await sync_registry()
    return public_list()


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _check_lockout(identifier: str) -> None:
    rec = await db.login_attempts.find_one({"identifier": identifier})
    if not rec:
        return
    locked_until = rec.get("locked_until")
    if isinstance(locked_until, datetime) and not locked_until.tzinfo:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if locked_until and locked_until > datetime.now(timezone.utc):
        sisa = int((locked_until - datetime.now(timezone.utc)).total_seconds() // 60) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Terlalu banyak percobaan login gagal. Coba lagi dalam {sisa} menit.")


async def _register_failure(identifier: str) -> None:
    from services.nilai_pengaturan import nilai
    rec = await db.login_attempts.find_one_and_update(
        {"identifier": identifier},
        {"$inc": {"count": 1}, "$set": {"last_attempt_at": datetime.now(timezone.utc)}},
        upsert=True, return_document=ReturnDocument.AFTER)
    if rec and rec.get("count", 0) >= int(await nilai("keamanan.maks_salah_sandi")):
        menit = int(await nilai("keamanan.lama_kunci_menit"))
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$set": {"locked_until": datetime.now(timezone.utc) + timedelta(minutes=menit),
                      "count": 0}})


@router.post("/auth/login")
async def login(payload: LoginRequest, request: Request, response: Response) -> Dict[str, Any]:
    email = (payload.email or "").strip()
    identifier = f"{_client_ip(request)}:{email.lower()}"
    await _check_lockout(identifier)
    user = safe_doc(await db.users.find_one({"email": email, "status": "active"}, {"_id": 0}))
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        await _register_failure(identifier)
        raise HTTPException(status_code=401, detail="Email atau password tidak sesuai")
    await db.login_attempts.delete_one({"identifier": identifier})
    # FASE E-1 (E1.6) — badan usaha utama sudah DIARSIPKAN → tidak boleh masuk.
    # Pesannya menyebut nama badan usahanya supaya pengguna tahu harus minta apa ke
    # admin (dipindahkan ke badan usaha lain), bukan menyangka passwordnya salah.
    home_id = user.get("home_entity_id") or ""
    if home_id:
        from services.entity_lifecycle_service import entity_status_map, WRITE_LOCKED_STATUSES
        info = (await entity_status_map()).get(home_id)
        if info and info["status"] in WRITE_LOCKED_STATUSES:
            raise HTTPException(
                status_code=403,
                detail=f"Akun Anda terdaftar di “{info['name']}” yang sudah diarsipkan, "
                       "jadi belum bisa masuk. Minta admin memindahkan akun Anda ke "
                       "badan usaha yang aktif.")
    # FASE E-2 (E2.5) — catat waktu login terakhir supaya daftar akun bisa menunjukkan
    # akun mana yang benar-benar dipakai (dulu kolom ini kosong selamanya).
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_login_at": now_iso()}})
    if is_legacy_hash(user.get("password_hash", "")):
        # SEC-1 — migrasi transparan SHA256 → bcrypt saat login sukses
        await db.users.update_one({"id": user["id"]},
                                  {"$set": {"password_hash": hash_password(payload.password)}})
    token = secrets.token_urlsafe(32)  # SEC-2 — entropi 256-bit
    # FIX-1 (audit B1b UI-44) — sesi cookie LAMA di peramban ini (pengguna sebelumnya yang "Keluar" tanpa mencapai
    # server) dicabut saat login baru: satu peramban = satu sesi, tidak ada sesi tertinggal yang bisa dipakai lagi.
    _old_cookie = request.cookies.get(SESSION_COOKIE) or ""
    if _old_cookie:
        await db.sessions.delete_one({"token": _old_cookie})
    # KF-T7 (#68) — umur sesi = `keamanan.umur_sesi_jam` saat sesi dibuat; dicatat di sesi (`ttl_hours`) supaya
    # perpanjangan memakai umur sesinya sendiri (sesi yang sudah ada tidak ikut berubah saat pengaturan diubah).
    from services.nilai_pengaturan import nilai
    ttl_jam = int(await nilai("keamanan.umur_sesi_jam"))
    await db.sessions.insert_one(
        {"id": new_id("session"), "token": token, "user_id": user["id"],
         "created_at": now_iso(), "expires_at": session_expiry(ttl_jam), "ttl_hours": ttl_jam})
    response.set_cookie(SESSION_COOKIE, token, httponly=True, secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE,
                        max_age=ttl_jam * 3600, path="/")
    user.pop("password_hash", None)
    # FASE E-0 (L7) — jejak login distempel ke entitas HOME pengguna. Tanpa ini baris
    # login menumpuk sebagai "tingkat grup" dan laporan audit per entitas jadi bolong.
    await audit(user["name"], "login", "user", user["id"],
                {"email": user["email"], "role": user["role"]},
                scope_entity_id=user.get("home_entity_id") or "")
    onboarding = safe_doc(await db.user_onboarding.find_one({"user_id": user["id"]}, {"_id": 0}))
    entity_context = await build_entity_context(user)
    perms = await _my_permissions(user)
    user["role_label"] = perms["role_label"]
    user["employee_id"] = await _employee_id_of(user)   # PR-T7
    # PR-T7 (PR-UX-41) — konteks izin LENGKAP sejak jawaban login (sama dengan `GET /api/auth/me`) + daftar peran:
    # dulu `view_resources` baru datang dari `/auth/me`, dan selama itu `canCurrent()` menjawab "boleh".
    return {"token": token, "user": user, "onboarding": onboarding,
            "entity_context": entity_context, **perms, **(await _my_nav(user.get("role") or "")),
            "roles": await _roles_list()}


@router.get("/roles")
async def list_roles(request: Request) -> Dict[str, Any]:
    """FASE E-8 (E8.1) — daftar peran YANG SAH + penjelasannya (registry peran).

    Dipakai formulir akun di layar "Badan Usaha & Akses" supaya pilihan peran tidak
    pernah bercabang dari kebenaran server, dan supaya peran baru muncul otomatis.
    """
    await current_user(request)   # cukup terautentikasi: ini daftar referensi
    from role_registry import public_list
    from services.custom_role_service import sync_registry
    await sync_registry()
    return {"roles": public_list()}


@router.get("/auth/me")
async def me(request: Request) -> Dict[str, Any]:
    """User aktif + entity context (active = header X-Entity-Id bila valid)."""
    user = await current_user(request)
    requested = request.headers.get("X-Entity-Id")
    user["entity_context"] = await build_entity_context(user, requested)
    perms = await _my_permissions(user)
    user["role_label"] = perms["role_label"]
    user["permissions"] = perms["permissions"]
    user["employee_id"] = await _employee_id_of(user)   # PR-T7
    user.update(await _my_nav(user.get("role") or ""))
    return user


@router.get("/auth/context")
async def auth_context(request: Request) -> Dict[str, Any]:
    """Entity context terpisah (dipakai Entity Switcher / refresh konteks)."""
    user = await current_user(request)
    requested = request.headers.get("X-Entity-Id")
    return await build_entity_context(user, requested)


@router.post("/auth/logout")
async def logout(request: Request, response: Response) -> Dict[str, str]:
    # FIX-1 (audit B1b UI-44) — cabut SEMUA sesi yang dibawa permintaan ini (Bearer & cookie bisa berbeda di peramban
    # bersama), lalu hapus cookie. Dulu hanya satu token (cookie diutamakan) dan aplikasi tidak memanggil endpoint ini.
    tokens = {t for t in (extract_token(request), request.cookies.get(SESSION_COOKIE) or "") if t}
    if tokens:
        await db.sessions.delete_many({"token": {"$in": list(tokens)}})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"message": "Keluar berhasil"}
