"""Fulfillment & ATP service (Fase 1 / Sub-fase 1.4 — ATP & Fulfillment Modes).

Mengklasifikasikan SUMBER PEMENUHAN per baris Sales Order (KN_16 §2) di atas
model inventory Roll-as-SSOT (KN_15):

  - from_stock     : stok on-hand milik entitas penjual cukup (available).
  - from_incoming  : sebagian/seluruh dipeg ke barang masuk (PO open / in-transit) → ATP.
  - inter_company  : kekurangan dapat dipenuhi dari stok entitas LAIN (perlu transfer antar-entitas).
  - backorder      : tidak ada sumber → menunggu stok (waiting_stock).

ATP (Available-To-Promise) mengikuti definisi proyeksi balance (KN_15):
  ATP = available + incoming   (incoming = in_transit_inbound + on_order PO terbuka)

Catatan konsistensi (RC-1/RC-10): service ini READ-ONLY (tidak memutasi stok).
Klasifikasi dipakai oleh preview-allocation (POS) & Inventory Status Board agar
Sales tahu risiko pemenuhan SEBELUM order dibuat. Reservasi nyata tetap di
roll_service.allocate_and_reserve_rolls (owner-scoped) saat order dibuat.
"""
from typing import Any, Dict, List, Optional
from db import db
from core_utils import DEFAULT_ENTITY_ID

# Status PO yang masih "pipeline" (belum jadi roll available). Mencakup PO yang
# menunggu approval, sudah disetujui/dikirim ke supplier, dan sedang diterima.
from services.roll_service import OPEN_PO_STATUSES  # KN-A11 — satu definisi bersama

EPS = 0.001


async def _entity_map() -> Dict[str, Dict[str, Any]]:
    return {e["id"]: e for e in await db.business_entities.find({}, {"_id": 0}).to_list(200)}


def _entity_label(entities: Dict[str, Dict[str, Any]], eid: str) -> str:
    e = entities.get(eid, {})
    return e.get("short_name") or e.get("legal_name") or eid


async def build_supply_index(
    product_ids: Optional[List[str]] = None,
    registered_only: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """Bangun indeks pasokan per produk → per entitas → per gudang.

    Menggabungkan:
      - inventory_balances (available/reserved/on_hand/in_transit_inbound) per (produk, gudang, owner)
      - purchase_orders OPEN (on_order = quantity - received_qty) per (produk, gudang, entitas)

    Return:
      { product_id: { entity_id: {
            available, reserved, on_hand, incoming, atp,
            warehouses: { warehouse_id: {available, reserved, on_hand, incoming, atp} }
      } } }
    """
    # FIX-2 (B3a STK-5/DUP-1/SSOT-4) — saldo dibaca lewat SATU layanan angka stok (`stock_figures.segments`): gudang
    # yang DIHITUNG saja (aktif & bukan data uji) dan cadangan makloon sudah dialokasikan dengan satu aturan. Dulu
    # `registered_only=False` (pratinjau alokasi) membaca semua saldo termasuk gudang yatim; kini semua pemanggil sama.
    from services.stock_figures import segments as _segments, counted_warehouse_ids
    known_wh = await counted_warehouse_ids()

    supply: Dict[str, Dict[str, Any]] = {}

    def _seg(pid: str, eid: str, wid: str) -> Dict[str, Any]:
        prod = supply.setdefault(pid, {})
        ent = prod.setdefault(eid, {
            "available": 0.0, "reserved": 0.0, "on_hand": 0.0, "incoming": 0.0, "atp": 0.0,
            "makloon_reserved": 0.0, "committed": 0.0, "available_rolls": 0, "warehouses": {},
        })
        wh = ent["warehouses"].setdefault(wid, {
            "available": 0.0, "reserved": 0.0, "on_hand": 0.0, "incoming": 0.0, "atp": 0.0,
            "committed": 0.0, "available_rolls": 0,
        })
        return ent, wh

    for b in await _segments(product_ids):
        pid, eid, wid = b["product_id"], b["owner_entity_id"] or DEFAULT_ENTITY_ID, b["warehouse_id"]
        ent, wh = _seg(pid, eid, wid)
        avail = float(b.get("available_qty", 0) or 0)
        rsv = float(b.get("reserved_qty", 0) or 0)
        oh = float(b.get("on_hand_qty", 0) or 0)
        in_inbound = float(b.get("in_transit_inbound_qty", 0) or 0)
        ent["available"] += avail; wh["available"] += avail
        ent["reserved"] += rsv; wh["reserved"] += rsv
        ent["on_hand"] += oh; wh["on_hand"] += oh
        ent["incoming"] += in_inbound; wh["incoming"] += in_inbound
        ent["makloon_reserved"] = round(ent["makloon_reserved"] + float(b.get("makloon_reserved_qty") or 0), 2)
        # FIX-2 (STK-9) — dialokasikan/diambil/dikemas dipisah dari "tertahan"; jumlah roll tersedia ikut (roll dulu).
        com = sum(float(b.get(k) or 0) for k in ("committed_qty", "picked_qty", "packed_qty"))
        ent["committed"] += com; wh["committed"] += com
        ent["available_rolls"] += int(b.get("available_rolls") or 0); wh["available_rolls"] += int(b.get("available_rolls") or 0)

    # on_order dari PO terbuka (qty - received_qty), per (produk, gudang, entitas)
    po_query: Dict[str, Any] = {"status": {"$in": OPEN_PO_STATUSES}}
    pos = await db.purchase_orders.find(po_query, {"_id": 0, "items": 1, "warehouse_id": 1, "entity_id": 1,
                                                     "expected_delivery_date": 1}).to_list(None)
    from services import atp_policy as _atp
    await _atp.horizon_days()   # FIX-2 keputusan #4 — horizon = setelan
    for po in pos:
        eid = po.get("entity_id") or DEFAULT_ENTITY_ID
        wid = po.get("warehouse_id")
        if not wid or wid not in known_wh:
            continue
        if not _atp.within_horizon(po.get("expected_delivery_date")):   # KN-D11 — horizon ATP tunggal
            continue
        for it in po.get("items", []):
            pid = it.get("product_id")
            if not pid:
                continue
            if product_ids and pid not in product_ids:
                continue
            # FIX-2 (DUP-2) — sisa PO dalam satuan dasar lewat SATU rumus (`stock_figures.po_open_base_qty`).
            from services.stock_figures import po_open_base_qty
            on_order = po_open_base_qty(it)
            if on_order <= EPS:
                continue
            ent, wh = _seg(pid, eid, wid)
            ent["incoming"] += on_order; wh["incoming"] += on_order

    # FIX-2 (STK-4) — pembelian antar-PT yang DIKONFIRMASI ikut "barang masuk" PT pembeli (definisi `atp_policy`);
    # dulu papan stok tidak membacanya sehingga ATP papan ≠ `/stock/atp` untuk produk & PT yang sama. Draf tidak dihitung.
    from services.stock_figures import incoming_rows
    for r in await incoming_rows(product_ids, sources=("interco",)):
        if not r["in_atp"] or not _atp.within_horizon(r.get("eta")):
            continue
        ent = supply.setdefault(r["product_id"], {}).get(r["owner_entity_id"])
        if ent is None:
            ent, _ = _seg(r["product_id"], r["owner_entity_id"], "")
            ent["warehouses"].pop("", None)
        ent["incoming"] += float(r["qty"] or 0)

    # KN-D11 — ATP = available + incoming(horizon) − backorder aktif (SATU rumus: atp_policy).
    for pid, ents in supply.items():
        for eid, ent in ents.items():
            pending_ent = await _atp.pending_backorder_qty(pid, eid)
            for wid, wh in ent["warehouses"].items():
                pending_wh = await _atp.pending_backorder_qty(pid, eid, wid, include_unassigned=False)
                wh["pending_demand"] = pending_wh
                wh["atp"] = _atp.compute_atp(wh["available"], wh["incoming"], pending_wh)
                for k in ("available", "reserved", "on_hand", "incoming", "committed"):
                    wh[k] = round(wh[k], 2)
            ent["pending_demand"] = pending_ent
            ent["atp"] = _atp.compute_atp(ent["available"], ent["incoming"], pending_ent)
            for k in ("available", "reserved", "on_hand", "incoming", "committed"):
                ent[k] = round(ent.get(k, 0.0), 2)
    return supply


def _classify_one(
    pid: str, qty: float, entity_id: str,
    supply: Dict[str, Any], products: Dict[str, Any], entities: Dict[str, Any],
) -> Dict[str, Any]:
    """Klasifikasi 1 baris → mode + breakdown + ATP + peluang inter-entitas."""
    prod = products.get(pid, {})
    ents = supply.get(pid, {})
    own = ents.get(entity_id, {"available": 0.0, "incoming": 0.0, "atp": 0.0})
    own_available = float(own.get("available", 0) or 0)
    own_incoming = float(own.get("incoming", 0) or 0)
    own_atp = round(own_available + own_incoming, 2)

    # Stok entitas lain (peluang inter-company)
    cross_entity: List[Dict[str, Any]] = []
    other_available_total = 0.0
    for eid, data in ents.items():
        if eid == entity_id:
            continue
        av = float(data.get("available", 0) or 0)
        if av > EPS:
            cross_entity.append({
                "entity_id": eid,
                "entity_name": _entity_label(entities, eid),
                "available_qty": round(av, 2),
            })
            other_available_total += av
    cross_entity.sort(key=lambda x: -x["available_qty"])

    # Waterfall alokasi (severity meningkat): stok → incoming → inter-entitas → backorder
    need = float(qty)
    from_stock = min(need, own_available); need -= from_stock
    from_incoming = min(need, own_incoming); need -= from_incoming
    inter_company = min(need, other_available_total); need -= inter_company
    backorder = round(max(0.0, need), 2)

    from_stock = round(from_stock, 2)
    from_incoming = round(from_incoming, 2)
    inter_company = round(inter_company, 2)

    if backorder > EPS:
        primary_mode = "backorder"
    elif inter_company > EPS:
        primary_mode = "inter_company"
    elif from_incoming > EPS:
        primary_mode = "from_incoming"
    else:
        primary_mode = "from_stock"

    fulfillable_qty = round(float(qty) - backorder, 2)
    explanation = _explain(primary_mode, qty, from_stock, from_incoming, inter_company,
                           backorder, own_available, own_incoming, cross_entity)

    return {
        "product_id": pid,
        "sku": prod.get("sku", ""),
        "product_name": prod.get("name", ""),
        "unit": prod.get("base_unit", "meter"),
        "requested_qty": round(float(qty), 2),
        "own_available": round(own_available, 2),
        "own_incoming": round(own_incoming, 2),
        "own_atp": own_atp,
        "other_entity_available": round(other_available_total, 2),
        "breakdown": {
            "from_stock": from_stock,
            "from_incoming": from_incoming,
            "inter_company": inter_company,
            "backorder": backorder,
        },
        "primary_mode": primary_mode,
        "can_fulfill_from_stock": own_available + EPS >= float(qty),
        "fulfillable_qty": fulfillable_qty,
        "cross_entity": cross_entity,
        "explanation": explanation,
    }


def _explain(mode, qty, fs, fi, ic, bo, own_av, own_inc, cross) -> str:
    if mode == "from_stock":
        return f"Stok on-hand cukup ({own_av:g}). Dapat langsung direservasi."
    if mode == "from_incoming":
        return (f"Stok on-hand {fs:g}, sisanya {fi:g} dipeg ke barang masuk (PO/incoming {own_inc:g}). "
                f"ATP terpenuhi tanpa backorder.")
    if mode == "inter_company":
        names = ", ".join(c["entity_name"] for c in cross) or "entitas lain"
        return (f"Kekurangan {ic:g} dapat dipenuhi dari {names} (transfer antar-entitas). "
                f"Stok sendiri {own_av:g}, incoming {own_inc:g}.")
    return (f"Kekurangan {bo:g} tidak ada sumber (stok {own_av:g} + incoming {own_inc:g} "
            f"+ entitas lain belum cukup) → backorder / menunggu stok.")


async def classify_lines(items: List[Dict[str, Any]], entity_id: str) -> Dict[str, Any]:
    """Klasifikasi daftar baris order untuk preview-allocation (READ-ONLY)."""
    entity_id = entity_id or DEFAULT_ENTITY_ID
    product_ids = [it.get("product_id") for it in items if it.get("product_id")]
    products = {p["id"]: p for p in await db.products.find(
        {"id": {"$in": product_ids}} if product_ids else {}, {"_id": 0}).to_list(2000)}
    entities = await _entity_map()
    supply = await build_supply_index(product_ids or None)

    lines: List[Dict[str, Any]] = []
    for it in items:
        pid = it.get("product_id")
        qty = float(it.get("quantity", 0) or 0)
        if not pid:
            continue
        lines.append(_classify_one(pid, qty, entity_id, supply, products, entities))

    modes_count: Dict[str, int] = {"from_stock": 0, "from_incoming": 0, "inter_company": 0, "backorder": 0}
    for ln in lines:
        modes_count[ln["primary_mode"]] = modes_count.get(ln["primary_mode"], 0) + 1

    return {
        "entity_id": entity_id,
        "entity_name": _entity_label(entities, entity_id),
        "lines": lines,
        "summary": {
            "total_lines": len(lines),
            "modes_count": modes_count,
            "all_from_stock": all(ln["primary_mode"] == "from_stock" for ln in lines) if lines else True,
            "has_backorder": any(ln["primary_mode"] == "backorder" for ln in lines),
            "has_intercompany": any(ln["primary_mode"] == "inter_company" for ln in lines),
            "has_incoming": any(ln["primary_mode"] == "from_incoming" for ln in lines),
        },
    }


async def status_board(
    product_id: Optional[str] = None,
    owner_entity_id: Optional[str] = None,
    visible_entity_ids: Optional[List[str]] = None,
    cross_entity_detail: bool = True,
    registered_only: bool = False,
) -> List[Dict[str, Any]]:
    """Inventory Status Board: ringkasan per produk (on_hand/available/reserved/
    incoming/atp) + breakdown per entitas & gudang + indikator peluang inter-entitas.

    FASE E-0/E-5 (E5.1 — keputusan pemilik #1): papan ini dulu MENGABAIKAN konteks
    entitas sehingga sales melihat rincian stok per gudang milik PT lain (akar
    masalah yang sama dengan L21: sales menjanjikan barang yang bukan miliknya).

    Aturan baru:
      * `cross_entity_detail=False` (peran sales/gudang) → `by_entity` HANYA entitas
        sendiri; total baris = total entitas sendiri; angka grup tetap diberikan
        sebagai **`global_total`** (agregat tanpa rincian entitas/gudang) supaya
        isyarat "tersedia di PT lain" tetap ada tanpa membocorkan angka per gudang.
      * `cross_entity_detail=True` (admin/manager) → rincian penuh seperti sebelumnya.
    """
    product_ids = [product_id] if product_id else None
    products_cur = await db.products.find(
        {"id": product_id} if product_id else {}, {"_id": 0}).to_list(None)
    products = {p["id"]: p for p in products_cur}
    warehouses = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0}).to_list(200)}
    entities = await _entity_map()
    supply = await build_supply_index(product_ids, registered_only=registered_only)

    rows: List[Dict[str, Any]] = []
    for pid, prod in products.items():
        ents = supply.get(pid, {})
        by_entity: List[Dict[str, Any]] = []
        totals = {"on_hand": 0.0, "available": 0.0, "reserved": 0.0, "incoming": 0.0, "atp": 0.0,
                  "committed": 0.0, "makloon_reserved": 0.0, "available_rolls": 0}
        pend_total = 0.0
        entities_with_stock = 0
        # Agregat GRUP dihitung SEBELUM penyaringan supaya isyarat lintas-PT tetap ada.
        group_total = {"on_hand": 0.0, "available": 0.0, "reserved": 0.0,
                       "incoming": 0.0, "atp": 0.0, "available_rolls": 0}
        group_entities_with_stock = 0
        for _eid, _ent in ents.items():
            for k in group_total:
                group_total[k] += _ent.get(k, 0)
            if _ent["available"] > EPS:
                group_entities_with_stock += 1
        for eid, ent in ents.items():
            if owner_entity_id and owner_entity_id != "all" and eid != owner_entity_id:
                continue
            if visible_entity_ids is not None and eid not in visible_entity_ids:
                continue
            by_wh = []
            for wid, wh in ent["warehouses"].items():
                by_wh.append({
                    "warehouse_id": wid,
                    "warehouse_name": warehouses.get(wid, {}).get("name", wid),
                    "warehouse_city": warehouses.get(wid, {}).get("city", ""),
                    **{k: wh.get(k, 0) for k in ("on_hand", "available", "reserved", "incoming", "atp", "committed",
                                                 "available_rolls")},
                    "pending_demand": round(float(wh.get("pending_demand") or 0), 2),
                })
            by_wh.sort(key=lambda x: -x["available"])
            by_entity.append({
                "entity_id": eid,
                "entity_name": _entity_label(entities, eid),
                "on_hand": ent["on_hand"], "available": ent["available"],
                "reserved": ent["reserved"], "incoming": ent["incoming"], "atp": ent["atp"],
                "committed": ent.get("committed", 0.0), "makloon_reserved": ent.get("makloon_reserved", 0.0),
                "available_rolls": ent.get("available_rolls", 0),
                "pending_demand": round(float(ent.get("pending_demand") or 0), 2),
                "by_warehouse": by_wh,
            })
            for k in totals:
                totals[k] += ent.get(k, 0)
            pend_total += float(ent.get("pending_demand") or 0)
            if ent["available"] > EPS:
                entities_with_stock += 1
        if owner_entity_id and owner_entity_id != "all" and not by_entity:
            # produk tanpa stok utk entitas terfilter → tetap tampil dgn nol
            pass
        by_entity.sort(key=lambda x: -x["available"])
        rows.append({
            "product_id": pid,
            "sku": prod.get("sku", ""),
            "product_name": prod.get("name", ""),
            "unit": prod.get("base_unit", "meter"),
            "image": prod.get("image", ""),
            "total_on_hand": round(totals["on_hand"], 2),
            "total_available": round(totals["available"], 2),
            "total_reserved": round(totals["reserved"], 2),
            "total_incoming": round(totals["incoming"], 2),
            "total_atp": round(totals["atp"], 2),
            "total_available_rolls": int(totals["available_rolls"]),
            # Transparansi rumus: ATP = tersedia + incoming(≤ horizon) − permintaan tertunda (backorder);
            # FIX-2 (STK-9) — stok fisik = tersedia + cadangan makloon + dipesan + dialokasikan + tertahan
            # (karantina/QC/blokir/hold/rusak/dalam proses). Dulu dialokasikan/diambil/dikemas ikut "tertahan".
            "total_pending_demand": round(pend_total, 2),
            "total_committed": round(totals["committed"], 2),
            "total_makloon_reserved": round(totals["makloon_reserved"], 2),
            "total_hold": round(max(totals["on_hand"] - totals["available"] - totals["reserved"]
                                    - totals["committed"] - totals["makloon_reserved"], 0.0), 2),
            "entities_with_stock": (entities_with_stock if cross_entity_detail
                                    else group_entities_with_stock),
            # Isyarat "tersedia di entitas lain" TANPA membocorkan angka per gudang.
            "has_intercompany_opportunity": group_entities_with_stock > 1 and (
                group_total["available"] - totals["available"] > EPS),
            "global_total": {
                "on_hand": round(group_total["on_hand"], 2),
                "available": round(group_total["available"], 2),
                "reserved": round(group_total["reserved"], 2),
                "incoming": round(group_total["incoming"], 2),
                "atp": round(group_total["atp"], 2),
                "available_rolls": int(group_total["available_rolls"]),
                "entities_with_stock": group_entities_with_stock,
            },
            "other_entities_available": round(
                max(group_total["available"] - totals["available"], 0), 2),
            "detail_scope": "group" if cross_entity_detail else "own_entity",
            "by_entity": by_entity,
        })
    rows.sort(key=lambda r: r["product_name"])
    return rows
