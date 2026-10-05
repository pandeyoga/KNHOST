"""W2-REQ-02 — tata kelola master produk: preview legacy → batch migrasi berjejak → rollback per batch.

Aturan: SKU stabil (tidak pernah diubah), koreksi nama tercatat di `name_history`; stage/fabric_type/
line_code/warna internal atribut terpisah; supplier color/lot tidak disentuh; lot internal tidak di-rename.
Standar penamaan perusahaan TIDAK dikarang: duplikasi hanya dibaca dari atribut kanonik.
Preview tidak menulis apa pun; apply hanya menerima usulan dari preview (dicocokkan ulang).
"""
import hashlib
import json
from typing import Any, Dict, List, Tuple

from fastapi import HTTPException

import domain_registry as dr
from db import db
from core_utils import new_id, now_iso, safe_doc

FIELDS = ("stage", "fabric_type", "line_code")
CANON_KEY = ("template_id", "stage", "fabric_type", "line_code", "color_code", "grade", "motif", "gramasi", "lebar")


def _sig(proposals: List[Dict[str, Any]]) -> str:
    raw = json.dumps(sorted((p["product_id"], p["field"], str(p["from"]), str(p["to"])) for p in proposals))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def _lines() -> Dict[str, Dict[str, Any]]:
    return {l["code"]: l for l in await db.product_lines.find({"active": {"$ne": False}}, {"_id": 0}).to_list(100)}


async def preview(scope_filter: Dict[str, Any]) -> Dict[str, Any]:
    lines = await _lines()
    prods = await db.products.find(scope_filter, {"_id": 0, "id": 1, "sku": 1, "name": 1, "status": 1,
                                                  **{k: 1 for k in CANON_KEY}}).to_list(5000)
    templates = {t["id"]: t for t in await db.product_templates.find(
        {}, {"_id": 0, "id": 1, "fabric_type": 1, "stage": 1, "line_code": 1}).to_list(5000)}
    missing, noncanon, proposals, conflicts = [], [], [], []
    for p in prods:
        tpl = templates.get(p.get("template_id") or "") or {}
        for f in FIELDS:
            raw = p.get(f)
            valid = (raw in lines) if f == "line_code" else dr.is_valid("stage" if f == "stage" else "fabric_type", raw)
            if valid:
                continue
            norm = None
            if raw:
                norm = dr.normalize_stage(raw) if f == "stage" else (
                    dr.normalize_fabric_type(raw) if f == "fabric_type" else
                    (str(raw).strip().lower() if str(raw).strip().lower() in lines else None))
            candidates = {c for c in [norm, tpl.get(f) if tpl.get(f) and tpl.get(f) != raw else None] if c}
            if f == "line_code" and not raw:
                ft = p.get("fabric_type") or tpl.get("fabric_type")
                by_ft = [c for c, l in lines.items() if l.get("fabric_type_required") == ft]
                if len(by_ft) == 1 and not tpl.get("line_code"):
                    candidates.add(by_ft[0])
            row = {"product_id": p["id"], "sku": p.get("sku"), "name": p.get("name"), "field": f, "from": raw or ""}
            (noncanon if raw else missing).append(row)
            if len(candidates) == 1:
                to = candidates.pop()
                proposals.append({**row, "to": to, "reason": "normalisasi nilai" if raw else "turunan template/lini"})
            elif len(candidates) > 1:
                conflicts.append({**row, "candidates": sorted(candidates)})
    groups: Dict[Tuple, List[Dict[str, Any]]] = {}
    for p in prods:
        key = tuple(str(p.get(k) or "") for k in CANON_KEY)
        if all(key[1:4]):  # hanya produk dengan atribut kanonik inti terisi
            groups.setdefault(key, []).append({"product_id": p["id"], "sku": p.get("sku"), "name": p.get("name")})
    duplicates = [{"attributes": dict(zip(CANON_KEY, k)), "products": v} for k, v in groups.items() if len(v) > 1]
    return {"generated_at": now_iso(), "product_count": len(prods), "missing": missing, "non_canonical": noncanon,
            "proposals": proposals, "conflicts": conflicts, "duplicate_candidates": duplicates,
            "preview_signature": _sig(proposals),
            "policy": {"sku_stable": True, "naming_standard": "belum ditetapkan pemilik — tidak diusulkan",
                       "customer_color_alias": "ditunda", "supplier_lot_color": "tidak disentuh"}}


async def apply_batch(scope_filter: Dict[str, Any], signature: str, accepted: List[Dict[str, Any]],
                      note: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    pv = await preview(scope_filter)
    if signature != pv["preview_signature"]:
        raise HTTPException(status_code=409, detail="Data berubah sejak preview — muat ulang preview sebelum eksekusi.")
    allowed = {(p["product_id"], p["field"]): p for p in pv["proposals"]}
    picks = [allowed.get((a.get("product_id"), a.get("field"))) for a in accepted]
    if not picks or any(p is None for p in picks):
        raise HTTPException(status_code=422, detail="Hanya usulan dari preview yang boleh dieksekusi.")
    batch_id = new_id("mgb")
    changes = []
    for p in picks:
        res = await db.products.update_one({"id": p["product_id"], p["field"]: p["from"] or {"$in": ["", None]}},
                                           {"$set": {p["field"]: p["to"], "updated_at": now_iso(),
                                                     "last_governance_batch": batch_id}})
        if res.modified_count == 1:
            changes.append({"product_id": p["product_id"], "sku": p["sku"], "field": p["field"],
                            "before": p["from"], "after": p["to"]})
    batch = {"id": batch_id, "status": "applied", "note": (note or "").strip(), "changes": changes,
             "preview_signature": signature, "applied_by": actor.get("name", ""), "applied_at": now_iso()}
    await db.master_governance_batches.insert_one(dict(batch))
    return safe_doc(batch)


async def rollback_batch(batch_id: str, reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    if len((reason or "").strip()) < 5:
        raise HTTPException(status_code=422, detail="Alasan rollback wajib (min. 5 karakter).")
    b = await db.master_governance_batches.find_one_and_update(
        {"id": batch_id, "status": "applied"}, {"$set": {"status": "rolling_back"}})
    if not b:
        raise HTTPException(status_code=409, detail="Batch tidak ditemukan atau sudah di-rollback.")
    restored, skipped = [], []
    for c in b["changes"]:
        res = await db.products.update_one({"id": c["product_id"], c["field"]: c["after"]},
                                           {"$set": {c["field"]: c["before"], "updated_at": now_iso()}})
        (restored if res.modified_count == 1 else skipped).append(c)
    await db.master_governance_batches.update_one({"id": batch_id}, {"$set": {
        "status": "rolled_back", "rollback_reason": reason.strip(), "rolled_back_by": actor.get("name", ""),
        "rolled_back_at": now_iso(), "rollback_restored": len(restored), "rollback_skipped": skipped}})
    return safe_doc(await db.master_governance_batches.find_one({"id": batch_id}, {"_id": 0}))


async def rename_product(product_id: str, new_name: str, reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Koreksi nama tanpa SKU baru; histori nama tercatat."""
    new_name, reason = (new_name or "").strip(), (reason or "").strip()
    if not new_name or len(reason) < 5:
        raise HTTPException(status_code=422, detail="Nama baru dan alasan (min. 5 karakter) wajib.")
    p = await db.products.find_one({"id": product_id}, {"_id": 0, "name": 1, "sku": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    await db.products.update_one({"id": product_id}, {"$set": {"name": new_name, "updated_at": now_iso()},
                                                      "$push": {"name_history": {
                                                          "from": p.get("name"), "to": new_name, "reason": reason,
                                                          "by": actor.get("name", ""), "at": now_iso()}}})
    return safe_doc(await db.products.find_one({"id": product_id}, {"_id": 0}))


async def list_batches() -> List[Dict[str, Any]]:
    return [safe_doc(d) for d in await db.master_governance_batches.find({}, {"_id": 0}).sort("applied_at", -1).to_list(200)]
