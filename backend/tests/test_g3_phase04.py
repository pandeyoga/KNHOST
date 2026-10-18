"""G3 Fase 04 — sumber angka, analitik, parser, tampilan.

    cd /app/backend && DB_NAME=g3_audit_phase04 python -m pytest tests/test_g3_phase04.py -q -n 0
"""
import asyncio
import os
from datetime import date, datetime
from types import SimpleNamespace

import pytest

if not os.environ.get("DB_NAME", "").startswith("g3_audit"):
    pytest.skip("Set DB_NAME=g3_audit_*", allow_module_level=True)

from db import db  # noqa: E402
from services.analytics_time import WIB  # noqa: E402


def run(c):
    return asyncio.get_event_loop().run_until_complete(c)


@pytest.fixture(autouse=True)
def _clean():
    async def wipe():
        for c in await db.list_collection_names():
            await db[c].delete_many({})
    run(wipe())
    yield


# ── D4-STOCK-02/03/04 ──
def _stock_patch(monkeypatch):
    from services import stock_analytics_service as sa
    monkeypatch.setattr(sa, "resolve_list_scope", lambda coll, q, ctx, e=None: dict(q))

    async def settings(e=None):
        return {}
    monkeypatch.setattr(sa, "get_effective_settings", settings)
    return sa


def test_stock_category_filter_full_cost_and_dates(monkeypatch):
    sa = _stock_patch(monkeypatch)

    async def go():
        await db.products.insert_many([{"id": "pW", "category": "woven", "sku": "W"},
                                       {"id": "pK", "category": "knitting", "sku": "K"}])
        await db.inventory_balances.insert_many([
            {"product_id": "pW", "warehouse_id": "w1", "owner_entity_id": "A", "on_hand_qty": 10},
            {"product_id": "pK", "warehouse_id": "w1", "owner_entity_id": "A", "on_hand_qty": 40}])
        await db.inventory_rolls.insert_many([
            {"id": "r1", "product_id": "pW", "warehouse_id": "w1", "owner_entity_id": "A", "status": "available",
             "length_remaining": 10, "unit_cost": 12, "base_unit_cost": 10, "created_at": "2026-01-05"},
            {"id": "r2", "product_id": "pK", "warehouse_id": "w1", "owner_entity_id": "A", "status": "available",
             "length_remaining": 40, "unit_cost": 5, "base_unit_cost": 5, "created_at": "bukan-tanggal"}])
        woven = await sa.compute_stock_analytics(None, category="woven")
        allr = await sa.compute_stock_analytics(None)
        return woven, allr
    woven, allr = run(go())
    s = woven["summary"]
    assert sum(b["qty"] for b in s["aging_buckets"]) == 10.0
    assert s["total_on_hand_value"] == 120.0 and s["total_base_value"] == 100.0 and s["total_landed_value"] == 20.0
    assert woven["rows"][0]["value_landed"] == 20.0
    assert sum(b["qty"] for b in allr["summary"]["aging_buckets"]) == 50.0


def test_stock_parse_ts_wib_boundary():
    from services.stock_analytics_service import _parse_ts, _age_days
    assert _parse_ts("2026-10-01").tzinfo is not None
    assert _parse_ts("") is None and _parse_ts("2026-13-40") is None
    now = datetime(2026, 10, 1, 0, 30, tzinfo=WIB)
    assert _age_days(now, _parse_ts("2026-09-30T17:10:00Z")) == 0     # 00:10 WIB hari ini
    assert _age_days(now, _parse_ts("2026-09-30T16:59:00+00:00")) == 1
    assert _age_days(now, _parse_ts("2026-09-30T23:00:00")) == 0      # naif = UTC → 06:00 WIB 1 Okt


# ── D4-AI-04 / D4-AI-03 ──
def test_ai_alloc_conserves():
    from services.analytics_facts import _alloc, build_rows
    assert sum(_alloc(1.01, [0.5, 0.5])) == pytest.approx(1.01) and _alloc(1.01, [0.5, 0.5]) == [0.51, 0.5]
    so = {"id": "s1", "grand_total": 100.03, "ppn_amount": 9.91, "total_amount": 95.0,
          "sales_team": [{"sales_id": "a", "split_pct": 1}, {"sales_id": "b", "split_pct": 1},
                         {"sales_id": "c", "split_pct": 1}],
          "items": [{"product_id": f"p{i}", "line_total": 9.0 + i / 3, "quantity": 1} for i in range(10)]}
    rows = build_rows(so, {}, {}, {})
    assert round(sum(r["net_alloc"] for r in rows), 2) == 90.12
    assert round(sum(r["ppn_alloc"] for r in rows), 2) == 9.91
    assert round(sum(r["gross"] for r in rows), 2) == 95.0
    assert rows == build_rows(so, {}, {}, {}) or all(a["_id"] == b["_id"] for a, b in zip(rows, build_rows(so, {}, {}, {})))


def test_ai_fact_write_failure_keeps_old_snapshot(monkeypatch):
    from services import analytics_facts as af

    async def pol():
        return {"sales_attribution": "team_split"}
    monkeypatch.setattr(af, "ai_policy", pol)

    async def go():
        await db.sales_orders.insert_one({"id": "s1", "status": "confirmed", "grand_total": 10, "created_at": "2026-01-01T00:00:00+00:00",
                                          "updated_at": "2026-01-01T00:00:00+00:00", "sales_id": "a",
                                          "items": [{"product_id": "p", "line_total": 10, "quantity": 1}]})
        await af.rebuild_facts()
        before = await db.fact_sales_lines.count_documents({})
        orig = db.fact_sales_lines.bulk_write

        async def boom(*a, **k):
            raise RuntimeError("fault")
        monkeypatch.setattr(type(db.fact_sales_lines), "bulk_write", boom, raising=False)
        try:
            await af.rebuild_facts()
        except RuntimeError:
            pass
        monkeypatch.setattr(type(db.fact_sales_lines), "bulk_write", orig, raising=False)
        after = await db.fact_sales_lines.count_documents({})
        st = await db.ai_fact_state.find_one({"id": af.STATE_ID})
        await af.rebuild_facts()
        await af.rebuild_facts()
        final = await db.fact_sales_lines.count_documents({})
        return before, after, st.get("last_error"), final
    before, after, err, final = run(go())
    assert before == 1 and after == 1 and "fault" in err and final == 1


# ── D4-HR-01 / D4-HR-02 ──
def test_hr_payroll_aggregate_and_turnover(monkeypatch):
    from services import hr_analytics_service as hs
    monkeypatch.setattr(hs, "resolve_list_scope", lambda coll, q, ctx, e=None: dict(q))

    async def go():
        t = lambda g, n: {"employees": 1, "gross": g, "net": n, "bpjs_emp": 1, "bpjs_er": 2, "pph21": 3, "commission": 0}  # noqa: E731
        await db.hr_payroll_runs.insert_many([
            {"id": "r1", "period": "2026-07", "entity_id": "A", "status": "posted", "totals": t(100, 90)},
            {"id": "r2", "period": "2026-07", "entity_id": "B", "status": "paid", "totals": t(200, 180)},
            {"id": "r3", "period": "2026-07", "entity_id": "B", "status": "draft", "totals": t(999, 999)}])
        await db.hr_employees.insert_many([
            {"id": "e1", "status": "resigned", "separation_date": "2026-07-15", "updated_at": "2026-10-02T00:00:00+00:00"},
            {"id": "e2", "status": "inactive", "updated_at": "2026-07-03T00:00:00+00:00"},
            {"id": "e3", "status": "active", "join_date": "2025-01-01"}])
        return await hs.hr_summary(None, None, "2026-07"), await hs.hr_summary(None, None, "2026-10")
    jul, octo = run(go())
    p = jul["payroll"]
    assert (p["gross"], p["net"], p["runs"], p["unposted_runs"], p["bpjs_total"], p["pph21"]) == (300, 270, 2, 1, 6, 6)
    assert next(x for x in jul["payroll_trend"] if x["period"] == "2026-07")["gross"] == 300
    assert jul["turnover"]["separations"] == 1 and jul["turnover"]["missing_separation_date"] == 1
    assert octo["turnover"]["separations"] == 0


def test_hr_separation_rules():
    from routers.hr import _apply_separation
    u = {"status": "resigned"}
    _apply_separation({"status": "active"}, u)
    assert len(u["separation_date"]) == 10
    u2 = {"name": "Baru"}
    _apply_separation({"status": "resigned", "separation_date": "2026-07-15"}, u2)
    assert "separation_date" not in u2
    u3 = {"status": "active"}
    _apply_separation({"status": "resigned", "separation_date": "2026-07-15"}, u3)
    assert u3["separation_date"] == "" and u3["separation_history"][0]["separation_date"] == "2026-07-15"


# ── D4-WMS-01/02/04 ──
def test_wms_health_wib_day_cc_and_putaway(monkeypatch):
    from services import wms_health_service as wh
    from services import putaway_order_service as pos

    async def ok(r):
        return None, None
    monkeypatch.setattr(pos, "identity_issue", ok)
    monkeypatch.setattr(wh, "now_wib", lambda: datetime(2026, 10, 1, 6, 0, tzinfo=WIB))

    async def go():
        await db.warehouses.insert_one({"id": "w1", "name": "G1"})
        await db.rfid_reads.insert_many([
            {"result": "red", "read_type": "gate_in", "warehouse_id": "w1", "timestamp": "2026-09-30T16:59:00+00:00"},
            {"result": "red", "read_type": "gate_in", "warehouse_id": "w1", "timestamp": "2026-09-30T17:00:00+00:00"},
            {"result": "red", "read_type": "gate_out", "warehouse_id": "w1", "timestamp": "2026-09-30T23:59:00+00:00"}])
        await db.rfid_cycle_counts.insert_many([
            {"id": "c1", "warehouse_id": "w1", "accuracy_pct": 95.0, "status": "completed", "created_at": "2026-09-01"},
            {"id": "c2", "warehouse_id": "w1", "accuracy_pct": 10.0, "status": "void", "created_at": "2026-09-05"}])
        await db.rfid_verify_sessions.insert_one({"id": "s1", "kind": "cycle_count", "warehouse_id": "w1",
                                                  "status": "open", "created_at": "2026-09-10"})
        base = {"warehouse_id": "w1", "owner_entity_id": "A", "length_remaining": 5,
                "journey": {"stage": "tag_verified", "routing": "store"}}
        await db.inventory_rolls.insert_many([
            {**base, "id": "r1", "status": "available", "active_movement": None},
            {**base, "id": "r2", "status": "reserved", "active_movement": None}])
        return await wh.health_dashboard(["A"])
    w = run(go())["warehouses"][0]
    assert w["red_reads_today"] == 2
    assert w["last_cc"]["accuracy_pct"] == 95.0 and w["latest_cc_status"]["status"] == "open"
    assert (w["putaway_ready"], w["putaway_blocked"], w["putaway_blocked_by_reason"]) == (1, 1, {"status_reserved": 1})


# ── D4-SIM-01 ──
def test_sim_bill_match_uses_evaluator():
    from services.config_simulator import _bill_match
    c = {"purchasing.bill_qty_tolerance_percent": 0, "purchasing.bill_price_tolerance_percent": 5}
    assert _bill_match(c, {"received_qty": 0, "billed_qty": 10, "po_price": 100, "billed_price": 100})["verdict"] == "block"
    assert _bill_match(c, {"received_qty": 100, "billed_qty": 100, "po_price": 100, "billed_price": 100})["verdict"] == "ok"
    assert _bill_match(c, {"received_qty": 100, "billed_qty": 101, "po_price": 100, "billed_price": 100})["verdict"] == "block"
    r = _bill_match(c, {"received_qty": 0, "billed_qty": 0, "po_price": 100, "billed_price": 100})
    assert "nan" not in str(r).lower()


# ── D4-BANK-01/02 ──
def test_bank_dates_strict():
    from services.bank_statement_parser import parse_date
    assert parse_date("2026-02-30") == "" and parse_date("2026-99-99") == "" and parse_date("2026-13-01") == ""
    assert parse_date("2024-02-29") == "2024-02-29" and parse_date("2026-02-29") == ""
    assert parse_date("2026-02-28") == "2026-02-28" and parse_date("31/04/2026") == ""
    assert parse_date("20260228") == "2026-02-28" and parse_date(" 28 Feb 2026 ") == "2026-02-28"


def test_bank_import_rejects_bad_dates(monkeypatch):
    from services import bank_recon_service as br

    async def acc(*a, **k):
        return {"id": "b1", "entity_id": "A"}
    monkeypatch.setattr(br, "_account", acc)
    res = run(br.import_lines("b1", "A", [{"stmt_date": "2026-02-30", "amount": 5, "direction": "in"},
                                          {"stmt_date": "2026-02-28", "amount": 5, "direction": "in"}], "t"))
    assert res["imported"] == 1 and len(res["line_errors"]) == 1
    assert run(db.bank_statement_lines.count_documents({"stmt_date": "2026-02-30"})) == 0


def test_mt940_reversal_marks():
    from services.bank_statement_parser import parse_mt940
    raw = ":61:2603010301D100,00NTRFREF1\n:86:biaya\n:61:2603010301RD100,00NTRFREF2\n" \
          ":61:260302C50,00NTRF\n:61:260302RC50,00NTRF\n:61:260230C10,00NTRF\n"
    rows, errors = parse_mt940(raw, {})
    dirs = [(r["direction"], r["amount"]) for r in rows]
    assert dirs == [("out", 100.0), ("in", 100.0), ("in", 50.0), ("out", 50.0)]
    assert sum(a if d == "in" else -a for d, a in dirs) == 0
    assert len(errors) == 1   # 30 Feb ditolak


# ── D4-ALERT-DATE-01 / AMT-01 ──
def test_ap_alert_calendar_and_outstanding(monkeypatch):
    from services import alert_service as al
    from services import analytics_time as at
    sent = []

    async def notif(**k):
        sent.append(k)
        return {"id": "n"}

    async def terms(ent=""):
        return {"NET30": 30}
    monkeypatch.setattr(al, "create_notification", notif)
    monkeypatch.setattr(al, "_term_days_map", terms)
    monkeypatch.setattr(at, "now_wib", lambda: datetime(2026, 10, 6, 13, 0, tzinfo=WIB))

    async def go():
        await db.suppliers.insert_one({"id": "s", "payment_term_code": "NET30"})
        await db.vendor_bills.insert_many([
            {"id": "b1", "status": "posted", "bill_number": "B1", "bill_date": "2026-09-06", "grand_total": 100,
             "amount_paid": 70, "supplier_id": "s"},
            {"id": "b2", "status": "posted", "bill_number": "B2", "bill_date": "2026-09-05", "grand_total": 50,
             "supplier_id": "s"},
            {"id": "b3", "status": "posted", "bill_number": "B3", "bill_date": "2026-09-06", "grand_total": 80,
             "amount_paid": 80, "supplier_id": "s"}])
        await al.job_ap_due()
    run(go())
    by = {n["ref"]: n for n in sent}
    assert "HARI INI" in by["ap_due:b1"]["title"] and by["ap_due:b1"]["severity"] == "warning"
    assert "Rp 30" in by["ap_due:b1"]["body"].replace(".", "") or "30" in by["ap_due:b1"]["body"]
    assert "LEWAT 1 hari" in by["ap_due:b2"]["title"]
    assert "ap_due:b3" not in by


# ── D4-KPI-* ──
def test_kpi_weight_period_score():
    from services import hr_kpi_service as k
    emp = {"id": "e1", "name": "X", "entity_id": "A"}

    async def go():
        await k.submit_kpi(emp, {"metric": "a", "period": "2026-10", "target": 100, "actual": 20, "weight": 1}, "t")
        await k.submit_kpi(emp, {"metric": "b", "period": "2026-10", "target": 100, "actual": 80, "weight": 3}, "t")
        z = await k.submit_kpi(emp, {"metric": "c", "period": "2026-10", "target": 100, "actual": 150, "weight": 0}, "t")
        for bad in ("2026-99", "2026-00", "2026-13", "abcd-10", "2026-1"):
            with pytest.raises(ValueError):
                await k.submit_kpi(emp, {"metric": "x", "period": bad, "target": 1, "actual": 1}, "t")
        with pytest.raises(ValueError):
            await k.update_kpi(z["id"], {"period": "bad"})
        with pytest.raises(ValueError):
            await k.update_kpi(z["id"], {"metric": "   "})
        await db.hr_kpi.insert_one({"id": "legacy", "employee_id": "e1", "period": "2026-99", "score": 10, "weight": 1})
        return z, await k.my_kpi(emp)
    z, me = run(go())
    assert z["weight"] == 0
    assert me["latest_period"] == "2026-10" and me["latest_score"] == 65.0 and me["invalid_periods"] == ["2026-99"]
    assert k.compute_score(100, -10) == 0.0 and k.compute_score(100, 200) == 150.0
    assert k.compute_score(100, 50, -1) == 0.0 and k.compute_score(0, 5) == 0.0
    assert k._weighted_avg([{"score": 80, "weight": 0}]) is None


# ── D4-BUD-THRESHOLD-01 ──
def test_budget_zero_threshold(monkeypatch):
    from services import budget_service as bs

    async def budgets(scope, year):
        return [{"id": "b", "dimension": "account", "key": "6-1", "amount": 150, "month": 0}]

    async def acts(scope, year):
        return {"6-1": {1: 10.0}}

    async def none(scope, year, *a, **k):
        return {}

    async def cmts(scope, year, *a, **k):
        return {("account", "6-1"): {"total": 20.0, "by_month": {1: 20.0}, "docs": []}}

    async def rules(e):
        return {"entity_id": e, "warn_threshold_pct": 0}
    for n, f in (("list_budgets", budgets), ("_actual_by_account", acts), ("_actual_by_category", none),
                 ("_commitment_map", cmts), ("get_rules", rules)):
        monkeypatch.setattr(bs, n, f)
    r = run(bs.budget_vs_actual({}, 2026, "A"))
    assert r["rows"][0]["status"] == "warning"


# ── D4-EQ-01 ──
def test_equity_kpi_from_pl(monkeypatch):
    from services import equity_statement_service as es

    async def bsheet(as_of=None, scope=None):
        return {"equity": {"lines": [], "current_earnings": 0.0}, "equity_total": 100.0}

    async def pl(start=None, end=None, scope=None):
        return {"net_income": 100.0}
    monkeypatch.setattr(es.fs, "balance_sheet", bsheet)
    monkeypatch.setattr(es.fs, "income_statement", pl)
    r = run(es.equity_statement("2026-01-01", "2026-12-31"))
    assert r["net_income"] == 100.0 and r["period_operating_net_income"] == 100.0
    assert r["movement_unclosed_earnings"] == 0.0


# ── D4-RND-01 ──
def test_rnd_same_name_two_people(monkeypatch):
    from services import rnd_kpi_service as rk

    async def w(e=""):
        return {"escalate_admin_days": 3, "on_time": 1, "score": 1, "acc": 1, "design": 0}

    async def ds(q, s):
        return {}

    async def dm(e):
        return {}
    monkeypatch.setattr(rk, "weights", w)
    monkeypatch.setattr(rk, "design_studio_stats", ds)
    monkeypatch.setattr(rk, "_division_map", dm)
    monkeypatch.setattr(rk, "compute_grade", lambda row, w: {"grade_score": None, "grade_letter": "—"})

    async def go():
        rd = lambda uid, nm: {"id": uid + nm, "performed_by": nm, "performed_by_user_id": uid,  # noqa: E731
                              "received_at": "2026-10-01T00:00:00+00:00", "result": "acc"}
        await db[rk.COLL].insert_one({"id": "s1", "status": "done", "rounds": [
            rd("U1", "Ani"), rd("U2", "Ani"), rd("U1", "Ani Baru"),
            {"id": "x", "performed_by": "Ani", "received_at": "2026-10-01T00:00:00+00:00"}]})
        return await rk.designer_kpi({}, period="all")
    items = run(go())["items"]
    keys = {r["designer_key"]: r for r in items}
    assert set(keys) == {"u:U1", "u:U2", "n:ani"}
    assert keys["u:U1"]["rounds"] == 2 and keys["n:ani"]["legacy_name_only"] is True


# ── D4-RET-CHAIN-01 (unit grouping) & D4-AI-02 ──
def test_ai_new_customer_line_scope():
    from services import analytics_engine as ae
    from services.analytics_time import Period

    async def go():
        base = {"entity_id": "A", "is_live": True, "is_sample": False}
        await db.fact_sales_lines.insert_many([
            {**base, "_id": "1", "customer_id": "cK", "line_code": "knitting", "date_wib": "2026-10-02"},
            {**base, "_id": "2", "customer_id": "cX", "line_code": "knitting", "date_wib": "2026-09-01"},
            {**base, "_id": "3", "customer_id": "cX", "line_code": "woven", "date_wib": "2026-10-03"}])
        sc = SimpleNamespace(entity_ids=["A"], sales_only=None, line_q={"line_code": "woven"})
        p = Period("custom", date(2026, 10, 1), date(2026, 10, 31))
        return await ae._src_fact_new(["new_customers"], [], None, p, [], sc, [], False)
    res = run(go())
    assert sum(v["new_customers"] for v in res.values()) == 1
