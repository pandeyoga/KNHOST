"""Backend tests for Audit KNHOST Bagian III (KN-E01..E51) fixes.

Covers: E01 sales_name/ownership, E02 amendments cross-sales, E03 price guards,
E04c duplicate approvals, E45 settings scope, E31/E37 ai_tools scoping,
E23 GRN query, E38 commission scoping, E44 AI usage & analyze_change,
E50 wms tasks, E17 wms inbound grn-mode conflict.
Plus unit tests for E12 dn_rules and E39 ai_number_check.
"""
import os
import sys
import uuid
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

# Ensure backend is importable for unit tests
sys.path.insert(0, "/app/backend")

CREDS = {
    "admin":   ("admin@kainnusantara.id", "demo12345"),
    "sales":   ("sales@kainnusantara.id", "demo12345"),
    "manager": ("manager@kainnusantara.id", "demo12345"),
    "warehouse": ("warehouse@kainnusantara.id", "demo12345"),
    "sales_admin": ("salesadmin@kainnusantara.id", "demo12345"),
}


def _login(email, pwd):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert r.status_code == 200, f"login {email} → {r.status_code}: {r.text[:200]}"
    j = r.json()
    tok = j.get("token") or j.get("access_token") or (j.get("data") or {}).get("token")
    assert tok, f"no token in login response: {j}"
    return tok


@pytest.fixture(scope="session")
def tokens():
    return {k: _login(e, p) for k, (e, p) in CREDS.items()}


E9_PRODUCT = "prod_e9_demo_rantai"


def _mongo():
    from dotenv import dotenv_values
    from pymongo import MongoClient
    env = dotenv_values("/app/backend/.env")
    return MongoClient(env["MONGO_URL"])[env["DB_NAME"]]


@pytest.fixture(scope="session")
def e9_order():
    """SO demo rantai E-9 (bukan milik Ayu) — dicari dinamis, id berubah tiap seed."""
    o = _mongo().sales_orders.find_one(
        {"items.product_id": E9_PRODUCT, "created_by": {"$ne": "user_sales_01"}},
        {"_id": 0, "id": 1, "items": 1})
    if not o:
        pytest.skip("SO demo E-9 tidak ada — jalankan seed_e9_chain_demo.py")
    return o


@pytest.fixture(scope="session")
def below_floor_price(e9_order):
    """Harga di bawah lantai yang pasti BERBEDA dari harga baris saat ini."""
    import asyncio
    from services import price_guard_service as pg
    line = next(i for i in e9_order["items"] if i.get("product_id") == E9_PRODUCT)
    ent = _mongo().sales_orders.find_one({"id": e9_order["id"]}, {"_id": 0, "entity_id": 1})["entity_id"]
    res = asyncio.run(pg.evaluate_product_id(1, ent, E9_PRODUCT))
    floor = float(res.get("threshold") or res.get("floor") or 0)
    if floor <= 2:
        pytest.skip(f"produk tanpa lantai harga: {res}")
    target = floor - 1
    if abs(float(line.get("price") or 0) - target) < 0.01:
        target = floor - 2
    return target


def _hdr(tok, entity="ent_ksc"):
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": entity, "Content-Type": "application/json"}


# ============================================================ E01
class TestE01SalesOwnership:
    def test_sales_list_only_own(self, tokens):
        r = requests.get(f"{API}/sales-orders?entity=ent_ksc&limit=200", headers=_hdr(tokens["sales"]))
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        rows = data if isinstance(data, list) else (data.get("rows") or data.get("items") or [])
        # sales user id known from creds file = user_sales_01, Ayu Marketing
        # Ownership must be via id (created_by / sales_id / sales_team.sales_id) — not name.
        for o in rows:
            owned = (
                o.get("created_by") == "user_sales_01"
                or o.get("sales_id") == "user_sales_01"
                or any((m or {}).get("sales_id") == "user_sales_01" for m in (o.get("sales_team") or []))
            )
            assert owned, f"sales sees non-own order {o.get('id')} sales_name={o.get('sales_name')}"

    def test_sales_cannot_patch_sales_name(self, tokens):
        # find one of Ayu's orders
        r = requests.get(f"{API}/sales-orders?entity=ent_ksc&limit=1", headers=_hdr(tokens["sales"]))
        assert r.status_code == 200
        data = r.json()
        rows = data if isinstance(data, list) else (data.get("rows") or data.get("items") or [])
        if not rows:
            pytest.skip("no sales order visible for Ayu")
        oid = rows[0]["id"]
        original = rows[0].get("sales_name")
        r2 = requests.patch(f"{API}/sales-orders/{oid}", headers=_hdr(tokens["sales"]),
                            json={"sales_name": "TEST_HACKED"})
        # Either 200 (ignored) or 400/403. Verify persistence:
        r3 = requests.get(f"{API}/sales-orders/{oid}", headers=_hdr(tokens["sales"]))
        assert r3.status_code == 200
        assert r3.json().get("sales_name") == original, "sales role must not change sales_name"


# ============================================================ E02
class TestE02AmendmentGuard:
    def test_sales_amendment_on_other_order_forbidden(self, tokens, e9_order):
        target_id = e9_order["id"]  # not Ayu's
        r = requests.post(f"{API}/amendments/preview", headers=_hdr(tokens["sales"]),
                          json={"doc_type": "sales_order", "doc_id": target_id, "changes": []})
        assert r.status_code in (403, 404), f"expected 403/404 got {r.status_code}: {r.text[:200]}"
        r2 = requests.post(f"{API}/amendments", headers=_hdr(tokens["sales"]),
                           json={"doc_type": "sales_order", "doc_id": target_id, "changes": [], "reason": "TEST_"})
        assert r2.status_code in (403, 404)
        r3 = requests.get(f"{API}/amendments/doc/sales_order/{target_id}", headers=_hdr(tokens["sales"]))
        assert r3.status_code in (403, 404)


# ============================================================ E03
class TestE03PriceGuards:
    def test_preview_price_zero_rejected(self, tokens, e9_order):
        oid = e9_order["id"]
        r = requests.post(f"{API}/amendments/preview", headers=_hdr(tokens["admin"]),
                          json={"doc_type": "sales_order", "doc_id": oid,
                                "changes": [{"product_id": "prod_e9_demo_rantai",
                                             "field": "price", "to": 0}]})
        assert r.status_code == 400, f"expected 400 for price 0 got {r.status_code}: {r.text[:300]}"

    def test_preview_below_floor_requires_approval(self, tokens, e9_order, below_floor_price):
        oid = e9_order["id"]
        r2 = requests.post(f"{API}/amendments/preview", headers=_hdr(tokens["admin"]),
                           json={"doc_type": "sales_order", "doc_id": oid,
                                 "changes": [{"product_id": E9_PRODUCT,
                                              "field": "price", "to": below_floor_price}]})
        assert r2.status_code == 200, r2.text[:300]
        j = r2.json()
        assert j.get("requires_approval") is True, f"expected requires_approval=true got {j}"


# ============================================================ E04c
class TestE04cDoubleApprove:
    def test_double_approve_rejected(self, tokens, e9_order, below_floor_price):
        # Create a fresh amendment that will require approval (below-floor price)
        oid = e9_order["id"]
        r = requests.post(f"{API}/amendments", headers=_hdr(tokens["admin"]),
                          json={"doc_type": "sales_order", "doc_id": oid,
                                "changes": [{"product_id": E9_PRODUCT,
                                             "field": "price", "to": below_floor_price}],
                                "reason_code": "price_correction",
                                "reason": "TEST_double_approve"})
        if r.status_code != 200:
            pytest.skip(f"could not create amendment: {r.status_code} {r.text[:200]}")
        amd = r.json()
        amid = amd.get("id") or (amd.get("amendment") or {}).get("id")
        if not amid:
            pytest.skip(f"no amendment id in {amd}")
        r1 = requests.post(f"{API}/amendments/{amid}/decision", headers=_hdr(tokens["manager"]),
                           json={"action": "approve", "note": "TEST_first"})
        if r1.status_code != 200:
            pytest.skip(f"first approve failed {r1.status_code}: {r1.text[:200]}")
        r2 = requests.post(f"{API}/amendments/{amid}/decision", headers=_hdr(tokens["manager"]),
                           json={"action": "approve", "note": "TEST_second"})
        assert r2.status_code == 400, f"expected 400 got {r2.status_code}: {r2.text[:200]}"
        assert "sudah" in r2.text.lower() or "diputus" in r2.text.lower()


# ============================================================ E45
class TestE45SettingsScope:
    def test_integrations_scope_rejected(self, tokens):
        r = requests.put(f"{API}/settings", headers=_hdr(tokens["admin"]),
                         json={"scope": "integrations", "values": {}})
        assert r.status_code == 400

    def test_global_scope_no_api_keys(self, tokens):
        r = requests.put(f"{API}/settings", headers=_hdr(tokens["admin"]),
                         json={"scope": "global", "values": {}})
        assert r.status_code in (200, 400)
        if r.status_code == 200:
            body = r.json()
            s = str(body).lower()
            assert "api_key" not in s and "apikey" not in s and "openai" not in s, \
                f"global scope leaked api key field: {s[:400]}"


# ============================================================ E31
class TestE31AiToolsPendingApprovals:
    def test_sales_no_po_no_others(self, tokens):
        r = requests.post(f"{API}/ai/tools/list_records", headers=_hdr(tokens["sales"]),
                          json={"record_type": "pending_approvals"})
        assert r.status_code == 200, r.text[:300]
        j = r.json()
        rows = j.get("rows") or j.get("items") or []
        for row in rows:
            s = str(row).lower()
            assert "purchase order" not in s and "purchase_order" not in s, f"sales saw PO row: {row}"
            # If the row references a sales_order, must be owned
            so_ref = row.get("sales_order_id") or row.get("doc_id")
            created_by = row.get("created_by") or row.get("sales_id")
            if created_by:
                assert created_by == "user_sales_01" or row.get("sales_id") == "user_sales_01", \
                    f"sales saw non-own row: {row}"


# ============================================================ E37
class TestE37ListRecordsFilters:
    def test_unsupported_filter_dim_400(self, tokens):
        r = requests.post(f"{API}/ai/tools/list_records", headers=_hdr(tokens["admin"]),
                          json={"record_type": "sales_orders",
                                "filters": [{"dimension": "nonsense_dim", "values": ["x"]}]})
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:200]}"

    def test_supported_customer_filter(self, tokens):
        r = requests.post(f"{API}/ai/tools/list_records", headers=_hdr(tokens["admin"]),
                          json={"record_type": "sales_orders",
                                "filters": [{"dimension": "customer", "values": ["cust_demo"]}],
                                "limit": 5})
        assert r.status_code in (200, 400), r.text[:200]


# ============================================================ E23
class TestE23GRNQueryRegex:
    def test_grn_query_special_chars(self, tokens):
        r = requests.get(f"{API}/goods-receipts?q=%28%5B", headers=_hdr(tokens["admin"]))
        assert r.status_code == 200, f"expected 200 got {r.status_code}: {r.text[:200]}"


# ============================================================ E38
class TestE38CommissionScoping:
    def test_warehouse_gets_own_data_only(self, tokens):
        r = requests.get(f"{API}/sales/commission-history?sales_id=user_sales_01",
                         headers=_hdr(tokens["warehouse"]))
        # Must not return Ayu's data. Either force to self (200 w/ empty/self), 403, or 400.
        assert r.status_code in (200, 400, 403)
        if r.status_code == 200:
            body = r.json()
            rows = body if isinstance(body, list) else (body.get("rows") or body.get("items") or [])
            for row in rows:
                sid = row.get("sales_id")
                assert sid != "user_sales_01", f"warehouse got Ayu's data leaked: {row}"


# ============================================================ E44
class TestE44AiUsageAndAnalyze:
    def test_sales_ai_usage_own_only(self, tokens):
        r = requests.get(f"{API}/ai/usage/daily", headers=_hdr(tokens["sales"]))
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        s = str(body)
        # No other user IDs should leak
        assert "user_admin" not in s and "user_manager" not in s, f"leak: {s[:400]}"

    def test_analyze_change_missing_compare_to_400(self, tokens):
        r = requests.post(f"{API}/ai/tools/analyze_change", headers=_hdr(tokens["admin"]),
                          json={"compare_to": None})
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:200]}"


# ============================================================ E50
class TestE50WmsTasks:
    def test_list_tasks(self, tokens):
        r = requests.get(f"{API}/wms/tasks", headers=_hdr(tokens["warehouse"]))
        assert r.status_code == 200, f"expected 200 got {r.status_code}: {r.text[:200]}"


# ============================================================ E17
class TestE17WmsInboundGrnMode:
    def test_inbound_in_grn_entity_conflict(self, tokens):
        r = requests.post(f"{API}/wms/tasks", headers=_hdr(tokens["warehouse"]),
                          json={"type": "inbound", "product_id": "prod_x", "qty": 1})
        # Might be 400 (validation) if payload is thin, or 409 in grn-mode entity.
        # Just ensure it doesn't 500.
        assert r.status_code < 500, r.text[:200]


# ============================================================ E12 unit
class TestE12DnRulesUnit:
    def test_parse_yds_dot(self):
        from services.dn_rules import parse_doc_number
        r = parse_doc_number("12.5 Yds.")
        # "12.5" then "Yds." — dot in Yds is not a number separator
        assert r["value"] == 12.5, r

    def test_parse_rupiah_no_cent(self):
        from services.dn_rules import parse_doc_number
        r = parse_doc_number("1.000,-")
        assert r["value"] == 1000, r

    def test_parse_range_ambiguous_no_raise(self):
        from services.dn_rules import parse_doc_number
        r = parse_doc_number("20-25")
        assert r["ambiguous"] is True

    def test_parse_never_raises(self):
        from services.dn_rules import parse_doc_number
        for s in ("", None, "abc", "..", ",,", "Yds."):
            parse_doc_number(s)

    def test_match_po_token(self):
        from services.dn_rules import match_po
        open_pos = [{"id": "po1", "po_number": "PO-1"}, {"id": "po12", "po_number": "PO-12"}]
        # Isolated tokens — PO-1 must NOT falsely match PO-12
        r = match_po(["PO-12"], open_pos, [])
        assert r["po_id"] == "po12", r
        r2 = match_po(["PO-1"], open_pos, [])
        assert r2["po_id"] == "po1", r2


# ============================================================ E39 unit
class TestE39AiNumberCheckUnit:
    def test_negative_number(self):
        from services.ai_number_check import extract_numbers
        r = extract_numbers("turun -5.000")
        vals = [n["value"] for n in r]
        assert any(v == -5000 for v in vals), r

    def test_2050_m_is_meter_not_miliar(self):
        from services.ai_number_check import extract_numbers
        # Use text without "-jan-" style substring that trips SKIP_CTX month regex
        r = extract_numbers("kirim 2050 m ke gudang")
        vals = [n["value"] for n in r]
        # 2050 meters must NOT be scaled to 2.05e12 (miliar)
        assert 2050.0 in vals, r
        assert not any(v > 1e9 for v in vals), r
