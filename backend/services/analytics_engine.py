"""Tanya KN F1.3 — kompilator `query_metrics` & `analyze_change` → agregasi Mongo.

Masukan = argumen tool (Lampiran C), keluaran = format hasil Katalog §E. Hak akses diterapkan
di sini (entitas, sales-sendiri, lini, margin, nilai stok, izin modul); model tidak pernah
menyusun kueri sendiri. Semua angka turunan (total, delta, persen, pangsa) dihitung mesin.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from db import db
from dependencies import has_permission
from core_utils import now_iso
from services import analytics_catalog as cat
from services import analytics_facts as facts
from services.analytics_config import ai_policy, role_may
from services.analytics_time import Period, compare_period, now_wib, period_from_args
from services.line_scope import visibility_query

MAX_TIME_MS = 10000
TZ = "Asia/Jakarta"
Key = Tuple[Any, ...]
_ttl_ready = False


class AnalyticsError(ValueError):
    """Argumen tidak sah → pesan Bahasa Indonesia untuk model/pengguna."""


@dataclass
class Scope:
    user: Dict[str, Any]
    entity_ids: List[str]
    sales_only: Optional[str]
    line_q: Dict[str, Any]
    policy: Dict[str, Any]
    perms: Dict[Tuple[str, str], bool] = field(default_factory=dict)
    _owned: Optional[List[str]] = None

    @property
    def role(self) -> str:
        return self.user.get("role") or ""

    async def allowed(self, perms) -> bool:
        for p in perms:
            if p not in self.perms:
                self.perms[p] = await has_permission(self.user, *p)
            if self.perms[p]:
                return True
        return False

    async def owned_customers(self) -> List[str]:
        if self._owned is None:
            self._owned = await db.customers.distinct("id", {"assigned_sales_id": self.sales_only})
        return self._owned


async def build_scope(user: Dict[str, Any], ctx: Any, entity_scope: str = "active") -> Scope:
    allowed = list(ctx.allowed_entity_ids or [ctx.active_entity_id])
    combined = ctx.is_cross_entity or ctx.can_view_combined
    if entity_scope in ("per_entity", "all_allowed") and combined:
        ids = allowed
    elif getattr(ctx, "view_all", False) and combined:
        ids = allowed
    else:
        ids = [ctx.active_entity_id]
    return Scope(user=user, entity_ids=ids, sales_only=user["id"] if user.get("role") == "sales" else None,
                 line_q=visibility_query(user, "line_code"), policy=await ai_policy())


# ── ekspresi tanggal ──────────────────────────────────────────────────────────
def _wib_day(field_path: str) -> Dict[str, Any]:
    return {"$dateToString": {"format": "%Y-%m-%d", "timezone": TZ,
                              "date": {"$dateFromString": {"dateString": field_path, "onError": None, "onNull": None}}}}


def _grain(day_expr: Any, grain: str) -> Any:
    if grain == "day":
        return day_expr
    if grain == "month":
        return {"$substrBytes": [day_expr, 0, 7]}
    if grain == "year":
        return {"$substrBytes": [day_expr, 0, 4]}
    if grain == "week":
        return {"$dateToString": {"format": "%Y-%m-%d", "date": {"$dateTrunc": {
            "date": {"$dateFromString": {"dateString": day_expr}}, "unit": "week", "startOfWeek": "monday"}}}}
    if grain == "quarter":
        return {"$concat": [{"$substrBytes": [day_expr, 0, 4]}, "-Q", {"$toString": {"$ceil": {
            "$divide": [{"$toInt": {"$substrBytes": [day_expr, 5, 2]}}, 3]}}}]}
    raise AnalyticsError(f"time_grain tidak dikenal: {grain}")


def _match_filters(src: str, filters: List[Dict[str, Any]], warnings: List[str]) -> Dict[str, Any]:
    fmap = cat.SOURCE_DIMS[src]
    q: Dict[str, Any] = {}
    for f in filters or []:
        dim, vals = f.get("dimension"), [str(v) for v in (f.get("values") or [])]
        if dim not in fmap:
            warnings.append(f"Saringan '{cat.DIMENSIONS.get(dim, dim)}' tidak berlaku untuk sebagian metrik dan diabaikan di sana.")
            continue
        if dim == "line_code":
            vals = [v.lower() for v in vals]
        q.setdefault("$and", []).append({fmap[dim]: {"$in" if f.get("op") != "not_in" else "$nin": vals}})
    return q


async def _group(coll: str, pre: List[Dict[str, Any]], dims: List[str], src: str, grain_expr: Any,
                 accs: Dict[str, Any], post: Optional[List[Dict[str, Any]]] = None) -> Dict[Key, Dict[str, float]]:
    fmap = cat.SOURCE_DIMS[src]
    gid: Dict[str, Any] = {f"d{i}": f"${fmap[d]}" for i, d in enumerate(dims)}
    if grain_expr is not None:
        gid["t"] = grain_expr
    pipe = pre + [{"$group": {"_id": gid, **accs}}] + (post or [])
    out: Dict[Key, Dict[str, float]] = {}
    async for r in db[coll].aggregate(pipe, maxTimeMS=MAX_TIME_MS):
        _id = r.pop("_id")
        key = tuple(_id.get(f"d{i}") or "" for i in range(len(dims))) + ((_id.get("t") or "",) if grain_expr is not None else ())
        out[key] = r
    return out


# ── sumber ────────────────────────────────────────────────────────────────────
_FACT_ACC = {"net": ("net", {"$sum": "$net_alloc"}), "gross": ("gross", {"$sum": "$gross"}),
             "discount": ("discount", {"$sum": "$discount"}), "ppn": ("ppn", {"$sum": "$ppn_alloc"}),
             "qty": ("qty", {"$sum": "$qty_base"}), "rolls": ("rolls", {"$sum": "$rolls"}),
             "orders": ("orders", {"$addToSet": "$so_id"}), "customers": ("customers", {"$addToSet": "$customer_id"})}


async def _src_fact(metrics, dims, grain, p: Period, filters, sc: Scope, w, include_samples, samples_only=False):
    match: Dict[str, Any] = {"entity_id": {"$in": sc.entity_ids}, "date_wib": {"$gte": p.date_from.isoformat(),
                                                                             "$lte": p.date_to.isoformat()},
                             "is_live": True}
    if samples_only:
        match["is_sample"] = True
    elif not include_samples:
        match["is_sample"] = False
    if sc.sales_only:
        match["sales_id"] = sc.sales_only
    match.update(sc.line_q)
    fq = _match_filters("fact", filters, w)
    pre = [{"$match": {**match, **({"$and": fq["$and"]} if fq else {})}}]
    need = set()
    for m in metrics:
        agg = cat.METRICS[m]["agg"]
        need |= {"net", "cost"} if agg == "margin" else {agg}
    accs = {k: v for a, (k, v) in _FACT_ACC.items() if a in need}
    if "cost" in need:
        accs["cost"] = {"$sum": "$cost"}
    res = await _group("fact_sales_lines", pre, dims, "fact", _grain("$date_wib", grain) if grain else None, accs)
    out = {}
    for k, r in res.items():
        row = {}
        for m in metrics:
            agg = cat.METRICS[m]["agg"]
            if agg == "margin":
                row[m] = r["net"] - r["cost"]
            elif agg in ("orders", "customers"):
                row[m] = len(r[agg])
            else:
                row[m] = r[agg]
        out[k] = row
    return out


async def _src_fact_new(metrics, dims, grain, p: Period, filters, sc: Scope, w, include_samples):
    match: Dict[str, Any] = {"entity_id": {"$in": sc.entity_ids}, "is_live": True, "is_sample": False}
    if sc.sales_only:
        match["sales_id"] = sc.sales_only
    fq = _match_filters("fact", filters, w)
    fmap = cat.SOURCE_DIMS["fact"]
    first = {fmap[d]: {"$first": f"${fmap[d]}"} for d in dims if d != "customer"}
    pipe = [{"$match": {**match, **({"$and": fq["$and"]} if fq else {})}}, {"$sort": {"date_wib": 1}},
            {"$group": {"_id": "$customer_id", "first": {"$first": "$date_wib"}, **first}},
            {"$match": {"first": {"$gte": p.date_from.isoformat(), "$lte": p.date_to.isoformat()}}},
            {"$addFields": {"customer_id": "$_id"}}]
    res = await _group("fact_sales_lines", pipe, dims, "fact", _grain("$first", grain) if grain else None,
                       {"n": {"$sum": 1}})
    return {k: {"new_customers": r["n"]} for k, r in res.items()}


async def _customer_clause(sc: Scope) -> Dict[str, Any]:
    return {"customer_id": {"$in": await sc.owned_customers()}} if sc.sales_only else {}


async def _src_returns(metrics, dims, grain, p, filters, sc, w, _s):
    fq = _match_filters("returns", filters, w)
    pre = [{"$match": {"entity_id": {"$in": sc.entity_ids}, "status": {"$in": ["issued", "posted"]},
                       "created_at": p.mongo_range(), **await _customer_clause(sc),
                       **await _line_products(sc, "lines.product_id")}}]
    val = "$net_amount"
    if "product" in dims or any(f.get("dimension") == "product" for f in filters or []):
        # Nilai nota dibagi rata ke baris produknya (nota kredit tidak menyimpan nilai per baris).
        pre += [{"$addFields": {"_n": {"$max": [{"$size": {"$ifNull": ["$lines", []]}}, 1]}}},
                {"$unwind": {"path": "$lines", "preserveNullAndEmptyArrays": True}},
                {"$addFields": {"product_id": "$lines.product_id"}}]
        val = {"$divide": ["$net_amount", "$_n"]}
    pre.append({"$match": fq})
    res = await _group("credit_notes", pre, dims, "returns", _grain(_wib_day("$created_at"), grain) if grain else None,
                       {"v": {"$sum": val}})
    return {k: {"returns_value": r["v"]} for k, r in res.items()}


async def _src_journal(metrics, dims, grain, p, filters, sc, w, _s):
    fq = _match_filters("journal", filters, w)
    pre = [{"$match": {"entity_id": {"$in": sc.entity_ids}, "status": "posted", "date": p.mongo_range(), **fq}},
           {"$unwind": "$lines"}, {"$match": {"lines.account_code": cat.REVENUE_ACCOUNT}}]
    res = await _group("journal_entries", pre, dims, "journal", _grain(_wib_day("$date"), grain) if grain else None,
                       {"v": {"$sum": {"$subtract": [{"$ifNull": ["$lines.credit", 0]}, {"$ifNull": ["$lines.debit", 0]}]}}})
    return {k: {"recognized_revenue": r["v"]} for k, r in res.items()}


async def _src_targets(metrics, dims, grain, p: Period, filters, sc, w, _s):
    months = sorted({(p.date_from + timedelta(days=i)).strftime("%Y-%m") for i in range(p.days)})
    if p.date_from.day != 1 or (p.date_to + timedelta(days=1)).day != 1:
        w.append("Target penjualan adalah target bulanan penuh; periode tidak mencakup bulan utuh.")
    match: Dict[str, Any] = {"entity_id": {"$in": sc.entity_ids}, "period_type": "month", "period": {"$in": months}}
    if sc.sales_only:
        match["sales_id"] = sc.sales_only
    fq = _match_filters("targets", filters, w)
    g = None
    if grain:
        if grain in ("day", "week"):
            w.append("Target hanya tersedia per bulan.")
        g = _grain({"$concat": ["$period", "-01"]}, "month" if grain in ("day", "week") else grain)
    res = await _group("sales_targets", [{"$match": {**match, **fq}}], dims, "targets", g,
                       {"v": {"$sum": "$target_sales_amount"}})
    return {k: {"sales_target": r["v"]} for k, r in res.items()}


async def _src_collections(metrics, dims, grain, p, filters, sc, w, _s):
    fq = _match_filters("collections", filters, w)
    pre = [{"$match": {"entity_id": {"$in": sc.entity_ids}, "status": "posted", "receipt_date": p.mongo_range(),
                       **await _customer_clause(sc)}}]
    if "sales_person" in dims or any(f.get("dimension") == "sales_person" for f in filters or []):
        # Uang masuk dikreditkan ke sales penanggung jawab pelanggan.
        pre += [{"$lookup": {"from": "customers", "localField": "customer_id", "foreignField": "id", "as": "_c"}},
                {"$addFields": {"sales_id": {"$ifNull": [{"$first": "$_c.assigned_sales_id"}, ""]}}}]
    pre.append({"$match": fq})
    res = await _group("ar_receipts", pre, dims, "collections",
                       _grain(_wib_day("$receipt_date"), grain) if grain else None, {"v": {"$sum": "$amount"}})
    return {k: {"collections_amount": r["v"]} for k, r in res.items()}


async def _src_ar(metrics, dims, grain, p, filters, sc: Scope, w, _s):
    from services.ar_aging_service import aging_report, BUCKET_KEYS
    from services.analytics_snapshots import snapshot_for
    recs: List[Dict[str, Any]] = []
    snap = await snapshot_for("fact_ar_daily", p.date_to)
    if snap:
        q = {"date": snap, "entity_id": {"$in": sc.entity_ids}, **({"sales_id": sc.sales_only} if sc.sales_only else {})}
        recs = await db.fact_ar_daily.find(q, {"_id": 0, "date": 0}).to_list(50000)
        w.append(f"Posisi piutang per {snap} dari snapshot harian 23.55 WIB.")
    if not snap and p.date_to < now_wib().date():   # KN-E36 — jangan diam-diam memakai posisi kini
        w.append(f"Snapshot piutang per {p.date_to.isoformat()} belum ada — angka di bawah adalah "
                 "POSISI HARI INI, bukan posisi akhir periode yang diminta.")
    for ent in ([] if snap else sc.entity_ids):
        rep = await aging_report(ent, sc.sales_only)
        for r in rep.get("customers") or []:
            for b in BUCKET_KEYS:
                amt = float(r.get(b) or 0)
                if amt:
                    recs.append({"entity_id": ent, "customer_id": r.get("customer_id") or "",
                                 "sales_id": r.get("assigned_sales_id") or "", "aging_bucket": b,
                                 "ar_outstanding": amt, "ar_overdue": amt if b != "current" else 0.0})
    fmap = cat.SOURCE_DIMS["ar"]
    for f in filters or []:
        if f.get("dimension") not in fmap:
            w.append(f"Saringan '{cat.DIMENSIONS.get(f.get('dimension'), f.get('dimension'))}' tidak berlaku untuk piutang.")
            continue
        vals, fld = set(map(str, f.get("values") or [])), fmap[f["dimension"]]
        recs = [r for r in recs if (r[fld] in vals) == (f.get("op") != "not_in")]
    if grain:
        w.append("Piutang adalah posisi saat ini; tidak dipecah per waktu.")
    out: Dict[Key, Dict[str, float]] = {}
    for r in recs:
        k = tuple(r[fmap[d]] for d in dims) + (("",) if grain else ())
        row = out.setdefault(k, {m: 0.0 for m in metrics})
        for m in metrics:
            row[m] += r[m]
    return out


async def _src_ap(metrics, dims, grain, p: Period, filters, sc, w, _s):
    fq = _match_filters("ap", filters, w)
    remaining = {"$subtract": [{"$ifNull": ["$grand_total", 0]}, {"$ifNull": ["$amount_paid", 0]}]}
    due_field = {"$ifNull": ["$due_date", "$bill_date"]}
    pre = [{"$match": {"entity_id": {"$in": sc.entity_ids},
                       "status": {"$nin": ["draft", "cancelled", "void", "paid", "rejected"]}, **fq}},
           {"$addFields": {"_rem": remaining, "_due": due_field}}, {"$match": {"_rem": {"$gt": 0.005}}}]
    if grain:
        w.append("Hutang adalah posisi saat ini; tidak dipecah per waktu.")
    if p.date_to < now_wib().date():   # KN-E36 — hutang tidak punya snapshot historis
        w.append("Hutang selalu POSISI HARI INI; periode masa lalu tidak diterapkan.")
    res = await _group("vendor_bills", pre, dims, "ap", "" if grain else None, {
        "outstanding": {"$sum": "$_rem"},
        "due": {"$sum": {"$cond": [{"$lt": ["$_due", p.end_utc]}, "$_rem", 0]}}})
    return {k: {m: r[cat.METRICS[m]["agg"]] for m in metrics} for k, r in res.items()}


async def _src_purchases(metrics, dims, grain, p, filters, sc, w, _s):
    fq = _match_filters("purchases", filters, w)
    pre = [{"$match": {"entity_id": {"$in": sc.entity_ids}, "status": {"$nin": list(cat.PO_DEAD)},
                       "created_at": p.mongo_range(), **fq}}]
    res = await _group("purchase_orders", pre, dims, "purchases",
                       _grain(_wib_day("$created_at"), grain) if grain else None, {
                           "value": {"$sum": {"$subtract": [{"$ifNull": ["$grand_total", 0]}, {"$ifNull": ["$ppn_amount", 0]}]}},
                           "count": {"$sum": 1}})
    return {k: {m: r[cat.METRICS[m]["agg"]] for m in metrics} for k, r in res.items()}


async def _line_products(sc, field: str = "product_id") -> Dict[str, Any]:
    """KN-E42 — pagar lini lewat produk untuk sumber yang tidak menyimpan line_code."""
    if not sc.line_q:
        return {}
    return {field: {"$in": await db.products.distinct("id", sc.line_q)}}


async def _src_received(metrics, dims, grain, p, filters, sc, w, _s):
    fq = _match_filters("received", filters, w)
    pre = [{"$match": {"owner_entity_id": {"$in": sc.entity_ids}, "movement_type": {"$in": list(cat.RECEIPT_MOVEMENTS)},
                       "timestamp": p.mongo_range(), **fq, **await _line_products(sc)}}]
    res = await _group("inventory_movements", pre, dims, "received",
                       _grain(_wib_day("$timestamp"), grain) if grain else None, {"qty": {"$sum": "$quantity"}})
    return {k: {"received_qty": r["qty"]} for k, r in res.items()}


def _age_bucket_expr() -> Dict[str, Any]:
    since = {"$dateFromString": {"dateString": {"$ifNull": ["$acquired.date", "$created_at"]}, "onError": None, "onNull": None}}
    days = {"$dateDiff": {"startDate": since, "endDate": "$$NOW", "unit": "day"}}
    return {"$switch": {"branches": [{"case": {"$lte": [days, 30]}, "then": "0-30"},
                                     {"case": {"$lte": [days, 60]}, "then": "31-60"},
                                     {"case": {"$lte": [days, 90]}, "then": "61-90"},
                                     {"case": {"$lte": [days, 180]}, "then": "91-180"}], "default": ">180"}}


async def _src_stock(metrics, dims, grain, p, filters, sc: Scope, w, _s):
    from services.analytics_snapshots import snapshot_for
    fq = _match_filters("stock", filters, w)
    aged = "stock_age_bucket" in dims or any(f.get("dimension") == "stock_age_bucket" for f in filters or [])
    snap = await snapshot_for("fact_stock_daily", p.date_to)
    if snap and not aged:
        w.append(f"Posisi stok per {snap} dari snapshot harian 23.55 WIB.")
        res = await _group("fact_stock_daily", [{"$match": {"date": snap, "owner_entity_id": {"$in": sc.entity_ids}, **sc.line_q, **fq}}],
                           dims, "stock", "" if grain else None, {k: {"$sum": f"${k}"} for k in ("qty", "rolls", "value", "avail", "reserved")})
        return {k: {m: r[cat.METRICS[m]["agg"]] for m in metrics} for k, r in res.items()}
    if snap and aged:
        w.append("Umur stok hanya tersedia untuk posisi saat ini; snapshot masa lalu tidak menyimpan umur.")
    elif not snap and p.date_to < now_wib().date():   # KN-E36
        w.append(f"Snapshot stok per {p.date_to.isoformat()} belum ada — angka di bawah adalah "
                 "POSISI HARI INI, bukan posisi akhir periode yang diminta.")
    pre = [{"$match": {"owner_entity_id": {"$in": sc.entity_ids}, "status": {"$in": list(cat.PHYSICAL_ROLL_STATUSES)},
                       **sc.line_q, **fq}}]
    if "stock_age_bucket" in dims or any(f.get("dimension") == "stock_age_bucket" for f in filters or []):
        pre.insert(0, {"$addFields": {"stock_age_bucket": _age_bucket_expr()}})
    if grain:
        w.append("Stok adalah posisi saat ini; tidak dipecah per waktu.")
    rem = {"$ifNull": ["$length_remaining", 0]}
    res = await _group("inventory_rolls", pre, dims, "stock", "" if grain else None, {
        "qty": {"$sum": rem}, "rolls": {"$sum": 1},
        "value": {"$sum": {"$multiply": [rem, {"$ifNull": ["$unit_cost", 0]}]}},
        "avail": {"$sum": {"$cond": [{"$eq": ["$status", "available"]}, rem, 0]}},
        "reserved": {"$sum": {"$cond": [{"$in": ["$status", list(cat.RESERVED_ROLL_STATUSES)]}, rem, 0]}}})
    return {k: {m: r[cat.METRICS[m]["agg"]] for m in metrics} for k, r in res.items()}


async def _src_fact_sample(metrics, dims, grain, p, filters, sc, w, s):
    return await _src_fact(metrics, dims, grain, p, filters, sc, w, s, samples_only=True)


SOURCES = {"fact": _src_fact, "fact_new": _src_fact_new, "fact_sample": _src_fact_sample, "returns": _src_returns,
           "journal": _src_journal, "targets": _src_targets, "collections": _src_collections, "ar": _src_ar,
           "ap": _src_ap, "purchases": _src_purchases, "received": _src_received, "stock": _src_stock}


# ── perakitan ─────────────────────────────────────────────────────────────────
async def _run(base: List[str], dims, grain, p, filters, sc, w, include_samples) -> Dict[Key, Dict[str, float]]:
    by_src: Dict[str, List[str]] = {}
    for m in base:
        by_src.setdefault(cat.METRICS[m]["source"], []).append(m)
    merged: Dict[Key, Dict[str, float]] = {}
    for src, ms in by_src.items():
        part = await SOURCES[src](ms, dims, grain, p, filters, sc, w, include_samples)
        for k, vals in part.items():
            merged.setdefault(k, {}).update(vals)
    return merged


def _derive(row: Dict[str, float]) -> None:
    def ratio(a, b, pct=False):
        if a not in row or b not in row:
            return None
        return (row[a] / row[b] * (100 if pct else 1)) if row[b] else None
    row["avg_order_value"] = ratio("net_sales", "orders_count")
    row["gross_margin_pct"] = ratio("gross_margin", "net_sales", True)
    row["target_achievement_pct"] = ratio("net_sales", "sales_target", True)


def _rnd(m: str, v: Any) -> Any:
    if v is None:
        return None
    unit = cat.METRICS[m]["unit"] if m in cat.METRICS else "idr"
    return round(float(v), {"idr": 2, "qty": 3, "pct": 2, "count": 3}[unit])


async def _labels(dim: str, ids: List[str]) -> Dict[str, str]:
    ids = [i for i in ids if i]
    if not ids:
        return {}
    spec = {"customer": ("customers", "name"), "product": ("products", "name"), "sales_person": ("users", "name"),
            "supplier": ("suppliers", "name"), "warehouse": ("warehouses", "name"),
            "entity": ("business_entities", "short_name")}[dim]
    out = {d["id"]: d.get(spec[1]) or d.get("legal_name") or d["id"] async for d in db[spec[0]].find(
        {"id": {"$in": ids}}, {"_id": 0, "id": 1, spec[1]: 1, "legal_name": 1})}
    if dim == "supplier":
        missing = [i for i in ids if i not in out]
        if missing:
            async for d in db.makloons.find({"id": {"$in": missing}}, {"_id": 0, "id": 1, "name": 1}):
                out[d["id"]] = d.get("name") or d["id"]
    return out


_EMPTY = {"sales_person": "Tanpa sales", "customer": "Tanpa pelanggan", "category": "Tanpa kategori",
          "line_code": "Tanpa lini", "customer_city": "Tanpa kota"}


def _validate(args: Dict[str, Any]) -> Tuple[List[str], List[str], Optional[str]]:
    metrics = list(dict.fromkeys(args.get("metrics") or []))
    dims = list(dict.fromkeys(args.get("group_by") or []))
    grain = args.get("time_grain") or None
    if not 1 <= len(metrics) <= cat.MAX_METRICS:
        raise AnalyticsError(f"Pilih 1–{cat.MAX_METRICS} metrik.")
    if len(dims) > cat.MAX_DIMS:
        raise AnalyticsError(f"Maksimal {cat.MAX_DIMS} dimensi.")
    bad = [m for m in metrics if m not in cat.METRICS]
    if bad:
        raise AnalyticsError(f"Metrik tidak dikenal: {', '.join(bad)}")
    if "date" in dims:
        dims.remove("date")
        grain = grain or "day"
    for m in metrics:
        sup = cat.supported_dims(m)
        miss = [d for d in dims if d not in sup] + (["date"] if grain and "date" not in sup and cat.METRICS[m]["source"] not in ("ar", "ap", "stock") else [])
        if miss:
            raise AnalyticsError(
                f"Metrik {m} tidak mendukung dimensi {', '.join(miss)}. Dimensi yang didukung: {', '.join(sorted(sup))}.")
    return metrics, dims, grain


async def _gate(metrics: List[str], sc: Scope) -> Tuple[List[str], List[str]]:
    ok, denied = [], []
    for m in metrics:
        meta = cat.METRICS[m]
        if (meta["requires"] and not role_may(sc.policy, meta["requires"], sc.role)) or not await sc.allowed(meta["perms"]):
            denied.append(m)
        else:
            ok.append(m)
    return ok, denied


def _base_metrics(metrics: List[str]) -> List[str]:
    base: List[str] = []
    for m in metrics:
        for b in cat.DERIVED_NEEDS.get(m, (m,)):
            if b not in base:
                base.append(b)
    return base


async def _compute(metrics, dims, grain, p, filters, sc, w, include_samples):
    base = _base_metrics(metrics)
    rows = await _run(base, dims, grain, p, filters, sc, w, include_samples)
    tot = (await _run(base, [], None, p, filters, sc, w, include_samples)).get((), {})
    for r in list(rows.values()) + [tot]:
        _derive(r)
    return rows, tot


def _columns(dims, grain, metrics, compare, shares) -> List[Dict[str, Any]]:
    cols = [{"key": d, "label": cat.DIMENSIONS[d], "type": "dimension", "unit": ""} for d in dims]
    if grain:
        cols.insert(0, {"key": "period", "label": {"day": "Tanggal", "week": "Minggu", "month": "Bulan",
                                                   "quarter": "Kuartal", "year": "Tahun"}[grain],
                        "type": "time", "unit": grain})
    for m in metrics:
        meta = cat.METRICS[m]
        cols.append({"key": m, "label": meta["label"], "type": "metric", "unit": meta["unit"]})
        if compare:
            cols += [{"key": f"{m}_prev", "label": f"{meta['label']} (pembanding)", "type": "metric", "unit": meta["unit"]},
                     {"key": f"{m}_delta", "label": f"Selisih {meta['label'].lower()}", "type": "delta", "unit": meta["unit"]},
                     {"key": f"{m}_delta_pct", "label": "Perubahan %", "type": "delta_pct", "unit": "pct"}]
        if shares and meta["additive"] and meta["unit"] != "pct":
            cols.append({"key": f"{m}_share", "label": f"Pangsa {meta['label'].lower()}", "type": "share", "unit": "pct"})
    return cols


def _delta(cur, prev):
    if cur is None and prev is None:
        return None, None
    c, pv = cur or 0.0, prev or 0.0
    return c - pv, ((c - pv) / abs(pv) * 100) if pv else None


async def save_result(result: Dict[str, Any], full_rows: List[Dict[str, Any]], tool: str, args: Dict[str, Any],
                      user: Dict[str, Any], session_id: Optional[str]) -> None:
    global _ttl_ready
    if not _ttl_ready:
        await db.ai_results.create_index("expires_at", expireAfterSeconds=0)
        await db.ai_results.create_index("result_id", unique=True)
        _ttl_ready = True
    now = datetime.now(timezone.utc)
    await db.ai_results.insert_one({
        "result_id": result["result_id"], "session_id": session_id or "", "user_id": user.get("id"), "tool": tool,
        "args": args, "title": result.get("title"), "columns": result["columns"], "rows": full_rows[:cat.ROW_STORE_LIMIT],
        "totals": result.get("totals"), "compare": result.get("compare"), "period": result.get("period"),
        "definition": result.get("definition"), "created_at": now_iso(), "expires_at": now + timedelta(days=30)})


async def query_metrics(args: Dict[str, Any], user: Dict[str, Any], ctx: Any,
                        session_id: Optional[str] = None, today=None) -> Dict[str, Any]:
    metrics, dims, grain = _validate(args)
    entity_scope = args.get("entity_scope") or "active"
    sc = await build_scope(user, ctx, entity_scope)
    if entity_scope == "per_entity" and "entity" not in dims:
        if len(dims) >= cat.MAX_DIMS:
            raise AnalyticsError("per_entity menambah dimensi entitas; kurangi dimensi lain.")
        dims.insert(0, "entity")
    warnings: List[str] = []
    try:
        p = period_from_args(args.get("period"), today=today)
    except ValueError as exc:
        raise AnalyticsError(str(exc)) from exc
    cmp_mode = args.get("compare") or "none"
    cp = compare_period(p, cmp_mode)
    shown, denied = await _gate(metrics, sc)
    if not shown:
        raise AnalyticsError("Semua metrik yang diminta tidak tersedia untuk peran Anda: " + ", ".join(denied))
    if any(m in cat.QTY_METRICS for m in shown) and not ({"product", "unit"} & set(dims)):
        if not all("unit" in cat.supported_dims(m) for m in shown):
            raise AnalyticsError("Qty tidak boleh dijumlah lintas satuan: minta metrik qty terpisah dari metrik lain, "
                                 "atau kelompokkan per produk.")
        if len(dims) >= cat.MAX_DIMS:
            raise AnalyticsError("Qty perlu dipisah per satuan; kurangi satu dimensi.")
        dims.append("unit")
        warnings.append("Qty dipisah per satuan (yard, meter, kg tidak dijumlah).")
    if any(cat.METRICS[m]["source"].startswith("fact") for m in shown):
        asof = await facts.ensure_fresh()
        if asof and p.date_to >= now_wib().date():
            warnings.append(f"Data penjualan hingga {asof} WIB.")
    include_samples = bool(args.get("include_samples"))
    rows, tot = await _compute(shown, dims, grain, p, args.get("filters") or [], sc, warnings, include_samples)
    prows, ptot = ({}, {})
    if cp:
        prows, ptot = await _compute(shown, dims, grain, cp, args.get("filters") or [], sc, warnings, include_samples)
    if cp and grain:
        warnings.append("Pembanding per waktu ditampilkan sebagai total; baris tren tidak dipasangkan.")
        prows = {}
    keys = list(rows.keys()) + [k for k in prows if k not in rows and not grain]
    labels = {d: await _labels(d, list({k[i] for k in keys})) for i, d in enumerate(dims) if d in cat.NAMED_DIMS}
    shares = bool(dims or grain)
    # KN-E34 — baris sudah per satuan; total/pembanding/porsi qty juga tidak boleh lintas satuan.
    ui = dims.index("unit") if "unit" in dims else None
    mixed = ui is not None and len({k[ui] for k in keys}) > 1
    unit_tot: Dict[Any, Dict[str, float]] = {}
    if mixed:
        for k, cur in rows.items():
            for m in shown:
                if m in cat.QTY_METRICS:
                    unit_tot.setdefault(k[ui], {})[m] = unit_tot.get(k[ui], {}).get(m, 0.0) + float(cur.get(m) or 0)
        warnings.append("Total qty tidak ditampilkan karena lintas satuan; porsi dihitung per satuan.")
    out_rows: List[Dict[str, Any]] = []
    for k in keys:
        cur, prev = rows.get(k, {}), prows.get(k, {})
        r: Dict[str, Any] = {}
        for i, d in enumerate(dims):
            raw = k[i]
            if d in labels:
                r[f"{d}_id"] = raw
                r[d] = labels[d].get(raw) or (_EMPTY.get(d) if not raw else raw)
            else:
                r[d] = raw or _EMPTY.get(d, "(kosong)")
        if grain:
            r["period"] = k[len(dims)]
        for m in shown:
            r[m] = _rnd(m, cur.get(m))
            if cp:
                r[f"{m}_prev"] = _rnd(m, prev.get(m))
                dv, dp = _delta(cur.get(m), prev.get(m))
                r[f"{m}_delta"], r[f"{m}_delta_pct"] = _rnd(m, dv), (round(dp, 2) if dp is not None else None)
            if shares and cat.METRICS[m]["additive"] and cat.METRICS[m]["unit"] != "pct":
                t = (unit_tot.get(k[ui], {}).get(m) if mixed and m in cat.QTY_METRICS else tot.get(m)) or 0
                r[f"{m}_share"] = round(cur[m] / t * 100, 2) if t and cur.get(m) is not None else None
        out_rows.append(r)
    sort = args.get("sort") or {}
    sort_by = sort.get("by") or ("period" if grain else shown[0])
    if out_rows and sort_by not in out_rows[0]:
        sort_by = "period" if grain else shown[0]
    desc = (sort.get("direction") or ("asc" if sort_by == "period" else "desc")) == "desc"
    present = [x for x in out_rows if x.get(sort_by) is not None]
    present.sort(key=lambda x: x[sort_by], reverse=desc)
    out_rows = present + [x for x in out_rows if x.get(sort_by) is None]
    limit = args.get("limit") or (10 if dims and not grain else cat.ROW_RETURN_LIMIT)
    limit = max(1, min(int(limit), cat.ROW_RETURN_LIMIT))
    no_tot = {m for m in shown if mixed and m in cat.QTY_METRICS}
    totals = {m: (None if m in no_tot else _rnd(m, tot.get(m))) for m in shown}
    compare = None
    if cp:
        compare = {"period": cp.to_dict(), "totals": {m: (None if m in no_tot else _rnd(m, ptot.get(m))) for m in shown},
                   "delta": {}, "delta_pct": {}}
        for m in shown:
            if m in no_tot:
                compare["delta"][m] = compare["delta_pct"][m] = None
                continue
            dv, dp = _delta(tot.get(m), ptot.get(m))
            compare["delta"][m], compare["delta_pct"][m] = _rnd(m, dv), (round(dp, 2) if dp is not None else None)
    if denied:
        warnings.append("Sebagian metrik disembunyikan karena hak akses: " + ", ".join(denied))
    result = {
        "result_id": "r_" + uuid.uuid4().hex[:10],
        "title": ", ".join(cat.METRICS[m]["label"] for m in shown) + (
            " per " + ", ".join(cat.DIMENSIONS[d].lower() for d in dims) if dims else ""),
        "definition": " · ".join(f"{cat.METRICS[m]['label']}: {cat.METRICS[m]['definition']}" for m in shown),
        "period": p.to_dict(),
        "entity_scope": {"mode": entity_scope, "entity_ids": sc.entity_ids},
        "columns": _columns(dims, grain, shown, bool(cp), shares),
        "rows": out_rows[:limit], "totals": totals, "compare": compare, "row_count": len(out_rows),
        "truncated": len(out_rows) > limit, "warnings": list(dict.fromkeys(warnings)), "denied": denied,
        "source": cat.CATALOG_VERSION,
    }
    await save_result(result, out_rows, "query_metrics", args, user, session_id)
    return result


async def analyze_change(args: Dict[str, Any], user: Dict[str, Any], ctx: Any,
                         session_id: Optional[str] = None, today=None) -> Dict[str, Any]:
    """Kontribusi perubahan satu metrik per anggota dimensi. Σ kontribusi (+ "lainnya") = perubahan total."""
    metric, dim = args.get("metric"), args.get("dimension")
    if metric not in cat.METRICS or dim not in cat.DIMENSIONS or dim == "date":
        raise AnalyticsError("Metrik/dimensi analisis tidak dikenal.")
    if dim not in cat.supported_dims(metric):
        raise AnalyticsError(f"Metrik {metric} tidak mendukung dimensi {dim}.")
    sc = await build_scope(user, ctx, "active")
    shown, denied = await _gate([metric], sc)
    if not shown:
        raise AnalyticsError(f"Metrik {metric} tidak tersedia untuk peran Anda.")
    try:
        p = period_from_args(args.get("period"), today=today)
    except ValueError as exc:
        raise AnalyticsError(str(exc)) from exc
    cp = compare_period(p, args.get("compare_to") or "previous_period")
    if cp is None:   # KN-E44 — compare_to "none" dulu → 500
        raise AnalyticsError("Analisis perubahan butuh periode pembanding (mis. periode sebelumnya / tahun lalu).")
    if metric in cat.QTY_METRICS and dim not in ("product", "unit") \
            and not any(f.get("dimension") == "unit" and len(f.get("values") or []) == 1 for f in args.get("filters") or []):
        # KN-E34 — perubahan qty tidak boleh menjumlah yard + meter + kg.
        raise AnalyticsError("Perubahan qty harus per produk atau disaring ke SATU satuan (filter unit).")
    warnings: List[str] = []
    if cat.METRICS[metric]["source"].startswith("fact"):
        await facts.ensure_fresh()
    cur, tot = await _compute([metric], [dim], None, p, args.get("filters") or [], sc, warnings, False)
    prev, ptot = await _compute([metric], [dim], None, cp, args.get("filters") or [], sc, warnings, False)
    if not cat.METRICS[metric]["additive"]:
        warnings.append("Metrik ini tidak aditif; jumlah kontribusi bisa berbeda dari perubahan total.")
    keys = set(cur) | set(prev)
    labels = await _labels(dim, [k[0] for k in keys]) if dim in cat.NAMED_DIMS else {}
    total_delta = (tot.get(metric) or 0) - (ptot.get(metric) or 0)
    items = []
    for k in keys:
        c, pv = cur.get(k, {}).get(metric) or 0.0, prev.get(k, {}).get(metric) or 0.0
        items.append({dim: labels.get(k[0]) or k[0] or _EMPTY.get(dim, "(kosong)"), f"{dim}_id": k[0],
                      "value": _rnd(metric, c), "value_prev": _rnd(metric, pv), "delta": c - pv,
                      "delta_pct": round((c - pv) / abs(pv) * 100, 2) if pv else None})
    top_n = max(1, min(int(args.get("top_n") or 5), 50))
    pos = sorted([i for i in items if i["delta"] > 0], key=lambda i: -i["delta"])[:top_n]
    neg = sorted([i for i in items if i["delta"] < 0], key=lambda i: i["delta"])[:top_n]
    shown_rows = pos + neg
    other = total_delta - sum(i["delta"] for i in shown_rows)
    if abs(other) > 0.005:
        shown_rows.append({dim: "Lainnya", f"{dim}_id": "", "value": None, "value_prev": None, "delta": other,
                           "delta_pct": None})
    for i in shown_rows:
        i["contribution_pct"] = round(i["delta"] / abs(total_delta) * 100, 2) if total_delta else None
        i["delta"] = _rnd(metric, i["delta"])
    meta = cat.METRICS[metric]
    result = {
        "result_id": "r_" + uuid.uuid4().hex[:10],
        "title": f"Penyebab perubahan {meta['label'].lower()} per {cat.DIMENSIONS[dim].lower()}",
        "definition": f"{meta['label']}: {meta['definition']}", "period": p.to_dict(),
        "entity_scope": {"mode": "active", "entity_ids": sc.entity_ids},
        "columns": [{"key": dim, "label": cat.DIMENSIONS[dim], "type": "dimension", "unit": ""},
                    {"key": "value", "label": meta["label"], "type": "metric", "unit": meta["unit"]},
                    {"key": "value_prev", "label": f"{meta['label']} (pembanding)", "type": "metric", "unit": meta["unit"]},
                    {"key": "delta", "label": "Selisih", "type": "delta", "unit": meta["unit"]},
                    {"key": "delta_pct", "label": "Perubahan %", "type": "delta_pct", "unit": "pct"},
                    {"key": "contribution_pct", "label": "Kontribusi %", "type": "share", "unit": "pct"}],
        "rows": shown_rows, "positive": pos, "negative": neg,
        "totals": {metric: _rnd(metric, tot.get(metric))},
        "compare": {"period": cp.to_dict(), "totals": {metric: _rnd(metric, ptot.get(metric))},
                    "delta": {metric: _rnd(metric, total_delta)},
                    "delta_pct": {metric: round(total_delta / abs(ptot[metric]) * 100, 2) if ptot.get(metric) else None}},
        "row_count": len(items), "truncated": len(items) > len(pos) + len(neg), "warnings": warnings,
        "denied": denied, "source": cat.CATALOG_VERSION,
    }
    await save_result(result, shown_rows, "analyze_change", args, user, session_id)
    return result
