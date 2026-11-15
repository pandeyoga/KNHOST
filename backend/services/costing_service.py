"""Costing service (EPIC3A) — Weighted Average Cost (WAC) per produk/entitas.

SSOT cost = `inventory_rolls.unit_cost` (sudah termasuk landed cost via
landed_cost_service; lihat `base_unit_cost` + Σ landed). WAC = rata-rata
tertimbang cost-per-unit dengan bobot `length_remaining` (stok hidup).

Prioritas sumber cost (margin-aware EPIC4):
  1. Roll cost (unit_cost / base_unit_cost) tertimbang length_remaining.
  2. Fallback `products.harga_pokok` (HPP manual) bila tak ada roll bercost.
  3. 0 (ditandai source="none") → line tanpa cost (EPIC4 boleh skip margin cap).
"""
from typing import Any, Dict, List, Optional
import time

from fastapi import HTTPException

from db import db

# Status roll yang dihitung sebagai "stok hidup" untuk WAC.
from services.roll_service import PHYSICAL_ROLL_STATUSES as _PHYS  # KN-C05
LIVE_ROLL_STATUSES = set(_PHYS)

# P2-4 — cache WAC ber-TTL pendek. WAC bergantung pada inventory_rolls (berubah
# saat GR/fulfillment), BUKAN pada pembayaran AR → aman di-cache singkat untuk
# memangkas recompute berulang (admin_home N×komisi, sales_home 6×history).
_WAC_TTL = 5.0
_WAC_CACHE: Dict[tuple, tuple] = {}  # (product_id, entity_id) -> (expires_at, result)


def invalidate_wac_cache() -> None:
    """Kosongkan cache WAC (panggil setelah perubahan cost/roll bila perlu real-time)."""
    _WAC_CACHE.clear()


def _roll_cost(r: Dict[str, Any]) -> float:
    uc = r.get("unit_cost")
    if uc not in (None, 0, 0.0):
        return float(uc)
    b = r.get("base_unit_cost")
    if b not in (None, 0, 0.0):
        return float(b)
    return 0.0


# FIX-7 — field roll yang dipakai rumus WAC (dulu dokumen roll UTUH dibaca per produk; dasbor memanggilnya untuk
# SETIAP produk → seluruh roll hidup dibaca utuh per buka aplikasi).
_WAC_ROLL_FIELDS = {"_id": 0, "product_id": 1, "length_remaining": 1, "unit": 1, "unit_cost": 1, "base_unit_cost": 1}


def _wac_acc() -> Dict[str, Any]:
    # R5.5 — base_val = Σ(base_unit_cost×len) untuk memisah komponen landed cost
    return {"total_len": 0.0, "total_val": 0.0, "base_val": 0.0, "costed_len": 0.0, "unconvertible": 0}


_CONV: List[Any] = []   # conv_qty diimpor malas sekali (hindari impor siklik saat modul dimuat)


def _wac_add(acc: Dict[str, Any], product: Dict[str, Any], r: Dict[str, Any], eng: Any) -> None:
    """SATU langkah rumus WAC per roll (dipakai `wac_for_product` & `wac_for_products`)."""
    if not _CONV:
        from services.receiving_roll_service import conv_qty
        _CONV.append(conv_qty)
    base_unit = product.get("base_unit") or "meter"
    ln_roll = float(r.get("length_remaining", 0) or 0)
    if ln_roll <= 0:
        return
    try:
        ln = _CONV[0](product, ln_roll, r.get("unit") or base_unit, base_unit, eng)
    except HTTPException:
        acc["unconvertible"] += 1  # tidak dicampur tanpa faktor; ditandai di hasil
        return
    acc["total_len"] += ln
    cost = _roll_cost(r)
    if cost > 0:
        acc["costed_len"] += ln
        acc["total_val"] += cost * ln_roll
        # base_unit_cost = HPP sebelum landed; bila kosong anggap = cost (landed 0).
        b = float(r.get("base_unit_cost") or 0) or cost
        acc["base_val"] += b * ln_roll


async def wac_for_product(
    product_id: str,
    entity_id: Optional[str] = None,
    product: Optional[Dict[str, Any]] = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Hitung WAC 1 produk. entity_id opsional → cost per kepemilikan entitas."""
    cache_key = (product_id, entity_id or "")
    if use_cache:
        hit = _WAC_CACHE.get(cache_key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
    if product is None:
        product = await db.products.find_one({"id": product_id}, {"_id": 0}) or {}
    query: Dict[str, Any] = {"product_id": product_id, "status": {"$in": list(LIVE_ROLL_STATUSES)}}
    if entity_id:
        query["owner_entity_id"] = entity_id
    # FN-03 — panjang dinormalisasi ke BASE UNIT produk (nilai = cost/unit roll × qty unit roll);
    # GN-12 — iterasi kursor penuh (dulu to_list(5000) memotong diam-diam).
    from services.receiving_roll_service import uom_engine
    eng = await uom_engine()
    acc = _wac_acc()
    async for r in db.inventory_rolls.find(query, _WAC_ROLL_FIELDS):
        _wac_add(acc, product, r, eng)
    result = _wac_result(product_id, entity_id, product, acc)
    if use_cache:
        _WAC_CACHE[cache_key] = (time.monotonic() + _WAC_TTL, result)
    return result


async def wac_for_products(products: List[Dict[str, Any]], use_cache: bool = True) -> Dict[str, Dict[str, Any]]:
    """FIX-7 — WAC banyak produk (tanpa entitas) dalam SATU pembacaan roll hidup berproyeksi; rumus per roll = `_wac_add`
    yang sama dengan `wac_for_product`. Produk yang gagal dihitung → tidak ada di hasil (pemanggil memakai cadangan)."""
    out: Dict[str, Dict[str, Any]] = {}
    miss: Dict[str, Dict[str, Any]] = {}
    now = time.monotonic()
    for p in products:
        pid = p.get("id")
        if not pid:
            continue
        hit = _WAC_CACHE.get((pid, "")) if use_cache else None
        if hit and hit[0] > now:
            out[pid] = hit[1]
        else:
            miss[pid] = p
    if not miss:
        return out
    from services.receiving_roll_service import uom_engine
    eng = await uom_engine()
    accs = {pid: _wac_acc() for pid in miss}
    failed: set = set()
    q = {"product_id": {"$in": list(miss)}, "status": {"$in": list(LIVE_ROLL_STATUSES)}}
    async for r in db.inventory_rolls.find(q, _WAC_ROLL_FIELDS):
        pid = r.get("product_id")
        if pid not in accs or pid in failed:
            continue
        try:
            _wac_add(accs[pid], miss[pid], r, eng)
        except Exception:  # noqa: BLE001 — sama dengan pemanggil lama: satu produk gagal tidak menjatuhkan yang lain
            failed.add(pid)
    for pid, acc in accs.items():
        if pid in failed:
            continue
        res = _wac_result(pid, None, miss[pid], acc)
        out[pid] = res
        if use_cache:
            _WAC_CACHE[(pid, "")] = (time.monotonic() + _WAC_TTL, res)
    return out


def _wac_result(product_id: str, entity_id: Optional[str], product: Dict[str, Any], acc: Dict[str, Any]) -> Dict[str, Any]:
    total_len, total_val, base_val = acc["total_len"], acc["total_val"], acc["base_val"]
    costed_len, unconvertible = acc["costed_len"], acc["unconvertible"]
    price = float(product.get("price", 0) or 0)
    hpp_manual = float(product.get("harga_pokok", 0) or 0)

    if costed_len > 0:
        wac = total_val / costed_len
        source = "roll" if costed_len >= total_len - 0.001 else "roll_partial"
    elif hpp_manual > 0:
        wac = hpp_manual
        source = "harga_pokok"
    else:
        wac = 0.0
        source = "none"

    # R5.5 — pisahkan WAC menjadi base + landed cost (basis valuasi retur/regrade/write-off).
    if costed_len > 0:
        wac_base = round(base_val / costed_len, 2)
        wac_landed = round(max(wac - wac_base, 0.0), 2)
    else:
        wac_base = round(wac, 2)
        wac_landed = 0.0
    landed_included = wac_landed > 0.005

    margin_amount = round(price - wac, 2) if wac > 0 else None
    margin_pct = round((margin_amount / price) * 100, 2) if (wac > 0 and price > 0) else None

    result = {
        "product_id": product_id,
        "sku": product.get("sku", ""),
        "name": product.get("name", ""),
        "category": product.get("category", ""),
        "base_unit": product.get("base_unit", "meter"),
        "entity_id": entity_id,
        "unconvertible_rolls": unconvertible,
        "wac": round(wac, 2),
        "wac_base": wac_base,          # R5.5 — HPP dasar (sebelum landed cost)
        "wac_landed": wac_landed,      # R5.5 — komponen landed cost (freight/duty/handling)
        "landed_included": landed_included,  # R5.5 — true bila WAC mengandung landed cost
        "source": source,
        "qty_on_hand": round(total_len, 2),
        "qty_costed": round(costed_len, 2),
        "price": round(price, 2),
        "margin_amount": margin_amount,
        "margin_pct": margin_pct,
    }
    return result


async def wac_all(entity_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """WAC seluruh produk aktif (untuk tabel margin / laporan)."""
    products = await db.products.find({"status": "active"}, {"_id": 0}).to_list(2000)
    out = []
    for p in products:
        out.append(await wac_for_product(p["id"], entity_id=entity_id, product=p))
    out.sort(key=lambda x: x["name"])
    return out
