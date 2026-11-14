"""H5 service — Integrasi pihak ketiga (config runtime di system_settings).

Scope `integrations` di koleksi `system_settings`. Saat ini: Anthropic Claude
(untuk Design Gallery auto-tag). Pola deep-merge anti data-loss (cermin H4 `bpjs`).

KEAMANAN: `get_integrations_public()` MEMASK api_key → FE hanya menerima `has_key`.
Hanya `get_integrations()` (internal/service) yang membaca key plaintext.

KP-T8 — pembungkus rahasia pindah ke `services/secret_box.py` (awalan `enc:v1:` dan `KN_SECRETS_KEY` sama). Hidup/mati
dan model pengenal gambar (`anthropic.enabled`/`anthropic.model`) kini kunci registry `integrations.anthropic.*`
(Pusat Pengaturan); nilainya tetap tersimpan di dokumen ini lewat `LEGACY_SCOPED_PREFIXES`. Objek `whatsapp` di dokumen
yang sama = koneksi WhatsApp tunggal, dikelola `services/wa_connection.py` (tidak ikut `get_integrations`).
"""
from typing import Any, Dict

from db import db
from core_utils import new_id, now_iso
from services import secret_box
from services.hr_service import deep_merge

SCOPE = "integrations"

# Model Claude vision yang didukung (2026). Default = sonnet (daily driver).
ANTHROPIC_MODELS = ["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5"]
DEFAULT_MODEL = "claude-sonnet-4-6"

# FB-01 — Gemini "Nano Banana Pro" untuk ilustrasi AI galeri (mockup/modifikasi).
GEMINI_MODELS = ["gemini-3-pro-image-preview", "gemini-3.1-flash-image-preview"]
GEMINI_DEFAULT_MODEL = "gemini-3-pro-image-preview"
GEMINI_DEFAULT_DAILY_LIMIT = 10        # G-8: ilustrasi per desain per hari
GEMINI_DEFAULT_COST_USD = 0.134        # G-8: estimasi tarif Google per gambar (model Pro, 1K–2K px)

DEFAULT_INTEGRATIONS: Dict[str, Any] = {
    "anthropic": {"api_key": "", "model": DEFAULT_MODEL, "enabled": False},
    "gemini": {"api_key": "", "model": GEMINI_DEFAULT_MODEL, "enabled": True},
    "openai": {"api_key": "", "verified_at": ""},   # GRN Fase 4 — OCR surat jalan
}


_PROVIDERS = ("anthropic", "gemini", "openai")
_ENC_PREFIX = secret_box.PREFIX
#: KP-T8 — kunci dokumen yang bukan konfigurasi penyedia (koneksi WhatsApp tunggal: `wa_connection`).
_BUKAN_PENYEDIA = ("scope", "id", "created_at", "updated_at", "updated_by", "whatsapp")


async def get_integrations(strict: bool = True) -> Dict[str, Any]:
    """Config penuh (TERMASUK api_key terdekripsi) — hanya untuk service internal (AI call).

    KP-T8 — `strict=False` (layar & simpan): kunci terbungkus yang tidak bisa dibuka (KN_SECRETS_KEY hilang/berbeda)
    dibiarkan terbungkus dan galatnya dicatat di `_secret_errors[penyedia]`, supaya layar tetap terbuka dan simpan
    berikutnya tidak menghapus kunci itu."""
    rec = await db.system_settings.find_one({"scope": SCOPE}, {"_id": 0})
    stored = {k: v for k, v in (rec or {}).items() if k not in _BUKAN_PENYEDIA}
    plain = [p for p in _PROVIDERS
             if (stored.get(p) or {}).get("api_key")
             and not secret_box.is_sealed(stored[p]["api_key"])]
    if plain and secret_box.available():
        # Migrasi malas (temuan lama #18): kunci polos lama langsung dienkripsi.
        await db.system_settings.update_one({"scope": SCOPE}, {"$set": {
            f"{p}.api_key": secret_box.seal(stored[p]["api_key"]) for p in plain}})
    cfg = deep_merge(DEFAULT_INTEGRATIONS, stored)
    for p in _PROVIDERS:
        if (cfg.get(p) or {}).get("api_key"):
            try:
                cfg[p] = {**cfg[p], "api_key": secret_box.open(cfg[p]["api_key"])}
            except secret_box.SecretBoxError as exc:
                if strict:
                    raise
                cfg.setdefault("_secret_errors", {})[p] = str(exc)
    return cfg


async def get_integrations_public() -> Dict[str, Any]:
    """Config ter-mask untuk FE: api_key → has_key(bool). TIDAK pernah bocorkan key."""
    from services.config_resolver import value_of
    cfg = await get_integrations(strict=False)
    ant = cfg.get("anthropic", {})
    gem = cfg.get("gemini", {})
    import os as _os
    gem_key = bool(gem.get("api_key") or _os.environ.get("GEMINI_API_KEY"))
    oai = cfg.get("openai", {})
    oai_key = bool(oai.get("api_key") or _os.environ.get("OPENAI_API_KEY"))
    return {
        "openai": {"has_key": oai_key, "verified_at": oai.get("verified_at") or "",
                   "source": "integrasi" if oai.get("api_key") else ("env" if oai_key else "")},
        # KP-T8 (KP-31) — hidup/mati & model = nilai yang dipakai mesin (registry `integrations.anthropic.*`); diubah di
        # Pusat Pengaturan, bukan di kartu ini.
        "anthropic": {
            "has_key": bool(ant.get("api_key")),
            "model": str(await value_of("integrations.anthropic.model") or DEFAULT_MODEL),
            "enabled": bool(await value_of("integrations.anthropic.enabled")),
            "models_available": ANTHROPIC_MODELS,
        },
        "gemini": {
            "has_key": gem_key,
            "model": gem.get("model") or GEMINI_DEFAULT_MODEL,
            "enabled": bool(gem.get("enabled", True)),
            "demo_mode": False,
            "ready": gem_key and bool(gem.get('enabled', True)),
            "verified_at": gem.get("verified_at") or "",          # G-3: LIVE hanya setelah uji lulus
            "daily_limit": int(gem.get("daily_limit") or GEMINI_DEFAULT_DAILY_LIMIT),
            "cost_per_image_usd": float(gem.get("cost_per_image_usd") or GEMINI_DEFAULT_COST_USD),
            "models_available": GEMINI_MODELS,
        },
        # KP-T8 — status kunci enkripsi server + kunci terbungkus yang tidak bisa dibuka (tanpa isi kunci).
        "secrets_key_configured": secret_box.available(),
        "secret_errors": dict(cfg.get("_secret_errors") or {}),
    }


async def update_integrations(patch: Dict[str, Any]) -> Dict[str, Any]:
    """Update parsial config Anthropic (deep-merge; aturan key di schema).
    Mengembalikan config PUBLIC (ter-mask).

    KP-T8 — `anthropic_enabled`/`anthropic_model` tidak lagi diterima (ditolak router; Pusat Pengaturan). Kunci yang
    tidak bisa dibuka tetap tersimpan terbungkus (`strict=False`)."""
    current = await get_integrations(strict=False)
    ant = dict(current.get("anthropic", {}))
    if patch.get("anthropic_clear_key"):
        ant["api_key"] = ""
    elif patch.get("anthropic_api_key"):
        ant["api_key"] = str(patch["anthropic_api_key"]).strip()
    gem = dict(current.get("gemini", {}))
    if patch.get("gemini_clear_key"):
        gem["api_key"] = ""
        gem["verified_at"] = ""
    elif patch.get("gemini_api_key"):
        gem["api_key"] = str(patch["gemini_api_key"]).strip()
        gem["verified_at"] = ""            # key baru → wajib diuji ulang (G-3)
    if patch.get("gemini_verified_at") is not None:
        gem["verified_at"] = str(patch["gemini_verified_at"])
    if patch.get("gemini_daily_limit") is not None:
        gem["daily_limit"] = max(1, int(patch["gemini_daily_limit"]))
    if patch.get("gemini_model") is not None:
        gem["model"] = str(patch["gemini_model"]).strip() or GEMINI_DEFAULT_MODEL
    if patch.get("gemini_enabled") is not None:
        gem["enabled"] = bool(patch["gemini_enabled"])
    oai = dict(current.get("openai", {}))
    if patch.get("openai_clear_key"):
        oai["api_key"], oai["verified_at"] = "", ""
    elif patch.get("openai_api_key"):
        oai["api_key"], oai["verified_at"] = str(patch["openai_api_key"]).strip(), ""
    if patch.get("openai_verified_at") is not None:
        oai["verified_at"] = str(patch["openai_verified_at"])
    ant, gem, oai = ({**d, "api_key": secret_box.seal(d.get("api_key") or "")} for d in (ant, gem, oai))
    to_set = {"anthropic": ant, "gemini": gem, "openai": oai, "updated_at": now_iso()}
    existing = await db.system_settings.find_one({"scope": SCOPE}, {"_id": 0})
    if existing:
        await db.system_settings.update_one({"scope": SCOPE}, {"$set": to_set})
    else:
        await db.system_settings.insert_one(
            {"id": new_id("set"), "scope": SCOPE, "created_at": now_iso(), **to_set})
    return await get_integrations_public()
