"""PR-T6 — RINGKASAN, POTRET, dan RIWAYAT peran untuk layar "Peran & Hak Akses" dan "Akun & Akses".

`role_summary` menjawab "peran ini akhirnya bisa apa" dari izin + sifat (PR-T4) + lintas PT + batas persetujuan (KP-T4)
+ aksi berisiko (PR-T5). `snapshot` = potret peran untuk `before`/`after` jejak audit; `role_history` membaca selisihnya.
Aturan peran (simpan, peran dasar, lintas PT) tetap di `services/custom_role_service.py`.
"""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
import role_registry as reg
from services.custom_role_service import _HIDDEN, current_permissions, load_hidden_views, sync_registry

TRAIT_TEXT = {"home_view": "Halaman awal", "data_scope": "Data yang terlihat", "kategori_kerja": "Kategori kerja",
              "notify_like": "Notifikasi peran lain"}


def _action_text(res: str, act: str) -> str:
    from access_modules import ACTION_LABEL
    return ACTION_LABEL.get(f"{res}.{act}") or ACTION_LABEL.get(act) or act.replace("_", " ")


def _pair_text(pair: str) -> str:
    from access_modules import RESOURCE_LABEL
    res, _, act = pair.partition(".")
    return f"{RESOURCE_LABEL.get(res, res)}: {_action_text(res, act)}"


def _holds(perms: Dict[str, Any], res: str, act: str) -> bool:
    acts = perms.get(res) or []
    return act in acts or "*" in acts


def hypothetical_traits(rid: Optional[str], base: Optional[str],
                         draft: Optional[Dict[str, Any]], perms: Dict[str, Any]) -> tuple:
    """(sifat efektif, kunci yang mengikuti peran dasar, peran dasar yang dipakai) untuk peran `rid` (None = baru)
    dengan peran dasar `base` (None = tidak diubah) dan draf sifat `draft` (nilai None = kembali ke turunan)."""
    entry = reg.ROLES.get(rid or "") or {}
    custom = not rid or bool(entry.get("custom"))
    use_base = (entry.get("base_role") or "") if base is None else base
    stored = dict(reg.TRAIT_OVERRIDES.get(rid) or {}) if rid else {}
    for k, v in (draft or {}).items():
        if k in reg.TRAIT_KEYS:
            if v is None:
                stored.pop(k, None)
            else:
                stored[k] = v
    out: Dict[str, Any] = {}
    follows: List[str] = []
    for k in reg.TRAIT_KEYS:
        if k in stored:
            out[k] = stored[k]
        elif not custom:
            out[k] = reg.trait_defaults(rid)[k]
        elif use_base and use_base in reg.ROLES and use_base != rid:
            out[k] = [use_base] if k == "notify_like" else reg.traits_of(use_base)[k]
            follows.append(k)
        else:
            out[k] = {"data_scope": "semua", "home_view": reg.PROFILE_HOME[0], "kategori_kerja": "",
                      "notify_like": []}[k]
    if "home_view" in stored and not reg.home_allowed(out["home_view"], perms, out["kategori_kerja"] or ""):
        out["home_view"] = reg.PROFILE_HOME[0]   # sama dengan `apply_traits`: halaman awal tersimpan tanpa izin
    return out, follows, use_base if custom else ""


async def _approvals_of(rid: Optional[str], rank_label: str) -> Any:
    """Batas persetujuan: baris lapisan grup `approval_policies` (KP-T4) yang mencantumkan peran ini; koleksi belum
    berisi → {"follows_rank_of": label peran yang peringkatnya dipakai}."""
    if not await db.approval_policies.count_documents({}):
        return {"follows_rank_of": rank_label}
    if not rid:
        return []
    from approval_kinds import APPROVAL_KINDS
    order = {k: i for i, k in enumerate(APPROVAL_KINDS)}
    rows = await db.approval_policies.find({"entity_id": "all", "active": True, "roles": rid}, {"_id": 0}) \
        .to_list(1000)
    rows.sort(key=lambda r: (order.get(r.get("doc_kind"), 999), int(r.get("level") or 1),
                             float(r.get("min_amount") or 0)))
    out = []
    for r in rows:
        k = APPROVAL_KINDS.get(r.get("doc_kind") or "") or {}
        mx = r.get("max_amount")
        out.append({"label": k.get("label") or r.get("doc_kind") or "", "level": r.get("label") or "Persetujuan",
                    "max_amount": None if mx in (None, "") else float(mx)})
    return out


async def role_summary(rid: Optional[str], *, perms: Optional[Dict[str, Any]] = None, base_role: Optional[str] = None,
                       traits: Optional[Dict[str, Any]] = None, cross_entity: Optional[bool] = None) -> Dict[str, Any]:
    """Ringkasan "peran ini akhirnya bisa apa" (spesifikasi PR-T6 §Server 2): halaman awal, data yang terlihat,
    kategori kerja, lintas PT, batas persetujuan, aksi per modul (bisa / tidak bisa per halaman), aksi berisiko, dan
    sifat yang masih mengikuti peran dasar. Tanpa `perms` = izin tersimpan peran `rid`."""
    from access_modules import MODULE_CATALOG, RESOURCE_LABEL, SENSITIVE_ACTIONS, full_actions, level_of
    await sync_registry()
    if rid and rid not in reg.ROLES:
        raise HTTPException(status_code=404, detail="Peran tidak ditemukan.")
    if perms is None:
        perms = await current_permissions(rid) if rid else {}
    t, follows, base = hypothetical_traits(rid, base_role, traits, perms)
    entry = reg.ROLES.get(rid or "") or {}
    if rid == "admin":
        cross = True
    elif cross_entity is not None:
        cross = bool(cross_entity)
    elif rid:
        cross = bool(entry.get("cross_entity"))   # peran dasar diganti → lintas PT dipatok (update_role)
    else:
        cross = bool((reg.ROLES.get(base) or {}).get("cross_entity")) if base else False
    modules = []
    for m in MODULE_CATALOG:
        info = level_of(perms, m["id"])
        if info["level"] == "none":
            continue
        pages = [{"label": RESOURCE_LABEL.get(r, r),
                  "can": [_action_text(r, a) for a in full_actions(r) if _holds(perms, r, a)],
                  "cannot": [_action_text(r, a) for a in full_actions(r) if not _holds(perms, r, a)]}
                 for r in m["resources"]]
        modules.append({"id": m["id"], "label": m["label"], "level": info["level"],
                        "partial": bool(info.get("partial")), "held": info["held"], "total": info["total"],
                        "pages": pages})
    risky: List[str] = []
    for (res, act), kalimat in SENSITIVE_ACTIONS.items():
        if _holds(perms, res, act) and kalimat not in risky:
            risky.append(kalimat)
    base_label = reg.role_label(base) if base else ""
    rank_label = base_label or (reg.role_label(rid) if rid else "peran ini")
    home = reg.HOME_BY_VIEW.get(t["home_view"]) or {}
    return {
        "home": {"view": t["home_view"], "label": home.get("label") or "Profil Saya"},
        "data_scope": {"value": t["data_scope"], "label": reg.DATA_SCOPE_LABEL.get(t["data_scope"], t["data_scope"])},
        "kategori": {"value": t["kategori_kerja"] or "",
                     "label": reg.WORK_CATEGORY_LABEL.get(t["kategori_kerja"] or "", t["kategori_kerja"])},
        "cross_entity": cross,
        "approvals": await _approvals_of(rid, rank_label),
        "modules": modules,
        "risky": risky,
        "follows_base": [f"{TRAIT_TEXT[k]} mengikuti {base_label}" for k in follows] if base_label else [],
    }


EMPTY_SNAPSHOT: Dict[str, Any] = {"permissions": [], "hidden_views": [], "cross_entity": False, "traits": {},
                                  "base_role": ""}


async def snapshot(rid: str) -> Dict[str, Any]:
    """Potret peran untuk jejak audit (`before`/`after`). `permissions` = daftar "sumber_daya.aksi" terurut (bukan
    peta: kunci seperti `gl_mapping` akan disamarkan penyaring rahasia audit). Peran tidak ada = potret kosong."""
    await sync_registry()
    if rid not in reg.ROLES:
        return dict(EMPTY_SNAPSHOT)
    await load_hidden_views()
    perms = await current_permissions(rid)
    return {"permissions": sorted(f"{r}.{a}" for r, acts in perms.items() for a in acts or []),
            "hidden_views": sorted(_HIDDEN.get(rid, [])),
            "cross_entity": bool(reg.ROLES[rid].get("cross_entity")),
            "traits": reg.traits_of(rid),
            "base_role": (reg.ROLES[rid].get("base_role") or "") if reg.ROLES[rid].get("custom") else ""}


HISTORY_ACTIONS = {
    "role_access_updated": "Hak akses diubah", "role_access_reset": "Dikembalikan ke bawaan",
    "custom_role_created": "Peran dibuat", "custom_role_deleted": "Peran dihapus",
    "role_followed_base": "Mengikuti izin baru peran dasar", "role_users_moved": "Akun dipindahkan ke peran lain",
}


def _trait_value_text(key: str, value: Any) -> str:
    if key == "data_scope":
        return reg.DATA_SCOPE_LABEL.get(value, value or "—")
    if key == "kategori_kerja":
        return reg.WORK_CATEGORY_LABEL.get(value or "", value or "—")
    if key == "home_view":
        return (reg.HOME_BY_VIEW.get(value or "") or {}).get("label") or "—"
    names = [reg.role_label(v) for v in (value or [])]
    return ", ".join(names) if names else "Tidak ada"


def _other_lines(action: str, before: Dict[str, Any], after: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    if action in ("custom_role_created", "custom_role_deleted"):
        base = after.get("base_role") if action == "custom_role_created" else before.get("base_role")
        if base:
            out.append(f"Peran dasar: {reg.role_label(base)}")
        return out
    bt, at = before.get("traits") or {}, after.get("traits") or {}
    for k in reg.TRAIT_KEYS:
        if k in bt and k in at and bt[k] != at[k]:
            out.append(f"{TRAIT_TEXT[k]}: {_trait_value_text(k, bt[k])} → {_trait_value_text(k, at[k])}")
    hb, ha = set(before.get("hidden_views") or []), set(after.get("hidden_views") or [])
    if hb != ha:
        parts = [f"{len(ha - hb)} disembunyikan" if ha - hb else "", f"{len(hb - ha)} ditampilkan lagi" if hb - ha else ""]
        out.append("Menu & tab: " + ", ".join(p for p in parts if p))
    if "cross_entity" in before and "cross_entity" in after and bool(before["cross_entity"]) != bool(after["cross_entity"]):
        onoff = {True: "semua PT aktif", False: "hanya PT yang ditugaskan"}
        out.append(f"PT: {onoff[bool(before['cross_entity'])]} → {onoff[bool(after['cross_entity'])]}")
    if before.get("base_role", "") != after.get("base_role", "") and ("base_role" in before or "base_role" in after):
        out.append(f"Peran dasar: {_base_text(before.get('base_role'))} → {_base_text(after.get('base_role'))}")
    return out


def _base_text(base: Optional[str]) -> str:
    return reg.role_label(base) if base else "tanpa peran dasar"


async def role_history(rid: str, limit: int = 50) -> Dict[str, Any]:
    """Riwayat perubahan peran dari jejak audit (`before`/`after` potret PR-T6). Terbaru dulu."""
    await sync_registry()
    lim = max(1, min(int(limit or 50), 200))
    rows = await db.audit_logs.find({"entity_type": "custom_role", "entity_id": rid,
                                     "action": {"$in": list(HISTORY_ACTIONS)}}, {"_id": 0}) \
        .sort("timestamp", -1).to_list(lim)
    items = []
    for row in rows:
        action = row.get("action") or ""
        before, after = row.get("before") or {}, row.get("after") or {}
        added: List[str] = []
        removed: List[str] = []
        other: List[str] = []
        users = int(after.get("users") or before.get("users") or 0)
        if action == "role_users_moved":
            users = int(after.get("moved") or 0)
            other.append(f"{users} akun dipindahkan ke {after.get('to_role_label') or reg.role_label(after.get('to_role', ''))}")
        elif isinstance(after.get("permissions"), list) and isinstance(before.get("permissions"), list):
            b, a = set(before["permissions"]), set(after["permissions"])
            added = [_pair_text(p) for p in sorted(a - b)]
            removed = [_pair_text(p) for p in sorted(b - a)]
            other = _other_lines(action, before, after)
        else:
            other.append("Rincian perubahan tidak tercatat (perubahan sebelum riwayat peran tersedia).")
        items.append({"at": row.get("timestamp", ""), "actor": row.get("actor", ""), "action": action,
                      "action_label": HISTORY_ACTIONS.get(action, "Perubahan"), "added": added, "removed": removed,
                      "other": other, "users": users})
    return {"items": items}
