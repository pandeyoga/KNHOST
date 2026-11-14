"""KM-T1 (KM-04, keputusan K-24) — periode target insentif: bulan · triwulan · tahun, mengikuti tahun buku PT.

Bentuk periode (`sales_targets.period`):
    month    `YYYY-MM`
    quarter  `YYYY-Qn` — triwulan ke-n = tiga bulan ke-n sejak AWAL tahun buku PT; `YYYY` = tahun BERAKHIRNYA tahun buku
    year     `YYYY`    — tahun buku yang berakhir di tahun itu

Bulan tutup tahun buku = pengaturan `finance.fiscal_year_end_month` (lapisan PT). Contoh: bulan tutup 3 (Maret) →
tahun buku 2027 = April 2026 – Maret 2027, sehingga `2027-Q1` = 1 April – 30 Juni 2026.

Batas bulan dan tahun memakai `closing_service._period_bounds` (satu rumus batas periode, `02_STANDAR.md` §5 D6);
triwulan disusun dari awal tahun buku yang sama. Semua tanggal berupa tanggal WIB `YYYY-MM-DD`.
"""
from __future__ import annotations

import calendar
import re
from typing import List, Optional, Tuple

PERIOD_TYPES = ("month", "quarter", "year")
PERIOD_TYPE_LABEL = {"month": "Bulan", "quarter": "Triwulan", "year": "Tahun"}
#: Pesan 400 spesifikasi (periode tidak cocok dengan jenisnya).
PESAN_PERIODE = "Periode tidak sesuai jenisnya. Contoh: 2026-10, 2026-Q4, atau 2026."

_POLA = {
    "month": re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$"),
    "quarter": re.compile(r"^(\d{4})-Q([1-4])$"),
    "year": re.compile(r"^(\d{4})$"),
}


class PeriodeError(ValueError):
    """Periode atau jenis periode tidak sah (pesan siap tampil → 400)."""


def normalize(period_type: str, period: str) -> Tuple[str, str]:
    """(jenis, periode) yang sudah dibakukan; galat → `PeriodeError(PESAN_PERIODE)`."""
    pt = str(period_type or "").strip().lower()
    p = str(period or "").strip().upper()
    if pt not in PERIOD_TYPES or not _POLA[pt].match(p):
        raise PeriodeError(PESAN_PERIODE)
    return pt, p


async def fiscal_end_month(entity_id: Optional[str]) -> int:
    """Bulan tutup tahun buku PT (1–12) dari Pusat Pengaturan."""
    from services.config_resolver import value_of
    try:
        return max(1, min(12, int(await value_of("finance.fiscal_year_end_month", {"entity_id": entity_id}) or 12)))
    except (TypeError, ValueError):
        import config_registry
        return int(config_registry.default_of("finance.fiscal_year_end_month"))


def _add_month(y: int, m: int, n: int) -> Tuple[int, int]:
    idx = y * 12 + (m - 1) + n
    return idx // 12, idx % 12 + 1


def bounds_with(period_type: str, period: str, fy_end_month: int) -> Tuple[str, str]:
    """Batas periode (tanggal WIB awal, akhir) untuk bulan tutup tahun buku tertentu (fungsi murni)."""
    from services.closing_service import _period_bounds
    pt, p = normalize(period_type, period)
    if pt == "month":
        return _period_bounds("month", p, fy_end_month)
    if pt == "year":
        return _period_bounds("year", p, fy_end_month)
    y, q = int(p[:4]), int(p[-1])
    start, _end = _period_bounds("year", str(y), fy_end_month)
    sy, sm = int(start[:4]), int(start[5:7])
    ay, am = _add_month(sy, sm, (q - 1) * 3)
    zy, zm = _add_month(ay, am, 2)
    return f"{ay}-{am:02d}-01", f"{zy}-{zm:02d}-{calendar.monthrange(zy, zm)[1]:02d}"


async def period_bounds(period_type: str, period: str, entity_id: Optional[str]) -> Tuple[str, str]:
    """(awal, akhir) tanggal WIB `YYYY-MM-DD`; triwulan & tahun mengikuti tahun buku PT (K-24)."""
    pt, p = normalize(period_type, period)
    return bounds_with(pt, p, await fiscal_end_month(entity_id) if pt != "month" else 12)


def months_between(start: str, end: str) -> List[str]:
    """Daftar `YYYY-MM` dari tanggal awal sampai akhir (inklusif)."""
    y, m = int(start[:4]), int(start[5:7])
    zy, zm = int(end[:4]), int(end[5:7])
    out: List[str] = []
    while (y, m) <= (zy, zm):
        out.append(f"{y}-{m:02d}")
        y, m = _add_month(y, m, 1)
    return out


async def months_of(period_type: str, period: str, entity_id: Optional[str]) -> List[str]:
    """Bulan-bulan (`YYYY-MM`) yang termasuk periode itu."""
    a, z = await period_bounds(period_type, period, entity_id)
    return months_between(a, z)


def previous_period(period_type: str, period: str) -> str:
    """Periode sebelumnya dengan jenis yang sama (untuk "Salin dari periode sebelumnya")."""
    pt, p = normalize(period_type, period)
    if pt == "month":
        y, m = _add_month(int(p[:4]), int(p[5:7]), -1)
        return f"{y}-{m:02d}"
    if pt == "quarter":
        y, q = int(p[:4]), int(p[-1])
        return f"{y - 1}-Q4" if q == 1 else f"{y}-Q{q - 1}"
    return str(int(p) - 1)


def period_label(period_type: str, period: str) -> str:
    """Teks periode untuk manusia: "Oktober 2026", "Triwulan IV 2026", "Tahun buku 2026"."""
    from services.book_date import _BULAN
    pt, p = normalize(period_type, period)
    if pt == "month":
        return f"{_BULAN[int(p[5:7])]} {p[:4]}"
    if pt == "quarter":
        return f"Triwulan {('I', 'II', 'III', 'IV')[int(p[-1]) - 1]} {p[:4]}"
    return f"Tahun buku {p}"


def current_period_with(period_type: str, today: str, fy_end_month: int) -> str:
    """Periode berjalan (jenis itu) yang memuat tanggal `today` (`YYYY-MM-DD`), untuk bulan tutup tahun buku tertentu."""
    pt = str(period_type or "month").strip().lower()
    y, m = int(today[:4]), int(today[5:7])
    if pt == "month":
        return f"{y}-{m:02d}"
    e = max(1, min(12, int(fy_end_month or 12)))
    fy = y if (e == 12 or m <= e) else y + 1
    if pt == "year":
        return str(fy)
    start = bounds_with("year", str(fy), e)[0]
    offset = (y * 12 + m) - (int(start[:4]) * 12 + int(start[5:7]))
    return f"{fy}-Q{offset // 3 + 1}"


async def current_period(period_type: str, entity_id: Optional[str]) -> str:
    """Periode berjalan hari ini (tanggal WIB) untuk PT."""
    from services.book_date import tanggal_buku
    pt = str(period_type or "month").strip().lower()
    if pt not in PERIOD_TYPES:
        raise PeriodeError(PESAN_PERIODE)
    return current_period_with(pt, tanggal_buku(), await fiscal_end_month(entity_id) if pt != "month" else 12)
