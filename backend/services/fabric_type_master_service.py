"""L01 — MASTER JENIS KAIN (`md_fabric_types`): woven/knit benih + tambahan admin (mis. dari laporan
impor dataset client). Isi `domain_registry.FABRIC_TYPES` in-place supaya validasi & semua pemilih ikut."""
import re
from typing import Any, Dict, List

from fastapi import HTTPException

import domain_registry as dr
from core_utils import now_iso
from db import db

COLL = "md_fabric_types"
UOMS = ("meter", "yard", "kg")


async def seed() -> None:
    if await db[COLL].count_documents({}):
        return
    await db[COLL].insert_many([{"code": f["value"], "name": f["label"], "control_uom": f.get("control_uom") or "meter",
                                 "description": f.get("description", ""), "active": True, "created_at": now_iso(),
                                 "created_by": "seed"} for f in dr.FABRIC_TYPES])


async def load() -> List[Dict[str, Any]]:
    rows = await db[COLL].find({}, {"_id": 0}).sort("created_at", 1).to_list(200)
    if rows:
        dr.FABRIC_TYPES[:] = [{"value": r["code"], "label": r["name"], "control_uom": r.get("control_uom") or "meter",
                               "description": r.get("description", ""), "active": r.get("active") is not False}
                              for r in rows]
    return rows


async def list_all() -> List[Dict[str, Any]]:
    return await db[COLL].find({}, {"_id": 0}).sort("created_at", 1).to_list(200)


async def create(body: Dict[str, Any], actor: str) -> Dict[str, Any]:
    code = re.sub(r"[^a-z0-9_]", "_", (body.get("code") or "").strip().lower()).strip("_")
    name = (body.get("name") or "").strip()
    uom = (body.get("control_uom") or "").strip().lower()
    if not code or len(code) > 30 or not name:
        raise HTTPException(status_code=400, detail="Kode (huruf kecil/angka) dan nama jenis kain wajib.")
    if uom not in UOMS:
        raise HTTPException(status_code=400, detail="Satuan kendali wajib: meter, yard, atau kg.")
    row = {"code": code, "name": name, "control_uom": uom, "description": (body.get("description") or "").strip()[:200],
           "active": True, "created_at": now_iso(), "created_by": actor}
    res = await db[COLL].update_one({"code": code}, {"$setOnInsert": row}, upsert=True)
    if not res.upserted_id:
        raise HTTPException(status_code=409, detail=f"Jenis kain '{code}' sudah ada.")
    await load()
    return await db[COLL].find_one({"code": code}, {"_id": 0})
