"""P12 — HR-01, HR-02, HR-03, IX-01, IX-03, IX-04, MK-01 — regression invariant (in-process, data sintetis).

Usage: cd /app/backend && python ../audit/iterations/2026-10-02-P12-payroll-hr-marketing/repro_p12.py
Angka acuan dihitung tangan dari aturan (PP 35/2021, PMK 168/2023, UU HPP ps.17), bukan memanggil fungsi aplikasi.
Data sintetis ber-prefix `audit_p12_*` dihapus di akhir.
"""
import asyncio
import copy
import json
import sys
import uuid
from datetime import date, timedelta

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
results = []
ENT = "ent_ksc"
T = f"audit_p12_{uuid.uuid4().hex[:6]}"


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def guarded(fid, coro):
    try:
        await coro
    except Exception as exc:  # noqa: BLE001
        check(fid, f"bagian {fid} crash", False, repr(exc)[:300])


async def main():
    from db import db
    from core_utils import now_iso
    from services import hr_service, hr_payroll_service as pay, hr_attendance_service as att
    from services import hr_leave_service as lvs

    cfg0 = await hr_service.get_hr_settings(ENT)

    def cfg(**ot):
        c = copy.deepcopy(cfg0)
        c["overtime"] = {**(c.get("overtime") or {}), "hours_divisor": 173, **ot}
        c.pop("ter_enabled", None)
        return c

    async def mk_emp(n, **kw):
        e = {"id": f"{T}_e{n}", "name": f"Audit P12 {n}", "entity_id": ENT, "status": "active",
             "base_salary": 173_000, "ptkp_status": "TK0", "bpjs_kes_enabled": False, "bpjs_tk_enabled": False,
             "created_at": now_iso(), **kw}
        await db.hr_employees.insert_one(dict(e))
        return e

    # ── HR-02 / IX-04 — lembur ──────────────────────────────────────────────
    async def overtime():
        e = await mk_emp("ot")
        # 2026-10-06 = Selasa (hari kerja). Absensi 120 mnt approved + pengajuan formal 120 mnt tanggal sama.
        await db.hr_attendance.insert_one({"id": f"{T}_a1", "employee_id": e["id"], "date": "2026-10-06",
                                           "overtime_min": 120, "approved": True, "status": "hadir",
                                           "method": "fingerprint", "entity_id": ENT})
        await db.hr_overtime.insert_one({"id": f"{T}_o1", "employee_id": e["id"], "date": "2026-10-06",
                                         "period": "2026-10", "minutes": 120, "status": "approved",
                                         "rate_basis": "normal", "entity_id": ENT})
        # 2026-10-07: absensi flagged & belum disetujui 120 mnt → tidak dibayar
        await db.hr_attendance.insert_one({"id": f"{T}_a2", "employee_id": e["id"], "date": "2026-10-07",
                                           "overtime_min": 120, "approved": False, "status": "flagged",
                                           "method": "mobile", "entity_id": ENT})
        s = await pay.compute_payslip(e, "2026-10", ENT, cfg())
        # upah sejam 1.000; 2 jam hari kerja = 1,5 + 2 = 3,5 jam → 3.500 (sekali)
        check("HR-02", "2 jam hari kerja = 3,5× upah sejam & overlap absensi+pengajuan dihitung sekali",
              abs(s["overtime"] - 3500) < 1, f"overtime={s['overtime']} min={s['overtime_min']}")
        check("IX-04", "absensi flagged/belum approved tidak dibayar", s["overtime_min"] == 120, s["overtime_min"])
        await db.hr_attendance.update_one({"id": f"{T}_a2"}, {"$set": {"approved": True}})
        s2 = await pay.compute_payslip(e, "2026-10", ENT, cfg())
        check("IX-04", "setelah approval dihitung satu kali", s2["overtime_min"] == 240 and abs(s2["overtime"] - 7000) < 1,
              f"min={s2['overtime_min']} amt={s2['overtime']}")
        # Hari istirahat (Minggu 2026-10-11), jadwal 5 hari, 10 jam: 8×2 + 1×3 + 1×4 = 23 jam
        await db.hr_overtime.insert_one({"id": f"{T}_o2", "employee_id": e["id"], "date": "2026-10-11",
                                         "period": "2026-10", "minutes": 600, "status": "approved",
                                         "rate_basis": "weekend", "entity_id": ENT})
        s3 = await pay.compute_payslip(e, "2026-10", ENT, cfg())
        check("HR-02", "hari istirahat 10 jam (5 hari kerja) = 23× upah sejam", abs(s3["overtime"] - 30000) < 1,
              s3["overtime"])
        # Duplikat pengajuan tanggal sama tidak dibayar dua kali
        await db.hr_overtime.insert_one({"id": f"{T}_o3", "employee_id": e["id"], "date": "2026-10-11",
                                         "period": "2026-10", "minutes": 600, "status": "approved",
                                         "rate_basis": "weekend", "entity_id": ENT})
        s4 = await pay.compute_payslip(e, "2026-10", ENT, cfg())
        check("HR-02", "duplikat pengajuan tanggal sama tidak dibayar dua kali", abs(s4["overtime"] - 30000) < 1,
              s4["overtime"])

    # ── IX-03 — shift malam ─────────────────────────────────────────────────
    async def night():
        sh = {"jam_in": "22:00", "jam_out": "06:00", "grace_late_min": 0}
        m = att.compute_metrics("2026-10-05T22:00:00+07:00", "2026-10-06T06:00:00+07:00", sh)
        check("IX-03", "shift 22–06 tepat jadwal: std 480, lembur 0",
              m["std_min"] == 480 and m["overtime_min"] == 0 and m["work_min"] == 480, m)
        m2 = att.compute_metrics("2026-12-31T22:00:00+07:00", "2027-01-01T07:00:00+07:00", sh)
        check("IX-03", "lintas tahun, keluar +60 mnt → lembur 60", m2["overtime_min"] == 60 and m2["early_leave_min"] == 0, m2)
        m3 = att.compute_metrics("2026-10-06T06:00:00+07:00", "2026-10-05T22:00:00+07:00", sh)
        check("IX-03", "clock-out sebelum masuk → tanpa lembur", m3["overtime_min"] == 0 and m3["work_min"] == 0, m3)
        m4 = att.compute_metrics("2026-10-05T08:00:00+07:00", "2026-10-05T18:00:00+07:00",
                                 {"jam_in": "08:00", "jam_out": "17:00"})
        check("IX-03", "shift siang tetap (std 540, lembur 60)", m4["std_min"] == 540 and m4["overtime_min"] == 60, m4)

    # ── HR-01 — PPh21 masa terakhir ────────────────────────────────────────
    async def tax():
        run_id = f"{T}_run"
        await db.hr_payroll_runs.insert_one({"id": run_id, "entity_id": ENT, "period": "2026-01", "status": "posted"})

        async def prior(e, months):
            for mth in range(1, months + 1):
                await db.hr_payslips.insert_one({"id": f"{T}_s{e['id'][-3:]}{mth}", "run_id": run_id,
                                                 "employee_id": e["id"], "entity_id": ENT,
                                                 "period": f"2026-{mth:02d}", "gross": 10_000_000,
                                                 "pph21": 200_000, "bpjs_emp": {"jht": 0, "jp": 0}})
        e = await mk_emp("tax", base_salary=10_000_000)
        await prior(e, 11)
        nov = await pay.compute_payslip(e, "2026-11", ENT, cfg())
        check("HR-01", "masa biasa tetap TER (10 jt kategori A = 2%)", abs(nov["pph21"] - 200_000) < 1, nov["pph21"])
        dec = await pay.compute_payslip(e, "2026-12", ENT, cfg())
        # 120 jt − BJ 6 jt − PTKP 54 jt = PKP 60 jt × 5% = 3 jt; dipotong Jan–Nov 2,2 jt → Des 800 rb
        check("HR-01", "Desember = PPh setahun Pasal 17 − potongan sebelumnya (800.000)",
              abs(dec["pph21"] - 800_000) < 1, f"pph21={dec['pph21']} annual={dec.get('pph21_annual')}")
        r = await mk_emp("rsg", base_salary=10_000_000, status="resigned", end_date="2026-06-15")
        await prior(r, 5)
        jun = await pay.compute_payslip(r, "2026-06", ENT, cfg())
        # 60 jt − BJ 3 jt = 57 jt < PTKP 54 jt? 57 − 54 = 3 jt × 5% = 150 rb; dipotong 1 jt → lebih potong −850 rb
        check("HR-01", "berhenti Juni: rekonsiliasi bagian tahun → lebih potong dikembalikan (−850.000)",
              abs(jun["pph21"] + 850_000) < 1 and abs(jun["net"] - (10_000_000 + 850_000)) < 1,
              f"pph21={jun['pph21']} net={jun['net']}")
        emps = await pay._active_employees(ENT, "2026-06") if "period" in pay._active_employees.__code__.co_varnames \
            else await pay._active_employees(ENT)
        check("HR-01", "karyawan berhenti pada periode itu ikut payroll masa terakhir", any(x["id"] == r["id"] for x in emps))

    # ── IX-01 / HR-03 — cuti ────────────────────────────────────────────────
    async def leave():
        e = await mk_emp("lv")
        await lvs.set_entitlement(e["id"], ENT, 2031, 0)
        b = await lvs.recompute_balance(e["id"], ENT, 2031)
        check("IX-01", "override jatah 0 bertahan setelah recompute", b["entitlement"] == 0, b)
        try:
            await lvs.set_entitlement(e["id"], ENT, 2031, -1)
            check("IX-01", "jatah negatif ditolak", False, "lolos")
        except ValueError:
            check("IX-01", "jatah negatif ditolak", True)
        await lvs.set_entitlement(e["id"], ENT, 2030, 12)
        # 2030-03-04 (Senin) .. 2030-03-15 (Jumat) = 10 hari kerja
        a = await lvs.submit_leave(e, {"leave_type": "cuti_tahunan", "date_from": "2030-03-04", "date_to": "2030-03-15"}, "audit")
        try:
            await lvs.submit_leave(e, {"leave_type": "cuti_tahunan", "date_from": "2030-04-01", "date_to": "2030-04-12"}, "audit")
            second = "lolos"
        except ValueError as exc:
            second = str(exc)
        check("HR-03", "dua pengajuan 10 hari dengan jatah 12 → yang kedua ditolak (pending dihitung)",
              second != "lolos", second)
        try:
            await lvs.submit_leave(e, {"leave_type": "izin", "date_from": "2030-03-06", "date_to": "2030-03-06"}, "audit")
            ov = "lolos"
        except ValueError as exc:
            ov = str(exc)
        check("HR-03", "pengajuan bertabrakan tanggal ditolak", ov != "lolos", ov)
        await lvs.approve_leave(a["id"], {"name": "audit"})
        b = await lvs.recompute_balance(e["id"], ENT, 2030)
        check("HR-03", "approved tidak melebihi jatah", b["used"] == 10 and b["remaining"] == 2, b)
        # lintas tahun 2030-12-30 (Senin) .. 2031-01-03 (Jumat) → 2 hari 2030, 3 hari 2031
        await lvs.set_entitlement(e["id"], ENT, 2031, 12)
        x = await lvs.submit_leave(e, {"leave_type": "cuti_tahunan", "date_from": "2030-12-30", "date_to": "2031-01-03"}, "audit")
        try:
            await lvs.approve_leave(x["id"], {"name": "audit"})
        except ValueError as exc:
            check("HR-03", "approve lintas tahun", False, exc)
        b30 = await lvs.recompute_balance(e["id"], ENT, 2030)
        b31 = await lvs.recompute_balance(e["id"], ENT, 2031)
        check("HR-03", "cuti lintas tahun dibebankan per tahun tanggal kerja (2030: +2, 2031: 3)",
              b30["used"] == 12 and b31["used"] == 3, f"2030={b30['used']} 2031={b31['used']}")
        # cancel A tidak menghapus absensi cuti milik request lain pada tanggal A
        await db.hr_attendance.update_one({"employee_id": e["id"], "date": "2030-03-05"},
                                          {"$set": {"leave_request_id": f"{T}_other", "note": "Cuti·LV-LAIN: x"}})
        await lvs.cancel_leave(a["id"], {"name": "audit"})
        kept = await db.hr_attendance.find_one({"employee_id": e["id"], "date": "2030-03-05"})
        gone = await db.hr_attendance.find_one({"employee_id": e["id"], "date": "2030-03-04"})
        check("HR-03", "cancel satu cuti tidak menghapus absensi request lain", bool(kept) and not gone,
              f"kept={bool(kept)} gone={bool(gone)}")

    # ── MK-01 — metrik marketing ───────────────────────────────────────────
    async def metrics():
        from services import marketing_service as mk
        pid = f"{T}_post"
        await db.mkt_posts.insert_one({"id": pid, "title": "Audit", "status": "published", "entity_id": ENT,
                                       "metrics": {"likes": 10.0}, "metrics_history": []})
        await mk.record_metrics(pid, {"reach": 100}, {"name": "audit"})
        p = await db.mkt_posts.find_one({"id": pid})
        check("MK-01", "update reach tidak menghapus likes", p["metrics"].get("likes") == 10 and p["metrics"].get("reach") == 100,
              p["metrics"])
        await mk.record_metrics(pid, {"likes": 0}, {"name": "audit"})
        p = await db.mkt_posts.find_one({"id": pid})
        check("MK-01", "likes 0 eksplisit mengganti nilai", p["metrics"].get("likes") == 0, p["metrics"])
        await asyncio.gather(mk.record_metrics(pid, {"shares": 5}, {"name": "a"}),
                             mk.record_metrics(pid, {"comments": 7}, {"name": "b"}))
        p = await db.mkt_posts.find_one({"id": pid})
        m = p["metrics"]
        check("MK-01", "dua update field berbeda bersamaan tidak saling menimpa",
              m.get("shares") == 5 and m.get("comments") == 7 and m.get("reach") == 100, m)

    for fid, fn in (("HR-02", overtime), ("IX-03", night), ("HR-01", tax), ("HR-03", leave), ("MK-01", metrics)):
        await guarded(fid, fn())

    rx = {"$regex": f"^{T}"}
    for coll, field in (("hr_employees", "id"), ("hr_attendance", "employee_id"), ("hr_overtime", "employee_id"),
                        ("hr_payslips", "employee_id"), ("hr_payroll_runs", "id"), ("hr_leave_requests", "employee_id"),
                        ("hr_leave_balances", "employee_id"), ("mkt_posts", "id")):
        await db[coll].delete_many({field: rx})
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")
    _ = (date, timedelta)


asyncio.run(main())
