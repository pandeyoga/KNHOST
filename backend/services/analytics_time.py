"""Tanya KN F0.1 — periode analitik dalam WIB (Asia/Jakarta) → batas UTC.

Semua tanggal transaksi disimpan sebagai teks ISO UTC (`now_iso()`); sebagian field lama
berformat `YYYY-MM-DD`. Batas yang dihasilkan di sini (`start_utc`, `end_utc`, eksklusif)
berupa teks ISO tanpa mikrodetik sehingga perbandingan string di Mongo benar untuk
KEDUA format (lihat `DATE_FIELDS` dan test `test_analytics_time.py`).
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

WIB = ZoneInfo("Asia/Jakarta")

PRESETS = ("today", "yesterday", "this_week", "last_week", "mtd", "last_month", "qtd",
           "last_quarter", "ytd", "last_year", "last_7d", "last_30d", "last_90d", "last_12m", "custom")
COMPARES = ("none", "previous_period", "same_period_last_year")

# F0.2 — format tanggal per field. "iso_utc" = teks ISO UTC; "ymd" = YYYY-MM-DD (tanggal WIB);
# "mixed" = data lama bisa keduanya. Batas ISO dari `Period` benar untuk ketiganya karena
# "YYYY-MM-DD" (hari D) selalu berada di antara "(D-1)T17:00:00" dan "DT17:00:00".
DATE_FIELDS: Dict[str, str] = {
    "sales_orders.created_at": "iso_utc",
    "credit_notes.created_at": "iso_utc",
    "ar_receipts.receipt_date": "mixed",
    "journal_entries.date": "mixed",
    "vendor_bills.bill_date": "mixed",
    "vendor_bills.due_date": "ymd",
    "purchase_orders.created_at": "iso_utc",
    "shipments.created_at": "iso_utc",
    "goods_receipts.receipt_date": "mixed",
    "inventory_rolls.created_at": "iso_utc",
}

_LABELS = {
    "today": "Hari ini", "yesterday": "Kemarin", "this_week": "Minggu ini", "last_week": "Minggu lalu",
    "mtd": "Bulan ini", "last_month": "Bulan lalu", "qtd": "Kuartal ini", "last_quarter": "Kuartal lalu",
    "ytd": "Tahun ini", "last_year": "Tahun lalu", "last_7d": "7 hari terakhir",
    "last_30d": "30 hari terakhir", "last_90d": "90 hari terakhir", "last_12m": "12 bulan terakhir",
    "custom": "Periode khusus",
}
_BULAN = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


@dataclass(frozen=True)
class Period:
    preset: str
    date_from: date   # inklusif, tanggal WIB
    date_to: date     # inklusif, tanggal WIB

    @property
    def start_utc(self) -> str:
        return wib_midnight_utc(self.date_from)

    @property
    def end_utc(self) -> str:
        return wib_midnight_utc(self.date_to + timedelta(days=1))

    @property
    def days(self) -> int:
        return (self.date_to - self.date_from).days + 1

    @property
    def label(self) -> str:
        return f"{_LABELS.get(self.preset, self.preset)} ({fmt_id(self.date_from)} – {fmt_id(self.date_to)})"

    def mongo_range(self) -> Dict[str, str]:
        return {"$gte": self.start_utc, "$lt": self.end_utc}

    def to_dict(self) -> Dict[str, Any]:
        return {"preset": self.preset, "from": self.date_from.isoformat(), "to": self.date_to.isoformat(),
                "tz": "Asia/Jakarta", "label": self.label}


def fmt_id(d: date) -> str:
    return f"{d.day} {_BULAN[d.month - 1]} {d.year}"


def wib_midnight_utc(d: date) -> str:
    return datetime.combine(d, time(0), WIB).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def now_wib() -> datetime:
    return datetime.now(WIB)


def to_wib_date(value: Any) -> Optional[str]:
    """Teks ISO UTC / YYYY-MM-DD / datetime → tanggal WIB `YYYY-MM-DD`."""
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(WIB).date().isoformat()
    s = str(value)
    if len(s) == 10:
        return s
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return s[:10]
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(WIB).date().isoformat()


def _month_end(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def _add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    y += d.year
    m += 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _q_start(d: date) -> date:
    return date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)


def resolve_period(preset: Optional[str], date_from: Optional[str] = None, date_to: Optional[str] = None,
                   today: Optional[date] = None) -> Period:
    """Preset/tanggal → `Period`. Bawaan (preset kosong) = `mtd`."""
    t = today or now_wib().date()
    p = preset or ("custom" if (date_from or date_to) else "mtd")
    if p not in PRESETS:
        raise ValueError(f"Preset periode tidak dikenal: {p}")
    if p == "custom":
        if not date_from:
            raise ValueError("Periode khusus wajib punya tanggal awal (YYYY-MM-DD)")
        a = date.fromisoformat(date_from)
        b = date.fromisoformat(date_to) if date_to else t
        if b < a:
            raise ValueError("Tanggal akhir periode lebih awal dari tanggal awal")
        return Period(p, a, b)
    if p == "today":
        return Period(p, t, t)
    if p == "yesterday":
        y = t - timedelta(days=1)
        return Period(p, y, y)
    if p == "this_week":
        return Period(p, t - timedelta(days=t.weekday()), t)
    if p == "last_week":
        s = t - timedelta(days=t.weekday() + 7)
        return Period(p, s, s + timedelta(days=6))
    if p == "mtd":
        return Period(p, t.replace(day=1), t)
    if p == "last_month":
        e = t.replace(day=1) - timedelta(days=1)
        return Period(p, e.replace(day=1), e)
    if p == "qtd":
        return Period(p, _q_start(t), t)
    if p == "last_quarter":
        e = _q_start(t) - timedelta(days=1)
        return Period(p, _q_start(e), e)
    if p == "ytd":
        return Period(p, date(t.year, 1, 1), t)
    if p == "last_year":
        return Period(p, date(t.year - 1, 1, 1), date(t.year - 1, 12, 31))
    if p == "last_12m":
        return Period(p, _add_months(t.replace(day=1), -11), t)
    n = {"last_7d": 7, "last_30d": 30, "last_90d": 90}[p]
    return Period(p, t - timedelta(days=n - 1), t)


def _shift_years(d: date, n: int) -> date:
    try:
        return d.replace(year=d.year + n)
    except ValueError:  # 29 Feb → 28 Feb
        return d.replace(year=d.year + n, day=28)


def compare_period(p: Period, mode: str) -> Optional[Period]:
    """Periode pembanding. `previous_period`:
    - satuan kalender penuh (last_week/last_month/last_quarter/last_year) → satuan sebelumnya penuh;
    - "sampai hari ini" (this_week/mtd/qtd/ytd) → hari yang sama di satuan sebelumnya
      (31 Mar mtd → 1–28/29 Feb);
    - selain itu → panjang sama tepat sebelumnya.
    """
    if mode in (None, "", "none"):
        return None
    if mode == "same_period_last_year":
        return Period(p.preset, _shift_years(p.date_from, -1), _shift_years(p.date_to, -1))
    if mode != "previous_period":
        raise ValueError(f"Perbandingan tidak dikenal: {mode}")
    a, b = p.date_from, p.date_to
    if p.preset in ("this_week", "last_week"):
        return Period(p.preset, a - timedelta(days=7), b - timedelta(days=7))
    if p.preset in ("mtd", "last_month"):
        s = _add_months(a, -1)
        e = _month_end(s.year, s.month) if p.preset == "last_month" else min(
            _add_months(b, -1), _month_end(s.year, s.month))
        return Period(p.preset, s, e)
    if p.preset in ("qtd", "last_quarter"):
        s = _add_months(a, -3)
        qe = _add_months(s, 2)
        qe = _month_end(qe.year, qe.month)
        e = qe if p.preset == "last_quarter" else min(_add_months(b, -3), qe)
        return Period(p.preset, s, e)
    if p.preset in ("ytd", "last_year", "last_12m"):
        return Period(p.preset, _shift_years(a, -1), _shift_years(b, -1))
    return Period(p.preset, a - timedelta(days=p.days), a - timedelta(days=1))


def period_from_args(arg: Optional[Dict[str, Any]], today: Optional[date] = None) -> Period:
    arg = arg or {}
    return resolve_period(arg.get("preset"), arg.get("from"), arg.get("to"), today=today)


def period_dict(p: Optional[Period]) -> Optional[Dict[str, Any]]:
    return p.to_dict() if p else None


__all__ = ["Period", "resolve_period", "compare_period", "period_from_args", "to_wib_date",
           "wib_midnight_utc", "DATE_FIELDS", "PRESETS", "COMPARES", "WIB", "asdict", "period_dict"]
