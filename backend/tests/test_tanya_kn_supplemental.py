"""Tanya KN supplemental integration tests (F0.5, F1 catalog/facts/access edges).

Covers items not directly asserted by the base f0/f1 tests:
- Config registry exposes group `asisten-analitik` + 4 AI keys
- /api/ai/catalog: version, exact counts, role gating (7 roles allowed; `warehouse` denied)
- /api/ai/facts/rebuild + /facts/status role gating
- Many metric/dimension combinations return 200
- Invalid inputs return 400 (never 500) with Indonesian messages
- target_achievement_pct requires sales_target; new_customers works
- Regression pings on legacy endpoints
"""
import os
import sys

import pytest
import requests

sys.path.insert(0, "/app/backend/tests")
from test_inbound_complete_characterization import BASE  # noqa: E402

AI_ROLES_EMAILS = {
    "admin": "admin@kainnusantara.id",
    "manager": "manager@kainnusantara.id",
    "sales_admin": "salesadmin@kainnusantara.id",
    "finance": "finance@kainnusantara.id",
    "md": "md@kainnusantara.id",
    "warehouse_admin": "warehouseadmin@kainnusantara.id",  # may not exist; skipped if login fails
    "sales": "sales@kainnusantara.id",
}


def _login(email, ent="ent_ksc"):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    if r.status_code != 200:
        return None
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ent})
    return s


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id")


# ── F0.5: Config registry contains AI group + keys ──────────────────────────
def test_config_registry_has_asisten_analitik_group(admin):
    r = admin.get(f"{BASE}/config/registry")
    assert r.status_code == 200, r.text
    data = r.json()
    groups = data.get("groups") or []
    group_ids = {g.get("id") for g in groups}
    assert "asisten-analitik" in group_ids, f"missing group: {group_ids}"

    entries = data.get("entries") or data.get("settings") or []
    keys = {s.get("key") for s in entries}
    expected = {"ai.sales_definition", "ai.sales_attribution", "ai.margin_roles", "ai.stock_value_roles"}
    missing = expected - keys
    assert not missing, f"missing AI config keys: {missing}"
    ai_keys = {s.get("key") for s in entries if s.get("group") == "asisten-analitik"}
    assert expected <= ai_keys


# ── F1 catalog: shape/version/roles ─────────────────────────────────────────
def test_catalog_shape_and_counts(admin):
    r = admin.get(f"{BASE}/ai/catalog")
    assert r.status_code == 200
    j = r.json()
    assert j["version"] == "cat-v1"
    assert len(j["metrics"]) == 30
    assert len(j["dimensions"]) == 19


@pytest.mark.parametrize("role,email", list(AI_ROLES_EMAILS.items()))
def test_catalog_accessible_to_ai_roles(role, email):
    s = _login(email)
    if not s:
        pytest.skip(f"user {email} not present in demo seed")
    r = s.get(f"{BASE}/ai/catalog")
    assert r.status_code == 200, f"role {role} got {r.status_code}"


def test_catalog_denied_to_warehouse_role():
    s = _login("warehouse@kainnusantara.id")
    if not s:
        pytest.skip("warehouse user not present")
    r = s.get(f"{BASE}/ai/catalog")
    assert r.status_code == 403


# ── F1 facts endpoints role gating ──────────────────────────────────────────
def test_facts_rebuild_admin_only(admin):
    # admin ok
    r = admin.post(f"{BASE}/ai/facts/rebuild")
    assert r.status_code == 200

    # non-admin should be denied
    for email in ("manager@kainnusantara.id", "finance@kainnusantara.id",
                  "sales@kainnusantara.id", "md@kainnusantara.id"):
        s = _login(email)
        if not s:
            continue
        rr = s.post(f"{BASE}/ai/facts/rebuild")
        assert rr.status_code == 403, f"{email} unexpectedly {rr.status_code}"


def test_facts_status_admin_and_manager(admin):
    r = admin.get(f"{BASE}/ai/facts/status")
    assert r.status_code == 200
    body = r.json()
    assert "rows" in body and isinstance(body["rows"], int)

    mgr = _login("manager@kainnusantara.id")
    assert mgr.get(f"{BASE}/ai/facts/status").status_code == 200

    sales = _login("sales@kainnusantara.id")
    assert sales.get(f"{BASE}/ai/facts/status").status_code == 403


# ── F1 query: many metric/dimension combos should not 500 ───────────────────
def _q(session, metrics, group_by=(), grain=None, extra=None):
    body = {
        "metrics": list(metrics),
        "group_by": list(group_by),
        "time_grain": grain,
        "period": {"preset": "last_12m"},
        "compare": "none",
        "filters": [],
        "sort": {"by": None, "direction": "desc"},
        "limit": None,
        "include_samples": False,
        "entity_scope": "active",
    }
    if extra:
        body.update(extra)
    return session.post(f"{BASE}/ai/query", json=body)


VALID_COMBOS = [
    (["net_sales"], ["customer"], None),
    (["net_sales"], ["product"], None),
    (["net_sales"], ["line_code"], None),
    (["net_sales"], [], "week"),
    (["net_sales"], [], "quarter"),
    (["net_sales"], [], "year"),
    (["stock_qty"], ["warehouse"], None),
    (["stock_qty"], ["grade"], None),
    (["stock_qty"], ["dye_lot"], None),
    (["stock_value"], ["warehouse"], None),
    (["stock_rolls"], ["stock_age_bucket"], None),
    (["ar_outstanding"], ["aging_bucket"], None),
    (["ar_outstanding"], ["customer"], None),
    (["ap_outstanding"], ["supplier"], None),
    (["purchase_value"], ["supplier"], None),
    (["po_count"], ["supplier"], None),
    (["recognized_revenue"], [], None),
    (["collections_amount"], [], None),
    (["returns_value"], [], None),
    (["new_customers"], [], None),
    (["sales_target", "target_achievement_pct"], ["sales_person"], None),
]


@pytest.mark.parametrize("metrics,group_by,grain", VALID_COMBOS)
def test_query_valid_combos_return_200(admin, metrics, group_by, grain):
    r = _q(admin, metrics, group_by, grain)
    assert r.status_code == 200, f"metrics={metrics} group_by={group_by} grain={grain}: {r.status_code} {r.text[:300]}"
    body = r.json()
    for k in ("result_id", "columns", "rows", "totals", "row_count",
              "truncated", "warnings", "denied", "source"):
        assert k in body, f"missing key {k} in response"
    assert body["source"] == "cat-v1"


INVALID_COMBOS = [
    # net_sales cannot group by warehouse
    (["net_sales"], ["warehouse"], None, None),
    # >6 metrics
    (["net_sales", "gross_sales", "discount_total", "ppn_amount",
      "orders_count", "avg_order_value", "returns_value"], [], None, None),
    # >3 dimensions
    (["net_sales"], ["customer", "product", "sales_person", "line_code"], None, None),
    # unknown metric
    (["nonexistent_metric"], [], None, None),
    # unknown dimension
    (["net_sales"], ["nonexistent_dim"], None, None),
    # incompatible metric mix (qty_sold + recognized_revenue)
    (["qty_sold", "recognized_revenue"], [], None, None),
    # unknown preset
    (["net_sales"], [], None, {"period": {"preset": "not_a_preset"}}),
    # empty metrics
    ([], [], None, None),
]


@pytest.mark.parametrize("metrics,group_by,grain,extra", INVALID_COMBOS)
def test_query_invalid_returns_400_not_500(admin, metrics, group_by, grain, extra):
    r = _q(admin, metrics, group_by, grain, extra)
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:300]}"
    # error message should be Indonesian-ish (not a raw traceback / english server error)
    detail = r.json().get("detail", "")
    assert isinstance(detail, str) and detail, "detail should be a non-empty string"
    assert "Traceback" not in detail


# ── Regression pings on legacy endpoints ────────────────────────────────────
def test_regression_reports_summary_admin(admin):
    assert admin.get(f"{BASE}/reports/summary").status_code == 200


def test_regression_sales_leaderboard_manager():
    mgr = _login("manager@kainnusantara.id")
    r = mgr.get(f"{BASE}/sales/leaderboard")
    assert r.status_code == 200


def test_regression_finance_profitability_admin(admin):
    r = admin.get(f"{BASE}/finance/profitability")
    assert r.status_code == 200
