"""AG-T2 (AG-03) — alat baca Asisten Keuangan: tiap alat = satu atau dua `GET` ke endpoint layar lewat `SelfApi`.

Modul ini TIDAK membaca database dan TIDAK menyusun cakupan sendiri (uji statik U15): izin, PT, cakupan data, dan
angka berasal dari endpoint yang sama dengan layar, dalam sesi pengguna yang bertanya. Hasil dipetakan ke bentuk hasil
Tanya KN (kolom, baris, total) ditambah keterangan wajib: `entity_label`, `period_label`, `notes`, `link`. Total dan
selisih diambil dari jawaban endpoint atau dihitung kode; model tidak menjumlah.

Alat bertanda teks bebas (`FREE_TEXT_TOOLS`) memuat uraian yang ditulis orang; isinya dibungkus `<<data … >>` sebelum
dikirim ke model, dan sesudah alat itu dipakai, alat tindakan ditolak sampai pesan pengguna berikutnya
(`ai_chat_service`).
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from services import analytics_catalog as cat
from services.ai_self_api import ENTITY_MESSAGE, SelfApi, SelfApiError
from services.analytics_time import fmt_id, now_wib, period_from_args

SOURCE_VERSION = "fin-v1"
#: Batas teknis pemindaian daftar jurnal (bukan aturan bisnis): berhenti dan katakan bila tercapai.
JOURNAL_SCAN_LIMIT = 2000
_PAGE = 200
FREE_TEXT_TOOLS = frozenset({"fin_journal_search", "fin_journal_get", "fin_account_ledger", "fin_bank_unmatched",
                             "fin_vendor_bills", "get_document"})
COMBINED_NOTE = "Penjumlahan beberapa PT, belum dieliminasi"
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


class FinanceToolError(ValueError):
    """Argumen alat tidak sah → pesan Bahasa Indonesia untuk model."""


@dataclass
class FinCall:
    api: SelfApi
    user: Dict[str, Any]
    ctx: Any
    session_id: Optional[str]
    scope: Dict[str, Any]   # `entity_scope.scope_meta` PT aktif permintaan (cadangan bila endpoint tidak menyebutnya)


# ── pembantu ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def data_text(v: Any) -> str:
    """Teks yang ditulis orang → dibungkus penanda data (bukan perintah) sebelum dikirim ke model."""
    s = str(v or "").replace("<<", "‹‹").replace(">>", "››").strip()
    return f"<<data {s} >>" if s else ""


def wrap_free_text(obj: Any, keys: Tuple[str, ...] = ("description", "notes", "note", "memo", "reason", "complaint_note",
                                                        "reject_reason", "remarks")) -> Any:
    if isinstance(obj, dict):
        return {k: (data_text(v) if k in keys and isinstance(v, str) and v else wrap_free_text(v, keys))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [wrap_free_text(v, keys) for v in obj]
    return obj


def _col(key, label, unit="", typ="metric"):
    return {"key": key, "label": label, "type": typ, "unit": unit}


def _txt(key, label):
    return _col(key, label, "", "dimension")


def _num(v: Any) -> float:
    try:
        return round(float(v or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _date_arg(args: Dict[str, Any], key: str) -> Optional[str]:
    v = args.get(key)
    if v in (None, ""):
        return None
    if not isinstance(v, str) or not _DATE_RE.match(v.strip()):
        raise FinanceToolError(f"Tanggal '{key}' harus berbentuk YYYY-MM-DD.")
    return v.strip()


def _period(args: Dict[str, Any]):
    try:
        return period_from_args(args.get("period") or {"preset": "mtd", "from": None, "to": None})
    except ValueError as exc:
        raise FinanceToolError(str(exc)) from exc


def _day_label(iso: Optional[str]) -> str:
    d = (iso or now_wib().date().isoformat())[:10]
    try:
        y, m, dd = (int(x) for x in d.split("-"))
        from datetime import date
        return fmt_id(date(y, m, dd))
    except ValueError:
        return d


def _scope_of(fc: FinCall, body: Any) -> Dict[str, Any]:
    meta = body.get("scope_meta") if isinstance(body, dict) else None
    return meta if isinstance(meta, dict) and meta.get("mode") else fc.scope


def _base_notes(scope: Dict[str, Any]) -> List[str]:
    return [COMBINED_NOTE] if scope.get("mode") == "combined" else []


def _limit(args: Dict[str, Any], default: int = 50) -> int:
    try:
        n = int(args.get("limit") or default)
    except (TypeError, ValueError):
        n = default
    return max(1, min(n, cat.ROW_RETURN_LIMIT))


async def _result(fc: FinCall, tool: str, args: Dict[str, Any], *, title: str, columns, rows, totals=None,
                  scope: Dict[str, Any], period_label: str, period: Optional[Dict[str, Any]] = None,
                  notes: Optional[List[str]] = None, link: Optional[Dict[str, Any]] = None, definition: str = "",
                  free_keys: Tuple[str, ...] = ()) -> Dict[str, Any]:
    """Simpan hasil (baris ASLI, untuk layar) dan kembalikan hasil untuk model (teks bebas dibungkus)."""
    from services.analytics_engine import save_result
    rows = list(rows or [])
    res = {"result_id": "r_" + uuid.uuid4().hex[:10], "title": title, "definition": definition,
           "period": period or {"label": period_label}, "entity_scope": None, "columns": columns,
           "rows": rows[:cat.ROW_RETURN_LIMIT], "totals": totals or {}, "compare": None, "row_count": len(rows),
           "truncated": len(rows) > cat.ROW_RETURN_LIMIT, "warnings": [], "denied": [], "source": SOURCE_VERSION,
           "entity_label": scope.get("label") or "", "period_label": period_label,
           "notes": [n for n in (_base_notes(scope) + list(notes or [])) if n],
           "link": link}
    await save_result(res, rows, tool, args, fc.user, fc.session_id)
    if free_keys:
        res = {**res, "rows": wrap_free_text(res["rows"], free_keys)}
    return res


def _link(view: str, nav_id: str = "", focus_type: str = "", focus_id: str = "", tab: str = "") -> Dict[str, Any]:
    out = {"view": view, "nav_id": nav_id or None, "focus_type": focus_type or None, "focus_id": focus_id or None}
    if tab:
        out["tab"] = tab
    return out


# ── jurnal & buku besar ───────────────────────────────────────────────────────────────────────────────────────────────
async def fin_journal_search(args, fc: FinCall):
    p = _period(args)
    lo, hi = p.date_from.isoformat(), p.date_to.isoformat()
    params = {"source": args.get("source_type") or None, "account_code": args.get("account_code") or None,
              "status": args.get("status") or None, "q": args.get("query") or None, "page_size": _PAGE}
    found: List[Dict[str, Any]] = []
    scanned, page, stopped = 0, 1, False
    while True:
        body = await fc.api.call("GET", "/api/gl/journal", params={**params, "page": page})
        items = body.get("items") or []
        for je in items:
            scanned += 1
            d = str(je.get("date") or "")[:10]
            if lo <= d <= hi:
                found.append(je)
            if scanned >= JOURNAL_SCAN_LIMIT:
                break
        if scanned >= JOURNAL_SCAN_LIMIT and body.get("has_more"):
            stopped = True
            break
        if not body.get("has_more") or not items:
            break
        page += 1
    found.sort(key=lambda j: (str(j.get("date") or ""), str(j.get("number") or "")), reverse=True)
    rows = [{"number": j.get("number"), "date": str(j.get("date") or "")[:10], "description": j.get("description") or "",
             "source": j.get("source_label") or j.get("source_type") or "", "status": j.get("status"),
             "total": _num(j.get("total_debit")), "entry_id": j.get("id")} for j in found]
    notes = [f"Rentang tanggal {fmt_id(p.date_from)} – {fmt_id(p.date_to)}"]
    if stopped:
        notes.append(f"Pencarian berhenti di {JOURNAL_SCAN_LIMIT} jurnal terbaru; persempit saringan untuk jurnal lebih lama")
    shown = rows[:_limit(args, 30)]
    return await _result(fc, "fin_journal_search", args, title="Jurnal", columns=[
        _txt("number", "Nomor jurnal"), _txt("date", "Tanggal"), _txt("description", "Keterangan"),
        _txt("source", "Sumber"), _txt("status", "Status"), _col("total", "Nilai", "idr")], rows=shown,
        totals={"count": len(rows), "total": round(sum(r["total"] for r in rows), 2)}, scope=fc.scope,
        period_label=p.label, period=p.to_dict(), notes=notes, link=_link("general-ledger", "ledger"),
        definition="Jurnal ber-status sesuai saringan, tanggal jurnal dalam rentang", free_keys=("description",))


async def fin_journal_get(args, fc: FinCall):
    ref = str(args.get("entry_id") or args.get("number") or "").strip()
    if not ref:
        raise FinanceToolError("Sebutkan nomor jurnal.")
    je = await fc.api.call("GET", f"/api/gl/journal/{ref}")
    rows = [{"account_code": ln.get("account_code"), "account_name": ln.get("account_name") or "",
             "description": ln.get("description") or "", "debit": _num(ln.get("debit")), "credit": _num(ln.get("credit"))}
            for ln in je.get("lines") or []]
    rows.append({"account_code": "", "account_name": "Keterangan jurnal", "description": je.get("description") or "",
                 "debit": None, "credit": None})
    return await _result(fc, "fin_journal_get", args, title=f"Jurnal {je.get('number') or ref}", columns=[
        _txt("account_code", "Kode akun"), _txt("account_name", "Akun"), _txt("description", "Keterangan"),
        _col("debit", "Debit", "idr"), _col("credit", "Kredit", "idr")], rows=rows,
        totals={"total_debit": _num(je.get("total_debit")), "total_credit": _num(je.get("total_credit"))},
        scope=fc.scope, period_label=_day_label(je.get("date")),
        notes=[f"Nomor jurnal {je.get('number') or ref}", f"Status {je.get('status') or '-'}"],
        link=_link("general-ledger", "ledger", "journal_entry", je.get("id") or ""), free_keys=("description",))


async def fin_account_ledger(args, fc: FinCall):
    code = str(args.get("account_code") or "").strip()
    if not code:
        raise FinanceToolError("Sebutkan kode akun.")
    as_of = _date_arg(args, "as_of")
    led = await fc.api.call("GET", f"/api/gl/accounts/{code}/ledger", params={"as_of": as_of})
    acc = led.get("account") or {}
    rows = [{"date": str(ln.get("date") or "")[:10], "number": ln.get("number"), "description": ln.get("description") or "",
             "debit": _num(ln.get("debit")), "credit": _num(ln.get("credit")), "running_balance": _num(ln.get("running_balance"))}
            for ln in led.get("lines") or []]
    scope = _scope_of(fc, led)
    return await _result(fc, "fin_account_ledger", args, title=f"Buku besar {acc.get('code') or code} {acc.get('name') or ''}".strip(),
                         columns=[_txt("date", "Tanggal"), _txt("number", "Nomor jurnal"), _txt("description", "Keterangan"),
                                  _col("debit", "Debit", "idr"), _col("credit", "Kredit", "idr"),
                                  _col("running_balance", "Saldo berjalan", "idr")], rows=rows,
                         totals={"balance": _num(led.get("balance")), "total_debit": _num(led.get("total_debit")),
                                 "total_credit": _num(led.get("total_credit")), "count": int(led.get("count") or 0)},
                         scope=scope, period_label=f"per {_day_label(as_of)}", notes=[f"Saldo per {_day_label(as_of)}"],
                         link=_link("general-ledger", "ledger"), free_keys=("description",))


async def fin_trial_balance(args, fc: FinCall):
    as_of = _date_arg(args, "as_of")
    tb = await fc.api.call("GET", "/api/gl/trial-balance", params={"as_of": as_of})
    rows = [{"code": r.get("code"), "name": r.get("name"), "debit_balance": _num(r.get("debit_balance")),
             "credit_balance": _num(r.get("credit_balance"))} for r in tb.get("rows") or []]
    lbl = _day_label(tb.get("as_of") or as_of)
    return await _result(fc, "fin_trial_balance", args, title="Neraca saldo", columns=[
        _txt("code", "Kode akun"), _txt("name", "Akun"), _col("debit_balance", "Saldo debit", "idr"),
        _col("credit_balance", "Saldo kredit", "idr")], rows=rows,
        totals={"total_debit": _num(tb.get("total_debit")), "total_credit": _num(tb.get("total_credit")),
                "account_count": int(tb.get("account_count") or 0)},
        scope=_scope_of(fc, tb), period_label=f"per {lbl}",
        notes=[f"Posisi per {lbl}"] + ([] if tb.get("balanced", True) else ["Neraca saldo tidak seimbang"]),
        link=_link("general-ledger", "ledger"))


# ── laporan keuangan ──────────────────────────────────────────────────────────────────────────────────────────────────
_FS_LINK = "fin-reports"


async def fin_income_statement(args, fc: FinCall):
    p = _period(args)
    st = await fc.api.call("GET", "/api/finance/income-statement",
                           params={"start": p.date_from.isoformat(), "end": p.date_to.isoformat()})
    rows = [{"section": s.get("label"), "account": ln.get("name") or ln.get("code"), "code": ln.get("code"),
             "amount": _num(ln.get("amount"))} for s in st.get("sections") or [] for ln in s.get("lines") or []]
    keys = (("revenue_total", "Total pendapatan"), ("cogs_total", "Total HPP"), ("gross_profit", "Laba kotor"),
            ("opex_total", "Total beban operasional"), ("operating_profit", "Laba usaha"), ("net_income", "Laba bersih"))
    rows += [{"section": "Ringkasan", "account": lbl, "code": "", "amount": _num(st.get(k))} for k, lbl in keys]
    return await _result(fc, "fin_income_statement", args, title="Laba rugi", columns=[
        _txt("section", "Bagian"), _txt("account", "Akun"), _col("amount", "Jumlah", "idr")], rows=rows,
        totals={k: _num(st.get(k)) for k, _ in keys}, scope=_scope_of(fc, st), period_label=p.label, period=p.to_dict(),
        notes=[f"Periode {fmt_id(p.date_from)} – {fmt_id(p.date_to)}", "Tanpa jurnal penutup"],
        link=_link("financial-statements", _FS_LINK, tab="pl"), definition="Laba rugi dari jurnal terposting (akrual)")


async def fin_balance_sheet(args, fc: FinCall):
    as_of, cmp_ = _date_arg(args, "as_of"), _date_arg(args, "compare_as_of")
    bs = await fc.api.call("GET", "/api/finance/balance-sheet", params={"as_of": as_of, "compare_as_of": cmp_})
    rows: List[Dict[str, Any]] = []
    for side, label in (("assets", "Aset"), ("liabilities", "Kewajiban")):
        for s in (bs.get(side) or {}).get("sections") or []:
            rows += [{"section": f"{label} · {s.get('label')}", "account": ln.get("name"), "amount": _num(ln.get("amount")),
                      **({"compare_amount": _num(ln.get("compare_amount"))} if cmp_ else {})} for ln in s.get("lines") or []]
    eq = bs.get("equity") or {}
    rows += [{"section": "Ekuitas", "account": ln.get("name"), "amount": _num(ln.get("amount")),
              **({"compare_amount": _num(ln.get("compare_amount"))} if cmp_ else {})} for ln in eq.get("lines") or []]
    rows.append({"section": "Ekuitas", "account": "Laba berjalan", "amount": _num(eq.get("current_earnings"))})
    keys = ("assets_total", "liabilities_total", "equity_total", "liabilities_equity_total")
    lbl = _day_label(bs.get("as_of") or as_of)
    cols = [_txt("section", "Bagian"), _txt("account", "Akun"), _col("amount", "Jumlah", "idr")]
    if cmp_:
        cols.append(_col("compare_amount", f"Per {_day_label(cmp_)}", "idr"))
    return await _result(fc, "fin_balance_sheet", args, title="Neraca", columns=cols, rows=rows,
                         totals={k: _num(bs.get(k)) for k in keys}, scope=_scope_of(fc, bs), period_label=f"per {lbl}",
                         notes=[f"Posisi per {lbl}"] + ([] if bs.get("balanced", True) else ["Neraca tidak seimbang"]),
                         link=_link("financial-statements", _FS_LINK, tab="bs"))


async def fin_cash_flow(args, fc: FinCall):
    p = _period(args)
    cf = await fc.api.call("GET", "/api/finance/cash-flow",
                           params={"start": p.date_from.isoformat(), "end": p.date_to.isoformat()})
    rows = [{"activity": (cf.get(k) or {}).get("label") or k, "amount": _num((cf.get(k) or {}).get("total"))}
            for k in ("operating", "investing", "financing")]
    totals = {"operating": rows[0]["amount"], "investing": rows[1]["amount"], "financing": rows[2]["amount"],
              "net_change": _num(cf.get("net_change")), "begin_cash": _num(cf.get("begin_cash")),
              "end_cash": _num(cf.get("end_cash"))}
    rows += [{"activity": "Kenaikan (penurunan) kas", "amount": totals["net_change"]},
             {"activity": "Kas awal periode", "amount": totals["begin_cash"]},
             {"activity": "Kas akhir periode", "amount": totals["end_cash"]}]
    return await _result(fc, "fin_cash_flow", args, title="Arus kas", columns=[_txt("activity", "Aktivitas"),
                                                                            _col("amount", "Jumlah", "idr")],
                         rows=rows, totals=totals, scope=_scope_of(fc, cf), period_label=p.label, period=p.to_dict(),
                         notes=[f"Periode {fmt_id(p.date_from)} – {fmt_id(p.date_to)}"]
                         + ([] if cf.get("reconciled", True) else ["Kas akhir belum cocok dengan saldo akun kas"]),
                         link=_link("financial-statements", _FS_LINK, tab="cf"))


async def fin_equity_changes(args, fc: FinCall):
    p = _period(args)
    eq = await fc.api.call("GET", "/api/finance/equity-changes",
                           params={"start": p.date_from.isoformat(), "end": p.date_to.isoformat()})
    rows = [{"code": c.get("code"), "name": c.get("name"), "begin": _num(c.get("begin")), "movement": _num(c.get("movement")),
             "end": _num(c.get("end"))} for c in eq.get("components") or []]
    keys = ("begin_total", "movement_total", "end_total", "net_income")
    return await _result(fc, "fin_equity_changes", args, title="Perubahan ekuitas", columns=[
        _txt("code", "Kode akun"), _txt("name", "Komponen"), _col("begin", "Awal", "idr"), _col("movement", "Mutasi", "idr"),
        _col("end", "Akhir", "idr")], rows=rows, totals={k: _num(eq.get(k)) for k in keys}, scope=_scope_of(fc, eq),
        period_label=p.label, period=p.to_dict(), notes=[f"Periode {fmt_id(p.date_from)} – {fmt_id(p.date_to)}"],
        link=_link("financial-statements", _FS_LINK, tab="eq"))


# ── piutang & hutang ──────────────────────────────────────────────────────────────────────────────────────────────────
_AR_DUE_NOTE = "Jatuh tempo dihitung dari surat jalan pertama ditambah termin; pesanan belum dikirim belum jatuh tempo"
_BUCKETS = (("current", "Belum jatuh tempo"), ("b1_30", "1–30 hari"), ("b31_60", "31–60 hari"),
            ("b61_90", "61–90 hari"), ("b90_plus", "> 90 hari"))


def _ar_scope(fc: FinCall, body: Dict[str, Any]) -> Dict[str, Any]:
    ids = body.get("entity_ids") or []
    if len(ids) > 1:
        return {**fc.scope, "mode": "combined"}
    return fc.scope


async def fin_ar_aging(args, fc: FinCall):
    as_of = _date_arg(args, "as_of")
    ag = await fc.api.call("GET", "/api/ar/aging", params={"as_of": as_of, "sales_id": args.get("sales_id") or None})
    rows = [{"customer": r.get("customer_name"), "customer_id": r.get("customer_id"),
             "sales_person": r.get("assigned_sales_name") or "", **{k: _num(r.get(k)) for k, _ in _BUCKETS},
             "outstanding": _num(r.get("outstanding")), "overdue": _num(r.get("overdue")),
             "oldest_days": int(r.get("oldest_days") or 0)} for r in ag.get("customers") or []]
    tot = ag.get("totals") or {}
    lbl = _day_label(as_of)
    return await _result(fc, "fin_ar_aging", args, title="Umur piutang", columns=[
        _txt("customer", "Pelanggan"), _txt("sales_person", "Sales"), *[_col(k, l, "idr") for k, l in _BUCKETS],
        _col("outstanding", "Sisa tagihan", "idr"), _col("overdue", "Lewat jatuh tempo", "idr"),
        _col("oldest_days", "Telat terlama (hari)", "count")], rows=rows[:_limit(args, 50)],
        totals={"total": _num(tot.get("total")), "overdue": _num(tot.get("overdue")),
                **{k: _num(tot.get(k)) for k, _ in _BUCKETS}, "customers": int(tot.get("customers") or 0),
                "orders": int(tot.get("orders") or 0)},
        scope=_ar_scope(fc, ag), period_label=f"per {lbl}", notes=[f"Posisi per {lbl}", _AR_DUE_NOTE],
        link=_link("ar-aging", "ar-aging"))


async def fin_ar_customer(args, fc: FinCall):
    cid = str(args.get("customer_id") or "").strip()
    if not cid:
        raise FinanceToolError("Sebutkan pelanggan (id dari find_entities).")
    as_of = _date_arg(args, "as_of")
    d = await fc.api.call("GET", f"/api/ar/aging/{cid}", params={"as_of": as_of})
    name = d.get("customer_name") or ""
    rows = [{"customer": name, "number": o.get("order_number"), "due_date": o.get("due_date") or "belum dikirim",
             "days_late": int(o.get("days_late") or 0), "bucket": o.get("bucket") or "",
             "outstanding": _num(o.get("outstanding"))} for o in d.get("items") or []]
    tot = d.get("totals") or {}
    lbl = _day_label(as_of)
    basis = {o.get("due_basis") for o in d.get("items") or []}
    notes = [f"Posisi per {lbl}", _AR_DUE_NOTE if "first_sj" in basis or not basis else
             "Pesanan belum dikirim, jadi belum jatuh tempo"]
    return await _result(fc, "fin_ar_customer", args, title="Piutang pelanggan", columns=[
        _txt("customer", "Pelanggan"), _txt("number", "Nomor pesanan"), _txt("due_date", "Jatuh tempo"),
        _col("days_late", "Hari terlambat", "count"), _col("outstanding", "Sisa tagihan", "idr")], rows=rows,
        totals={"total": _num(tot.get("total")), "overdue": _num(tot.get("overdue")), "orders": len(rows)},
        scope=fc.scope, period_label=f"per {lbl}", notes=notes, link=_link("ar-aging", "ar-aging", "customer", cid))


async def fin_ap_summary(args, fc: FinCall):
    ap = await fc.api.call("GET", "/api/vendor-bills/payables/summary")
    rows = [{"supplier": s.get("supplier_name") or "", "outstanding": _num(s.get("outstanding")),
             "bills": int(s.get("bill_count") or 0)} for s in ap.get("by_supplier") or []]
    aging = ap.get("aging") or {}
    return await _result(fc, "fin_ap_summary", args, title="Ringkasan hutang", columns=[
        _txt("supplier", "Pemasok"), _col("outstanding", "Sisa hutang", "idr"), _col("bills", "Tagihan", "count")],
        rows=rows, totals={"total_outstanding": _num(ap.get("total_outstanding")),
                           **{f"aging_{k}": _num(v) for k, v in aging.items()}},
        scope=fc.scope, period_label="saat ini", notes=["Posisi saat ini; tidak bisa per tanggal lampau"],
        link=_link("vendor-bills", "accounts-payable"))


async def fin_vendor_bills(args, fc: FinCall):
    status = args.get("status") or None
    lim = _limit(args, 30)
    body = await fc.api.call("GET", "/api/vendor-bills", params={"status": status, "page": 1, "page_size": min(lim, _PAGE)})
    rows = [{"number": b.get("bill_number"), "supplier": b.get("supplier_name") or "", "bill_date": str(b.get("bill_date") or "")[:10],
             "due_date": str(b.get("due_date") or "")[:10], "status": b.get("status"),
             "total": _num(b.get("grand_total") or b.get("total_amount")), "paid": _num(b.get("amount_paid")),
             "outstanding": _num(b.get("outstanding") if b.get("outstanding") is not None
                                 else _num(b.get("grand_total") or b.get("total_amount")) - _num(b.get("amount_paid"))),
             "notes": b.get("notes") or ""} for b in body.get("items") or []]
    return await _result(fc, "fin_vendor_bills", args, title="Tagihan pemasok", columns=[
        _txt("number", "Nomor tagihan"), _txt("supplier", "Pemasok"), _txt("bill_date", "Tanggal"),
        _txt("due_date", "Jatuh tempo"), _txt("status", "Status"), _col("total", "Nilai", "idr"),
        _col("outstanding", "Sisa", "idr")], rows=rows,
        totals={"count": int(body.get("total") or len(rows)), "outstanding": round(sum(r["outstanding"] for r in rows), 2)},
        scope=fc.scope, period_label="saat ini",
        notes=[f"Status disaring: {status}" if status else "Semua status"]
        + ([f"Menampilkan {len(rows)} dari {body.get('total')} tagihan"] if body.get("has_more") else []),
        link=_link("vendor-bills", "accounts-payable"), free_keys=("notes",))


# ── kas & bank ────────────────────────────────────────────────────────────────────────────────────────────────────────
async def fin_cash_position(args, fc: FinCall):
    cp = await fc.api.call("GET", "/api/bank-accounts/position")
    rows = [{"code": a.get("code"), "name": a.get("name"), "balance": _num(a.get("balance"))} for a in cp.get("gl_accounts") or []]
    un = cp.get("unlinked") or {}
    return await _result(fc, "fin_cash_position", args, title="Posisi kas & bank", columns=[
        _txt("code", "Kode akun"), _txt("name", "Akun"), _col("balance", "Saldo", "idr")], rows=rows,
        totals={"gl_total": _num(cp.get("gl_total")), "unlinked_count": int(un.get("count") or 0),
                "unlinked_net": _num(un.get("net"))},
        scope=fc.scope, period_label="saat ini", notes=["Saldo buku besar akun kas dan bank saat ini"],
        link=_link("bank-accounts", "cash-bank"))


async def fin_bank_unmatched(args, fc: FinCall):
    acc = str(args.get("bank_account_id") or "").strip()
    if not acc:
        raise FinanceToolError("Sebutkan rekening bank.")
    p = _period(args)
    rng = {"bank_account_id": acc, "start": p.date_from.isoformat(), "end": p.date_to.isoformat()}
    lines = await fc.api.call("GET", "/api/bank-reconciliation/lines", params={**rng, "status": args.get("status") or "unmatched"})
    summ = await fc.api.call("GET", "/api/bank-reconciliation/summary", params=rng)
    rows = [{"date": str(ln.get("stmt_date") or "")[:10], "description": ln.get("description") or "",
             "direction": "masuk" if ln.get("direction") == "in" else "keluar", "amount": _num(ln.get("amount")),
             "status": ln.get("status") or "", "line_id": ln.get("id")} for ln in (lines or [])]
    st = summ.get("statement") or {}
    return await _result(fc, "fin_bank_unmatched", args, title="Mutasi bank belum cocok", columns=[
        _txt("date", "Tanggal"), _txt("description", "Keterangan"), _txt("direction", "Arah"), _col("amount", "Jumlah", "idr"),
        _txt("status", "Status")], rows=rows[:_limit(args, 50)],
        totals={"lines": len(rows), "statement_in": _num(st.get("in")), "statement_out": _num(st.get("out")),
                "unmatched_lines": int(summ.get("unmatched_lines") or 0) if not isinstance(summ.get("unmatched_lines"), list)
                else len(summ.get("unmatched_lines"))},
        scope=fc.scope, period_label=p.label, period=p.to_dict(),
        notes=[f"Rekening {summ.get('account_name') or acc}", f"Rentang tanggal {fmt_id(p.date_from)} – {fmt_id(p.date_to)}"],
        link=_link("bank-reconciliation", "cash-bank"), free_keys=("description",))


async def fin_bank_candidates(args, fc: FinCall):
    line_id = str(args.get("line_id") or "").strip()
    if not line_id:
        raise FinanceToolError("Sebutkan baris mutasi bank.")
    body = await fc.api.call("GET", f"/api/bank-reconciliation/lines/{line_id}/candidates")
    rows = [{"kind": c.get("kind") or c.get("type") or "", "number": c.get("number") or c.get("ref") or "",
             "date": str(c.get("date") or "")[:10], "amount": _num(c.get("amount")), "score": _num(c.get("score"))}
            for c in body.get("candidates") or []]
    return await _result(fc, "fin_bank_candidates", args, title="Saran pencocokan mutasi bank", columns=[
        _txt("kind", "Jenis"), _txt("number", "Nomor"), _txt("date", "Tanggal"), _col("amount", "Jumlah", "idr"),
        _col("score", "Skor", "count")], rows=rows, totals={"candidates": len(rows)}, scope=fc.scope,
        period_label="saat ini", notes=["Saran pencocokan, belum dicocokkan"], link=_link("bank-reconciliation", "cash-bank"))


# ── periode & posting ─────────────────────────────────────────────────────────────────────────────────────────────────
async def fin_period_status(args, fc: FinCall):
    day = _date_arg(args, "date") or now_wib().date().isoformat()
    st = await fc.api.call("GET", "/api/finance/closing/status", params={"date": day})
    closings = await fc.api.call("GET", "/api/finance/closing")
    rows = [{"period": c.get("period_label") or c.get("period_key"), "status": c.get("status"),
             "closed_at": str(c.get("closed_at") or "")[:10], "net_income": _num(c.get("net_income"))}
            for c in (closings or [])[:24]]
    closed = bool(st.get("closed"))
    return await _result(fc, "fin_period_status", args, title="Status periode", columns=[
        _txt("period", "Periode"), _txt("status", "Status"), _txt("closed_at", "Ditutup"), _col("net_income", "Laba ditutup", "idr")],
        rows=rows, totals={"periods": len(rows)}, scope=fc.scope, period_label=_day_label(day),
        notes=[f"Tanggal yang diperiksa {_day_label(day)}: {'periode tertutup' if closed else 'periode terbuka'}"]
        + ([f"Periode tertutup: {st.get('period_label')}"] if closed and st.get("period_label") else []),
        link=_link("closing", "closing"))


async def fin_posting_failures(args, fc: FinCall):
    body = await fc.api.call("GET", "/api/finance/posting-failures", params={"page": 1, "page_size": _limit(args, 50)})
    labels = body.get("labels") or {}
    rows = [{"kind": labels.get(r.get("kind"), r.get("kind_label") or ""), "number": r.get("number") or "",
             "date": str(r.get("date") or "")[:10], "error": r.get("error") or r.get("gl_error") or ""}
            for r in body.get("items") or []]
    counts = body.get("counts") or {}
    return await _result(fc, "fin_posting_failures", args, title="Posting gagal", columns=[
        _txt("kind", "Jenis dokumen"), _txt("number", "Nomor"), _txt("date", "Tanggal"), _txt("error", "Sebab")], rows=rows,
        totals={"total": int(body.get("total") or 0), **{f"count_{k}": int(v or 0) for k, v in counts.items() if v}},
        scope=fc.scope, period_label="saat ini",
        notes=["Hanya jenis dokumen yang tercakup panel: " + ", ".join(labels.get(k, k) for k in counts)],
        link=_link("posting-failures", "closing"))


# ── antar-PT & konsolidasi ────────────────────────────────────────────────────────────────────────────────────────────
async def fin_interco_balances(args, fc: FinCall):
    accs = await fc.api.call("GET", "/api/interco/accounts")
    rows = [{"book": a.get("from_entity_name") or "", "partner": a.get("to_entity_name") or "",
             "side": "Piutang" if a.get("role") == "receivable" else "Utang",
             "outstanding": _num(a.get("outstanding")), "open_count": int(a.get("open_count") or 0)} for a in (accs or [])]
    return await _result(fc, "fin_interco_balances", args, title="Saldo antar-PT", columns=[
        _txt("book", "Buku PT"), _txt("partner", "PT pasangan"), _txt("side", "Sisi"), _col("outstanding", "Saldo", "idr"),
        _col("open_count", "Dokumen terbuka", "count")], rows=rows,
        totals={"pairs": len(rows), "outstanding_ar": round(sum(r["outstanding"] for r in rows if r["side"] == "Piutang"), 2),
                "outstanding_ap": round(sum(r["outstanding"] for r in rows if r["side"] == "Utang"), 2)},
        scope=fc.scope, period_label="saat ini",
        notes=["Pasangan PT dibaca dari sisi masing-masing", "Saldo dua sisi belum tentu sama"],
        link=_link("interco-transactions", "interco-transactions"))


async def fin_elimination_candidates(args, fc: FinCall):
    as_of = _date_arg(args, "as_of")
    body = await fc.api.call("GET", "/api/finance/consolidation/ic-candidates", params={"as_of": as_of})
    rows = [{"entity": pe.get("short_name") or "", "code": c.get("account_code") or "", "account": c.get("account_name") or "",
             "balance": _num(pe.get("balance"))} for c in body.get("candidates") or [] for pe in c.get("per_entity") or []]
    lbl = _day_label(body.get("as_of") or as_of)
    return await _result(fc, "fin_elimination_candidates", args, title="Usulan eliminasi antar-PT", columns=[
        _txt("entity", "PT"), _txt("code", "Kode akun"), _txt("account", "Akun"), _col("balance", "Saldo", "idr")], rows=rows,
        totals={"candidates": len(body.get("candidates") or []), "suggested_lines": len(body.get("suggested_lines") or []),
                "total_net": round(sum(_num(c.get("total_net")) for c in body.get("candidates") or []), 2)}, scope=fc.scope,
        period_label=f"per {lbl}", notes=["Usulan eliminasi, belum dibukukan", f"Posisi per {lbl}"],
        link=_link("consolidation", _FS_LINK))


# ── pajak & anggaran ──────────────────────────────────────────────────────────────────────────────────────────────────
async def fin_tax_invoices(args, fc: FinCall):
    status = args.get("status") or None
    body = await fc.api.call("GET", "/api/tax-invoices", params={"status": status})
    items = list(body or [])
    rows = [{"number": f.get("number") or f.get("nsfp") or "", "date": str(f.get("invoice_date") or f.get("created_at") or "")[:10],
             "customer": f.get("customer_name") or "", "status": f.get("status") or "", "dpp": _num(f.get("dpp")),
             "ppn": _num(f.get("ppn") or f.get("ppn_amount"))} for f in items[:_limit(args, 50)]]
    return await _result(fc, "fin_tax_invoices", args, title="Faktur pajak keluaran", columns=[
        _txt("number", "Nomor faktur"), _txt("date", "Tanggal"), _txt("customer", "Pelanggan"), _txt("status", "Status"),
        _col("dpp", "DPP", "idr"), _col("ppn", "PPN", "idr")], rows=rows,
        totals={"count": len(items), "dpp": round(sum(_num(f.get("dpp")) for f in items), 2),
                "ppn": round(sum(_num(f.get("ppn") or f.get("ppn_amount")) for f in items), 2)},
        scope=fc.scope, period_label="saat ini", notes=[f"Status disaring: {status}" if status else "Semua status"],
        link=_link("tax-invoices", "tax-hub"))


async def fin_vat_summary(args, fc: FinCall):
    masa = str(args.get("tax_period") or "").strip() or now_wib().strftime("%Y-%m")
    if not _MONTH_RE.match(masa):
        raise FinanceToolError("Masa pajak harus berbentuk YYYY-MM.")
    v = await fc.api.call("GET", "/api/tax/vat-summary", params={"period": masa})
    k, m = v.get("keluaran") or {}, v.get("masukan") or {}
    rows = [{"kind": "PPN keluaran", "dpp": _num(k.get("dpp")), "ppn": _num(k.get("ppn")), "count": int(k.get("count") or 0)},
            {"kind": "PPN masukan", "dpp": _num(m.get("dpp")), "ppn": _num(m.get("ppn")), "count": int(m.get("count") or 0)}]
    return await _result(fc, "fin_vat_summary", args, title="Rekap PPN", columns=[
        _txt("kind", "Jenis"), _col("dpp", "DPP", "idr"), _col("ppn", "PPN", "idr"), _col("count", "Faktur", "count")], rows=rows,
        totals={"ppn_keluaran": rows[0]["ppn"], "ppn_masukan": rows[1]["ppn"], "net_ppn": _num(v.get("net_ppn"))},
        scope=fc.scope, period_label=f"masa {masa}",
        notes=[f"Masa pajak {masa}", v.get("position_label") or ""], link=_link("cs-pajak", "tax-hub"))


async def fin_budget_vs_actual(args, fc: FinCall):
    try:
        year = int(args.get("year") or now_wib().year)
    except (TypeError, ValueError) as exc:
        raise FinanceToolError("Tahun anggaran harus angka.") from exc
    b = await fc.api.call("GET", "/api/finance/budget-vs-actual", params={"year": year})
    rows = [{"key": r.get("label") or r.get("key") or r.get("account_name") or "", "budget": _num(r.get("budget")),
             "actual": _num(r.get("actual")), "remaining": _num(r.get("remaining")), "used_pct": r.get("used_pct")}
            for r in b.get("rows") or []]
    tot = b.get("totals") or {}
    return await _result(fc, "fin_budget_vs_actual", args, title="Anggaran vs realisasi", columns=[
        _txt("key", "Pos anggaran"), _col("budget", "Anggaran", "idr"), _col("actual", "Realisasi", "idr"),
        _col("remaining", "Sisa", "idr"), _col("used_pct", "Terpakai %", "pct")], rows=rows,
        totals={k: _num(tot.get(k)) for k in ("budget", "actual", "committed", "remaining", "variance")},
        scope=_scope_of(fc, b), period_label=f"tahun {year}", notes=[f"Tahun anggaran {year}"],
        link=_link("budget", _FS_LINK))


Tool = Callable[[Dict[str, Any], FinCall], Awaitable[Dict[str, Any]]]
TOOLS: Dict[str, Tool] = {fn.__name__: fn for fn in (
    fin_journal_search, fin_journal_get, fin_account_ledger, fin_trial_balance, fin_income_statement, fin_balance_sheet,
    fin_cash_flow, fin_equity_changes, fin_ar_aging, fin_ar_customer, fin_ap_summary, fin_vendor_bills, fin_cash_position,
    fin_bank_unmatched, fin_bank_candidates, fin_period_status, fin_posting_failures, fin_interco_balances,
    fin_elimination_candidates, fin_tax_invoices, fin_vat_summary, fin_budget_vs_actual)}


async def execute(tool: str, args: Dict[str, Any], fc: FinCall) -> Dict[str, Any]:
    """Jalankan satu alat keuangan. Galat endpoint (403 izin, 404, 400) → `{"error": pesan endpoint}` untuk model."""
    fn = TOOLS.get(tool)
    if not fn:
        return {"error": f"Alat tidak dikenal: {tool}"}
    args = dict(args or {})
    if "entity_id" in args:   # N1 — PT dari sesi; ditolak lewat aturan pintu yang sama (tanpa memanggil aplikasi)
        return {"error": ENTITY_MESSAGE, "status": 400}
    try:
        return await fn(args, fc)
    except SelfApiError as exc:
        return {"error": exc.message, "status": exc.status}
    except FinanceToolError as exc:
        return {"error": str(exc)}
