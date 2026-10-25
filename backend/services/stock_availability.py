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
    return {w["id"] async for w in db.warehouses.find({}, {"_id": 0, "id": 1}) if w.get("id")}


async def deduct_makloon(supply: Dict[str, Dict[str, Any]], product_ids: Optional[List[str]] = None) -> None:
    """W2-REQ-07 — bahan yang dicadangkan untuk makloon bukan stok bebas: kurangi dari `available` entitas lalu dari
    gudang (terbesar dulu). `supply` = {product_id: {entity_id: {"available", "warehouses": {wid: {"available"}}}}}.
    SATU implementasi untuk papan stok & definisi "Tersedia" (K-04)."""
    mres_q: Dict[str, Any] = {"status": "active"}
    if product_ids:
        mres_q["product_id"] = {"$in": product_ids}
    for m in await db.material_reservations.find(mres_q, {"_id": 0, "product_id": 1, "owner_entity_id": 1,
                                                          "qty": 1}).to_list(5000):
        ent = supply.get(m.get("product_id"), {}).get(m.get("owner_entity_id") or DEFAULT_ENTITY_ID)
        if not ent:
            continue
        left = float(m.get("qty") or 0)
        ent["makloon_reserved"] = round(ent.get("makloon_reserved", 0.0) + left, 2)
        take = min(left, ent["available"]); ent["available"] -= take; left = take
        for wh in sorted(ent["warehouses"].values(), key=lambda w: -w["available"]):
            cut = min(left, wh["available"]); wh["available"] -= cut; left -= cut
            if left <= EPS:
                break


async def available_index(product_ids: Optional[List[str]] = None,
                          owner_entity_ids: Optional[Iterable[str]] = None) -> Dict[str, Dict[str, Any]]:
    """{product_id: {entity_id: {"available", "makloon_reserved", "warehouses": {wid: {"available"}}}}} menurut
    definisi tunggal K-04 (gudang terdaftar saja, sesudah cadangan makloon).
    `owner_entity_ids`: None atau memuat "all" = semua badan usaha; daftar kosong = tidak ada (cakupan kosong)."""
    reg = await registered_warehouse_ids()
    q: Dict[str, Any] = {}
    if product_ids:
        q["product_id"] = {"$in": list(product_ids)}
    if owner_entity_ids is not None:
        req = [e for e in owner_entity_ids if e]
        if "all" not in req:
            if not req:
                return {}
            q["owner_entity_id"] = {"$in": req}
    supply: Dict[str, Dict[str, Any]] = {}
    async for b in db.inventory_balances.find(q, {"_id": 0, "product_id": 1, "warehouse_id": 1,
                                                 "owner_entity_id": 1, "available_qty": 1}):
        pid, wid = b.get("product_id"), b.get("warehouse_id")
        if not pid or not wid or wid not in reg:
            continue
        eid = b.get("owner_entity_id") or DEFAULT_ENTITY_ID
        ent = supply.setdefault(pid, {}).setdefault(eid, {"available": 0.0, "warehouses": {}})
        wh = ent["warehouses"].setdefault(wid, {"available": 0.0})
        av = float(b.get("available_qty", 0) or 0)
        ent["available"] += av
        wh["available"] += av
    await deduct_makloon(supply, list(product_ids) if product_ids else None)
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
