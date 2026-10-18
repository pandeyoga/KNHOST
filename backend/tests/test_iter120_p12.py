"""HTTP-level smoke/integration tests for P12 (Payroll / HR / Marketing) — iter-120.

Deeper service-level invariants (23/23) are already covered by
`audit/iterations/2026-10-02-P12-payroll-hr-marketing/repro_p12.py`. This file
exercises the real HTTP surface via REACT_APP_BACKEND_URL to prove routers are
wired, auth/scope works and the key invariants surface through the API.

Scope:
  * payroll preview + create run (no 500) and payslip fields
  * attendance shift 22:00–06:00 → std_min 480, overtime_min 0
  * leave entitlement 0 persists, -1 rejected, overlap/over-quota rejected,
    cross-year split (2030 vs 2031), cancel of approved removes only its leaves
  * overtime API approved: overlap with attendance → counted once
  * marketing posts/{id}/metrics partial update preserves other fields

All synthetic data uses the `test_iter120_` prefix and is torn down.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL",
                      "https://rfid-gate-monitor.preview.emergentagent.com").rstrip("/")
ENTITY = "ent_ksc"
TAG = f"test_iter120_{uuid.uuid4().hex[:6]}"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "knhost")


# ───────────────────────── Fixtures ─────────────────────────
@pytest.fixture(scope="module")
def admin() -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login",
               json={"email": "admin@kainnusantara.id", "password": "demo12345"},
               timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    s.headers.update({"Authorization": f"Bearer {tok}",
                      "X-Entity-Id": ENTITY,
                      "Content-Type": "application/json"})
    return s


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def mongo():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    yield db
    # teardown — remove all synthetic rows this test created
    for col in ("hr_employees", "hr_attendance", "hr_overtime",
                "hr_leave_requests", "hr_leave_balances",
                "hr_payroll_runs", "hr_payslips", "hr_shifts",
                "mkt_posts", "mkt_campaigns"):
        db[col].delete_many({"$or": [
            {"id": {"$regex": f"^{TAG}"}},
            {"employee_id": {"$regex": f"^{TAG}"}},
            {"name": {"$regex": f"^{TAG}"}},
            {"title": {"$regex": f"^{TAG}"}},
            {"number": {"$regex": TAG}},
        ]})
    db.journal_entries.delete_many({"ref_number": {"$regex": TAG}})
    client.close()


@pytest.fixture(scope="module")
def employee(mongo) -> Dict[str, Any]:
    """Insert a synthetic employee for payroll/leave/overtime tests."""
    emp_id = f"{TAG}_emp"
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": emp_id, "number": f"{TAG}-EMP-1", "name": f"{TAG} Karyawan",
        "entity_id": ENTITY, "status": "active",
        "base_salary": 173_000, "ptkp_status": "TK0",
        "bpjs_kes_enabled": False, "bpjs_tk_enabled": False,
        "created_at": now, "updated_at": now,
    }
    mongo.hr_employees.insert_one(dict(doc))
    return doc


# ═══════════════════════════ HR-01/HR-02 PAYROLL (HTTP) ═══════════════════════
class TestPayrollHttp:
    def test_preview_period_december_annual_pph21(self, admin, employee):
        """HR-01 — Desember: pph21_method='annual_pasal17' terisi untuk karyawan sintetis."""
        period = "2030-12"
        r = admin.post(f"{BASE}/api/hr/payroll/runs/preview",
                       json={"entity_id": ENTITY, "period": period}, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["period"] == period
        slips = data.get("payslips", [])
        mine = [s for s in slips if s["employee_id"] == employee["id"]]
        assert mine, f"synthetic emp not in preview; got {len(slips)} slips"
        s = mine[0]
        assert s["pph21_method"] == "annual_pasal17", s["pph21_method"]
        # annual block populated (may be zeros when ter disabled, structure must exist)
        assert "pph21_annual" in s
        assert "tax_gross" in s and "overtime_events" in s

    def test_preview_period_normal_ter_method(self, admin, employee):
        """HR-01 — bulan biasa: pph21_method='ter'."""
        r = admin.post(f"{BASE}/api/hr/payroll/runs/preview",
                       json={"entity_id": ENTITY, "period": "2030-06"}, timeout=60)
        assert r.status_code == 200, r.text
        mine = [s for s in r.json()["payslips"] if s["employee_id"] == employee["id"]]
        assert mine and mine[0]["pph21_method"] == "ter"

    def test_overtime_overlap_counted_once(self, admin, employee, mongo):
        """HR-02/IX-04 — overtime via attendance approved + hr_overtime approved pada tanggal yg sama
        dihitung sekali: overtime_min=120, overtime≈3,5 × base/173 = 3500."""
        now = datetime.now(timezone.utc).isoformat()
        mongo.hr_attendance.insert_one({
            "id": f"{TAG}_att_ok", "employee_id": employee["id"], "date": "2030-06-03",
            "overtime_min": 120, "approved": True, "status": "hadir",
            "method": "fingerprint", "entity_id": ENTITY, "created_at": now})
        mongo.hr_overtime.insert_one({
            "id": f"{TAG}_ot_ok", "employee_id": employee["id"], "date": "2030-06-03",
            "period": "2030-06", "minutes": 120, "status": "approved",
            "rate_basis": "normal", "entity_id": ENTITY, "created_at": now})
        # flagged attendance same month not counted
        mongo.hr_attendance.insert_one({
            "id": f"{TAG}_att_flag", "employee_id": employee["id"], "date": "2030-06-04",
            "overtime_min": 120, "approved": False, "status": "flagged",
            "method": "mobile", "entity_id": ENTITY, "created_at": now})

        r = admin.post(f"{BASE}/api/hr/payroll/runs/preview",
                       json={"entity_id": ENTITY, "period": "2030-06"}, timeout=60)
        assert r.status_code == 200, r.text
        mine = [s for s in r.json()["payslips"] if s["employee_id"] == employee["id"]][0]
        assert mine["overtime_min"] == 120, mine["overtime_min"]
        assert abs(mine["overtime"] - 3500) < 1, mine["overtime"]

    def test_create_run_no_500(self, admin, employee):
        """HR-01 — create run tidak 500 (admin + X-Entity-Id)."""
        period = "2030-11"
        r = admin.post(f"{BASE}/api/hr/payroll/runs",
                       json={"entity_id": ENTITY, "period": period}, timeout=60)
        assert r.status_code == 200, r.text
        run = r.json()
        assert run["entity_id"] == ENTITY and run["period"] == period
        assert "totals" in run and run.get("id", "").startswith("prun_")


# ═══════════════════════════ HR / Attendance shift lintas tengah malam ═════════
class TestNightShift:
    def test_shift_22_to_06_std_480(self, admin, employee, mongo):
        """HR / IX-01 — shift 22:00–06:00 lalu absensi manual lintas hari → std_min 480, overtime_min 0."""
        shift_id = f"{TAG}_shift_night"
        mongo.hr_shifts.insert_one({
            "id": shift_id, "name": f"{TAG} Shift Malam", "code": f"{TAG}SN",
            "jam_in": "22:00", "jam_out": "06:00", "break_min": 0, "grace_late_min": 0,
            "work_days": [0, 1, 2, 3, 4, 5, 6], "status": "active",
            "entity_id": ENTITY, "created_at": datetime.now(timezone.utc).isoformat(),
        })
        # Pin employee to this shift
        mongo.hr_employees.update_one(
            {"id": employee["id"]}, {"$set": {"shift_id": shift_id}})

        r = admin.post(f"{BASE}/api/hr/attendance/manual",
                       json={"employee_id": employee["id"], "date": "2030-07-10",
                             "clock_in": "22:00", "clock_out": "06:00",
                             "status": "hadir", "note": f"{TAG} night"},
                       timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("std_min") == 480, f"std_min={d.get('std_min')} doc={d}"
        assert d.get("overtime_min", 0) == 0, d.get("overtime_min")


# ═══════════════════════════ HR-03 LEAVE (HTTP) ═══════════════════════════
class TestLeave:
    def test_entitlement_negative_rejected(self, admin, employee):
        """IX-01 — jatah negatif ditolak (400)."""
        r = admin.post(f"{BASE}/api/hr/leave-balances/set",
                       json={"employee_id": employee["id"], "year": 2030, "entitlement": -1},
                       timeout=30)
        assert r.status_code == 400, r.text

    def test_entitlement_zero_persists(self, admin, employee):
        """HR-03 — set entitlement 0 → balance tetap 0 (bukan default 12)."""
        r = admin.post(f"{BASE}/api/hr/leave-balances/set",
                       json={"employee_id": employee["id"], "year": 2031, "entitlement": 0},
                       timeout=30)
        assert r.status_code == 200, r.text
        assert int(r.json().get("entitlement", -1)) == 0
        g = admin.get(f"{BASE}/api/hr/leave-balances",
                      params={"entity_id": ENTITY, "year": 2031}, timeout=30)
        assert g.status_code == 200, g.text
        rows = [row for row in g.json() if row["employee_id"] == employee["id"]]
        assert rows and int(rows[0]["entitlement"]) == 0

    def test_quota_12_then_two_tens_rejected(self, admin, employee):
        """HR-03 — jatah 12: ajukan 10 lalu 10 lain → kedua 400."""
        year = 2032
        admin.post(f"{BASE}/api/hr/leave-balances/set",
                   json={"employee_id": employee["id"], "year": year, "entitlement": 12},
                   timeout=30)
        # first 10 days
        r1 = admin.post(f"{BASE}/api/hr/leave-requests",
                        json={"employee_id": employee["id"],
                              "leave_type": "cuti_tahunan",
                              "date_from": f"{year}-03-02", "date_to": f"{year}-03-11",
                              "reason": f"{TAG} r1"}, timeout=30)
        assert r1.status_code == 200, r1.text
        # second 10 days different range
        r2 = admin.post(f"{BASE}/api/hr/leave-requests",
                        json={"employee_id": employee["id"],
                              "leave_type": "cuti_tahunan",
                              "date_from": f"{year}-05-02", "date_to": f"{year}-05-11",
                              "reason": f"{TAG} r2"}, timeout=30)
        assert r2.status_code == 400, r2.text

    def test_overlapping_dates_rejected(self, admin, employee):
        """HR-03 — rentang bertumpang-tindih dengan pengajuan existing → 400."""
        year = 2033
        admin.post(f"{BASE}/api/hr/leave-balances/set",
                   json={"employee_id": employee["id"], "year": year, "entitlement": 20},
                   timeout=30)
        r1 = admin.post(f"{BASE}/api/hr/leave-requests",
                        json={"employee_id": employee["id"], "leave_type": "cuti_tahunan",
                              "date_from": f"{year}-04-05", "date_to": f"{year}-04-07",
                              "reason": f"{TAG} ov1"}, timeout=30)
        assert r1.status_code == 200, r1.text
        r2 = admin.post(f"{BASE}/api/hr/leave-requests",
                        json={"employee_id": employee["id"], "leave_type": "cuti_tahunan",
                              "date_from": f"{year}-04-06", "date_to": f"{year}-04-08",
                              "reason": f"{TAG} ov2"}, timeout=30)
        assert r2.status_code == 400, r2.text

    def test_cross_year_split_and_cancel_isolation(self, admin, employee, mongo):
        """HR-03 — cuti lintas tahun 2030-12-30..2031-01-03 (5 hari kalender; 2 di 2030, 3 di 2031).
        Cancel approved hanya menghapus absensi method leave milik request itu."""
        admin.post(f"{BASE}/api/hr/leave-balances/set",
                   json={"employee_id": employee["id"], "year": 2034, "entitlement": 12}, timeout=30)
        admin.post(f"{BASE}/api/hr/leave-balances/set",
                   json={"employee_id": employee["id"], "year": 2035, "entitlement": 12}, timeout=30)

        # Use spec example years (2030/2031) where 12/30-12/31 are Mon-Tue (2 workdays)
        # and 01/01-01/03 are Wed-Fri (3 workdays). Note: these years are safely in the
        # future relative to seed data and employee is synthetic.
        year_a, year_b = 2030, 2031
        admin.post(f"{BASE}/api/hr/leave-balances/set",
                   json={"employee_id": employee["id"], "year": year_a, "entitlement": 12}, timeout=30)
        admin.post(f"{BASE}/api/hr/leave-balances/set",
                   json={"employee_id": employee["id"], "year": year_b, "entitlement": 12}, timeout=30)
        r = admin.post(f"{BASE}/api/hr/leave-requests",
                       json={"employee_id": employee["id"], "leave_type": "cuti_tahunan",
                             "date_from": f"{year_a}-12-30", "date_to": f"{year_b}-01-03",
                             "reason": f"{TAG} cross"}, timeout=30)
        assert r.status_code == 200, r.text
        leave_cross = r.json()
        appr = admin.post(f"{BASE}/api/hr/leave-requests/{leave_cross['id']}/approve", timeout=30)
        assert appr.status_code == 200, appr.text

        # balance usage: 2 in year_a and 3 in year_b
        g_a = admin.get(f"{BASE}/api/hr/leave-balances",
                        params={"entity_id": ENTITY, "year": year_a}, timeout=30).json()
        g_b = admin.get(f"{BASE}/api/hr/leave-balances",
                        params={"entity_id": ENTITY, "year": year_b}, timeout=30).json()
        used_a = next((row["used"] for row in g_a if row["employee_id"] == employee["id"]), 0) or 0
        used_b = next((row["used"] for row in g_b if row["employee_id"] == employee["id"]), 0) or 0
        # Spec: 2030-12-30 (Mon), 12-31 (Tue) = 2 workdays in 2030;
        # 2031-01-01 (Wed), 01-02 (Thu), 01-03 (Fri) = 3 workdays in 2031.
        assert used_a == 2, f"year_a expected 2 workdays, got {used_a}"
        assert used_b == 3, f"year_b expected 3 workdays, got {used_b}"

        # another approved leave to prove cancel isolation
        r_other = admin.post(f"{BASE}/api/hr/leave-requests",
                             json={"employee_id": employee["id"], "leave_type": "cuti_tahunan",
                                   "date_from": f"{year_a}-02-11", "date_to": f"{year_a}-02-11",
                                   "reason": f"{TAG} other"}, timeout=30)
        assert r_other.status_code == 200, r_other.text
        other = r_other.json()
        assert admin.post(f"{BASE}/api/hr/leave-requests/{other['id']}/approve", timeout=30).status_code == 200

        # count att leave rows before cancel of cross
        def att_counts():
            return (
                mongo.hr_attendance.count_documents(
                    {"employee_id": employee["id"], "method": "leave",
                     "leave_request_id": leave_cross["id"]}),
                mongo.hr_attendance.count_documents(
                    {"employee_id": employee["id"], "method": "leave",
                     "leave_request_id": other["id"]}),
            )
        before_cross, before_other = att_counts()
        assert before_cross > 0 and before_other > 0

        c = admin.post(f"{BASE}/api/hr/leave-requests/{leave_cross['id']}/cancel",
                       json={"reason": f"{TAG} cancel"}, timeout=30)
        assert c.status_code == 200, c.text

        after_cross, after_other = att_counts()
        assert after_cross == 0, f"cross leave att still remains: {after_cross}"
        assert after_other == before_other, f"other leave att changed: {before_other}->{after_other}"


# ═══════════════════════════ MK-01 Marketing metrics ═══════════════════════════
class TestMarketingMetrics:
    def test_partial_metrics_preserve_other_fields(self, admin, mongo):
        """MK-01 — update reach saja tidak menghapus likes; likes=0 eksplisit menimpa."""
        post_id = f"{TAG}_post"
        now = datetime.now(timezone.utc).isoformat()
        mongo.mkt_posts.insert_one({
            "id": post_id, "number": f"{TAG}-MKT-1", "title": f"{TAG} Post",
            "entity_id": ENTITY, "status": "published",
            "channel": "instagram", "account_id": "", "campaign_id": "",
            "publish_at": now, "created_at": now, "updated_at": now,
            "metrics": {"likes": 10.0}, "metrics_history": [],
        })

        r1 = admin.post(f"{BASE}/api/marketing/posts/{post_id}/metrics",
                        json={"metrics": {"reach": 100}, "note": f"{TAG} patch reach"},
                        timeout=30)
        assert r1.status_code == 200, r1.text
        m = r1.json().get("metrics", {})
        assert float(m.get("likes", 0)) == 10.0, m
        assert float(m.get("reach", 0)) == 100.0, m

        r2 = admin.post(f"{BASE}/api/marketing/posts/{post_id}/metrics",
                        json={"metrics": {"likes": 0}, "note": f"{TAG} zero likes"},
                        timeout=30)
        assert r2.status_code == 200, r2.text
        m2 = r2.json().get("metrics", {})
        assert float(m2.get("likes", -1)) == 0.0, m2
        assert float(m2.get("reach", 0)) == 100.0, m2

        # metrics_history captured patch_fields and snapshot
        doc = mongo.mkt_posts.find_one({"id": post_id}, {"_id": 0, "metrics_history": 1}) or {}
        hist = doc.get("metrics_history") or []
        assert len(hist) >= 2
        last = hist[-1]
        assert "patch_fields" in last or "patch" in last, last
        assert "snapshot" in last or "metrics" in last, last
