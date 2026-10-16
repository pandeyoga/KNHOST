"""P13 — Audit trail (before/after/diff/actor_id/source/content_hash) & secret redaction.

Prasyarat: backend hidup; admin@kainnusantara.id / demo12345; X-Entity-Id: ent_ksc.
Semua data uji di-prefix TEST_ dan dibersihkan sesudah selesai.
"""
import os
import re
import time
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL harus di-set"
ENT = "ent_ksc"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
_mongo = MongoClient(MONGO_URL)[DB_NAME]


# ── Fixtures ────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "admin@kainnusantara.id", "password": "demo12345"})
    assert r.status_code == 200, r.text
    data = r.json()
    token = data["token"]
    user_id = data["user"]["id"]
    s.headers.update({
        "Authorization": f"Bearer {token}",
        "X-Entity-Id": ENT,
        "Content-Type": "application/json",
    })
    return {"session": s, "token": token, "user_id": user_id}


def _latest_audit(action: str, entity_id: str, since_ts: float):
    """Ambil baris audit_logs terbaru untuk aksi+entity_id tertentu."""
    time.sleep(0.3)  # audit_logs ditulis async
    rows = list(_mongo.audit_logs.find(
        {"action": action, "entity_id": entity_id}
    ).sort("timestamp", -1).limit(5))
    return rows[0] if rows else None


def _assert_audit_shape(row, expected_actor_id: str, action: str):
    assert row is not None, f"audit row {action} tidak ditemukan"
    assert row.get("actor_id") == expected_actor_id, f"actor_id salah: {row.get('actor_id')}"
    assert row.get("source"), "source kosong"
    ch = row.get("content_hash", "")
    assert isinstance(ch, str) and re.fullmatch(r"[0-9a-f]{64}", ch), f"content_hash bukan 64 hex: {ch!r}"


# ── GL account PATCH/DELETE ─────────────────────────────────────────────────
class TestGLAccountAudit:
    code = None

    def test_create_test_account(self, admin):
        s = admin["session"]
        code = f"TEST_{int(time.time())}"
        r = s.post(f"{BASE_URL}/api/gl/accounts", json={
            "code": code, "name": "TEST_GL Original", "type": "asset",
            "normal_balance": "debit",
        })
        assert r.status_code in (200, 201), r.text
        TestGLAccountAudit.code = code

    def test_patch_gl_account_before_after_diff(self, admin):
        s = admin["session"]
        code = TestGLAccountAudit.code
        assert code
        t0 = time.time()
        r = s.patch(f"{BASE_URL}/api/gl/accounts/{code}",
                    json={"name": "TEST_GL Updated"})
        assert r.status_code == 200, r.text
        row = _latest_audit("gl_account_updated", code, t0)
        _assert_audit_shape(row, admin["user_id"], "gl_account_updated")
        assert (row.get("before") or {}).get("name") == "TEST_GL Original"
        assert (row.get("after") or {}).get("name") == "TEST_GL Updated"
        diff = row.get("diff") or []
        name_diff = next((d for d in diff if d.get("field") == "name"), None)
        assert name_diff and name_diff["from"] == "TEST_GL Original" and name_diff["to"] == "TEST_GL Updated"

    def test_delete_gl_account_before_snapshot(self, admin):
        s = admin["session"]
        code = TestGLAccountAudit.code
        t0 = time.time()
        r = s.delete(f"{BASE_URL}/api/gl/accounts/{code}")
        assert r.status_code in (200, 204), r.text
        row = _latest_audit("gl_account_deleted", code, t0)
        _assert_audit_shape(row, admin["user_id"], "gl_account_deleted")
        before = row.get("before") or {}
        assert before.get("code") == code
        assert before.get("name") == "TEST_GL Updated"


# ── Bank account PATCH ──────────────────────────────────────────────────────
class TestBankAccountAudit:
    acc_id = None

    def test_create_test_bank(self, admin):
        s = admin["session"]
        r = s.post(f"{BASE_URL}/api/bank-accounts", json={
            "name": "TEST_Bank Original", "account_type": "bank",
            "entity_id": ENT, "currency": "IDR",
        })
        assert r.status_code in (200, 201), r.text
        TestBankAccountAudit.acc_id = r.json()["id"]

    def test_patch_bank_audit(self, admin):
        s = admin["session"]
        aid = TestBankAccountAudit.acc_id
        t0 = time.time()
        r = s.patch(f"{BASE_URL}/api/bank-accounts/{aid}",
                    json={"name": "TEST_Bank Updated"})
        assert r.status_code == 200, r.text
        row = _latest_audit("bank_account_updated", aid, t0)
        _assert_audit_shape(row, admin["user_id"], "bank_account_updated")
        assert (row.get("before") or {}).get("name") == "TEST_Bank Original"
        assert (row.get("after") or {}).get("name") == "TEST_Bank Updated"
        diff = row.get("diff") or []
        assert any(d.get("field") == "name" for d in diff)

    def test_cleanup_bank(self, admin):
        # Soft-cleanup via deactivate PATCH (set is_active False)
        aid = TestBankAccountAudit.acc_id
        admin["session"].patch(f"{BASE_URL}/api/bank-accounts/{aid}",
                               json={"is_active": False})


# ── Settings PUT (scope ent_ksc) ────────────────────────────────────────────
class TestSettingsAudit:
    prev_finance = None

    def test_put_settings_before_value(self, admin):
        s = admin["session"]
        # Baca nilai lama scope ent_ksc
        prev = _mongo.system_settings.find_one({"scope": ENT}, {"_id": 0})
        prev_finance = (prev or {}).get("finance") or {}
        TestSettingsAudit.prev_finance = prev_finance
        new_finance = {**prev_finance, "test_marker_p13": "TEST_v1"}
        t0 = time.time()
        r = s.put(f"{BASE_URL}/api/settings",
                  json={"scope": ENT, "finance": new_finance})
        assert r.status_code == 200, r.text
        row = _latest_audit("settings_updated", ENT, t0)
        _assert_audit_shape(row, admin["user_id"], "settings_updated")
        # before harus memuat kunci finance (nilai lama) — kalau belum ada, None
        before = row.get("before") or {}
        assert "finance" in before, f"'finance' absen di before: {list(before.keys())}"
        assert before.get("finance") == prev_finance or before.get("finance") is None

    def test_restore_settings(self, admin):
        # Kembalikan nilai semula agar tak mengotori data
        s = admin["session"]
        prev = TestSettingsAudit.prev_finance or {}
        s.put(f"{BASE_URL}/api/settings", json={"scope": ENT, "finance": prev})


# ── Customer PATCH ──────────────────────────────────────────────────────────
class TestCustomerAudit:
    cust_id = None
    original_credit_limit = None

    def test_pick_customer(self, admin):
        # pakai pelanggan existing milik ent_ksc
        s = admin["session"]
        r = s.get(f"{BASE_URL}/api/customers?entity_id={ENT}")
        assert r.status_code == 200
        rows = r.json()
        rows = rows if isinstance(rows, list) else rows.get("items", [])
        assert rows, "tidak ada pelanggan di ent_ksc"
        TestCustomerAudit.cust_id = rows[0]["id"]
        TestCustomerAudit.original_credit_limit = rows[0].get("credit_limit", 0)

    def test_patch_customer_credit_limit(self, admin):
        s = admin["session"]
        cid = TestCustomerAudit.cust_id
        orig = TestCustomerAudit.original_credit_limit or 0
        new_val = float(orig) + 12345.0
        t0 = time.time()
        r = s.patch(f"{BASE_URL}/api/customers/{cid}",
                    json={"data": {"credit_limit": new_val}})
        assert r.status_code == 200, r.text
        row = _latest_audit("customer_updated", cid, t0)
        _assert_audit_shape(row, admin["user_id"], "customer_updated")
        before = row.get("before") or {}
        after = row.get("after") or {}
        # after HANYA field yang diubah (plus updated_at). Field dokumen lain tidak muncul.
        assert set(after.keys()) <= {"credit_limit", "updated_at"}, f"after terlalu lebar: {list(after.keys())}"
        assert float(after.get("credit_limit") or 0) == new_val
        assert float(before.get("credit_limit") or 0) == float(orig)

    def test_restore_customer(self, admin):
        s = admin["session"]
        cid = TestCustomerAudit.cust_id
        s.patch(f"{BASE_URL}/api/customers/{cid}",
                json={"data": {"credit_limit": TestCustomerAudit.original_credit_limit or 0}})


# ── HR employee PATCH base_salary ───────────────────────────────────────────
class TestHREmployeeAudit:
    emp_id = None

    def test_create_test_employee(self, admin):
        s = admin["session"]
        r = s.post(f"{BASE_URL}/api/hr/employees", json={
            "name": "TEST_Karyawan P13",
            "nik": f"TEST{int(time.time())}",
            "base_salary": 5000000,
            "entity_id": ENT,
        })
        assert r.status_code in (200, 201), r.text
        TestHREmployeeAudit.emp_id = r.json()["id"]

    def test_patch_base_salary_pii_excluded(self, admin):
        """base_salary ∈ hr_service.PII_FIELDS → sengaja dikecualikan dari jejak audit.

        Dicatat sebagai IMPLEMENTATION.md: "PATCH karyawan (PII tetap dikecualikan)".
        Jadi audit row tetap tertulis & valid (actor_id, source, hash), tetapi before/after
        TIDAK memuat base_salary. Perubahan nilainya tetap terjadi di koleksi master.
        """
        s = admin["session"]
        eid = TestHREmployeeAudit.emp_id
        t0 = time.time()
        r = s.patch(f"{BASE_URL}/api/hr/employees/{eid}",
                    json={"data": {"base_salary": 7500000}})
        assert r.status_code == 200, r.text
        assert float(r.json().get("base_salary") or 0) == 7500000
        row = _latest_audit("hr_employee_updated", eid, t0)
        _assert_audit_shape(row, admin["user_id"], "hr_employee_updated")
        before = row.get("before") or {}
        after = row.get("after") or {}
        # Verifikasi: base_salary memang dikecualikan dari before/after (PII policy)
        assert "base_salary" not in after, "base_salary bocor di after (PII seharusnya dikecualikan)"
        assert "base_salary" not in before, "base_salary bocor di before (PII seharusnya dikecualikan)"

    def test_patch_phone_non_pii(self, admin):
        """Field non-PII (phone) MUNCUL di before/after jejak audit."""
        s = admin["session"]
        eid = TestHREmployeeAudit.emp_id
        # pastikan nilai awal
        s.patch(f"{BASE_URL}/api/hr/employees/{eid}",
                json={"data": {"phone": "08123456789"}})
        time.sleep(0.3)
        t0 = time.time()
        r = s.patch(f"{BASE_URL}/api/hr/employees/{eid}",
                    json={"data": {"phone": "08987654321"}})
        assert r.status_code == 200, r.text
        row = _latest_audit("hr_employee_updated", eid, t0)
        _assert_audit_shape(row, admin["user_id"], "hr_employee_updated")
        before = row.get("before") or {}
        after = row.get("after") or {}
        assert after.get("phone") == "08987654321"
        assert before.get("phone") == "08123456789"

    def test_cleanup_employee(self, admin):
        eid = TestHREmployeeAudit.emp_id
        admin["session"].delete(f"{BASE_URL}/api/hr/employees/{eid}")
        # hard remove jejak synth
        _mongo.hr_employees.delete_one({"id": eid})


# ── Redaction: tidak ada secret bocor di audit_logs baris baru ──────────────
def test_no_secret_in_recent_audit_rows():
    """Scan 200 baris audit_logs terbaru: kunci password/token/secret harus [REDACTED] bila ada."""
    hint_keys = ("password", "token", "secret", "api_key", "private_key", "otp", "session", "credential", "pin")
    rows = list(_mongo.audit_logs.find({}, {"_id": 0}).sort("timestamp", -1).limit(200))
    bad = []

    def _scan(d, path=""):
        if isinstance(d, dict):
            for k, v in d.items():
                if any(h in str(k).lower() for h in hint_keys):
                    if v not in (None, "", "[REDACTED]"):
                        bad.append(f"{path}.{k}={v!r}")
                _scan(v, f"{path}.{k}")
        elif isinstance(d, list):
            for i, x in enumerate(d):
                _scan(x, f"{path}[{i}]")

    for r in rows:
        _scan({"before": r.get("before"), "after": r.get("after")})
    assert not bad, f"Potensi secret bocor: {bad[:5]}"
