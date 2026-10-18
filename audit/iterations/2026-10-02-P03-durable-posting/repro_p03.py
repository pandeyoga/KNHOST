"""P03 invariants (FN-15, FN-07, FN-08, FN-10, FN-12, CX-01, CX-03, CX-04, CX-05, CX-06, CX-07, CX-08, IX-14, IX-17)
— service asli + fault injection, DB sintetis lokal (entitas `ent_audit_p03_*`).

Usage: cd /app/backend && python ../audit/iterations/2026-10-02-P03-durable-posting/repro_p03.py
Semua data sintetis (entitas, jurnal, kas, dokumen) dihapus di akhir.
"""
import asyncio
import json
import sys
import uuid

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


def err(exc):
    return getattr(exc, "status_code", type(exc).__name__), str(getattr(exc, "detail", exc))[:160]


async def expect_fail(fid, name, coro, pred=lambda e: True):
    try:
        out = await coro
        check(fid, name, False, f"diterima: {str(out)[:120]}")
    except Exception as exc:  # noqa: BLE001
        check(fid, name, pred(exc), err(exc))


async def main():
    from db import db
    from core_utils import now_iso
    from services import gl_service as gl
    T = uuid.uuid4().hex[:6]
    E = f"ent_audit_p03_{T}"
    today = now_iso()[:10]
    actor = {"id": "u_audit", "name": "auditor", "role": "admin"}

    async def close_period():
        await db.period_closings.insert_one({"id": f"pc_{T}", "entity_id": E, "status": "closed", "period_type": "month",
                                             "period_key": today[:7], "start_date": today, "end_date": today})

    async def open_period():
        await db.period_closings.delete_many({"entity_id": E})

    async def je_count(st, sid):
        return await db.journal_entries.count_documents({"source_type": st, "source_id": sid, "status": {"$ne": "void"}})
    try:
        # ── FN-15 — validator pusat ─────────────────────────────────────────
        base = dict(description="t", date=now_iso(), source_type="audit_p03", source_id=f"x_{T}", entity_id=E, created_by="a")
        bad = {
            "tidak seimbang": [{"account_code": "1-1100", "debit": 100}, {"account_code": "3-2900", "credit": 90}],
            "NaN": [{"account_code": "1-1100", "debit": float("nan")}, {"account_code": "3-2900", "credit": 100}],
            "negatif": [{"account_code": "1-1100", "debit": -100}, {"account_code": "3-2900", "credit": -100}],
            "dua sisi": [{"account_code": "1-1100", "debit": 100, "credit": 100}, {"account_code": "3-2900", "credit": 0}],
            "akun induk": [{"account_code": "1-0000", "debit": 100}, {"account_code": "3-2900", "credit": 100}],
            "akun tak ada": [{"account_code": "9-9999", "debit": 100}, {"account_code": "3-2900", "credit": 100}],
        }
        for label, lines in bad.items():
            await expect_fail("FN-15", f"jurnal {label} ditolak sebelum insert", gl._insert_entry(lines=lines, **base),
                              lambda e: isinstance(e, getattr(gl, "JournalValidationError", ())))
        ok = await gl._insert_entry(lines=[{"account_code": "1-1100", "debit": 100}, {"account_code": "3-2900", "credit": 100}], **base)
        check("FN-15", "jurnal valid tetap terposting", ok["total_debit"] == ok["total_credit"] == 100, ok["number"])

        # ── FN-08 — saldo awal rekening ↔ GL ──────────────────────────────
        from services import bank_service as bs

        class P:
            name = f"Bank Audit {T}"; account_type = "bank"; bank_name = "X"; account_number = "1"
            entity_id = E; opening_balance = 1000.0; currency = "IDR"; note = ""
        acc = await bs.create_account(P, actor)
        check("FN-08", "rekening baru saldo awal 1000 → jurnal pembukaan Dr Bank/Cr 3-2900",
              await je_count("bank_opening_balance", acc["id"]) == 1, acc.get("opening_je_id"))
        await bs.update_account(acc["id"], {"opening_balance": 1500.0})
        adj = await db.journal_entries.find_one({"source_type": "bank_opening_adjustment", "source_id": f"{acc['id']}:1"}, {"_id": 0})
        check("FN-08", "ubah saldo awal → jurnal penyesuaian selisih 500 (bukan edit diam-diam)",
              adj and adj["total_debit"] == 500, (adj or {}).get("number"))

        # ── FN-07 — kas manual / void (lewat router in-process) ──────────
        from routers import cash as cash_router
        from services import cash_ledger  # noqa: F401
        txn = {"id": f"cash_{T}", "number": f"CASH-{T}", "cash_type": "kas_besar", "direction": "in", "amount": 250.0,
               "category": "lain", "description": "audit", "entity_id": E, "ref_type": "", "ref_id": "",
               "txn_date": now_iso(), "status": "posted", "account_id": ""}
        await db.cash_transactions.insert_one(dict(txn))
        await gl.post_cash_durable(txn)
        t1 = await db.cash_transactions.find_one({"id": txn["id"]}, {"_id": 0})
        check("FN-07", "kas manual berjurnal langsung (gl_status posted)", t1.get("gl_status") == "posted" and
              await je_count("cash_transaction", txn["id"]) == 1, t1.get("gl_status"))
        src = open("routers/cash.py").read()
        check("FN-07", "void kas: pembalik jurnal + tolak kas turunan dokumen (statis)",
              "post_cash_void" in src and "batalkan lewat dokumen asalnya" in src, "routers/cash.py")
        rev = await gl.post_cash_void(txn["id"], label="audit")
        rev2 = await gl.post_cash_void(txn["id"], label="audit")
        check("FN-07", "pembalik jurnal kas idempotent", rev and rev2 is None and await je_count("cash_transaction_void", txn["id"]) == 1, "")
        _ = cash_router

        # ── Preflight periode tertutup (dipakai FN-07/FN-10/CX-*/IX-14/IX-17) ──
        await close_period()
        await expect_fail("P03", "preflight menolak periode tertutup", gl.preflight_posting(E, now_iso()),
                          lambda e: isinstance(e, gl.ClosedPeriodError))

        # ── FN-10 — kwitansi AR ditolak sebelum mutasi saat periode tertutup ─
        from services import ar_receipt_service as ar
        cust = f"cust_{T}"
        await db.customers.insert_one({"id": cust, "name": f"Cust {T}", "entity_id": E, "deposit_balance": 0})
        so = f"so_{T}"
        await db.sales_orders.insert_one({"id": so, "number": f"SO-{T}", "customer_id": cust, "entity_id": E,
                                          "status": "confirmed", "payment_method": "tempo", "grand_total": 200.0,
                                          "total_amount": 200.0, "paid_total": 0.0, "payments": [],
                                          "created_at": now_iso(), "items": []})
        await expect_fail("FN-10", "kwitansi di periode tertutup → 409 tanpa kwitansi/alokasi",
                          ar.create_receipt({"customer_id": cust, "amount": 50, "entity_id": E,
                                             "allocations": [{"order_id": so, "amount": 50}]}, actor),
                          lambda e: getattr(e, "status_code", 0) == 409)
        o = await db.sales_orders.find_one({"id": so}, {"_id": 0})
        check("FN-10", "order tidak termutasi & tidak ada kwitansi", not o.get("payments") and
              await db.ar_receipts.count_documents({"customer_id": cust}) == 0, o.get("paid_total"))
        await open_period()
        # GL gagal → status gagal TERLIHAT, repost idempotent
        orig = gl.post_cash_transaction

        async def boom(*a, **k):
            raise RuntimeError("fault injection GL")
        gl.post_cash_transaction = boom
        rc = await ar.create_receipt({"customer_id": cust, "amount": 50, "entity_id": E,
                                      "allocations": [{"order_id": so, "amount": 50}]}, actor)
        gl.post_cash_transaction = orig
        check("FN-10", "GL gagal → kwitansi gl_status=failed (tidak tampil sukses final)", rc.get("gl_status") == "failed", rc.get("gl_status"))
        await ar.repost_receipt(rc["id"])
        await ar.repost_receipt(rc["id"])
        # Fixture: nominal sintetis kecil (<toleransi pembulatan FASE G-3) memicu write-off otomatis sisa piutang;
        # dibuang supaya AR tetap terbuka untuk uji store credit (bukan bagian dari invariant P03).
        await db.sales_orders.update_one({"id": so}, {"$pull": {"payments": {"method": "writeoff"}}})
        check("FN-10", "repost 2x → tepat satu jurnal kas", await je_count("cash_transaction", rc["cash_txn_id"]) == 1, "")

        # ── CX-01 / CX-03 — store credit ──────────────────────────────────
        from services import store_credit_service as sc
        await sc.issue(customer_id=cust, entity_id=E, amount=100, ref_type="audit", ref_id=f"iss_{T}")
        await expect_fail("CX-01", "redeem 10 dengan alokasi 150 ditolak (Σ alokasi ≠ nominal)",
                          sc.redeem(customer_id=cust, entity_id=E, amount=10, allocations=[{"order_id": so, "amount": 150}], actor=actor),
                          lambda e: getattr(e, "status_code", 0) == 400)
        o = await db.sales_orders.find_one({"id": so}, {"_id": 0})
        check("CX-01", "tidak ada mutasi AR dari permintaan tidak sah", round(ar.order_paid(o), 2) == 50, ar.order_paid(o))
        orig_r = gl.post_store_credit_redemption
        gl.post_store_credit_redemption = boom
        await expect_fail("CX-03", "GL store credit gagal → 409", sc.redeem(customer_id=cust, entity_id=E, amount=50,
                                                                             allocations=[{"order_id": so, "amount": 50}], actor=actor))
        gl.post_store_credit_redemption = orig_r
        o = await db.sales_orders.find_one({"id": so}, {"_id": 0})
        bal = await sc.balance(cust, E)
        lock = (await db.customers.find_one({"id": cust}, {"_id": 0})).get("saga_lock")
        check("CX-03", "setelah gagal: AR dikompensasi (paid tetap 50), saldo kredit 100, kunci lepas",
              round(ar.order_paid(o), 2) == 50 and round(bal, 2) == 100 and not lock, {"paid": ar.order_paid(o), "bal": bal})
        try:
            red = await sc.redeem(customer_id=cust, entity_id=E, amount=50, allocations=[{"order_id": so, "amount": 50}], actor=actor)
            check("CX-03", "retry sah: AR +50, saldo 50, satu jurnal", round(await sc.balance(cust, E), 2) == 50 and
                  await je_count("store_credit_redemption", red["id"]) <= 1, red.get("applied_amount"))
        except Exception as exc:  # noqa: BLE001
            check("CX-03", "retry sah setelah kompensasi", False, err(exc))

        # ── CX-04 / CX-05 — uang muka ─────────────────────────────────────
        from services import cash_advance_service as ca
        from entity_scope import EntityContext
        ctx = EntityContext(user=actor, active_entity_id=E, allowed_entity_ids=[E])
        ca_id = f"ca_{T}"
        await db[ca.CA_COLL].insert_one({"id": ca_id, "number": f"PD-{T}", "entity_id": E, "status": "approved",
                                         "total_amount": 100.0, "kegiatan": "audit", "approvals": []})

        class D:
            cash_type = "kas_kecil"; txn_date = None; note = ""
        gl.post_cash_transaction = boom
        await expect_fail("CX-04", "pencairan: GL gagal → 409", ca.disburse_cash_advance(ca_id, D, ctx, actor))
        gl.post_cash_transaction = orig
        d = await ca.disburse_cash_advance(ca_id, D, ctx, actor)
        n_cash = await db.cash_transactions.count_documents({"ref_type": "cash_advance", "ref_id": ca_id})
        check("CX-04", "retry pencairan: tepat SATU kas 100 + satu jurnal, status disbursed",
              n_cash == 1 and d["status"] == "disbursed" and await je_count("cash_transaction", d["disbursement"]["cash_txn_id"]) == 1,
              {"cash": n_cash, "status": d["status"]})
        await expect_fail("CX-04", "pencairan kedua ditolak", ca.disburse_cash_advance(ca_id, D, ctx, actor),
                          lambda e: getattr(e, "status_code", 0) == 409)

        class S:
            cash_advance_id = ca_id; expense_lines = [{"category": "petty_cash_lain", "amount": 100, "description": "x"}]
            divisi = ""; periode = ""; dibuat_oleh = ""; catatan = ""
        s1 = await ca.create_settlement(S, ctx, actor)
        await expect_fail("CX-05", "LPJ kedua saat LPJ pertama aktif ditolak", ca.create_settlement(S, ctx, actor),
                          lambda e: getattr(e, "status_code", 0) == 409)
        await ca.approve_settlement(s1["id"], ctx, actor)
        await expect_fail("CX-05", "LPJ baru untuk PD settled ditolak", ca.create_settlement(S, ctx, actor),
                          lambda e: getattr(e, "status_code", 0) == 409)

        # ── CX-06 / CX-07 — rekonsiliasi bank ─────────────────────────────
        from services import bank_recon_service as br
        b1, b2 = f"bk1_{T}", f"bk2_{T}"
        await db.bank_accounts.insert_many([{"id": b1, "name": "B1", "entity_id": E, "cash_type": "kas_besar"},
                                            {"id": b2, "name": "B2", "entity_id": E, "cash_type": "kas_besar"}])
        tx_in2 = {"id": f"tin2_{T}", "number": "T-IN2", "direction": "in", "amount": 100.0, "account_id": b2, "entity_id": E, "status": "posted", "cash_type": "kas_besar"}
        tx_out1 = {"id": f"tout1_{T}", "number": "T-OUT1", "direction": "out", "amount": 100.0, "account_id": b1, "entity_id": E, "status": "posted", "cash_type": "kas_besar"}
        tx_in1 = {"id": f"tin1_{T}", "number": "T-IN1", "direction": "in", "amount": 100.0, "account_id": b1, "entity_id": E, "status": "posted", "cash_type": "kas_besar"}
        await db.cash_transactions.insert_many([dict(tx_in2), dict(tx_out1), dict(tx_in1)])
        ln_out = {"id": f"ln1_{T}", "bank_account_id": b1, "entity_id": E, "direction": "out", "amount": 100.0, "status": "unmatched"}
        ln_120 = {"id": f"ln2_{T}", "bank_account_id": b1, "entity_id": E, "direction": "in", "amount": 120.0, "status": "unmatched"}
        ln_in = {"id": f"ln3_{T}", "bank_account_id": b1, "entity_id": E, "direction": "in", "amount": 100.0, "status": "unmatched"}
        await db.bank_statement_lines.insert_many([dict(ln_out), dict(ln_120), dict(ln_in)])
        await expect_fail("CX-06", "OUT vs IN ditolak", br.manual_match(ln_out["id"], tx_in1["id"], "a", [E]))
        await expect_fail("CX-06", "BANK1 vs transaksi BANK2 ditolak", br.manual_match(ln_in["id"], tx_in2["id"], "a", [E]))
        await expect_fail("CX-07", "split T60+T60 atas transaksi 100 ditolak tanpa write",
                          br.match_split(ln_120["id"], [{"txn_id": tx_in1["id"], "amount": 60}, {"txn_id": tx_in1["id"], "amount": 60}], "a", [E]))
        t = await db.cash_transactions.find_one({"id": tx_in1["id"]}, {"_id": 0})
        check("CX-07", "reconciled_amount tidak bertambah setelah penolakan", float(t.get("reconciled_amount") or 0) == 0, t.get("reconciled_amount"))
        m = await br.manual_match(ln_in["id"], tx_in1["id"], "a", [E])
        check("CX-06", "bank/arah/nominal sama diterima", m["status"] == "matched", m["status"])

        # ── CX-08 — reschedule tidak mengubah arti referensi seq ──────────
        from services import payment_plan_service as pp
        so2 = f"so2_{T}"
        await db.sales_orders.insert_one({"id": so2, "number": f"SO2-{T}", "customer_id": cust, "entity_id": E, "status": "confirmed",
                                          "payment_method": "tempo", "grand_total": 200.0, "total_amount": 200.0, "paid_total": 150.0,
                                          "payments": [{"id": "p1", "amount": 150.0, "receipt_id": f"rc2_{T}"}], "items": []})
        await db.ar_receipts.insert_one({"id": f"rc2_{T}", "status": "posted", "customer_id": cust,
                                         "allocations": [{"order_id": so2, "applied": 100.0, "plan_line_seq": 2},
                                                         {"order_id": so2, "applied": 50.0}]})
        plan_id = f"pyp_{T}"
        await db[pp.COLL].insert_one({"id": plan_id, "doc_type": "sales_order", "doc_id": so2, "entity_id": E, "customer_id": cust,
                                      "status": "active", "total_amount": 200.0, "lines": [
                                          {"seq": 1, "label": "C1", "amount": 100.0, "due_date": "2026-10-01", "kind": "installment"},
                                          {"seq": 2, "label": "C2", "amount": 100.0, "due_date": "2026-11-01", "kind": "installment"}]})
        await pp.recompute_paid(plan_id)
        try:
            await pp.reschedule_line(plan_id, 1, 50, "2026-12-01", actor=actor)
            plan = await pp.get(plan_id)
            l2 = next(x for x in plan["lines"] if x.get("label") == "C2")
            check("CX-08", "setelah split baris 1, baris 2 (seq 2) tetap paid 100",
                  l2["seq"] == 2 and round(float(l2["paid_amount"]), 2) == 100, [(x["seq"], x["label"], x.get("paid_amount")) for x in plan["lines"]])
        except Exception as exc:  # noqa: BLE001
            check("CX-08", "reschedule berjalan", False, err(exc))

        # ── FN-12 — aset terkapitalisasi ──────────────────────────────────
        from services import fixed_asset_service as fa
        asset = await fa.create_asset({"name": f"Mesin {T}", "acquisition_cost": 1200, "useful_life_months": 12,
                                       "entity_id": E}, actor)
        if await je_count("fixed_asset_acquisition", asset["id"]):
            await expect_fail("FN-12", "edit biaya aset terkapitalisasi ditolak", fa.update_asset(asset["id"], {"acquisition_cost": 2000}),
                              lambda e: isinstance(e, ValueError))
        else:
            check("FN-12", "aset membuat jurnal perolehan", False, "tanpa jurnal")
        ok_ = await fa.update_asset(asset["id"], {"name": "Mesin rename"})
        check("FN-12", "edit nonfinansial tetap boleh", ok_["name"] == "Mesin rename", "")

        # ── IX-14 — GRN: preflight + jurnal GR gagal tidak 'done' ─────────
        from services import goods_receipt_close_service as grc
        await close_period()
        errs = await grc._close_preflight({"entity_id": E, "lines": []})
        check("IX-14", "close GRN ditolak sebelum `closing` bila periode tertutup", any("DITUTUP" in e for e in errs), errs[:1])
        task_id = f"task_{T}"
        await db.wms_tasks.insert_one({"id": task_id, "gl_posting": {"status": "failed", "amount": 500.0, "entity_id": E, "label": "PO-A"}})
        await expect_fail("IX-14", "jurnal GR masih gagal → 409 (baris tidak done)", grc._ensure_gr_posted(task_id),
                          lambda e: getattr(e, "status_code", 0) == 409)
        await open_period()
        await grc._ensure_gr_posted(task_id)
        await grc._ensure_gr_posted(task_id)
        tk = await db.wms_tasks.find_one({"id": task_id}, {"_id": 0})
        check("IX-14", "setelah periode dibuka: tepat satu jurnal GR, status posted",
              await je_count("goods_receipt", task_id) == 1 and tk["gl_posting"]["status"] == "posted", tk["gl_posting"]["status"])

        # ── IX-17 — retur beli ────────────────────────────────────────────
        from services import purchase_return_service as prsvc
        po = f"po_{T}"
        await db.purchase_orders.insert_one({"id": po, "number": f"PO-{T}", "entity_id": E, "returned_amount": 0.0, "items": []})
        ret_id = f"pr_{T}"
        await db.purchase_returns.insert_one({"id": ret_id, "number": f"PR-{T}", "entity_id": E, "warehouse_id": "wh_x",
                                              "status": "pending_approval", "supplier_flow": False, "po_id": po, "items": [],
                                              "total_amount": 100.0, "ppn_amount": 0.0, "grand_total": 100.0})
        await close_period()
        await expect_fail("IX-17", "approve di periode tertutup ditolak", prsvc.approve_and_adjust_stock(ret_id, "mgr"))
        r_ = await db.purchase_returns.find_one({"id": ret_id}, {"_id": 0})
        p_ = await db.purchase_orders.find_one({"id": po}, {"_id": 0})
        check("IX-17", "tidak ada status final / AP berubah sebelum jurnal", r_["status"] == "pending_approval" and p_["returned_amount"] == 0,
              {"status": r_["status"], "returned": p_["returned_amount"]})
        await open_period()
        orig_pr = gl.post_purchase_return
        gl.post_purchase_return = boom
        await expect_fail("IX-17", "GL retur gagal → error (bukan sukses)", prsvc.approve_and_adjust_stock(ret_id, "mgr"))
        gl.post_purchase_return = orig_pr
        r_ = await db.purchase_returns.find_one({"id": ret_id}, {"_id": 0})
        check("IX-17", "status posting gagal terlihat (gl_status=failed)", r_.get("gl_status") == "failed", r_.get("gl_status"))
        await prsvc.approve_and_adjust_stock(ret_id, "mgr")
        r_ = await db.purchase_returns.find_one({"id": ret_id}, {"_id": 0})
        p_ = await db.purchase_orders.find_one({"id": po}, {"_id": 0})
        check("IX-17", "approve ulang melanjutkan: satu jurnal, AP berkurang SEKALI",
              r_.get("gl_status") == "posted" and await je_count("purchase_return", ret_id) == 1 and p_["returned_amount"] == 100,
              {"gl": r_.get("gl_status"), "returned": p_["returned_amount"]})
    finally:
        gl.post_cash_transaction = gl.post_cash_transaction
        for c in ("journal_entries", "cash_transactions", "bank_accounts", "bank_statement_lines", "customers", "sales_orders",
                  "ar_receipts", "store_credit_ledger", "store_credit_redemptions", "fin_fixed_assets", "purchase_orders",
                  "purchase_returns", "period_closings", "cash_advances", "cash_advance_settlements",
                  "payment_variance_decisions", "number_sequences"):
            await db[c].delete_many({"entity_id": E})
        await db.ar_receipts.delete_many({"customer_id": f"cust_{T}"})
        await db.wms_tasks.delete_many({"id": f"task_{T}"})
        await db.payment_plans.delete_many({"id": f"pyp_{T}"})
    passed = sum(1 for r in results if r["pass"])
    print(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"pass={passed} fail={len(results) - passed}")


try:
    asyncio.run(main())
except Exception as _exc:  # noqa: BLE001 — HEAD tanpa kontrak baru: cetak hasil parsial + titik crash
    passed = sum(1 for r_ in results if r_["pass"])
    print(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"CRASH (kontrak belum ada di kode ini): {type(_exc).__name__}: {_exc}")
    print(f"pass={passed} fail={len(results) - passed} crashed=1")
