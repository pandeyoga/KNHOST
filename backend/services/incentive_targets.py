"""KM-T1 (KM-04, keputusan K-24) — target insentif per PT dan komponen insentif per PT; `sales_roster`.

Target (`sales_targets`, kunci baru): satu dokumen per (PT, sales, jenis periode, periode) — indeks unik
`uq_target_pt_sales_periode`. Target triwulan dan tahun adalah ANGKA TERSENDIRI (tidak dijumlah dari target bulanan).
PT target = PT konteks pengguna (`02_STANDAR.md` §3.4 N1), bukan PT asal sales. Sales = akun aktif mana pun yang
ditugaskan di PT itu (dulu hanya peran persis `sales`, PR-UX-04).

Komponen (`incentive_components`): daftar per PT — kode huruf besar unik per PT, nama, periode dasar, kolom angka yang
ditampilkan, kena pajak, aktif. Tanpa isi bawaan.

`sales_roster(entity_id, period_type, period)` adalah SATU tempat penentu "daftar sales" untuk layar dan hitungan insentif
(bukan gerbang wewenang): akun yang punya fakta atau target pada periode itu ∪ akun aktif yang perannya — atau peran
acuannya (peran kustom) — `sales`.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from core_utils import new_id, now_iso, safe_doc
from db import db
from services import incentive_periods as ip

TARGETS = "sales_targets"
COMPONENTS = "incentive_components"

PESAN_SALES = "Akun ini tidak ditugaskan di PT yang sedang dibuka."
PESAN_NEGATIF = "Target tidak boleh negatif."
PESAN_KODE_KEMBAR = "Kode komponen sudah dipakai di PT ini."
PESAN_KODE = "Kode komponen hanya huruf besar, angka, garis bawah, atau tanda hubung (paling banyak 24 huruf)."
PESAN_NAMA = "Nama komponen wajib diisi."
PESAN_KOLOM = "Pilih minimal satu angka yang ditampilkan: omzet, pencairan, atau harga."
PESAN_DASAR = "Periode dasar harus bulan, triwulan, tahun, atau bebas."

COMPONENT_BASIS = ("month", "quarter", "year", "free")
COMPONENT_BASIS_LABEL = {"month": "Bulanan", "quarter": "Triwulanan", "year": "Tahunan", "free": "Bebas"}
COMPONENT_COLUMNS = ("omzet", "pencairan", "harga")
COMPONENT_COLUMN_LABEL = {"omzet": "Omzet", "pencairan": "Pencairan", "harga": "Kualitas harga"}
_KODE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,23}$")


class InsentifError(ValueError):
    """Galat isian Target & Aturan dengan kalimat siap tampil; `status` = kode HTTP."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ── Siapa yang boleh diberi target ───────────────────────────────────────────────────────────────────────────────────
def _assigned(user: Dict[str, Any], entity_id: str) -> bool:
    return entity_id in (user.get("allowed_entity_ids") or []) or entity_id in (
        user.get("home_entity_id"), user.get("entity_id"))


async def assigned_user(user_id: str, entity_id: str) -> Dict[str, Any]:
    """Akun aktif yang ditugaskan di PT → dokumennya; selain itu `InsentifError(PESAN_SALES)`."""
    u = await db.users.find_one({"id": user_id or "__none__", "status": "active"},
                                {"_id": 0, "id": 1, "name": 1, "role": 1, "allowed_entity_ids": 1,
                                 "home_entity_id": 1, "entity_id": 1})
    if not u or not _assigned(u, entity_id):
        raise InsentifError(PESAN_SALES)
    return u


def _is_sales_role(role: str) -> bool:
    """Peran `sales` atau peran kustom beracuan `sales` (penentu daftar, bukan wewenang)."""
    from role_registry import base_or_self
    return base_or_self(role) == "sales"


async def sales_roster(entity_id: str, period_type: str = "", period: str = "") -> List[Dict[str, Any]]:
    """Daftar sales PT untuk periode itu: punya fakta/target pada periode ∪ akun aktif berperan (acuan) `sales`."""
    ids: set = set()
    if period_type and period:
        pt, p = ip.normalize(period_type, period)
        months = await ip.months_of(pt, p, entity_id)
        for coll in ("fact_shipment_sales", "fact_collections"):
            ids |= set(await db[coll].distinct("sales_id", {"entity_id": entity_id, "period": {"$in": months}}))
        ids |= set(await db[TARGETS].distinct("sales_id", {"entity_id": entity_id, "period_type": pt, "period": p}))
    ids.discard("")
    out: Dict[str, Dict[str, Any]] = {}
    async for u in db.users.find({"$or": [{"status": "active"}, {"id": {"$in": sorted(ids)}}]},
                                 {"_id": 0, "id": 1, "name": 1, "role": 1, "status": 1, "allowed_entity_ids": 1,
                                  "home_entity_id": 1, "entity_id": 1}):
        if u["id"] in ids or (u.get("status") == "active" and _is_sales_role(u.get("role") or "")
                              and _assigned(u, entity_id)):
            out[u["id"]] = {"id": u["id"], "name": u.get("name") or "", "active": u.get("status") == "active"}
    return sorted(out.values(), key=lambda r: (r["name"].lower(), r["id"]))


# ── Target ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def _amount(v: Any) -> float:
    try:
        n = round(float(v or 0), 2)
    except (TypeError, ValueError):
        raise InsentifError("Target harus berupa angka.")
    if n < 0:
        raise InsentifError(PESAN_NEGATIF)
    return n


async def save_target(entity_id: str, payload: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Simpan target menurut kunci unik (PT, sales, jenis periode, periode); simpan ulang = perbarui."""
    from pymongo.errors import DuplicateKeyError
    try:
        pt, p = ip.normalize(payload.get("period_type"), payload.get("period"))
    except ip.PeriodeError as exc:
        raise InsentifError(str(exc))
    sales = await assigned_user(str(payload.get("sales_id") or ""), entity_id)
    try:
        new_cust = max(0, int(payload.get("target_new_customers") or 0))
    except (TypeError, ValueError):
        raise InsentifError("Target pelanggan baru harus berupa bilangan bulat.")
    key = {"entity_id": entity_id, "sales_id": sales["id"], "period_type": pt, "period": p}
    now = now_iso()
    fields = {"sales_name": sales.get("name") or "",
              "target_sales_amount": _amount(payload.get("target_sales_amount")),
              "target_collection_amount": _amount(payload.get("target_collection_amount")),
              "target_new_customers": new_cust, "notes": str(payload.get("notes") or "").strip()[:500],
              "updated_by": actor.get("name", ""), "updated_at": now}
    for _ in range(3):
        try:
            await db[TARGETS].update_one(key, {"$set": fields, "$setOnInsert": {
                **key, "id": new_id("starg"), "created_by": actor.get("name", ""), "created_at": now}}, upsert=True)
            break
        except DuplicateKeyError:
            continue   # simpan bersamaan dengan kunci yang sama: yang kalah mengulang sebagai pembaruan
    return safe_doc(await db[TARGETS].find_one(key, {"_id": 0}))


async def list_targets(entity_id: str, period_type: str, period: str, sales_id: str = "") -> List[Dict[str, Any]]:
    pt, p = ip.normalize(period_type, period)
    q: Dict[str, Any] = {"entity_id": entity_id, "period_type": pt, "period": p}
    if sales_id:
        q["sales_id"] = sales_id
    rows = await db[TARGETS].find(q, {"_id": 0}).sort([("sales_name", 1), ("sales_id", 1)]).to_list(None)
    return [safe_doc(r) for r in rows]


async def copy_targets(entity_id: str, period_type: str, from_period: str, to_period: str,
                       actor: Dict[str, Any]) -> Dict[str, int]:
    """Salin target periode `from` ke `to` (jenis periode sama) yang belum ada di periode tujuan."""
    from pymongo.errors import DuplicateKeyError
    try:
        pt, src = ip.normalize(period_type, from_period)
        _pt, dst = ip.normalize(period_type, to_period)
    except ip.PeriodeError as exc:
        raise InsentifError(str(exc))
    if src == dst:
        raise InsentifError("Periode asal dan tujuan sama.")
    copied = skipped = 0
    now = now_iso()
    async for t in db[TARGETS].find({"entity_id": entity_id, "period_type": pt, "period": src}, {"_id": 0}):
        key = {"entity_id": entity_id, "sales_id": t["sales_id"], "period_type": pt, "period": dst}
        if await db[TARGETS].find_one(key, {"_id": 0, "id": 1}):
            skipped += 1
            continue
        try:
            await db[TARGETS].insert_one({
                **key, "id": new_id("starg"), "sales_name": t.get("sales_name") or "",
                "target_sales_amount": float(t.get("target_sales_amount") or 0),
                "target_collection_amount": float(t.get("target_collection_amount") or 0),
                "target_new_customers": int(t.get("target_new_customers") or 0), "notes": t.get("notes") or "",
                "copied_from": src, "created_by": actor.get("name", ""), "created_at": now,
                "updated_by": actor.get("name", ""), "updated_at": now})
            copied += 1
        except DuplicateKeyError:
            skipped += 1
    return {"copied": copied, "skipped": skipped}


# ── Komponen insentif ────────────────────────────────────────────────────────────────────────────────────────────────
def _component_fields(payload: Dict[str, Any], *, partial: bool) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not partial or "code" in payload:
        code = str(payload.get("code") or "").strip().upper()
        if not _KODE.match(code):
            raise InsentifError(PESAN_KODE)
        out["code"] = code
    if not partial or "name" in payload:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise InsentifError(PESAN_NAMA)
        out["name"] = name[:120]
    if not partial or "basis_period_type" in payload:
        b = str(payload.get("basis_period_type") or "").strip().lower()
        if b not in COMPONENT_BASIS:
            raise InsentifError(PESAN_DASAR)
        out["basis_period_type"] = b
    if not partial or "columns" in payload:
        cols = [c for c in COMPONENT_COLUMNS if c in set(payload.get("columns") or [])]
        if not cols:
            raise InsentifError(PESAN_KOLOM)
        out["columns"] = cols
    for f, default in (("taxable", True), ("is_active", True)):
        if not partial or f in payload:
            v = payload.get(f)
            out[f] = default if v is None else bool(v)
    return out


async def list_components(entity_id: str) -> List[Dict[str, Any]]:
    rows = await db[COMPONENTS].find({"entity_id": entity_id}, {"_id": 0}).sort("code", 1).to_list(None)
    return [safe_doc(r) for r in rows]


async def create_component(entity_id: str, payload: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    from pymongo.errors import DuplicateKeyError
    f = _component_fields(payload, partial=False)
    if await db[COMPONENTS].find_one({"entity_id": entity_id, "code": f["code"]}, {"_id": 0, "id": 1}):
        raise InsentifError(PESAN_KODE_KEMBAR, 409)
    now = now_iso()
    doc = {"id": new_id("icomp"), "entity_id": entity_id, **f, "created_by": actor.get("name", ""),
           "created_at": now, "updated_by": actor.get("name", ""), "updated_at": now}
    try:
        await db[COMPONENTS].insert_one(dict(doc))
    except DuplicateKeyError:
        raise InsentifError(PESAN_KODE_KEMBAR, 409)
    return doc


async def update_component(doc: Dict[str, Any], payload: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    from pymongo.errors import DuplicateKeyError
    f = _component_fields(payload, partial=True)
    if f.get("code") and f["code"] != doc.get("code") and await db[COMPONENTS].find_one(
            {"entity_id": doc["entity_id"], "code": f["code"]}, {"_id": 0, "id": 1}):
        raise InsentifError(PESAN_KODE_KEMBAR, 409)
    if f:
        try:
            await db[COMPONENTS].update_one({"id": doc["id"]}, {"$set": {
                **f, "updated_by": actor.get("name", ""), "updated_at": now_iso()}})
        except DuplicateKeyError:
            raise InsentifError(PESAN_KODE_KEMBAR, 409)
    return safe_doc(await db[COMPONENTS].find_one({"id": doc["id"]}, {"_id": 0}))


def component_labels(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Label Indonesia komponen untuk layar (tanpa kode mentah)."""
    return {**doc, "basis_label": COMPONENT_BASIS_LABEL.get(doc.get("basis_period_type"), "—"),
            "columns_label": [COMPONENT_COLUMN_LABEL[c] for c in doc.get("columns") or [] if c in COMPONENT_COLUMN_LABEL]}
