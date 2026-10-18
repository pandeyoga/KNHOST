"""L01 LN-012 — MASTER GRADE (`md_grades`): tambah, ubah, aktif/nonaktif tanpa ubah kode.

- Grade aktif awal A, A1, B, BS (keputusan owner 2026-10-16); A2, B1, C disimpan
  sebagai HISTORIS (nonaktif) — tidak dihapus/dipetakan diam-diam, transaksi lama tetap terbaca.
- Tidak ada hapus fisik. Nonaktif = tidak bisa dipakai input baru (semua form & API grade).
- Urutan mutu memakai `rank` (1 = terbaik) dan unik.
- Registry sinkron `domain_registry.GRADES` diisi ulang sesudah setiap perubahan dan berkala.
"""
import re
from typing import Any, Dict, List

from fastapi import HTTPException

import domain_registry as dr
from core_utils import now_iso
from db import db

COLL = "md_grades"
OWNER_ACTIVE = {"A", "A1", "B", "BS"}
CODE_RX = re.compile(r"^[A-Z0-9]{1,2}$")


async def seed() -> None:
    if await db[COLL].count_documents({}):
        return
    rows = []
    for g in dr.GRADES:
        code = g["value"]
        rows.append({"code": code, "name": g.get("label") or code, "rank": int(g["rank"]),
                     "description": g.get("description", ""), "active": code in OWNER_ACTIVE,
                     "historical": code not in OWNER_ACTIVE, "max_points": None,
                     "created_at": now_iso(), "updated_at": now_iso(), "created_by": "Migrasi L01",
                     "history": [{"at": now_iso(), "by": "Migrasi L01",
                                  "change": "seed dari domain_registry; aktif=" + str(code in OWNER_ACTIVE)}]})
    await db[COLL].insert_many(rows)
    await db[COLL].create_index("code", unique=True)
    await db[COLL].create_index("rank", unique=True)


async def load() -> List[Dict[str, Any]]:
    rows = await db[COLL].find({}, {"_id": 0, "history": 0}).sort("rank", 1).to_list(200)
    dr.set_grades(rows)
    return rows


async def refresh_forever(interval: float = 30.0) -> None:
    """Multi-worker: perubahan master dari worker lain terbaca ≤ `interval` detik."""
    import asyncio
    import logging
    while True:
        await asyncio.sleep(interval)
        try:
            await load()
            from services import fabric_type_master_service as _fts
            await _fts.load()
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).warning("refresh grade gagal: %s", exc)


async def list_all() -> List[Dict[str, Any]]:
    rows = await db[COLL].find({}, {"_id": 0}).sort("rank", 1).to_list(200)
    usage = {r["_id"]: r["n"] async for r in db.inventory_rolls.aggregate(
        [{"$group": {"_id": "$grade", "n": {"$sum": 1}}}])}
    for r in rows:
        r["rolls_using"] = int(usage.get(r["code"], 0))
    return rows


def _clean(body: Dict[str, Any], creating: bool) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if creating:
        code = str(body.get("code") or "").strip().upper()
        if not CODE_RX.match(code):
            raise HTTPException(status_code=422, detail="Kode grade 1–2 huruf/angka (dipakai di kode SKU), mis. A3.")
        out["code"] = code
    if creating or "name" in body:
        name = str(body.get("name") or "").strip()
        if len(name) < 1 or len(name) > 60:
            raise HTTPException(status_code=422, detail="Nama grade wajib (maks. 60 karakter).")
        out["name"] = name
    if creating or "rank" in body:
        try:
            rank = int(body.get("rank"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Urutan mutu (rank) wajib angka; 1 = terbaik.")
        if rank < 1 or rank > 99:
            raise HTTPException(status_code=422, detail="Rank 1–99 (1 = terbaik).")
        out["rank"] = rank
    if "description" in body:
        out["description"] = str(body.get("description") or "").strip()[:200]
    if "max_points" in body:
        mp = body.get("max_points")
        if mp in (None, ""):
            out["max_points"] = None
        else:
            try:
                out["max_points"] = float(mp)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail="Batas poin 4-point harus angka atau kosong.")
    return out


async def _assert_rank_free(rank: int, exclude: str = "") -> None:
    other = await db[COLL].find_one({"rank": rank, "code": {"$ne": exclude}}, {"_id": 0, "code": 1})
    if other:
        raise HTTPException(status_code=409, detail=f"Rank {rank} sudah dipakai grade {other['code']}. Pilih urutan lain.")


async def create(body: Dict[str, Any], actor: str) -> Dict[str, Any]:
    row = _clean(body, True)
    if await db[COLL].find_one({"code": row["code"]}):
        raise HTTPException(status_code=409, detail=f"Grade {row['code']} sudah ada — aktifkan/ubah yang lama.")
    await _assert_rank_free(row["rank"])
    row.update({"active": body.get("active") is not False, "historical": False,
                "description": row.get("description", ""), "max_points": row.get("max_points"),
                "created_at": now_iso(), "updated_at": now_iso(), "created_by": actor,
                "history": [{"at": now_iso(), "by": actor, "change": "dibuat"}]})
    try:
        await db[COLL].insert_one(dict(row))
    except Exception as exc:  # noqa: BLE001 — unique index (balapan dua admin)
        raise HTTPException(status_code=409, detail="Kode atau rank grade bentrok dengan perubahan lain.") from exc
    await load()
    row.pop("_id", None)
    return row


async def update(code: str, body: Dict[str, Any], actor: str) -> Dict[str, Any]:
    code = code.upper()
    cur = await db[COLL].find_one({"code": code}, {"_id": 0})
    if not cur:
        raise HTTPException(status_code=404, detail="Grade tidak ditemukan.")
    patch = _clean(body, False)
    if "rank" in patch and patch["rank"] != cur["rank"]:
        await _assert_rank_free(patch["rank"], exclude=code)
    if not patch:
        raise HTTPException(status_code=422, detail="Tidak ada perubahan.")
    patch["updated_at"] = now_iso()
    change = {k: [cur.get(k), v] for k, v in patch.items() if k != "updated_at" and cur.get(k) != v}
    try:
        await db[COLL].update_one({"code": code}, {"$set": patch, "$push": {"history": {
            "at": now_iso(), "by": actor, "change": change}}})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=409, detail="Rank bentrok dengan perubahan lain.") from exc
    await load()
    return await db[COLL].find_one({"code": code}, {"_id": 0})


async def set_active(code: str, active: bool, reason: str, actor: str) -> Dict[str, Any]:
    code = code.upper()
    cur = await db[COLL].find_one({"code": code}, {"_id": 0})
    if not cur:
        raise HTTPException(status_code=404, detail="Grade tidak ditemukan.")
    if len((reason or "").strip()) < 5:
        raise HTTPException(status_code=400, detail="Alasan aktif/nonaktif wajib (min. 5 karakter).")
    if not active:
        n_active = await db[COLL].count_documents({"active": {"$ne": False}, "code": {"$ne": code}})
        if n_active < 1:
            raise HTTPException(status_code=409, detail="Minimal satu grade harus tetap aktif.")
        used = await db.customer_grade_rules.count_documents({"min_grade": code})
        if used:
            raise HTTPException(status_code=409, detail=f"Grade {code} dipakai sebagai minimum {used} pelanggan — "
                                                        "ubah aturan pelanggan dulu.")
    res = await db[COLL].update_one({"code": code, "active": {"$ne": active} if active else {"$ne": False}},
                                    {"$set": {"active": active, "updated_at": now_iso()},
                                     "$push": {"history": {"at": now_iso(), "by": actor,
                                                           "change": {"active": [not active, active]},
                                                           "reason": reason.strip()}}})
    if not res.modified_count:
        raise HTTPException(status_code=409, detail=f"Grade {code} sudah {'aktif' if active else 'nonaktif'}.")
    await load()
    return await db[COLL].find_one({"code": code}, {"_id": 0})
