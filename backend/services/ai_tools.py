"""Tanya KN F2.1 — eksekusi 6 tool (Lampiran C). Semua baca-saja, identitas pengguna asli.

Hasil setiap tool/bagian disimpan di `ai_results` (result_id) sehingga grafik/tabel/unduhan
mengambil angka dari server, bukan dari teks model.
"""
from __future__ import annotations

import difflib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from db import db
from core_utils import strip_cost_fields
from dependencies import audit
from services import analytics_catalog as cat
from services import analytics_engine as engine
from services.analytics_time import now_wib, period_from_args
from services.ar_aging_service import _eligible_outstanding, term_days, parse_dt
from services.sales_ownership import apply_scope, assert_may_open

Q_DEFAULT = {"group_by": [], "time_grain": None, "compare": "none", "filters": [],
             "sort": {"by": None, "direction": "desc"}, "limit": None, "include_samples": False,
             "entity_scope": "active"}


def _col(key, label, unit="", typ="metric"):
    return {"key": key, "label": label, "type": typ, "unit": unit}


def _txt(key, label):
    return _col(key, label, "", "dimension")


async def _save(title: str, columns, rows, user, session_id, tool, args, *, period=None, warnings=None,
                definition="", totals=None, denied=None) -> Dict[str, Any]:
    res = {"result_id": "r_" + uuid.uuid4().hex[:10], "title": title, "definition": definition,
           "period": period, "entity_scope": None, "columns": columns, "rows": rows[:cat.ROW_RETURN_LIMIT],
           "totals": totals or {}, "compare": None, "row_count": len(rows),
           "truncated": len(rows) > cat.ROW_RETURN_LIMIT, "warnings": warnings or [], "denied": denied or [],
           "source": cat.CATALOG_VERSION}
    await engine.save_result(res, rows, tool, args, user, session_id)
    return res


# ── list_records ─────────────────────────────────────────────────────────────
_FILTER_FIELDS: Dict[str, Dict[str, str]] = {
    "sales_orders": {"customer": "customer_id", "payment_status": "payment_status", "order_status": "status",
                     "entity": "entity_id", "warehouse": "warehouse_id"},
    "purchase_orders": {"supplier": "supplier_id", "entity": "entity_id", "order_status": "status"},
    "ar_receipts": {"customer": "customer_id", "entity": "entity_id"},
    "customers": {"customer": "id", "customer_city": "city", "customer_segment": "segment"},
    "shipments": {"customer": "customer_id", "entity": "entity_id", "warehouse": "warehouse_id"},
    "credit_notes": {"customer": "customer_id", "entity": "entity_id"},
    "goods_receipts": {"supplier": "supplier_id", "entity": "entity_id", "warehouse": "warehouse_id"},
    "inventory_rolls": {"product": "product_id", "grade": "grade", "dye_lot": "dye_lot",
                        "warehouse": "warehouse_id", "line_code": "line_code", "unit": "unit"},
}

async def _ar_orders(sc: engine.Scope, overdue_only: bool, limit: int,
                     cfilter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    cq: Dict[str, Any] = {"entity_id": {"$in": sc.entity_ids}, **(cfilter or {})}
    if sc.sales_only:
        cq["assigned_sales_id"] = sc.sales_only
    custs = {c["id"]: c async for c in db.customers.find(cq, {"_id": 0})}
    now = datetime.now(timezone.utc)
    out = []
    async for o in db.sales_orders.find({"customer_id": {"$in": list(custs)}}, {"_id": 0, "items": 0, "status_history": 0}):
        amt = _eligible_outstanding(o)
        if amt is None:
            continue
        due = (parse_dt(o.get("created_at")) or now) + timedelta(days=term_days(custs[o["customer_id"]], o))
        late = (now - due).days
        if overdue_only and late <= 0:
            continue
        out.append({"number": o.get("number"), "customer": o.get("customer_name"), "due_date": due.date().isoformat(),
                    "days_overdue": max(late, 0), "outstanding": round(amt, 2), "payment_status": o.get("payment_status")})
    return out


async def list_records(args, user, ctx, session_id=None) -> Dict[str, Any]:
    rt = args.get("record_type")
    sc = await engine.build_scope(user, ctx)
    filters = [f for f in (args.get("filters") or []) if f.get("values")]
    used: set = set()

    def _fq(coll: str) -> Dict[str, Any]:
        """KN-E37 — terapkan `filters` ke kueri; dimensi yang tidak didukung ditolak jujur."""
        fields = _FILTER_FIELDS.get(coll, {})
        out: Dict[str, Any] = {}
        for f in filters:
            fld = fields.get(f["dimension"])
            if not fld:
                continue
            used.add(f["dimension"])
            out[fld] = {"$nin" if f.get("op") == "not_in" else "$in": list(f["values"])}
        return out

    limit = max(1, min(int(args.get("limit") or 20), cat.ROW_RETURN_LIMIT))
    p = period_from_args(args["period"]) if args.get("period") else None
    ents = {"$in": sc.entity_ids}
    rows: List[Dict[str, Any]] = []
    cols: List[Dict[str, Any]] = []
    title = rt
    perm = {"ar_open_items": ("order", "view"), "overdue_invoices": ("order", "view"), "customer_payments": ("ar_receipt", "view"),
            "purchase_orders": ("purchase_order", "view"), "overdue_purchase_orders": ("purchase_order", "view"),
            "vendor_bills_due": ("vendor_bill", "view"), "incoming_goods": ("purchase_order", "view"),
            "goods_receipts": ("goods_receipt", "view"), "shipments": ("order", "view"), "stock_rolls": ("inventory", "view"),
            "low_stock": ("inventory", "view"), "slow_stock": ("inventory", "view"),
            "makloon_orders": ("makloon_order", "view")}.get(rt, ("order", "view"))
    if not await sc.allowed((perm,)):
        raise engine.AnalyticsError("Daftar ini tidak tersedia untuk peran Anda.")
    if rt in ("sales_orders", "open_orders"):
        q: Dict[str, Any] = {"entity_id": ents, "status": {"$nin": ["cancelled", "draft", "expired", "rejected"]}}
        if rt == "open_orders":
            q["status"] = {"$in": ["confirmed", "approved", "reserved", "waiting_stock", "partially_shipped"]}
        if p:
            q["created_at"] = p.mongo_range()
        q.update(_fq("sales_orders"))
        q = apply_scope(q, user)
        async for o in db.sales_orders.find(q, {"_id": 0, "number": 1, "customer_name": 1, "status": 1, "created_at": 1,
                                                "grand_total": 1, "ppn_amount": 1, "payment_status": 1}).sort("created_at", -1).limit(limit):
            rows.append({"number": o.get("number"), "customer": o.get("customer_name"), "status": o.get("status"),
                         "date": str(o.get("created_at"))[:10], "net_sales": round(float(o.get("grand_total") or 0) - float(o.get("ppn_amount") or 0), 2),
                         "payment_status": o.get("payment_status")})
        cols = [_txt("number", "Nomor"), _txt("customer", "Pelanggan"), _txt("status", "Status"), _txt("date", "Tanggal"),
                _col("net_sales", "Nilai bersih", "idr"), _txt("payment_status", "Status bayar")]
        title = "Pesanan terbuka" if rt == "open_orders" else "Pesanan penjualan"
    elif rt in ("ar_open_items", "overdue_invoices"):
        rows = await _ar_orders(sc, rt == "overdue_invoices", limit, _fq("customers"))
        cols = [_txt("number", "Nomor SO"), _txt("customer", "Pelanggan"), _txt("due_date", "Jatuh tempo"),
                _col("days_overdue", "Hari terlambat", "count"), _col("outstanding", "Sisa tagihan", "idr")]
        title = "Piutang lewat jatuh tempo" if rt == "overdue_invoices" else "Piutang terbuka"
    elif rt == "inactive_customers":
        days = int(args.get("days") or 60)
        cut = (now_wib().date() - timedelta(days=days)).isoformat()
        cq: Dict[str, Any] = {"entity_id": ents, **_fq("customers")}
        if sc.sales_only:
            cq["assigned_sales_id"] = sc.sales_only
        last = {r["_id"]: r async for r in db.fact_sales_lines.aggregate([
            {"$match": {"entity_id": ents, "is_live": True, "is_sample": False}}, {"$sort": {"date_wib": 1}},
            {"$group": {"_id": "$customer_id", "last": {"$last": "$date_wib"}, "last_so": {"$last": "$so_id"}}}])}
        async for c in db.customers.find(cq, {"_id": 0, "id": 1, "name": 1, "city": 1}):
            lr = last.get(c["id"])
            if not lr or lr["last"] < cut:
                rows.append({"customer": c.get("name"), "city": c.get("city") or "", "last_order": lr["last"] if lr else "—"})
        cols = [_txt("customer", "Pelanggan"), _txt("city", "Kota"), _txt("last_order", "Pesanan terakhir")]
        title = f"Pelanggan tanpa pesanan > {days} hari"
    elif rt in ("purchase_orders", "overdue_purchase_orders", "incoming_goods"):
        q = {"entity_id": ents, "status": {"$nin": list(cat.PO_DEAD)}, **_fq("purchase_orders")}
        if rt != "purchase_orders":
            q["status"] = {"$in": ["pending", "approved", "receiving", "partially_received", "sent"]}
        today = now_wib().date().isoformat()
        async for po in db.purchase_orders.find(q, {"_id": 0, "po_number": 1, "supplier_name": 1, "status": 1,
                                                     "expected_delivery_date": 1, "grand_total": 1}).limit(500):
            eta = str(po.get("expected_delivery_date") or "")[:10]
            late = (now_wib().date() - datetime.fromisoformat(eta).date()).days if eta else 0
            if rt == "overdue_purchase_orders" and (not eta or eta >= today):
                continue
            if rt == "incoming_goods" and p and not (eta and p.date_from.isoformat() <= eta <= p.date_to.isoformat()):
                continue
            rows.append({"number": po.get("po_number"), "supplier": po.get("supplier_name"), "status": po.get("status"),
                         "eta": eta or "—", "days_late": max(late, 0), "value": po.get("grand_total")})
        cols = [_txt("number", "Nomor PO"), _txt("supplier", "Supplier"), _txt("status", "Status"), _txt("eta", "Perkiraan datang"),
                _col("days_late", "Hari terlambat", "count"), _col("value", "Nilai", "idr")]
        title = {"purchase_orders": "Purchase order", "overdue_purchase_orders": "PO lewat perkiraan kedatangan",
                 "incoming_goods": "Kedatangan terjadwal"}[rt]
    elif rt == "vendor_bills_due":
        horizon = (now_wib().date() + timedelta(days=int(args.get("days_ahead") or 14))).isoformat()
        async for b in db.vendor_bills.find({"entity_id": ents, "status": {"$nin": ["draft", "cancelled", "void", "paid"]}}, {"_id": 0}):
            due = str(b.get("due_date") or b.get("bill_date") or "")[:10]
            rem = float(b.get("grand_total") or 0) - float(b.get("amount_paid") or 0)
            if rem > 0.005 and due <= horizon:
                rows.append({"number": b.get("bill_number"), "supplier": b.get("supplier_name"), "due_date": due, "outstanding": round(rem, 2)})
        cols = [_txt("number", "Nomor tagihan"), _txt("supplier", "Supplier"), _txt("due_date", "Jatuh tempo"), _col("outstanding", "Sisa", "idr")]
        title = "Tagihan supplier jatuh tempo"
    elif rt == "customer_payments":
        q = {"entity_id": ents, "status": "posted", **({"receipt_date": p.mongo_range()} if p else {}),
             **_fq("ar_receipts")}
        if sc.sales_only:
            q["customer_id"] = {"$in": await sc.owned_customers()}
        async for r in db.ar_receipts.find(q, {"_id": 0}).sort("receipt_date", -1).limit(limit):
            rows.append({"number": r.get("number"), "customer": r.get("customer_name"), "date": str(r.get("receipt_date"))[:10], "amount": r.get("amount")})
        cols = [_txt("number", "Nomor"), _txt("customer", "Pelanggan"), _txt("date", "Tanggal"), _col("amount", "Jumlah", "idr")]
        title = "Uang masuk pelanggan"
    elif rt in ("shipments",):
        q = {"entity_id": ents, **({"created_at": p.mongo_range()} if p else {}), **_fq("shipments")}
        if sc.sales_only:   # KN-E31 — hanya pengiriman pesanan milik sales
            own = await db.sales_orders.distinct("id", apply_scope({"entity_id": ents}, user))
            q["$or"] = [{"order_id": {"$in": own}}, {"sales_order_id": {"$in": own}}]
        async for s in db.shipments.find(q, {"_id": 0}).sort("created_at", -1).limit(limit):
            rows.append({"number": s.get("number") or s.get("id"), "order": s.get("order_number") or s.get("so_number"),
                         "status": s.get("status"), "date": str(s.get("created_at"))[:10]})
        cols = [_txt("number", "Pengiriman"), _txt("order", "Pesanan"), _txt("status", "Status"), _txt("date", "Tanggal")]
        title = "Pengiriman"
    elif rt in ("stock_rolls", "slow_stock"):
        q = {"owner_entity_id": ents, "status": {"$in": list(cat.PHYSICAL_ROLL_STATUSES)}, **sc.line_q,
             **_fq("inventory_rolls")}
        if rt == "slow_stock":
            q["created_at"] = {"$lt": (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()}
        async for r in db.inventory_rolls.find(q, {"_id": 0}).sort("created_at", 1).limit(limit):
            rows.append({"roll_no": r.get("roll_no"), "product_id": r.get("product_id"), "dye_lot": r.get("dye_lot"),
                         "grade": r.get("grade"), "qty": r.get("length_remaining"), "unit": r.get("unit"),
                         "received": str((r.get("acquired") or {}).get("date") or r.get("created_at"))[:10]})
        cols = [_txt("roll_no", "Roll"), _txt("product_id", "Produk"), _txt("dye_lot", "Dye lot"), _txt("grade", "Grade"),
                _col("qty", "Sisa", "qty"), _txt("unit", "Satuan"), _txt("received", "Diterima")]
        title = "Stok tidak bergerak > 90 hari" if rt == "slow_stock" else "Roll stok"
    elif rt == "low_stock":
        prods = {p_["id"]: p_ async for p_ in db.products.find({"reorder_point": {"$gt": 0}, **sc.line_q},   # KN-E42
                                                                {"_id": 0, "id": 1, "name": 1, "reorder_point": 1, "base_unit": 1})}
        agg = db.inventory_balances.aggregate([{"$match": {"owner_entity_id": ents, "product_id": {"$in": list(prods)}}},
                                                {"$group": {"_id": "$product_id", "avail": {"$sum": "$available_qty"}}}])
        async for a in agg:
            pr = prods[a["_id"]]
            if a["avail"] < pr["reorder_point"]:
                rows.append({"product": pr.get("name"), "available": a["avail"], "reorder_point": pr["reorder_point"], "unit": pr.get("base_unit")})
        cols = [_txt("product", "Produk"), _col("available", "Tersedia", "qty"), _col("reorder_point", "Titik pesan ulang", "qty"), _txt("unit", "Satuan")]
        title = "Stok di bawah titik pesan ulang"
    elif rt == "makloon_orders":
        async for m in db.makloon_orders.find({"entity_id": ents, "status": {"$nin": ["completed", "cancelled"]}}, {"_id": 0}).limit(limit):
            rows.append({"number": m.get("mko_number"), "material": m.get("material_name"), "status": m.get("status"),
                         "qty": m.get("material_qty"), "unit": m.get("material_unit")})
        cols = [_txt("number", "Nomor MKO"), _txt("material", "Bahan"), _txt("status", "Status"), _col("qty", "Qty bahan", "qty"), _txt("unit", "Satuan")]
        title = "Order makloon berjalan"
    elif rt == "pending_approvals":
        # KN-E31 — SO ikut pagar pemilik sales; PO hanya bila berhak purchase_order.view.
        srcs = [("sales_orders", "number", "Pesanan penjualan",
                 apply_scope({"entity_id": ents, "status": "waiting_approval", **_fq("sales_orders")}, user))]
        if await sc.allowed((("purchase_order", "view"),)):
            srcs.append(("purchase_orders", "po_number", "Purchase order",
                         {"entity_id": ents, "status": "waiting_approval", **_fq("purchase_orders")}))
        for coll, num, lbl, fq in srcs:
            async for d in db[coll].find(fq, {"_id": 0}).limit(limit):
                rows.append({"type": lbl, "number": d.get(num), "party": d.get("customer_name") or d.get("supplier_name"),
                             "value": d.get("grand_total"), "date": str(d.get("created_at"))[:10]})
        cols = [_txt("type", "Jenis"), _txt("number", "Nomor"), _txt("party", "Pihak"), _col("value", "Nilai", "idr"), _txt("date", "Tanggal")]
        title = "Menunggu persetujuan"
    elif rt in ("returns", "goods_receipts"):
        coll, num = ("credit_notes", "number") if rt == "returns" else ("goods_receipts", "number")
        q = {"entity_id": ents, **({"created_at": p.mongo_range()} if p else {}), **_fq(coll)}
        if sc.sales_only and rt == "returns":   # KN-E31 — nota kredit pelanggan milik sales
            q["customer_id"] = {"$in": await sc.owned_customers()}
        async for d in db[coll].find(q, {"_id": 0}).sort("created_at", -1).limit(limit):
            rows.append({"number": d.get(num), "party": d.get("customer_name") or d.get("supplier_name") or "",
                         "status": d.get("status"), "value": d.get("net_amount"), "date": str(d.get("created_at"))[:10]})
        cols = [_txt("number", "Nomor"), _txt("party", "Pihak"), _txt("status", "Status"), _col("value", "Nilai", "idr"), _txt("date", "Tanggal")]
        title = "Retur (nota kredit)" if rt == "returns" else "Kedatangan barang (GRN)"
    else:
        raise engine.AnalyticsError(f"Jenis daftar tidak dikenal: {rt}")
    unused = sorted({f["dimension"] for f in filters} - used)
    if unused:
        raise engine.AnalyticsError(
            f"Saringan {', '.join(unused)} belum didukung untuk daftar '{rt}'. "
            "Hapus saringan itu atau pakai query_metrics.")
    sort = args.get("sort") or {}
    if sort.get("by") and rows and sort["by"] in rows[0]:
        rows.sort(key=lambda r: (r.get(sort["by"]) is None, r.get(sort["by"]) or 0), reverse=sort.get("direction") != "asc")
    rows = strip_cost_fields(rows[:limit], sc.role)   # KN-E37 — limit berlaku untuk semua jenis
    return await _save(title, cols, rows, user, session_id, "list_records", args, period=p.to_dict() if p else None)


# ── run_report ───────────────────────────────────────────────────────────────
def _q(metrics, period, **kw):
    return {**Q_DEFAULT, "metrics": metrics, "period": period or {"preset": "mtd", "from": None, "to": None}, **kw}


async def _section(fn, args, user, ctx, session_id, warn):
    try:
        return await fn(args, user, ctx, session_id=session_id)
    except engine.AnalyticsError as exc:
        warn.append(str(exc))
        return None


async def run_report(args, user, ctx, session_id=None) -> Dict[str, Any]:
    rep, per = args.get("report"), args.get("period")
    top = args.get("top_n") or 10
    as_of = (args.get("as_of") or "").strip() if isinstance(args.get("as_of"), str) else ""
    if as_of and not per:   # KN-E37 — as_of dipakai sebagai tanggal posisi laporan saldo/umur
        per = {"preset": "custom", "from": as_of, "to": as_of}
    qm, ac, lr = engine.query_metrics, engine.analyze_change, list_records
    today = {"preset": "today", "from": None, "to": None}
    plan: Dict[str, Any] = {
        "daily_brief": {"kpi": (qm, _q(["net_sales", "orders_count", "customers_active", "collections_amount"], per or today, compare="previous_period")),
                        "top_customers": (qm, _q(["net_sales", "orders_count"], per or today, group_by=["customer"], limit=5)),
                        "alerts": (lr, {"record_type": "pending_approvals", "period": None, "limit": 20})},
        "weekly_executive": {"kpi": (qm, _q(["net_sales", "orders_count", "customers_active", "collections_amount"], per, compare="previous_period")),
                             "highlights": (ac, {"metric": "net_sales", "dimension": "customer", "period": per, "compare_to": "previous_period", "top_n": 5})},
        "target_vs_actual": {"kpi": (qm, _q(["net_sales", "sales_target", "target_achievement_pct"], per)),
                             "detail": (qm, _q(["net_sales", "sales_target", "target_achievement_pct"], per, group_by=["sales_person"], limit=50))},
        "sales_kpi": {"kpi": (qm, _q(["net_sales", "orders_count", "avg_order_value", "customers_active"], per, compare="previous_period"))},
        "sales_leaderboard": {"ranking": (qm, _q(["net_sales", "orders_count", "customers_active"], per, group_by=["sales_person"], limit=top))},
        "entity_comparison": {"entities": (qm, _q(["net_sales", "orders_count", "ar_overdue"], per, entity_scope="per_entity"))},
        "ar_aging": {"buckets": (qm, _q(["ar_outstanding"], per, group_by=["aging_bucket"])),
                     "customers": (qm, _q(["ar_outstanding", "ar_overdue"], per, group_by=["customer"], limit=top))},
        "ap_aging": {"suppliers": (qm, _q(["ap_outstanding", "ap_due"], per, group_by=["supplier"], limit=top))},
        "profitability": {"products": (qm, _q(["net_sales", "gross_margin", "gross_margin_pct"], per, group_by=["product"], limit=top))},
        "stock_health": {"aging": (qm, _q(["stock_qty", "stock_rolls"], per, group_by=["stock_age_bucket"])),
                         "dead_items": (lr, {"record_type": "slow_stock", "period": None, "limit": top})},
        "stock_valuation": {"warehouses": (qm, _q(["stock_value", "stock_rolls"], per, group_by=["warehouse"]))},
        "receiving_today": {"receipts": (qm, _q(["received_qty"], per or today, group_by=["product"])),
                            "discrepancies": (lr, {"record_type": "goods_receipts", "period": per or today, "limit": 50})},
        "dispatch_today": {"shipments": (lr, {"record_type": "shipments", "period": per or today, "limit": 50}),
                           "pending": (lr, {"record_type": "open_orders", "period": None, "limit": 50})},
        "supplier_scorecard": {"ranking": (qm, _q(["purchase_value", "po_count"], per, group_by=["supplier"], limit=top))},
        "makloon_status": {"open_orders": (lr, {"record_type": "makloon_orders", "period": None, "limit": 50})},
    }
    warn: List[str] = []
    sections: Dict[str, Any] = {}
    if rep in ("cash_position", "cashflow_forecast", "income_statement"):
        from services.finance_tower_service import _cash_position
        from services.cashflow_forecast_service import cashflow_forecast
        from services.financial_statement_service import income_statement
        sc = await engine.build_scope(user, ctx)
        if not await sc.allowed((("accounting", "view"), ("cash", "view"))):
            raise engine.AnalyticsError("Laporan keuangan tidak tersedia untuk peran Anda.")
        scope = {"entity_id": {"$in": sc.entity_ids}}
        if rep == "income_statement":
            p = period_from_args(per)
            st = await income_statement(p.date_from.isoformat(), p.date_to.isoformat(), scope=scope)
            rows = [{"section": s["label"], "account": ln.get("name") or ln.get("code"), "amount": ln.get("amount", ln.get("balance"))}
                    for s in st["sections"] for ln in s.get("lines") or []]
            rows += [{"section": "Ringkasan", "account": lbl, "amount": st[k]} for k, lbl in (
                ("revenue_total", "Total pendapatan"), ("gross_profit", "Laba kotor"), ("opex_total", "Total beban operasional"),
                ("net_income", "Laba bersih"))]
            if sc.role not in ("admin", "manager", "finance"):
                raise engine.AnalyticsError("Laba rugi tidak tersedia untuk peran Anda.")
            sections["statement"] = await _save("Laba rugi", [_txt("section", "Bagian"), _txt("account", "Akun"), _col("amount", "Jumlah", "idr")],
                                                rows, user, session_id, "run_report", args, period=p.to_dict(),
                                                totals={"amount": st["net_income"]}, definition="Laba rugi dari jurnal posted (akrual)")
        elif rep == "cash_position":
            cp = await _cash_position(scope)
            sections["kpi"] = await _save("Posisi kas & bank", [_txt("name", "Akun"), _col("balance", "Saldo", "idr")],
                                          cp["accounts"], user, session_id, "run_report", args, totals={"balance": cp["total"]})
        else:
            fc = await cashflow_forecast(scope=scope)
            rows = [{"label": b.get("label"), "inflow": b.get("inflow"), "outflow": b.get("outflow"),
                     "net": round(float(b.get("inflow") or 0) - float(b.get("outflow") or 0), 2)} for b in fc.get("buckets") or fc.get("weeks") or []]
            sections["weeks"] = await _save("Perkiraan arus kas", [_txt("label", "Periode"), _col("inflow", "Masuk", "idr"),
                                            _col("outflow", "Keluar", "idr"), _col("net", "Bersih", "idr")], rows, user, session_id, "run_report", args)
    elif rep in plan:
        rfilters = args.get("filters") or []
        for name, (fn, a) in plan[rep].items():
            if rfilters:   # KN-E37 — saringan laporan diteruskan ke tiap bagian
                a = {**a, "filters": rfilters}
            res = await _section(fn, a, user, ctx, session_id, warn)
            if res:
                sections[name] = res
    else:
        warn.append("Laporan ini belum tersedia di versi asisten sekarang.")
    await audit(user.get("name", ""), "ai_tool_run_report", "ai_results", rep or "", {"sections": list(sections)})
    return {"report": rep, "sections": sections, "warnings": warn}


# ── find_entities & get_document ─────────────────────────────────────────────
async def find_entities(args, user, ctx, session_id=None) -> Dict[str, Any]:
    kind, text = args.get("kind"), str(args.get("query") or "").strip().lower()
    sc = await engine.build_scope(user, ctx)
    spec = {"customer": ("customers", {"entity_id": {"$in": sc.entity_ids}, **({"assigned_sales_id": sc.sales_only} if sc.sales_only else {})}),
            "product": ("products", dict(sc.line_q)), "sales_person": ("users", {"role": {"$in": ["sales", "sales_admin"]}}),
            "supplier": ("suppliers", {}), "warehouse": ("warehouses", {})}.get(kind)
    if not spec or not text:
        raise engine.AnalyticsError("kind/query tidak sah untuk find_entities.")
    cands = []
    async for d in db[spec[0]].find(spec[1], {"_id": 0, "id": 1, "name": 1, "sku": 1, "code": 1}).limit(5000):
        label = str(d.get("name") or "")
        score = max(difflib.SequenceMatcher(None, text, label.lower()).ratio(),
                    1.0 if label.lower().startswith(text) else 0.0, 0.9 if text in label.lower() else 0.0,
                    1.0 if text == str(d.get("sku") or d.get("code") or "").lower() else 0.0)
        if score >= 0.5:
            cands.append({"id": d["id"], "name": label, "code": d.get("sku") or d.get("code") or "", "score": round(score, 3)})
    cands.sort(key=lambda c: -c["score"])
    return {"kind": kind, "query": text, "candidates": cands[:5]}


async def get_document(args, user, ctx, session_id=None) -> Dict[str, Any]:
    dt, number = args.get("doc_type"), str(args.get("number") or "").strip()
    spec = {"sales_order": ("sales_orders", "number", ("order", "view")), "purchase_order": ("purchase_orders", "po_number", ("purchase_order", "view")),
            "vendor_bill": ("vendor_bills", "bill_number", ("vendor_bill", "view")), "goods_receipt": ("goods_receipts", "number", ("goods_receipt", "view")),
            "makloon_order": ("makloon_orders", "mko_number", ("makloon_order", "view"))}.get(dt)
    if not spec:
        raise engine.AnalyticsError("Jenis dokumen tidak dikenal.")
    sc = await engine.build_scope(user, ctx)
    if not await sc.allowed((spec[2],)):
        raise engine.AnalyticsError("Dokumen ini tidak tersedia untuk peran Anda.")
    doc = await db[spec[0]].find_one({spec[1]: number, "entity_id": {"$in": sc.entity_ids}},
                                     {"_id": 0, "status_history": 0, "refs": 0, "payments": 0, "allocations": 0})
    if not doc:
        raise engine.AnalyticsError(f"Dokumen {number} tidak ditemukan di entitas Anda.")
    if dt == "sales_order":
        assert_may_open(doc, user)
    keep = ("id", "number", "po_number", "bill_number", "mko_number", "status", "customer_name", "supplier_name", "created_at",
            "grand_total", "ppn_amount", "payment_status", "expected_delivery_date", "items", "lines")
    slim = {k: doc[k] for k in keep if k in doc}
    return strip_cost_fields(slim, sc.role)


# ── ops_metrics · forecast · propose_action (2026-09-28) ─────────────────────
async def ops_metrics(args, user, ctx, session_id=None) -> Dict[str, Any]:
    from services import ai_ops_metrics as ops
    spec = ops.KINDS.get(args.get("kind"))
    if not spec:
        raise engine.AnalyticsError("Jenis metrik operasional tidak dikenal.")
    fn, perm, title, cols, definition = spec
    sc = await engine.build_scope(user, ctx)
    if sc.sales_only or not await sc.allowed((perm,)):
        raise engine.AnalyticsError("Metrik operasional ini tidak tersedia untuk peran Anda.")
    p = period_from_args(args.get("period") or {"preset": "last_90d", "from": None, "to": None})
    rows = await fn(sc.entity_ids, p)
    rows = rows[:max(1, min(int(args.get("limit") or 50), cat.ROW_RETURN_LIMIT))]
    return await _save(title, [_col(k, lbl, u, t) for k, lbl, t, u in cols], rows, user, session_id, "ops_metrics", args,
                       period=p.to_dict(), definition=definition)


async def forecast(args, user, ctx, session_id=None) -> Dict[str, Any]:
    from services import ai_forecast as fc
    kind, sc = args.get("kind"), await engine.build_scope(user, ctx)
    limit = max(1, min(int(args.get("limit") or 30), cat.ROW_RETURN_LIMIT))
    warn = ["Perkiraan statistik sederhana dari riwayat — bukan kepastian."]
    if kind == "cashflow":
        return await run_report({"report": "cashflow_forecast"}, user, ctx, session_id)
    if kind == "stock_demand":
        if not await sc.allowed((("inventory", "view"),)):
            raise engine.AnalyticsError("Data stok tidak tersedia untuk peran Anda.")
        h = int(args.get("horizon_weeks") or 6)
        rows = await fc.demand_rows(sc.entity_ids, sc.line_q, h, args.get("product_ids") or None)
        cols = [_txt("product", "Produk"), _txt("unit", "Satuan"), _col("avg_weekly", "Rata-rata/minggu", "qty"),
                _col("trend_pct", "Tren 4 mgg", "pct"), _col("available", "Tersedia", "qty"), _col("incoming", "Dalam PO", "qty"),
                _col("forecast", f"Perkiraan {h} mgg", "qty"), _col("suggested_qty", "Saran pesan", "qty"),
                _col("days_cover", "Cukup (hari)", "count"), _txt("supplier", "Supplier"), _txt("product_id", "ID produk"),
                _txt("supplier_id", "ID supplier")]
        return await _save(f"Perkiraan kebutuhan stok {h} minggu", cols, rows[:limit], user, session_id, "forecast", args, warnings=warn,
                           definition="Rata-rata mingguan 12 minggu (bobot 60% ke 4 minggu terakhir) × horizon; saran = perkiraan + stok pengaman 1 minggu − tersedia − dalam PO")
    if kind == "churn_risk":
        if not await sc.allowed((("order", "view"),)):
            raise engine.AnalyticsError("Data pelanggan tidak tersedia untuk peran Anda.")
        rows = await fc.churn_rows(sc.entity_ids, await sc.owned_customers() if sc.sales_only else None)
        cols = [_txt("customer", "Pelanggan"), _col("orders_12m", "Pesanan 12 bln", "count"), _col("value_12m", "Nilai 12 bln", "idr"),
                _col("median_gap_days", "Jarak order biasa (hari)", "count"), _col("days_since_last", "Hari sejak order terakhir", "count"),
                _txt("last_order", "Order terakhir"), _col("risk_score", "Skor risiko berhenti", "count"), _txt("risk", "Risiko"),
                _txt("customer_id", "ID pelanggan")]
        return await _save("Risiko pelanggan berhenti order", cols, rows[:limit], user, session_id, "forecast", args, warnings=warn,
                           definition="Skor 5–95 dari rasio hari sejak order terakhir ÷ jarak order biasa (median); ≥2× = tinggi")
    raise engine.AnalyticsError("Jenis perkiraan tidak dikenal.")


async def propose_action(args, user, ctx, session_id=None) -> Dict[str, Any]:
    from services import ai_actions
    return await ai_actions.propose_action(args, user, ctx, session_id)


TOOLS = {"query_metrics": engine.query_metrics, "analyze_change": engine.analyze_change, "list_records": list_records,
         "run_report": run_report, "find_entities": find_entities, "get_document": get_document,
         "ops_metrics": ops_metrics, "forecast": forecast, "propose_action": propose_action}


async def execute(tool: str, args: Dict[str, Any], user, ctx, session_id: Optional[str] = None) -> Dict[str, Any]:
    fn = TOOLS.get(tool)
    if not fn:
        return {"error": f"Tool tidak dikenal: {tool}"}
    try:
        return await fn(args or {}, user, ctx, session_id=session_id)
    except engine.AnalyticsError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001 — galat tool dikembalikan ke model, bukan 500
        from fastapi import HTTPException
        if isinstance(exc, HTTPException):
            return {"error": str(exc.detail)}
        raise
