"""H4 — hitung komisi tiap sales x bulan x PT lewat sales_force_service.compute_commission (mesin yang dipakai
Insentif saya, Lembar Insentif, dan slip gaji). Jalankan dari <worktree>/backend dengan DB_NAME=h4_before|h4_after."""
import asyncio, json, os, sys
sys.path.insert(0, os.getcwd())
from db import db
from services import sales_force_service as sf

BULAN = ["2026-08", "2026-09", "2026-10", "2026-11", "2026-12"]
PT = ["ent_ksc", "ent_kanda", "all"]
KUNCI = ("order_id", "order_number", "name", "sku", "qty_base", "rate", "commission", "price_reason")

async def main(out):
    ids = set(await db.sales_orders.distinct("created_by"))
    async for u in db.users.find({"role": {"$in": ["sales", "sales_admin"]}}, {"id": 1}):
        ids.add(u["id"])
    res = {"db": os.environ["DB_NAME"], "users": sorted(ids), "data": {}, "payroll_engine": {}}
    for uid in sorted(ids):
        for pt in PT:
            for b in BULAN:
                try:
                    r = await sf.compute_commission(uid, b, entity_id=pt)
                except Exception as e:
                    r = {"error": repr(e)}
                bd = r.get("breakdown") or []
                res["data"][f"{uid}|{pt}|{b}"] = {
                    "total_incentive": r.get("total_incentive"),
                    "commission_raw": r.get("commission_raw"),   # hanya ada SESUDAH
                    "carry_in": r.get("carry_in"), "carry_out": r.get("carry_out"),
                    "keys": sorted(k for k in r.keys()),
                    "error": r.get("error"),
                    "lines": [{k: l.get(k) for k in KUNCI} for l in bd],
                }
    # jalur slip gaji (hr_payroll_service._commission_for), hanya karyawan sales
    from services import hr_payroll_service as hp
    async for emp in db.hr_employees.find({}, {"_id": 0}):
        for b in BULAN:
            ent = emp.get("entity_id") or "ent_ksc"
            try:
                v = await hp._commission_for(emp, b, ent)
                tot = v.get("total") if isinstance(v, dict) else v
                extra = v if isinstance(v, dict) else None
            except Exception as e:
                tot, extra = repr(e), None
            if tot:
                res["payroll_engine"][f"{emp['id']}|{ent}|{b}"] = {"total": tot, "detail": extra}
    for coll in ("commission_carry_balances", "sales_incentives", "incentive_sheets"):
        res[f"count_{coll}"] = await db[coll].count_documents({})
    json.dump(res, open(out, "w"), indent=1, sort_keys=True, default=str)

asyncio.run(main(sys.argv[1]))
