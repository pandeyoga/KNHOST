"""IMP-20 (P01) — cakupan LOKASI KERJA pengguna gudang (site → gudang).

Berbeda dari pemilik stok (`owner_entity_id`) dan hak pakai gudang shared/dedicated
(`warehouse_scope_service`). Penugasan: `users.location_site_ids` (semua gudang di site)
dipersempit opsional oleh `users.location_warehouse_ids`. Operator tanpa penugasan
tidak melihat pekerjaan gudang mana pun saat pembatasan aktif. Supervisor (DEC-09)
melihat semua lokasi dan boleh mengambil alih tugas dengan alasan tercatat.

FIX-1 (audit WMS-RFID 9 Nov 2026, K-B1-01) — DUA lapis yang sengaja dipisah:
  * **Pagar keras** (`warehouse_ids_for`) — hanya kategori kerja "gudang" (PR-T4; bawaan peran `warehouse`) saat setelan
    `wms.location_scope_enforced` aktif. Dipakai SEMUA pemeriksa akses (daftar, detail,
    aksi tulis). Tidak bisa dilepas pengguna.
  * **Saringan tampilan** (`view_for`) — SEMUA akun yang punya lokasi kerja: daftar tugas &
    tampilan stok/roll WMS-RFID bawaannya = gedung di lokasi kerja. Supervisor & peran
    non-gudang boleh memilih "Semua lokasi" / lokasi lain lewat header `X-Location-Scope`
    (aksi eksplisit di bilah cakupan); petugas `warehouse` hanya bisa MEMPERSEMPIT di dalam
    pagarnya. Akun tanpa lokasi kerja → mode `unset` (semua lokasi + anjuran mengisi, tampil
    di bilah cakupan — tidak diam-diam).
  * Gedung bertanda data uji (`is_test`, skrip penanda yang bisa dibalik — K-B1-10) tidak
    ikut di tampilan "semua lokasi" & pemilih bawaan.
"""
import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from db import db
from role_registry import role_in  # peran acuan dikenali (keputusan owner 2026-10-21)

SETTING_KEY = "wms.location_scope_enforced"
#: PR-T4 — pagar keras lokasi kerja berlaku untuk kategori kerja ini (dulu nama peran `warehouse`).
SCOPED_CATEGORY = "gudang"
SUPERVISOR_ROLES = {"warehouse_admin", "manager", "admin"}
VIEW_HEADER = "X-Location-Scope"
TEST_FLAG = "is_test"    # K-B1-10 — penanda data uji (dipasang skrip, bisa dibalik)
WAREHOUSE_FIELDS: Dict[str, tuple] = {
    "wms_tasks": ("warehouse_id",), "shipments": ("warehouse_id",),
    "inventory_rolls": ("warehouse_id",), "inventory_movements": ("warehouse_id",),
    "inventory_balances": ("warehouse_id",), "goods_receipts": ("warehouse_id",),
    "warehouse_transfers": ("source_warehouse_id", "dest_warehouse_id"),
    # UAT 24 Okt (P9.5) — Putaway Order dulu di luar lingkup lokasi (petugas Soreang bisa melihat/membuat PA
    # Rancamalang).
    "putaway_orders": ("from_warehouse_id", "to_warehouse_id"),
    # FIX-1 (B2a STM-IN-02, B3a SCP-2, B1 UI-02) — opname/pendaftaran, tag & job cetak RFID, sesi verifikasi,
    # order makloon & retur supplier dulu tidak ikut pagar lokasi (petugas Rancamalang memindai opname Jakarta).
    "cycle_count_sessions": ("warehouse_id",),
    "rfid_tags": ("warehouse_id",),
    "rfid_print_jobs": ("warehouse_id",),
    "rfid_verify_sessions": ("warehouse_id",),
    "makloon_orders": ("from_warehouse_id", "target_warehouse_id"),
    "purchase_returns": ("warehouse_id",),
}
_CACHE: Dict[str, Any] = {"at": 0.0, "on": False}
_TEST_CACHE: Dict[str, Any] = {"at": 0.0, "ids": []}


def invalidate() -> None:
    _CACHE["at"] = 0.0


async def enforced() -> bool:
    if time.monotonic() - _CACHE["at"] > 15:
        from services.config_resolver import value_of
        _CACHE["on"] = bool(await value_of(SETTING_KEY))
        _CACHE["at"] = time.monotonic()
    return _CACHE["on"]


def is_supervisor(user: Dict[str, Any]) -> bool:
    return role_in((user or {}).get("role"), SUPERVISOR_ROLES)


async def warehouse_ids_for(user: Dict[str, Any]) -> Optional[List[str]]:
    """None = tanpa batas lokasi; [] = tidak ada lokasi; selain itu daftar gudang."""
    from role_registry import category_of
    if category_of((user or {}).get("role")) != SCOPED_CATEGORY or not await enforced():
        return None
    sites = user.get("location_site_ids") or []
    whs = user.get("location_warehouse_ids") or []
    if not sites:
        return list(whs)
    ids = [w["id"] async for w in db.warehouses.find({"site_id": {"$in": sites}}, {"_id": 0, "id": 1})]
    return [w for w in ids if w in whs] if whs else ids


def query_for(collection: str, ids: Optional[List[str]]) -> Optional[Dict[str, Any]]:
    fields = WAREHOUSE_FIELDS.get(collection)
    if ids is None or not fields:
        return None
    ors = [{f: {"$in": ids}} for f in fields]
    return ors[0] if len(ors) == 1 else {"$or": ors}


def narrow(collection: str, query: Dict[str, Any], ids: Optional[List[str]]) -> Dict[str, Any]:
    wq = query_for(collection, ids)
    if not wq:
        return query
    q = dict(query or {})
    q["$and"] = [*(q.get("$and") or []), wq]
    return q


def doc_in_scope(collection: str, doc: Dict[str, Any], ids: Optional[List[str]]) -> bool:
    fields = WAREHOUSE_FIELDS.get(collection)
    if ids is None or not fields or not doc:
        return True
    vals = [doc.get(f) for f in fields if doc.get(f)]
    return not vals or any(v in ids for v in vals)


async def assert_warehouse(user: Dict[str, Any], warehouse_id: str, action: str = "mengerjakan ini") -> None:
    ids = await warehouse_ids_for(user)
    if ids is None or not warehouse_id or warehouse_id in ids:
        return
    wh = await db.warehouses.find_one({"id": warehouse_id}, {"_id": 0, "name": 1, "code": 1}) or {}
    from services.warehouse_scope_service import wh_label   # FIX-1 — "Gudang Gudang Utama …" → "Gudang Utama …"
    raise HTTPException(status_code=403, detail=(
        f"{wh_label(wh) if wh else 'Gudang ' + warehouse_id} di luar lokasi tugas Anda — Anda tidak bisa {action}. "
        "Minta supervisor gudang mengambil alih atau admin menambah penugasan lokasi Anda."))


async def summary(user: Dict[str, Any], choice: str = "", entity_id: Optional[str] = None) -> Dict[str, Any]:
    """`entity_id` (M33) — PT aktif di bilah atas; pilihan lokasi hanya gudang yang boleh dipakai PT itu."""
    ids = await warehouse_ids_for(user)
    on = await enforced()
    sites = [s.get("name") async for s in db.warehouse_sites.find(
        {"id": {"$in": user.get("location_site_ids") or []}}, {"_id": 0, "name": 1})]
    whs = [] if ids is None else [w.get("code") or w.get("name") async for w in db.warehouses.find(
        {"id": {"$in": ids}}, {"_id": 0, "code": 1, "name": 1})]
    view = await resolve_view(user, choice)
    home = await home_warehouse_ids(user)
    return {"enforced": on, "role": user.get("role"), "supervisor": is_supervisor(user),
            "restricted": ids is not None, "sites": sites, "warehouses": whs,
            "warehouse_ids": ids, "no_assignment": ids == [],
            # FIX-1 (K-B1-01) — lokasi kerja (semua peran) + cakupan tampilan aktif untuk bilah cakupan.
            "home_set": home is not None, "home_warehouse_ids": home or [],
            "home_label": await _label_for(user.get("location_site_ids") or [], home),
            "view": view, "can_pick_all": ids is None,
            "options": await view_options(user, ids, entity_id)}


# ─── FIX-1 — saringan TAMPILAN lokasi kerja (semua peran) ─────────────────────
async def test_warehouse_ids() -> List[str]:
    """Gudang bertanda data uji (`is_test`) — disembunyikan dari tampilan "semua lokasi" & pemilih bawaan."""
    if time.monotonic() - _TEST_CACHE["at"] > 15:
        _TEST_CACHE["ids"] = [w["id"] async for w in db.warehouses.find({TEST_FLAG: True}, {"_id": 0, "id": 1})]
        _TEST_CACHE["at"] = time.monotonic()
    return list(_TEST_CACHE["ids"])


def invalidate_test_cache() -> None:
    _TEST_CACHE["at"] = 0.0


async def _warehouses_of_sites(site_ids: List[str]) -> List[str]:
    if not site_ids:
        return []
    return [w["id"] async for w in db.warehouses.find({"site_id": {"$in": list(site_ids)}}, {"_id": 0, "id": 1})]


async def home_warehouse_ids(user: Dict[str, Any]) -> Optional[List[str]]:
    """Lokasi kerja akun (SEMUA peran). None = belum diatur (admin mengisinya di Pengguna)."""
    sites = (user or {}).get("location_site_ids") or []
    whs = (user or {}).get("location_warehouse_ids") or []
    if not sites and not whs:
        return None
    if not sites:
        return list(whs)
    ids = await _warehouses_of_sites(sites)
    return [w for w in ids if w in whs] if whs else ids


def parse_choice(raw: Optional[str]) -> Tuple[str, str]:
    """Nilai header `X-Location-Scope`: '' (lokasi kerja) · 'all' · 'site:<id>' · 'wh:<id>'."""
    val = str(raw or "").strip()
    if not val or val in ("home", "default"):
        return "home", ""
    if val == "all":
        return "all", ""
    kind, _, ref = val.partition(":")
    if kind in ("site", "wh") and ref.strip():
        return kind, ref.strip()
    return "home", ""


async def _label_for(site_ids: List[str], ids: Optional[List[str]]) -> str:
    if ids is None:
        return ""
    if site_ids:
        names = [s.get("name") async for s in db.warehouse_sites.find({"id": {"$in": list(site_ids)}}, {"_id": 0, "name": 1})]
        if names:
            whs_in = await _warehouses_of_sites(site_ids)
            narrowed = set(ids) != set(whs_in)
            if not narrowed:
                return ", ".join(n for n in names if n)
    codes = [w.get("code") or w.get("name") async for w in db.warehouses.find({"id": {"$in": list(ids)}}, {"_id": 0, "code": 1, "name": 1})]
    return ", ".join(c for c in codes if c) or "—"


async def resolve_view(user: Dict[str, Any], raw_choice: Optional[str] = "") -> Dict[str, Any]:
    """Cakupan TAMPILAN daftar pekerjaan fisik & stok/roll WMS-RFID.

    Hasil: `ids` (None = semua lokasi), `mode` (home | all | picked | restricted | unset), `label`, `choice`.
    Petugas berpagar (`warehouse` + setelan aktif) tidak bisa melebar: pilihan di luar pagar → kembali ke pagar.
    """
    hard = await warehouse_ids_for(user)
    home = await home_warehouse_ids(user)
    kind, ref = parse_choice(raw_choice)
    picked: Optional[List[str]] = None
    picked_label = ""
    if kind == "site":
        picked = await _warehouses_of_sites([ref])
        site = await db.warehouse_sites.find_one({"id": ref}, {"_id": 0, "name": 1}) or {}
        picked_label = site.get("name") or ref
    elif kind == "wh":
        wh = await db.warehouses.find_one({"id": ref}, {"_id": 0, "id": 1, "code": 1, "name": 1})
        picked = [wh["id"]] if wh else []
        picked_label = (wh or {}).get("name") or (wh or {}).get("code") or ref
    if hard is not None:
        inside = [w for w in (picked or []) if w in hard]
        if picked is not None and inside:
            return {"ids": inside, "mode": "picked", "label": picked_label, "choice": f"{kind}:{ref}", "restricted": True}
        label = await _label_for((user or {}).get("location_site_ids") or [], hard)
        return {"ids": hard, "mode": "restricted", "label": label or "—", "choice": "", "restricted": True,
                "ignored_choice": bool(picked is not None or kind == "all")}
    if kind == "all":
        return {"ids": None, "mode": "all", "label": "Semua lokasi", "choice": "all", "restricted": False}
    if picked is not None:
        return {"ids": picked, "mode": "picked", "label": picked_label, "choice": f"{kind}:{ref}", "restricted": False}
    if home is not None:
        label = await _label_for((user or {}).get("location_site_ids") or [], home)
        return {"ids": home, "mode": "home", "label": label, "choice": "", "restricted": False}
    return {"ids": None, "mode": "unset", "label": "Semua lokasi — lokasi kerja belum diatur", "choice": "",
            "restricted": False}


async def view_for(ctx: Any) -> Dict[str, Any]:
    """Cakupan tampilan untuk konteks permintaan (di-cache di objek konteks — satu kali per permintaan)."""
    cached = getattr(ctx, "_location_view", None)
    if cached is not None:
        return cached
    view = await resolve_view(getattr(ctx, "user", {}) or {}, getattr(ctx, "location_choice", "") or "")
    view["test_ids"] = await test_warehouse_ids() if view["ids"] is None else []
    try:
        setattr(ctx, "_location_view", view)
    except Exception:  # noqa: BLE001 — konteks beku/tiruan uji
        pass
    return view


def narrow_view(collection: str, query: Dict[str, Any], view: Dict[str, Any]) -> Dict[str, Any]:
    """Saring query ke cakupan tampilan; "semua lokasi" tetap membuang gedung data uji."""
    q = narrow(collection, dict(query or {}), view.get("ids"))
    test_ids = view.get("test_ids") or []
    fields = WAREHOUSE_FIELDS.get(collection)
    if view.get("ids") is None and test_ids and fields:
        q["$and"] = [*(q.get("$and") or []), *[{f: {"$nin": test_ids}} for f in fields]]
    return q


def warehouse_filter(view: Dict[str, Any], requested: Optional[str]) -> Any:
    """Nilai filter `warehouse_id` untuk layanan lama yang menerima satu gudang (str) — kini juga `{"$in": [...]}`.

    `requested` di luar cakupan tampilan petugas berpagar → 403 (bukan diam-diam kosong)."""
    ids = view.get("ids")
    if requested:
        if ids is not None and view.get("restricted") and requested not in ids:
            raise HTTPException(status_code=403, detail="Gudang di luar lokasi tugas Anda.")
        return requested
    if ids is not None:
        return {"$in": list(ids)}
    test_ids = view.get("test_ids") or []
    return {"$nin": test_ids} if test_ids else None


async def view_options(user: Dict[str, Any], hard: Optional[List[str]] = None,
                       entity_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Pilihan bilah cakupan: lokasi kerja · semua lokasi (bila boleh) · tiap AREA (site) — tanpa data uji.

    M33 (pemilik 16 Nov) — hanya gudang yang boleh dipakai PT aktif (`warehouse_scope_service.usable_query`: gudang
    bersama + gudang khusus PT itu); daftar area dan jumlah gedungnya diturunkan dari gudang yang lolos.
    M7 — lokasi = AREA ("Rancamalang (5 gedung)"), bukan tiap gudang. Pilihan per gedung hanya untuk petugas
    berpagar (`hard`) yang perlu mempersempit di dalam lokasinya. Nilai `wh:<id>` lama tetap diterima `parse_choice`."""
    from services.warehouse_scope_service import usable_query
    q: Dict[str, Any] = {"active": {"$ne": False}, TEST_FLAG: {"$ne": True}}
    if hard is not None:
        q["id"] = {"$in": list(hard)}
    pt = usable_query(entity_id)
    if pt:
        q = {"$and": [q, pt]}
    whs = [w async for w in db.warehouses.find(q, {"_id": 0, "id": 1, "code": 1, "name": 1, "site_id": 1})]
    site_ids = sorted({w.get("site_id") for w in whs if w.get("site_id")})
    sites = {s["id"]: s async for s in db.warehouse_sites.find(
        {"id": {"$in": site_ids}, TEST_FLAG: {"$ne": True}}, {"_id": 0, "id": 1, "name": 1})}
    out: List[Dict[str, Any]] = [{"value": "", "label": "Lokasi kerja saya", "kind": "home"}]
    if hard is None:
        out.append({"value": "all", "label": "Semua lokasi", "kind": "all"})
    for sid in sorted(sites, key=lambda s: str(sites[s].get("name") or "")):
        n = sum(1 for w in whs if w.get("site_id") == sid)
        out.append({"value": f"site:{sid}", "label": f"{sites[sid].get('name')} ({n} gedung)", "kind": "site"})
    for w in sorted(whs, key=lambda x: str(x.get("code") or x.get("name") or "")):
        # Gudang tanpa area (data lama) tetap bisa dipilih sendiri; gudang ber-area hanya untuk petugas berpagar.
        if hard is None and w.get("site_id") in sites:
            continue
        out.append({"value": f"wh:{w['id']}", "label": f"{w.get('code') or ''} · {w.get('name') or ''}".strip(" ·"),
                    "kind": "wh"})
    return out


async def assert_doc_side(user: Dict[str, Any], doc: Dict[str, Any], field: str, action: str) -> None:
    """Aksi tulis dokumen gudang: gudang SISI aksi (asal untuk terbit/kirim, tujuan untuk tiba/terima) harus di
    lokasi tugas petugas berpagar. STM-IN-02 — dulu hanya daftar & pembuatan yang dicek."""
    await assert_warehouse(user, (doc or {}).get(field) or "", action)


async def validate_assignment(site_ids: List[str], warehouse_ids: List[str]) -> Dict[str, List[str]]:
    site_ids = [s for s in dict.fromkeys(site_ids or []) if s]
    warehouse_ids = [w for w in dict.fromkeys(warehouse_ids or []) if w]
    known_sites = {s["id"] async for s in db.warehouse_sites.find({"id": {"$in": site_ids}}, {"_id": 0, "id": 1})}
    if set(site_ids) - known_sites:
        raise HTTPException(status_code=400, detail=f"Site tidak dikenal: {sorted(set(site_ids) - known_sites)}")
    whs = {w["id"]: w async for w in db.warehouses.find({"id": {"$in": warehouse_ids}}, {"_id": 0, "id": 1, "site_id": 1, "name": 1})}
    if set(warehouse_ids) - set(whs):
        raise HTTPException(status_code=400, detail=f"Gudang tidak dikenal: {sorted(set(warehouse_ids) - set(whs))}")
    if site_ids:
        outside = [w["name"] for w in whs.values() if w.get("site_id") not in site_ids]
        if outside:
            raise HTTPException(status_code=400, detail=(
                f"Gudang {', '.join(outside)} tidak berada di site yang ditugaskan. "
                "Penyempitan gudang hanya boleh di dalam site terpilih."))
    return {"location_site_ids": site_ids, "location_warehouse_ids": warehouse_ids}


async def delivery_clause(ids: Optional[List[str]]) -> Optional[Dict[str, Any]]:
    """Pengiriman (`logistics_deliveries`) tidak menyimpan gudang — lokasinya = gudang surat jalan (`shipments`).
    FIX-1 (B3a SCP-2) — dulu daftar pengiriman tanpa lokasi sama sekali."""
    if ids is None:
        return None
    sids = await db.shipments.distinct("id", {"warehouse_id": {"$in": list(ids)}})
    return {"shipment_ids": {"$in": sids}}


async def assert_delivery(user: Dict[str, Any], delivery: Dict[str, Any], action: str = "mengerjakan pengiriman ini") -> None:
    """Petugas berpagar: pengiriman wajib memuat surat jalan dari gudang lokasi tugasnya."""
    ids = await warehouse_ids_for(user)
    sids = list((delivery or {}).get("shipment_ids") or [])
    if ids is None or not sids:
        return
    whs = await db.shipments.distinct("warehouse_id", {"id": {"$in": sids}})
    if whs and not any(w in ids for w in whs if w):
        raise HTTPException(status_code=404, detail="Data di luar lokasi tugas Anda")


async def inspection_clause(ids: Optional[List[str]]) -> Optional[Dict[str, Any]]:
    """SPK inspeksi tidak menyimpan gudang — lokasinya = gudang tugas penerimaannya (`task_id`). SPK tanpa tugas
    (cek acak/retur) tetap terlihat. FIX-1 (B2a STM-IN-02: 118 SPK lintas lokasi)."""
    if ids is None:
        return None
    tids = [t for t in await db.inspections.distinct("task_id") if t]
    inside = await db.wms_tasks.distinct("id", {"id": {"$in": tids}, "warehouse_id": {"$in": list(ids)}}) if tids else []
    return {"$or": [{"task_id": {"$in": inside}}, {"task_id": {"$in": [None, ""]}}, {"task_id": {"$exists": False}}]}


async def assert_inspection(user: Dict[str, Any], doc: Dict[str, Any]) -> None:
    ids = await warehouse_ids_for(user)
    tid = (doc or {}).get("task_id")
    if ids is None or not tid:
        return
    task = await db.wms_tasks.find_one({"id": tid}, {"_id": 0, "warehouse_id": 1}) or {}
    if task.get("warehouse_id") and task["warehouse_id"] not in ids:
        raise HTTPException(status_code=404, detail="Data di luar lokasi tugas Anda")
