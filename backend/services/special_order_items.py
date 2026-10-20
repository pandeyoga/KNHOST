"""L03 LN-030 — item Pesanan Khusus: multi-produk, sumber desain per item, redesign."""
from typing import Any, Dict, List

from db import db
from core_utils import new_id, now_iso

SOURCE_TYPES: Dict[str, str] = {
    "parent_product": "Induk produk (custom warna)",
    "approved_artwork": "Motif/artwork ACC (belum produk)",
    "customer_reference": "Referensi / desain pelanggan",
    "redesign": "Redesign dari artwork lama",
}
ORIGINS: Dict[str, str] = {"special_order": "Special Order", "redesign": "Redesign"}
ARTWORK_USABLE = {"approved", "final_submitted", "active"}
ITEM_TYPES = ("printing", "labdip", "handfeel")


class ItemError(ValueError):
    pass


async def assert_artwork_usable(design_id: str, entity_id: str) -> Dict[str, Any]:
    d = await db.design_gallery.find_one({"id": design_id}, {"_id": 0})
    if not d:
        raise ItemError("Artwork tidak ditemukan di Design Studio.")
    if entity_id and d.get("entity_id") and d["entity_id"] != entity_id:
        raise ItemError(f"Artwork {d.get('code') or design_id} milik badan usaha lain.")
    if (d.get("status") or "draft") not in ARTWORK_USABLE:
        raise ItemError(f"Artwork {d.get('code') or design_id} belum ACC — hanya artwork ACC yang bisa dipilih.")
    if d.get("on_hold"):
        h = d.get("hold") or {}
        raise ItemError(f"Artwork {d.get('code') or design_id} sedang HOLD"
                        + (f" ({h.get('reason')})" if h.get("reason") else "")
                        + " — hanya PIC Designer berwenang yang dapat melepasnya.")
    return d


async def _parent_of(item: Dict[str, Any]) -> Dict[str, str]:
    tid, pid = (item.get("source_template_id") or "").strip(), (item.get("source_product_id") or "").strip()
    if pid:
        p = await db.products.find_one({"id": pid}, {"_id": 0, "id": 1, "name": 1, "sku": 1, "template_id": 1})
        if not p:
            raise ItemError("Produk induk tidak ditemukan.")
        return {"source_product_id": p["id"], "source_template_id": p.get("template_id") or tid,
                "source_label": f"{p.get('sku') or ''} {p.get('name') or ''}".strip()}
    if tid:
        t = await db.product_templates.find_one({"id": tid}, {"_id": 0, "id": 1, "name": 1})
        if not t:
            raise ItemError("Induk produk tidak ditemukan.")
        return {"source_product_id": "", "source_template_id": t["id"], "source_label": t.get("name", "")}
    raise ItemError("Item bersumber induk produk wajib memilih induk/produk.")


CLIENT_SOURCES = ("parent_product", "approved_artwork", "customer_reference")


async def build_items(raw: List[Dict[str, Any]], entity_id: str) -> List[Dict[str, Any]]:
    """Validasi & normalisasi item. Tidak membuat produk apa pun (artwork ACC dipakai apa adanya).
    Sumber `redesign` hanya lahir dari POST /special-orders/{id}/redesign."""
    out: List[Dict[str, Any]] = []
    for i, r in enumerate(raw, start=1):
        st = (r.get("source_type") or "").strip()
        if st not in CLIENT_SOURCES:
            raise ItemError(f"Item {i}: sumber harus salah satu dari {', '.join(CLIENT_SOURCES)}. "
                            "Redesign dibuat lewat tombol 'Ubah motif' pada pesanan asal.")
        qty = float(r.get("quantity") or 0)
        if qty <= 0:
            raise ItemError(f"Item {i}: jumlah wajib > 0.")
        types = [t for t in (r.get("request_types") or []) if t in ITEM_TYPES]
        if not types:
            raise ItemError(f"Item {i}: pilih minimal satu jenis uji/permintaan (printing/labdip/handfeel).")
        item: Dict[str, Any] = {
            "id": new_id("soi"), "line_no": i, "source_type": st, "source_type_label": SOURCE_TYPES[st],
            "description": (r.get("description") or "").strip() or f"Item {i}",
            "request_types": types, "quantity": qty, "unit": r.get("unit") or "meter",
            "target_price": float(r.get("target_price") or 0), "color_id": r.get("color_id") or "",
            "notes": (r.get("notes") or "").strip(), "source_product_id": "", "source_template_id": "",
            "source_design_id": "", "source_design_code": "", "source_label": "",
            "design_request_id": "", "sample_ids": [],
        }
        if st == "parent_product":
            item.update(await _parent_of(r))
        elif st == "approved_artwork":
            did = (r.get("source_design_id") or "").strip()
            if not did:
                raise ItemError(f"Item {i}: pilih artwork sumber.")
            d = await assert_artwork_usable(did, entity_id)
            item.update({"source_design_id": d["id"], "source_design_code": d.get("code", ""),
                         "source_label": f"{d.get('code') or ''} {d.get('title') or ''}".strip()})
        item["subtotal"] = round(qty * item["target_price"], 2)
        out.append(item)
    return out


def items_of(od: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(od.get("items") or [])


# FE-01 lanjutan — keputusan owner 2026-10-21: item OD dapat dibatalkan SATU PER SATU. Item batal
# tidak dihapus (jejak & alasannya tetap), tetapi tidak lagi ikut harga, pengadaan, ACC, maupun SO.
ITEM_CANCELLED = "cancelled"


def is_active_item(item: Dict[str, Any]) -> bool:
    return (item or {}).get("status") != ITEM_CANCELLED


def active_items(od: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [i for i in od.get("items") or [] if is_active_item(i)]


async def _design_of_request(req_id: str) -> Dict[str, Any]:
    req = await db.design_requests.find_one({"id": req_id}, {"_id": 0, "design_id": 1, "gallery_ids": 1}) if req_id else None
    ids = ([req.get("design_id")] if (req or {}).get("design_id") else []) + list(reversed((req or {}).get("gallery_ids") or []))
    for gid in ids:
        d = await db.design_gallery.find_one({"id": gid}, {"_id": 0})
        if d:
            return d
    return {}


async def artwork_of(od: Dict[str, Any], item_id: str = "") -> tuple:
    """Item + artwork lamanya (sumber artwork atau hasil permintaan desain) untuk redesign."""
    items = items_of(od)
    if items:
        item = next((i for i in items if i.get("id") == item_id), None) if item_id else (items[0] if len(items) == 1 else None)
        if not item:
            raise ItemError("Pilih item yang motifnya akan diubah.")
    else:
        item = {"id": "", "description": (od.get("custom_item") or {}).get("description", ""),
                **{k: (od.get("custom_item") or {}).get(k) for k in ("quantity", "unit", "target_price")},
                "design_request_id": od.get("design_request_id", "")}
    design: Dict[str, Any] = {}
    if item.get("source_design_id"):
        design = await db.design_gallery.find_one({"id": item["source_design_id"]}, {"_id": 0}) or {}
    if not design:
        design = await _design_of_request(item.get("design_request_id") or "")
    if not design:
        raise ItemError("Item ini belum punya artwork — redesign hanya untuk item yang sudah punya artwork.")
    return item, design


async def item_chain(od: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Rantai per item: permintaan desain + sample yang membawa `special_order_item_id`."""
    samples: Dict[str, List[Dict[str, Any]]] = {}
    async for s in db.md_samples.find({"special_order_id": od["id"]},
                                      {"_id": 0, "id": 1, "number": 1, "status": 1, "sample_types": 1,
                                       "special_order_item_id": 1, "design_id": 1, "created_at": 1}):
        samples.setdefault(s.get("special_order_item_id") or "", []).append(s)
    req_ids = [i.get("design_request_id") for i in items_of(od) if i.get("design_request_id")]
    reqs = {r["id"]: r async for r in db.design_requests.find(
        {"id": {"$in": req_ids}}, {"_id": 0, "id": 1, "number": 1, "status": 1, "design_id": 1, "gallery_ids": 1})}
    out = []
    for i in items_of(od):
        out.append({**i, "design_request": reqs.get(i.get("design_request_id") or ""),
                    "samples": sorted(samples.get(i["id"], []), key=lambda s: s.get("created_at") or ""),
                    "can_redesign": bool(i.get("source_design_id") or (reqs.get(i.get("design_request_id") or "") or {}).get("gallery_ids"))})
    return out


async def set_item_links(od_id: str, item_id: str, design_request_id: str = "", sample_id: str = "") -> None:
    upd: Dict[str, Any] = {"$set": {"updated_at": now_iso()}}
    if design_request_id:
        upd["$set"]["items.$.design_request_id"] = design_request_id
    if sample_id:
        upd["$addToSet"] = {"items.$.sample_ids": sample_id}
    await db.special_orders.update_one({"id": od_id, "items.id": item_id}, upd)
