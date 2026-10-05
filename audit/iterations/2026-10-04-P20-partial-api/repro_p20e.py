"""P20e — HR-01 (cuti tumpang-tindih/batal/lintas tahun menjaga jatah & absensi) · HR-03 (payroll satu periode → GL → bayar) ·
HR-05 (posting GL payroll gagal → retry tanpa ganda; bayar bersamaan → satu pembayaran).

Usage: cd /app/backend && python ../audit/iterations/2026-10-04-P20-partial-api/repro_p20e.py
Self-clean: run/slip/cuti/absensi/jurnal/kas baru dihapus; saldo cuti, akun GL, nomor dipulihkan.
"""
import json
import os
import sys
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, ".")
load_dotenv(".env")
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402

BASE = "http://localhost:8001/api"
ENT = "ent_ksc"
T = f"TEST_P20E_{uuid.uuid4().hex[:6]}"
PERIOD = "2026-10"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
NEW = ["hr_payroll_runs", "hr_payslips", "hr_leave_requests", "hr_attendance", "journal_entries", "cash_transactions",
       "audit_logs", "notifications", "gl_outbox", "hr_leave_balances"]
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:400]})


def login(email):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT})
    return s


def ok(r):
    assert r.status_code == 200, f"{r.request.method} {r.url} → {r.status_code} {r.text[:400]}"
    return r.json()


def net(ids):
    tot = defaultdict(float)
    for j in db.journal_entries.find({"id": {"$in": [i for i in ids if i]}, "status": {"$ne": "void"}}, {"_id": 0, "lines": 1}):
        for ln in j["lines"]:
            tot[ln["account_code"]] += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return {k: round(v, 2) for k, v in tot.items() if abs(v) > 0.005}


def bal(emp, yr):
    b = db.hr_leave_balances.find_one({"employee_id": emp, "year": yr}, {"_id": 0}) or {}
    return int(b.get("used") or 0), int(b.get("pending") or 0), int(b.get("entitlement") or 0)


def hr01(s):
    emp = db.hr_employees.find_one({"entity_id": ENT, "status": "active"}, {"_id": 0})["id"]
    for yr in (2026, 2027):
        ok(s.post(f"{BASE}/hr/leave-balances/set", json={"employee_id": emp, "year": yr, "entitlement": 12}))
    b26, b27 = bal(emp, 2026), bal(emp, 2027)
    a = ok(s.post(f"{BASE}/hr/leave-requests", json={"employee_id": emp, "leave_type": "cuti_tahunan", "date_from": "2026-12-30",
                                                    "date_to": "2027-01-05", "reason": f"{T} lintas tahun"}))
    check("HR-01", "cuti 30 Des–5 Jan (5 hari kerja) → pending terpecah per tahun: 2026 +2, 2027 +3",
          a["days"] == 5 and bal(emp, 2026)[1] - b26[1] == 2 and bal(emp, 2027)[1] - b27[1] == 3, (a["days"], bal(emp, 2026), bal(emp, 2027)))
    clash = s.post(f"{BASE}/hr/leave-requests", json={"employee_id": emp, "leave_type": "izin", "date_from": "2027-01-04",
                                                     "date_to": "2027-01-04", "reason": f"{T} tabrakan"})
    check("HR-01", "pengajuan yang menimpa tanggal cuti lain (meski jenis lain) ditolak 400", clash.status_code == 400 and "bertabrakan" in clash.text,
          (clash.status_code, clash.text[:120]))
    big = s.post(f"{BASE}/hr/leave-requests", json={"employee_id": emp, "leave_type": "cuti_tahunan", "date_from": "2027-02-01",
                                                   "date_to": "2027-02-12", "reason": f"{T} terlalu panjang"})
    check("HR-01", "10 hari 2027 saat sisa 2027 = 12−3 pending = 9 → ditolak 400, pending tidak bocor",
          big.status_code == 400 and bal(emp, 2027)[1] - b27[1] == 3, (big.status_code, big.text[:120], bal(emp, 2027)))
    ok(s.post(f"{BASE}/hr/leave-requests/{a['id']}/approve"))
    att = db.hr_attendance.count_documents({"employee_id": emp, "leave_request_id": a["id"]})
    check("HR-01", "approve → used 2026 +2 / 2027 +3, pending kembali, 5 absensi 'leave' tercatat",
          bal(emp, 2026)[0] - b26[0] == 2 and bal(emp, 2027)[0] - b27[0] == 3 and bal(emp, 2026)[1] == b26[1]
          and bal(emp, 2027)[1] == b27[1] and att == 5, (bal(emp, 2026), bal(emp, 2027), att))
    cx = s.post(f"{BASE}/hr/leave-requests/{a['id']}/cancel", json={"reason": f"{T} batal"})
    check("HR-01", "batal cuti approved → used kembali ke awal di dua tahun, absensi cuti dihapus",
          cx.status_code == 200 and bal(emp, 2026) == b26 and bal(emp, 2027) == b27
          and db.hr_attendance.count_documents({"employee_id": emp, "leave_request_id": a["id"]}) == 0, (cx.status_code, bal(emp, 2026), bal(emp, 2027)))
    again = s.post(f"{BASE}/hr/leave-requests/{a['id']}/cancel", json={"reason": "ulang"})
    re = s.post(f"{BASE}/hr/leave-requests", json={"employee_id": emp, "leave_type": "cuti_tahunan", "date_from": "2026-12-30",
                                                  "date_to": "2026-12-31", "reason": f"{T} ajukan ulang"})
    check("HR-01", "batal ulang 400 (final); tanggal yang dibatalkan bisa diajukan lagi", again.status_code == 400 and re.status_code == 200,
          (again.status_code, re.status_code, re.text[:100]))


def hr03_hr05(s):
    db.hr_payroll_runs.delete_many({"entity_id": ENT, "period": PERIOD})
    run = ok(s.post(f"{BASE}/hr/payroll/runs", json={"entity_id": ENT, "period": PERIOD}))
    rid, tot = run["id"], run["totals"]
    check("HR-03", "run periode dibuat: slip = karyawan aktif, totals.net = Σ take-home slip", len(run["payslips"]) == int(tot.get("employees") or 0) >= 1
          and abs(sum(float(p.get("net") or 0) for p in run["payslips"]) - float(tot.get("net") or 0)) < 1, (len(run["payslips"]), tot))
    early = s.post(f"{BASE}/hr/payroll/runs/{rid}/post-gl")
    ok(s.post(f"{BASE}/hr/payroll/runs/{rid}/submit"))
    ok(s.post(f"{BASE}/hr/payroll/runs/{rid}/approve"))
    db.gl_accounts.update_many({"code": "2-1600"}, {"$set": {"is_active": False}})
    f1 = s.post(f"{BASE}/hr/payroll/runs/{rid}/post-gl")
    r_ = db.hr_payroll_runs.find_one({"id": rid}, {"_id": 0})
    check("HR-05", "post GL sebelum approve 400; akun Hutang Gaji nonaktif → post gagal 4xx berpesan, run tetap approved, tanpa jurnal",
          early.status_code == 400 and 400 <= f1.status_code < 500 and "2-1600" in f1.text and r_["status"] == "approved"
          and not db.journal_entries.find_one({"source_id": rid}), (early.status_code, f1.status_code, f1.text[:150], r_["status"]))
    db.gl_accounts.update_many({"code": "2-1600"}, {"$set": {"is_active": True}})
    with ThreadPoolExecutor(3) as ex:
        posts = list(ex.map(lambda _: s.post(f"{BASE}/hr/payroll/runs/{rid}/post-gl"), range(3)))
    r_ = db.hr_payroll_runs.find_one({"id": rid}, {"_id": 0})
    pj = [j["id"] for j in db.journal_entries.find({"source_id": f"{ENT}:{PERIOD}", "source_type": "payroll_run", "status": {"$ne": "void"}})]
    n1 = net(pj)
    check("HR-05", "retry post GL 3× bersamaan → 1 sukses + 2 ditolak 400 (bukan 500), run posted, tepat 1 jurnal gaji",
          r_["status"] == "posted" and sorted(p.status_code for p in posts) == [200, 400, 400] and len(pj) == 1,
          ([p.status_code for p in posts], r_["status"], len(pj)))
    th = round(float(tot.get("net") or 0), 2)
    check("HR-03", "jurnal payroll seimbang & Hutang Gaji (2-1600) dikredit = Σ take-home", n1.get("2-1600") == -th and
          round(sum(n1.values()), 2) == 0, (n1, th))
    with ThreadPoolExecutor(3) as ex:
        pays = list(ex.map(lambda _: s.post(f"{BASE}/hr/payroll/runs/{rid}/pay", json={"cash_account": "1-1100"}), range(3)))
    r_ = db.hr_payroll_runs.find_one({"id": rid}, {"_id": 0})
    pay_jes = list(db.journal_entries.find({"source_id": f"{ENT}:{PERIOD}", "source_type": "payroll_pay", "status": {"$ne": "void"}}, {"_id": 0, "id": 1}))
    n2 = net([j["id"] for j in pay_jes])
    check("HR-05", "bayar 3× bersamaan → 1 sukses + 2 ditolak 400, tepat 1 jurnal pembayaran, run paid",
          r_["status"] == "paid" and len(pay_jes) == 1 and sorted(p.status_code for p in pays) == [200, 400, 400],
          ([p.status_code for p in pays], r_["status"], pay_jes))
    check("HR-03", "pembayaran: Dr 2-1600 / Cr kas = Σ take-home → Hutang Gaji netral; slip berstatus paid",
          n2.get("2-1600") == th and n2.get("1-1100") == -th and round(n1.get("2-1600", 0) + n2.get("2-1600", 0), 2) == 0
          and db.hr_payslips.count_documents({"run_id": rid, "status": {"$ne": "paid"}}) == 0, (n2, th))
    p2 = s.post(f"{BASE}/hr/payroll/runs/{rid}/pay", json={"cash_account": "1-1100"})
    check("HR-05", "bayar ulang run paid → 400", p2.status_code == 400, p2.status_code)


def main():
    full = snapshot_stock(["number_sequences", "gl_accounts", "hr_leave_balances", "bank_accounts", "cash_balances", "hr_payroll_runs"])
    ids = snapshot_new_ids(NEW)
    s = login("admin@kainnusantara.id")
    try:
        for fn in (hr01, hr03_hr05):
            try:
                fn(s)
            except Exception as exc:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check("RUN", f"eksekusi {fn.__name__}", False, repr(exc)[:300])
    finally:
        db.gl_accounts.update_many({"code": "2-1600"}, {"$set": {"is_active": True}})
        purge_new_ids(ids, verbose=False)
        restore_stock(full)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


if __name__ == "__main__":
    main()
