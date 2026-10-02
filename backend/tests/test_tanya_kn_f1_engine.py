"""Tanya KN F1 — fakta penjualan & mesin kueri dicocokkan dengan hitungan manual.

Fixture: pesanan TEST_ bertanggal Feb–Apr 2025 (tidak bersinggungan dengan data seed).
Maret 2025, entitas KSC (hitung manual):
  SO A 10 Mar — tim sales 60/40 (sales_01/sales_02), diskon baris 100.000 + diskon pesanan 10%,
       PPN DPP nilai lain → bersih 1.350.000 · kotor 1.600.000 · diskon 250.000 · PPN 148.500 · HPP 800.000
  SO F 15 Mar 23.59 WIB — tanpa sales, pembuat admin → sales pelanggan (sales_03) · bersih 2.000.000 · 20 kg
  SO B 1 Apr 00.30 WIB (31 Mar UTC) → BUKAN Maret · SO C batal · SO D sampel · SO E entitas Kanda
  SO G 10 Feb — pelanggan Toko Kain (pembanding) bersih 500.000
"""
import os
import sys

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, "/app/backend/tests")
sys.path.insert(0, "/app/backend")
from test_inbound_complete_characterization import BASE  # noqa: E402
from services.analytics_facts import attribute_sales, build_rows  # noqa: E402

MAR = {"preset": "custom", "from": "2025-03-01", "to": "2025-03-31"}


def _item(pid, lt, qty, unit, cost, disc=0.0, line="printing"):
    return {"product_id": pid, "product_name": pid, "line_total": lt, "discount_amount": disc, "base_quantity": qty,
            "quantity": qty, "base_unit": unit, "unit_cost": cost, "line_code": line, "category": "Uji"}


def _so(sid, ent, cust, created, grand, ppn, total, items, status="confirmed", **kw):
    return {"id": f"TEST_{sid}", "number": f"TEST/SO-{sid}", "entity_id": ent, "customer_id": cust,
            "customer_name": cust, "created_at": created, "updated_at": created, "status": status,
            "order_type": kw.pop("order_type", "regular"), "grand_total": grand, "ppn_amount": ppn,
            "total_amount": total, "items": items, "payment_status": "unpaid", **kw}


FIXTURE = [
    _so("A", "ent_ksc", "cust_toko_kain", "2025-03-10T03:00:00+00:00", 1498500.0, 148500.0, 1600000.0,
        [_item("prod_batik_mega", 1000000.0, 100, "yard", 6000, disc=100000.0), _item("prod_x", 500000.0, 50, "meter", 4000, line="woven")],
        sales_team=[{"sales_id": "user_sales_01", "split_pct": 60}, {"sales_id": "user_sales_02", "split_pct": 40}],
        created_by="user_admin_01"),
    _so("F", "ent_ksc", "cust_fashion_bandung", "2025-03-15T16:59:00+00:00", 2200000.0, 200000.0, 2000000.0,
        [_item("prod_knit", 2000000.0, 20, "kg", 50000, line="knit")], created_by="user_admin_01"),
    _so("B", "ent_ksc", "cust_butik_bali", "2025-03-31T17:30:00+00:00", 1000000.0, 0.0, 1000000.0,
        [_item("prod_batik_mega", 1000000.0, 10, "yard", 0)], sales_id="user_sales_01"),
    _so("C", "ent_ksc", "cust_toko_kain", "2025-03-12T03:00:00+00:00", 5000000.0, 0.0, 5000000.0,
        [_item("prod_batik_mega", 5000000.0, 10, "yard", 0)], status="cancelled", sales_id="user_sales_01"),
    _so("D", "ent_ksc", "cust_toko_kain", "2025-03-12T04:00:00+00:00", 300000.0, 0.0, 300000.0,
        [_item("prod_batik_mega", 300000.0, 3, "yard", 0)], order_type="sample", sales_id="user_sales_01"),
    _so("E", "ent_kanda", "cust_moda_surabaya", "2025-03-20T03:00:00+00:00", 2000000.0, 0.0, 2000000.0,
        [_item("prod_batik_mega", 2000000.0, 20, "yard", 0)], sales_id="user_sales_01"),
    _so("G", "ent_ksc", "cust_toko_kain", "2025-02-10T03:00:00+00:00", 500000.0, 0.0, 500000.0,
        [_item("prod_batik_mega", 500000.0, 5, "yard", 0)], sales_id="user_sales_01"),
]


def _login(email, ent="ent_ksc"):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ent})
    return s


@pytest.fixture(scope="module")
def env():
    mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    ids = [s["id"] for s in FIXTURE]
    mdb.sales_orders.delete_many({"id": {"$in": ids}})
    mdb.sales_orders.insert_many([dict(s) for s in FIXTURE])
    admin = _login("admin@kainnusantara.id")
    assert admin.post(f"{BASE}/ai/facts/rebuild", params={"from": "2025-01-01"}).status_code == 200
    yield {"admin": admin, "mdb": mdb}
    mdb.sales_orders.delete_many({"id": {"$in": ids}})
    mdb.fact_sales_lines.delete_many({"so_id": {"$in": ids}})


def _q(s, metrics, group_by=(), period=MAR, **kw):
    body = {"metrics": list(metrics), "group_by": list(group_by), "time_grain": kw.get("grain"), "period": period,
            "compare": kw.get("compare", "none"), "filters": kw.get("filters", []),
            "sort": {"by": None, "direction": "desc"}, "limit": None,
            "include_samples": kw.get("samples", False), "entity_scope": kw.get("scope", "active")}
    return s.post(f"{BASE}/ai/query", json=body)


def _ok(r):
    assert r.status_code == 200, r.text
    return r.json()


# ── unit: pembentukan baris fakta ───────────────────────────────────────────
def test_build_rows_allocates_discount_ppn_and_split():
    rows = build_rows(FIXTURE[0], {"assigned_sales_id": "user_sales_01"}, {}, {})
    assert len(rows) == 4 and {r["sales_id"] for r in rows} == {"user_sales_01", "user_sales_02"}
    assert round(sum(r["net_alloc"] for r in rows), 2) == 1350000.0
    assert round(sum(r["gross"] for r in rows), 2) == 1600000.0
    assert round(sum(r["discount"] for r in rows), 2) == 250000.0
    assert round(sum(r["ppn_alloc"] for r in rows), 2) == 148500.0
    assert round(sum(r["cost"] for r in rows), 2) == 800000.0
    s1 = [r for r in rows if r["sales_id"] == "user_sales_01"]
    assert round(sum(r["net_alloc"] for r in s1), 2) == 810000.0
    assert rows[0]["date_wib"] == "2025-03-10"


def test_attribution_chain():
    users = {"user_admin_01": {"role": "admin"}, "user_sales_09": {"role": "sales"}}
    assert attribute_sales({"sales_id": "s"}, {}, users) == [("s", 1.0)]
    assert attribute_sales({"created_by": "user_sales_09"}, {"assigned_sales_id": "o"}, users) == [("user_sales_09", 1.0)]
    assert attribute_sales({"created_by": "user_admin_01"}, {"assigned_sales_id": "o"}, users) == [("o", 1.0)]
    assert attribute_sales({"sales_team": [{"sales_id": "a", "split_pct": 60}]}, {"assigned_sales_id": "o"}, users,
                           "customer_owner") == [("o", 1.0)]
    assert attribute_sales({}, {}, users) == [("", 1.0)]
    assert build_rows(FIXTURE[3], {}, {}, {})[0]["is_live"] is False


# ── mesin kueri vs hitungan manual ──────────────────────────────────────────
def test_totals_march_ksc(env):
    d = _ok(_q(env["admin"], ["net_sales", "gross_sales", "discount_total", "ppn_amount", "orders_count", "gross_margin"]))
    t = d["totals"]
    assert t["net_sales"] == 3350000.0 and t["orders_count"] == 2
    assert t["gross_sales"] == 3600000.0 and t["discount_total"] == 250000.0
    assert t["ppn_amount"] == 348500.0 and t["gross_margin"] == 3350000.0 - 800000.0 - 1000000.0
    assert d["period"]["from"] == "2025-03-01" and d["source"] == "cat-v1"


def test_group_by_sales_person_split_and_fallback(env):
    rows = {r["sales_person_id"]: r for r in _ok(_q(env["admin"], ["net_sales", "orders_count"], ["sales_person"]))["rows"]}
    assert rows["user_sales_01"]["net_sales"] == 810000.0 and rows["user_sales_02"]["net_sales"] == 540000.0
    assert rows["user_sales_03"]["net_sales"] == 2000000.0
    assert rows["user_sales_01"]["orders_count"] == 1 and rows["user_sales_01"]["net_sales_share"] == round(810000 / 3350000 * 100, 2)


def test_daily_grain_wib_midnight(env):
    rows = {r["period"]: r["net_sales"] for r in _ok(_q(env["admin"], ["net_sales"], grain="day"))["rows"]}
    assert rows == {"2025-03-10": 1350000.0, "2025-03-15": 2000000.0}
    apr = _ok(_q(env["admin"], ["net_sales"], period={"preset": "custom", "from": "2025-04-01", "to": "2025-04-01"}))
    assert apr["totals"]["net_sales"] == 1000000.0


def test_samples_and_qty_per_unit(env):
    d = _ok(_q(env["admin"], ["sample_orders_count"]))
    assert d["totals"]["sample_orders_count"] == 1
    assert _ok(_q(env["admin"], ["net_sales"], samples=True))["totals"]["net_sales"] == 3650000.0
    q = _ok(_q(env["admin"], ["qty_sold"]))
    units = {r["unit"]: r["qty_sold"] for r in q["rows"]}
    assert units == {"yard": 100.0, "meter": 50.0, "kg": 20.0} and q["warnings"]
    assert _q(env["admin"], ["qty_sold", "net_sales", "recognized_revenue"]).status_code == 400


def test_compare_previous_period(env):
    d = _ok(_q(env["admin"], ["net_sales"], period={"preset": "custom", "from": "2025-03-01", "to": "2025-03-31"},
               compare="previous_period"))
    assert d["compare"]["totals"]["net_sales"] == 500000.0
    assert d["compare"]["delta"]["net_sales"] == 2850000.0 and d["compare"]["delta_pct"]["net_sales"] == 570.0


def test_analyze_change_contributions_sum_to_total(env):
    r = _ok(env["admin"].post(f"{BASE}/ai/analyze-change", json={
        "metric": "net_sales", "dimension": "customer", "period": MAR, "compare_to": "previous_period",
        "filters": [], "top_n": 1}))
    assert round(sum(x["delta"] for x in r["rows"]), 2) == r["compare"]["delta"]["net_sales"] == 2850000.0


def test_entity_scope(env):
    mgr = _login("manager@kainnusantara.id")
    assert _ok(_q(mgr, ["net_sales"]))["totals"]["net_sales"] == 3350000.0
    assert _ok(_q(mgr, ["net_sales"], scope="all_allowed"))["totals"]["net_sales"] == 5350000.0
    per = {r["entity_id"]: r["net_sales"] for r in _ok(_q(mgr, ["net_sales"], scope="per_entity"))["rows"]}
    assert per == {"ent_ksc": 3350000.0, "ent_kanda": 2000000.0}
    sales = _login("sales@kainnusantara.id")
    assert _ok(_q(sales, ["net_sales"], scope="all_allowed"))["entity_scope"]["entity_ids"] == ["ent_ksc"]


def test_sales_sees_only_own_attribution(env):
    d = _ok(_q(_login("sales@kainnusantara.id"), ["net_sales", "orders_count"], ["sales_person"]))
    assert d["totals"]["net_sales"] == 810000.0
    assert {r["sales_person_id"] for r in d["rows"]} == {"user_sales_01"}


def test_margin_and_permissions_denied(env):
    fin = _login("finance@kainnusantara.id")
    assert _q(fin, ["gross_margin"]).status_code == 400
    d = _ok(_q(fin, ["net_sales", "gross_margin_pct"]))
    assert d["denied"] == ["gross_margin_pct"] and "gross_margin_pct" not in d["totals"]
    assert _q(_login("warehouse@kainnusantara.id"), ["net_sales"]).status_code == 403
    assert _q(env["admin"], ["net_sales"], ["warehouse"]).status_code == 400


def test_result_saved_and_owner_only(env):
    d = _ok(_q(env["admin"], ["net_sales"], ["customer"]))
    got = _ok(env["admin"].get(f"{BASE}/ai/results/{d['result_id']}"))
    assert got["rows"] and got["tool"] == "query_metrics"
    assert _login("sales@kainnusantara.id").get(f"{BASE}/ai/results/{d['result_id']}").status_code == 404
