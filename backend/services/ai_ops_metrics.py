"""Tanya KN — metrik operasional gudang, QC, makloon & performa supplier (dihitung server, baca-saja)."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Tuple

from db import db
from services.analytics_time import Period, now_wib

OK_RESULTS = ("", "sesuai", None)


def _d(iso: Any) -> date | None:
    try:
        return date.fromisoformat(str(iso)[:10])
    except ValueError:
        return None


def _pct(a: float, b: float) -> float | None:
    return round(a / b * 100, 1) if b else None


def _qc_issue(ln: Dict[str, Any]) -> bool:
    return bool(ln.get("hold")) or ln.get("color_result") not in OK_RESULTS or ln.get("handfeel_result") not in OK_RESULTS


async def supplier_performance(ids: List[str], p: Period) -> List[Dict[str, Any]]:
    today = now_wib().date()
    per: Dict[str, Dict[str, Any]] = {}
    q = {"entity_id": {"$in": ids}, "status": {"$nin": ["rejected", "cancelled", "draft"]}, "created_at": p.mongo_range()}
    async for po in db.purchase_orders.find(q, {"_id": 0, "supplier_id": 1, "supplier_name": 1, "items": 1, "created_at": 1,
                                                 "completed_at": 1, "expected_delivery_date": 1}):
        s = per.setdefault(po.get("supplier_id") or po.get("supplier_name"), {
            "supplier": po.get("supplier_name"), "po_count": 0, "completed": 0, "on_time": 0, "with_eta": 0,
            "lead": [], "ordered": 0.0, "received": 0.0, "late_open": 0, "qc_lines": 0, "qc_issues": 0})
        s["po_count"] += 1
        s["ordered"] += sum(float(i.get("quantity") or 0) for i in po.get("items") or [])
        s["received"] += sum(float(i.get("received_qty") or 0) for i in po.get("items") or [])
        eta, done, made = _d(po.get("expected_delivery_date")), _d(po.get("completed_at")), _d(po.get("created_at"))
        if done:
            s["completed"] += 1
            if made:
                s["lead"].append((done - made).days)
            if eta:
                s["with_eta"] += 1
                s["on_time"] += done <= eta
        elif eta and eta < today:
            s["late_open"] += 1
    async for ins in db.inspections.find({"entity_id": {"$in": ids}, "kind": "po_receipt", "created_at": p.mongo_range()},
                                         {"_id": 0, "supplier_id": 1, "supplier_name": 1, "lines": 1}):
        s = per.get(ins.get("supplier_id")) or per.get(ins.get("supplier_name"))
        if s:
            s["qc_lines"] += len(ins.get("lines") or [])
            s["qc_issues"] += sum(1 for ln in ins.get("lines") or [] if _qc_issue(ln))
    return [{"supplier": s["supplier"], "po_count": s["po_count"], "completed": s["completed"],
             "on_time_pct": _pct(s["on_time"], s["with_eta"]),
             "avg_lead_days": round(sum(s["lead"]) / len(s["lead"]), 1) if s["lead"] else None,
             "fill_pct": _pct(s["received"], s["ordered"]), "late_open": s["late_open"],
             "qc_lines": s["qc_lines"], "qc_issue_pct": _pct(s["qc_issues"], s["qc_lines"])}
            for s in sorted(per.values(), key=lambda x: -x["po_count"])]


async def receiving_discrepancy(ids: List[str], p: Period) -> List[Dict[str, Any]]:
    rows = []
    async for g in db.goods_receipts.find({"entity_id": {"$in": ids}, "status": {"$ne": "cancelled"}, "created_at": p.mongo_range()},
                                          {"_id": 0, "number": 1, "partner_name": 1, "status": 1, "lines": 1, "discrepancies": 1, "created_at": 1}):
        lines = g.get("lines") or []
        bad = [ln for ln in lines if (ln.get("recon") or {}).get("classes", ["match"]) != ["match"]]
        discs = [d for d in g.get("discrepancies") or [] if not d.get("superseded")]
        rows.append({"number": g.get("number"), "supplier": g.get("partner_name"), "status": g.get("status"),
                     "date": str(g.get("created_at"))[:10], "lines": len(lines), "lines_mismatch": len(bad),
                     "diff_qty": round(sum(float((ln.get("recon") or {}).get("diff_qty") or 0) for ln in bad), 2),
                     "open_blockers": sum(1 for d in discs if d.get("blocking") and not d.get("resolution")),
                     "kinds": ", ".join(sorted({d.get("kind", "") for d in discs})) or "—"})
    rows.sort(key=lambda r: (-r["lines_mismatch"], -abs(r["diff_qty"])))
    return rows


async def dispatch_speed(ids: List[str], p: Period) -> List[Dict[str, Any]]:
    ships = await db.shipments.find({"entity_id": {"$in": ids}, "created_at": p.mongo_range()},
                                    {"_id": 0, "order_id": 1, "warehouse_name": 1, "created_at": 1}).to_list(5000)
    so = {o["id"]: o.get("created_at") async for o in db.sales_orders.find(
        {"id": {"$in": list({s.get("order_id") for s in ships})}}, {"_id": 0, "id": 1, "created_at": 1})}
    per: Dict[str, List[int]] = {}
    for s in ships:
        a, b = _d(so.get(s.get("order_id"))), _d(s.get("created_at"))
        if a and b:
            per.setdefault(s.get("warehouse_name") or "—", []).append((b - a).days)
    return [{"warehouse": wh, "shipments": len(v), "avg_days": round(sum(v) / len(v), 1),
             "within_2d_pct": _pct(sum(1 for x in v if x <= 2), len(v)), "max_days": max(v)}
            for wh, v in sorted(per.items(), key=lambda kv: -len(kv[1]))]


async def qc_results(ids: List[str], p: Period) -> List[Dict[str, Any]]:
    per: Dict[Tuple[str, str], Dict[str, Any]] = {}
    async for ins in db.inspections.find({"entity_id": {"$in": ids}, "created_at": p.mongo_range()}, {"_id": 0}):
        k = (ins.get("supplier_name") or ins.get("customer_name") or "—", ins.get("kind") or "")
        s = per.setdefault(k, {"party": k[0], "kind": "Penerimaan PO" if k[1] == "po_receipt" else "Retur pelanggan" if k[1] == "return_customer" else k[1],
                               "inspections": 0, "lines": 0, "hold": 0, "color_diff": 0, "handfeel_diff": 0, "points": []})
        s["inspections"] += 1
        for ln in ins.get("lines") or []:
            s["lines"] += 1
            s["hold"] += bool(ln.get("hold"))
            s["color_diff"] += ln.get("color_result") not in OK_RESULTS
            s["handfeel_diff"] += ln.get("handfeel_result") not in OK_RESULTS
            if ln.get("points_snapshot") is not None:
                s["points"].append(float(ln["points_snapshot"]))
    return [{**{k: v for k, v in s.items() if k != "points"},
             "avg_points": round(sum(s["points"]) / len(s["points"]), 1) if s["points"] else None,
             "issue_pct": _pct(max(s["hold"], s["color_diff"] + s["handfeel_diff"]), s["lines"])}
            for s in sorted(per.values(), key=lambda x: -x["lines"])]


async def makloon_wip(ids: List[str], p: Period) -> List[Dict[str, Any]]:
    today, rows = now_wib().date(), []
    lo = p.date_from.isoformat()
    async for m in db.makloon_orders.find({"entity_id": {"$in": ids}, "status": {"$nin": ["cancelled"]}},
                                          {"_id": 0, "mko_number": 1, "steps": 1}):
        for st in m.get("steps") or []:
            var = st.get("variance") or {}
            wip = st.get("status") == "issued"
            late_var = st.get("status") == "received" and var.get("level") not in (None, "ok") and str(st.get("received_at") or "")[:10] >= lo
            if not (wip or late_var):
                continue
            issued = _d(st.get("issued_at"))
            rows.append({"number": m.get("mko_number"), "step": st.get("stage_label") or st.get("process_type"),
                         "vendor": st.get("makloon_name"), "state": "Di vendor (WIP)" if wip else "Selesai · selisih",
                         "issued": issued.isoformat() if issued else "—",
                         "age_days": (today - issued).days if (issued and wip) else None,
                         "input_qty": st.get("input_qty"), "unit": st.get("input_unit"),
                         "expected_out": st.get("expected_output_qty"), "variance_pct": var.get("variance_pct")})
    rows.sort(key=lambda r: -(r["age_days"] or 0))
    return rows


KINDS = {
    "supplier_performance": (supplier_performance, ("purchase_order", "view"), "Performa supplier", [
        ("supplier", "Supplier", "dimension", ""), ("po_count", "Jumlah PO", "metric", "count"), ("completed", "PO selesai", "metric", "count"),
        ("on_time_pct", "Tepat waktu", "metric", "pct"), ("avg_lead_days", "Rata-rata lead time (hari)", "metric", "count"),
        ("fill_pct", "Kelengkapan qty", "metric", "pct"), ("late_open", "PO terbuka terlambat", "metric", "count"),
        ("qc_lines", "Roll diperiksa QC", "metric", "count"), ("qc_issue_pct", "Masalah QC", "metric", "pct")],
        "Tepat waktu = tanggal selesai PO ≤ perkiraan datang · kelengkapan = qty diterima ÷ qty dipesan · masalah QC = roll ditahan/warna/handfeel beda"),
    "receiving_discrepancy": (receiving_discrepancy, ("goods_receipt", "view"), "Selisih penerimaan (SJ vs hitung fisik)", [
        ("number", "GRN", "dimension", ""), ("supplier", "Pengirim", "dimension", ""), ("status", "Status", "dimension", ""),
        ("date", "Tanggal", "dimension", ""), ("lines", "Baris", "metric", "count"), ("lines_mismatch", "Baris selisih", "metric", "count"),
        ("diff_qty", "Total selisih qty", "metric", "qty"), ("open_blockers", "Selisih belum diputuskan", "metric", "count"),
        ("kinds", "Jenis selisih", "dimension", "")], "Selisih = hitung fisik − qty di surat jalan per baris GRN"),
    "dispatch_speed": (dispatch_speed, ("order", "view"), "Kecepatan pengiriman per gudang", [
        ("warehouse", "Gudang", "dimension", ""), ("shipments", "Pengiriman", "metric", "count"), ("avg_days", "Rata-rata hari SO→kirim", "metric", "count"),
        ("within_2d_pct", "≤ 2 hari", "metric", "pct"), ("max_days", "Terlama (hari)", "metric", "count")],
        "Hari dari pesanan dibuat sampai pengiriman dibuat"),
    "qc_results": (qc_results, ("goods_receipt", "view"), "Hasil inspeksi QC", [
        ("party", "Supplier/Pelanggan", "dimension", ""), ("kind", "Jenis", "dimension", ""), ("inspections", "Inspeksi", "metric", "count"),
        ("lines", "Roll", "metric", "count"), ("hold", "Ditahan", "metric", "count"), ("color_diff", "Warna beda", "metric", "count"),
        ("handfeel_diff", "Handfeel beda", "metric", "count"), ("avg_points", "Rata-rata poin cacat", "metric", "count"),
        ("issue_pct", "Roll bermasalah", "metric", "pct")], "Dari dokumen inspeksi (4-point, warna, handfeel)"),
    "makloon_wip": (makloon_wip, ("makloon_order", "view"), "Makloon: barang di vendor & selisih hasil", [
        ("number", "MKO", "dimension", ""), ("step", "Langkah", "dimension", ""), ("vendor", "Vendor", "dimension", ""),
        ("state", "Keadaan", "dimension", ""), ("issued", "Dikirim", "dimension", ""), ("age_days", "Umur di vendor (hari)", "metric", "count"),
        ("input_qty", "Qty bahan", "metric", "qty"), ("unit", "Satuan", "dimension", ""), ("expected_out", "Perkiraan hasil", "metric", "qty"),
        ("variance_pct", "Selisih hasil", "metric", "pct")], "WIP = langkah berstatus dikirim ke vendor, belum diterima"),
}
