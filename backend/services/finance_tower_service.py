"""FINANCE — Control Tower (Dashboard Keuangan terpadu) (EPIC P1-5).

Satu endpoint agregat untuk dashboard: posisi kas (GL), ringkasan AR & AP + aging,
snapshot Laba-Rugi (MTD & YTD), tren bulanan + rasio (reuse BI), serta daftar
jatuh tempo teratas. Ter-scope per entitas.
"""
from typing import Any, Dict, List, Optional

from db import db
from core_utils import now_iso
from services import financial_statement_service as fs
from services import finance_bi_service as bi
from services import ar_aging_service as ar
from services.vendor_bill_service import bill_financials
from services.cash_flow_service import CASH_CODES

PAYABLE_BILL_STATUSES = ["posted", "paid"]
EPS = 0.005


async def _cash_position(scope: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Posisi kas buku besar. Kas & Bank 1 — akun kas = `report_basis.kode_kas` (termasuk sub-akun rekening); dua akun
    bawaan selalu tampil, akun kas lain bila pernah dijurnal (sama dengan `bank_service.cash_position`)."""
    from services import report_basis as rb
    amap = await fs._accounts_map()
    agg = await fs._aggregate(scope, None, include_closing=True)
    kas = await rb.kode_kas(scope)
    lines = []
    total = 0.0
    for code in sorted(set(CASH_CODES) | {c for c in kas if c in agg}):
        v = agg.get(code, {"debit": 0.0, "credit": 0.0})
        bal = round(float(v.get("debit", 0) or 0) - float(v.get("credit", 0) or 0), 2)
        total += bal
        lines.append({"code": code, "name": amap.get(code, {}).get("name", code), "balance": bal})
    return {"total": round(total, 2), "accounts": lines}


async def _ap_summary(scope: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    from services import report_basis as rb
    today = rb.tanggal_buku()
    # PK-41 (RP-01) — kursor tanpa batas (dulu 20.000 tagihan) dengan saringan "belum lunas" di kueri; umur =
    # `report_basis.hari_antara(jatuh tempo, hari ini)`, jatuh tempo kosong = tanggal tagihan + termin pemasok.
    q: Dict[str, Any] = {"status": {"$in": PAYABLE_BILL_STATUSES}, "payment_status": {"$ne": "paid"}, **(scope or {})}
    bills = [b async for b in db.vendor_bills.find(q, {"_id": 0})]
    term_cache: Dict[str, int] = {}
    aging = {"d0_30": 0.0, "d31_60": 0.0, "d61_90": 0.0, "d90_plus": 0.0}
    total = 0.0
    top: List[Dict[str, Any]] = []
    for b in bills:
        out = bill_financials(b)["outstanding"]
        if out <= EPS:
            continue
        total += out
        due, _basis = await rb.jatuh_tempo_tagihan(b, term_cache)
        days = rb.hari_antara(due, today) if due else 0
        bk = "d0_30" if days <= 30 else "d31_60" if days <= 60 else "d61_90" if days <= 90 else "d90_plus"
        aging[bk] = round(aging[bk] + out, 2)
        top.append({"number": b.get("bill_number"), "party": b.get("supplier_name", ""),
                    "party_id": b.get("supplier_id", ""), "amount": out, "days": days})
    # UAT 24 Okt (audit UI tahap 2) — G1-38: "Hutang Terbesar" dulu per TAGIHAN (satu pemasok muncul 4×) sementara
    # "Piutang Terbesar" per pelanggan. Kini dikelompokkan per pemasok: jumlah sisa + banyaknya tagihan + umur tertua.
    by_party: Dict[str, Dict[str, Any]] = {}
    for t in top:
        k = t["party_id"] or t["party"] or t["number"]
        g = by_party.setdefault(k, {"party": t["party"] or t["number"], "party_id": t["party_id"], "amount": 0.0,
                                    "bill_count": 0, "days": 0, "number": t["number"]})
        g["amount"] = round(g["amount"] + t["amount"], 2)
        g["bill_count"] += 1
        g["days"] = max(g["days"], t["days"])
    grouped = sorted(by_party.values(), key=lambda x: x["amount"], reverse=True)
    return {"outstanding": round(total, 2), "aging": aging, "top": grouped[:5]}


def _pl_snapshot(stmt: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "revenue": stmt.get("revenue_total", 0),
        "cogs": stmt.get("cogs_total", 0),
        "gross_profit": stmt.get("gross_profit", 0),
        "opex": stmt.get("opex_total", 0),
        "net_income": stmt.get("net_income", 0),
        "net_margin": stmt.get("net_margin", 0),
    }


async def finance_tower(scope: Optional[Dict[str, Any]] = None,
                        entity_id: Optional[str] = None,
                        entity_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    # Hari ini, bulan, dan tahun berjalan = tanggal buku WIB. Dulu jam UTC: pukul 00.00–07.00 WIB jurnal hari itu
    # tidak ikut MTD/YTD, dan pada tanggal 1 MTD masih bulan LALU (tanggal 1 Januari: YTD masih tahun lalu).
    from services.book_date import tanggal_buku
    today = tanggal_buku()
    year = int(today[:4])
    ym = today[:7]
    month_start = f"{ym}-01"
    year_start = f"{year}-01-01"

    cash = await _cash_position(scope)
    mtd = _pl_snapshot(await fs.income_statement(month_start, today, scope))
    ytd = _pl_snapshot(await fs.income_statement(year_start, today, scope))
    ap = await _ap_summary(scope)
    # PK-41 (RP-09) — umur piutang dengan saringan PT yang SAMA dengan `scope` (mode gabungan `{"$in": entity_ids}`);
    # dulu dipanggil tanpa saringan sehingga piutang PT di luar penugasan ikut terhitung.
    ar_rep = await ar.aging_report((scope or {}).get("entity_id")
                                   or (entity_id if entity_id and entity_id != "all" else None))
    ar_tot = ar_rep.get("totals", {})
    bi_data = await bi.finance_bi(year, scope, entity_ids or ([entity_id] if entity_id else []))

    # Pola UI 16 Nov (M32) — `customer_id` ikut dikirim: nama di "Piutang Terbesar" membuka kartu pelanggan (baca saja).
    ar_top = [
        {"customer_id": c.get("customer_id", ""), "customer_name": c.get("customer_name", ""),
         "outstanding": c.get("outstanding", 0),
         "overdue": c.get("overdue", 0), "oldest_days": c.get("oldest_days", 0)}
        for c in ar_rep.get("customers", [])[:5]
    ]

    return {
        "period": {"month": ym, "year": year},
        "cash": cash,
        "ar": {
            "outstanding": ar_tot.get("total", 0),
            "ar_ledger": ar_tot.get("ar_ledger", 0),   # PK-41 — piutang tercatat (surat jalan berjurnal)
            "exposure": ar_tot.get("exposure", 0),      # PK-41 — pesanan belum dikirim
            "overdue": ar_tot.get("overdue", 0),
            "aging": {
                "current": ar_tot.get("current", 0), "b1_30": ar_tot.get("b1_30", 0),
                "b31_60": ar_tot.get("b31_60", 0), "b61_90": ar_tot.get("b61_90", 0),
                "b90_plus": ar_tot.get("b90_plus", 0),
            },
            "top": ar_top,
            "bucket_labels": ar_rep.get("bucket_labels") or [],   # PK-41 (RP-12) — judul kolom umur PT
        },
        "ap": ap,
        # PK-41 (RP-09) — modal kerja memakai piutang TERCATAT (bukan total belum lunas yang memuat pesanan belum dikirim).
        "working_capital": round(cash["total"] + ar_tot.get("ar_ledger", 0) - ap["outstanding"], 2),
        "working_capital_basis": "Kas + piutang tercatat − hutang",
        "pl": {"mtd": mtd, "ytd": ytd},
        "monthly": bi_data.get("monthly", []),
        "ratios": bi_data.get("ratios", {}),
        "entity_comparison": bi_data.get("entity_comparison", []),
        "generated_at": now_iso(),
    }
