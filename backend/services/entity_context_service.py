"""F0-A — Entity identity & context helper (Multi-Entity foundation).

Sumber tunggal untuk:
- Default & enrichment skema entitas (`is_group`, `ownership_pct` — KP-T1).
- Membangun "entity context" user (home + allowed + active) untuk auth/me & switcher.

MODEL 1 (silo selling): sales/warehouse terkunci ke 1 entitas; admin/manager
boleh lintas-entitas (oversight). SO selalu dibukukan atas entitas sales.
"""
from typing import Any, Dict, List, Optional

from db import db
from core_utils import now_iso

PRIMARY_ENTITY_ID = "ent_ksc"

# Role yang boleh mengoperasikan SEMUA entitas (oversight lintas-PT).
# FASE E-8 (E8.1) — daftarnya sekarang DITURUNKAN dari registry peran supaya tidak
# ada dua pendapat. `sales_admin` SENGAJA tidak masuk: keputusan pemilik E8.10b#1
# (Admin Sales berbasis PENUGASAN lewat `users.allowed_entity_ids`, bukan lintas-PT).
from role_registry import CROSS_ENTITY_ROLES  # noqa: E402

# Default field entitas (enrichment idempotent untuk record lama).
# KP-T1 (KP-01) — lima isian yang tidak dibaca kode mana pun (`numbering_scheme`, `incentive_payer`, `coa_template`,
# `fiscal_year_start`, `parent_entity_id`) dan `currency` dibuang. Sumber tunggalnya: tahun buku & mata uang =
# kunci registry `finance.fiscal_year_end_month` / `finance.base_currency` (lapisan PT), penomoran = KP-T5, insentif =
# `commission.*`, bagan akun = `gl_service.seed_default_coa`, grup = `is_group` + `ownership_pct` (K-10).
ENTITY_DEFAULTS = {
    "is_group": False,
    "ownership_pct": 100.0,        # K-10 — persen kepemilikan grup atas PT ini; dibaca PK-31
}
#: KP-T1 — isian yang DITULIS `ensure_entity_defaults` saat aplikasi menyala (perilaku lama untuk `is_group`).
#: `ownership_pct` sengaja tidak: mengisinya pada data nyata = skrip `scripts/migrate_kpt1_profil_pt.py` (H3);
#: sebelum itu pembaca memakai bawaan 100 dari `ENTITY_DEFAULTS` (`uniform_entity`).
BOOT_DEFAULT_KEYS = ("is_group",)


def entity_defaults() -> Dict[str, Any]:
    return dict(ENTITY_DEFAULTS)


def is_pkp(entity: Dict[str, Any]) -> bool:
    """Status PKP entitas (driver PPN) — diturunkan dari default_tax_mode."""
    return (entity or {}).get("default_tax_mode") == "ppn"


async def all_active_entity_ids() -> List[str]:
    # FIX-1 (B1 K-B1-10) — badan usaha bertanda data uji (`is_test`, dipasang skrip penanda yang bisa dibalik) tidak
    # ikut penugasan dinamis admin/manajer → tidak muncul di pengalih & tidak ikut "Semua Entitas".
    rows = await db.business_entities.find(
        {"status": "active", "is_test": {"$ne": True}}, {"_id": 0, "id": 1}).to_list(200)
    return [r["id"] for r in rows]


async def active_entity_ids_for(entity_ids: List[str]) -> List[str]:
    """FASE E-1 (E1.5) — saring daftar entitas menjadi yang MASIH AKTIF saja.

    Dipakai `entity_summaries`/pemilih entitas: badan usaha terarsip tidak boleh
    lagi muncul sebagai pilihan konteks kerja, walau masih tercatat di
    `users.allowed_entity_ids` (riwayat penugasan sengaja tidak dihapus).
    """
    if not entity_ids:
        return []
    rows = await db.business_entities.find(
        {"id": {"$in": list(entity_ids)}, "status": "active"}, {"_id": 0, "id": 1}).to_list(500)
    active = {r["id"] for r in rows}
    return [e for e in entity_ids if e in active]


def resolve_allowed_entities(role: str, home_entity_id: str,
                             all_ids: List[str]) -> List[str]:
    """Tentukan daftar entitas yang boleh dioperasikan user (Model 1)."""
    if role in CROSS_ENTITY_ROLES:
        return list(all_ids) or [home_entity_id]
    return [home_entity_id]


async def entity_summaries(entity_ids: List[str],
                          home_entity_id: str = "") -> List[Dict[str, Any]]:
    """Ringkasan badan usaha untuk pemilih entitas/FE (satu bentuk seragam).

    FASE E-1 (E1.8) — memakai `entity_lifecycle_service.uniform_entity` supaya
    bentuknya IDENTIK dengan `/api/entities`; sebelumnya dua endpoint ini
    mengembalikan bentuk berbeda sehingga FE butuh tambalan label sendiri.
    `is_home` dipakai E-3 untuk menandai badan usaha utama di pemilih entitas.
    """
    from services.entity_lifecycle_service import uniform_entity
    rows = await db.business_entities.find(
        {"id": {"$in": entity_ids}}, {"_id": 0}).to_list(200)
    out = [{**uniform_entity(e), "is_home": e["id"] == home_entity_id} for e in rows]
    # urutkan sesuai urutan entity_ids
    order = {eid: i for i, eid in enumerate(entity_ids)}
    out.sort(key=lambda x: order.get(x["id"], 999))
    return out


async def build_entity_context(user: Dict[str, Any],
                               requested_entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Bangun konteks entitas untuk user (dipakai login, /auth/me, /auth/context).

    - home_entity_id  : entitas kerja/payroll user.
    - allowed_entity_ids : entitas yang boleh dioperasikan (Model 1).
    - active_entity_id : entitas aktif (header X-Entity-Id jika valid, else home).
    - entities : ringkasan entitas yang diizinkan (untuk switcher).
    - can_switch_entity : true bila >1 entitas diizinkan.
    """
    role = user.get("role", "")
    all_ids = await all_active_entity_ids()
    home = user.get("home_entity_id") or PRIMARY_ENTITY_ID
    # Untuk role cross-entity (admin/manager) selalu resolve DINAMIS agar entitas
    # baru yang di-provision muncul di switcher tanpa perlu logout-login.
    # Untuk role lain, pakai daftar yang tersimpan di record user (Model 1: silo).
    if role in CROSS_ENTITY_ROLES:
        allowed = resolve_allowed_entities(role, home, all_ids)
    else:
        # FASE E-1 (E1.5) — badan usaha yang sudah DIARSIPKAN dibuang dari daftar
        # pilihan supaya tidak bisa dipilih lalu gagal saat menulis. Riwayat
        # penugasan di record user sengaja tidak dihapus.
        stored = user.get("allowed_entity_ids") or [home]
        allowed = await active_entity_ids_for(stored) or ([home] if home in all_ids else [])
    # active = requested bila valid & diizinkan, else home (atau allowed pertama)
    if requested_entity_id and requested_entity_id in allowed:
        active = requested_entity_id
    else:
        active = home if home in allowed else (allowed[0] if allowed else home)
    from services.entity_lifecycle_service import archived_readable_ids
    archived = await archived_readable_ids(user)
    return {
        "home_entity_id": home,
        "allowed_entity_ids": allowed,
        "active_entity_id": active,
        "can_switch_entity": len(allowed) > 1,
        "is_cross_entity": user.get("role") in CROSS_ENTITY_ROLES,
        "entities": await entity_summaries(allowed, home_entity_id=home),
        "archived_entities": await entity_summaries(archived) if archived else [],
    }


# ─── Migrasi idempotent (dipanggil bootstrap) ────────────────────────────────

async def ensure_entity_defaults() -> int:
    """Lengkapi field default pada entitas yang belum punya (idempotent). KP-T1 — hanya `BOOT_DEFAULT_KEYS`."""
    changed = 0
    async for e in db.business_entities.find({}, {"_id": 0}):
        patch = {k: ENTITY_DEFAULTS[k] for k in BOOT_DEFAULT_KEYS if k not in e}
        if patch:
            patch["updated_at"] = now_iso()
            await db.business_entities.update_one({"id": e["id"]}, {"$set": patch})
            changed += 1
    return changed


async def ensure_user_entities() -> int:
    """Pastikan setiap user punya home_entity_id + allowed_entity_ids (idempotent).

    Default aman: home = PRIMARY_ENTITY_ID; allowed sesuai role.
    Distribusi demo (sales3 → Kanda) di-set oleh seed, bukan migrasi ini.
    """
    all_ids = await all_active_entity_ids() or [PRIMARY_ENTITY_ID]
    changed = 0
    async for u in db.users.find({}, {"_id": 0, "id": 1, "role": 1,
                                      "home_entity_id": 1, "allowed_entity_ids": 1}):
        patch: Dict[str, Any] = {}
        home = u.get("home_entity_id")
        if not home:
            home = PRIMARY_ENTITY_ID
            patch["home_entity_id"] = home
        if not u.get("allowed_entity_ids"):
            patch["allowed_entity_ids"] = resolve_allowed_entities(u.get("role", ""), home, all_ids)
        if patch:
            patch["updated_at"] = now_iso()
            await db.users.update_one({"id": u["id"]}, {"$set": patch})
            changed += 1
    return changed
