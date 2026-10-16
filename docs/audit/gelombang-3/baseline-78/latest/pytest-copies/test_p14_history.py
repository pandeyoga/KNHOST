"""Backend tests for P14 'Riwayat Perubahan' (audit history) + base_salary masking.

Covers:
- GET /api/audit-logs/resource (admin ok, sales 403)
- GL account create/update/delete history + integrity
- HR employee base_salary masked in diff
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ENT = "ent_ksc"


def _login(email: str, pw: str = "demo12345") -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers():
    tok = _login("admin@kainnusantara.id")
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": ENT, "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def sales_headers():
    tok = _login("sales@kainnusantara.id")
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": ENT, "Content-Type": "application/json"}


# --- Audit history permission ---

def test_audit_resource_admin_ok(admin_headers):
    # pick any gl account via list
    r = requests.get(f"{BASE_URL}/api/gl/accounts", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    accts = r.json()
    if isinstance(accts, dict):
        accts = accts.get("items") or accts.get("accounts") or []
    assert accts, "no gl accounts to probe"
    code = accts[0]["code"]
    r = requests.get(
        f"{BASE_URL}/api/audit-logs/resource",
        headers=admin_headers,
        params={"entity_type": "gl_account", "entity_id": code},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "total" in body and "items" in body
    assert "truncated" in body


def test_audit_resource_sales_forbidden(sales_headers):
    r = requests.get(
        f"{BASE_URL}/api/audit-logs/resource",
        headers=sales_headers,
        params={"entity_type": "gl_account", "entity_id": "1-00000"},
        timeout=30,
    )
    assert r.status_code == 403, f"sales should be forbidden, got {r.status_code} {r.text}"


# --- GL account CRUD history ---

def test_gl_account_create_patch_delete_history(admin_headers):
    code = f"9-7{int(time.time()) % 100000:05d}"
    payload = {"code": code, "name": "TEST_P14 Lama", "type": "expense", "is_postable": True}
    r = requests.post(f"{BASE_URL}/api/gl/accounts", json=payload, headers=admin_headers, timeout=30)
    assert r.status_code in (200, 201), r.text

    # patch name
    r = requests.patch(
        f"{BASE_URL}/api/gl/accounts/{code}",
        json={"name": "TEST_P14 Baru"},
        headers=admin_headers,
        timeout=30,
    )
    assert r.status_code in (200, 204), r.text

    # fetch history
    r = requests.get(
        f"{BASE_URL}/api/audit-logs/resource",
        headers=admin_headers,
        params={"entity_type": "gl_account", "entity_id": code},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items, "expected audit items for new gl_account"
    # find row with diff name from->to
    found = False
    for it in items:
        for d in it.get("diff") or []:
            if d.get("field") == "name" and d.get("from") == "TEST_P14 Lama" and d.get("to") == "TEST_P14 Baru":
                found = True
                assert it.get("integrity") in ("ok", "unsigned"), it
                break
        if found:
            break
    assert found, f"did not find name diff Lama->Baru in items: {items}"

    # cleanup: delete
    r = requests.delete(f"{BASE_URL}/api/gl/accounts/{code}", headers=admin_headers, timeout=30)
    assert r.status_code in (200, 204), r.text


# --- HR base_salary masking ---

def test_hr_base_salary_masked(admin_headers):
    r = requests.get(f"{BASE_URL}/api/hr/employees", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    emps = body if isinstance(body, list) else (body.get("items") or body.get("employees") or [])
    assert emps, "no employees"
    emp = emps[0]
    emp_id = emp.get("id") or emp.get("employee_id") or emp.get("_id")
    assert emp_id

    # current base_salary (may be masked); fetch raw via patch: we need to set a new value
    # Use arbitrary value then revert
    new_val = 7777000
    r = requests.patch(
        f"{BASE_URL}/api/hr/employees/{emp_id}",
        json={"data": {"base_salary": new_val}},
        headers=admin_headers,
        timeout=30,
    )
    assert r.status_code in (200, 204), r.text

    # read audit
    r = requests.get(
        f"{BASE_URL}/api/audit-logs/resource",
        headers=admin_headers,
        params={"entity_type": "hr_employee", "entity_id": emp_id},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items
    # newest row at [0]
    top = items[0]
    # ensure no plaintext value in the row
    serial = str(top)
    assert str(new_val) not in serial, f"plaintext salary leaked in audit row: {serial[:400]}"
    diff = top.get("diff") or []
    bs = [d for d in diff if d.get("field") == "base_salary"]
    assert bs, f"no base_salary diff entry; diff={diff}"
    assert bs[0].get("masked") is True
    assert bs[0].get("from") == "[REDACTED]"
    assert bs[0].get("to") == "[REDACTED]"

    # revert: set to a safe value (use original if present, else 0)
    original = emp.get("base_salary")
    revert_val = original if isinstance(original, (int, float)) else 0
    requests.patch(
        f"{BASE_URL}/api/hr/employees/{emp_id}",
        json={"data": {"base_salary": revert_val}},
        headers=admin_headers,
        timeout=30,
    )
