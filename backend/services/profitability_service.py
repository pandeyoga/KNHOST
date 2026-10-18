"""FINANCE — Analisis Profitabilitas / Margin (EPIC P0-2 · R5.6).

G3 D4-FIN-04 (keputusan user) — dua metrik terpisah:
- **Realisasi** (`totals`, `by_*`, `monthly`): barang yang BENAR-BENAR terkirim (surat jalan).
  Pendapatan = porsi nilai pesanan (grand − PPN) sesuai barang keluar, tanggal = tanggal kirim
  (WIB), HPP = snapshot biaya roll saat dispatch. Pesanan lama tanpa surat jalan yang sudah
  shipped/done diakui per pesanan (tanggal kirim/`delivered_at`, HPP WAC — ditandai `legacy`).
- **Estimasi nilai pesanan** (`estimate`): SO confirmed/reserved/dikirim menurut tanggal pesanan,
  HPP WAC kini. Tidak dicampur dengan realisasi.
"""
from typing import Any, Dict, List, Optional, Tuple

from db import db
from core_utils import now_iso
from services.costing_service import wac_for_product
from services.analytics_time import to_wib_date

EPS = 0.005
# Status SO untuk ESTIMASI nilai pesanan (booked).
SOLD_STATUSES = ["confirmed", "reserved", "partially_shipped", "shipped", "done"]
SHIPPED_STATUSES = ["partially_shipped", "shipped", "done"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
DIMS = ("by_product", "by_category", "by_customer", "by_sales", "by_entity")


def _pct(margin: float, revenue: float) -> Optional[float]:
    return round(margin / revenue * 100, 1) if revenue > EPS else None


def _date_filter(start: Optional[str], end: Optional[str]) -> Dict[str, str]:
    f: Dict[str, str] = {}
    if start:
        f["$gte"] = start[:10] if "T" not in start else start  # G3 V3-DATE-01
    if end:
        f["$lte"] = end if "T" in end else f"{end}T23:59:59.999999"
    return f


def _new_acc() -> Dict[str, Any]:
    return {**{d: {} for d in DIMS}, "monthly": {}, "orders": set(),
            "rev": 0.0, "base": 0.0, "landed": 0.0, "qty": 0.0}


def _bump(bucket: Dict[str, Dict[str, Any]], key: str, name: str, r: Dict[str, Any]) -> None:
    row = bucket.setdefault(key, {"key": key, "name": name, "revenue": 0.0, "cogs_base": 0.0,
                                  "cogs_landed": 0.0, "qty": 0.0, "orders": set()})
    row["revenue"] += r["revenue"]
    row["cogs_base"] += r["cogs_base"]
    row["cogs_landed"] += r["cogs_landed"]
    row["qty"] += r["qty"]
    row["orders"].add(r["oid"])


def _add(acc: Dict[str, Any], r: Dict[str, Any]) -> None:
    _bump(acc["by_product"], r["pid"], r["pname"], r)
    _bump(acc["by_category"], r["cat"], r["cat"], r)
    _bump(acc["by_customer"], r["cid"] or r["cust_name"], r["cust_name"], r)
    _bump(acc["by_sales"], r["sales_key"], r["sales_name"], r)
    _bump(acc["by_entity"], r["ent"] or "(none)", r["ent_name"], r)
    mkey = (to_wib_date(r["date"]) or "")[:7]
    m = acc["monthly"].setdefault(mkey, {"revenue": 0.0, "cogs_base": 0.0, "cogs_landed": 0.0})
    m["revenue"] += r["revenue"]
    m["cogs_base"] += r["cogs_base"]
    m["cogs_landed"] += r["cogs_landed"]
    acc["rev"] += r["revenue"]
    acc["base"] += r["cogs_base"]
    acc["landed"] += r["cogs_landed"]
    acc["qty"] += r["qty"]
    acc["orders"].add(r["oid"])


def _finalize(bucket: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for row in bucket.values():
        rev, cb, cl = round(row["revenue"], 2), round(row["cogs_base"], 2), round(row["cogs_landed"], 2)
        cogs = round(cb + cl, 2)
        margin = round(rev - cogs, 2)
        out.append({"key": row["key"], "name": row["name"], "revenue": rev, "cogs_base": cb,
                    "cogs_landed": cl, "cogs": cogs, "landed_included": cl > EPS, "margin": margin,
                    "margin_pct": _pct(margin, rev), "qty": round(row["qty"], 2),
                    "orders": len(row["orders"])})
    out.sort(key=lambda r: r["margin"], reverse=True)
    return out


def _trend(monthly: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
    trend = []
    for mk in sorted(monthly.keys()):
        rev = round(monthly[mk]["revenue"], 2)
        cb, cl = round(monthly[mk]["cogs_base"], 2), round(monthly[mk]["cogs_landed"], 2)
        cg = round(cb + cl, 2)
        mm = int(mk[5:7]) if len(mk) >= 7 and mk[5:7].isdigit() else 0
        trend.append({"month": mk, "label": f"{MONTHS[mm - 1]} {mk[:4]}" if mm else mk,
                      "revenue": rev, "cogs_base": cb, "cogs_landed": cl, "cogs": cg,
                      "margin": round(rev - cg, 2)})
    return trend


def _totals(acc: Dict[str, Any]) -> Dict[str, Any]:
    rev, base, landed = round(acc["rev"], 2), round(acc["base"], 2), round(acc["landed"], 2)
    cogs = round(base + landed, 2)
    gross = round(rev - cogs, 2)
    return {"revenue": rev, "cogs_base": base, "cogs_landed": landed, "cogs": cogs,
            "landed_included": landed > EPS, "margin": gross, "margin_pct": _pct(gross, rev),
            "qty": round(acc["qty"], 2), "orders": len(acc["orders"])}


def _order_net_alloc(o: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[float]]:
    """G3 D4-FIN-03 — pendapatan order = grand_total − ppn_amount dialokasikan proporsional ke baris."""
    lines = [it for it in o.get("items", [])
             if float(it.get("base_quantity") or it.get("quantity") or 0) > 0
             or float(it.get("line_total", it.get("subtotal", 0)) or 0) > 0]
    raw = [float(it.get("line_total", it.get("subtotal", 0)) or 0) for it in lines]
    gt = float(o.get("grand_total") or 0)
    net = round(gt - float(o.get("ppn_amount") or 0), 2) if gt > 0 else round(sum(raw), 2)
    tot_raw = sum(raw)
    alloc = [round(r * net / tot_raw, 2) if tot_raw else 0.0 for r in raw]
    if alloc:
        alloc[-1] = round(alloc[-1] + net - sum(alloc), 2)
    return lines, alloc


class _Ctx:
    def __init__(self, entity_id: Optional[str]):
        self.entity_id = entity_id
        self.cmap: Dict[str, Dict[str, Any]] = {}
        self.emap: Dict[str, str] = {}
        self.wac: Dict[str, Tuple[float, float]] = {}

    async def load(self, orders: List[Dict[str, Any]]) -> None:
        cids = list({o.get("customer_id") for o in orders if o.get("customer_id")} - set(self.cmap))
        if cids:
            for c in await db.customers.find({"id": {"$in": cids}}, {"_id": 0, "id": 1, "name": 1,
                                             "assigned_sales_id": 1, "assigned_sales_name": 1}).to_list(None):
                self.cmap[c["id"]] = c
        eids = list({o.get("entity_id") or self.entity_id for o in orders
                     if (o.get("entity_id") or self.entity_id)} - set(self.emap))
        if eids:
            for e in await db.business_entities.find({"id": {"$in": eids}}, {"_id": 0, "id": 1,
                                                     "short_name": 1, "legal_name": 1}).to_list(None):
                self.emap[e["id"]] = e.get("short_name") or e.get("legal_name") or e["id"]

    async def wac_split(self, pid: str, ent: Optional[str], it: Dict[str, Any]) -> Tuple[float, float]:
        ck = f"{pid}::{ent or ''}"
        if ck not in self.wac:
            w = await wac_for_product(pid, entity_id=ent)
            wac = float(w.get("wac", 0) or 0)
            wb, wl = float(w.get("wac_base", 0) or 0), float(w.get("wac_landed", 0) or 0)
            if wac <= 0:
                wb, wl = float(it.get("unit_cost", 0) or 0), 0.0  # fallback snapshot roll
            elif wb <= 0 and wl <= 0:
                wb = wac
            self.wac[ck] = (wb, wl)
        return self.wac[ck]

    def row(self, o: Dict[str, Any], it: Dict[str, Any], revenue: float, cb: float, cl: float,
            qty: float, date: str) -> Dict[str, Any]:
        ent = o.get("entity_id") or self.entity_id
        cid = o.get("customer_id") or ""
        cust = self.cmap.get(cid, {})
        sales_name = o.get("sales_name") or cust.get("assigned_sales_name") or "(Tanpa Sales)"
        pid = it.get("product_id") or ""
        return {"oid": o.get("id"), "ent": ent, "ent_name": self.emap.get(ent or "", ent or "(Tanpa PT)"),
                "cid": cid, "cust_name": o.get("customer_name") or cust.get("name") or "(Tanpa Pelanggan)",
                "sales_key": o.get("assigned_sales_id") or cust.get("assigned_sales_id") or sales_name,
                "sales_name": sales_name, "pid": pid, "pname": it.get("product_name") or pid,
                "cat": it.get("category") or "(Tanpa Kategori)", "revenue": revenue,
                "cogs_base": cb, "cogs_landed": cl, "qty": qty, "date": date}


async def _order_rows(ctx: _Ctx, o: Dict[str, Any], date: str):
    lines, alloc = _order_net_alloc(o)
    for idx, it in enumerate(lines):
        qty = float(it.get("base_quantity") or it.get("quantity") or 0)
        wb, wl = await ctx.wac_split(it.get("product_id") or "", o.get("entity_id") or ctx.entity_id, it)
        yield ctx.row(o, it, alloc[idx], round(wb * qty, 2), round(wl * qty, 2), qty, date)


async def _shipment_row(ctx: _Ctx, o: Dict[str, Any], sh: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    from services import gl_service as gl
    it = gl._order_item_for(o, sh.get("product_id", ""))
    qty = float(sh.get("qty") or 0)
    if not it or qty <= 0:
        return None
    _, alloc = _order_net_alloc(o)
    net = round(sum(alloc), 2)
    revenue = round(net * gl.shipment_value_share(o, sh), 2)
    snap = sh.get("rolls") or []
    if snap and all(float(r.get("unit_cost") or 0) > 0 for r in snap):
        cb = round(sum(float(r.get("extended_cost") or float(r["unit_cost"]) * float(r.get("length") or 0))
                       for r in snap), 2)
        cl = 0.0  # snapshot roll sudah memuat landed cost yang terbebankan saat kirim
    else:
        wb, wl = await ctx.wac_split(it.get("product_id") or "", o.get("entity_id") or ctx.entity_id, it)
        cb, cl = round(wb * qty, 2), round(wl * qty, 2)
    return ctx.row(o, it, revenue, cb, cl, qty, sh.get("created_at") or "")


def _section(acc: Dict[str, Any]) -> Dict[str, Any]:
    return {"totals": _totals(acc), **{d: _finalize(acc[d]) for d in DIMS}, "monthly": _trend(acc["monthly"])}


async def profitability(start: Optional[str] = None, end: Optional[str] = None,
                        scope: Optional[Dict[str, Any]] = None,
                        entity_id: Optional[str] = None) -> Dict[str, Any]:
    from services import gl_service as gl
    ctx = _Ctx(entity_id)
    date_f = _date_filter(start, end)

    # ── Realisasi: surat jalan dalam periode (tanggal kirim) ──
    sq: Dict[str, Any] = {"status": {"$nin": list(gl.SHIPMENT_DEAD)}}
    if date_f:
        sq["created_at"] = date_f
    ships = await db.shipments.find(sq, {"_id": 0}).to_list(None)
    oids = list({s.get("order_id") for s in ships if s.get("order_id")})
    ship_orders: Dict[str, Dict[str, Any]] = {}
    if oids:
        rows = await db.sales_orders.find({"id": {"$in": oids}, "status": {"$nin": list(gl.DEAD_STATUSES)},
                                           **(scope or {})}, {"_id": 0}).to_list(None)
        ship_orders = {o["id"]: o for o in rows}
    # pesanan lama shipped/done TANPA surat jalan sama sekali → diakui per pesanan
    lq: Dict[str, Any] = {"status": {"$in": SHIPPED_STATUSES}, **(scope or {})}
    legacy_cand = await db.sales_orders.find(lq, {"_id": 0}).to_list(None)
    has_ship = set(await db.shipments.distinct("order_id", {"order_id": {"$in": [o["id"] for o in legacy_cand]},
                                                            "status": {"$nin": list(gl.SHIPMENT_DEAD)}})) \
        if legacy_cand else set()
    legacy = []
    for o in legacy_cand:
        if o["id"] in has_ship:
            continue
        d = o.get("delivered_at") or o.get("shipped_at") or o.get("created_at") or ""
        if ("$gte" in date_f and d < date_f["$gte"]) or ("$lte" in date_f and d > date_f["$lte"]):
            continue
        legacy.append((o, d))

    # ── Estimasi nilai pesanan: tanggal pesanan, WAC kini ──
    eq: Dict[str, Any] = {"status": {"$in": SOLD_STATUSES}, **(scope or {})}
    if date_f:
        eq["created_at"] = date_f
    booked = await db.sales_orders.find(eq, {"_id": 0}).to_list(None)

    await ctx.load(list(ship_orders.values()) + [o for o, _ in legacy] + booked)

    real = _new_acc()
    for sh in ships:
        o = ship_orders.get(sh.get("order_id"))
        if o:
            r = await _shipment_row(ctx, o, sh)
            if r:
                _add(real, r)
    for o, d in legacy:
        async for r in _order_rows(ctx, o, d):
            _add(real, r)
    est = _new_acc()
    for o in booked:
        async for r in _order_rows(ctx, o, o.get("created_at") or ""):
            _add(est, r)

    return {
        "period": {"start": start or "", "end": end or ""},
        "metric": "realised_shipped",
        "metric_label": "Realisasi = barang terkirim (tanggal & HPP saat kirim)",
        **_section(real),
        "legacy_orders": len(legacy),
        "estimate": {"label": "Nilai pesanan (estimasi, tanggal pesanan · HPP WAC kini)", **_section(est)},
        "cost_basis": "HPP snapshot roll saat kirim (fallback WAC)",
        "tz": "Asia/Jakarta",
        "generated_at": now_iso(),
    }
