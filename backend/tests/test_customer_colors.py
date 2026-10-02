"""Backend tests: Warna Pelanggan (customer colors), Kunci Warna Eksklusif, PDF, use-requests.

Covers:
- GET /api/color-library/customer-colors shape & counts
- Product create/patch lock behavior (409 with Indonesian message)
- Use-request flow: create/duplicate/reason/owner/target rules, approve/reject/revoke perms
- PDF card endpoint
"""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://exclusive-palette.preview.emergentagent.com").rstrip("/")
ENT = "ent_ksc"


def _login(email: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    r.raise_for_status()
    return r.json()["token"]


@pytest.fixture(scope="module")
def mgr():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {_login('manager@kainnusantara.id')}", "X-Entity-Id": ENT, "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {_login('admin@kainnusantara.id')}", "X-Entity-Id": ENT, "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def sales():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {_login('sales@kainnusantara.id')}", "X-Entity-Id": ENT, "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def customer_colors(mgr):
    r = mgr.get(f"{BASE_URL}/api/color-library/customer-colors")
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="module")
def sjt_color_id(mgr):
    r = mgr.get(f"{BASE_URL}/api/color-library", params={"q": "KN-SJT-01"})
    r.raise_for_status()
    rows = r.json()
    assert rows and rows[0]["code"] == "KN-SJT-01"
    return rows[0]["id"]


# ---------- 1. customer-colors shape ----------
class TestCustomerColorsShape:
    def test_butik_bali_colors(self, customer_colors):
        bali = next((c for c in customer_colors if c["customer_id"] == "cust_butik_bali"), None)
        assert bali, "Butik Bali Indah missing"
        codes = {c["code"]: c for c in bali["colors"]}
        for code in ("KN-BLI-EMS-01", "KN-GRN-03", "KN-PUR-01"):
            assert code in codes, f"missing {code}"

        ems = codes["KN-BLI-EMS-01"]
        assert ems["owned"] is True
        assert ems.get("exclusive_source", {}).get("kind") == "auto"

        grn = codes["KN-GRN-03"]
        assert grn["owned"] is True
        assert grn.get("exclusive_source", {}).get("kind") == "auto"

        pur = codes["KN-PUR-01"]
        assert pur["owned"] is False
        assert pur["general_products_count"] == 1

        for col in bali["colors"]:
            assert "supplier_versions" in col
            assert "grants" in col
            assert "pending_requests_count" in col

    def test_toko_sejahtera(self, customer_colors):
        sj = next((c for c in customer_colors if c["customer_id"] == "cust_toko_kain"), None)
        assert sj, "Toko Kain Sejahtera missing"
        codes = {c["code"]: c for c in sj["colors"]}
        assert "KN-SJT-01" in codes
        col = codes["KN-SJT-01"]
        assert col["owned"] is True
        assert col.get("exclusive_source", {}).get("kind") == "manual"


# ---------- 2. Lock on product create/patch ----------
class TestProductColorLock:
    _created_ids: list = []

    def _payload(self, color_code: str, exclusive: str = "") -> dict:
        import uuid
        suffix = uuid.uuid4().hex[:6].upper()
        return {
            "template_id": "ptpl_9714f5bf332ebba38e99",
            "sku": f"TST-LOCK-{color_code}-{suffix}",
            "name": f"TST Lock {color_code} {suffix}",
            "base_unit": "yard",
            "fabric_type": "woven",
            "stage": "finished",
            "gramasi": 200,
            "lebar": 1.5,
            "color_code": color_code,
            "exclusive_customer_id": exclusive,
        }

    def test_create_product_with_owned_color_blocked(self, admin):
        r = admin.post(f"{BASE_URL}/api/products", json=self._payload("KN-SJT-01"))
        assert r.status_code == 409, f"expected 409, got {r.status_code}: {r.text[:400]}"
        msg = r.json().get("detail", "")
        assert "Toko Kain Sejahtera" in msg, f"missing owner name: {msg}"
        assert re.search(r"izin.*manajer|persetujuan manajer|Ajukan izin", msg, re.I), f"missing izin manager hint: {msg}"

    def test_patch_general_product_to_owned_color_blocked(self, admin):
        # prod_batik_mega is a general product (exclusivity=umum)
        r = admin.patch(f"{BASE_URL}/api/products/prod_batik_mega", json={"data": {"color_code": "KN-SJT-01"}})
        assert r.status_code == 409, f"expected 409, got {r.status_code}: {r.text[:400]}"
        assert "Toko Kain Sejahtera" in r.json().get("detail", "")

    def test_create_product_with_nonowned_color_not_blocked_by_lock(self, admin):
        # KN-PUR-01 not owned → should not 409 (may fail on unrelated grounds, but not lock)
        payload = self._payload("KN-PUR-01")
        r = admin.post(f"{BASE_URL}/api/products", json=payload)
        # Only fail if 409 is due to LOCK (not SKU collision / variant collision)
        if r.status_code == 409:
            detail = r.json().get("detail", "")
            assert not ("eksklusif" in detail and "milik" in detail), f"unexpected lock 409 for non-owned color: {detail}"
        if r.status_code in (200, 201):
            self._created_ids.append(r.json().get("id"))
            # Cleanup immediately to avoid affecting shape test (counts)
            pid = r.json().get("id")
            if pid:
                admin.delete(f"{BASE_URL}/api/products/{pid}")

    @classmethod
    def teardown_class(cls):
        # hard-delete any TST-* products (endpoint DELETE only soft-deletes)
        try:
            import asyncio, sys
            sys.path.insert(0, "/app/backend")
            from db import db  # type: ignore

            async def _clear():
                await db.products.delete_many({"sku": {"$regex": "^TST-"}})
            asyncio.get_event_loop().run_until_complete(_clear())
        except Exception as e:
            print(f"cleanup skipped: {e}")


# ---------- 3. Use-request flow ----------
class TestUseRequestFlow:
    req_id = None

    def test_sales_create_request_success(self, sales, sjt_color_id):
        r = sales.post(f"{BASE_URL}/api/color-library/{sjt_color_id}/use-requests",
                       json={"target_customer_id": "", "reason": "Butuh warna ini untuk sampel umum"})
        assert r.status_code == 200, r.text[:300]
        row = r.json()
        assert row["status"] == "pending"
        assert row["color_code"] == "KN-SJT-01"
        TestUseRequestFlow.req_id = row["id"]

    def test_duplicate_pending_400(self, sales, sjt_color_id):
        r = sales.post(f"{BASE_URL}/api/color-library/{sjt_color_id}/use-requests",
                       json={"target_customer_id": "", "reason": "duplikasi permintaan yang sama"})
        assert r.status_code == 400

    def test_reason_too_short_400(self, sales, sjt_color_id):
        r = sales.post(f"{BASE_URL}/api/color-library/{sjt_color_id}/use-requests",
                       json={"target_customer_id": "cust_butik_bali", "reason": "abc"})
        assert r.status_code == 400

    def test_request_for_nonowned_color_400(self, sales, mgr):
        # KN-PUR-01 has no owner
        r = mgr.get(f"{BASE_URL}/api/color-library", params={"q": "KN-PUR-01"})
        pur_id = r.json()[0]["id"]
        r = sales.post(f"{BASE_URL}/api/color-library/{pur_id}/use-requests",
                       json={"target_customer_id": "", "reason": "coba warna umum"})
        assert r.status_code == 400

    def test_owner_as_target_400(self, sales, sjt_color_id):
        r = sales.post(f"{BASE_URL}/api/color-library/{sjt_color_id}/use-requests",
                       json={"target_customer_id": "cust_toko_kain", "reason": "warna sendiri saja"})
        assert r.status_code == 400

    def test_sales_cannot_approve_403(self, sales):
        assert TestUseRequestFlow.req_id
        r = sales.post(f"{BASE_URL}/api/color-library/use-requests/{TestUseRequestFlow.req_id}/approve", json={"note": ""})
        assert r.status_code == 403

    def test_list_use_requests_pending_first(self, mgr):
        r = mgr.get(f"{BASE_URL}/api/color-library/use-requests")
        assert r.status_code == 200
        rows = r.json()
        assert any(x["id"] == TestUseRequestFlow.req_id for x in rows)
        # pending first
        statuses = [x["status"] for x in rows]
        pending_idx = [i for i, s in enumerate(statuses) if s == "pending"]
        non_pending_idx = [i for i, s in enumerate(statuses) if s != "pending"]
        if pending_idx and non_pending_idx:
            assert max(pending_idx) < min(non_pending_idx)

    def test_reject_requires_note_400(self, mgr):
        # first create a fresh request to reject
        # use same pending (still in pending) → reject without note must 400
        r = mgr.post(f"{BASE_URL}/api/color-library/use-requests/{TestUseRequestFlow.req_id}/reject", json={"note": ""})
        assert r.status_code == 400

    def test_manager_approve(self, mgr):
        r = mgr.post(f"{BASE_URL}/api/color-library/use-requests/{TestUseRequestFlow.req_id}/approve",
                     json={"note": "disetujui utk uji"})
        assert r.status_code == 200, r.text[:300]
        assert r.json()["status"] == "approved"

    def test_after_approve_product_create_not_locked(self, admin):
        payload = {
            "template_id": "ptpl_9714f5bf332ebba38e99",
            "sku": "TST-AFTER-APPROVE",
            "name": "TST After Approve",
            "base_unit": "yard",
            "fabric_type": "woven",
            "stage": "finished",
            "gramasi": 200,
            "lebar": 1.5,
            "color_code": "KN-SJT-01",
        }
        r = admin.post(f"{BASE_URL}/api/products", json=payload)
        # No 409 with LOCK message (may still 409 for SKU collision / other reasons)
        if r.status_code == 409:
            detail = r.json().get("detail", "")
            assert "eksklusif" not in detail or "Toko Kain Sejahtera" not in detail, f"still locked after approve: {detail}"
        if r.status_code in (200, 201):
            pid = r.json().get("id")
            if pid:
                admin.delete(f"{BASE_URL}/api/products/{pid}")

    def test_revoke_reapplies_lock(self, mgr, admin):
        r = mgr.post(f"{BASE_URL}/api/color-library/use-requests/{TestUseRequestFlow.req_id}/revoke",
                     json={"note": "cabut izin utk uji"})
        assert r.status_code == 200, r.text[:300]
        assert r.json()["status"] == "revoked"

        payload = {
            "template_id": "ptpl_9714f5bf332ebba38e99",
            "sku": "TST-AFTER-REVOKE",
            "name": "TST After Revoke",
            "base_unit": "yard",
            "fabric_type": "woven",
            "stage": "finished",
            "gramasi": 200,
            "lebar": 1.5,
            "color_code": "KN-SJT-01",
        }
        r = admin.post(f"{BASE_URL}/api/products", json=payload)
        assert r.status_code == 409, f"expected re-locked, got {r.status_code}: {r.text[:300]}"

    @classmethod
    def teardown_class(cls):
        # Clear all use_requests on KN-SJT-01 to restore demo state
        try:
            import asyncio, sys
            sys.path.insert(0, "/app/backend")
            from db import db  # type: ignore

            async def _clear():
                await db.color_library.update_one({"code": "KN-SJT-01"}, {"$set": {"use_requests": []}})
            asyncio.get_event_loop().run_until_complete(_clear())
        except Exception as e:
            print(f"cleanup skipped: {e}")

        # delete any TST-* products (hard-delete)
        try:
            import asyncio as _asyncio, sys as _sys
            _sys.path.insert(0, "/app/backend")
            from db import db as _db  # type: ignore

            async def _clear_prods():
                await _db.products.delete_many({"sku": {"$regex": "^TST-"}})
            _asyncio.get_event_loop().run_until_complete(_clear_prods())
        except Exception:
            pass


# ---------- 4. PDF card ----------
class TestCustomerColorCardPDF:
    def test_visible_customer_pdf(self, mgr):
        r = mgr.get(f"{BASE_URL}/api/color-library/customer-colors/cust_butik_bali/card")
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("Content-Type", "")
        assert r.content[:4] == b"%PDF"

    def test_unknown_customer_404(self, mgr):
        r = mgr.get(f"{BASE_URL}/api/color-library/customer-colors/cust_does_not_exist/card")
        assert r.status_code == 404
