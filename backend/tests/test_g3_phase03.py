"""Gelombang 3 · Fase 03 — uji service (Batch A + sebagian Batch B). DB uji terpisah.

    cd /app/backend && DB_NAME=g3_audit_phase03 python -m pytest tests/test_g3_phase03.py -q -n 0
"""
import asyncio
import os

import pytest

if not os.environ.get("DB_NAME", "").startswith("g3_audit"):
    pytest.skip("Set DB_NAME=g3_audit_*", allow_module_level=True)

from db import db  # noqa: E402


def run(c):
    return asyncio.get_event_loop().run_until_complete(c)


@pytest.fixture(autouse=True)
def _clean():
    async def wipe():
        for c in await db.list_collection_names():
            await db[c].delete_many({})
    run(wipe())
    yield


def _opts():
    return {"lines": [{"product_id": "p1", "product_name": "Kain", "unit": "meter", "backorder_qty": 100.0,
                       "incoming_total": 0.0, "promise_date": "", "own_available": 30.0,
                       "other_entities": [{"entity_id": "ent_B", "available": 500.0}]}]}


# D4-PLAN-02
def test_plan02_duplicate_product_rows_rejected():
    from services import fulfillment_plan_service as fps
    from services.fulfillment_decision_service import FulfillmentError
    with pytest.raises(FulfillmentError):
        fps._validate([{"product_id": "p1", "reorder_qty": 100}, {"product_id": "p1", "reorder_qty": 100}], _opts())
    with pytest.raises(FulfillmentError):  # alokasi PT sama ganda dijumlah lalu dibatasi kekurangan
        fps._validate([{"product_id": "p1", "interco": [{"entity_id": "ent_B", "qty": 60},
                                                        {"entity_id": "ent_B", "qty": 60}]}], _opts())


# D4-PLAN-03 + D4-PLAN-01
def test_plan03_partial_failure_recorded_partial_with_remaining(monkeypatch):
    from services import fulfillment_plan_service as fps
    from services import fulfillment_decision_service as fds
    from services import backorder_service
    recorded = {}

    async def order(_id):
        return {"id": "so1", "number": "SO-1", "entity_id": "ent_A"}

    async def options(o):
        return _opts()

    async def prices(plan, buyer):
        return None

    async def stock(oid, pid, qty, actor):
        return 30.0

    async def interco(*a, **k):
        raise fds.FulfillmentError("transfer gagal")

    async def record(o, d):
        recorded["d"] = d
    monkeypatch.setattr(fds, "_order", order)
    monkeypatch.setattr(fps, "plan_options", options)
    monkeypatch.setattr(fps, "_assert_prices", prices)
    monkeypatch.setattr(backorder_service, "fulfill_from_stock", stock)
    monkeypatch.setattr(fds, "_take_from_other_entity", interco)
    monkeypatch.setattr(fds, "_record", record)
    with pytest.raises(fds.FulfillmentError):
        run(fps.decide_plan("so1", [{"product_id": "p1", "stock_qty": 30,
                                     "interco": [{"entity_id": "ent_B", "qty": 70}]}], {"name": "t"}))
    d = recorded["d"]
    assert d["scope"] == "partial" and d["remaining"] == {"p1": 70.0} and d["error"]


def test_plan01_reaffirmed_pr_adds_zero_qty(monkeypatch):
    from services import fulfillment_plan_service as fps
    from services import fulfillment_decision_service as fds
    from services import restock_service

    async def open_prs(oid):
        return [{"id": "pr1", "number": "PR-1", "status": "submitted",
                 "items": [{"product_id": "p1", "quantity": 20}]}]
    monkeypatch.setattr(restock_service, "_open_restock_prs", open_prs)
    monkeypatch.setattr(restock_service, "OPEN_PR_STATUSES", ["submitted"], raising=False)
    plan = [{**_opts()["lines"][0], "stock": 0, "reorder": 80.0, "wait": 0, "interco": []}]
    done = []
    run(fps._execute({"id": "so1", "number": "SO-1"}, plan, {"name": "t"}, "", done))
    assert done[0]["qty"] == 0.0 and done[0]["reaffirmed"] and done[0]["existing_pr_qty"] == 20.0
    o = {"fulfillment_decisions": [{"parts": done}]}
    monkeypatch.setattr(fds, "decision_history", lambda order: order["fulfillment_decisions"])
    assert fps._planned(o).get("p1", 0.0) == 0.0


# D4-SALES-01
def test_sales01_target_scoped_by_entity():
    from services import sales_force_service as sf

    async def go():
        await db.users.insert_one({"id": "s1", "entity_id": "ent_A"})
        await db.sales_targets.insert_many([
            {"sales_id": "s1", "period": "2026-01", "entity_id": "ent_A", "target_collection_amount": 100},
            {"sales_id": "s1", "period": "2026-01", "target_collection_amount": 50}])
        return (await sf._target_collection_for("s1", "2026-01", "ent_A"),
                await sf._target_collection_for("s1", "2026-01", "ent_B"),
                await sf._target_collection_for("s1", "2026-01", None))
    a, b, allv = run(go())
    assert (a, b, allv) == (150.0, 0.0, 150.0)


# D4-COA-01
def test_coa01_multi_entity_includes_entity_specific_accounts(monkeypatch):
    from services import financial_statement_service as fs
    from services import gl_service

    async def eff(codes=None, entity_id=None):
        base = {"1-1100": {"code": "1-1100", "type": "asset"}}
        if entity_id == "ent_A":
            base["4-7700"] = {"code": "4-7700", "type": "income"}
        return dict(base)
    monkeypatch.setattr(gl_service, "effective_accounts", eff)
    m = run(fs._accounts_map({"entity_id": {"$in": ["ent_A", "ent_B"]}}))
    assert "4-7700" in m and "1-1100" in m


# D4-COMM-BOUNDS-01
def test_comm_bounds_patch_rejects_negative():
    from pydantic import ValidationError
    from schemas_contracts import SupplierContractPatch
    from schemas_supplier_items import SupplierItemPatch
    for kw in ({"tariff_rate": -5}, {"shrinkage_pct": 101}, {"lead_time_days": -1}):
        with pytest.raises(ValidationError):
            SupplierContractPatch(**kw)
    for kw in ({"last_price": -1}, {"moq": -1}, {"conv_factor": 0}):
        with pytest.raises(ValidationError):
            SupplierItemPatch(**kw)
    assert SupplierContractPatch(tariff_rate=10).tariff_rate == 10


# D4-BUD-EDIT-01
def test_budget_update_rejects_duplicate_and_bad_year():
    from services import budget_service as bs

    async def go():
        base = {"entity_id": "ent_A", "year": 2026, "dimension": "account", "key": "6-1000", "amount": 1}
        await db.budgets.insert_many([{**base, "id": "b1", "month": 1}, {**base, "id": "b2", "month": 2}])
        errs = []
        for patch in ({"month": 1}, {"year": 1900}):
            try:
                await bs.update_budget("b2", patch, {"entity_id": "ent_A"})
            except ValueError as e:
                errs.append(str(e))
        ok = await bs.update_budget("b2", {"month": 3}, {"entity_id": "ent_A"})
        return errs, ok
    errs, ok = run(go())
    assert len(errs) == 2 and ok["month"] == 3


# D4-UOM-BF-01
def test_uom_backfill_counts_unique_existing_rolls():
    from services import dual_qty_service as dq

    async def go():
        await db.inventory_rolls.insert_one({"id": "R1"})
        await db.sales_returns.insert_one({"id": "ret1", "items": [{"roll_ids": ["R1", "R1", "MISSING"]}]})
        await dq.backfill(db)
        return await db.sales_returns.find_one({"id": "ret1"}, {"_id": 0})
    assert run(go())["items"][0]["qty_rolls"] == 1


# V3-DATE-01
def test_date01_date_only_first_day_included():
    from services import financial_statement_service as fs

    async def go():
        await db.journal_entries.insert_many([
            {"id": "j1", "status": "posted", "date": "2026-01-01",
             "lines": [{"account_code": "1-1100", "debit": 100, "credit": 0}]},
            {"id": "j2", "status": "posted", "date": "2025-12-31T23:00:00",
             "lines": [{"account_code": "1-1100", "debit": 7, "credit": 0}]}])
        return await fs._aggregate({}, {"$gte": fs._day_start("2026-01-01"), "$lte": fs._day_end("2026-01-31")})
    agg = run(go())
    assert round(sum(v.get("debit", 0) for v in agg.values()), 2) == 100.0


# D4-FIN-02
def test_fin02_term_zero_kept_and_snapshot_wins():
    from services.customer_service import _term_days
    assert _term_days({"payment_profile": {"term_days": 30}}, {"payment_term_days": 0}) == 0
    assert _term_days({"payment_profile": {"term_days": 30}}, {"payment_term_days": 90}) == 90
    assert _term_days({"payment_profile": {"term_days": 0}}, {}) == 0
    assert _term_days({}, {}) == 30


def test_fin02_forecast_excludes_cash_method():
    from services import cashflow_forecast_service as cf

    async def go():
        await db.sales_orders.insert_many([
            {"id": "o1", "number": "SO-T", "status": "confirmed", "grand_total": 100, "payment_method": "tunai",
             "payment_profile_method": "tunai", "created_at": "2026-01-01T00:00:00+00:00"},
            {"id": "o2", "number": "SO-K", "status": "confirmed", "grand_total": 200, "payment_term_days": 90,
             "payment_profile_method": "tempo", "created_at": "2026-01-01T00:00:00+00:00"}])
        return await cf.cashflow_forecast({})
    res = run(go())
    nums = [i["number"] for i in res.get("ar_items", res.get("inflow_items", []))] if isinstance(res, dict) else []
    assert "SO-T" not in nums


# D4-FIN-03
def test_fin03_revenue_excludes_included_ppn(monkeypatch):
    from services import profitability_service as ps

    async def wac(pid, entity_id=None):
        return {"wac": 0}
    monkeypatch.setattr(ps, "wac_for_product", wac)

    async def go():
        await db.sales_orders.insert_one({
            "id": "o1", "status": "shipped", "entity_id": "ent_A", "grand_total": 1000.0, "ppn_amount": 99.1,
            "created_at": "2026-01-05T00:00:00", "items": [
                {"product_id": "p1", "quantity": 1, "line_total": 600.0},
                {"product_id": "p2", "quantity": 1, "line_total": 400.0}]})
        return await ps.profitability()
    res = run(go())
    tot = res.get("totals") or res.get("summary") or {}
    assert round(float(tot.get("revenue", -1)), 2) == 900.9, tot
