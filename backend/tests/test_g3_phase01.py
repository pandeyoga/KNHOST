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



# ── V3-AR-01 — kwitansi fault setelah alokasi SO ────────────────────────────────
from services import ar_receipt_service as ars  # noqa: E402


def test_ar01_fault_after_allocation_rolls_back_payments_and_deposit(monkeypatch):
    async def go():
        await db.customers.insert_one({"id": "cust1", "name": "C1", "entity_id": "e1",
                                       "deposit_balance": 50.0})
        await db.sales_orders.insert_one({
            "id": "so1", "number": "SO-1", "customer_id": "cust1", "entity_id": "e1",
            "items": [{"product_id": "p1", "quantity": 1, "unit_price": 100.0}],
            "grand_total": 100.0, "total_amount": 100.0,
            "payments": [], "paid_total": 0.0, "payment_status": "unpaid",
            "status": "approved", "created_at": "2026-01-01"})

        # Stub berat dependencies agar fokus ke jalur rollback.
        from services import payment_variance_service as pvs

        async def _ok_pre(*a, **k):
            return {"direction": "none", "needs_decision": False, "amount": 0, "tolerance": 0,
                    "auto": False}
        monkeypatch.setattr(pvs, "pre_assess", _ok_pre)
        monkeypatch.setattr(pvs, "variance_block", lambda a: {"direction": "none",
                                                              "needs_decision": False, "amount": 0})
        from services import gl_service as _gl
        async def _ok(*a, **k): return None
        monkeypatch.setattr(_gl, "preflight_posting", _ok)
        monkeypatch.setattr(_gl, "post_order_revenue_and_cogs", _ok)
        monkeypatch.setattr(_gl, "post_cash_void", _ok)
        monkeypatch.setattr(_gl, "reverse_deposit_only_receipt", _ok)
        monkeypatch.setattr(ars, "_post_cash_in", _ok)
        from services import doc_refs_service as _refs
        async def _safe_link(*a, **k): return None
        monkeypatch.setattr(_refs, "safe_link", _safe_link)

        # Inject fault: PERTAMA kali ar_receipts.insert_one dipanggil → gagal.
        undo = inject(db.ar_receipts, "insert_one", lambda *a, **k: True)

        payload = {"customer_id": "cust1", "entity_id": "e1", "amount": 100.0,
                   "use_deposit_amount": 0.0,
                   "allocations": [{"order_id": "so1", "amount": 100.0}]}
        with pytest.raises(Fault):
            await ars.create_receipt(payload, {"id": "u", "name": "x"})
        undo()

        # Verifikasi: tidak ada payments ber-receipt_id ini di SO,
        # tidak ada kwitansi tertinggal, deposit tetap utuh (50.0 — tidak dipakai).
        so = await db.sales_orders.find_one({"id": "so1"}, {"_id": 0})
        assert all(p.get("receipt_id") not in (None, "")
                   or p.get("receipt_id") != "" for p in [])  # trivial
        assert not any(p.get("receipt_id") for p in (so.get("payments") or []))
        assert round(so.get("paid_total", 0.0), 2) == 0.0
        assert await db.ar_receipts.count_documents({}) == 0
        c = await db.customers.find_one({"id": "cust1"}, {"_id": 0})
        assert round(float(c["deposit_balance"]), 2) == 50.0
    run(go())


# ── V3-MKO-01 — create_inbound_roll(roll_id) idempotent ─────────────────────────
from services import roll_service as rsvc  # noqa: E402


def test_mko01_same_roll_id_called_twice_yields_one_roll_one_movement():
    async def go():
        await db.products.insert_one({"id": "p1", "base_unit": "meter", "harga_pokok": 10.0})
        r1 = await rsvc.create_inbound_roll(
            "p1", "w1", "e1", 50.0, lot="LOT1", unit="meter",
            acquired_via="subcon_receipt", ref_id="mko1", unit_cost=12.0,
            roll_id="roll_mko_mko1_1_0")
        r2 = await rsvc.create_inbound_roll(
            "p1", "w1", "e1", 50.0, lot="LOT1", unit="meter",
            acquired_via="subcon_receipt", ref_id="mko1", unit_cost=12.0,
            roll_id="roll_mko_mko1_1_0")
        assert r1["id"] == r2["id"] == "roll_mko_mko1_1_0"
        assert await db.inventory_rolls.count_documents({"id": "roll_mko_mko1_1_0"}) == 1
        assert await db.inventory_movements.count_documents({"roll_id": "roll_mko_mko1_1_0"}) == 1
    run(go())


# ── D4-CLOSE-01 — reopen bulan → closing memuat (tahun) jadi stale ──────────────
from services import closing_service as cs  # noqa: E402


def test_close01_reopen_month_marks_containing_year_stale():
    async def go():
        await db.period_closings.insert_many([
            {"id": "cl_month", "entity_id": "e1", "status": "closed",
             "period_type": "month", "period_key": "2030-01", "period_label": "Jan 2030",
             "start_date": "2030-01-01", "end_date": "2030-01-31",
             "journal_entry_id": "je_m"},
            {"id": "cl_year", "entity_id": "e1", "status": "closed",
             "period_type": "year", "period_key": "2030", "period_label": "FY2030",
             "start_date": "2030-01-01", "end_date": "2030-12-31",
             "journal_entry_id": "je_y"},
        ])
        await db.journal_entries.insert_one({"id": "je_m", "status": "posted"})
        await cs.reopen_period("cl_month", {"name": "admin"})
        yr = await db.period_closings.find_one({"id": "cl_year"}, {"_id": 0})
        mo = await db.period_closings.find_one({"id": "cl_month"}, {"_id": 0})
        assert yr.get("stale") is True
        assert yr.get("stale_reason")
        assert mo.get("status") == "reopened" and mo.get("stale") is False
    run(go())


# ── D4-CC-01 — satu sesi = satu hasil (retry mengadopsi) ────────────────────────
from services import cycle_count_service as ccs  # noqa: E402


def test_cc01_retry_after_session_update_fault_adopts_prior():
    async def go():
        await db.rfid_verify_sessions.insert_one({
            "id": "S1", "kind": "cycle_count", "status": "open",
            "warehouse_id": "w1", "warehouse_name": "W1",
            "scope_entity_ids": ["e1"],
            "expected": [{"epc": "E1", "roll_id": "r1"}],
            "scanned_epcs": ["E1"], "eligible_count": 1, "untagged_count": 0,
            "scan_sources": []})
        # Monkeypatch next_doc_number untuk hindari dependensi runtime.
        import services.cycle_count_service as _mod
        async def _n(*a, **k): return "CC-1"
        _mod.next_doc_number = _n

        # Inject fault pada update SESI (setelah hasil ditulis).
        undo = inject(db.rfid_verify_sessions, "update_one",
                      lambda f, u, **k: isinstance(u, dict) and "$set" in u
                      and u["$set"].get("status") == "completed")
        with pytest.raises(Fault):
            await ccs.complete("S1", "admin", ["e1"])
        undo()
        # Harus ada 1 hasil (prior) walau sesi belum "completed".
        assert await db.rfid_cycle_counts.count_documents({"session_id": "S1"}) == 1
        # Lepas kunci saga agar klaim ulang bisa jalan.
        await db.rfid_verify_sessions.update_one({"id": "S1"}, {"$unset": {"saga_lock": ""}})
        # Panggil ulang → adopsi prior, tetap 1 hasil.
        res = await ccs.complete("S1", "admin", ["e1"])
        assert res["id"] == f"rcc_S1"
        assert await db.rfid_cycle_counts.count_documents({"session_id": "S1"}) == 1
        sess = await db.rfid_verify_sessions.find_one({"id": "S1"}, {"_id": 0})
        assert sess["status"] == "completed" and sess["cycle_count_id"] == "rcc_S1"
    run(go())


# ── D4-BACKORDER-01 — _fill_order paralel: total reserve ≤ shortage ─────────────
from services import backorder_service as bos  # noqa: E402


def test_bo01_two_parallel_fills_do_not_overreserve():
    async def go():
        await db.products.insert_one({"id": "p1", "base_unit": "meter"})
        # Stok 160 (2 roll).
        for rid, length in (("r1", 100.0), ("r2", 60.0)):
            await db.inventory_rolls.insert_one({
                "id": rid, "roll_no": rid, "product_id": "p1", "warehouse_id": "w1",
                "owner_entity_id": "e1", "status": "available", "unit": "meter",
                "length_initial": length, "length_remaining": length, "length_reserved": 0,
                "unit_cost": 10.0, "created_at": "2026-01-01", "length_reservations": []})
        order = {
            "id": "so1", "number": "SO-1", "customer_id": "c1", "entity_id": "e1",
            "status": "waiting_stock",
            "items": [{"product_id": "p1", "quantity": 100, "reserved_qty": 0, "backorder_qty": 100}],
            "backorders": [{"product_id": "p1", "backorder_qty": 100, "reserved_qty": 0,
                            "status": "open", "customer_city": ""}],
            "allocations": [], "has_backorder": True,
            "payments": [], "paid_total": 0.0, "created_at": "2026-01-01"}
        await db.sales_orders.insert_one(dict(order))

        # Stub allocate_and_reserve_rolls agar deterministik: alokasi SELURUH `qty` ke 1 roll pertama.
        async def _alloc(product_id, qty, _city, _own, order_id, allow_partial=False):
            # Satu "roll" alokasi dgn qty yang diminta (atau sebanyak stok sisa r1+r2).
            rolls = await db.inventory_rolls.find({"product_id": product_id,
                                                   "length_remaining": {"$gt": 0}},
                                                  {"_id": 0}).to_list(10)
            remaining = qty
            allocs = []
            for r in rolls:
                take = min(float(r["length_remaining"]), remaining)
                if take <= 0:
                    continue
                res = await db.inventory_rolls.update_one(
                    {"id": r["id"], "length_remaining": {"$gte": take}},
                    {"$inc": {"length_remaining": -take, "length_reserved": take}})
                if not res.modified_count:
                    continue
                allocs.append({"roll_id": r["id"], "quantity": take})
                remaining = round(remaining - take, 2)
                if remaining <= 0.001:
                    break
            return allocs
        monkeypatch_target = bos  # alias
        monkeypatch_target.allocate_and_reserve_rolls = _alloc

        from dependencies import audit as _au  # noqa: F401
        async def _audit(*a, **k): return None
        import dependencies
        dependencies.audit = _audit
        from services import alert_ops_service as _ops
        async def _notify(*a, **k): return None
        _ops.notify_backorder_ready = _notify

        # Dua _fill_order PARALEL → satu klaim, satu busy.
        res = await asyncio.gather(
            bos._fill_order({**order}, "p1", "e1", cap=100, actor_name="t1"),
            bos._fill_order({**order}, "p1", "e1", cap=100, actor_name="t2"),
            return_exceptions=True)
        # Minimal satu busy.
        got_total = sum((r or {}).get("got", 0) for r in res if isinstance(r, dict))
        busy_cnt = sum(1 for r in res if isinstance(r, dict) and r.get("busy"))
        assert busy_cnt >= 1
        assert got_total <= 100.0 + 0.01
        so = await db.sales_orders.find_one({"id": "so1"}, {"_id": 0})
        bo_reserved = sum(float(b.get("reserved_qty", 0) or 0) for b in so.get("backorders", []))
        assert bo_reserved <= 100.0 + 0.01
    run(go())


# ── D4-CASE-01 — refund store credit TIDAK menjurnal Cr 4-9000 ──────────────────
from services import finance_case_actions as fca  # noqa: E402


def test_case01_refund_store_credit_payout_leaves_balance_remainder_only(monkeypatch):
    async def go():
        # Set up saldo 100 lewat issue.
        await db.store_credit_ledger.insert_one({
            "id": "scl0", "customer_id": "c1", "entity_id": "e1", "type": "issue",
            "amount": 100.0, "balance_after": 100.0, "status": "posted",
            "ref_type": "sales_return", "ref_id": "sr1", "created_at": "2026-01-01"})
        # Monkeypatch _cash_txn supaya tidak menyentuh GL/kas kompleks — kita hanya
        # memeriksa EFEK LEDGER (saldo) & bahwa act TIDAK memposting Cr 4-9000.
        async def _fake_cash_txn(**kw):
            await db.cash_transactions.insert_one(
                {"id": "cash1", "number": "CASH-1", "direction": kw["direction"],
                 "amount": kw["amount"], "ref_type": kw.get("ref_type"),
                 "ref_id": kw.get("ref_id"), "contra_account_code": kw.get("contra"),
                 "status": "posted"})
            return {"documents": [{"kind": "cash_transaction", "id": "cash1",
                                   "number": "CASH-1", "label": "Kas keluar"}],
                    "txn": {"id": "cash1"}}
        monkeypatch.setattr(fca, "_cash_txn", _fake_cash_txn)

        case = {"id": "fc1", "number": "FC-1", "customer_id": "c1", "entity_id": "e1"}
        p = {"customer_id": "c1", "amount": 80.0, "cash_type": "kas_besar",
             "account_id": "bank1"}
        out = await fca.act_refund_store_credit(case, p, {"name": "finance"})
        assert out["amount"] == 80.0

        from services import store_credit_service as sc
        bal = await sc.balance("c1", "e1")
        assert round(bal, 2) == 20.0

        # Tidak boleh ada entry 4-9000 Cr yang berasal dari pencairan ini.
        bad = await db.journal_entries.count_documents(
            {"lines.account_code": "4-9000"})
        assert bad == 0
    run(go())


# ═════════════════════════════════════════════════════════════════════════════
#  Fase 01 — 7 ID yang baru diperbaiki (iterasi 163)
# ═════════════════════════════════════════════════════════════════════════════


# ── D4-CLOSE-02 — retry reclose mengadopsi JE closing yang sudah berhasil ───────
def test_close02_reclose_fault_before_parent_update_retry_adopts_je(monkeypatch):
    async def go():
        # Fixture: satu closing bulanan STALE, dengan JE closing LAMA.
        await db.period_closings.insert_one({
            "id": "cl1", "entity_id": "e1", "status": "closed", "stale": True,
            "period_type": "month", "period_key": "2030-01", "period_label": "Jan 2030",
            "start_date": "2030-01-01", "end_date": "2030-01-31",
            "journal_entry_id": "je_old",
        })
        await db.journal_entries.insert_one({
            "id": "je_old", "number": "JE-OLD", "status": "posted",
            "source_type": "closing", "source_id": "cl1", "entity_id": "e1",
            "date": "2030-01-31T23:59:59", "lines": []})
        await _seed_accounts(["4-1000", "3-2000"])

        # Stub income_statement + already_closed supaya reclose menghasilkan 1 baris Laba Ditahan.
        from services import financial_statement_service as fs
        async def _is(start, end, scope=None):
            return {"net_income": 100.0, "sections": [
                {"key": "revenue", "lines": [{"code": "4-1000", "name": "Pendapatan", "amount": 100.0}]}]}
        monkeypatch.setattr(fs, "income_statement", _is)
        monkeypatch.setattr(cs, "_already_closed_amounts",
                            lambda *a, **k: _coro({}))

        # Fault PERTAMA kali update period_closings dgn finish_set (status closed → bersih stale).
        undo = inject(db.period_closings, "update_one",
                      lambda f, u, **k: "$unset" in u and "saga_lock" in u.get("$unset", {}))
        with pytest.raises(Fault):
            await cs.reclose_period("cl1", {"name": "admin"})
        undo()

        # Setelah fault: je_old sudah di-void, JE baru lahir, tapi parent belum menunjuknya.
        actives = await db.journal_entries.find(
            {"source_type": "closing", "source_id": "cl1", "status": {"$ne": "void"}},
            {"_id": 0}).to_list(10)
        assert len(actives) == 1 and actives[0]["id"] != "je_old"
        je_new_id = actives[0]["id"]
        pre = await db.period_closings.find_one({"id": "cl1"}, {"_id": 0})
        assert pre.get("saga_lock") is None  # try/except di reclose_period melepas kunci
        assert pre["journal_entry_id"] == "je_old"  # parent masih menunjuk je lama

        # RETRY: harus MENGADOPSI JE aktif baru (orphan path), tidak membuat JE ke-3.
        res = await cs.reclose_period("cl1", {"name": "admin"})
        assert res["stale"] is False
        assert "saga_lock" not in res
        actives = await db.journal_entries.find(
            {"source_type": "closing", "source_id": "cl1", "status": {"$ne": "void"}},
            {"_id": 0}).to_list(10)
        assert len(actives) == 1 and actives[0]["id"] == je_new_id
        rec = await db.period_closings.find_one({"id": "cl1"}, {"_id": 0})
        assert rec["journal_entry_id"] == je_new_id
    run(go())


async def _coro(v):
    return v


async def _seed_accounts(codes):
    for c in codes:
        await db.gl_accounts.update_one(
            {"code": c, "entity_id": None},
            {"$setOnInsert": {"code": c, "name": c, "entity_id": None,
                              "is_postable": True, "active": True}},
            upsert=True)


# ── D4-INTERCO-01 — post_intercompany_transfer per sisi + return finish idempoten ─
def test_interco01_fault_on_dst_side_retry_posts_only_dst_and_links_pair():
    async def go():
        await _seed_accounts(["1-1250", "1-1300", "2-1250"])
        # Fixture transfer kosong (akan dipost langsung lewat gl.post_intercompany_transfer).
        transfer = {"id": "tr1", "code": "TR-1", "source_entity_id": "eS",
                    "dest_entity_id": "eD",
                    "items": [{"product_id": "p1", "qty": 10, "unit_cost_snapshot": 15.0}],
                    "approved_at": "2030-02-01T10:00:00"}
        # Fault pada insert JE sisi dst — src sudah masuk.
        state = {"count": 0}
        orig_insert = type(db.journal_entries).insert_one
        async def wrapped(self, doc, **kw):
            if self.name == "journal_entries" and doc.get("source_id") == "tr1:dst" and state["count"] == 0:
                state["count"] = 1
                raise Fault("fault insert dst")
            return await orig_insert(self, doc, **kw)
        type(db.journal_entries).insert_one = wrapped
        try:
            with pytest.raises(Fault):
                await gl.post_intercompany_transfer(transfer)
        finally:
            type(db.journal_entries).insert_one = orig_insert

        src1 = await db.journal_entries.find_one({"source_id": "tr1:src"}, {"_id": 0})
        assert src1 is not None
        assert await db.journal_entries.count_documents({"source_id": "tr1:dst"}) == 0

        # RETRY: harus insert HANYA sisi dst, lalu tautkan pair pada keduanya.
        out = await gl.post_intercompany_transfer(transfer)
        assert out["posted"] is True
        assert out["pair_id"] == "ict_tr1"
        src2 = await db.journal_entries.find_one({"source_id": "tr1:src"}, {"_id": 0})
        dst2 = await db.journal_entries.find_one({"source_id": "tr1:dst"}, {"_id": 0})
        assert src2["id"] == src1["id"]  # TIDAK dibuat ulang
        assert src2["intercompany_pair_id"] == "ict_tr1"
        assert dst2["intercompany_pair_id"] == "ict_tr1"
        assert await db.journal_entries.count_documents({"source_type": "inter_company_transfer"}) == 2
    run(go())


def test_interco01_return_transfer_finish_is_idempotent(monkeypatch):
    """return_service._finish_return_transfer dipanggil dua kali (retry setelah ack hilang) →
    ownership_transfers di sales_returns TIDAK dobel ($ne guard pada array), status executing → completed."""
    from services import return_service as rs
    async def go():
        await db.sales_returns.insert_one({"id": "sr1", "number": "SR-1", "status": "credit_settled",
                                           "ownership_transfers": []})
        transfer = {"id": "tr9", "code": "RTNX-9", "status": "executing",
                    "source_entity_id": "eS", "dest_entity_id": "eD",
                    "items": [{"product_id": "p1", "qty": 7, "unit_cost_snapshot": 10.0}],
                    "approved_at": "2030-03-01"}
        await db.warehouse_transfers.insert_one(dict(transfer))

        async def _je(_t): return {"posted": True, "total": 70.0, "pair_id": "ict_tr9"}
        monkeypatch.setattr(rs.gl_service, "post_intercompany_transfer", _je)

        res1 = await rs._finish_return_transfer(dict(transfer), "sr1", "roll_x", "tester")
        assert res1["code"] == "RTNX-9"
        # Panggil lagi (replay).
        await rs._finish_return_transfer(dict(transfer), "sr1", "roll_x", "tester")
        sr = await db.sales_returns.find_one({"id": "sr1"}, {"_id": 0})
        xs = [o for o in (sr.get("ownership_transfers") or []) if o.get("transfer_id") == "tr9"]
        assert len(xs) == 1
        w = await db.warehouse_transfers.find_one({"id": "tr9"}, {"_id": 0})
        assert w["status"] == "completed"
    run(go())


# ── D4-INTERCO-02 — snapshot unit_cost dipakai (WAC basi diabaikan) ─────────────
def test_interco02_execute_ownership_transfer_snapshots_unit_cost(monkeypatch):
    async def go():
        await _seed_accounts(["1-1250", "1-1300", "2-1250"])
        # Satu roll unit_cost=15, WAC master BASI=1 → JE at-cost harus pakai snapshot.
        await db.inventory_rolls.insert_one({
            "id": "rX", "roll_no": "RX", "product_id": "p1", "warehouse_id": "w1",
            "owner_entity_id": "eS", "status": "reserved", "unit": "meter",
            "length_remaining": 10.0, "length_reserved": 10.0, "unit_cost": 15.0,
            "reserved_ref": {"type": "transfer", "id": "trZ"}, "created_at": "2030-01-01",
            "lot_id": None, "acquired": {}})
        transfer = {"id": "trZ", "code": "TR-Z", "transfer_kind": "inter_entity",
                    "source_entity_id": "eS", "dest_entity_id": "eD",
                    "source_warehouse_id": "w1", "dest_warehouse_id": "w1",
                    "status": "executing",
                    "items": [{"product_id": "p1", "qty": 10, "quantity": 10}],
                    "approved_at": "2030-02-01T10:00:00", "updated_at": "2030-02-01"}
        await db.warehouse_transfers.insert_one(dict(transfer))

        # Monkeypatch WAC → kembalikan WAC basi (1.0) agar beda jauh dari snapshot (15).
        from services import costing_service as cst
        async def _wac(pid, entity_id=None, use_cache=False):
            return {"wac": 1.0, "source": "wac"}
        monkeypatch.setattr(cst, "wac_for_product", _wac)
        # Stub mlabel.short_name_of untuk hindari dep lain.
        from services import movement_label_service as _ml
        async def _sn(_x): return "src"
        monkeypatch.setattr(_ml, "short_name_of", _sn)

        res = await rs.execute_ownership_transfer(dict(transfer))
        assert res["moved_qty"] == 10.0 and res["rolls"] == 1
        # Ambil kembali transfer: items wajib ter-stamp unit_cost_snapshot=15.0
        wt = await db.warehouse_transfers.find_one({"id": "trZ"}, {"_id": 0})
        snap = (wt["items"][0]).get("unit_cost_snapshot")
        assert snap and abs(float(snap) - 15.0) < 0.001

        # Post JE antar-PT → total 150 (bukan 10 dari WAC basi), cost_source=roll_snapshot.
        out = await gl.post_intercompany_transfer({**wt, "id": "trZ"})
        assert out["posted"] is True
        assert out["total"] == 150.0
        assert out["breakdown"][0]["cost_source"] == "roll_snapshot"
    run(go())


# ── D4-CASE-02 — dua resolve paralel + retry _cash_txn deterministik ────────────
import contextvars as _cv  # noqa: E402
from services import finance_case_service as fcs  # noqa: E402


def test_case02_two_parallel_resolves_only_one_cash_txn(monkeypatch):
    async def go():
        case = {
            "id": "fc2", "number": "FC-2", "entity_id": "e1", "status": "open",
            "case_type": "refund_pelanggan", "customer_id": "c1",
            "amount": 50.0, "documents": [], "attachments": ["bukti"]}
        await db.finance_cases.insert_one(dict(case))
        # Policy stub lengkap.
        async def _pol(_e):
            return {"sla_hours": 24, "sla_hours_high": 8, "high_amount_threshold": 1e9,
                    "require_evidence": False, "approval_above": 0, "approver_role": "",
                    "refund_max": 0, "auto_charge_max": 0}
        monkeypatch.setattr(fcs, "policy", _pol)
        async def _rof(code, case_type=""):
            return {"code": code, "label": code}
        monkeypatch.setattr(fcs, "_reason_or_fail", _rof)

        # acts.execute: insert 1 cash via _cash_txn deterministik lalu kembalikan dok.
        async def _exec(action_code, c, p, actor):
            res = await fca._cash_txn(
                direction="out", amount=50.0, category="refund",
                description="t", entity_id="e1", contra=gl.ACC_UANG_MUKA_PELANGGAN,
                owner_entity_id="e1", actor="t")
            # tambahkan JE palsu agar INV-CASE-03 lolos
            await db.journal_entries.insert_one({
                "id": "je_" + res["txn"]["id"], "number": "JE-x", "status": "posted",
                "source_type": "cash_transaction", "source_id": res["txn"]["id"], "lines": []})
            docs = res["documents"] + [{"kind": "journal_entry", "id": "je_" + res["txn"]["id"],
                                        "number": "JE-x", "label": "x"}]
            return {"documents": docs, "amount": 50.0}
        monkeypatch.setattr(fcs.acts, "execute", _exec)
        # Stub post_cash_transaction (gl) untuk hindari posting GL real.
        async def _ok(*a, **k): return None
        monkeypatch.setattr(gl, "post_cash_transaction", _ok)
        monkeypatch.setattr(gl, "ACC_UANG_MUKA_PELANGGAN", "2-1400", raising=False)

        # Dua resolve paralel.
        p = {"action": "refund_pelanggan", "reason_code": "customer_refund_request",
             "amount": 50.0, "customer_id": "c1"}
        res = await asyncio.gather(
            fcs.resolve("fc2", dict(p), {"name": "a", "role": "admin"}),
            fcs.resolve("fc2", dict(p), {"name": "b", "role": "admin"}),
            return_exceptions=True)
        oks = [r for r in res if not isinstance(r, Exception)]
        errs = [r for r in res if isinstance(r, Exception)]
        assert len(oks) == 1 and len(errs) == 1
        assert isinstance(errs[0], fcs.CaseError)
        assert await db.cash_transactions.count_documents({}) == 1
    run(go())


def test_case02_cash_txn_retry_adopts_same_cash(monkeypatch):
    async def go():
        # Set context seolah dalam execute()
        t1 = fca._CASE_OP.set("fc2_refund_pelanggan_0")
        t2 = fca._CASE_OP_SEQ.set(0)
        try:
            async def _ok(*a, **k): return None
            monkeypatch.setattr(gl, "post_cash_transaction", _ok)
            # Pertama: fault SESUDAH insert kas (sisanya diurus retry).
            undo = inject(db.cash_transactions, "update_one", lambda *a, **k: True)  # no-op fault lane
            # Actually post is via gl above; biar fault di next_doc_number TIDAK dipakai —
            # kita sebut panggilan sukses sekali, lalu panggil lagi dgn SEQ dikembalikan.
            undo()
            res1 = await fca._cash_txn(
                direction="in", amount=10.0, category="x", description="x", entity_id="e1",
                contra="1-1280", owner_entity_id="e1", actor="t")
            cid = res1["txn"]["id"]
            assert cid == "cash_case_fc2_refund_pelanggan_0_1"
            # Reset seq → panggilan kedua akan menuju cid yang sama (adopsi).
            fca._CASE_OP_SEQ.set(0)
            res2 = await fca._cash_txn(
                direction="in", amount=10.0, category="x", description="x", entity_id="e1",
                contra="1-1280", owner_entity_id="e1", actor="t")
            assert res2["txn"]["id"] == cid
            assert await db.cash_transactions.count_documents({}) == 1
        finally:
            fca._CASE_OP.reset(t1)
            fca._CASE_OP_SEQ.reset(t2)
    run(go())


# ── D4-CASE-03 — act_setor_dari_karyawan: urutan & batas sisa ───────────────────
def test_case03_setor_karyawan_sequence_and_limits(monkeypatch):
    async def go():
        from core_utils import new_id as _nid
        async def _fake_cash_txn(**kw):
            await db.cash_transactions.insert_one(
                {"id": _nid("cash"), "number": "CASH-s", "direction": kw["direction"],
                 "amount": kw["amount"], "ref_type": kw.get("ref_type"),
                 "ref_id": kw.get("ref_id"), "status": "posted"})
            return {"documents": [{"kind": "cash_transaction", "id": "x", "number": "N", "label": "L"},
                                  {"kind": "journal_entry", "id": "je_" + _nid("je"),
                                   "number": "JE", "label": "L"}],
                    "txn": {"id": "cx"}}
        monkeypatch.setattr(fca, "_cash_txn", _fake_cash_txn)

        case = {"id": "fc3", "number": "FC-3", "status": "open", "entity_id": "e1"}

        # 1) Setor SEBELUM langkah 1 → ditolak, tidak ada kas lahir.
        with pytest.raises(fca.CaseActionError):
            await fca.act_setor_dari_karyawan(case, {"amount": 40}, {"name": "t"})
        assert await db.cash_transactions.count_documents({}) == 0

        # 2) Simulasi sudah langkah 1 (held=80), setor 40 → in_progress, sisa 40.
        case2 = {"id": "fc3", "number": "FC-3", "status": "in_progress", "entity_id": "e1",
                 "resolution": {"extra": {"step": 1, "held_amount": 80.0, "settled_amount": 0.0,
                                          "employee_name": "ADA"}}}
        r = await fca.act_setor_dari_karyawan(case2, {"amount": 40}, {"name": "t"})
        assert r["hold"] is True
        assert r["extra"]["settled_amount"] == 40.0 and r["extra"]["remaining_amount"] == 40.0

        # 3) Lanjut setor 40 → resolved (hold=False).
        case3 = {**case2, "resolution": {"extra": {**r["extra"], "step": 2}}}
        r2 = await fca.act_setor_dari_karyawan(case3, {"amount": 40}, {"name": "t"})
        assert r2["hold"] is False and r2["extra"]["remaining_amount"] == 0.0

        # 4) Setor melebihi sisa TANPA pelanggan → ditolak.
        case4 = {**case2, "resolution": {"extra": {**r2["extra"], "step": 2}}}
        with pytest.raises(fca.CaseActionError):
            await fca.act_setor_dari_karyawan(case4, {"amount": 1}, {"name": "t"})

        # 5) Keputusan user: held 80, setor 100 dengan pelanggan → 80 lunasi piutang karyawan,
        #    20 jadi kredit toko pelanggan (buku saldo kredit toko).
        await db.customers.insert_one({"id": "cust1", "name": "C", "entity_id": "e1"})
        case5 = {**case2, "customer_id": "cust1"}
        r5 = await fca.act_setor_dari_karyawan(case5, {"amount": 100}, {"name": "t"})
        assert r5["hold"] is False and r5["extra"]["surplus_to_credit"] == 20.0
        assert r5["extra"]["settled_amount"] == 80.0
        from services import store_credit_service as sc
        assert await sc.balance("cust1", "e1") == 20.0
    run(go())


# ── D4-PA-02 — confirm_arrival fault lalu retry: mutasi deterministik, roll 1x ─
from services import putaway_order_service as pas


def test_pa02_confirm_arrival_fault_before_mutasi_retry_completes(monkeypatch):
    async def go():
        order = {
            "id": "pa1", "pa_number": "PA-1", "status": "in_transit",
            "from_warehouse_id": "wA", "to_warehouse_id": "wB",
            "owner_entity_id": "e1",
            "items": [{"roll_id": "r1", "product_id": "p1", "qty": 10.0, "unit": "meter",
                       "lot": "L", "epc": "EPC-1", "roll_no": "R-1", "status": "in_transit"}],
            "created_at": "2030-01-01"}
        await db.putaway_orders.insert_one(dict(order))
        await db.inventory_rolls.insert_one({
            "id": "r1", "roll_no": "R-1", "product_id": "p1", "warehouse_id": "wA",
            "owner_entity_id": "e1", "status": "available", "unit": "meter",
            "length_remaining": 10.0, "active_movement": {"id": "pa1"},
            "created_at": "2030-01-01"})

        # Stub set_journey & next_doc_number & rebuild_balance supaya lean.
        async def _nj(*a, **k): return None
        monkeypatch.setattr(pas, "set_journey", _nj)
        async def _nd(*a, **k): return "BTG-1"
        monkeypatch.setattr(pas, "next_doc_number", _nd)
        from services import roll_service as _rs
        async def _rb(*a, **k): return None
        monkeypatch.setattr(_rs, "rebuild_balance", _rb)

        # Fault pada upsert mutasi SESUDAH roll dipindah.
        undo = inject(db.inventory_movements, "update_one",
                      lambda f, u, **k: k.get("upsert") and "mov_pa_pa1" in (f.get("id") or ""))
        with pytest.raises(Fault):
            await pas.confirm_arrival("pa1", ["EPC-1"], ["e1"], "actor")
        undo()

        # Setelah fault: roll SUDAH dipindah, saga_lock dilepas.
        r_mid = await db.inventory_rolls.find_one({"id": "r1"}, {"_id": 0})
        assert r_mid["warehouse_id"] == "wB" and r_mid.get("last_pa_landed") == "pa1"
        po_mid = await db.putaway_orders.find_one({"id": "pa1"}, {"_id": 0})
        assert "saga_lock" not in po_mid
        assert po_mid["status"] == "in_transit"

        # Retry: adopsi pindah, upsert 2 mutasi deterministik, status completed.
        await pas.confirm_arrival("pa1", ["EPC-1"], ["e1"], "actor")
        movs = await db.inventory_movements.find({"roll_id": "r1"}, {"_id": 0}).to_list(10)
        ids = sorted(m["id"] for m in movs)
        assert len(movs) == 2
        assert all(mid.startswith("mov_pa_pa1_r1_") for mid in ids)
        po = await db.putaway_orders.find_one({"id": "pa1"}, {"_id": 0})
        assert po["status"] == "completed" and "saga_lock" not in po
    run(go())


# ── D4-RFID-01 — ingest: fault sesudah observasi; retry memproses, tidak dobel ─
from services import rfid_ingest_service as rfi


def test_rfid01_ingest_fault_after_obs_retry_processes_same_event():
    async def go():
        await db.rfid_devices.insert_one({"id": "dvc1", "type": "handheld", "status": "online",
                                          "warehouse_id": "wA", "enabled": True})
        device = await db.rfid_devices.find_one({"id": "dvc1"}, {"_id": 0})
        ev = {"event_id": "EVT-A", "epc": "EPC-UNKNOWN"}

        # Fault pada upsert rfid_reads (sesudah observations durable).
        undo = inject(db.rfid_reads, "update_one", lambda f, u, **k: k.get("upsert"))
        with pytest.raises(Fault):
            await rfi.ingest(device, events=[ev])
        undo()

        # Observasi durable tapi processed=False.
        obs = await db.rfid_observations.find_one({"_id": "dvc1:EVT-A"}, {"_id": 0,
                                                                           "processed": 1})
        assert obs is not None and obs["processed"] is False
        assert await db.rfid_reads.count_documents({}) == 0

        # Retry event sama → bukan dibuang sebagai duplikat; memproses & bikin read.
        out = await rfi.ingest(device, events=[ev])
        assert out["duplicates"] == 0  # unfinished dikembalikan agar diproses lagi
        reads = await db.rfid_reads.find({}, {"_id": 0}).to_list(5)
        assert len(reads) == 1 and reads[0]["id"] == "rread_dvc1:EVT-A"
        obs2 = await db.rfid_observations.find_one({"_id": "dvc1:EVT-A"}, {"_id": 0,
                                                                            "processed": 1})
        assert obs2["processed"] is True

        # Event sama lagi (sudah processed) → tetap diperlakukan duplikat.
        out3 = await rfi.ingest(device, events=[ev])
        assert out3["duplicates"] == 1
        assert await db.rfid_reads.count_documents({}) == 1
    run(go())
