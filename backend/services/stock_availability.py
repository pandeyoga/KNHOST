"""K-04 (keputusan pemilik 26 Okt 2026) — SATU definisi stok "Tersedia" & "Stok rendah".

Tersedia = panjang roll berstatus `available` yang TIDAK diblokir / karantina / ditahan (hold) / rusak / WIP /
sedang diklaim perpindahan, dikurangi panjang yang sudah dipesan — yaitu bucket `available_qty` saldo
`inventory_balances` yang DIBANGUN ULANG DARI ROLL (`roll_service.rebuild_balance`) — di gudang yang TERDAFTAR di
master, lalu dikurangi cadangan bahan makloon aktif (`material_reservations`). Angka ini sama dengan papan stok
(Inventori › Status Stok: "Stok Fisik = Tersedia + Dipesan + tertahan (karantina/QC/blokir/cadangan makloon)").

Dipakai: papan stok (`fulfillment_service.build_supply_index(registered_only=True)` dari router), Saran Reorder
(`purchase_requisition_service.reorder_suggestions` → juga kartu "Stok Rendah/Perlu reorder" Control Tower),
"Stok rendah" Dasbor Manajer & Operasi Gudang (`low_stock_summary`).

Stok rendah = per PRODUK per badan usaha: 0 < Tersedia < LOW_STOCK_QTY (satuan dasar produk). Tersedia 0 = "habis",
bukan "rendah" (sama dengan penanda baris di Operasi Gudang).
"""
from typing import Any, Dict, Iterable, List, Optional, Set

from db import db
from core_utils import DEFAULT_ENTITY_ID

EPS = 0.001
LOW_STOCK_QTY = 100.0
AVAILABLE_LABEL = ("Tersedia = roll siap jual (tidak diblokir, karantina, atau ditahan) dikurangi yang sudah "
                   "dipesan & cadangan makloon — sama dengan papan stok")
LOW_STOCK_LABEL = f"produk dengan tersedia di atas 0 dan di bawah {int(LOW_STOCK_QTY)} (satuan dasar), per badan usaha"


def is_low_stock(available: float, threshold: float = LOW_STOCK_QTY) -> bool:
    """Satu aturan "Stok rendah": masih ada (> 0) tetapi di bawah ambang. 0 = habis (bukan rendah)."""
    return EPS < float(available or 0) < float(threshold)


async def registered_warehouse_ids() -> Set[str]:
    """FIX-2 (DUP-1) — gudang yang DIHITUNG di angka stok: aktif & bukan data uji (`stock_figures.counted_warehouse_ids`).
    Dulu: semua gudang master (termasuk 5 non-aktif & 6 `TEST_WH`) — berbeda dengan katalog POS (aktif saja)."""
    from services.stock_figures import counted_warehouse_ids
    return await counted_warehouse_ids()


async def deduct_makloon(supply: Dict[str, Dict[str, Any]], product_ids: Optional[List[str]] = None) -> None:
    """W2-REQ-07 — bahan yang dicadangkan untuk makloon bukan stok bebas: kurangi dari `available` entitas lalu dari
    gudang (terbesar dulu). `supply` = {product_id: {entity_id: {"available", "warehouses": {wid: {"available"}}}}}.
    FIX-2 — pembungkus aturan tunggal `stock_figures.allocate_makloon` (satu aturan alokasi untuk semua endpoint)."""
    from services.stock_figures import allocate_makloon, makloon_by_product_entity
    segs: List[Dict[str, Any]] = []
    for pid, by_ent in supply.items():
        for eid, ent in by_ent.items():
            for wid, wh in (ent.get("warehouses") or {}).items():
                segs.append({"product_id": pid, "owner_entity_id": eid, "warehouse_id": wid,
                             "available_qty": float(wh.get("available") or 0), "_wh": wh})
    mk = await makloon_by_product_entity(product_ids)
    allocate_makloon(segs, mk)
    for (pid, eid), qty in mk.items():
        ent = supply.get(pid, {}).get(eid)
        if ent is not None:
            ent["makloon_reserved"] = round(ent.get("makloon_reserved", 0.0) + float(qty or 0), 2)
    for s in segs:
        cut = s.get("makloon_reserved_qty", 0.0)
        if cut > 0:
            s["_wh"]["available"] -= cut
            ent = supply[s["product_id"]][s["owner_entity_id"]]
            ent["available"] -= cut


async def available_index(product_ids: Optional[List[str]] = None,
                          owner_entity_ids: Optional[Iterable[str]] = None) -> Dict[str, Dict[str, Any]]:
    """{product_id: {entity_id: {"available", "makloon_reserved", "warehouses": {wid: {"available"}}}}} menurut
    definisi tunggal K-04 (gudang yang dihitung saja, sesudah cadangan makloon) — FIX-2: dibangun dari
    `stock_figures.segments` (satu layanan angka stok).
    `owner_entity_ids`: None atau memuat "all" = semua badan usaha; daftar kosong = tidak ada (cakupan kosong)."""
    from services.stock_figures import segments
    want: Optional[Set[str]] = None
    if owner_entity_ids is not None:
        req = [e for e in owner_entity_ids if e]
        if "all" not in req:
            if not req:
                return {}
            want = set(req)
    supply: Dict[str, Dict[str, Any]] = {}
    for s in await segments(product_ids):
        if want is not None and s["owner_entity_id"] not in want:
            continue
        ent = supply.setdefault(s["product_id"], {}).setdefault(
            s["owner_entity_id"], {"available": 0.0, "makloon_reserved": 0.0, "warehouses": {}})
        av = float(s["available_qty"])
        ent["available"] += av
        ent["makloon_reserved"] = round(ent["makloon_reserved"] + s.get("makloon_reserved_qty", 0.0), 2)
        ent["warehouses"].setdefault(s["warehouse_id"], {"available": 0.0})["available"] += av
    return supply


async def available_by_product(owner_entity_id: Optional[str] = None,
                               product_ids: Optional[List[str]] = None) -> Dict[str, float]:
    """Tersedia per produk (satuan dasar) untuk satu badan usaha (atau semua bila kosong/"all")."""
    idx = await available_index(product_ids, [owner_entity_id] if owner_entity_id else None)
    return {pid: round(sum(max(e["available"], 0.0) for e in by_ent.values()), 2) for pid, by_ent in idx.items()}


async def low_stock_summary(owner_entity_ids: Optional[Iterable[str]] = None, limit: int = 50) -> Dict[str, Any]:
    """"Stok rendah" per produk per badan usaha (definisi tunggal K-04). Item diurutkan dari yang paling sedikit."""
    idx = await available_index(None, list(owner_entity_ids) if owner_entity_ids is not None else None)
    pids = list(idx)
    prods = {p["id"]: p for p in await db.products.find(
        {"id": {"$in": pids}}, {"_id": 0, "id": 1, "sku": 1, "name": 1, "base_unit": 1}).to_list(None)} if pids else {}
    items: List[Dict[str, Any]] = []
    for pid, by_ent in idx.items():
        for eid, ent in by_ent.items():
            av = round(max(ent["available"], 0.0), 2)
            if is_low_stock(av):
                p = prods.get(pid, {})
                items.append({"product_id": pid, "entity_id": eid, "sku": p.get("sku", ""),
                              "product_name": p.get("name", ""), "unit": p.get("base_unit") or "",
                              "available": av})
    items.sort(key=lambda r: (r["available"], r["sku"]))
    return {"count": len(items), "items": items[:limit], "threshold": LOW_STOCK_QTY,
            "label": LOW_STOCK_LABEL, "available_label": AVAILABLE_LABEL}
