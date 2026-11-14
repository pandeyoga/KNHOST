"""PERAN KUSTOM & TINGKAT AKSES — aturan bisnis untuk layar "Peran & Hak Akses".

Sumber kebenaran izin tetap `permission_settings.matrix` (dibaca `dependencies.permission_matrix`).
Berkas ini menerjemahkan 3 tingkat per modul (none/view/manage) ke matriks aksi, dan menjaga
registry peran (`role_registry.ROLES`) tetap memuat peran kustom yang tersimpan di basis data.
"""
import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from access_modules import LEVELS, apply_levels, clean_permissions, levels_of, nav_allowed_for_perms, nav_for_levels
from core_utils import now_iso
from db import db
from permissions_config import DEFAULT_PERMISSIONS
import role_registry as reg

LOCKED_ROLES = {"admin"}


async def list_custom() -> List[Dict[str, Any]]:
    return await db.custom_roles.find({}, {"_id": 0}).sort("created_at", 1).to_list(200)


async def sync_registry() -> None:
    reg.register_custom_roles(await list_custom())
    rec = await db.permission_settings.find_one({"id": "default"}, {"_id": 0, "cross_entity": 1, "matrix": 1,
                                                                    "role_traits": 1}) or {}
    reg.apply_cross_entity(rec.get("cross_entity") or {})
    # PR-T4 — sifat peran (cakupan data, halaman awal, kategori kerja, alamat notifikasi) sesudah lintas PT.
    reg.apply_traits(rec.get("role_traits") or {}, {**DEFAULT_PERMISSIONS, **(rec.get("matrix") or {})})
    from core_utils import refresh_cost_safe_roles   # PR-T2 — kolom biaya/HPP mengikuti izin `costing.view`
    refresh_cost_safe_roles(rec.get("matrix") or DEFAULT_PERMISSIONS)


async def _set_cross_entity(rid: str, value: Optional[bool]) -> None:
    """Simpan (bool) atau hapus (None = kembali ke bawaan) pengaturan lintas badan usaha satu peran."""
    if value is None:
        await db.permission_settings.update_one({"id": "default"}, {"$unset": {f"cross_entity.{rid}": ""}})
    else:
        await db.permission_settings.update_one({"id": "default"}, {"$set": {f"cross_entity.{rid}": bool(value)}},
                                                upsert=True)


async def _matrix() -> Dict[str, Dict[str, List[str]]]:
    record = await db.permission_settings.find_one({"id": "default"}, {"_id": 0})
    return deepcopy(record.get("matrix") if record and record.get("matrix") else DEFAULT_PERMISSIONS)


async def _save_matrix(matrix: Dict[str, Any]) -> None:
    await db.permission_settings.update_one(
        {"id": "default"}, {"$set": {"matrix": matrix, "updated_at": now_iso()}, "$inc": {"version": 1}}, upsert=True)
    from services.field_visibility import invalidate
    invalidate()


async def _users_by_role() -> Dict[str, int]:
    rows = await db.users.aggregate([
        {"$match": {"status": "active"}},
        {"$group": {"_id": "$role", "n": {"$sum": 1}}},
    ]).to_list(200)
    return {r["_id"]: r["n"] for r in rows if r.get("_id")}


def _clean_levels(levels: Optional[Dict[str, Any]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in (levels or {}).items():
        lvl = v.get("level") if isinstance(v, dict) else v
        if lvl not in LEVELS:
            raise HTTPException(status_code=400,
                                detail=f"Tingkat akses “{lvl}” untuk modul “{k}” tidak dikenal "
                                       f"(pilihan: Tidak ada · Lihat saja · Kelola penuh).")
        out[k] = lvl
    return out


def _clean_perms(perms: Any) -> Dict[str, List[str]]:
    try:
        return clean_permissions(perms)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _clean_label(label: str) -> str:
    clean = re.sub(r"\s+", " ", (label or "").strip())
    if len(clean) < 2 or len(clean) > 40:
        raise HTTPException(status_code=400, detail="Nama peran wajib 2–40 karakter.")
    return clean


async def _assert_label_unique(label: str, exclude_id: str = "") -> None:
    low = label.lower()
    for rid, r in reg.ROLES.items():
        if rid != exclude_id and (r["label"].lower() == low or r["long_label"].lower() == low):
            raise HTTPException(status_code=409,
                                detail=f"Nama peran “{label}” sudah dipakai. Pilih nama lain.")


def _version(perms: Dict[str, Any], hidden: List[str], doc: Dict[str, Any], cross: bool = False,
             traits: Optional[Dict[str, Any]] = None) -> str:
    """LN-015 — sidik isi peran untuk deteksi konflik simpan antar-admin. PR-T4: sifat peran ikut."""
    raw = json.dumps([{k: sorted(v or []) for k, v in sorted(perms.items())}, sorted(hidden),
                      doc.get("label", ""), doc.get("description", ""), bool(cross), traits or {}], sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def _same_perms(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """PR-T9 — izin sama bila per sumber daya sama sebagai HIMPUNAN; daftar kosong = tidak ada."""
    def norm(p: Dict[str, Any]) -> Dict[str, frozenset]:
        return {k: frozenset(v) for k, v in (p or {}).items() if v}
    return norm(a) == norm(b)


def _modified_parts(rid: str, perms: Dict[str, Any], custom: bool) -> List[str]:
    """PR-T9 — bagian peran BAWAAN yang berbeda dari bawaan sistem: izin, menu tersembunyi, lintas PT."""
    default = DEFAULT_PERMISSIONS.get(rid)
    if custom or default is None:
        return []
    parts: List[str] = []
    if not _same_perms(perms, default):
        parts.append("izin")
    if _HIDDEN.get(rid):
        parts.append("menu")
    if (reg.ROLES.get(rid) or {}).get("cross_entity", False) != reg.cross_entity_default(rid):
        parts.append("lintas_pt")
    if reg.TRAIT_OVERRIDES.get(rid):   # PR-T4 — sifat peran disimpan Admin
        parts.append("sifat")
    return parts


def _role_view(rid: str, matrix: Dict[str, Any], users: Dict[str, int],
               custom_docs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    entry = reg.ROLES.get(rid) or {}
    perms = matrix.get(rid, {}) or {}
    custom = rid in custom_docs
    doc = custom_docs.get(rid, {})
    parts = _modified_parts(rid, perms, custom)
    pending = {k: list(v) for k, v in (doc.get("pending_defaults") or {}).items() if v} if custom else {}
    return {
        "id": rid,
        "label": entry.get("label", rid),
        "long_label": entry.get("long_label", rid),
        "description": doc.get("description") if custom else entry.get("description", ""),
        "custom": custom,
        "base_role": doc.get("base_role", "") if custom else "",
        "base_role_label": reg.role_label(doc.get("base_role", "")) if custom and doc.get("base_role") else "",
        "rank": entry.get("rank", 0),
        "cross_entity": entry.get("cross_entity", False),
        # Keputusan owner 2026-10-21 — dapat diatur per peran; bawaan: peran bawaan → sistem, kustom → acuannya.
        "cross_entity_default": reg.cross_entity_default(rid),
        "cross_entity_overridden": entry.get("cross_entity", False) != reg.cross_entity_default(rid),
        "cross_entity_locked": rid in LOCKED_ROLES,
        "home_view": entry.get("home_view", ""),
        "users": users.get(rid, 0),
        "locked": rid in LOCKED_ROLES,
        "deletable": custom and users.get(rid, 0) == 0,
        "modified": bool(parts),
        "modified_parts": parts,
        # PR-T9 — izin baru peran dasar yang belum diikuti peran kustom ini (modulnya pernah diubah).
        "pending_from_base": pending,
        "pending_from_base_count": sum(len(v) for v in pending.values()),
        "levels": levels_of(perms),
        "permissions": perms,
        "turn_alerts": _turn_alerts(perms),
        "updated_at": doc.get("updated_at", ""),
        "hidden_views": sorted(_HIDDEN.get(rid, [])),
        # PR-T1 — peran yang akunnya boleh dikelola pemegang peran ini (permission_settings.assignable_roles).
        "assignable_roles": sorted(_ASSIGNABLE.get(rid, [])),
        "assignable_roles_labels": [reg.role_label(r) for r in sorted(_ASSIGNABLE.get(rid, []))],
        # PR-T4 — sifat peran: efektif, turunan, kunci yang disimpan Admin, dan pilihan halaman awal.
        **_traits_view(rid, perms),
        "version": _version(perms, _HIDDEN.get(rid, []), doc, entry.get("cross_entity", False),
                            {"efektif": reg.traits_of(rid), "simpan": reg.TRAIT_OVERRIDES.get(rid) or {}}),
    }


# ─── PR-T4 — sifat peran ─────────────────────────────────────────────────────────────────────────────────────────────
PRT4_MIGRATION_ID = "prt4:sifat-peran"


def _traits_view(rid: str, perms: Dict[str, Any]) -> Dict[str, Any]:
    t = reg.traits_of(rid)
    return {"traits": t, "traits_default": reg.trait_defaults(rid),
            "traits_overridden": sorted(reg.TRAIT_OVERRIDES.get(rid) or {}),
            "home_view_fallback": bool((reg.ROLES.get(rid) or {}).get("home_view_fallback")),
            "home_choices": reg.home_choices_for(perms, t["kategori_kerja"])}


def clean_traits(rid: Optional[str], traits: Optional[Dict[str, Any]], perms: Dict[str, Any],
                 base_role: str = "") -> Dict[str, Any]:
    """Periksa isian `traits` (PATCH/POST). Hasil: {kunci: nilai | None (= kembali ke turunan)}. 400 bila tidak sah.
    `perms` = izin peran SESUDAH simpan (syarat halaman awal)."""
    if not traits:
        return {}
    if not isinstance(traits, dict):
        raise HTTPException(status_code=400, detail="Isian sifat peran tidak dikenal.")
    out: Dict[str, Any] = {}
    for key, val in traits.items():
        if key not in reg.TRAIT_KEYS:
            raise HTTPException(status_code=400, detail="Isian sifat peran tidak dikenal.")
        if val is None:
            out[key] = None
        elif key == "data_scope":
            if val not in reg.DATA_SCOPES:
                raise HTTPException(status_code=400, detail=f"Cakupan data “{val}” tidak dikenal.")
            out[key] = val
        elif key == "kategori_kerja":
            if val not in reg.WORK_CATEGORIES:
                raise HTTPException(status_code=400, detail=f"Kategori kerja “{val}” tidak dikenal.")
            out[key] = val
        elif key == "notify_like":
            vals = val if isinstance(val, list) else [val]
            if any(str(v) not in reg.BUILTIN_HOME for v in vals):
                raise HTTPException(status_code=400, detail="Alamat notifikasi hanya boleh peran bawaan.")
            out[key] = sorted({str(v) for v in vals})
        elif key == "home_view":
            out[key] = str(val)
    if out.get("home_view"):
        choice = reg.HOME_BY_VIEW.get(out["home_view"])
        if not choice:
            raise HTTPException(status_code=400, detail=f"Halaman awal “{out['home_view']}” tidak dikenal.")
        if out.get("kategori_kerja") is not None:
            category = out["kategori_kerja"]
        elif "kategori_kerja" in out and rid:   # null pada simpan yang sama = kembali ke turunan
            category = reg.trait_defaults(rid)["kategori_kerja"]
        else:
            category = _projected_trait(rid, "kategori_kerja", base_role)
        if not reg.home_allowed(out["home_view"], perms, category or ""):
            raise HTTPException(status_code=400,
                                detail=f"Halaman awal “{choice['label']}” butuh akses yang belum dimiliki peran ini.")
    return out


def _projected_trait(rid: Optional[str], key: str, base_role: str = "") -> Any:
    """Nilai efektif sebuah sifat bila kunci itu TIDAK diisi pada simpan ini (peran baru: turunan peran dasarnya)."""
    if rid:
        return reg.traits_of(rid)[key]
    if base_role and base_role in reg.ROLES:
        return reg.traits_of(base_role)[key] if key != "notify_like" else [base_role]
    return {"data_scope": "semua", "home_view": reg.PROFILE_HOME[0], "kategori_kerja": "", "notify_like": []}[key]


def projected_scope(rid: Optional[str], traits: Optional[Dict[str, Any]], base_role: str = "") -> Optional[str]:
    """Cakupan data HASIL simpan (untuk penjaga kenaikan hak). `None` = simpan ini tidak menyentuh cakupan."""
    t = traits or {}
    if rid is not None and "data_scope" not in t:
        return None
    if t.get("data_scope") is not None:
        return t["data_scope"]
    if rid is None:
        return _projected_trait(None, "data_scope", base_role)
    return reg.trait_defaults(rid)["data_scope"]   # null = kembali ke turunan


async def _save_traits(rid: str, traits: Dict[str, Any]) -> None:
    sets = {f"role_traits.{rid}.{k}": v for k, v in traits.items() if v is not None}
    unsets = {f"role_traits.{rid}.{k}": "" for k, v in traits.items() if v is None}
    update: Dict[str, Any] = {}
    if sets:
        update["$set"] = sets
    if unsets:
        update["$unset"] = unsets
    if update:
        await db.permission_settings.update_one({"id": "default"}, update, upsert=True)


async def migrate_role_traits() -> Dict[str, Any]:
    """PR-T4 — sekali jalan (`permission_settings.migrations_applied` ∋ `prt4:sifat-peran`). Hanya peran kustom TANPA
    peran dasar yang memegang `design_request.view` tetapi tidak `order.view` maupun `customer.view`: simpan
    `data_scope = "milik_sendiri"` (sebelum PR-T4 peran itu hanya melihat tugas desainnya). Selain itu tidak ada tulisan:
    semua nilai awal diturunkan. Dipanggil `bootstrap.run_bootstrap` sesudah `ensure_permission_ledger`."""
    record = await db.permission_settings.find_one({"id": "default"}, {"_id": 0, "matrix": 1, "role_traits": 1,
                                                                       "migrations_applied": 1})
    if not record or record.get("migrations_applied") is None or \
            PRT4_MIGRATION_ID in (record.get("migrations_applied") or []):
        return {"ditulis": []}
    matrix = record.get("matrix") or {}
    stored = record.get("role_traits") or {}

    def has(perms: Dict[str, Any], res: str, act: str) -> bool:
        acts = perms.get(res) or []
        return act in acts or "*" in acts

    written: List[str] = []
    for c in await db.custom_roles.find({}, {"_id": 0, "id": 1, "base_role": 1}).to_list(500):
        cid, perms = c.get("id") or "", matrix.get(c.get("id") or "") or {}
        if not cid or c.get("base_role") or "data_scope" in (stored.get(cid) or {}):
            continue
        if has(perms, "design_request", "view") and not has(perms, "order", "view") \
                and not has(perms, "customer", "view"):
            written.append(cid)
    update: Dict[str, Any] = {"$addToSet": {"migrations_applied": PRT4_MIGRATION_ID}}
    if written:
        update["$set"] = {f"role_traits.{cid}.data_scope": "milik_sendiri" for cid in written}
    await db.permission_settings.update_one({"id": "default"}, update)
    if written:
        from dependencies import audit
        await audit("Sistem (migrasi PR-T4)", "role_traits_migrated", "permission_settings", "default",
                    {"data_scope_milik_sendiri": written},
                    reason="PR-T4 — peran desain tanpa peran dasar tetap hanya melihat tugasnya")
    return {"ditulis": written}


PRT4_KPI_MIGRATION_ID = "prt4:izin-kpi-sales"


async def migrate_kpi_permission() -> Dict[str, Any]:
    """PR-T4 — sekali jalan (`prt4:izin-kpi-sales`): `order.view_sales_kpi` untuk Admin, Manajer, Admin Sales, Finance
    dan peran kustom yang berdasar keempatnya, masing-masing hanya bila memegang `order.view` (hari ini mereka melihat
    KPI sales lain lewat nama peran; tanpa `order.view` mereka memang tidak bisa membukanya). Pasangan bawaan dicatat di
    `defaults_applied` supaya `sync_permission_modules` tidak meneruskannya lagi (pencabutan Admin sesudahnya
    bertahan). Dipanggil `bootstrap.run_bootstrap` sesudah `ensure_permission_ledger`, sebelum
    `sync_permission_modules`."""
    from permissions_config import PRT4_KPI_ROLES
    record = await db.permission_settings.find_one({"id": "default"}, {"_id": 0})
    if not record or record.get("migrations_applied") is None or \
            PRT4_KPI_MIGRATION_ID in (record.get("migrations_applied") or []):
        return {"diberi": []}
    matrix: Dict[str, Any] = record.get("matrix") or {}
    customs = await db.custom_roles.find({"base_role": {"$in": list(PRT4_KPI_ROLES)}}, {"_id": 0}).to_list(500)
    granted: List[str] = []
    for rid in [*PRT4_KPI_ROLES, *[c["id"] for c in customs]]:
        perms = matrix.get(rid)
        acts = list((perms or {}).get("order") or [])
        if perms is not None and "view" in acts and "view_sales_kpi" not in acts:
            perms["order"] = acts + ["view_sales_kpi"]
            granted.append(rid)
    patch: Dict[str, Any] = {}
    applied = record.get("defaults_applied")
    if applied is not None:   # None = instalasi sebelum L01: garis dasar dibuat dari bawaan oleh sync_permission_modules
        for rid in PRT4_KPI_ROLES:
            done = applied.setdefault(rid, {})
            cur = list(done.get("order") or [])
            done["order"] = cur + [a for a in ("view_sales_kpi",) if a not in cur]
        patch["defaults_applied"] = applied
    if granted:
        patch.update({"matrix": matrix, "updated_at": now_iso()})
    update: Dict[str, Any] = {"$addToSet": {"migrations_applied": PRT4_KPI_MIGRATION_ID}}
    if patch:
        update["$set"] = patch
    await db.permission_settings.update_one({"id": "default"}, update)
    for c in customs:
        if c["id"] in granted:
            pending = {k: [a for a in v if not (k == "order" and a == "view_sales_kpi")]
                       for k, v in (c.get("pending_defaults") or {}).items()}
            await db.custom_roles.update_one({"id": c["id"]}, {"$set": {
                "levels": {k: v["level"] for k, v in levels_of(matrix.get(c["id"]) or {}).items()},
                "pending_defaults": {k: v for k, v in pending.items() if v}, "updated_at": now_iso()}})
    if granted:
        from dependencies import audit
        await audit("Sistem (migrasi PR-T4)", "role_kpi_permission_migrated", "permission_settings", "default",
                    {"order.view_sales_kpi": granted},
                    reason="PR-T4 — KPI sales lain dulu lewat nama peran, kini izin yang terlihat dan bisa dicabut")
    return {"diberi": granted}


_HIDDEN: Dict[str, List[str]] = {}
_ASSIGNABLE: Dict[str, List[str]] = {}


async def load_hidden_views() -> Dict[str, List[str]]:
    rec = await db.permission_settings.find_one({"id": "default"}, {"_id": 0, "hidden_views": 1,
                                                                    "assignable_roles": 1}) or {}
    _HIDDEN.clear()
    _HIDDEN.update(rec.get("hidden_views") or {})
    _ASSIGNABLE.clear()
    _ASSIGNABLE.update(rec.get("assignable_roles") or {})
    return _HIDDEN


async def current_permissions(rid: str) -> Dict[str, List[str]]:
    """PR-T1 — izin peran yang berlaku sekarang (matriks tersimpan, atau bawaan bila belum pernah diubah)."""
    current = (await _matrix()).get(rid)
    return deepcopy(current if current is not None else DEFAULT_PERMISSIONS.get(rid, {}))


async def projected_permissions(rid: Optional[str], payload: Dict[str, Any]) -> Dict[str, List[str]]:
    """PR-T1 — izin HASIL simpan (buat: acuan + tingkat; ubah: izin sekarang + tingkat), tanpa menyimpan.
    Urutannya sama dengan `create_custom`/`update_role`: izin rinci (`permissions`) menimpa tingkat."""
    if rid is None:
        base = (payload.get("base_role") or "").strip()
        perms = apply_levels(await current_permissions(base) if base else {}, _clean_levels(payload.get("levels")))
    else:
        perms = await current_permissions(rid)
        if payload.get("levels") is not None:
            perms = apply_levels(perms, _clean_levels(payload["levels"]))
    if payload.get("permissions") is not None:
        perms = _clean_perms(payload["permissions"])
    return perms


async def hidden_views_of(rid: str) -> List[str]:
    return sorted((await load_hidden_views()).get(rid, []))


def _turn_alerts(perms: Dict[str, List[str]]) -> List[str]:
    """Judul notifikasi "giliran" yang akan diterima pemegang izin ini (untuk pratinjau)."""
    from services.turn_notification_service import TURN_MAP
    out: List[str] = []
    for rules in TURN_MAP.values():
        for rule in rules.values():
            perm = rule.get("permission")
            if perm and perm[1] in (perms.get(perm[0]) or []):
                out.append(rule["title"])
    return out


async def all_roles() -> List[Dict[str, Any]]:
    await sync_registry()
    await load_hidden_views()
    matrix, users, customs = await _matrix(), await _users_by_role(), await list_custom()
    cdocs = {c["id"]: c for c in customs}
    return [_role_view(rid, matrix, users, cdocs) for rid in reg.role_ids()]


async def get_role(rid: str) -> Dict[str, Any]:
    await sync_registry()
    if rid not in reg.ROLES:
        raise HTTPException(status_code=404, detail="Peran tidak ditemukan.")
    await load_hidden_views()
    cdocs = {c["id"]: c for c in await list_custom()}
    out = _role_view(rid, await _matrix(), await _users_by_role(), cdocs)
    out["accounts"] = await _accounts_of_role(rid)
    return out


async def _accounts_of_role(rid: str) -> List[Dict[str, Any]]:
    rows = await db.users.find(
        {"role": rid}, {"_id": 0, "id": 1, "name": 1, "email": 1, "status": 1, "home_entity_id": 1},
    ).sort("name", 1).to_list(200)
    ents = {e["id"]: e for e in await db.business_entities.find(
        {}, {"_id": 0, "id": 1, "short_name": 1, "legal_name": 1}).to_list(200)}
    for r in rows:
        e = ents.get(r.get("home_entity_id") or "") or {}
        r["entity_name"] = e.get("short_name") or e.get("legal_name") or ""
    return rows


def _slug(label: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:24]
    return f"cr_{s or 'peran'}"


async def create_custom(payload: Dict[str, Any]) -> Dict[str, Any]:
    await sync_registry()
    label = _clean_label(payload.get("label", ""))
    await _assert_label_unique(label)
    base = (payload.get("base_role") or "").strip()
    if base and (base not in reg.ROLES):
        raise HTTPException(status_code=400, detail="Peran acuan (template) tidak dikenal.")
    if base in LOCKED_ROLES:
        raise HTTPException(status_code=400, detail="Peran Admin tidak bisa dijadikan template.")
    levels = _clean_levels(payload.get("levels"))
    traits_in = payload.get("traits")
    rid = _slug(label)
    existing = {r["id"] for r in await list_custom()}
    n = 2
    while rid in existing or rid in reg.ROLES:
        rid = f"{_slug(label)}_{n}"
        n += 1
    matrix = await _matrix()
    perms = apply_levels(deepcopy(matrix.get(base, {})) if base else {}, levels)
    if payload.get("permissions") is not None:
        perms = _clean_perms(payload["permissions"])
    traits = clean_traits(None, traits_in, perms, base)   # PR-T4 — sebelum apa pun disimpan
    matrix[rid] = perms
    doc = {"id": rid, "label": label, "description": (payload.get("description") or "").strip()[:200],
           "base_role": base, "levels": {k: v["level"] for k, v in levels_of(perms).items()},
           "created_at": now_iso(), "updated_at": now_iso()}
    await db.custom_roles.insert_one(dict(doc))
    await _save_matrix(matrix)
    if payload.get("cross_entity") is not None:   # tanpa nilai → mengikuti peran acuan
        await _set_cross_entity(rid, bool(payload["cross_entity"]))
    await _save_traits(rid, traits)
    await sync_registry()
    return await get_role(rid)


async def update_role(rid: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    await sync_registry()
    if rid in LOCKED_ROLES:
        raise HTTPException(status_code=403,
                            detail="Peran Admin dikunci: hak aksesnya tidak bisa diubah supaya "
                                   "tidak ada yang terkunci keluar dari sistem.")
    if rid not in reg.ROLES:
        raise HTTPException(status_code=404, detail="Peran tidak ditemukan.")
    custom = bool(reg.ROLES[rid].get("custom"))
    expected = (payload.get("expected_version") or "").strip()
    if expected and (await get_role(rid))["version"] != expected:
        raise HTTPException(status_code=409, detail={
            "code": "ROLE_VERSION_CONFLICT",
            "message": "Peran ini baru saja diubah admin lain. Muat ulang versi terbaru lalu ulangi perubahan Anda — tidak ada yang ditimpa."})
    matrix = await _matrix()
    changes: Dict[str, Any] = {}
    if "levels" in payload and payload["levels"] is not None:
        levels = _clean_levels(payload["levels"])
        current = matrix.get(rid)
        if current is None:
            current = DEFAULT_PERMISSIONS.get(rid, {})
        matrix[rid] = apply_levels(deepcopy(current), levels)
        changes["levels"] = levels
    if payload.get("hidden_views") is not None:
        from access_modules import all_nav_ids
        hv = sorted({str(v) for v in payload["hidden_views"] if str(v) in all_nav_ids()})
        bad = [v for v in payload["hidden_views"] if str(v) not in all_nav_ids()]
        if bad:
            raise HTTPException(status_code=400, detail=f"Menu/tab tidak dikenal: {', '.join(map(str, bad))}")
        await db.permission_settings.update_one({"id": "default"}, {"$set": {f"hidden_views.{rid}": hv}})
        changes["hidden_views"] = hv
    if payload.get("cross_entity") is not None:
        want = bool(payload["cross_entity"])
        # sama dengan bawaan → simpan sebagai "ikut bawaan" supaya perubahan bawaan/peran acuan tetap mengalir
        await _set_cross_entity(rid, None if want == reg.cross_entity_default(rid) else want)
        changes["cross_entity"] = want
    if payload.get("assignable_roles") is not None:   # PR-T1 — router memastikan hanya Admin yang sampai di sini
        wanted = [str(r) for r in payload["assignable_roles"]]
        bad = [r for r in wanted if r not in reg.ROLES or r in LOCKED_ROLES]
        if bad:
            raise HTTPException(status_code=400, detail=(
                "Peran Admin tidak bisa dimasukkan ke daftar kelola akun." if any(r in LOCKED_ROLES for r in bad)
                else f"Peran tidak dikenal: {', '.join(bad)}"))
        await db.permission_settings.update_one({"id": "default"},
                                                {"$set": {f"assignable_roles.{rid}": sorted(set(wanted))}},
                                                upsert=True)
        changes["assignable_roles"] = sorted(set(wanted))
    if payload.get("permissions") is not None:
        before = matrix.get(rid) or DEFAULT_PERMISSIONS.get(rid, {})
        matrix[rid] = _clean_perms(payload["permissions"])
        changes["permissions"] = {
            r: sorted(matrix[rid].get(r, [])) for r in set(before) | set(matrix[rid])
            if sorted(before.get(r, [])) != sorted(matrix[rid].get(r, []))}
    traits: Dict[str, Any] = {}
    if payload.get("traits") is not None:   # PR-T4 — diperiksa terhadap izin HASIL simpan ini
        perms_after = matrix.get(rid)
        traits = clean_traits(rid, payload["traits"], perms_after if perms_after is not None
                              else DEFAULT_PERMISSIONS.get(rid, {}))
        changes["traits"] = traits
    if custom:
        patch: Dict[str, Any] = {"updated_at": now_iso()}
        if payload.get("label") is not None:
            label = _clean_label(payload["label"])
            await _assert_label_unique(label, exclude_id=rid)
            patch["label"] = label
            changes["label"] = label
        if payload.get("description") is not None:
            patch["description"] = str(payload["description"]).strip()[:200]
        patch["levels"] = {k: v["level"] for k, v in levels_of(matrix.get(rid, {})).items()}
        await db.custom_roles.update_one({"id": rid}, {"$set": patch})
    elif payload.get("label") is not None or payload.get("description") is not None:
        raise HTTPException(status_code=400,
                            detail="Nama & deskripsi peran bawaan sistem tidak bisa diubah; "
                                   "hanya hak aksesnya.")
    await _save_matrix(matrix)
    await _save_traits(rid, traits)
    await sync_registry()
    out = await get_role(rid)
    out["changes"] = changes
    return out


async def reset_builtin(rid: str) -> Dict[str, Any]:
    await sync_registry()
    if rid in LOCKED_ROLES or rid not in DEFAULT_PERMISSIONS:
        raise HTTPException(status_code=400, detail="Hanya peran bawaan (selain Admin) yang bisa dikembalikan ke bawaan.")
    matrix = await _matrix()
    matrix[rid] = deepcopy(DEFAULT_PERMISSIONS[rid])
    await _save_matrix(matrix)
    await _set_cross_entity(rid, None)   # lintas badan usaha ikut kembali ke bawaan
    # PR-T9 — menu yang disembunyikan ikut kembali ke bawaan (tidak ada yang disembunyikan).
    await db.permission_settings.update_one({"id": "default"}, {"$unset": {f"hidden_views.{rid}": "",
                                                                         f"role_traits.{rid}": ""}})   # + PR-T4
    await load_hidden_views()
    await sync_registry()
    return await get_role(rid)


async def follow_base(rid: str, resources: Optional[List[str]] = None, *, dry_run: bool = False) -> Dict[str, Any]:
    """PR-T9 — tambahkan izin baru peran dasar yang tertunda (`custom_roles.pending_defaults`) ke peran kustom.

    `resources` kosong/None = semua yang tertunda. `dry_run` → {"added", "permissions"} tanpa menyimpan (dipakai
    router untuk penjaga kenaikan hak)."""
    await sync_registry()
    if rid not in reg.ROLES:
        raise HTTPException(status_code=404, detail="Peran tidak ditemukan.")
    doc = await db.custom_roles.find_one({"id": rid}, {"_id": 0}) or {}
    if not doc or not doc.get("base_role"):
        raise HTTPException(status_code=400,
                            detail="Hanya peran kustom yang punya peran dasar yang bisa mengikuti izin baru.")
    pending = {k: list(v) for k, v in (doc.get("pending_defaults") or {}).items() if v}
    pick = [r for r in pending if not resources or r in set(resources)]
    if not pick:
        raise HTTPException(status_code=400, detail="Tidak ada izin baru dari peran dasar untuk diikuti.")
    matrix = await _matrix()
    perms = deepcopy(matrix.get(rid) or {})
    added: Dict[str, List[str]] = {}
    for res in pick:
        cur = list(perms.get(res) or [])
        new = [a for a in pending[res] if a not in cur]
        if new:
            added[res] = new
        perms[res] = cur + new
    if dry_run:
        return {"added": added, "permissions": perms}
    matrix[rid] = perms
    rest = {k: v for k, v in pending.items() if k not in pick}
    await _save_matrix(matrix)
    await db.custom_roles.update_one({"id": rid}, {"$set": {
        "pending_defaults": rest, "levels": {k: v["level"] for k, v in levels_of(perms).items()},
        "updated_at": now_iso()}})
    await sync_registry()
    out = await get_role(rid)
    out["added"] = added
    return out


async def delete_custom(rid: str) -> Dict[str, Any]:
    await sync_registry()
    if rid not in reg.ROLES or not reg.ROLES[rid].get("custom"):
        raise HTTPException(status_code=400, detail="Peran bawaan sistem tidak bisa dihapus.")
    n = await db.users.count_documents({"role": rid})
    if n:
        inactive = await db.users.count_documents({"role": rid, "status": {"$ne": "active"}})
        extra = f" ({inactive} di antaranya nonaktif)" if inactive else ""
        raise HTTPException(
            status_code=409,
            detail=f"Peran ini masih dipakai {n} akun{extra}. Pindahkan akun tersebut ke peran lain "
                   f"dulu (layar Akun & Akses), baru hapus.")
    matrix = await _matrix()
    matrix.pop(rid, None)
    await _save_matrix(matrix)
    await db.permission_settings.update_one({"id": "default"}, {"$unset": {f"hidden_views.{rid}": "",
                                                                         f"cross_entity.{rid}": "",
                                                                         f"assignable_roles.{rid}": "",
                                                                         f"role_traits.{rid}": ""}})
    await db.custom_roles.delete_one({"id": rid})
    await sync_registry()
    return {"id": rid, "deleted": True}


async def preview_role(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Pratinjau hak (tanpa menyimpan): notifikasi giliran & layar yang notifikasinya lolos."""
    await sync_registry()
    src = (payload.get("role_id") or payload.get("base_role") or "").strip()
    if src and src not in reg.ROLES:
        raise HTTPException(status_code=400, detail="Peran acuan tidak dikenal.")
    matrix = await _matrix()
    current = matrix.get(src) if src else {}
    if current is None:
        current = DEFAULT_PERMISSIONS.get(src, {})
    perms = apply_levels(deepcopy(current or {}), _clean_levels(payload.get("levels")))
    if payload.get("permissions") is not None:
        perms = _clean_perms(payload["permissions"])
    return {"turn_alerts": _turn_alerts(perms), "screens": sorted(nav_allowed_for_perms(perms)),
            "levels": levels_of(perms)}


async def move_users(rid: str, to_role: str, *, exclude_user_id: str = "") -> Dict[str, Any]:
    await sync_registry()
    if rid not in reg.ROLES or to_role not in reg.ROLES:
        raise HTTPException(status_code=404, detail="Peran tidak ditemukan.")
    if rid in LOCKED_ROLES:   # PR-T1 — tanpa ini Admin terakhir bisa ikut terpindah (penjaga admin terakhir lolos)
        raise HTTPException(status_code=400,
                            detail="Akun Admin tidak bisa dipindahkan massal. Ubah satu per satu di Akun & Akses.")
    if to_role == rid:
        raise HTTPException(status_code=400, detail="Peran tujuan sama dengan peran asal.")
    if to_role in LOCKED_ROLES:
        raise HTTPException(status_code=400, detail="Akun tidak bisa dipindahkan massal ke peran Admin.")
    query: Dict[str, Any] = {"role": rid}
    if exclude_user_id:   # akun pelaku sendiri tidak ikut dipindah
        query["id"] = {"$ne": exclude_user_id}
    ids = [u["id"] for u in await db.users.find(query, {"_id": 0, "id": 1}).to_list(500)]
    if ids:
        await db.users.update_many({"role": rid, "id": {"$in": ids}},
                                   {"$set": {"role": to_role, "updated_at": now_iso()}})
        from services.user_admin_service import revoke_sessions   # sama seperti ubah peran satu akun
        for uid in ids:
            await revoke_sessions(uid, reason="role_moved")
    return {"from_role": rid, "to_role": to_role, "to_role_label": reg.role_label(to_role),
            "moved": len(ids), "user_ids": ids}


async def assert_valid_role_async(role: str) -> str:
    await sync_registry()
    return reg.assert_valid_role(role)


def nav_of(levels: Dict[str, str]) -> Dict[str, List[str]]:
    return nav_for_levels(levels)
