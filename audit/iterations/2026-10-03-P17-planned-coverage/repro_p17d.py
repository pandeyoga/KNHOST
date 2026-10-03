"""P17d — COMM-04: komisi → akrual GL → settlement payroll → reversal (pembayaran batal) tetap rekonsiliasi.

Komisi dikendalikan (monkeypatch `sales_force_service.compute_commission`) supaya yang diuji murni buku besar:
akrual Dr 6-5000/Cr 2-1500, true-up saat komisi berubah, payroll memindah 2-1500 → 2-1600.
Usage: cd /app/backend && python ../audit/iterations/2026-10-03-P17-planned-coverage/repro_p17d.py
"""
import asyncio
import json
import sys

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402

ENT, PERIOD = "ent_ksc", "2026-10"
SRC = f"{ENT}:{PERIOD}"
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def acct(db, code, extra=None):
    q = {"entity_id": ENT, "status": {"$ne": "void"}, "source_id": {"$regex": f"^{SRC}($|[#@])"},
         "source_type": {"$in": ["incentive_accrual", "incentive_accrual_adj", "payroll_run"]}, **(extra or {})}
    bal = 0.0
    async for je in db.journal_entries.find(q, {"_id": 0, "lines": 1}):
        for ln in je["lines"]:
            if ln["account_code"] == code:
                bal += float(ln.get("credit") or 0) - float(ln.get("debit") or 0)
    return round(bal, 2)


async def run(db):
    from services import gl_service as gl, sales_force_service as sf
    if await db.journal_entries.find_one({"source_id": {"$regex": f"^{SRC}($|[#@])"}, "status": {"$ne": "void"},
                                          "source_type": {"$in": ["incentive_accrual", "incentive_accrual_adj", "payroll_run"]}}):
        check("COMM-04", "prasyarat: periode uji belum punya akrual/payroll", False, SRC)
        return
    real = sf.compute_commission
    users = await db.users.find({"role": "sales", "status": "active"}, {"_id": 0, "id": 1}).to_list(50)
    first = users[0]["id"]
    amount = {"v": 1_000_000.0}

    async def fake(sales_id, period, entity_id=None):
        return {"total_incentive": amount["v"] if sales_id == first else 0.0}
    sf.compute_commission = fake
    try:
        je = await gl.post_incentive_accrual(ENT, PERIOD, "TEST_P17D")
        check("COMM-04", "akrual komisi 1.000.000: Dr Beban 6-5000 / Cr Hutang Insentif 2-1500",
              je and await acct(db, gl.ACC_HUTANG_INSENTIF) == 1_000_000 and await acct(db, gl.ACC_BEBAN_INSENTIF) == -1_000_000,
              await acct(db, gl.ACC_HUTANG_INSENTIF))
        again = await gl.post_incentive_accrual(ENT, PERIOD, "TEST_P17D")
        check("COMM-04", "posting ulang tanpa perubahan komisi tidak membuat jurnal baru", again is None, again and again.get("number"))
        amount["v"] = 600_000.0   # pembayaran pelanggan dibatalkan → komisi on-collection turun
        adj = await gl.post_incentive_accrual(ENT, PERIOD, "TEST_P17D")
        st = await gl.incentive_accrual_status(ENT, PERIOD)
        check("COMM-04", "reversal: komisi turun ke 600.000 → jurnal koreksi -400.000, saldo 2-1500 = 600.000",
              bool(adj) and await acct(db, gl.ACC_HUTANG_INSENTIF) == 600_000 and st["amount"] == 600_000,
              (adj and adj.get("source_type"), await acct(db, gl.ACC_HUTANG_INSENTIF), st.get("amount")))
        dup = await gl.post_incentive_accrual(ENT, PERIOD, "TEST_P17D")
        check("COMM-04", "koreksi idempoten (klik ulang tidak menggandakan)", dup is None and await acct(db, gl.ACC_HUTANG_INSENTIF) == 600_000,
              await acct(db, gl.ACC_HUTANG_INSENTIF))
        amount["v"] = 750_000.0   # pembayaran susulan masuk sebelum payroll
        run_doc = {"entity_id": ENT, "period": PERIOD, "number": "TEST_P17D-PR", "commission_mode": "accrue_then_settle"}
        slips = [{"salary_earnings": 5_000_000, "commission": 750_000, "net": 5_750_000}]
        pr = await gl.post_payroll_run(run_doc, slips, "TEST_P17D")
        check("COMM-04", "settlement payroll: komisi slip 750.000 → akrual di-true-up dulu, 2-1500 periode = 0",
              bool(pr) and await acct(db, gl.ACC_HUTANG_INSENTIF) == 0, await acct(db, gl.ACC_HUTANG_INSENTIF))
        check("COMM-04", "beban insentif periode = komisi dibayar (750.000), tanpa beban ganda",
              await acct(db, gl.ACC_BEBAN_INSENTIF) == -750_000, await acct(db, gl.ACC_BEBAN_INSENTIF))
        bad = [j["number"] async for j in db.journal_entries.find(
            {"source_id": {"$regex": f"^{SRC}($|[#@])"}, "entity_id": ENT}, {"_id": 0, "number": 1, "total_debit": 1, "total_credit": 1})
            if round(j["total_debit"], 2) != round(j["total_credit"], 2)]
        check("COMM-04", "semua jurnal komisi seimbang", not bad, bad)
    finally:
        sf.compute_commission = real


async def main():
    from db import db
    full = snapshot_stock(["number_sequences"])
    ids = snapshot_new_ids(["journal_entries", "gl_postings", "audit_logs"])
    try:
        await run(db)
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        check("COMM-04", "eksekusi skenario", False, repr(exc)[:200])
    finally:
        purge_new_ids(ids, verbose=False)
        restore_stock(full)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
