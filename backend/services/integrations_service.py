"""H5 service — Integrasi pihak ketiga (config runtime di system_settings).

Scope `integrations` di koleksi `system_settings`. Saat ini: Anthropic Claude
(untuk Design Gallery auto-tag). Pola deep-merge anti data-loss (cermin H4 `bpjs`).

KEAMANAN: `get_integrations_public()` MEMASK api_key → FE hanya menerima `has_key`.
Hanya `get_integrations()` (internal/service) yang membaca key plaintext.
"""
from typing import Any, Dict

from db import db
from core_utils import new_id, now_iso
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
_ENC_PREFIX = "enc:v1:"


def _fernet():
    """Kunci enkripsi rahasia at-rest (KN_SECRETS_KEY, Fernet). None → belum dikonfigurasi."""
    import os as _os
    key = (_os.environ.get("KN_SECRETS_KEY") or "").strip()
    if not key:
        return None
    from cryptography.fernet import Fernet
    return Fernet(key.encode())


def _enc(value: str) -> str:
    f = _fernet()
    if not value or value.startswith(_ENC_PREFIX) or f is None:
        return value
    return _ENC_PREFIX + f.encrypt(value.encode()).decode()


def _dec(value: str) -> str:
    if not value or not str(value).startswith(_ENC_PREFIX):
        return value
    f = _fernet()
    if f is None:
        raise RuntimeError("KN_SECRETS_KEY belum diisi — kunci API terenkripsi tidak bisa dibaca.")
    return f.decrypt(value[len(_ENC_PREFIX):].encode()).decode()


async def get_integrations() -> Dict[str, Any]:
    """Config penuh (TERMASUK api_key terdekripsi) — hanya untuk service internal (AI call)."""
    rec = await db.system_settings.find_one({"scope": SCOPE}, {"_id": 0})
    stored = {k: v for k, v in (rec or {}).items()
              if k not in ("scope", "id", "created_at", "updated_at")}
    plain = [p for p in _PROVIDERS
             if (stored.get(p) or {}).get("api_key")
             and not str(stored[p]["api_key"]).startswith(_ENC_PREFIX)]
    if plain and _fernet() is not None:
        # Migrasi malas (temuan lama #18): kunci polos lama langsung dienkripsi.
        await db.system_settings.update_one({"scope": SCOPE}, {"$set": {
            f"{p}.api_key": _enc(stored[p]["api_key"]) for p in plain}})
    cfg = deep_merge(DEFAULT_INTEGRATIONS, stored)
    for p in _PROVIDERS:
        if (cfg.get(p) or {}).get("api_key"):
            cfg[p] = {**cfg[p], "api_key": _dec(cfg[p]["api_key"])}
    return cfg


async def get_integrations_public() -> Dict[str, Any]:
    """Config ter-mask untuk FE: api_key → has_key(bool). TIDAK pernah bocorkan key."""
    cfg = await get_integrations()
    ant = cfg.get("anthropic", {})
    gem = cfg.get("gemini", {})
    import os as _os
    gem_key = bool(gem.get("api_key") or _os.environ.get("GEMINI_API_KEY"))
    oai = cfg.get("openai", {})
    oai_key = bool(oai.get("api_key") or _os.environ.get("OPENAI_API_KEY"))
    return {
        "openai": {"has_key": oai_key, "verified_at": oai.get("verified_at") or "",
                   "source": "integrasi" if oai.get("api_key") else ("env" if oai_key else "")},
        "anthropic": {
            "has_key": bool(ant.get("api_key")),
            "model": ant.get("model") or DEFAULT_MODEL,
            "enabled": bool(ant.get("enabled")),
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
    }


async def update_integrations(patch: Dict[str, Any]) -> Dict[str, Any]:
    """Update parsial config Anthropic (deep-merge; aturan key di schema).
    Mengembalikan config PUBLIC (ter-mask)."""
    current = await get_integrations()
    ant = dict(current.get("anthropic", {}))
    if patch.get("anthropic_clear_key"):
        ant["api_key"] = ""
    elif patch.get("anthropic_api_key"):
        ant["api_key"] = str(patch["anthropic_api_key"]).strip()
    if patch.get("anthropic_model") is not None:
        model = str(patch["anthropic_model"]).strip() or DEFAULT_MODEL
        ant["model"] = model
    if patch.get("anthropic_enabled") is not None:
        ant["enabled"] = bool(patch["anthropic_enabled"])
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
    ant, gem, oai = ({**d, "api_key": _enc(d.get("api_key") or "")} for d in (ant, gem, oai))
    to_set = {"anthropic": ant, "gemini": gem, "openai": oai, "updated_at": now_iso()}
    existing = await db.system_settings.find_one({"scope": SCOPE}, {"_id": 0})
    if existing:
        await db.system_settings.update_one({"scope": SCOPE}, {"$set": to_set})
    else:
        await db.system_settings.insert_one(
            {"id": new_id("set"), "scope": SCOPE, "created_at": now_iso(), **to_set})
    return await get_integrations_public()
