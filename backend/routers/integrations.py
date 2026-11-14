"""H5 router — Integrasi AI (Anthropic Claude) config.

Scope `integrations` di system_settings. Key API TIDAK pernah dikembalikan plaintext — GET hanya mengembalikan
`has_key`. Lihat memory/PLAN_HRD.md §10b HR-Q5.

KP-T8 (KP-32) — delapan endpoint di sini dijaga izin sendiri `integration.manage` (modul Pusat Pengaturan; dulu
`hr.manage_settings`, yang tetap menjaga pengaturan SDM). Koneksi WhatsApp tunggal untuk Pengingat dan Kirim Dokumen
(KP-16) diatur di `/admin/integrations/whatsapp…`; hidup/mati & model pengenal gambar (KP-31) di Pusat Pengaturan.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from access_modules import module_label_of
from dependencies import require_permission, audit
from schemas_integrations import IntegrationsUpdate
from services import integrations_service as integ
from services import wa_connection

router = APIRouter(prefix="/api")

#: Z6 — kalimat 403 untuk manusia (modul pemilik sumber daya `integration`, saat ini "Pusat Pengaturan").
PESAN_403 = ("Anda belum punya akses untuk mengatur integrasi. "
             f"Minta Admin menambahkan akses '{module_label_of('integration')}'.")
PESAN_DI_REGISTRY = "Hidup/mati dan model diatur di Pengaturan › Integrasi & Sistem › AI & Tampilan."


class WaConnectionUpdate(BaseModel):
    """Koneksi WhatsApp tunggal. Token kosong/tidak dikirim = tidak diubah; `clear_tokens` menghapus keduanya."""
    provider: Optional[str] = None
    access_token: Optional[str] = None
    fonnte_token: Optional[str] = None
    phone_number_id: Optional[str] = None
    sender: Optional[str] = None
    sender_label: Optional[str] = None
    default_country_code: Optional[str] = None
    template_name: Optional[str] = None
    template_lang: Optional[str] = None
    clear_tokens: bool = False


class WaAdoptBody(BaseModel):
    from_: str = Field(alias="from")
    reason: str = ""


class WaConnectionTest(BaseModel):
    phone: str
    text: Optional[str] = None


@router.get("/admin/integrations")
async def get_integrations(request: Request) -> Dict[str, Any]:
    """Config integrasi ter-MASK (api_key → has_key) + `secrets_key_configured`."""
    await require_permission(request, "integration", "manage", PESAN_403)
    return await integ.get_integrations_public()


@router.put("/admin/integrations")
async def update_integrations(payload: IntegrationsUpdate, request: Request) -> Dict[str, Any]:
    """Set/clear kunci penyedia. Return config ter-mask. KP-T8 — hidup/mati & model pengenal gambar ditolak di sini."""
    actor = await require_permission(request, "integration", "manage", PESAN_403)
    patch = payload.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=400, detail="Tidak ada perubahan dikirim.")
    if "anthropic_enabled" in patch or "anthropic_model" in patch:
        raise HTTPException(status_code=400, detail=PESAN_DI_REGISTRY)
    res = await integ.update_integrations(patch)
    # Audit TANPA membocorkan key (catat hanya status perubahan).
    await audit(actor["name"], "integrations_update", "system_settings", "integrations",
                {"key_changed": bool(patch.get("anthropic_api_key") or patch.get("anthropic_clear_key")
                                     or patch.get("gemini_api_key") or patch.get("gemini_clear_key")
                                     or patch.get("openai_api_key") or patch.get("openai_clear_key")),
                 "model": res["anthropic"]["model"], "enabled": res["anthropic"]["enabled"],
                 "gemini_model": res["gemini"]["model"], "gemini_enabled": res["gemini"]["enabled"]})
    return res


@router.post("/admin/integrations/gemini/test")
async def test_gemini(request: Request) -> Dict[str, Any]:
    """G-3 — uji koneksi key Gemini (panggilan ringan). Lulus → `verified_at` diisi → status LIVE."""
    actor = await require_permission(request, "integration", "manage", PESAN_403)
    from services import gemini_image_service as gem
    from core_utils import now_iso
    cfg = await gem.resolve_config()
    if not cfg["api_key"]:
        raise HTTPException(status_code=400, detail="API key Gemini belum diisi.")
    try:
        res = await gem.test_connection(cfg["api_key"])
    except ValueError as e:
        await integ.update_integrations({"gemini_verified_at": ""})
        await audit(actor["name"], "integrations_gemini_test", "system_settings", "integrations",
                    {"ok": False, "error": str(e)[:200]})
        raise HTTPException(status_code=400, detail=str(e))
    ts = now_iso()
    await integ.update_integrations({"gemini_verified_at": ts})
    await audit(actor["name"], "integrations_gemini_test", "system_settings", "integrations",
                {"ok": True, "models_seen": res.get("models_seen")})
    return {"ok": True, "verified_at": ts, "model": cfg["model"], **res}


@router.post("/admin/integrations/openai/test")
async def test_openai(request: Request) -> Dict[str, Any]:
    """GRN Fase 4 — uji kunci OpenAI (daftar model; tanpa biaya token). Lulus → `verified_at` diisi."""
    actor = await require_permission(request, "integration", "manage", PESAN_403)
    from core_utils import now_iso
    from services import ocr_openai_client as oc
    key = await oc.resolve_key()
    if not key:
        raise HTTPException(status_code=400, detail="Kunci OpenAI belum diisi.")
    try:
        res = await oc.test_connection(key)
    except ValueError as e:
        await integ.update_integrations({"openai_verified_at": ""})
        await audit(actor["name"], "integrations_openai_test", "system_settings", "integrations", {"ok": False})
        raise HTTPException(status_code=400, detail=str(e))
    ts = now_iso()
    await integ.update_integrations({"openai_verified_at": ts})
    await audit(actor["name"], "integrations_openai_test", "system_settings", "integrations",
                {"ok": True, "models_seen": res.get("models_seen")})
    return {"ok": True, "verified_at": ts, **res}


# ═══ KP-T8 (KP-16) — koneksi WhatsApp tunggal ════════════════════════════════════
@router.get("/admin/integrations/whatsapp")
async def get_wa_connection(request: Request) -> Dict[str, Any]:
    """Koneksi tunggal (tanpa token) + pemakai + `conflict` bila dua konfigurasi lama berbeda."""
    await require_permission(request, "integration", "manage", PESAN_403)
    return await wa_connection.public_view()


@router.put("/admin/integrations/whatsapp")
async def put_wa_connection(payload: WaConnectionUpdate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "integration", "manage", PESAN_403)
    patch = payload.model_dump(exclude_unset=True)
    try:
        res = await wa_connection.simpan(patch, actor.get("name", ""))
    except wa_connection.KoneksiError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    await audit(actor["name"], "wa_connection_update", "system_settings", "integrations.whatsapp",
                {"provider": res.get("provider"),
                 "tokens_changed": bool(patch.get("access_token") or patch.get("fonnte_token")
                                        or patch.get("clear_tokens"))})
    return res


@router.post("/admin/integrations/whatsapp/adopt")
async def adopt_wa_connection(payload: WaAdoptBody, request: Request) -> Dict[str, Any]:
    """Dua koneksi lama berbeda → pemilik memilih satu untuk keduanya (alasan wajib)."""
    actor = await require_permission(request, "integration", "manage", PESAN_403)
    try:
        res = await wa_connection.adopt(payload.from_, payload.reason, actor.get("name", ""))
    except wa_connection.KoneksiError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    await audit(actor["name"], "wa_connection_adopt", "system_settings", "integrations.whatsapp",
                {"from": payload.from_, "provider": res.get("provider")}, payload.reason.strip())
    return res


@router.post("/admin/integrations/whatsapp/test")
async def test_wa_connection(payload: WaConnectionTest, request: Request) -> Dict[str, Any]:
    """Kirim uji lewat jalur `send_test` (dicatat di Outbox WhatsApp)."""
    actor = await require_permission(request, "integration", "manage", PESAN_403)
    from services import wa_alert_service as was
    try:
        row = await was.send_test(payload.phone, payload.text or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit(actor["name"], "wa_test_send", "sys_wa_outbox", row.get("id", ""),
                {"to": row.get("to"), "status": row.get("status"), "via": "integrations"})
    return row
