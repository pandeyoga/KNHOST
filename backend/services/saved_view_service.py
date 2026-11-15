"""FIX-8 (K-B4-12 = YA, B4 §3.4 [6–8]) — TAMPILAN TERSIMPAN daftar utama gudang.

Satu tampilan = kombinasi **saringan + urut + kolom (+ mode tampilan)** sebuah daftar, disimpan DI SERVER per pengguna
(koleksi `saved_views`), dipulihkan saat daftar dibuka. Admin boleh MEMBAGIKAN tampilan ke peran dan/atau PT
(opsional ditandai "bawaan" untuk penerimanya).

Aturan yang dijamin di sini (bukan di klien):
  · Daftar & isi state di-whitelist per daftar (`LISTS`): hanya kunci saringan/urut/kolom/mode yang dikenal daftar itu.
    Kunci CAKUPAN (PT aktif, lokasi kerja, site — FIX-1) TIDAK PERNAH disimpan: cakupan tetap dari bilah
    "Lokasi: … ▾" + pemilih PT dan dipagari endpoint daftarnya. Tampilan tidak bisa memperluas data yang terlihat.
  · Izin melihat/menyimpan tampilan = izin melihat daftarnya (mis. `transfer.view` untuk daftar Transfer).
  · Pribadi: hanya pemilik yang melihat/mengubah/menghapus. Dibagikan: hanya **admin** yang membagikan, mengubah,
    atau menghapus; penerima = peran cocok (bila diisi) DAN PT yang ia baca beririsan (bila diisi). PT tujuan wajib
    PT yang bisa dibaca admin itu.
  · Bawaan: satu tampilan pribadi per pengguna per daftar (`is_default`); bawaan bersama (`share.is_default`) dipakai
    bila pengguna belum punya bawaan pribadi.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from core_utils import new_id, now_iso
from db import db

COLL = "saved_views"
MAX_PER_USER_LIST = 30
MAX_STATE_BYTES = 4096
SCOPE_KEYS = frozenset({"entity_id", "owner_entity_id", "entity", "entity_scope", "location", "location_view",
                        "location_scope", "site_id", "site", "scope", "work_entity_id"})

#: Daftar yang punya tampilan tersimpan. `perm` = izin lihat daftar (sama dengan endpoint daftarnya).
LISTS: Dict[str, Dict[str, Any]] = {
    "wms.inventory_rolls": {
        "label": "Operasi Gudang › Stok › Roll", "perm": ("product", "view"),
        "filters": {"warehouse_id", "line", "check", "peg_only"},
        "sorts": set(), "columns": {"owner", "warehouse", "lot", "dye_lot", "grade", "weight", "pegging"},
        "modes": {"list", "group"},
    },
    "wms.transfers": {
        "label": "Operasi Gudang › Transfer", "perm": ("transfer", "view"),
        "filters": {"kind", "status", "line"},
        "sorts": {"created_at", "code", "status"},
        "columns": {"items", "requested_by", "approved_by"}, "modes": set(),
    },
    "wms.outbound_tasks": {
        "label": "Barang Keluar › Tugas", "perm": ("wms", "view"),
        "filters": {"status", "warehouse_id", "kind"},
        "sorts": set(), "columns": set(), "modes": set(),
    },
}


def _is_admin(user: Dict[str, Any]) -> bool:
    return (user or {}).get("role") == "admin"


def list_spec(list_key: str) -> Dict[str, Any]:
    spec = LISTS.get((list_key or "").strip())
    if not spec:
        raise HTTPException(status_code=400, detail=f"Daftar tidak mendukung tampilan tersimpan: {list_key or '(kosong)'}")
    return spec


def _clean_value(key: str, val: Any) -> Any:
    if isinstance(val, bool) or val is None:
        return val
    if isinstance(val, (int, float)):
        if val != val or val in (float("inf"), float("-inf")):   # NaN/Inf
            raise HTTPException(status_code=400, detail=f"Nilai saringan “{key}” tidak sah.")
        return val
    if isinstance(val, str):
        if len(val) > 200:
            raise HTTPException(status_code=400, detail=f"Nilai saringan “{key}” terlalu panjang (maks. 200 huruf).")
        return val
    if isinstance(val, list):
        if len(val) > 50 or not all(isinstance(x, str) and len(x) <= 200 for x in val):
            raise HTTPException(status_code=400, detail=f"Nilai saringan “{key}” tidak sah (daftar teks ≤ 50 butir).")
        return val
    raise HTTPException(status_code=400, detail=f"Nilai saringan “{key}” tidak sah.")


def clean_state(list_key: str, state: Any) -> Dict[str, Any]:
    """Whitelist isi tampilan. Kunci cakupan (PT/lokasi) ditolak dengan pesan jelas — bukan dibuang diam-diam."""
    spec = list_spec(list_key)
    if not isinstance(state, dict):
        raise HTTPException(status_code=400, detail="Isi tampilan harus objek {filters, sort, columns, mode}.")
    extra = set(state) - {"filters", "sort", "columns", "mode"}
    if extra:
        raise HTTPException(status_code=400, detail=f"Bagian tampilan tidak dikenal: {', '.join(sorted(extra))}.")
    out: Dict[str, Any] = {"filters": {}, "sort": None, "columns": [], "mode": ""}
    filters = state.get("filters") or {}
    if not isinstance(filters, dict):
        raise HTTPException(status_code=400, detail="Saringan tampilan harus objek.")
    for k, v in filters.items():
        if k in SCOPE_KEYS:
            raise HTTPException(status_code=400, detail=(
                f"Saringan “{k}” adalah cakupan PT/lokasi — cakupan tidak disimpan di tampilan "
                "(diatur lewat bilah Lokasi & pemilih PT)."))
        if k not in spec["filters"]:
            raise HTTPException(status_code=400, detail=f"Saringan “{k}” tidak dikenal untuk daftar ini.")
        out["filters"][k] = _clean_value(k, v)
    sort = state.get("sort")
    if sort:
        if not isinstance(sort, dict) or sort.get("key") not in spec["sorts"] or sort.get("dir", "asc") not in ("asc", "desc"):
            raise HTTPException(status_code=400, detail="Urutan tampilan tidak dikenal untuk daftar ini.")
        out["sort"] = {"key": sort["key"], "dir": sort.get("dir", "asc")}
    cols = state.get("columns") or []
    if not isinstance(cols, list) or not all(isinstance(c, str) and c in spec["columns"] for c in cols):
        raise HTTPException(status_code=400, detail="Kolom tampilan tidak dikenal untuk daftar ini.")
    out["columns"] = list(dict.fromkeys(cols))
    mode = state.get("mode") or ""
    if mode and mode not in spec["modes"]:
        raise HTTPException(status_code=400, detail="Mode tampilan tidak dikenal untuk daftar ini.")
    out["mode"] = mode
    if len(json.dumps(out, ensure_ascii=False)) > MAX_STATE_BYTES:
        raise HTTPException(status_code=400, detail="Isi tampilan terlalu besar.")
    return out


def clean_name(name: Any) -> str:
    s = " ".join(str(name or "").split())
    if not s:
        raise HTTPException(status_code=400, detail="Isi nama tampilan.")
    if len(s) > 60:
        raise HTTPException(status_code=400, detail="Nama tampilan maksimal 60 huruf.")
    return s


async def clean_share(user: Dict[str, Any], share: Any) -> Dict[str, Any]:
    """Bagikan ke peran/PT — hanya admin; PT tujuan wajib PT yang bisa dibaca admin itu."""
    share = share or {}
    if not isinstance(share, dict):
        raise HTTPException(status_code=400, detail="Bagian berbagi harus objek {roles, entity_ids, is_default}.")
    roles = [str(r).strip() for r in (share.get("roles") or []) if str(r).strip()]
    ents = [str(e).strip() for e in (share.get("entity_ids") or []) if str(e).strip()]
    is_def = bool(share.get("is_default"))
    if not roles and not ents:
        if is_def:
            raise HTTPException(status_code=400, detail="Bawaan bersama butuh penerima (peran atau PT).")
        return {"roles": [], "entity_ids": [], "is_default": False}
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Hanya admin yang boleh membagikan tampilan ke peran atau PT.")
    import role_registry as reg
    bad = [r for r in roles if not reg.is_role(r)]
    if bad:
        raise HTTPException(status_code=400, detail=f"Peran tidak dikenal: {', '.join(bad)}.")
    from services.entity_lifecycle_service import readable_entity_ids
    readable = set(await readable_entity_ids(user))
    out_of = [e for e in ents if e not in readable]
    if out_of:
        raise HTTPException(status_code=403, detail="Tampilan hanya boleh dibagikan ke PT yang bisa Anda akses.")
    return {"roles": sorted(set(roles)), "entity_ids": sorted(set(ents)), "is_default": is_def}


def _is_shared(view: Dict[str, Any]) -> bool:
    sh = view.get("share") or {}
    return bool(sh.get("roles") or sh.get("entity_ids"))


def _applies_to(view: Dict[str, Any], user: Dict[str, Any], readable: set) -> bool:
    sh = view.get("share") or {}
    roles, ents = sh.get("roles") or [], sh.get("entity_ids") or []
    if not roles and not ents:
        return False
    if roles and user.get("role") not in roles:
        return False
    if ents and not (set(ents) & readable):
        return False
    return True


def public(view: Dict[str, Any], user: Dict[str, Any], readable: set) -> Dict[str, Any]:
    mine = view.get("owner_user_id") == user.get("id")
    shared = _is_shared(view)
    return {
        "id": view["id"], "list_key": view["list_key"], "name": view["name"], "state": view.get("state") or {},
        "share": view.get("share") or {"roles": [], "entity_ids": [], "is_default": False},
        "is_default": bool(view.get("is_default")) if mine else False,
        "owner_name": view.get("owner_name") or "", "mine": mine, "shared": shared,
        "applies_to_me": mine or _applies_to(view, user, readable),
        "can_edit": (mine and not shared) or _is_admin(user),
        "updated_at": view.get("updated_at") or view.get("created_at") or "",
    }


async def _readable(user: Dict[str, Any]) -> set:
    from services.entity_lifecycle_service import readable_entity_ids
    return set(await readable_entity_ids(user))


async def list_views(user: Dict[str, Any], list_key: str) -> Dict[str, Any]:
    list_spec(list_key)
    readable = await _readable(user)
    rows = await db[COLL].find({"list_key": list_key}, {"_id": 0}).sort("name", 1).to_list(500)
    out: List[Dict[str, Any]] = []
    for v in rows:
        mine = v.get("owner_user_id") == user.get("id")
        if mine or _applies_to(v, user, readable) or (_is_admin(user) and _is_shared(v)):
            out.append(public(v, user, readable))
    own_def = next((v for v in out if v["mine"] and v["is_default"]), None)
    shared_defs = sorted((v for v in out if v["shared"] and v["applies_to_me"] and v["share"].get("is_default")),
                         key=lambda v: v["updated_at"], reverse=True)
    default = own_def or (shared_defs[0] if shared_defs else None)
    return {"list_key": list_key, "label": LISTS[list_key]["label"], "items": out,
            "default_id": default["id"] if default else "", "can_share": _is_admin(user),
            "spec": {"filters": sorted(LISTS[list_key]["filters"]), "sorts": sorted(LISTS[list_key]["sorts"]),
                     "columns": sorted(LISTS[list_key]["columns"]), "modes": sorted(LISTS[list_key]["modes"])}}


async def _get_owned_or_admin(user: Dict[str, Any], view_id: str) -> Dict[str, Any]:
    v = await db[COLL].find_one({"id": view_id}, {"_id": 0})
    if not v:
        raise HTTPException(status_code=404, detail="Tampilan tidak ditemukan.")
    mine = v.get("owner_user_id") == user.get("id")
    if _is_shared(v):
        if not _is_admin(user):
            raise HTTPException(status_code=403, detail="Tampilan bersama hanya bisa diubah admin.")
    elif not mine:
        # Tampilan pribadi orang lain tidak pernah terbaca — 404 (bukan 403) supaya keberadaannya tidak bocor.
        raise HTTPException(status_code=404, detail="Tampilan tidak ditemukan.")
    return v


async def _unset_other_defaults(user_id: str, list_key: str, keep_id: str) -> None:
    await db[COLL].update_many({"owner_user_id": user_id, "list_key": list_key, "id": {"$ne": keep_id},
                                "is_default": True}, {"$set": {"is_default": False}})


async def create_view(user: Dict[str, Any], body: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    list_key = (body.get("list_key") or "").strip()
    list_spec(list_key)
    n = await db[COLL].count_documents({"owner_user_id": user["id"], "list_key": list_key})
    if n >= MAX_PER_USER_LIST:
        raise HTTPException(status_code=400, detail=f"Maksimal {MAX_PER_USER_LIST} tampilan per daftar — hapus yang lama dulu.")
    doc = {
        "id": new_id("sv"), "list_key": list_key, "name": clean_name(body.get("name")),
        "state": clean_state(list_key, body.get("state") or {}),
        "share": await clean_share(user, body.get("share")),
        "is_default": bool(body.get("is_default")),
        "owner_user_id": user["id"], "owner_name": user.get("name") or user.get("email") or "",
        "created_at": now_iso(), "updated_at": now_iso(), "updated_by": user["id"],
    }
    await db[COLL].insert_one(dict(doc))
    if doc["is_default"]:
        await _unset_other_defaults(user["id"], list_key, doc["id"])
    readable = await _readable(user)
    return public(doc, user, readable), doc


async def update_view(user: Dict[str, Any], view_id: str, body: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    before = await _get_owned_or_admin(user, view_id)
    patch: Dict[str, Any] = {}
    if "name" in body:
        patch["name"] = clean_name(body.get("name"))
    if "state" in body:
        patch["state"] = clean_state(before["list_key"], body.get("state") or {})
    if "share" in body:
        patch["share"] = await clean_share(user, body.get("share"))
    if "is_default" in body:
        if before.get("owner_user_id") != user.get("id"):
            raise HTTPException(status_code=403, detail="Bawaan pribadi hanya untuk tampilan milik Anda.")
        patch["is_default"] = bool(body.get("is_default"))
    if not patch:
        raise HTTPException(status_code=400, detail="Tidak ada perubahan.")
    patch.update({"updated_at": now_iso(), "updated_by": user["id"]})
    await db[COLL].update_one({"id": view_id}, {"$set": patch})
    if patch.get("is_default"):
        await _unset_other_defaults(user["id"], before["list_key"], view_id)
    after = await db[COLL].find_one({"id": view_id}, {"_id": 0})
    readable = await _readable(user)
    return public(after, user, readable), before, after


async def delete_view(user: Dict[str, Any], view_id: str) -> Dict[str, Any]:
    before = await _get_owned_or_admin(user, view_id)
    await db[COLL].delete_one({"id": view_id})
    return before


def list_perm(list_key: str) -> Optional[Tuple[str, str]]:
    spec = LISTS.get((list_key or "").strip())
    return spec["perm"] if spec else None
