"""Tanya KN F0.1/F0.2 — periode WIB, pembanding, dan batas string tanggal (unit murni)."""
import sys
from datetime import date

sys.path.insert(0, "/app/backend")
from services.analytics_time import compare_period, resolve_period, to_wib_date  # noqa: E402

T = date(2026, 9, 24)  # Kamis


def _in(p, value):
    r = p.mongo_range()
    return r["$gte"] <= value < r["$lt"]


def test_order_2330_wib_stays_on_wib_date():
    assert to_wib_date("2026-09-24T16:30:00+00:00") == "2026-09-24"   # 23.30 WIB
    assert to_wib_date("2026-09-24T17:00:00+00:00") == "2026-09-25"   # 00.00 WIB
    p = resolve_period("today", today=T)
    assert p.start_utc == "2026-09-23T17:00:00+00:00" and p.end_utc == "2026-09-24T17:00:00+00:00"
    assert _in(p, "2026-09-24T16:30:00.123456+00:00")
    assert not _in(p, "2026-09-24T17:00:00.000001+00:00")
    assert not _in(p, "2026-09-23T16:59:59.999999+00:00")


def test_string_range_also_matches_ymd_fields():
    p = resolve_period("custom", "2026-09-10", "2026-09-12", today=T)
    assert _in(p, "2026-09-10") and _in(p, "2026-09-12")
    assert not _in(p, "2026-09-09") and not _in(p, "2026-09-13")


def test_presets_week_starts_monday():
    assert resolve_period("this_week", today=T).date_from == date(2026, 9, 21)
    lw = resolve_period("last_week", today=T)
    assert (lw.date_from, lw.date_to) == (date(2026, 9, 14), date(2026, 9, 20))
    lq = resolve_period("last_quarter", today=T)
    assert (lq.date_from, lq.date_to) == (date(2026, 4, 1), date(2026, 6, 30))
    assert resolve_period(None, today=T).preset == "mtd"
    l12 = resolve_period("last_12m", today=T)
    assert l12.date_from == date(2025, 10, 1)


def test_mtd_31_march_compares_with_february():
    p = resolve_period("mtd", today=date(2026, 3, 31))
    c = compare_period(p, "previous_period")
    assert (c.date_from, c.date_to) == (date(2026, 2, 1), date(2026, 2, 28))
    lm = compare_period(resolve_period("last_month", today=date(2026, 3, 15)), "previous_period")
    assert (lm.date_from, lm.date_to) == (date(2026, 1, 1), date(2026, 1, 31))


def test_leap_year():
    c = compare_period(resolve_period("mtd", today=date(2024, 3, 31)), "previous_period")
    assert c.date_to == date(2024, 2, 29)
    y = compare_period(resolve_period("custom", "2024-02-29", "2024-02-29", today=T), "same_period_last_year")
    assert y.date_from == date(2023, 2, 28)


def test_rolling_previous_period_same_length():
    p = resolve_period("last_7d", today=T)
    c = compare_period(p, "previous_period")
    assert c.days == 7 and c.date_to == date(2026, 9, 17)
    assert compare_period(p, "none") is None
