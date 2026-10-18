"""FINANCE — Laporan Arus Kas (Cash Flow Statement). FN-04: klasifikasi per jurnal kas
(bukan selisih saldo per prefix akun) — lihat cash_flow_statement.

Diturunkan sepenuhnya dari `journal_entries` (SSOT double-entry), konsisten dgn
Laba-Rugi & Neraca. Prinsip identitas kas:

    ΔKas = -Δ(Aset non-kas) + Δ(Kewajiban) + Δ(Ekuitas + Laba/Rugi P&L)

Karena setiap jurnal seimbang (Σdebit = Σkredit), untuk SETIAP akun non-kas
kontribusi kas = -(Δ(debit−credit)) dan totalnya PASTI = Δ saldo kas. Jurnal
penutup (source_type="closing") DIKECUALIKAN (tak menyentuh kas; menjaga label
Laba bersih tetap operasional & ekuitas hanya gerakan modal riil).

Klasifikasi:
- Operasi   : Laba bersih (akun P&L) + perubahan modal kerja (aset lancar
              non-kas 1-1xxx & kewajiban lancar 2-1xxx).
- Investasi : perubahan aset tetap/non-lancar (1-2xxx dst).
- Pendanaan : perubahan ekuitas (3-xxxx) + kewajiban jangka panjang (2-2xxx+).
"""
from typing import Any, Dict, List, Optional

from core_utils import now_iso
from services import financial_statement_service as fs

EPS = 0.005
CASH_CODES = {"1-1100", "1-1110"}  # Kas Besar/Bank + Kas Kecil (kas & setara kas)


def _is_cash(code: str) -> bool:
    return code in CASH_CODES


def _raw(agg: Dict[str, Dict[str, float]], code: str) -> float:
    v = agg.get(code, {"debit": 0.0, "credit": 0.0})
    return float(v.get("debit", 0) or 0) - float(v.get("credit", 0) or 0)


def _section(atype: str, code: str) -> str:
    if atype in ("income", "expense"):
        return "pnl"
    if atype == "asset":
        return "investing" if code.startswith("1-2") else "operating"
    if atype == "liability":
        return "operating" if code.startswith("2-1") else "financing"
    if atype == "equity":
        return "financing"
    return "operating"


async def _cash_codes(amap: Dict[str, Dict[str, Any]]) -> set:
    """Kas & setara kas: akun baku + akun yang ditandai `is_cash`/`cash_equivalent` di COA."""
    return CASH_CODES | {c for c, a in amap.items() if a.get("is_cash") or a.get("cash_equivalent")}


def split_journal_cash(lines: List[Dict[str, Any]], cash: set) -> List[tuple]:
    """G3 V3-CF-01 — pecah tiap lawan akun jadi (porsi kas, porsi nonkas).

    Kas bersih jurnal C = Σ(debit−kredit) akun kas. Hanya lawan akun yang searah dengan C
    (sisi yang dibayar/diterima tunai) yang menerima porsi kas, pro-rata nilainya; sisanya
    + lawan akun berlawanan arah (mis. AP/AR yang menampung sisa) = nonkas. Σ porsi kas = C.
    """
    c = sum(float(ln.get("debit", 0) or 0) - float(ln.get("credit", 0) or 0)
            for ln in lines if ln["account_code"] in cash)
    eff: Dict[str, float] = {}
    for ln in lines:
        if ln["account_code"] in cash:
            continue
        code = ln["account_code"]
        eff[code] = eff.get(code, 0.0) - (float(ln.get("debit", 0) or 0) - float(ln.get("credit", 0) or 0))
    same = sum(v for v in eff.values() if v * c > 0)
    ratio = (c / same) if abs(c) > EPS and abs(same) > EPS else 0.0
    out = []
    for code, v in eff.items():
        cash_amt = v * ratio if v * c > 0 else 0.0
        out.append((code, cash_amt, v - cash_amt))
    return out


async def cash_flow_statement(start: Optional[str] = None, end: Optional[str] = None,
                              scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """FN-04 — klasifikasi PER JURNAL: hanya jurnal yang menyentuh akun kas yang menghasilkan
    arus kas; lawan akunnya menentukan aktivitas. Jurnal nonkas (penyusutan, reclass, beli aset
    kredit, akrual) = 0 dan diungkapkan terpisah bila menyentuh akun investasi/pendanaan."""
    from db import db
    amap = await fs._accounts_map(scope)
    cash = await _cash_codes(amap)

    begin_agg: Dict[str, Dict[str, float]] = {}
    if start:
        begin_agg = await fs._aggregate(scope, {"$lt": fs._day_start(start)}, include_closing=False)
    end_filter = {"$lte": fs._day_end(end)} if end else None
    end_agg = await fs._aggregate(scope, end_filter, include_closing=False)
    begin_cash = sum(_raw(begin_agg, c) for c in cash)
    end_cash = sum(_raw(end_agg, c) for c in cash)

    q: Dict[str, Any] = {"status": {"$ne": "void"}, "source_type": {"$ne": "closing"}, **(scope or {})}
    df: Dict[str, str] = {}
    if start:
        df["$gte"] = fs._day_start(start)
    if end:
        df["$lte"] = fs._day_end(end)
    if df:
        q["date"] = df
    buckets: Dict[str, Dict[str, float]] = {"pnl": {}, "operating": {}, "investing": {}, "financing": {}}
    noncash: Dict[str, float] = {}
    async for je in db.journal_entries.find(q, {"_id": 0, "lines": 1}):
        lines = [ln for ln in je.get("lines", []) if ln.get("account_code")]
        for code, cash_amt, noncash_amt in split_journal_cash(lines, cash):
            sec = _section(amap.get(code, {}).get("type", ""), code)
            if abs(cash_amt) > 1e-9:
                buckets[sec][code] = buckets[sec].get(code, 0.0) + cash_amt
            if abs(noncash_amt) > 1e-9 and sec in ("investing", "financing"):
                noncash[code] = noncash.get(code, 0.0) + noncash_amt

    def _lines(d: Dict[str, float]) -> List[Dict[str, Any]]:
        return sorted(({"code": c, "name": amap.get(c, {}).get("name", c), "amount": round(v, 2)}
                       for c, v in d.items() if abs(v) > EPS), key=lambda x: x["code"])

    operating_wc = _lines(buckets["operating"])
    investing = _lines(buckets["investing"])
    financing = _lines(buckets["financing"])
    net_income = round(sum(buckets["pnl"].values()), 2)
    wc_total = round(sum(l["amount"] for l in operating_wc), 2)
    operating_total = round(net_income + wc_total, 2)
    investing_total = round(sum(l["amount"] for l in investing), 2)
    financing_total = round(sum(l["amount"] for l in financing), 2)
    net_change = round(operating_total + investing_total + financing_total, 2)
    end_cash_r = round(end_cash, 2)
    begin_cash_r = round(begin_cash, 2)
    computed_end = round(begin_cash_r + net_change, 2)

    return {
        "period": {"start": start or "", "end": end or ""},
        "method": "journal_cash_classification",
        "allocation": "pro_rata_cash_side",
        "operating": {
            "label": "Arus Kas dari Aktivitas Operasi",
            "net_income": net_income,
            "net_income_label": "Penerimaan/pengeluaran kas atas pendapatan & beban",
            "working_capital": operating_wc,
            "total": operating_total,
        },
        "investing": {"label": "Arus Kas dari Aktivitas Investasi", "lines": investing, "total": investing_total},
        "financing": {"label": "Arus Kas dari Aktivitas Pendanaan", "lines": financing, "total": financing_total},
        "noncash_disclosure": {
            "label": "Transaksi investasi/pendanaan nonkas (tidak memengaruhi kas)",
            "lines": _lines(noncash)},
        "net_change": net_change,
        "begin_cash": begin_cash_r,
        "end_cash": computed_end,
        "end_cash_actual": end_cash_r,
        "reconciled": abs(computed_end - end_cash_r) < 0.5,
        "generated_at": now_iso(),
    }
