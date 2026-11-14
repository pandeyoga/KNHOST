"""FINANCE — Proyeksi Arus Kas (Cash Flow Forecast) (EPIC P1-3).

Proyeksi likuiditas ke depan dari:
- INFLOW  : piutang (AR) belum lunas per BARIS TAGIHAN (PK-41, `report_basis.baris_tagihan`): baris surat jalan
            jatuh tempo = tanggal surat jalan + termin; bagian belum dikirim = perkiraan dikirim hari ini + termin.
- OUTFLOW : hutang (AP) belum lunas dari vendor_bills (posted/paid partial),
            jatuh tempo = due_date, atau tanggal tagihan + termin pemasok bila kosong.
Hari ke jatuh tempo = `report_basis.hari_antara(hari ini, jatuh tempo)` (tanggal WIB; RP-11). Pesanan dan tagihan
dibaca tanpa batas dengan saringan "belum lunas" di kueri (RP-01).
Dikelompokkan ke bucket waktu + posisi kas kumulatif dari saldo kas GL awal.
"""
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from db import db
from core_utils import now_iso
from services import financial_statement_service as fs
from services.vendor_bill_service import bill_financials
from services.cash_flow_service import CASH_CODES

EPS = 0.005
PAYABLE_BILL_STATUSES = ["posted", "paid"]
DEAD_SO = {"cancelled", "draft", "rejected", "expired"}
NON_AR_METHODS = {"tunai", "cash"}

BUCKETS = [
    ("overdue", "Jatuh Tempo (Lewat)", -10**9, -1),
    ("d0_30", "0–30 hari", 0, 30),
    ("d31_60", "31–60 hari", 31, 60),
    ("d61_90", "61–90 hari", 61, 90),
    ("d90_plus", "> 90 hari", 91, 10**9),
]


def _bucket_key(days: int) -> str:
    for key, _lbl, lo, hi in BUCKETS:
        if lo <= days <= hi:
            return key
    return "d90_plus"


async def _cash_now(scope: Optional[Dict[str, Any]]) -> float:
    agg = await fs._aggregate(scope, None, include_closing=True)
    total = 0.0
    for code in CASH_CODES:
        v = agg.get(code, {"debit": 0.0, "credit": 0.0})
        total += float(v.get("debit", 0) or 0) - float(v.get("credit", 0) or 0)
    return round(total, 2)


async def cashflow_forecast(scope: Optional[Dict[str, Any]] = None,
                            entity_id: Optional[str] = None) -> Dict[str, Any]:
    from services import report_basis as rb
    from services.customer_service import DEAD_STATUSES, _term_days
    today = rb.tanggal_buku()
    cash_now = await _cash_now(scope)

    buckets: Dict[str, Dict[str, Any]] = {
        k: {"key": k, "label": lbl, "inflow": 0.0, "outflow": 0.0}
        for k, lbl, _lo, _hi in BUCKETS
    }
    ar_items: List[Dict[str, Any]] = []
    ap_items: List[Dict[str, Any]] = []

    # ── INFLOW (AR) ── G3 D4-FIN-02 — basis AR & termin = AR kanonis: metode tunai dikecualikan, termin dari snapshot SO
    # (payment_term_days) dulu, termin 0 tetap 0. PK-41 — per baris tagihan (surat jalan) posisi hari ini.
    soq: Dict[str, Any] = {**(scope or {}), "status": {"$nin": sorted(DEAD_STATUSES)}, "payment_status": {"$ne": "paid"}}
    orders = [o async for o in db.sales_orders.find(soq, {"_id": 0})]
    cids = list({o.get("customer_id") for o in orders if o.get("customer_id")})
    cmap: Dict[str, Dict[str, Any]] = {}
    for i in range(0, len(cids), rb.KELOMPOK):
        async for c in db.customers.find({"id": {"$in": cids[i:i + rb.KELOMPOK]}}, {"_id": 0, "id": 1, "payment_profile": 1}):
            cmap[c["id"]] = c
    lines_by_order = await rb.baris_tagihan(orders, cmap, per=today)
    terms = await rb.peta_termin(orders)
    for o in orders:
        cust = cmap.get(o.get("customer_id"), {})
        for ln in lines_by_order.get(o.get("id")) or []:
            if ln["sumber"] == rb.SUMBER_BELUM_DIKIRIM:
                # belum dikirim: perkiraan paling cepat = dikirim hari ini + termin (bukan "lewat")
                due = (date.fromisoformat(today) + timedelta(days=_term_days(cust, o, terms))).isoformat()
                basis = "estimate_not_shipped"
            else:
                due, basis = ln["jatuh_tempo"], "per_sj"
            days = rb.hari_antara(today, due)
            bk = _bucket_key(days)
            buckets[bk]["inflow"] = round(buckets[bk]["inflow"] + ln["sisa"], 2)
            ar_items.append({"number": o.get("number"), "party": o.get("customer_name", ""),
                             "ref_number": ln["ref_number"], "amount": ln["sisa"], "due_date": due,
                             "days_to_due": days, "bucket": bk, "due_basis": basis})

    # ── OUTFLOW (AP) ──
    vbq: Dict[str, Any] = {"status": {"$in": PAYABLE_BILL_STATUSES}, "payment_status": {"$ne": "paid"}, **(scope or {})}
    term_cache: Dict[str, int] = {}
    async for b in db.vendor_bills.find(vbq, {"_id": 0}):
        fin = bill_financials(b)
        out = fin["outstanding"]
        if out <= EPS:
            continue
        due, _basis = await rb.jatuh_tempo_tagihan(b, term_cache)
        due = due or today
        days = rb.hari_antara(today, due)
        bk = _bucket_key(days)
        buckets[bk]["outflow"] = round(buckets[bk]["outflow"] + out, 2)
        ap_items.append({"number": b.get("bill_number"), "party": b.get("supplier_name", ""),
                         "amount": out, "due_date": due, "days_to_due": days, "bucket": bk})

    ordered = []
    running = cash_now
    total_in = total_out = 0.0
    for key, lbl, _lo, _hi in BUCKETS:
        b = buckets[key]
        net = round(b["inflow"] - b["outflow"], 2)
        running = round(running + net, 2)
        total_in += b["inflow"]
        total_out += b["outflow"]
        ordered.append({**b, "net": net, "cumulative_cash": running})

    ar_items.sort(key=lambda x: x["days_to_due"])
    ap_items.sort(key=lambda x: x["days_to_due"])
    return {
        "cash_now": cash_now,
        "buckets": ordered,
        "total_inflow": round(total_in, 2),
        "total_outflow": round(total_out, 2),
        "net_flow": round(total_in - total_out, 2),
        "projected_cash": running,
        "ar_items": ar_items[:100],
        "ap_items": ap_items[:100],
        "generated_at": now_iso(),
    }
