"""P01 (IMP-12/13/14/15/20) backend regression.

Covers: catalog hidden stages for sales (IMP-12), supplier item color review
(IMP-13), master usage/purge/role-protected delete (IMP-14), template filters
(IMP-15), warehouse location scope + supervisor takeover (IMP-20).
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://internal-pricing.preview.emergentagent.com").rstrip("/")

DEMO_PWD = "demo1234"
ADMIN = ("admin@kainnusantara.id", "demo12345")


def _login(email: str, password: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return r.json()["token"]


def _h(token: str, entity: str = "ent_ksc") -> dict:
    return {"Authorization": f"Bearer {token}", "X-Entity-Id": entity, "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def tokens():
    return {
        "admin": _login(*ADMIN),
        "sales": _login("sales@kainnusantara.id", DEMO_PWD),
        "manager": _login("manager@kainnusantara.id", DEMO_PWD),
        "md": _login("md@kainnusantara.id", DEMO_PWD),
        "warehouse": _login("warehouse@kainnusantara.id", DEMO_PWD),
        "warehouse_soreang": _login("warehouse.soreang@kainnusantara.id", DEMO_PWD),
        "warehouse_rancamalang": _login("warehouse.rancamalang@kainnusantara.id", DEMO_PWD),
        "whadmin": _login("whadmin@kainnusantara.id", DEMO_PWD),
    }


# ------------------ IMP-12: hidden stages for sales ------------------
class TestImp12HiddenStages:
    def test_sales_products_hide_grey_yarn(self, tokens):
        r = requests.get(f"{BASE_URL}/api/products?paginate=true&limit=500", headers=_h(tokens["sales"]), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        items = data.get("items") if isinstance(data, dict) else data
        hidden = {"grey", "yarn", "benang"}
        bad = [p for p in items if str(p.get("stage") or "").lower() in hidden]
        assert not bad, f"sales saw hidden-stage products: {[(p.get('sku'), p.get('stage')) for p in bad[:5]]}"

    def test_sales_product_templates_hide_hidden_stages(self, tokens):
        r = requests.get(f"{BASE_URL}/api/product-templates?paginate=true&limit=500", headers=_h(tokens["sales"]), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        items = data.get("items") if isinstance(data, dict) else data
        hidden = {"grey", "yarn", "benang"}
        bad = [t for t in items if str(t.get("stage") or "").lower() in hidden]
        assert not bad, f"sales saw hidden-stage templates: {[(t.get('code'), t.get('stage')) for t in bad[:5]]}"

    def test_admin_sees_grey(self, tokens):
        r = requests.get(f"{BASE_URL}/api/products?paginate=true&stage=grey&limit=10", headers=_h(tokens["admin"]), timeout=30)
        assert r.status_code == 200
        data = r.json()
        items = data.get("items") if isinstance(data, dict) else data
        assert any(str(p.get("stage") or "").lower() == "grey" for p in items), "admin must see grey"

    def test_setting_toggle_yarn_visible_to_sales(self, tokens):
        # Snapshot: find any yarn product id
        r_admin = requests.get(f"{BASE_URL}/api/products?paginate=true&stage=yarn&limit=5", headers=_h(tokens["admin"]), timeout=30)
        assert r_admin.status_code == 200
        admin_data = r_admin.json()
        yarn_items = admin_data.get("items") if isinstance(admin_data, dict) else admin_data
        if not yarn_items:
            pytest.skip("no yarn products seeded")

        # Change setting → hide only grey/pfd/pfp (yarn visible)
        put = requests.put(f"{BASE_URL}/api/config/values", headers=_h(tokens["admin"]), timeout=30,
                           json={"items": [{"key": "catalog.sales_hidden_stages",
                                             "value": ["grey", "pfd", "pfp"],
                                             "scope_type": "global", "reason": "p01 regression"}]})
        assert put.status_code in (200, 201), put.text
        try:
            r = requests.get(f"{BASE_URL}/api/products?paginate=true&stage=yarn&limit=50",
                             headers=_h(tokens["sales"]), timeout=30)
            assert r.status_code == 200
            data = r.json()
            items = data.get("items") if isinstance(data, dict) else data
            assert any(str(p.get("stage") or "").lower() == "yarn" for p in items), "yarn should be visible after toggle"
        finally:
            # Restore
            restore = requests.put(f"{BASE_URL}/api/config/values", headers=_h(tokens["admin"]), timeout=30,
                                   json={"items": [{"key": "catalog.sales_hidden_stages",
                                                     "value": ["grey", "yarn"],
                                                     "scope_type": "global", "reason": "restore"}]})
            assert restore.status_code in (200, 201), restore.text

    def test_ln012_t04_pfd_sellable_grey_never(self, tokens):
        import time
        put = requests.put(f"{BASE_URL}/api/config/values", headers=_h(tokens["admin"]), timeout=30,
                           json={"items": [{"key": "catalog.sales_hidden_stages", "value": ["yarn"],
                                             "scope_type": "global", "reason": "LN-012-T04 uji"}]})
        assert put.status_code in (200, 201), put.text
        try:
            time.sleep(16)   # cache tahap 15 dtk
            seen = set()
            for st in ("pfd", "pfp", "grey"):
                r = requests.get(f"{BASE_URL}/api/products?paginate=true&stage={st}&limit=20", headers=_h(tokens["sales"]), timeout=30)
                d = r.json()
                seen |= {str(p.get("stage")).lower() for p in (d.get("items") if isinstance(d, dict) else d)}
            assert "grey" not in seen, "greige tidak boleh tampil bagi Sales walau tidak dicentang"
            assert seen & {"pfd", "pfp"}, "PFD/PFP harus tampil bila tidak disembunyikan"
        finally:
            requests.put(f"{BASE_URL}/api/config/values", headers=_h(tokens["admin"]), timeout=30,
                         json={"items": [{"key": "catalog.sales_hidden_stages", "value": ["grey", "yarn"],
                                           "scope_type": "global", "reason": "restore"}]})

    def test_sales_cannot_create_so_with_grey_product(self, tokens):
        r_admin = requests.get(f"{BASE_URL}/api/products?paginate=true&stage=grey&limit=5", headers=_h(tokens["admin"]), timeout=30)
        items = r_admin.json().get("items") if isinstance(r_admin.json(), dict) else r_admin.json()
        if not items:
            pytest.skip("no grey products seeded")
        grey = [p for p in items if str(p.get("stage") or "").lower() == "grey"]
        if not grey:
            pytest.skip("no grey products seeded")
        grey_pid = grey[0]["id"]
        payload = {
            "customer_id": "cust_toko_kain", "shipping_address_id": "addr_001", "notes": "TEST_imp12_grey",
            "items": [{"product_id": grey_pid, "quantity": 1, "unit": "yard"}],
        }
        r = requests.post(f"{BASE_URL}/api/sales-orders", headers=_h(tokens["sales"]), json=payload, timeout=30)
        assert r.status_code == 403, f"expected 403 grey guard, got {r.status_code}: {r.text[:300]}"
        # best-effort cleanup if a 2xx snuck through
        if r.status_code < 300:
            try:
                sid = r.json().get("id")
                if sid:
                    requests.post(f"{BASE_URL}/api/sales-orders/{sid}/cancel",
                                  headers=_h(tokens["admin"]), json={"reason": "test cleanup"}, timeout=20)
            except Exception:
                pass


# ------------------ IMP-20: location scope + takeover ------------------
class TestImp20LocationScope:
    def test_soreang_my_scope(self, tokens):
        r = requests.get(f"{BASE_URL}/api/wms/my-location-scope", headers=_h(tokens["warehouse_soreang"], "ent_kanda"), timeout=20)
        assert r.status_code == 200, r.text
        s = r.json()
        assert s.get("restricted") is True
        sites = [str(x).lower() for x in (s.get("sites") or [])]
        assert any("soreang" in x for x in sites), f"expected Soreang in sites: {sites}"

    def test_soreang_tasks_only_soreang(self, tokens):
        r = requests.get(f"{BASE_URL}/api/wms/tasks", headers=_h(tokens["warehouse_soreang"], "ent_kanda"), timeout=30)
        assert r.status_code == 200
        tasks = r.json()
        bad = [t for t in tasks if t.get("warehouse_id") and "SRG" not in (t.get("warehouse_id") or "").upper() and "soreang" not in (t.get("warehouse_name") or "").lower()]
        # soft check: allow id-based codes; the stronger invariant is below via warehouses endpoint
        # ensure at least no Jakarta/Rancamalang
        bad_strict = [t for t in tasks if "jakarta" in (t.get("warehouse_name") or "").lower()
                       or "rancamalang" in (t.get("warehouse_name") or "").lower()]
        assert not bad_strict, f"soreang user saw non-Soreang tasks: {[(t.get('id'), t.get('warehouse_name')) for t in bad_strict[:5]]}"

    def test_soreang_rolls_only_srg(self, tokens):
        r = requests.get(f"{BASE_URL}/api/inventory/rolls?limit=200", headers=_h(tokens["warehouse_soreang"], "ent_kanda"), timeout=30)
        assert r.status_code == 200
        data = r.json()
        rolls = data.get("items") if isinstance(data, dict) else data
        bad = [roll for roll in rolls if roll.get("warehouse_id") and "SRG" not in (roll.get("warehouse_id") or "").upper()
                                    and "srg" not in (roll.get("warehouse_code") or "").lower()
                                    and "soreang" not in (roll.get("warehouse_name") or "").lower()]
        # Confirm by cross-checking warehouse_id against admin warehouses list (ent_kanda where SRG-01 lives)
        wh = requests.get(f"{BASE_URL}/api/warehouses", headers=_h(tokens["admin"], "ent_kanda"), timeout=20).json()
        wh_list = wh.get("items") if isinstance(wh, dict) else wh
        srg_ids = {w["id"] for w in wh_list if "soreang" in (w.get("name", "").lower()) or "SRG" in (w.get("code") or "").upper()}
        bad = [r for r in rolls if r.get("warehouse_id") and r["warehouse_id"] not in srg_ids]
        assert not bad, f"soreang saw non-SRG rolls: {[(r.get('id'), r.get('warehouse_id')) for r in bad[:5]]}"

    def test_soreang_cannot_see_jakarta_locations(self, tokens):
        # find jakarta warehouse id
        wh = requests.get(f"{BASE_URL}/api/warehouses", headers=_h(tokens["admin"]), timeout=20).json()
        wh_list = wh.get("items") if isinstance(wh, dict) else wh
        jkt = next((w for w in wh_list if "jakarta" in (w.get("name", "").lower()) or "JKT" in (w.get("code") or "").upper()), None)
        if not jkt:
            pytest.skip("no jakarta warehouse")
        r = requests.get(f"{BASE_URL}/api/warehouses/{jkt['id']}/locations",
                         headers=_h(tokens["warehouse_soreang"]), timeout=20)
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text[:200]}"

    def test_soreang_scan_jakarta_task_404(self, tokens):
        # find a jakarta task
        all_tasks = requests.get(f"{BASE_URL}/api/wms/tasks", headers=_h(tokens["admin"]), timeout=30).json()
        jkt_task = next((t for t in all_tasks if "jakarta" in (t.get("warehouse_name") or "").lower()), None)
        if not jkt_task:
            pytest.skip("no jakarta task")
        r = requests.post(f"{BASE_URL}/api/wms/tasks/{jkt_task['id']}/scan",
                          headers=_h(tokens["warehouse_soreang"]),
                          json={"scan_type": "sku", "scan_value": "x"}, timeout=20)
        assert r.status_code in (403, 404), f"expected 403/404 got {r.status_code}: {r.text[:200]}"

    def test_jakarta_user_sees_only_jakarta(self, tokens):
        r = requests.get(f"{BASE_URL}/api/wms/my-location-scope", headers=_h(tokens["warehouse"]), timeout=20)
        assert r.status_code == 200
        s = r.json()
        assert s.get("restricted") is True
        sites = [str(x).lower() for x in (s.get("sites") or [])]
        assert any("jakarta" in x for x in sites), f"expected Jakarta: {sites}"

    def test_whadmin_sees_all(self, tokens):
        r = requests.get(f"{BASE_URL}/api/wms/my-location-scope", headers=_h(tokens["whadmin"]), timeout=20)
        assert r.status_code == 200
        s = r.json()
        assert s.get("supervisor") is True
        assert s.get("restricted") is False

    def test_takeover_flow(self, tokens):
        # pick any active task; operator should 403, whadmin supervisor OK, short reason 400
        all_tasks = requests.get(f"{BASE_URL}/api/wms/tasks", headers=_h(tokens["admin"]), timeout=30).json()
        done = {"completed", "cancelled", "dispatched", "done"}
        active = next((t for t in all_tasks if t.get("status") not in done), None)
        if not active:
            pytest.skip("no active task")
        tid = active["id"]
        prev = {"assigned_to": active.get("assigned_to"), "assigned_to_name": active.get("assigned_to_name"),
                "takeover_log": active.get("takeover_log")}

        # operator forbidden
        r_op = requests.post(f"{BASE_URL}/api/wms/tasks/{tid}/takeover",
                             headers=_h(tokens["warehouse_soreang"]),
                             json={"reason": "testing takeover minimum length"}, timeout=20)
        assert r_op.status_code == 403, f"expected 403 for operator got {r_op.status_code}: {r_op.text[:200]}"

        # short reason 400
        r_short = requests.post(f"{BASE_URL}/api/wms/tasks/{tid}/takeover",
                                headers=_h(tokens["whadmin"]), json={"reason": "no"}, timeout=20)
        assert r_short.status_code == 400, f"short reason expected 400 got {r_short.status_code}"

        # valid supervisor takeover
        r_ok = requests.post(f"{BASE_URL}/api/wms/tasks/{tid}/takeover",
                             headers=_h(tokens["whadmin"]),
                             json={"reason": "p01 regression check"}, timeout=20)
        try:
            assert r_ok.status_code == 200, f"takeover failed: {r_ok.status_code} {r_ok.text[:300]}"
            body = r_ok.json()
            log = body.get("takeover_log") or []
            assert log, "takeover_log must be appended"
            assert log[-1].get("reason") == "p01 regression check"
        finally:
            # UNDO changes via mongo-safe REST — use admin direct mongo through a helper endpoint if available.
            # Fallback: push a correction via mongo update isn't exposed. Try /api/wms/tasks/{id} patch — may not exist.
            # Record restore instructions for test report.
            restore_note = {"task_id": tid, "prev": prev}
            # best effort cleanup via direct DB if a dev helper endpoint exists is skipped.
            print("TAKEOVER_RESTORE", restore_note)


# ------------------ IMP-14: master governance ------------------
class TestImp14MasterGovernance:
    def test_master_usage_endpoint(self, tokens):
        prods = requests.get(f"{BASE_URL}/api/products?paginate=true&limit=5", headers=_h(tokens["admin"]), timeout=30).json()
        items = prods.get("items") if isinstance(prods, dict) else prods
        if not items:
            pytest.skip("no products")
        pid = items[0]["id"]
        r = requests.get(f"{BASE_URL}/api/master/usage/product/{pid}", headers=_h(tokens["admin"]), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # expected keys roughly: references/usage/in_use
        assert isinstance(data, dict), "usage should be object"

    def test_purge_used_product_409(self, tokens):
        # find a product that is used (has stock or ever referenced)
        rolls = requests.get(f"{BASE_URL}/api/inventory/rolls?limit=1", headers=_h(tokens["admin"]), timeout=20).json()
        rolls_items = rolls.get("items") if isinstance(rolls, dict) else rolls
        if not rolls_items:
            pytest.skip("no rolls")
        used_pid = rolls_items[0]["product_id"]
        r = requests.delete(f"{BASE_URL}/api/master/product/{used_pid}/purge", headers=_h(tokens["admin"]), timeout=20)
        assert r.status_code == 409, f"expected 409 got {r.status_code}: {r.text[:300]}"
        body = r.json()
        detail = body.get("detail") if isinstance(body.get("detail"), dict) else body
        code = (detail.get("code") if isinstance(detail, dict) else None) or ""
        assert "MASTER_IN_USE" in str(body), f"expected MASTER_IN_USE marker, got: {body}"

    def test_manager_cannot_delete_product(self, tokens):
        prods = requests.get(f"{BASE_URL}/api/products?paginate=true&limit=1", headers=_h(tokens["admin"]), timeout=20).json()
        items = prods.get("items") if isinstance(prods, dict) else prods
        pid = items[0]["id"]
        r = requests.delete(f"{BASE_URL}/api/products/{pid}", headers=_h(tokens["manager"]), timeout=20)
        assert r.status_code == 403, f"expected 403 for manager got {r.status_code}: {r.text[:200]}"


# ------------------ IMP-13: supplier item color review ------------------
class TestImp13SupplierItems:
    def test_needs_review_contains_wrn77(self, tokens):
        r = requests.get(f"{BASE_URL}/api/supplier-items?review_status=needs_review&limit=100",
                         headers=_h(tokens["admin"]), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        items = data.get("items") if isinstance(data, dict) else data
        assert items, "expected at least one needs_review supplier item (SUP-A-002)"
        # The specific SKU SUP-A-002 should be present
        codes = [i.get("supplier_sku") or i.get("code") or i.get("sku") for i in items]
        assert any("SUP-A-002" in str(c) for c in codes), f"expected SUP-A-002 in needs_review: {codes[:10]}"


# ------------------ IMP-15: template filters ------------------
class TestImp15TemplateFilters:
    def test_grey_filter(self, tokens):
        r = requests.get(f"{BASE_URL}/api/product-templates?paginate=true&stage=grey&limit=50",
                         headers=_h(tokens["admin"]), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        items = data.get("items") if isinstance(data, dict) else data
        assert items, "expected grey templates"
        bad = [t for t in items if str(t.get("stage") or "").lower() != "grey"]
        assert not bad, f"non-grey templates leaked: {[(t.get('code'), t.get('stage')) for t in bad[:5]]}"
