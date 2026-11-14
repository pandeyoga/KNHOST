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

from access_modules import (LEVELS, apply_levels, check_levels, clean_permissions, levels_of, nav_allowed_for_perms,
                            nav_for_levels)
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
    # PR-T6 — menu peran bawaan boleh bertambah sebesar selisih izin sekarang terhadap izin bawaannya.
    reg.apply_builtin_nav({**DEFAULT_PERMISSIONS, **(rec.get("matrix") or {})})
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


async def _users_by_role(active: bool = True) -> Dict[str, int]:
    """Jumlah akun per peran: aktif (bawaan) atau — PR-T6 — yang TIDAK aktif (`active=False`)."""
    rows = await db.users.aggregate([
        {"$match": {"status": "active" if active else {"$ne": "active"}}},
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
                                       f"(pilihan: Tidak ada · Lihat saja · Semua aksi).")
        out[k] = lvl
    try:   # PR-T5 — tingkat di luar `levels_available` modulnya (mis. "Lihat saja" pada modul sakelar) ditolak
        check_levels(out)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
               custom_docs: Dict[str, Dict[str, Any]], inactive: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
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
        # PR-T6 — "bisa dihapus" = peran kustom tanpa akun APA PUN (penghapusan menolak akun nonaktif juga).
        "users_inactive": (inactive or {}).get(rid, 0),
        "locked": rid in LOCKED_ROLES,
        "deletable": custom and users.get(rid, 0) == 0 and (inactive or {}).get(rid, 0) == 0,
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


PRT5_MIGRATION_ID = "prt5:katalog"


async def migrate_prt5_catalog() -> Dict[str, Any]:
    """PR-T5 — sekali jalan (`prt5:katalog`): pasangan izin yang dihapus dari katalog (`permissions_config.
    PRT5_REMOVED_PAIRS`, seluruh sumber daya `sales_pov`) dibuang dari `matrix` SEMUA peran (bawaan & kustom), dari
    `defaults_applied`, dan dari `custom_roles.pending_defaults`; `custom_roles.levels` dihitung ulang dengan id modul
    baru (modul `admin` dipecah lima). Tidak ada izin yang ditambahkan; pasangan yang dibuang tidak pernah diperiksa
    server, jadi tidak ada akses yang berubah. Dipanggil `bootstrap.run_bootstrap` sesudah `ensure_permission_ledger`,
    sebelum `sync_permission_modules`."""
    from permissions_config import PRT5_REMOVED_PAIRS, PRT5_REMOVED_RESOURCES
    return await _buang_pasangan_tersimpan(
        PRT5_MIGRATION_ID, PRT5_REMOVED_PAIRS, PRT5_REMOVED_RESOURCES, pelaku="Sistem (migrasi PR-T5)",
        alasan="PR-T5 — izin yang tidak pernah diperiksa server dihapus dari katalog")


CRT1_MIGRATION_ID = "crt1:izin-kredit"


async def migrate_crt1_catalog() -> Dict[str, Any]:
    """CR-T1 — sekali jalan (`crt1:izin-kredit`): `customer.manage_credit` (jalur sementara PK-45, kini dijawab 410)
    dibuang dari matriks tersimpan, `defaults_applied`, dan `pending_defaults` — sama seperti PR-T5. Tanpa ini editor
    peran mengirim balik pasangan yang tidak lagi dikenal katalog dan simpan ditolak 400. Penggantinya
    (`credit_profile.*`) diteruskan `sync_permission_modules` seperti izin bawaan baru lain."""
    from permissions_config import CRT1_REMOVED_PAIRS
    return await _buang_pasangan_tersimpan(
        CRT1_MIGRATION_ID, CRT1_REMOVED_PAIRS, (), pelaku="Sistem (migrasi CR-T1)",
        alasan="CR-T1 — plafon & blokir kredit kini lewat pengajuan profil kredit (izin credit_profile)")


PK22_MIGRATION_ID = "pk22:izin-penggajian"


async def migrate_pk22_payroll_permission() -> Dict[str, Any]:
    """PK-22 (FY-09) — sekali jalan (`pk22:izin-penggajian`): peran (kustom maupun bawaan yang matriksnya diubah Admin)
    yang memegang `hr.manage_payroll` dan BELUM punya sumber daya `payroll` diberi kelima pasangan `payroll.*`
    (`permissions_config.PK22_PAYROLL_ACTIONS`) — hari ini mereka menyiapkan, mengesahkan, memposting, dan membayar gaji
    lewat `hr.manage_payroll`, jadi tidak ada yang kehilangan akses saat endpoint beralih ke izin baru. Pasangan bawaan
    Admin & Manajer dicatat di `defaults_applied` supaya `sync_permission_modules` tidak meneruskannya lagi (pencabutan
    sesudahnya bertahan). Dipanggil `bootstrap.run_bootstrap` sesudah `ensure_permission_ledger`, sebelum
    `sync_permission_modules`."""
    from permissions_config import PK22_DEFAULT_PAIRS, PK22_PAYROLL_ACTIONS
    record = await db.permission_settings.find_one({"id": "default"}, {"_id": 0})
    if not record or record.get("migrations_applied") is None or \
            PK22_MIGRATION_ID in (record.get("migrations_applied") or []):
        return {"diberi": []}
    matrix: Dict[str, Any] = record.get("matrix") or {}
    customs = {c["id"]: c for c in await db.custom_roles.find({}, {"_id": 0}).to_list(500)}
    granted: List[str] = []
    for rid, perms in matrix.items():
        if not isinstance(perms, dict) or perms.get("payroll"):
            continue
        if "manage_payroll" in (perms.get("hr") or []):
            perms["payroll"] = list(PK22_PAYROLL_ACTIONS)
            granted.append(rid)
    patch: Dict[str, Any] = {}
    applied = record.get("defaults_applied")
    if applied is not None:   # None = instalasi sebelum L01: garis dasar dibuat dari bawaan oleh sync_permission_modules
        for rid, mods in PK22_DEFAULT_PAIRS.items():
            done = applied.setdefault(rid, {})
            for res, acts in mods.items():
                cur = list(done.get(res) or [])
                done[res] = cur + [a for a in acts if a not in cur]
        patch["defaults_applied"] = applied
    if granted:
        patch.update({"matrix": matrix, "updated_at": now_iso()})
    update: Dict[str, Any] = {"$addToSet": {"migrations_applied": PK22_MIGRATION_ID}}
    if patch:
        update["$set"] = patch
    await db.permission_settings.update_one({"id": "default"}, update)
    for cid in granted:
        c = customs.get(cid)
        if not c:
            continue
        pending = {k: v for k, v in (c.get("pending_defaults") or {}).items() if k != "payroll"}
        await db.custom_roles.update_one({"id": cid}, {"$set": {
            "levels": {k: v["level"] for k, v in levels_of(matrix.get(cid) or {}).items()},
            "pending_defaults": pending, "updated_at": now_iso()}})
    if granted:
        from dependencies import audit
        await audit("Sistem (migrasi PK-22)", "role_payroll_permission_migrated", "permission_settings", "default",
                    {"payroll": granted},
                    reason="PK-22 — menyiapkan, mengesahkan, memposting, dan membayar gaji kini lima izin terpisah")
    return {"diberi": granted}


async def _buang_pasangan_tersimpan(migration_id: str, pairs: Any, resources: Any, *, pelaku: str,
                                    alasan: str) -> Dict[str, Any]:
    """Buang pasangan izin `pairs` (dan seluruh sumber daya `resources`) dari matriks tersimpan sekali jalan
    (`migration_id` di `migrations_applied`). Dipakai PR-T5 dan CR-T1."""
    record = await db.permission_settings.find_one({"id": "default"}, {"_id": 0})
    if not record or record.get("migrations_applied") is None or \
            migration_id in (record.get("migrations_applied") or []):
        return {"dibuang": {}}

    def bersihkan(perms: Dict[str, Any]) -> Dict[str, List[str]]:
        """Pasangan yang dibuang dari `perms` (diubah di tempat)."""
        out: Dict[str, List[str]] = {}
        for res in resources:
            if res in perms:
                out[res] = list(perms.pop(res) or [])
        for res, act in pairs:
            acts = perms.get(res)
            if isinstance(acts, list) and act in acts:
                perms[res] = [a for a in acts if a != act]
                out.setdefault(res, []).append(act)
                if not perms[res]:
                    del perms[res]
        return out

    matrix: Dict[str, Any] = record.get("matrix") or {}
    removed = {rid: hit for rid, perms in matrix.items() if isinstance(perms, dict) and (hit := bersihkan(perms))}
    applied = record.get("defaults_applied")
    applied_hit = {rid: hit for rid, perms in (applied or {}).items()
                   if isinstance(perms, dict) and (hit := bersihkan(perms))}
    patch: Dict[str, Any] = {}
    if removed:
        patch.update({"matrix": matrix, "updated_at": now_iso()})
    if applied_hit:
        patch["defaults_applied"] = applied
    update: Dict[str, Any] = {"$addToSet": {"migrations_applied": migration_id}}
    if patch:
        update["$set"] = patch
    await db.permission_settings.update_one({"id": "default"}, update)
    for c in await db.custom_roles.find({}, {"_id": 0}).to_list(500):
        pending = {k: list(v or []) for k, v in (c.get("pending_defaults") or {}).items()}
        bersihkan(pending)
        await db.custom_roles.update_one({"id": c["id"]}, {"$set": {
            "levels": {k: v["level"] for k, v in levels_of(matrix.get(c["id"]) or {}).items()},
            "pending_defaults": {k: v for k, v in pending.items() if v}}})
    if removed:
        from dependencies import audit
        await audit(pelaku, "role_catalog_cleaned", "permission_settings", "default", removed, reason=alasan)
    return {"dibuang": removed}


_HIDDEN: Dict[str, List[str]] = {}
_ASSIGNABLE: Dict[str, List[str]] = {}


async def load_hidden_views() -> Dict[str, List[str]]:
    rec = await db.permission_settings.find_one({"id": "default"}, {"_id": 0, "hidden_views": 1,
                                                                    "assignable_roles": 1}) or {}
    _HIDDEN.clear()
    _HIDDEN.update(rec.get("hidden_views") or {})
    # MN-T1 — id menu yang tidak lagi dikenal katalog (mis. grup `kas-aset` yang dihapus MN-T1) dibuang SAAT DIMUAT, supaya
    # editor peran yang menyimpan ulang daftar ini tidak ditolak "Menu/tab tidak dikenal" (`_clean_hidden`). Data
    # tersimpan tidak diubah di sini; tergantikan saat peran disimpan.
    from access_modules import all_nav_ids
    known = all_nav_ids()
    for rid, vals in list(_HIDDEN.items()):
        if any(v not in known for v in (vals or [])):
            _HIDDEN[rid] = [v for v in vals if v in known]
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
    inactive = await _users_by_role(active=False)
    return [_role_view(rid, matrix, users, cdocs, inactive) for rid in reg.role_ids()]


async def get_role(rid: str) -> Dict[str, Any]:
    await sync_registry()
    if rid not in reg.ROLES:
        raise HTTPException(status_code=404, detail="Peran tidak ditemukan.")
    await load_hidden_views()
    cdocs = {c["id"]: c for c in await list_custom()}
    out = _role_view(rid, await _matrix(), await _users_by_role(), cdocs, await _users_by_role(active=False))
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
    if base in LOCKED_ROLES:   # PR-T6 — satu istilah "peran dasar" (dulu "peran acuan (template)")
        raise HTTPException(status_code=400, detail=MSG_BASE_ADMIN)
    if base and (base not in reg.ROLES):
        raise HTTPException(status_code=400, detail=MSG_BASE_UNKNOWN)
    levels = _clean_levels(payload.get("levels"))
    hidden_in = _clean_hidden(payload.get("hidden_views")) if payload.get("hidden_views") is not None else None
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
    if hidden_in is not None:   # PR-T6 (PR-UX-37) — menu tersembunyi ikut dalam satu panggilan pembuatan
        await _save_hidden(rid, hidden_in)
        await load_hidden_views()
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
    new_base = await _clean_base_change(rid, custom, payload)   # PR-T6 — peran dasar (hanya peran kustom)
    if "levels" in payload and payload["levels"] is not None:
        levels = _clean_levels(payload["levels"])
        current = matrix.get(rid)
        if current is None:
            current = DEFAULT_PERMISSIONS.get(rid, {})
        matrix[rid] = apply_levels(deepcopy(current), levels)
        changes["levels"] = levels
    if payload.get("hidden_views") is not None:
        hv = _clean_hidden(payload["hidden_views"])
        await _save_hidden(rid, hv)
        changes["hidden_views"] = hv
    accounts_to_review: Optional[List[Dict[str, Any]]] = None
    was_cross = bool(reg.ROLES[rid].get("cross_entity"))
    if payload.get("cross_entity") is not None:
        want = bool(payload["cross_entity"])
        # Peran bawaan: sama dengan bawaan → "ikut bawaan" (perubahan bawaan sistem tetap mengalir). PR-T6: peran kustom
        # SELALU menyimpan nilai eksplisit (dulu "sama dengan bawaan" disimpan "ikut", lalu nilai efektifnya mengikuti
        # peran dasar yang sudah diubah — mematikan lintas PT tidak berefek).
        await _set_cross_entity(rid, want if custom else (None if want == reg.cross_entity_default(rid) else want))
        changes["cross_entity"] = want
        if was_cross and not want:   # PR-T6 — penugasan tidak diubah otomatis; Admin meninjau daftarnya
            accounts_to_review = await _accounts_to_review(rid)
    elif new_base is not None and custom and new_base != (reg.ROLES[rid].get("base_role") or ""):
        # PR-T6 — mengganti peran dasar tidak mengubah lintas PT: nilai efektif sekarang dipatok bila belum disimpan.
        stored = ((await db.permission_settings.find_one({"id": "default"}, {"_id": 0, "cross_entity": 1}) or {})
                  .get("cross_entity") or {})
        if rid not in stored:
            await _set_cross_entity(rid, was_cross)
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
        if new_base is not None:   # PR-T6 — izin tidak berubah; sifat turunan & menu warisan ikut peran dasar baru
            patch["base_role"] = new_base
            changes["base_role"] = new_base
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
    if accounts_to_review is not None:
        out["accounts_to_review"] = accounts_to_review
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
    """Pratinjau hak (tanpa menyimpan): notifikasi giliran, layar yang notifikasinya lolos, tingkat — PR-T6: + `summary`
    (ringkasan peran dari izin, peran dasar, sifat, dan lintas PT yang sedang disunting) dan `nav_added` (menu peran
    bawaan yang bertambah dibanding izin bawaannya)."""
    await sync_registry()
    rid = (payload.get("role_id") or "").strip()
    base_in = payload.get("base_role")
    base_in = base_in.strip() if isinstance(base_in, str) else None
    src = rid or (base_in or "")
    if src and src not in reg.ROLES:
        raise HTTPException(status_code=400, detail=MSG_BASE_UNKNOWN)
    matrix = await _matrix()
    current = matrix.get(src) if src else {}
    if current is None:
        current = DEFAULT_PERMISSIONS.get(src, {})
    perms = apply_levels(deepcopy(current or {}), _clean_levels(payload.get("levels")))
    if payload.get("permissions") is not None:
        perms = _clean_perms(payload["permissions"])
    if base_in and base_in not in reg.ROLES:
        raise HTTPException(status_code=400, detail=MSG_BASE_UNKNOWN)
    from services.role_insight_service import role_summary   # PR-T6
    summary = await role_summary(rid or None, perms=perms, base_role=base_in, traits=payload.get("traits"),
                                 cross_entity=payload.get("cross_entity"))
    return {"turn_alerts": _turn_alerts(perms), "screens": sorted(nav_allowed_for_perms(perms)),
            "levels": levels_of(perms), "summary": summary, "nav_added": reg.nav_added_for(rid, perms)}


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
    rows = await db.users.find(query, {"_id": 0, "id": 1, "name": 1}).to_list(500)
    # PR-T6 — tiap akun lewat jalur ubah akun yang sama dengan layar Akun & Akses: penugasan PT dihitung ulang menurut
    # aturan peran tujuan dan sesinya dicabut (dulu `role` ditulis langsung). Akun yang ditolak dilaporkan, bukan
    # menggagalkan seluruh pemindahan. `updated` dipakai router untuk jejak audit per akun (tidak dikirim ke layar).
    from services.user_admin_service import update_user
    moved, failed, updated = [], [], []
    for u in rows:
        try:
            updated.append(await update_user(u["id"], {"role": to_role}))
            moved.append(u["id"])
        except HTTPException as exc:
            failed.append({"id": u["id"], "name": u.get("name", ""),
                           "reason": exc.detail if isinstance(exc.detail, str) else str(exc.detail)})
    return {"from_role": rid, "to_role": to_role, "to_role_label": reg.role_label(to_role),
            "moved": len(moved), "user_ids": moved, "failed": failed, "updated": updated}


async def assert_valid_role_async(role: str) -> str:
    await sync_registry()
    return reg.assert_valid_role(role)


def nav_of(levels: Dict[str, str]) -> Dict[str, List[str]]:
    return nav_for_levels(levels)


# ─── PR-T6 — peran dasar, menu saat dibuat, lintas PT ─────────────────────────────────────────────────────────────────
MSG_BASE_CUSTOM_ONLY = "Peran dasar hanya bisa diatur pada peran kustom."
MSG_BASE_ADMIN = "Peran Admin tidak bisa dijadikan peran dasar."
MSG_BASE_UNKNOWN = "Peran dasar tidak dikenal."


async def _save_hidden(rid: str, hidden: List[str]) -> None:
    """Simpan menu/tab yang disembunyikan satu peran (`permission_settings.hidden_views.<id>`, pola `_set_cross_entity`)."""
    await db.permission_settings.update_one({"id": "default"}, {"$set": {f"hidden_views.{rid}": hidden}}, upsert=True)


def _clean_hidden(values: Any) -> List[str]:
    """Id menu/tab yang disembunyikan (400 bila tidak dikenal) — dipakai buat (PR-UX-37) dan ubah peran."""
    from access_modules import all_nav_ids
    vals = [str(v) for v in (values or [])]
    bad = [v for v in vals if v not in all_nav_ids()]
    if bad:
        raise HTTPException(status_code=400, detail=f"Menu/tab tidak dikenal: {', '.join(bad)}")
    return sorted(set(vals))


async def _clean_base_change(rid: str, custom: bool, payload: Dict[str, Any]) -> Optional[str]:
    """`base_role` di PATCH: None = tidak diubah; "" = tanpa peran dasar; selain itu peran bawaan selain Admin.
    Diperiksa SEBELUM apa pun ditulis."""
    if payload.get("base_role") is None:
        return None
    if not custom:
        raise HTTPException(status_code=400, detail=MSG_BASE_CUSTOM_ONLY)
    base = str(payload["base_role"]).strip()
    if base in LOCKED_ROLES:
        raise HTTPException(status_code=400, detail=MSG_BASE_ADMIN)
    if base and (base not in DEFAULT_PERMISSIONS or base == rid):
        raise HTTPException(status_code=400, detail=MSG_BASE_UNKNOWN)
    return base


async def _entity_labels() -> Dict[str, str]:
    return {e["id"]: e.get("short_name") or e.get("legal_name") or "PT tanpa nama"
            for e in await db.business_entities.find({}, {"_id": 0, "id": 1, "short_name": 1, "legal_name": 1})
            .to_list(500)}


async def _accounts_to_review(rid: str) -> List[Dict[str, Any]]:
    """Akun peran `rid` yang penugasannya lebih dari satu PT (ditinjau Admin sesudah lintas PT dimatikan)."""
    labels = await _entity_labels()
    rows = await db.users.find({"role": rid}, {"_id": 0, "id": 1, "name": 1, "allowed_entity_ids": 1}) \
        .sort("name", 1).to_list(500)
    return [{"id": u["id"], "name": u.get("name", ""),
             "allowed_entities": [labels.get(e, "PT tidak dikenal") for e in u.get("allowed_entity_ids") or []]}
            for u in rows if len(u.get("allowed_entity_ids") or []) > 1]


def projected_scope_after(rid: str, traits: Optional[Dict[str, Any]], base_role: Optional[str]) -> Optional[str]:
    """Cakupan data HASIL simpan bila PATCH juga mengganti peran dasar (sifat yang belum diisi sendiri ikut peran dasar
    baru). `None` = cakupan tidak berubah oleh simpan ini."""
    if base_role is None:
        return projected_scope(rid, traits)
    from services.role_insight_service import hypothetical_traits
    after = hypothetical_traits(rid, base_role.strip(), traits, {})[0]["data_scope"]
    return None if after == reg.traits_of(rid)["data_scope"] else after
