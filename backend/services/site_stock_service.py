"""UAT 24 Okt (P8, fase F1) — stok per LOKASI untuk katalog POS / HP.

Dulu katalog sengaja "TOTAL GLOBAL" (`ProductQuickView`: "Inventory POS = TOTAL GLOBAL saja"), sehingga sales di
Jakarta melihat stok Rancamalang seolah siap di depannya. Pemilik: pengguna memilih lokasi dulu, katalog menonjolkan
stok DI LOKASI ITU, roll dipilih lokasi dulu lalu FIFO.

Per produk untuk gudang yang DIHITUNG di lokasi itu (aktif, bukan data uji):
* `own_qty`   — Tersedia milik PT penjual (bisa langsung dijual),
* `group_qty` — Tersedia milik PT lain grup di lokasi yang sama (perlu transfer antar-PT; di gudang bersama cukup ganti
                pemilik),
* `rolls`     — jumlah roll tersedia milik PT penjual; `group_rolls` — milik PT lain.
Satuan = satuan dasar produk — tidak pernah dijumlah lintas satuan.

FIX-2 (B3a STK-13/SSOT-4/DUP-4) — angka diambil dari SATU layanan angka stok (`stock_figures.segments`): "Tersedia" =
definisi tunggal K-04 (panjang yang dipesan untuk dipotong, klaim PA, tahan QC/MD Quality, dan cadangan makloon TIDAK
ikut). Dulu: Σ `length_remaining` roll `available` mentah → +2 … +25 yard di "Di {site}".
"""
from typing import Any, Dict, List, Optional

from db import db


async def site_warehouse_ids(site_id: str) -> List[str]:
    from services.stock_figures import warehouse_map
    return [wid for wid, w in (await warehouse_map()).items() if w["counted"] and (w.get("site_id") or "") == site_id]


async def site_stock(site_id: str, entity_id: Optional[str], product_ids: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
    if not site_id:
        return {}
    whs = set(await site_warehouse_ids(site_id))
    if not whs:
        return {}
    from services.stock_figures import segments
    own = entity_id if entity_id and entity_id != "all" else None
    segs = [s for s in await segments(product_ids or None) if s["warehouse_id"] in whs]
    pids = list({s["product_id"] for s in segs})
    units = {p["id"]: p.get("base_unit") or "" async for p in db.products.find(
        {"id": {"$in": pids}}, {"_id": 0, "id": 1, "base_unit": 1})} if pids else {}
    out: Dict[str, Dict[str, Any]] = {}
    for s in segs:
        qty = max(float(s["available_qty"]), 0.0)
        rolls = int(s.get("available_rolls") or 0)
        if qty <= 0.004 and rolls == 0:
            continue
        slot = out.setdefault(s["product_id"], {"own_qty": 0.0, "group_qty": 0.0, "rolls": 0, "group_rolls": 0,
                                                "unit": units.get(s["product_id"], "")})
        if own is None or s["owner_entity_id"] == own:
            slot["own_qty"] = round(slot["own_qty"] + qty, 2)
            slot["rolls"] += rolls
        else:
            slot["group_qty"] = round(slot["group_qty"] + qty, 2)
            slot["group_rolls"] += rolls
    return out
