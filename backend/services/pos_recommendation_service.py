"""
F-4b — POS advanced recommendations, dihitung dari histori `sales_orders` (TANPA AI, TANPA koleksi baru).
- best_sellers: produk terlaris (frekuensi order > volume > revenue).
- frequently_bought_together: produk yang sering muncul di order yang sama (market-basket).
- substitutes: alternatif in-stock saat produk habis (kategori sama, prioritas grade sama).
UAT 24 Okt (P12) — sorotan POS bisa dinyalakan/dimatikan per PT (`pos.*`); terlaris memakai JENDELA WAKTU dan hanya
menampilkan produk yang boleh dipesan pelanggan aktif; produk UNGGULAN (diatur MD/Manajer di master produk) dan
REKOMENDASI per pelanggan (keputusan pemilik P12-K1 b: desain/kategori yang pernah dibeli).
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from db import db
from services.customer_service import DEAD_STATUSES

HIGHLIGHT_KEYS = {"best_sellers": "pos.best_sellers.enabled", "reorder": "pos.reorder.enabled", "fbt": "pos.fbt.enabled",
                  "featured": "pos.featured.enabled", "recommendation": "pos.recommendation.enabled"}


async def highlights_config(entity_id: str) -> Dict[str, Any]:
    from services.config_resolver import value_of
    ctx = {"entity_id": entity_id or ""}
    out: Dict[str, Any] = {k: {"enabled": bool(await value_of(key, ctx))} for k, key in HIGHLIGHT_KEYS.items()}
    out["best_sellers"]["window_days"] = int(await value_of("pos.best_sellers.window_days", ctx) or 90)
    return out


async def _live_orders(scope_ids: List[str], window_days: int = 0, customer_id: str = "") -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"entity_id": {"$in": list(scope_ids)}}  # GN-10 — scope wajib, tanpa fallback global
    if window_days and window_days > 0:
        q["created_at"] = {"$gte": (datetime.now(timezone.utc) - timedelta(days=int(window_days))).isoformat()}
    if customer_id:
        q["customer_id"] = customer_id
    orders = await db.sales_orders.find(q, {"_id": 0, "items": 1, "status": 1, "id": 1}).to_list(8000)
    return [o for o in orders if o.get("status") not in DEAD_STATUSES]


def visible_for(p: Optional[Dict[str, Any]], customer_id: str = "") -> bool:
    """Boleh DITAWARKAN di POS: aktif, sudah boleh dipesan (lifecycle), dan bukan SKU eksklusif pelanggan lain
    (pembeli lama desain customer label tetap boleh — P1-K1). Tanpa pelanggan aktif, SKU eksklusif tidak ditawarkan."""
    from services import rnd_gate
    if not p or not rnd_gate.is_orderable(p):
        return False
    owner = p.get("exclusive_customer_id") or ""
    if not owner:
        return True
    return bool(customer_id) and (owner == customer_id or customer_id in (p.get("exclusive_allow_customer_ids") or []))


async def _products(ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    ids = [i for i in dict.fromkeys(ids) if i]
    if not ids:
        return {}
    return {p["id"]: p async for p in db.products.find({"id": {"$in": ids}}, {"_id": 0})}


async def _available_many(ids: List[str]) -> Dict[str, float]:
    """Stok global (minus cadangan makloon) untuk banyak produk sekaligus — dulu satu query per produk (N+1)."""
    from services.sales_stock_service import _sum_by_product
    if not ids:
        return {}
    bal = await _sum_by_product("inventory_balances", {"product_id": {"$in": ids}}, ["available_qty"])
    mk = await _sum_by_product("material_reservations", {"status": "active", "product_id": {"$in": ids}}, ["qty"])
    return {pid: round(max(float((bal.get(pid) or {}).get("available_qty") or 0)
                           - float((mk.get(pid) or {}).get("qty") or 0), 0.0), 2) for pid in ids}


def _row(p: Dict[str, Any], avail: float, extra: Dict[str, Any]) -> Dict[str, Any]:
    return {"product_id": p["id"], "sku": p.get("sku"), "product_name": p.get("name"), "category": p.get("category"),
            "color": p.get("color"), "grade": p.get("grade"), "image": p.get("image"),
            "price": float(p.get("price", 0) or 0), "base_unit": p.get("base_unit"),
            "available_qty": round(float(avail or 0), 2), **extra}


async def _available_in_scope(pid: str, scope_ids: List[str]) -> float:
    # 2026-10 — stok sales = GLOBAL lintas entitas (minus cadangan makloon), sama dengan katalog kasir.
    from services.sales_stock_service import global_available
    return await global_available(pid)


async def _enrich(pid: str, extra: Dict[str, Any], scope_ids: List[str]) -> Optional[Dict[str, Any]]:
    p = await db.products.find_one({"id": pid}, {"_id": 0})
    if not p:
        return None
    summ = {"available_qty": await _available_in_scope(pid, scope_ids)}
    return {
        "product_id": pid,
        "sku": p.get("sku"),
        "product_name": p.get("name"),
        "category": p.get("category"),
        "color": p.get("color"),
        "grade": p.get("grade"),
        "image": p.get("image"),
        "price": float(p.get("price", 0) or 0),
        "base_unit": p.get("base_unit"),
        "available_qty": round(float(summ.get("available_qty", 0) or 0), 2),
        **extra,
    }


async def best_sellers(scope_ids: List[str], limit: int = 8, *, window_days: int = 0,
                       customer_id: str = "") -> List[Dict[str, Any]]:
    orders = await _live_orders(scope_ids, window_days)
    agg: Dict[str, Dict[str, float]] = {}
    for o in orders:
        counted = set()
        for it in (o.get("items") or []):
            pid = it.get("product_id")
            if not pid:
                continue
            a = agg.setdefault(pid, {"order_count": 0.0, "qty": 0.0, "revenue": 0.0})
            a["qty"] += float(it.get("base_quantity") or it.get("quantity") or 0)
            a["revenue"] += float(it.get("line_total") or it.get("subtotal") or 0)
            if pid not in counted:
                a["order_count"] += 1
                counted.add(pid)
    ranked = sorted(agg.items(), key=lambda kv: (kv[1]["order_count"], kv[1]["qty"], kv[1]["revenue"]), reverse=True)
    prods = await _products(pid for pid, _ in ranked[: max(limit * 6, 60)])
    # SKU hasil Pesanan Khusus bukan barang katalog — tidak ikut "Terlaris" (audit UI 143).
    picked = [(pid, a) for pid, a in ranked if visible_for(prods.get(pid), customer_id)
              and not (prods.get(pid) or {}).get("special_order_id")][:limit]
    avail = await _available_many([pid for pid, _ in picked])
    return [_row(prods[pid], avail.get(pid, 0), {"order_count": int(a["order_count"]), "qty_sold": round(a["qty"], 2),
                                               "revenue": round(a["revenue"], 2), "window_days": window_days})
            for pid, a in picked]


async def featured(customer_id: str = "", limit: int = 12) -> List[Dict[str, Any]]:
    """Produk Unggulan/Push: `is_featured` diatur MD/Manajer di master produk, tampil sampai `featured_until`."""
    today = datetime.now(timezone.utc).date().isoformat()
    rows = await db.products.find({"is_featured": True, "status": {"$ne": "inactive"},
                                   "$or": [{"featured_until": {"$in": [None, ""]}}, {"featured_until": {"$gte": today}}]},
                                  {"_id": 0}).sort([("featured_rank", 1), ("name", 1)]).to_list(200)
    rows = [p for p in rows if visible_for(p, customer_id)][:limit]
    avail = await _available_many([p["id"] for p in rows])
    return [_row(p, avail.get(p["id"], 0), {"featured_rank": p.get("featured_rank"), "featured_until": p.get("featured_until") or "",
                                            "featured_note": p.get("featured_note") or ""}) for p in rows]


REC_WEIGHT = {"design_code": 4, "design_category_code": 3, "pattern_category_code": 2, "category": 1}
REC_LABEL = {"design_code": "desain sama", "design_category_code": "kategori desain sama", "pattern_category_code": "pattern sama",
             "category": "kategori sama"}


async def recommended_for_customer(customer_id: str, scope_ids: List[str], limit: int = 10) -> List[Dict[str, Any]]:
    """P12-K1 (b) — rekomendasi per pelanggan: produk BERSTOK yang berbagi kode/kategori desain, pattern, atau kategori
    dengan barang yang pernah dibeli pelanggan itu, belum pernah ia beli, dan boleh ia pesan."""
    if not customer_id:
        return []
    orders = await _live_orders(scope_ids, customer_id=customer_id)
    bought = {it.get("product_id") for o in orders for it in o.get("items") or [] if it.get("product_id")}
    if not bought:
        return []
    hist = await _products(bought)
    keys = {f: {p.get(f) for p in hist.values() if p.get(f)} for f in REC_WEIGHT}
    ors = [{f: {"$in": list(v)}} for f, v in keys.items() if v]
    if not ors:
        return []
    cands = [p for p in await db.products.find({"$or": ors, "id": {"$nin": list(bought)}, "status": {"$ne": "inactive"},
                                                "special_order_id": {"$in": [None, ""]}},
                                               {"_id": 0}).to_list(600) if visible_for(p, customer_id)]
    avail = await _available_many([p["id"] for p in cands])
    scored = []
    for p in cands:
        hits = [f for f in REC_WEIGHT if p.get(f) and p.get(f) in keys[f]]
        if hits and avail.get(p["id"], 0) > 0:
            scored.append((sum(REC_WEIGHT[f] for f in hits), avail[p["id"]], p, REC_LABEL[max(hits, key=REC_WEIGHT.get)]))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [_row(p, a, {"reason": why}) for _, a, p, why in scored[:limit]]


async def frequently_bought_together(product_id: str, scope_ids: List[str], limit: int = 6) -> List[Dict[str, Any]]:
    orders = await _live_orders(scope_ids)
    co: Dict[str, int] = {}
    for o in orders:
        pids = [it.get("product_id") for it in (o.get("items") or []) if it.get("product_id")]
        if product_id not in pids:
            continue
        for pid in set(p for p in pids if p != product_id):
            co[pid] = co.get(pid, 0) + 1
    ranked = sorted(co.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    out: List[Dict[str, Any]] = []
    for pid, cnt in ranked:
        row = await _enrich(pid, {"together_count": cnt}, scope_ids)
        if row:
            out.append(row)
    return out


async def substitutes(product_id: str, scope_ids: List[str], limit: int = 6) -> List[Dict[str, Any]]:
    """Alternatif in-stock saat produk OOS. Tiered: kategori sama > grade sama > populer.
    Selalu hanya mengembalikan produk yang masih ADA stok (available_qty > 0)."""
    base = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not base:
        return []
    cands = await db.products.find(
        {"id": {"$ne": product_id}, "status": {"$ne": "inactive"}}, {"_id": 0}
    ).to_list(300)
    scored = []
    for p in cands:
        avail = await _available_in_scope(p["id"], scope_ids)
        if avail <= 0:
            continue
        same_cat = p.get("category") == base.get("category")
        same_grade = p.get("grade") == base.get("grade")
        reason = "kategori" if same_cat else ("grade" if same_grade else "populer")
        score = (2 if same_cat else 0) + (1 if same_grade else 0)
        scored.append((score, avail, same_cat, same_grade, reason, p))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    out: List[Dict[str, Any]] = []
    for score, avail, same_cat, same_grade, reason, p in scored[:limit]:
        row = await _enrich(p["id"], {"same_category": same_cat, "same_grade": same_grade, "match_reason": reason}, scope_ids)
        if row:
            out.append(row)
    return out
