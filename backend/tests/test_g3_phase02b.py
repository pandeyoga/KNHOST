"""Gelombang 3 · Fase 02 (batch akhir) — uji SERVICE ASLI untuk 7 temuan terakhir + 3 penyelesaian parsial.

DB uji terpisah (BUKAN data pelanggan).

Jalankan:
    cd /app/backend && DB_NAME=g3_audit_phase02 python -m pytest tests/test_g3_phase02b.py -q
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

if not os.environ.get("DB_NAME", "").startswith("g3_audit"):
    pytest.skip("Set DB_NAME=g3_audit_* — tes ini menulis ke database uji sendiri.",
                allow_module_level=True)

from db import db  # noqa: E402

SCOPE = ["ent_A", "ent_B"]


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def iso(days=0):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


@pytest.fixture(autouse=True)
def _clean():
    async def wipe():
        for c in await db.list_collection_names():
            await db[c].delete_many({})
    run(wipe())
    yield


def _roll(rid, **kw):
    base = {"id": rid, "roll_no": rid.upper(), "product_id": "p1", "owner_entity_id": "ent_A",
            "warehouse_id": "wh1", "status": "available", "length_initial": 10.0, "length_remaining": 10.0,
            "unit": "meter", "lot": "L1", "grade": "A", "active_movement": None, "rfid_tag_id": None,
            "created_at": iso(-5), "updated_at": iso(-5)}
    base.update(kw)
    return base


async def _seed_master():
    await db.products.insert_one({"id": "p1", "sku": "SKU1", "name": "Kain 1", "base_unit": "meter",
                                  "category": "FAB"})
    await db.warehouses.insert_many([{"id": "wh1", "name": "Transit"}, {"id": "wh2", "name": "Gudang 2"}])


# ── V3-WEIGHT-01 ─────────────────────────────────────────────────────────────
def test_weight01_concurrent_split_conserves_weight():
    from services import roll_service as rs

    async def go():
        await _seed_master()
        await db.inventory_rolls.insert_one(_roll("r_w", weight_kg=3.0, secondary_measures={"kg": 3.0}))
        snap = await db.inventory_rolls.find_one({"id": "r_w"}, {"_id": 0})
        # Dua potongan BERSAMAAN dari snapshot yang sama (kasus repro audit)
        a, b = await asyncio.gather(rs._split_roll(dict(snap), 2, "so_1"), rs._split_roll(dict(snap), 2, "so_2"))
        parent = await db.inventory_rolls.find_one({"id": "r_w"}, {"_id": 0})
        return parent, [a, b]
    parent, kids = run(go())
    assert parent["length_remaining"] == 6.0
    total = round(parent["weight_kg"] + sum(k["weight_kg"] for k in kids), 3)
    assert total == 3.0, f"berat total harus tetap 3 kg, dapat {total} (induk {parent['weight_kg']})"
    assert parent["secondary_measures"]["kg"] == parent["weight_kg"]
    assert all(k["weight_provenance"]["estimated"] is True for k in kids)


def test_weight01_confirm_cut_uses_pre_cut_basis_and_conserves():
    from services import roll_service as rs

    async def go():
        await _seed_master()
        await db.inventory_rolls.insert_one(_roll("r_c", weight_kg=3.0))
        snap = await db.inventory_rolls.find_one({"id": "r_c"}, {"_id": 0})
        r1 = await rs._reserve_length(snap, 2, "so_1")
        r2 = await rs._reserve_length(snap, 2, "so_2")
        out = await asyncio.gather(rs.confirm_cut("r_c", r1["reservation_id"]),
                                   rs.confirm_cut("r_c", r2["reservation_id"]))
        parent = await db.inventory_rolls.find_one({"id": "r_c"}, {"_id": 0})
        return parent, [o["child"] for o in out]
    parent, kids = run(go())
    assert parent["length_remaining"] == 6.0
    assert [k["weight_kg"] for k in kids] == [0.6, 0.6]
    assert round(parent["weight_kg"] + 1.2, 3) == 3.0


# ── V3-WMS-02 ────────────────────────────────────────────────────────────────
def test_wms02_loading_check_scoped_per_shipment_warehouse():
    from services import loading_check_service as lc

    async def go():
        await _seed_master()
        await db.sales_orders.insert_one({"id": "so_L", "number": "SO-L", "entity_id": "ent_A"})
        await db.rfid_tags.insert_one({"id": "t1", "epc": "E" * 24, "status": "active", "roll_id": "r_ready"})
        await db.inventory_rolls.insert_many([
            _roll("r_ready", status="committed", rfid_tag_id="t1",
                  reserved_ref={"type": "sales_order", "id": "so_L"}),
            _roll("r_cutwait", warehouse_id="wh2", length_reserved=3.0,
                  length_reservations=[{"id": "rsv1", "ref": {"type": "sales_order", "id": "so_L"},
                                        "qty": 3.0, "status": "reserved"}]),
        ])
        sess = await lc.start("so_L", ["ent_A"], "tester", "wh1")
        with pytest.raises(HTTPException) as e:
            await lc.start("so_L", ["ent_A"], "tester", "wh2")
        return sess, e.value
    sess, err = run(go())
    assert sess["warehouse_id"] == "wh1" and len(sess["expected"]) == 1
    assert err.status_code == 409, "gudang 2 tetap tertahan potong miliknya sendiri"


def test_wms02_result_per_warehouse_and_guard():
    from services import loading_check_service as lc

    async def go():
        await _seed_master()
        await db.sales_orders.insert_one({"id": "so_M", "number": "SO-M", "entity_id": "ent_A"})
        await db.inventory_rolls.insert_many([
            _roll("r1", status="committed", reserved_ref={"type": "sales_order", "id": "so_M"}),
            _roll("r2", warehouse_id="wh2", status="committed", reserved_ref={"type": "sales_order", "id": "so_M"}),
        ])
        await lc.override("so_M", "override uji wh1", "spv", "wh1")
        await lc.dispatch_guard("so_M", "wh1")  # lolos: hasil gudang 1
        st = await lc.status_for_order("so_M", "wh2")
        return st
    st = run(go())
    assert st["last_result"] is None, "hasil gudang 1 tidak berlaku untuk pengiriman gudang 2"
    assert [w["warehouse_id"] for w in st["by_warehouse"]] == ["wh1"]


# ── D4-STOCK-01 ──────────────────────────────────────────────────────────────
def test_stock01_value_and_velocity_not_double_counted(monkeypatch):
    from services import stock_analytics_service as sas
    from entity_scope import EntityContext

    async def settings(_e=None):
        return {}
    monkeypatch.setattr(sas, "resolve_list_scope", lambda c, q, ctx, e=None: q)
    monkeypatch.setattr(sas, "get_effective_settings", settings)

    async def go():
        await _seed_master()
        await db.inventory_balances.insert_many([
            {"product_id": "p1", "warehouse_id": "wh1", "owner_entity_id": "ent_A", "on_hand_qty": 10},
            {"product_id": "p1", "warehouse_id": "wh1", "owner_entity_id": "ent_B", "on_hand_qty": 20}])
        await db.inventory_rolls.insert_many([
            _roll("ra", base_unit_cost=10.0),
            _roll("rb", owner_entity_id="ent_B", length_remaining=20.0, base_unit_cost=20.0)])
        await db.inventory_movements.insert_many([
            {"product_id": "p1", "warehouse_id": "wh1", "owner_entity_id": "ent_A", "movement_type": "outbound_ship",
             "quantity": -3, "timestamp": iso(-1)},
            {"product_id": "p1", "warehouse_id": "wh1", "owner_entity_id": "ent_B", "movement_type": "outbound_ship",
             "quantity": -7, "timestamp": iso(-1)}])
        ctx = EntityContext({"id": "u", "role": "super_admin"}, "ent_A", SCOPE, True)
        return await sas.compute_stock_analytics(ctx, None)
    res = run(go())
    row = next(r for r in res["rows"] if r["product_id"] == "p1")
    assert row["value"] == 500.0, row
    assert row["sold_qty_window"] == 10.0, row
    assert row["on_hand_qty"] == 30.0


# ── D4-AI-06 ─────────────────────────────────────────────────────────────────
def test_ai06_product_group_mixed_units_has_no_grand_total(monkeypatch):
    from services import analytics_engine as ae

    class Sc:
        entity_ids = ["ent_A"]

    async def scope(*a, **k):
        return Sc()

    async def gate(m, sc):
        return m, []

    async def compute(shown, dims, grain, p, filters, sc, warnings, inc):
        return {("p_m",): {"stock_qty": 10.0}, ("p_k",): {"stock_qty": 5.0}}, {"stock_qty": 15.0}

    async def noop(*a, **k):
        return None

    async def labels(d, ids):
        return {}
    monkeypatch.setattr(ae, "build_scope", scope)
    monkeypatch.setattr(ae, "_gate", gate)
    monkeypatch.setattr(ae, "_compute", compute)
    monkeypatch.setattr(ae, "save_result", noop)
    monkeypatch.setattr(ae, "_labels", labels)

    async def go():
        await db.products.insert_many([{"id": "p_m", "base_unit": "meter"}, {"id": "p_k", "base_unit": "kg"}])
        return await ae.query_metrics({"metrics": ["stock_qty"], "group_by": ["product"]},
                                      {"id": "u", "role": "super_admin"}, None)
    out = run(go())
    assert out["totals"]["stock_qty"] is None, out["totals"]
    assert out["totals_by_unit"] == {"meter": {"stock_qty": 10.0}, "kg": {"stock_qty": 5.0}}
    shares = {r["product_id"]: r.get("stock_qty_share") for r in out["rows"]}
    assert shares == {"p_m": 100.0, "p_k": 100.0}, "porsi dihitung per satuan"


# ── D4-AI-05 (jalur live) ────────────────────────────────────────────────────
def test_ai05_live_stock_splits_length_reserved(monkeypatch):
    from services import analytics_engine as ae
    captured = {}

    async def fake_group(coll, pre, dims, src, grain, acc):
        captured["acc"] = acc
        pipe = pre + [{"$group": {"_id": None, **acc}}]
        r = await db[coll].aggregate(pipe).to_list(1)
        return {(): r[0]}
    monkeypatch.setattr(ae, "_group", fake_group)

    class Sc:
        entity_ids = ["ent_A"]
        line_q = {}

    async def go():
        await db.inventory_rolls.insert_one(_roll("r5", length_reserved=3.0))
        fn = next(getattr(ae, n) for n in dir(ae) if n == "_src_stock")
        p = ae.period_from_args(None)
        return await fn(["stock_available_qty", "stock_reserved_qty"], [], None, p, [], Sc(), [], False)
    res = run(go())
    vals = res[()]
    assert vals["stock_available_qty"] == 7.0 and vals["stock_reserved_qty"] == 3.0, vals


# ── D4-PLAN-05 ───────────────────────────────────────────────────────────────
def test_plan05_one_po_not_promised_to_two_so(monkeypatch):
    from services import stock_bucket_service as sbs

    async def incoming(pid, ent):
        return [{"qty": 100.0, "eta": "2026-12-01", "source": "po", "po_number": "PO-1"}]
    monkeypatch.setattr(sbs, "_incoming_supply", incoming)

    async def go():
        await _seed_master()
        for i, ts in ((1, iso(-3)), (2, iso(-1))):
            await db.sales_orders.insert_one({
                "id": f"so_{i}", "number": f"SO-{i}", "entity_id": "ent_A", "has_backorder": True,
                "status": "waiting_stock", "created_at": ts,
                "backorders": [{"id": f"bo_{i}", "product_id": "p1", "backorder_qty": 100.0, "created_at": ts}]})
        return await sbs.pending_so_board({"entity_id": "ent_A"})
    rows = {r["order_id"]: r for r in run(go())}
    assert rows["so_1"]["covered_qty"] == 100.0 and rows["so_1"]["coverage"] == "covered"
    assert rows["so_2"]["covered_qty"] == 0.0 and rows["so_2"]["coverage"] == "uncovered"
    assert rows["so_2"]["uncovered_qty"] == 100.0
    assert rows["so_2"]["incoming_claimed_by_older"] == 100.0
    assert sum(r["covered_qty"] for r in rows.values()) == 100.0
    assert all(r["supply_is_forecast"] for r in rows.values())


# ── D4-PA-01 + D4-TAG-01 ─────────────────────────────────────────────────────
async def _seed_pa_roll(rid="r_pa", tag="t_pa"):
    await db.rfid_tags.insert_one({"id": tag, "epc": "A" * 23 + "1", "status": "active", "roll_id": rid,
                                   "owner_entity_id": "ent_A", "created_at": iso(-4)})
    await db.inventory_rolls.insert_one(_roll(rid, rfid_tag_id=tag, journey={
        "stage": "tag_verified", "routing": "store", "verified_tag_id": tag, "updated_at": iso(-3)}))


def test_pa01_so_cannot_take_roll_claimed_by_pa():
    from services import roll_service as rs
    from services import putaway_order_service as pa

    async def go():
        await _seed_master()
        await _seed_pa_roll()
        await pa.create_order("wh1", "wh2", ["r_pa"], SCOPE, "tester")
        roll = await db.inventory_rolls.find_one({"id": "r_pa"}, {"_id": 0})
        cands = await rs._available_rolls_for_order("p1", "ent_A", "so_X")
        part = await rs._reserve_length(roll, 6, "so_X")
        whole = await rs._reserve_single_roll("r_pa", "so_X")
        bal = await db.inventory_balances.find_one({"product_id": "p1", "warehouse_id": "wh1"}, {"_id": 0})
        return cands, part, whole, bal
    cands, part, whole, bal = run(go())
    assert cands == [] and part is None and whole is None
    assert bal["available_qty"] == 0 and bal["hold_qty"] == 10.0, "roll diklaim PA keluar dari ATP"


def test_pa01_dispatch_rejects_live_length_reservation():
    from services import putaway_order_service as pa

    async def go():
        await _seed_master()
        await _seed_pa_roll()
        order = await pa.create_order("wh1", "wh2", ["r_pa"], SCOPE, "tester")
        await db.inventory_rolls.update_one({"id": "r_pa"}, {"$set": {"length_reserved": 6.0}})
        with pytest.raises(HTTPException) as e:
            await pa.dispatch(order["id"], SCOPE)
        roll = await db.inventory_rolls.find_one({"id": "r_pa"}, {"_id": 0})
        return e.value, roll
    err, roll = run(go())
    assert err.status_code == 409 and roll["status"] == "available" and roll["warehouse_id"] == "wh1"


def test_pa01_normal_dispatch_still_works():
    from services import putaway_order_service as pa

    async def go():
        await _seed_master()
        await _seed_pa_roll()
        order = await pa.create_order("wh1", "wh2", ["r_pa"], SCOPE, "tester")
        return await pa.dispatch(order["id"], SCOPE)
    assert run(go())["status"] == "in_transit"


def test_tag01_retired_and_pending_tags_rejected_until_reverified():
    from services import putaway_order_service as pa
    from services import rfid_service

    async def go():
        await _seed_master()
        await _seed_pa_roll()
        await rfid_service.retire_tag("t_pa", SCOPE)
        errs = []
        with pytest.raises(HTTPException) as e1:
            await pa.create_order("wh1", "wh2", ["r_pa"], SCOPE, "tester")
        errs.append(e1.value)
        await db.rfid_tags.insert_one({"id": "t_new", "epc": "B" * 24, "status": "pending_print",
                                       "roll_id": "r_pa", "created_at": iso()})
        await db.inventory_rolls.update_one({"id": "r_pa"}, {"$set": {"rfid_tag_id": "t_new"}})
        with pytest.raises(HTTPException) as e2:
            await pa.create_order("wh1", "wh2", ["r_pa"], SCOPE, "tester")
        errs.append(e2.value)
        await db.rfid_tags.update_one({"id": "t_new"}, {"$set": {"status": "active"}})
        with pytest.raises(HTTPException) as e3:
            await pa.create_order("wh1", "wh2", ["r_pa"], SCOPE, "tester")
        errs.append(e3.value)
        ready_before = await pa._rolls_ready("wh1", SCOPE)
        await db.inventory_rolls.update_one({"id": "r_pa"}, {"$set": {"journey.verified_tag_id": "t_new"}})
        ok = await pa.create_order("wh1", "wh2", ["r_pa"], SCOPE, "tester")
        return errs, ready_before, ok
    errs, ready_before, ok = run(go())
    assert all(e.status_code == 400 for e in errs)
    assert "tidak punya tag" in errs[0].detail and "pending_print" in errs[1].detail
    assert "belum diverifikasi" in errs[2].detail
    assert ready_before == []
    assert ok["items"][0]["epc"] == "B" * 24


def test_tag01_retire_blocked_during_active_movement():
    from services import putaway_order_service as pa
    from services import rfid_service

    async def go():
        await _seed_master()
        await _seed_pa_roll()
        await pa.create_order("wh1", "wh2", ["r_pa"], SCOPE, "tester")
        with pytest.raises(HTTPException) as e:
            await rfid_service.retire_tag("t_pa", SCOPE)
        tag = await db.rfid_tags.find_one({"id": "t_pa"}, {"_id": 0})
        return e.value, tag
    err, tag = run(go())
    assert err.status_code == 409 and tag["status"] == "active"


# ── D4-RET-POLICY-01 ─────────────────────────────────────────────────────────
async def _seed_ret():
    await db.suppliers.insert_many([
        {"id": "sup_A", "name": "SupA", "return_policy": {"window_days": 30}},
        {"id": "sup_B", "name": "SupB", "return_policy": {"window_days": 1}}])
    await db.purchase_orders.insert_many([
        {"id": "po_A", "po_number": "PO-A", "entity_id": "ent_A", "status": "completed", "supplier_id": "sup_A",
         "created_at": iso(-10), "last_received_at": iso(-9), "items": [{"product_id": "p1"}]},
        {"id": "po_B", "po_number": "PO-B", "entity_id": "ent_B", "status": "completed", "supplier_id": "sup_B",
         "created_at": iso(-1), "last_received_at": iso(-60), "items": [{"product_id": "p1"}]}])


def test_retpolicy01_uses_physical_origin_not_latest_po():
    from services import return_policy_service as rps

    async def go():
        await _seed_ret()
        await db.inventory_rolls.insert_one(_roll("r_src", po_id="po_A", status="delivered",
                                                  reserved_ref={"type": "sales_order", "id": "so_R"}))
        return await rps._linked_supplier_deadline({"id": "so_R", "entity_id": "ent_A",
                                                    "items": [{"product_id": "p1"}]}, 14)
    out = run(go())
    assert out["supplier_id"] == "sup_A" and out["po_number"] == "PO-A", out


def test_retpolicy01_cut_child_traced_via_parent():
    from services import return_policy_service as rps

    async def go():
        await _seed_ret()
        await db.inventory_rolls.insert_many([
            _roll("r_parent", po_id="po_A"),
            _roll("r_child", parent_roll_id="r_parent", status="delivered",
                  reserved_ref={"type": "sales_order", "id": "so_C"})])
        return await rps._linked_supplier_deadline({"id": "so_C", "entity_id": "ent_A"}, 14)
    assert run(go())["supplier_id"] == "sup_A"


def test_retpolicy01_untraceable_falls_back_and_flags_admin(monkeypatch):
    from services import return_policy_service as rps

    async def policy(**k):
        return {"id": "pol", "name": "Std", "window_days": 14, "link_to_supplier_window": True,
                "enforce_window": True, "allowed_return_types": ["defect"]}
    monkeypatch.setattr(rps, "resolve_sales_return_policy", policy)

    async def go():
        await _seed_ret()
        await db.inventory_rolls.insert_one(_roll("r_op", status="delivered", acquired={"via": "cycle_count_adjustment"},
                                                  reserved_ref={"type": "sales_order", "id": "so_U"}))
        order = {"id": "so_U", "entity_id": "ent_A", "dispatched_at": iso(-2), "items": [{"product_id": "p1"}]}
        return await rps.check_sales_return_eligibility(order)
    res = run(go())
    assert res["supplier_linked"]["source"] == "untraceable"
    assert res["needs_admin_review"] is True and res["eligible"] is True
    assert res["window_days"] == 14
    assert any("Asal barang tidak diketahui" in w for w in res["warnings"])
