"""P05 (COA, laporan, period close) — regression invariant pada DB sintetis.

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-05-P05-coa-reports-close/repro_p05.py
Data sintetis ber-prefix `audit_p05_*` / entitas `ent_audit_p05_*` dihapus di akhir.
"""
import asyncio
import json
import sys
import uuid
from types import SimpleNamespace as NS

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


def je(lines, date, eid, desc="audit p05"):
    return NS(lines=[{"account_code": c, "debit": d, "credit": k, "description": ""} for c, d, k in lines],
              date=date, description=desc, entity_id=eid)


async def main():
    from db import db
    from core_utils import now_iso
    from services import gl_service as gl, financial_statement_service as fs, cash_flow_service as cf
    from services import closing_service as cs, period_unlock_service as pus, consolidation_service as cons
    T = uuid.uuid4().hex[:6]
    E, F, G = (f"ent_audit_p05_{x}_{T}" for x in "efg")
    admin = {"id": f"u_a_{T}", "name": "Audit Admin", "role": "admin"}
    other = {"id": f"u_b_{T}", "name": "Audit Rejector", "role": "manager"}
    X, Y = f"9-AUD{T}", f"9-CUS{T}"
    S = {}
    try:
        for eid in (E, F, G):
            await db.business_entities.insert_one({"id": eid, "short_name": eid[-8:], "legal_name": eid, "is_group": False,
                                                   "audit_fixture": True})
        # ── FN-05 — COA efektif per entitas, bukan last-write-wins ─────────────
        async def sec_1():
            await db.gl_accounts.insert_many([
                {"code": X, "name": "Global X", "type": "income", "entity_id": None, "is_postable": True, "is_active": True},
                {"code": X, "name": "Override E", "type": "expense", "entity_id": E, "is_postable": True, "is_active": True},
                {"code": X, "name": "Override F", "type": "income", "entity_id": F, "is_postable": True, "is_active": True},
                {"code": Y, "name": "Khusus E", "type": "expense", "entity_id": E, "is_postable": True, "is_active": True},
            ])
            async def amap(scope):
                try:
                    return await fs._accounts_map(scope)
                except TypeError:  # HEAD lama: tanpa parameter scope
                    return await fs._accounts_map()
            me = await amap({"entity_id": E})
            mf = await amap({"entity_id": F})
            mg = await amap({"entity_id": G})
            mgrp = await amap({"entity_id": {"$in": [E, F]}})
            check("FN-05", "laporan E memakai override E", me[X]["name"] == "Override E" and me[X]["type"] == "expense", me[X])
            check("FN-05", "laporan F memakai override F", mf[X]["name"] == "Override F", mf[X]["name"])
            check("FN-05", "entitas tanpa override memakai global", mg[X]["name"] == "Global X", mg[X]["name"])
            check("FN-05", "akun khusus E tidak bocor ke F", Y in me and Y not in mf, "")
            check("FN-05", "laporan multi-entitas memakai dimensi global", mgrp[X]["name"] == "Global X", mgrp[X]["name"])
        try:
            await sec_1()
        except Exception as exc:  # noqa: BLE001
            check('FN-05', 'bagian FN-05 crash', False, repr(exc))

        # ── FN-06 — jurnal manual memakai resolver akun efektif ────────────────
        async def sec_2():
            d_ok = S["d_ok"] = "2025-03-10T10:00:00"
            try:
                e1 = await gl.create_manual_entry(je([(Y, 100, 0), ("1-1100", 0, 100)], d_ok, E), admin, entity_id=E)
            except ValueError as exc:  # HEAD lama: akun khusus entitas ditolak
                check("FN-06", "akun khusus E dapat diposting di E", False, exc)
                e1 = await gl.create_manual_entry(je([("6-4000", 100, 0), ("1-1100", 0, 100)], d_ok, E), admin, entity_id=E)
            S["e1"] = e1
            check("FN-06", "akun khusus E dapat diposting di E", e1.get("status") == "posted", e1.get("number"))
            try:
                await gl.create_manual_entry(je([(Y, 100, 0), ("1-1100", 0, 100)], d_ok, F), admin, entity_id=F)
                check("FN-06", "akun khusus E ditolak di F", False, "lolos")
            except ValueError as exc:
                check("FN-06", "akun khusus E ditolak di F", "tidak ditemukan" in str(exc), exc)
            await db.gl_accounts.insert_one({"code": "6-4000", "name": "Beban Ops (nonaktif E)", "type": "expense",
                                             "entity_id": E, "is_postable": True, "is_active": False, "audit_fixture": T})
            try:
                await gl.create_manual_entry(je([("6-4000", 50, 0), ("1-1100", 0, 50)], d_ok, E), admin, entity_id=E)
                check("FN-06", "override nonaktif menghalangi posting", False, "lolos")
            except ValueError as exc:
                check("FN-06", "override nonaktif menghalangi posting", "nonaktif" in str(exc), exc)
            e_glob = await gl.create_manual_entry(je([("6-4000", 50, 0), ("1-1100", 0, 50)], d_ok, F), admin, entity_id=F)
            check("FN-06", "global default tetap bekerja di F", e_glob.get("status") == "posted", "")
            try:
                await gl._insert_entry(lines=[{"account_code": "6-4000", "debit": 5, "credit": 0},
                                              {"account_code": "1-1100", "debit": 0, "credit": 5}],
                                       description="auto", date=d_ok, source_type="audit_auto", source_id=T,
                                       entity_id=E, created_by="audit")
                check("FN-06", "autopost juga menolak override nonaktif", False, "lolos")
            except gl.JournalValidationError as exc:
                check("FN-06", "autopost juga menolak override nonaktif", "nonaktif" in str(exc), exc)
        try:
            await sec_2()
        except Exception as exc:  # noqa: BLE001
            check('FN-06', 'bagian FN-06 crash', False, repr(exc))

        # ── FN-16 — neraca default dibatasi hari ini ───────────────────────────
        async def sec_3():
            today = now_iso()[:10]
            y = int(today[:4]) + 1
            future = f"{y}{today[4:10]}T09:00:00"
            await gl.create_manual_entry(je([("1-2100", 777, 0), ("1-1100", 0, 777)], future, G), admin, entity_id=G)
            bs_def = await fs.balance_sheet(scope={"entity_id": G})
            bs_fut = await fs.balance_sheet(as_of=future[:10], scope={"entity_id": G})

            def asset_amt(bs, code):
                return sum(ln["amount"] for s in bs["assets"]["sections"] for ln in s.get("lines", []) if ln.get("code") == code)
            check("FN-16", "jurnal masa depan tidak masuk neraca default", asset_amt(bs_def, "1-2100") == 0, asset_amt(bs_def, "1-2100"))
            check("FN-16", "label as_of = cutoff hari ini", bs_def["as_of"] == today, bs_def["as_of"])
            check("FN-16", "as_of masa depan memasukkan jurnal itu", asset_amt(bs_fut, "1-2100") == 777, asset_amt(bs_fut, "1-2100"))
        try:
            await sec_3()
        except Exception as exc:  # noqa: BLE001
            check('FN-16', 'bagian FN-16 crash', False, repr(exc))

        # ── FN-04 — arus kas per jurnal kas ───────────────────────────────────
        async def sec_4():
            d = "2025-05-"
            await gl.create_manual_entry(je([("6-4000", 100, 0), ("1-2900", 0, 100)], d + "02T10:00:00", G, "susut"), admin, entity_id=G)
            await gl.create_manual_entry(je([("1-2200", 100, 0), ("2-1100", 0, 100)], d + "03T10:00:00", G, "aset kredit"), admin, entity_id=G)
            await gl.create_manual_entry(je([("1-2300", 40, 0), ("1-1100", 0, 40)], d + "04T10:00:00", G, "aset tunai"), admin, entity_id=G)
            await gl.create_manual_entry(je([("1-1100", 250, 0), ("4-1000", 0, 250)], d + "05T10:00:00", G, "jual tunai"), admin, entity_id=G)
            c = await cf.cash_flow_statement(start="2025-05-01", end="2025-05-31", scope={"entity_id": G})
            inv = {ln["code"]: ln["amount"] for ln in c["investing"]["lines"]}
            nonc = {ln["code"]: ln["amount"] for ln in c.get("noncash_disclosure", {}).get("lines", [])}
            check("FN-04", "penyusutan tidak masuk CFO/CFI", "1-2900" not in inv and c["operating"]["net_income"] == 250, (inv, c["operating"]))
            check("FN-04", "beli aset kredit tidak masuk CFI, diungkap nonkas", "1-2200" not in inv and nonc.get("1-2200") == -100, (inv, nonc))
            check("FN-04", "beli aset tunai masuk CFI", inv.get("1-2300") == -40, inv)
            check("FN-04", "total arus kas = Δkas & reconciled", c["net_change"] == 210 and c["reconciled"], (c["net_change"], c["reconciled"]))
        try:
            await sec_4()
        except Exception as exc:  # noqa: BLE001
            check('FN-04', 'bagian FN-04 crash', False, repr(exc))

        # ── FN-13 — close bersamaan: tepat satu ───────────────────────────────
        async def sec_5():
            outs = await asyncio.gather(*[cs.close_period("month", "2025-03", admin, E) for _ in range(3)], return_exceptions=True)
            ok = [o for o in outs if isinstance(o, dict)]
            n_je = await db.journal_entries.count_documents({"entity_id": E, "source_type": "closing", "status": {"$ne": "void"}})
            check("FN-13", "3 close bersamaan → tepat 1 sukses, 1 jurnal penutup", len(ok) == 1 and n_je == 1, [type(o).__name__ for o in outs])
            check("FN-13", "kunci close dilepas setelah selesai", not await db.period_close_locks.find_one({"_id": E}), "")
        try:
            await sec_5()
        except Exception as exc:  # noqa: BLE001
            check('FN-13', 'bagian FN-13 crash', False, repr(exc))

        # ── FN-09 — void jurnal di periode tertutup ────────────────────────────
        async def sec_6():
            try:
                await gl.void_entry(S["e1"]["id"], admin)
                check("FN-09", "void di periode tertutup ditolak tanpa unlock", False, "lolos")
            except gl.ClosedPeriodError as exc:
                check("FN-09", "void di periode tertutup ditolak tanpa unlock", True, str(exc)[:80])
            st = (await db.journal_entries.find_one({"id": S["e1"]["id"]}, {"_id": 0, "status": 1}))["status"]
            check("FN-09", "jurnal asli tetap posted", st == "posted", st)
        try:
            await sec_6()
        except Exception as exc:  # noqa: BLE001
            check('FN-09', 'bagian FN-09 crash', False, repr(exc))

        # ── IX-08 — approve vs reject bersamaan ────────────────────────────────
        async def sec_7():
            req = await pus.request_unlock(period_type="month", period_key="2025-03", entity_id=E, reason="audit", actor=admin)
            outs = await asyncio.gather(pus.approve_request(req["id"], other), pus.reject_request(req["id"], other, "no"),
                                        return_exceptions=True)
            wins = [o for o in outs if isinstance(o, dict)]
            conf = [o for o in outs if isinstance(o, getattr(pus, "DecisionConflict", ValueError))]
            final = await db.period_unlock_requests.find_one({"id": req["id"]}, {"_id": 0})
            check("IX-08", "tepat satu keputusan menang, lainnya konflik", len(wins) == 1 and len(conf) == 1, [type(o).__name__ for o in outs])
            active = await pus.find_active_unlock(E, "2025-03-10")
            if final["status"] == "rejected":
                check("IX-08", "reject menang → tidak ada unlock aktif & tanpa approved_by", active is None and not final.get("approved_by"), final["status"])
            else:
                check("IX-08", "approve menang → tanpa jejak rejected_by", active is not None and not final.get("rejected_by"), final["status"])
            try:
                await pus.approve_request(req["id"], other)
                check("IX-08", "retry keputusan ditolak", False, "lolos")
            except ValueError:
                check("IX-08", "retry keputusan ditolak", True, "")
            # void dalam jendela unlock → jejak unlock
            req2 = await pus.request_unlock(period_type="month", period_key="2025-03", entity_id=E, reason="audit2", actor=admin) \
                if final["status"] == "rejected" else None
            if req2:
                await pus.approve_request(req2["id"], other)
            v = await gl.void_entry(S["e1"]["id"], admin)
            check("FN-09", "void dengan unlock aktif tercatat di jendela unlock", v["status"] == "void" and v.get("voided_in_unlock"), v.get("voided_in_unlock"))
            try:
                await gl.void_entry(S["e1"]["id"], admin)
                check("FN-09", "void ulang ditolak", False, "lolos")
            except ValueError:
                check("FN-09", "void ulang ditolak", True, "")
        try:
            await sec_7()
        except Exception as exc:  # noqa: BLE001
            check('IX-08', 'bagian IX-08 crash', False, repr(exc))

        # ── CX-09 — perimeter eliminasi ────────────────────────────────────────
        async def sec_8():
            imp = {"revenue": 0, "cogs": 0, "opex": 0, "assets": -30, "liabilities": -30, "equity": 0}
            await db.intercompany_eliminations.insert_many([
                {"id": f"icelim_fg_{T}", "entity_from": F, "entity_to": G, "effective_date": "2025-01-01", "impact": imp, "audit_fixture": T},
                {"id": f"icelim_ef_{T}", "entity_from": E, "entity_to": F, "effective_date": "2025-01-01",
                 "impact": {**imp, "assets": -5, "liabilities": -5}, "audit_fixture": T}])
            s_e = await cons.summary([E], 2025, "2025-12-31")
            s_ef = await cons.summary([E, F], 2025, "2025-12-31")
            check("CX-09", "E saja: tanpa eliminasi F↔G / E↔F", s_e["elimination"]["assets"] == 0, s_e["elimination"])
            check("CX-09", "E+F: hanya eliminasi E↔F", s_ef["elimination"]["assets"] == -5, s_ef["elimination"])
            n_before = await db.intercompany_eliminations.count_documents({})
            await cons.summary([E, F], 2025, "2025-12-31")
            check("CX-09", "membaca laporan tidak menulis eliminasi", await db.intercompany_eliminations.count_documents({}) == n_before, "")
        try:
            await sec_8()
        except Exception as exc:  # noqa: BLE001
            check('CX-09', 'bagian CX-09 crash', False, repr(exc))
    finally:
        ents = [E, F, G]
        await db.journal_entries.delete_many({"entity_id": {"$in": ents}})
        await db.period_closings.delete_many({"entity_id": {"$in": ents}})
        await db.period_unlock_requests.delete_many({"entity_id": {"$in": ents}})
        await db.period_close_locks.delete_many({"_id": {"$in": ents}})
        await db.gl_accounts.delete_many({"$or": [{"code": {"$in": [X, Y]}}, {"audit_fixture": T}]})
        await db.intercompany_eliminations.delete_many({"audit_fixture": T})
        await db.business_entities.delete_many({"id": {"$in": ents}})
        await db.counters.delete_many({"_id": {"$regex": T}}) if "counters" in await db.list_collection_names() else None
    npass = sum(r["pass"] for r in results)
    print(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"pass={npass} fail={len(results) - npass}")


asyncio.run(main())
