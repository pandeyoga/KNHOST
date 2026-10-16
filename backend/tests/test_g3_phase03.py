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



# V3-PO-01/03 — tugas per baris, refresh, ditutup hanya sesudah approval & qty cocok
def _patch_pvt(monkeypatch):
    from services import po_variance_task_service as pvt
    from services import notification_service as notif

    async def tol(e):
        return 2.0

    async def owner(po):
        return None

    async def noop(*a, **k):
        return None
    monkeypatch.setattr(pvt, "_tolerance_pct", tol)
    monkeypatch.setattr(pvt, "_responsible_user", owner)
    monkeypatch.setattr(pvt, "audit", noop)
    monkeypatch.setattr(notif, "create_notification", noop)
    return pvt


def test_po01_task_refreshes_and_legacy_lines_separate(monkeypatch):
    pvt = _patch_pvt(monkeypatch)

    async def go():
        await db.purchase_orders.insert_one({"id": "po1", "status": "partial", "entity_id": "ent_A", "items": [
            {"product_id": "p1", "quantity": 100, "received_qty": 90},
            {"product_id": "p1", "quantity": 50, "received_qty": 40}]})
        await pvt.ensure_for_po("po1")
        n1 = await db.po_variance_tasks.count_documents({"po_id": "po1", "status": "open"})
        await db.purchase_orders.update_one({"id": "po1"}, {"$set": {"items.0.received_qty": 95}})
        await pvt.ensure_for_po("po1")
        t0 = await db.po_variance_tasks.find_one({"line_key": "p1#0"}, {"_id": 0})
        await db.purchase_orders.update_one({"id": "po1"}, {"$set": {"items.0.received_qty": 100}})
        await pvt.ensure_for_po("po1")
        t0b = await db.po_variance_tasks.find_one({"line_key": "p1#0"}, {"_id": 0})
        return n1, t0, t0b
    n1, t0, t0b = run(go())
    assert n1 == 2
    assert t0["received_qty"] == 95 and t0["short_qty"] == 5
    assert t0b["status"] == "obsolete"


def test_po03_amendment_task_closed_only_after_approval_and_qty_match(monkeypatch):
    pvt = _patch_pvt(monkeypatch)

    async def go():
        await db.purchase_orders.insert_one({"id": "po2", "status": "waiting_approval", "items": [
            {"product_id": "p1", "quantity": 960, "received_qty": 960}]})
        await db.po_variance_tasks.insert_one({"id": "t1", "po_id": "po2", "product_id": "p1",
                                               "line_key": "p1#0", "status": "pending_amendment"})
        a = await pvt.close_amendment_tasks("po2", "x")
        await db.purchase_orders.update_one({"id": "po2"}, {"$set": {"status": "pending", "items.0.quantity": 1000}})
        b = await pvt.close_amendment_tasks("po2", "x")
        await db.purchase_orders.update_one({"id": "po2"}, {"$set": {"items.0.quantity": 960}})
        c = await pvt.close_amendment_tasks("po2", "x")
        return a, b, c
    assert run(go()) == (0, 0, 1)


def test_po02_amend_qty_to_received_allowed_other_changes_locked():
    from fastapi import HTTPException
    from services.po_amendment_service import _assert_received_line_locked

    class It:
        product_id, unit, price, discount_percent = "p1", "meter", 0, 0
        quantity = 960
    old = [{"product_id": "p1", "quantity": 1000, "unit": "meter", "price": 10, "discount_percent": 0}]
    _assert_received_line_locked("SKU", It(), old, 960.0)
    It.quantity = 970
    with pytest.raises(HTTPException):
        _assert_received_line_locked("SKU", It(), old, 960.0)



# V3-CF-01 — jurnal campuran kas/nonkas
def _cf_accounts(monkeypatch):
    from services import financial_statement_service as fs

    async def amap(scope=None):
        return {"1-1100": {"type": "asset", "name": "Bank"}, "1-1110": {"type": "asset", "name": "Kas Kecil"},
                "1-2100": {"type": "asset", "name": "Mesin"}, "1-2200": {"type": "asset", "name": "Kendaraan"},
                "1-2900": {"type": "asset", "name": "Akum. Susut"}, "1-1200": {"type": "asset", "name": "Piutang"},
                "2-1100": {"type": "liability", "name": "Utang"}, "4-1000": {"type": "income", "name": "Penjualan"},
                "6-1000": {"type": "expense", "name": "Penyusutan"}}
    monkeypatch.setattr(fs, "_accounts_map", amap)


def _je(i, lines, date="2026-03-10"):
    return {"id": f"je{i}", "status": "posted", "date": date,
            "lines": [{"account_code": c, "debit": d, "credit": k} for c, d, k in lines]}


def _cf(lines_list):
    from services import cash_flow_service as cfs

    async def go():
        await db.journal_entries.insert_many([_je(i, ln) for i, ln in enumerate(lines_list)])
        return await cfs.cash_flow_statement("2026-03-01", "2026-03-31")
    return run(go())


def test_cf01_mixed_asset_cash_and_credit(monkeypatch):
    _cf_accounts(monkeypatch)
    r = _cf([[("1-2100", 100, 0), ("1-1100", 0, 40), ("2-1100", 0, 60)]])
    assert r["investing"]["total"] == -40.0
    assert r["operating"]["total"] == 0.0
    assert {l["code"]: l["amount"] for l in r["noncash_disclosure"]["lines"]} == {"1-2100": -60.0}
    assert r["net_change"] == -40.0 and r["reconciled"]


def test_cf01_other_fixtures(monkeypatch):
    _cf_accounts(monkeypatch)
    r = _cf([
        [("1-2100", 100, 0), ("2-1100", 0, 100)],                      # aset penuh kredit
        [("1-2200", 50, 0), ("1-1100", 0, 50)],                        # aset penuh tunai
        [("1-1110", 30, 0), ("1-1100", 0, 30)],                        # bank → kas kecil
        [("6-1000", 10, 0), ("1-2900", 0, 10)],                        # penyusutan
        [("1-1200", 200, 0), ("4-1000", 0, 200)],                      # jual kredit
        [("1-1100", 200, 0), ("1-1200", 0, 200)],                      # pelunasan
        [("1-2100", 60, 0), ("1-2200", 40, 0), ("1-1100", 0, 50), ("2-1100", 0, 50)],  # campuran 2 aset
    ])
    inv = {l["code"]: l["amount"] for l in r["investing"]["lines"]}
    assert inv == {"1-2200": -70.0, "1-2100": -30.0}
    assert r["investing"]["total"] == -100.0
    assert r["operating"]["total"] == 200.0  # hanya pelunasan piutang
    nc = {l["code"]: l["amount"] for l in r["noncash_disclosure"]["lines"]}
    assert nc == {"1-2100": -130.0, "1-2200": -20.0, "1-2900": 10.0}
    assert r["net_change"] == 100.0 and r["reconciled"]


# D4-FIN-04 — realisasi = terkirim; estimasi terpisah
def test_fin04_reserved_is_estimate_only_partial_shipment_realised(monkeypatch):
    from services import profitability_service as ps

    async def wac(pid, entity_id=None):
        return {"wac": 3.0, "wac_base": 3.0, "wac_landed": 0.0}
    monkeypatch.setattr(ps, "wac_for_product", wac)

    async def go():
        await db.sales_orders.insert_many([
            {"id": "oR", "status": "reserved", "entity_id": "ent_A", "grand_total": 100.0, "ppn_amount": 0,
             "created_at": "2026-03-01T03:00:00+00:00",
             "items": [{"product_id": "p1", "quantity": 10, "line_total": 100.0}]},
            {"id": "oP", "status": "partially_shipped", "entity_id": "ent_A", "grand_total": 200.0, "ppn_amount": 0,
             "created_at": "2026-02-20T03:00:00+00:00",
             "items": [{"product_id": "p1", "quantity": 10, "line_total": 200.0}]}])
        await db.shipments.insert_one({"id": "sh1", "order_id": "oP", "product_id": "p1", "qty": 5,
                                       "status": "dispatched", "created_at": "2026-02-28T18:00:00+00:00",
                                       "rolls": [{"length": 5, "unit_cost": 4.0, "extended_cost": 20.0}]})
        return await ps.profitability("2026-02-01", "2026-03-31")
    r = run(go())
    assert r["totals"]["revenue"] == 100.0 and r["totals"]["cogs"] == 20.0
    assert [m["month"] for m in r["monthly"]] == ["2026-03"]   # 28 Feb 18:00 UTC = 1 Mar WIB
    assert r["estimate"]["totals"]["revenue"] == 300.0 and r["estimate"]["totals"]["cogs"] == 60.0


# D4-CASH-01 — jenis kas tetap dari master rekening
def test_cash01_opening_type_stable_after_void(monkeypatch):
    from routers import cash as cash_router
    from services import bank_service as bs

    class Ctx:
        view_all, active_entity_id = False, "ent_A"

    async def perm(*a, **k):
        return {"role": "admin"}

    async def ctx(req):
        return Ctx()

    async def pending(_db):
        return {}
    monkeypatch.setattr(cash_router, "require_permission", perm)
    monkeypatch.setattr(cash_router, "entity_ctx", ctx)
    monkeypatch.setattr(cash_router, "resolve_scope_ids", lambda c, e=None: ["ent_A"])
    monkeypatch.setattr(cash_router.cash_entity_service, "group_cash_pending", pending)

    async def go():
        await db.bank_accounts.insert_many([
            {"id": "a1", "entity_id": "ent_A", "account_type": "bank", "opening_balance": 1000},
            {"id": "a2", "entity_id": "ent_A", "account_type": "cash", "opening_balance": 50},
            {"id": "a3", "entity_id": "ent_A", "account_type": "bank", "opening_balance": 500}])
        await db.cash_transactions.insert_one({"id": "t1", "account_id": "a1", "entity_id": "ent_A",
                                               "cash_type": "kas_kecil", "direction": "out", "amount": 10,
                                               "status": "posted"})
        n = await bs.backfill_cash_type()
        n2 = await bs.backfill_cash_type()
        before = await cash_router.cash_summary(None, None)
        await db.cash_transactions.update_one({"id": "t1"}, {"$set": {"status": "void"}})
        after = await cash_router.cash_summary(None, None)
        types = {a["id"]: a["cash_type"] async for a in db.bank_accounts.find({}, {"_id": 0})}
        return n, n2, before, after, types
    n, n2, before, after, types = run(go())
    assert (n, n2) == (3, 0)
    assert types == {"a1": "kas_kecil", "a2": "kas_kecil", "a3": "kas_besar"}
    for s in (before, after):
        assert s["kas_kecil"]["opening"] == 1050.0 and s["kas_besar"]["opening"] == 500.0
    assert after["kas_kecil_per_entity"]["ent_A"]["balance"] == 1050.0


# D4-DATE-01 — periode WIB
def test_date01_in_period_uses_wib():
    from services.sales_force_service import _in_period
    assert _in_period("2026-09-30T18:00:00+00:00", "2026-10") is True
    assert _in_period("2026-09-30T18:00:00+00:00", "2026-09") is False
    assert _in_period("2026-09-30T16:59:59Z", "2026-09") is True
    assert _in_period("2026-12-31T18:00:00+00:00", "2027") is True
    assert _in_period("2026-12-31T18:00:00+00:00", "2027-Q1") is True
    assert _in_period("2026-10-01T00:30:00+07:00", "2026-10") is True
    assert _in_period("2026-10-01", "2026-10") is True


def test_date01_home_default_month_wib(monkeypatch):
    from datetime import datetime
    from services import home_service as hs
    from services.analytics_time import WIB
    monkeypatch.setattr(hs, "now_wib", lambda: datetime(2026, 10, 1, 1, 0, tzinfo=WIB))
    assert hs._current_month() == "2026-10" and hs._today_prefix() == "2026-10-01"
    assert hs._today_range() == {"$gte": "2026-09-30T17:00:00+00:00", "$lt": "2026-10-01T17:00:00+00:00"}


# V3-PO-02 — amandemen qty → qty diterima selalu minta persetujuan ulang
def test_po02_qty_to_received_forces_reapproval(monkeypatch):
    from services import po_amendment_service as pas
    import dependencies

    async def items(payload, old_items, received_map, *a, **k):
        return [{**old_items[0], "quantity": 960}]

    async def pricing(raw, *a, **k):
        return {"items": raw, "total_amount": 9600, "grand_total": 9600, "items_discount_total": 0,
                "order_discount_percent": 0, "order_discount_amount": 0, "discount_total": 0,
                "net_subtotal": 9600, "dpp": 9600, "ppn_rate": 0, "ppn_mode": "", "is_pkp": False, "ppn_amount": 0}

    async def appr(*a, **k):
        return {"approval_chain": [], "needs_approval": False, "required_role": None,
                "approval_reason": "", "price_deviation": {"flagged": False}}

    async def noop(*a, **k):
        return None
    monkeypatch.setattr(pas, "_build_items", items)
    monkeypatch.setattr(pas, "compute_order_pricing", pricing)
    monkeypatch.setattr(pas, "_build_approval", appr)
    monkeypatch.setattr(dependencies, "audit", noop)

    class P:
        reason, items, supplier_id, supplier_name, supplier_contact = "tutup selisih", [1], None, None, None
        warehouse_id, expected_delivery_date, notes, order_discount_percent, tax_mode = None, None, None, None, None
        amended_by = "t"

    async def go():
        await db.purchase_orders.insert_one({"id": "po9", "status": "partial", "entity_id": "ent_A",
                                             "updated_at": "x", "items": [
                                                 {"product_id": "p1", "sku": "S1", "quantity": 1000,
                                                  "received_qty": 960, "price": 10}]})
        return await pas.amend_po("po9", P(), {"name": "t", "id": "u"})
    res = run(go())
    po = res["po"]
    assert res["needs_approval"] is True and po["status"] == "waiting_approval"
    assert po["approval_chain"] and "qty_to_received" in po["approval_reason"]
