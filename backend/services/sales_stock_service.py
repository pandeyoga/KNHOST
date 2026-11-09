"""Stok GLOBAL untuk layar sales (Kasir/POS, katalog): sales tidak memilah per entitas —
pemenuhan lintas entitas (transfer / PO) diputuskan admin. Barang datang dipisah:
untuk SO (sudah terikat pesanan, tidak bisa dijanjikan lagi) vs untuk restock (boleh dijanjikan).

FIX-2 (audit B3a SSOT-4/STK-5/STK-8/STK-12, B1 UI-06) — modul ini kini PEMBUNGKUS layanan angka stok tunggal
`services/stock_figures.py`. Yang berubah untuk pengguna:
* `entity_available_qty` (stok PT penjual) kini dikurangi cadangan makloon PT itu — dulu `/products` 477,63 vs
  `/dashboard` 177,63 untuk produk & PT yang sama;
* gudang non-aktif / data uji / saldo yatim tidak ikut (dulu semua saldo);
* "barang datang" grup tidak lagi menghitung pembelian antar-PT (barangnya sudah ada di stok PT penjual — hitung
  ganda); antar-PT dikonfirmasi tampil sebagai `entity_incoming_qty` milik PT pembeli; draf tidak dihitung;
* bila `scope` diberikan, tiap produk membawa `stock_figures` = dua angka {local, global} (roll lalu panjang).
"""
from typing import Any, Dict, List, Optional

from db import db


async def _sum_by_product(coll: str, match: Dict[str, Any], fields: List[str]) -> Dict[str, Dict[str, float]]:
    group: Dict[str, Any] = {"_id": "$product_id"}
    group.update({f: {"$sum": f"${f}"} for f in fields})
    return {r["_id"]: r for r in await db[coll].aggregate([{"$match": match}, {"$group": group}]).to_list(None)}


async def global_available(pid: str) -> float:
    """Tersedia GLOBAL satu produk (definisi tunggal `stock_figures`)."""
    from services.stock_figures import segments, sum_segments
    return sum_segments(await segments([pid]))["available_qty"]


async def global_available_many(ids: List[str]) -> Dict[str, float]:
    """Tersedia GLOBAL banyak produk sekaligus (satu baca saldo)."""
    from services.stock_figures import segments, sum_segments
    segs = await segments(ids)
    out: Dict[str, List[Dict[str, Any]]] = {pid: [] for pid in ids}
    for s in segs:
        out.setdefault(s["product_id"], []).append(s)
    return {pid: sum_segments(ss)["available_qty"] for pid, ss in out.items()}


async def apply_global(products: List[Dict[str, Any]], entity_id: str = "",
                       scope: Optional[Dict[str, Any]] = None,
                       segs: Optional[List[Dict[str, Any]]] = None) -> None:
    """`entity_id` = PT penjual (entitas aktif). Trial 22 Okt (B6): stok PT itu ikut dikirim terpisah
    (`entity_available_qty`, `entity_roll_count`, `stock_entity_name`) supaya katalog HP tidak membuat sales
    mengira stok grup = stok PT-nya sendiri. `scope` (FIX-2) = cakupan LOKAL pengguna (`stock_figures.viewer_scope`)."""
    from services import stock_figures as sf
    ids = [p["id"] for p in products if p.get("id")]
    if not ids:
        return
    # FIX-7 — `segs` = SEMUA segmen yang sudah dibaca pemanggil (dasbor) → dipersempit ke produk ini; sama dengan
    # `sf.segments(ids)` (alokasi makloon per produk × PT tidak bergantung produk lain). Tanpa `segs` dibaca di sini.
    if segs is None:
        segs = await sf.segments(ids)
    else:
        _want = set(ids)
        segs = [s for s in segs if s["product_id"] in _want]
    per: Dict[str, List[Dict[str, Any]]] = {}
    for s in segs:
        per.setdefault(s["product_id"], []).append(s)
    ent_name = ""
    if entity_id and entity_id != "all":
        ent = await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "short_name": 1, "legal_name": 1,
                                                                       "name": 1}) or {}
        ent_name = ent.get("short_name") or ent.get("name") or ent.get("legal_name") or ""
    inc_so: Dict[str, float] = {}
    inc_rs: Dict[str, float] = {}
    inc_ent: Dict[str, float] = {}
    for r in await sf.incoming_rows(ids, sources=("po", "interco")):
        pid = r["product_id"]
        if r["in_global"]:
            tgt = inc_so if r["bound_so"] else inc_rs
            tgt[pid] = tgt.get(pid, 0.0) + r["qty"]
        if entity_id and r["owner_entity_id"] == entity_id and r["in_atp"]:
            inc_ent[pid] = inc_ent.get(pid, 0.0) + r["qty"]
    figs = await sf.figures_for(ids, scope, segs) if scope is not None else {}
    for p in products:
        ss = per.get(p.get("id"), [])
        g = sf.sum_segments(ss)
        if entity_id and entity_id != "all":
            e = sf.sum_segments([s for s in ss if s["owner_entity_id"] == entity_id])
            p["entity_available_qty"] = e["available_qty"]
            p["entity_roll_count"] = int(e["available_rolls"])
            p["entity_makloon_reserved_qty"] = e["makloon_reserved_qty"]
            p["entity_incoming_qty"] = round(inc_ent.get(p["id"], 0.0), 2)
            if ent_name:
                p["stock_entity_name"] = ent_name
        p.update({
            "available_qty": g["available_qty"],
            "reserved_qty": round(g["reserved_qty"], 2),
            "on_hand_qty": round(g["on_hand_qty"], 2),
            "roll_count": int(g["available_rolls"]),
            "on_hand_roll_count": int(g["on_hand_rolls"]),
            "makloon_reserved_qty": round(g["makloon_reserved_qty"], 2),
            "incoming_so_qty": round(inc_so.get(p["id"], 0.0), 2),
            "incoming_restock_qty": round(inc_rs.get(p["id"], 0.0), 2),
            "stock_scope": "global",
        })
        if p.get("id") in figs:
            p["stock_figures"] = figs[p["id"]]
    if scope is not None:
        label = scope.get("label") or ""
        for p in products:
            p["stock_scope_label"] = label
