"""Iteration 158 — verify status-counts endpoints for Cuti/Kontrabon/Kasus Keuangan.

Covers:
- GET /api/hr/leave-requests/status-counts   -> {<status>: n, total: N}
- GET /api/contra-bons/status-counts         -> {<status>: n, ...}
- GET /api/finance-cases/stats               -> includes by_status, total

Admin login: admin@kainnusantara.id / demo12345
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"


# ────────── Fixtures ──────────
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "admin@kainnusantara.id", "password": "demo12345"})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# ────────── Leave status-counts ──────────
class TestLeaveStatusCounts:
    def test_status_counts_shape(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/hr/leave-requests/status-counts")
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert isinstance(data, dict)
        assert "total" in data, f"missing total; keys={list(data.keys())}"
        # sum of non-total == total
        s = sum(v for k, v in data.items() if k != "total")
        assert s == data["total"], f"status sum {s} != total {data['total']}"


# ────────── Contra-bon status-counts ──────────
class TestContraBonStatusCounts:
    def test_status_counts_shape(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/contra-bons/status-counts")
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert isinstance(data, dict)
        # must return at least one key or empty-but-dict
        for k, v in data.items():
            assert isinstance(v, int), f"{k}={v} not int"


# ────────── Finance cases stats.by_status ──────────
class TestFinanceCasesStats:
    def test_stats_by_status(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/finance-cases/stats")
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "by_status" in data, f"missing by_status, keys={list(data.keys())}"
        assert isinstance(data["by_status"], dict)
        assert "total" in data
        s = sum(data["by_status"].values())
        assert s == data["total"], f"by_status sum {s} != total {data['total']}"


# ────────── Leave: create+approve+reject -> verify counts per status ──────────
class TestLeaveCountsDynamic:
    def test_create_and_decide_updates_counts(self, admin_session):
        # pick any employee
        emps = admin_session.get(f"{BASE_URL}/api/hr/employees").json()
        if not isinstance(emps, list) or not emps:
            pytest.skip("no employees")
        emp = emps[0]
        emp_id = emp["id"]

        # baseline counts
        base = admin_session.get(f"{BASE_URL}/api/hr/leave-requests/status-counts").json()
        base_total = base.get("total", 0)
        base_pending = base.get("pending", 0)
        base_approved = base.get("approved", 0)
        base_rejected = base.get("rejected", 0)

        created_ids = []
        payload_a = {
            "employee_id": emp_id,
            "leave_type": "cuti_tahunan",
            "date_from": "2026-02-10",
            "date_to": "2026-02-10",
            "reason": "TEST_iter158_a",
        }
        payload_b = {
            "employee_id": emp_id,
            "leave_type": "cuti_tahunan",
            "date_from": "2026-02-11",
            "date_to": "2026-02-11",
            "reason": "TEST_iter158_b",
        }
        try:
            ra = admin_session.post(f"{BASE_URL}/api/hr/leave-requests", json=payload_a)
            assert ra.status_code in (200, 201), ra.text[:300]
            doc_a = ra.json()
            created_ids.append(doc_a["id"])

            rb = admin_session.post(f"{BASE_URL}/api/hr/leave-requests", json=payload_b)
            assert rb.status_code in (200, 201), rb.text[:300]
            doc_b = rb.json()
            created_ids.append(doc_b["id"])

            # after create → total +2 pending
            c1 = admin_session.get(f"{BASE_URL}/api/hr/leave-requests/status-counts").json()
            assert c1["total"] == base_total + 2
            assert c1.get("pending", 0) == base_pending + 2

            # approve doc_a
            ap = admin_session.post(
                f"{BASE_URL}/api/hr/leave-requests/{doc_a['id']}/approve",
                json={"notes": "TEST_iter158 approve"},
            )
            assert ap.status_code in (200, 201), ap.text[:300]

            # reject doc_b
            rj = admin_session.post(
                f"{BASE_URL}/api/hr/leave-requests/{doc_b['id']}/reject",
                json={"notes": "TEST_iter158 reject"},
            )
            assert rj.status_code in (200, 201), rj.text[:300]

            c2 = admin_session.get(f"{BASE_URL}/api/hr/leave-requests/status-counts").json()
            assert c2["total"] == base_total + 2
            assert c2.get("approved", 0) == base_approved + 1
            assert c2.get("rejected", 0) == base_rejected + 1
            # sum == total
            s = sum(v for k, v in c2.items() if k != "total")
            assert s == c2["total"]

        finally:
            # cleanup: no DELETE endpoint — reach into DB directly
            if created_ids:
                try:
                    import asyncio
                    from db import db as _db  # type: ignore

                    async def _rm():
                        await _db.hr_leave_requests.delete_many({"id": {"$in": created_ids}})
                    asyncio.run(_rm())
                except Exception:
                    pass
