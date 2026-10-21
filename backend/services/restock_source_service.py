"""P05 IMP-19 — sumber restock per ARTIKEL (product_templates) dan penegakan jalur PR/PO/MKO.

Keputusan pemilik 2026-10-11 (DEC-07):
  * Artikel lama TIDAK di-default; tanpa mapping = "belum diatur", MD mengisi manual.
  * Artikel "both" (supplier atau makloon): jalur dipilih SETIAP KALI dengan alasan.
  * L01 LN-013 (owner 2026-10-16): supplier/makloon = DEFAULT. Jalur lain boleh dengan alasan
    (tercatat `deviation`), tidak lagi hard block.
  * Unknown: kebijakan `purchasing.restock_source_unknown` (warn | block).
Hanya berlaku untuk barang jadi (stage finished); bahan baku (benang/grey/PFD) tidak dibatasi.
"""
from typing import Any, Dict, Iterable, List, Optional, Tuple

from db import db
from core_utils import now_iso

MODES = {"supplier": "Supplier (beli jadi)", "makloon": "Makloon (produksi)", "both": "Supplier atau makloon"}
ROUTE_LABEL = {"purchase": "pembelian supplier", "makloon": "makloon"}


class RestockRouteError(ValueError):
    pass


def applies(product: Dict[str, Any]) -> bool:
    return (product.get("stage") or "finished") == "finished"


async def unknown_policy(entity_id: str) -> str:
    from services import config_resolver
    try:
        v = await config_resolver.value_of("purchasing.restock_source_unknown", {"entity_id": entity_id})
    except Exception:  # noqa: BLE001
        v = None
    return v if v in ("warn", "block") else "warn"


async def _templates(ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    ids = [i for i in set(ids) if i]
    return {t["id"]: t async for t in db.product_templates.find(
        {"id": {"$in": ids}}, {"_id": 0, "id": 1, "name": 1, "restock_source": 1})}


async def check_lines(lines: List[Tuple[Dict[str, Any], str]], *, reason: str, entity_id: str,
                      where: str) -> Dict[str, Any]:
    """lines = [(product, route)] route ∈ purchase|makloon. Raise RestockRouteError bila jalur tidak sah."""
    lines = [(p, r) for p, r in lines if p and applies(p)]
    tpls = await _templates(p.get("template_id") for p, _ in lines)
    policy = await unknown_policy(entity_id)
    reason = (reason or "").strip()
    out: List[Dict[str, Any]] = []
    warnings: List[str] = []
    for p, route in lines:
        tpl = tpls.get(p.get("template_id") or "") or {}
        art = tpl.get("name") or p.get("sku") or p.get("name") or p.get("id")
        mode = (tpl.get("restock_source") or {}).get("mode") or ""
        row = {"product_id": p.get("id"), "template_id": tpl.get("id", ""), "article": art,
               "mode": mode or "unmapped", "route": route, "reason": ""}
        if not mode and not p.get("template_id"):
            # Cek UI UAT v3 (S16) — produk lama tanpa template artikel tidak bisa dipetakan di layar mana pun
            # (Sumber Restock diatur per template) → dulu PR diblok selamanya. Cukup diberi peringatan.
            row["mode"] = "no_template"
            warnings.append(f"{where}: produk {art} belum tertaut artikel (template) — sumber restock tidak bisa "
                            "diatur; jalur dicatat apa adanya.")
        elif not mode:
            msg = (f"{where}: sumber restock artikel {art} belum diatur — minta MD mengisi di "
                   "Master Produk › Sumber Restock.")
            if policy == "block":
                raise RestockRouteError(msg)
            warnings.append(msg)
        elif (mode == "supplier" and route == "makloon") or (mode == "makloon" and route == "purchase"):
            # L01 LN-013 (keputusan owner 2026-10-16) — sumber restock = DEFAULT/rekomendasi, bukan
            # larangan. Menyimpang dari default boleh, asal alasan ditulis dan tercatat di dokumen.
            default = ROUTE_LABEL["purchase" if mode == "supplier" else "makloon"]
            if not reason:
                raise RestockRouteError(f"{where}: default artikel {art} adalah {default} — tulis alasan "
                                        f"memilih jalur {ROUTE_LABEL.get(route, route)}.")
            row.update({"reason": reason, "deviation": True, "default_route": default})
            warnings.append(f"{where}: artikel {art} memakai jalur {ROUTE_LABEL.get(route, route)} "
                            f"(menyimpang dari default {default}) — alasan: {reason}")
        elif mode == "both":
            if not reason:
                raise RestockRouteError(f"{where}: artikel {art} bisa dari supplier atau makloon — "
                                        f"tulis alasan memilih jalur {ROUTE_LABEL.get(route, route)}.")
            row["reason"] = reason
        out.append(row)
    return {"routes": out, "warnings": warnings, "policy": policy, "checked_at": now_iso()}


async def auto_route(product: Dict[str, Any]) -> str:
    """Jalur otomatis untuk reorder dari SO: makloon-only → makloon; selain itu purchase."""
    if not applies(product):
        return "purchase"
    tpl = (await _templates([product.get("template_id") or ""])).get(product.get("template_id") or "") or {}
    return "makloon" if (tpl.get("restock_source") or {}).get("mode") == "makloon" else "purchase"


async def save(template_id: str, body: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    tpl = await db.product_templates.find_one({"id": template_id}, {"_id": 0, "id": 1, "restock_source": 1})
    if not tpl:
        raise LookupError("Artikel tidak ditemukan")
    mode = (body.get("mode") or "").strip()
    if mode not in MODES:
        raise RestockRouteError("Pilih sumber restock: supplier, makloon, atau keduanya.")
    rec = {"mode": mode, "note": (body.get("note") or "").strip()[:300],
           "lead_time_days": int(body["lead_time_days"]) if str(body.get("lead_time_days") or "").isdigit() else None,
           "updated_by": actor.get("name", ""), "updated_at": now_iso()}
    hist = {"at": rec["updated_at"], "by": rec["updated_by"],
            "before": (tpl.get("restock_source") or {}).get("mode") or "unmapped", "after": mode}
    await db.product_templates.update_one(
        {"id": template_id},
        {"$set": {"restock_source": rec}, "$push": {"restock_source_history": {"$each": [hist], "$slice": -30}}})
    return await get(template_id)


async def get(template_id: str) -> Optional[Dict[str, Any]]:
    return await db.product_templates.find_one(
        {"id": template_id}, {"_id": 0, "id": 1, "name": 1, "sku_prefix": 1, "line_code": 1, "stage": 1,
                              "restock_source": 1, "restock_source_history": 1})


async def list_articles(q: str = "", status: str = "", limit: int = 100) -> Dict[str, Any]:
    base: Dict[str, Any] = {"stage": {"$in": ["finished", None, ""]}}
    if q:
        base["$or"] = [{"name": {"$regex": q, "$options": "i"}}, {"sku_prefix": {"$regex": q, "$options": "i"}}]
    unmapped = {"$or": [{"restock_source.mode": {"$exists": False}}, {"restock_source.mode": None}]}
    flt = {"$and": [base, unmapped]} if status == "unmapped" else (
        {**base, "restock_source.mode": {"$in": list(MODES)}} if status == "mapped" else base)
    rows = await db.product_templates.find(flt, {"_id": 0, "id": 1, "name": 1, "sku_prefix": 1, "line_code": 1,
                                                 "restock_source": 1}).sort("name", 1).to_list(limit)
    total = await db.product_templates.count_documents(base)
    n_unmapped = await db.product_templates.count_documents({"$and": [base, unmapped]})
    return {"items": rows, "total": total, "unmapped": n_unmapped, "mapped": total - n_unmapped,
            "modes": [{"value": k, "label": v} for k, v in MODES.items()]}
