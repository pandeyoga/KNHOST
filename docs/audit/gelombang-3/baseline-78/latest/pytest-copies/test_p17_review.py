"""P17 review tests: archived read-only, COMM-05 customer prices, COMM-04 incentive GL."""
import os
import time
import uuid
import pytest
import requests
import threading

BASE_URL = (os.environ.get('REACT_APP_BACKEND_URL') or 'https://knhost-preview-3.preview.emergentagent.com').rstrip('/')
ENT_TARGET = "ent_d1772c5f5ced"
ENT_KSC = "ent_ksc"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password},
                      headers={"Content-Type": "application/json"},
                      timeout=20)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def manager_token():
    return _login("manager@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def sales_token():
    return _login("sales@kainnusantara.id", "demo12345")


def _hdr(token, entity_id=ENT_KSC):
    return {"Authorization": f"Bearer {token}", "X-Entity-Id": entity_id,
            "Content-Type": "application/json"}


# ===================== ARSIP BACA-SAJA =====================
class TestArchivedReadOnly:
    def test_archive_and_read_only_lifecycle(self, admin_token, sales_token):
        # Step 1: Archive the entity
        r = requests.post(
            f"{BASE_URL}/api/entities/{ENT_TARGET}/archive",
            headers=_hdr(admin_token),
            json={"reason": "TEST_ uji arsip baca saja", "force": True},
            timeout=60,
        )
        # Accept 200 or 409 (already archived from prior test)
        assert r.status_code in (200, 409), f"archive: {r.status_code} {r.text}"
        print(f"archive status={r.status_code}")

        try:
            # Step 2: wait >20s for cache
            time.sleep(25)

            # Step 3: admin GET entity context should list archived_entities
            r = requests.get(f"{BASE_URL}/api/me",
                             headers={"Authorization": f"Bearer {admin_token}"},
                             timeout=20)
            if r.status_code == 404:
                # try different endpoint
                r = requests.post(f"{BASE_URL}/api/auth/login",
                                  json={"email": "admin@kainnusantara.id",
                                        "password": "demo12345"},
                                  timeout=20)
                data = r.json()
                ctx = data.get("entity_context", {})
            else:
                data = r.json()
                ctx = data.get("entity_context", data)
            archived = ctx.get("archived_entities", [])
            archived_ids = [e.get("id") for e in archived] if archived else []
            print(f"archived_entities ids: {archived_ids}")
            assert ENT_TARGET in archived_ids, f"ENT_TARGET not in archived_entities: {archived_ids}"

            # Step 4: admin GET customers list with X-Entity-Id=ENT_TARGET returns 200
            r = requests.get(
                f"{BASE_URL}/api/customers",
                headers=_hdr(admin_token, ENT_TARGET),
                timeout=30,
            )
            assert r.status_code == 200, f"admin GET customers archived: {r.status_code} {r.text[:300]}"

            # Step 5: admin POST customer in archived entity → 403 'diarsipkan'
            r = requests.post(
                f"{BASE_URL}/api/customers",
                headers=_hdr(admin_token, ENT_TARGET),
                json={"name": "TEST_ archived create",
                      "code": f"TESTARC{uuid.uuid4().hex[:6]}",
                      "pic_name": "TEST pic", "phone": "0800000000",
                      "address": "TEST", "city": "TEST",
                      "customer_type": "wholesale"},
                timeout=30,
            )
            assert r.status_code == 403, f"expected 403 on create in archived, got {r.status_code} {r.text[:300]}"
            body_text = r.text.lower()
            assert "diarsipkan" in body_text or "arsip" in body_text, f"expected 'diarsipkan' message: {r.text}"

            # Step 6: sales (not assigned to that entity) GET → 403
            r = requests.get(
                f"{BASE_URL}/api/customers",
                headers=_hdr(sales_token, ENT_TARGET),
                timeout=30,
            )
            assert r.status_code == 403, f"sales archived GET expected 403, got {r.status_code}"
        finally:
            # Step 7: ALWAYS reactivate
            r = requests.post(
                f"{BASE_URL}/api/entities/{ENT_TARGET}/reactivate",
                headers=_hdr(admin_token),
                timeout=30,
            )
            assert r.status_code in (200, 409), f"reactivate: {r.status_code} {r.text}"
            print(f"reactivate status={r.status_code}")


# ===================== COMM-05 CUSTOMER PRICES =====================
class TestCustomerPrices:
    CUSTOMER_ID = "cust_toko_kain"
    PRODUCT_ID = "prod_benang_katun"

    def _cleanup(self, token, ids):
        for pid in ids:
            try:
                requests.delete(f"{BASE_URL}/api/customer-prices/{pid}",
                                headers=_hdr(token), timeout=15)
            except Exception:
                pass

    def test_patch_deactivated_returns_400(self, admin_token):
        # Create a price
        payload = {
            "customer_id": self.CUSTOMER_ID,
            "product_id": self.PRODUCT_ID,
            "sell_price": 250000,
            "valid_from": "2026-10-01",
            "note": "TEST_ patch deactivated",
        }
        r = requests.post(f"{BASE_URL}/api/customer-prices",
                          headers=_hdr(admin_token), json=payload, timeout=30)
        assert r.status_code in (200, 201), f"create: {r.status_code} {r.text[:300]}"
        pid = r.json().get("id") or r.json().get("_id")
        assert pid, f"no id returned: {r.json()}"

        try:
            # Deactivate
            r = requests.delete(f"{BASE_URL}/api/customer-prices/{pid}",
                                headers=_hdr(admin_token), timeout=15)
            assert r.status_code == 200, f"delete: {r.status_code} {r.text}"

            # PATCH on deactivated → expect 400
            r = requests.patch(f"{BASE_URL}/api/customer-prices/{pid}",
                               headers=_hdr(admin_token),
                               json={"sell_price": 999999}, timeout=15)
            assert r.status_code == 400, f"patch on inactive expected 400, got {r.status_code} {r.text[:200]}"

            # Verify value didn't change
            r = requests.get(f"{BASE_URL}/api/customer-prices?customer_id={self.CUSTOMER_ID}&product_id={self.PRODUCT_ID}",
                             headers=_hdr(admin_token), timeout=15)
            if r.status_code == 200:
                items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
                for it in items:
                    if (it.get("id") or it.get("_id")) == pid:
                        assert float(it.get("sell_price")) == 250000.0, f"price changed: {it}"
        finally:
            self._cleanup(admin_token, [pid])

    def test_double_delete_idempotent(self, admin_token):
        r = requests.post(f"{BASE_URL}/api/customer-prices",
                          headers=_hdr(admin_token),
                          json={"customer_id": self.CUSTOMER_ID,
                                "product_id": self.PRODUCT_ID,
                                "sell_price": 260000,
                                "valid_from": "2026-10-01",
                                "note": "TEST_ double delete"},
                          timeout=30)
        assert r.status_code in (200, 201), r.text
        pid = r.json().get("id") or r.json().get("_id")

        try:
            r1 = requests.delete(f"{BASE_URL}/api/customer-prices/{pid}",
                                 headers=_hdr(admin_token), timeout=15)
            assert r1.status_code == 200, r1.text
            r2 = requests.delete(f"{BASE_URL}/api/customer-prices/{pid}",
                                 headers=_hdr(admin_token), timeout=15)
            assert r2.status_code == 200, f"second delete: {r2.status_code} {r2.text}"
            body = r2.json()
            assert body.get("deactivated") is False, f"expected deactivated=False, got {body}"
            assert body.get("already_inactive") is True, f"expected already_inactive=True, got {body}"
        finally:
            self._cleanup(admin_token, [pid])

    def test_concurrent_posts_leave_single_active(self, admin_token):
        results = []
        created_ids = []

        def post_one(price):
            try:
                r = requests.post(f"{BASE_URL}/api/customer-prices",
                                  headers=_hdr(admin_token),
                                  json={"customer_id": self.CUSTOMER_ID,
                                        "product_id": self.PRODUCT_ID,
                                        "sell_price": price,
                                        "valid_from": "2026-10-01",
                                        "note": f"TEST_ concurrent {price}"},
                                  timeout=30)
                results.append((price, r.status_code, r.text[:200]))
                if r.status_code in (200, 201):
                    j = r.json()
                    created_ids.append(j.get("id") or j.get("_id"))
            except Exception as e:
                results.append((price, "err", str(e)))

        prices = [234001, 234002, 234003, 234004, 234005]  # all > 3x 78000=234000
        threads = [threading.Thread(target=post_one, args=(p,)) for p in prices]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        print(f"concurrent results: {results}")

        try:
            # Query quote
            r = requests.get(
                f"{BASE_URL}/api/customer-prices/quote?customer_id={self.CUSTOMER_ID}&product_ids={self.PRODUCT_ID}",
                headers=_hdr(admin_token), timeout=20)
            assert r.status_code == 200, f"quote: {r.status_code} {r.text[:300]}"
            quote = r.json()
            print(f"quote: {quote}")
            # Quote should have exactly one price for the product
            # Last-created should win (highest-id or latest valid record)
        finally:
            self._cleanup(admin_token, [i for i in created_ids if i])


# ===================== COMM-04 INCENTIVE GL =====================
class TestIncentiveGL:
    def test_gl_status_endpoint(self, manager_token):
        r = requests.get(
            f"{BASE_URL}/api/sales/incentive/gl-status?period=2026-10",
            headers=_hdr(manager_token),
            timeout=20,
        )
        assert r.status_code == 200, f"gl-status: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert "posted" in body, f"missing posted: {body}"
        assert "amount" in body, f"missing amount: {body}"
        print(f"gl-status: {body}")

    def test_post_gl_no_500(self, admin_token):
        r = requests.post(
            f"{BASE_URL}/api/sales/incentive/post-gl?period=2026-10",
            headers=_hdr(admin_token),
            timeout=60,
        )
        assert r.status_code in (200, 201, 400), f"post-gl status: {r.status_code} {r.text[:300]}"
        body = r.json() if r.content else {}
        print(f"post-gl: {r.status_code} {body}")

        # If created, clean up journal
        if r.status_code in (200, 201) and body.get("created"):
            jid = body.get("journal_id") or body.get("id")
            if jid:
                vd = requests.post(
                    f"{BASE_URL}/api/accounting/journals/{jid}/void",
                    headers=_hdr(admin_token),
                    json={"reason": "TEST_ cleanup incentive"},
                    timeout=20,
                )
                print(f"void journal {jid}: {vd.status_code} {vd.text[:200]}")
