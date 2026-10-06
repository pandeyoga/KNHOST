"""Gelombang 3 · Fase 01 — uji fault-injection (DB uji terpisah, BUKAN data pelanggan).

Jalankan:  cd /app/backend && DB_NAME=g3_audit_phase01 python -m pytest tests/test_g3_phase01.py -q
"""
import asyncio
import os

import pytest

if not os.environ.get("DB_NAME", "").startswith("g3_audit"):
    pytest.skip("Set DB_NAME=g3_audit_* — tes ini menulis ke database uji sendiri.", allow_module_level=True)

from db import db  # noqa: E402


class Fault(Exception):
    pass


def inject(coll, method, when, times=1):
    """Ganti `method` di kelas koleksi Motor (atribut db.x selalu objek baru) agar melempar Fault
    untuk koleksi `coll.name` saat `when(*args)` benar (maks `times` kali)."""
    cls, name = type(coll), coll.name
    orig = getattr(cls, method)
    state = {"left": times}

    def wrapped(self, *a, **kw):
        if self.name == name and state["left"] > 0 and when(*a, **kw):
            state["left"] -= 1

            async def boom():
                raise Fault(f"fault {name}.{method}")
            return boom()
        return orig(self, *a, **kw)
    setattr(cls, method, wrapped)
    return lambda: setattr(cls, method, orig)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def _clean():
    async def wipe():
        for c in await db.list_collection_names():
            await db[c].delete_many({})
    run(wipe())
    yield


# ── V3-PROD-01 / V3-PROD-02 ─────────────────────────────────────────────────────
from services import production_service as ps  # noqa: E402


async def _roll(length=20.0):
    await db.inventory_rolls.insert_one({"id": "r1", "product_id": "p1", "warehouse_id": "w1",
                                         "owner_entity_id": "e1", "status": "available",
                                         "length_remaining": length, "length_reserved": 0,
                                         "unit_cost": 10, "created_at": "2026-01-01"})


async def _state():
    roll = await db.inventory_rolls.find_one({"id": "r1"})
    live = await db.inventory_movements.count_documents(
        {"movement_type": "production_consume", "reversed": {"$ne": True}})
    revs = await db.inventory_movements.count_documents({"movement_type": "production_consume_reversal"})
    return roll["length_remaining"], live, revs


@pytest.mark.parametrize("stage", ["cas", "unset_pending"])
def test_prod01_fault_then_retry_consumes_once(stage):
    async def go():
        await _roll()
        if stage == "cas":
            undo = inject(db.inventory_rolls, "find_one_and_update", lambda *a, **k: True)
        else:
            undo = inject(db.inventory_movements, "update_one",
                          lambda f, u, **k: "$unset" in u and "pending" in u["$unset"])
        with pytest.raises(Fault):
            await ps._consume_material("p1", "w1", "e1", 5, "wo1", "op1")
        undo()
        await ps.reverse_operation("op1")          # yang dilakukan retry complete_work_order
        assert (await _state())[0] == 20.0
        qty, _v, _l = await ps._consume_material("p1", "w1", "e1", 5, "wo1", "op2")
        assert qty == 5
        length, live, _ = await _state()
        assert (length, live) == (15.0, 1)
        assert await db.inventory_movements.count_documents({"pending": True}) == 0
    run(go())


@pytest.mark.parametrize("stage", ["restore", "reversal_insert", "mark_reversed"])
def test_prod02_reverse_fault_restores_exactly_once(stage):
    async def go():
        await _roll(10)
        await ps._consume_material("p1", "w1", "e1", 5, "wo1", "op1")
        if stage == "restore":
            undo = inject(db.inventory_rolls, "update_one", lambda f, *a, **k: "op_marks" in f)
        elif stage == "reversal_insert":
            undo = inject(db.inventory_movements, "update_one", lambda f, u, **k: k.get("upsert"))
        else:
            undo = inject(db.inventory_movements, "update_one",
                          lambda f, u, **k: "$set" in u and u["$set"].get("reversed") is True)
        with pytest.raises(Fault):
            await ps.reverse_operation("op1")
        undo()
        await ps.reverse_operation("op1")
        await ps.reverse_operation("op1")          # response hilang → dipanggil lagi
        length, live, revs = await _state()
        assert (length, live, revs) == (10.0, 0, 1)
    run(go())


# ── V3-CUT-01 ───────────────────────────────────────────────────────────────────
from services import roll_service as rs  # noqa: E402


async def _cut_roll():
    await db.products.insert_one({"id": "p1", "base_unit": "meter"})
    await db.inventory_rolls.insert_one({
        "id": "r1", "roll_no": "R-1", "product_id": "p1", "warehouse_id": "w1", "owner_entity_id": "e1",
        "status": "available", "unit": "meter", "length_initial": 100.0, "length_remaining": 100.0,
        "length_reserved": 30.0, "created_at": "2026-01-01",
        "length_reservations": [{"id": "rsv1", "qty": 30.0, "status": "reserved",
                                 "ref": {"type": "sales_order", "id": "so1"}}]})


@pytest.mark.parametrize("stage", ["child_insert", "movement"])
def test_cut01_fault_after_parent_decrement_resumes_once(stage):
    async def go():
        await _cut_roll()
        if stage == "child_insert":
            undo = inject(db.inventory_rolls, "insert_one", lambda *a, **k: True)
        else:
            undo = inject(db.inventory_movements, "update_one", lambda f, u, **k: k.get("upsert"))
        with pytest.raises(Fault):
            await rs.confirm_cut("r1", "rsv1")
        undo()
        await rs.confirm_cut("r1", "rsv1")
        parent = await db.inventory_rolls.find_one({"id": "r1"})
        kids = await db.inventory_rolls.count_documents({"parent_roll_id": "r1"})
        cuts = await db.inventory_movements.count_documents({"movement_type": "roll_cut"})
        assert (parent["length_remaining"], kids, cuts, parent.get("pending_cut_ops")) == (70.0, 1, 1, [])
        child = await db.inventory_rolls.find_one({"parent_roll_id": "r1"})
        assert child["length_remaining"] == 30.0 and child["reserved_ref"]["id"] == "so1"
        with pytest.raises(Exception):
            await rs.confirm_cut("r1", "rsv1")       # sudah tuntas → tidak ada potong kedua
    run(go())


# ── V3-BANK-01 ──────────────────────────────────────────────────────────────────
from services import bank_recon_service as br  # noqa: E402


def test_bank01_two_parallel_matches_on_one_line():
    async def go():
        await db.bank_statement_lines.insert_one({"id": "L1", "status": "unmatched", "amount": 100})
        for t in ("T1", "T2"):
            await db.cash_transactions.insert_one({"id": t, "amount": 100, "status": "posted"})
        line = await db.bank_statement_lines.find_one({"id": "L1"}, {"_id": 0})
        res = await asyncio.gather(br._link(line, [{"txn_id": "T1", "amount": 100}], "a", "manual", "single"),
                                   br._link(line, [{"txn_id": "T2", "amount": 100}], "b", "manual", "single"),
                                   return_exceptions=True)
        assert sum(1 for r in res if isinstance(r, ValueError)) == 1
        recon = [t["reconciled_amount"] async for t in db.cash_transactions.find({}) if t.get("reconciled_amount")]
        ln = await db.bank_statement_lines.find_one({"id": "L1"})
        assert recon == [100] and len(ln["matched_txn_ids"]) == 1 and "match_lock" not in ln
    run(go())


# ── V3-MASTER-01 ────────────────────────────────────────────────────────────────
from services import master_governance_service as mg  # noqa: E402


def test_master01_batch_durable_before_product_change(monkeypatch):
    async def go():
        await db.products.insert_one({"id": "p1", "sku": "S1", "category": "old"})
        prop = {"product_id": "p1", "sku": "S1", "field": "category", "from": "old", "to": "new"}

        async def fake_preview(_f):
            return {"preview_signature": "sig", "proposals": [prop]}
        monkeypatch.setattr(mg, "preview", fake_preview)
        undo = inject(db.master_governance_batches, "update_one", lambda *a, **k: True)
        with pytest.raises(Fault):
            await mg.apply_batch({}, "sig", [prop], "n", {"name": "x"})
        undo()
        b = await db.master_governance_batches.find_one({})
        assert b["status"] == "applying"
        await mg.rollback_batch(b["id"], "pulihkan batch", {"name": "x"})
        assert (await db.products.find_one({"id": "p1"}))["category"] == "old"
    run(go())


# ── D4-GL-01 / D4-GL-02 ─────────────────────────────────────────────────────────
from services import gl_service as gl  # noqa: E402


def test_gl01_void_rejected_after_reverse_claim():
    async def go():
        await db.journal_entries.insert_one({"id": "je1", "status": "posted", "source_type": "manual",
                                             "entity_id": "e1", "date": "2030-01-05",
                                             "reversed_by_entry_id": "je2"})
        with pytest.raises(ValueError):
            await gl.void_entry("je1", {"name": "x"})
        assert (await db.journal_entries.find_one({"id": "je1"}))["status"] == "posted"
    run(go())


def test_gl02_manual_entry_rejects_nan_infinity(monkeypatch):
    async def go():
        async def accounts(codes, _eid):
            return {c: {"name": c, "is_postable": True} for c in codes}
        monkeypatch.setattr(gl, "effective_accounts", accounts)

        class P:
            entity_id, date, description = "e1", "2030-01-05", "x"
            lines = [{"account_code": "6-1000", "debit": float("nan"), "credit": 0},
                     {"account_code": "1-1000", "debit": 0, "credit": float("nan")}]
        for bad in (float("nan"), float("inf")):
            P.lines[0]["debit"], P.lines[1]["credit"] = bad, bad
            with pytest.raises(ValueError):
                await gl.create_manual_entry(P, {"name": "x"})
        assert await db.journal_entries.count_documents({}) == 0
    run(go())


# ── D4-ASSET-01 / D4-ASSET-02 ───────────────────────────────────────────────────
from services import fixed_asset_service as fa  # noqa: E402


def _asset_fixture(monkeypatch):
    async def fake_post(**kw):
        sid = f"{kw['asset_id']}:{kw['period']}"
        if await db.journal_entries.find_one({"source_id": sid}):
            return None
        await db.journal_entries.insert_one({"id": f"je_{sid}", "number": sid, "status": "posted",
                                             "source_type": "fixed_asset_depreciation", "source_id": sid,
                                             "amount": kw["amount"]})
        return {"id": f"je_{sid}", "number": sid}
    monkeypatch.setattr(fa.gl_service, "post_depreciation", fake_post)
    return db.fin_fixed_assets.insert_one({"id": "a1", "status": "active", "acquisition_cost": 1200,
                                          "salvage_value": 0, "useful_life_months": 12,
                                          "accumulated_depreciation": 0, "depreciated_months": 0})


def test_asset02_concurrent_periods_accumulate(monkeypatch):
    async def go():
        await _asset_fixture(monkeypatch)
        await asyncio.gather(fa.run_depreciation("2030-01", {"name": "x"}),
                             fa.run_depreciation("2030-02", {"name": "y"}))
        a = await db.fin_fixed_assets.find_one({"id": "a1"})
        assert (a["accumulated_depreciation"], a["depreciated_months"], a["book_value"]) == (200, 2, 1000)
        assert await db.fin_depreciation_entries.count_documents({}) == 2
    run(go())


def test_asset01_fault_after_journal_retry_completes_once(monkeypatch):
    async def go():
        await _asset_fixture(monkeypatch)
        undo = inject(db.fin_depreciation_entries, "update_one", lambda *a, **k: True)
        with pytest.raises(Fault):
            await fa.run_depreciation("2030-01", {"name": "x"})
        undo()
        await db.fin_fixed_assets.update_one({"id": "a1"}, {"$set": {"depreciation_claims.2030-01": "2000-01-01"}})
        await fa.run_depreciation("2030-01", {"name": "x"})
        await fa.run_depreciation("2030-01", {"name": "x"})
        a = await db.fin_fixed_assets.find_one({"id": "a1"})
        assert (a["accumulated_depreciation"], a["depreciated_months"]) == (100, 1)
        assert await db.fin_depreciation_entries.count_documents({}) == 1
        assert await db.journal_entries.count_documents({}) == 1
    run(go())

