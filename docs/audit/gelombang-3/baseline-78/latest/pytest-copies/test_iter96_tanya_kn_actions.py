"""Iter96 — Tanya KN answer→action, insights, forecast/ops, glossary, chat context.

Testing pipeline (backend only for pytest):
- ops_metrics kinds return result_id + rows; sales role forbidden.
- forecast kinds (stock_demand, churn_risk, cashflow) return expected shape.
- propose_action draft_po → confirm creates real PO; confirm again → 409; dismiss on second proposal.
- collection_followup confirm → notification for sales user.
- insights scan RBAC + list; scheduler job registered.
- Config catalog exposes ai.glossary + ai.anomaly_* keys.
- Chat with context: SSE returns events; invalid context ignored.
- Glossary: config PUT then _session_context contains 'KAMUS ISTILAH'; reset.
- Number checker: 'dalam 90 hari terakhir' not flagged.
"""
from __future__ import annotations

import os
import json
import time

import pytest
import requests

def _read_env(key: str) -> str:
    v = os.environ.get(key)
    if v:
        return v
    with open("C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/frontend/.env") as f:
        for line in f:
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError(f"missing env {key}")


BASE_URL = _read_env("REACT_APP_BACKEND_URL").rstrip("/")
ENTITY_ID = "ent_ksc"


def _login(email: str, password: str = "demo12345"):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"Login {email} failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    tok = body.get("token")
    assert tok, "No token"
    return tok, body.get("user") or {}


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}",
            "X-Entity-Id": ENTITY_ID,
            "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def admin_login():
    return _login("admin@kainnusantara.id")


@pytest.fixture(scope="session")
def manager_login():
    return _login("manager@kainnusantara.id")


@pytest.fixture(scope="session")
def sales_login():
    return _login("sales@kainnusantara.id")


@pytest.fixture(scope="session")
def finance_login():
    return _login("finance@kainnusantara.id")


@pytest.fixture(scope="session")
def admin_token(admin_login):
    return admin_login[0]


@pytest.fixture(scope="session")
def manager_token(manager_login):
    return manager_login[0]


@pytest.fixture(scope="session")
def sales_token(sales_login):
    return sales_login[0]


@pytest.fixture(scope="session")
def finance_token(finance_login):
    return finance_login[0]


# ── ops_metrics ─────────────────────────────────────────────────────────────
OPS_KINDS = ["supplier_performance", "receiving_discrepancy",
             "dispatch_speed", "qc_results", "makloon_wip"]


@pytest.mark.parametrize("kind", OPS_KINDS)
def test_ops_metrics_kind(admin_token, kind):
    r = requests.post(f"{BASE_URL}/api/ai/tools/ops_metrics",
                      headers=_headers(admin_token),
                      json={"kind": kind, "period": {"preset": "last_90d"}},
                      timeout=30)
    assert r.status_code == 200, f"{kind} → {r.status_code} {r.text[:300]}"
    d = r.json()
    assert d.get("result_id", "").startswith("r_"), f"{kind} missing result_id: {d}"
    assert isinstance(d.get("rows"), list), f"{kind} rows not list"
    assert isinstance(d.get("columns"), list) and d["columns"], f"{kind} columns empty"


def test_ops_metrics_sales_forbidden(sales_token):
    r = requests.post(f"{BASE_URL}/api/ai/tools/ops_metrics",
                      headers=_headers(sales_token),
                      json={"kind": "supplier_performance"},
                      timeout=15)
    # tool errors are wrapped in 400
    assert r.status_code in (400, 403), f"expected error for sales, got {r.status_code}"
    assert "peran" in r.text.lower() or "tidak tersedia" in r.text.lower()


# ── forecast ────────────────────────────────────────────────────────────────
def test_forecast_stock_demand(admin_token):
    r = requests.post(f"{BASE_URL}/api/ai/tools/forecast",
                      headers=_headers(admin_token),
                      json={"kind": "stock_demand", "horizon_weeks": 6},
                      timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert d.get("result_id", "").startswith("r_")
    rows = d.get("rows") or []
    if rows:
        keys = set(rows[0].keys())
        for k in ("suggested_qty", "days_cover", "product_id", "supplier_id"):
            assert k in keys, f"stock_demand missing {k}: {keys}"


def test_forecast_churn(admin_token):
    r = requests.post(f"{BASE_URL}/api/ai/tools/forecast",
                      headers=_headers(admin_token),
                      json={"kind": "churn_risk"},
                      timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    rows = d.get("rows") or []
    for row in rows:
        rs = row.get("risk_score")
        assert rs is None or 5 <= rs <= 95, f"risk_score {rs} out of 5..95"
        assert "risk" in row


def test_forecast_cashflow(admin_token):
    r = requests.post(f"{BASE_URL}/api/ai/tools/forecast",
                      headers=_headers(admin_token),
                      json={"kind": "cashflow"},
                      timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert "sections" in d, d
    assert "weeks" in d["sections"], d["sections"].keys()


# ── propose_action + confirm/dismiss ────────────────────────────────────────
CREATED_PO_NUMBERS: list = []


def test_propose_draft_po_and_confirm(admin_token):
    # Propose
    r = requests.post(f"{BASE_URL}/api/ai/tools/propose_action",
                      headers=_headers(admin_token),
                      json={"action_type": "draft_po",
                            "items": [{"product_id": "prod_batik_mega",
                                       "quantity": 100, "unit": None}],
                            "reason": "TEST_iter96_smoke"},
                      timeout=30)
    assert r.status_code == 200, r.text[:400]
    p = r.json()
    pid = p.get("proposal_id")
    assert pid and pid.startswith("aiact_"), f"bad pid: {p}"
    assert p.get("action_type") == "draft_po"
    assert p.get("rows"), "no rows"
    # Supplier auto = Cirebon Craft
    row0 = p["rows"][0]
    assert "Cirebon Craft" in (row0.get("supplier") or ""), row0

    # GET by owner
    r2 = requests.get(f"{BASE_URL}/api/ai/actions/{pid}", headers=_headers(admin_token), timeout=15)
    assert r2.status_code == 200
    assert r2.json()["status"] == "pending"

    # Confirm with edits qty=5
    r3 = requests.post(f"{BASE_URL}/api/ai/actions/{pid}/confirm",
                       headers=_headers(admin_token),
                       json={"edits": {"pos": [{"items": [{"quantity": 5}]}]}},
                       timeout=45)
    assert r3.status_code == 200, r3.text[:400]
    d = r3.json()
    assert d["status"] == "confirmed"
    assert isinstance(d.get("result"), list) and d["result"], d
    po_no = d["result"][0]
    CREATED_PO_NUMBERS.append(po_no)
    print(f"TEST_iter96 created PO: {po_no}")

    # Confirming again → 409
    r4 = requests.post(f"{BASE_URL}/api/ai/actions/{pid}/confirm",
                       headers=_headers(admin_token),
                       json={"edits": {}}, timeout=15)
    assert r4.status_code == 409, f"expected 409, got {r4.status_code}: {r4.text[:200]}"


def test_get_action_other_user_404(admin_token, manager_token):
    # create by admin
    r = requests.post(f"{BASE_URL}/api/ai/tools/propose_action",
                      headers=_headers(admin_token),
                      json={"action_type": "draft_po",
                            "items": [{"product_id": "prod_batik_mega", "quantity": 10}],
                            "reason": "TEST_iter96_owner_check"},
                      timeout=20)
    assert r.status_code == 200
    pid = r.json()["proposal_id"]
    # manager (not admin, not owner) → 404
    r2 = requests.get(f"{BASE_URL}/api/ai/actions/{pid}",
                      headers=_headers(manager_token), timeout=10)
    assert r2.status_code == 404, f"expected 404 for other user, got {r2.status_code}"
    # dismiss it as owner (cleanup)
    r3 = requests.post(f"{BASE_URL}/api/ai/actions/{pid}/dismiss",
                       headers=_headers(admin_token), timeout=10)
    assert r3.status_code == 200
    assert r3.json()["status"] == "dismissed"


def test_dismiss_pending(admin_token):
    r = requests.post(f"{BASE_URL}/api/ai/tools/propose_action",
                      headers=_headers(admin_token),
                      json={"action_type": "draft_po",
                            "items": [{"product_id": "prod_batik_mega", "quantity": 10}],
                            "reason": "TEST_iter96_dismiss"},
                      timeout=20)
    assert r.status_code == 200
    pid = r.json()["proposal_id"]
    r2 = requests.post(f"{BASE_URL}/api/ai/actions/{pid}/dismiss",
                       headers=_headers(admin_token), timeout=10)
    assert r2.status_code == 200
    assert r2.json()["status"] == "dismissed"


def test_collection_followup_notifies_sales(admin_token, sales_login):
    sales_token, sales_user = sales_login
    sales_id = sales_user["id"]

    r = requests.post(f"{BASE_URL}/api/ai/tools/propose_action",
                      headers=_headers(admin_token),
                      json={"action_type": "collection_followup",
                            "reason": "TEST_iter96_ar_reminder"},
                      timeout=20)
    if r.status_code != 200:
        pytest.skip(f"No overdue AR to reminders: {r.text[:200]}")
    pid = r.json()["proposal_id"]
    r2 = requests.post(f"{BASE_URL}/api/ai/actions/{pid}/confirm",
                       headers=_headers(admin_token), json={}, timeout=30)
    assert r2.status_code == 200, r2.text[:300]
    d = r2.json()
    assert d["status"] == "confirmed"

    # Verify sales sees a notification of type ai_followup
    time.sleep(1)
    nr = requests.get(f"{BASE_URL}/api/notifications?limit=30",
                      headers=_headers(sales_token), timeout=10)
    assert nr.status_code == 200
    items = nr.json() if isinstance(nr.json(), list) else nr.json().get("items", [])
    types = {(x.get("type") or x.get("notif_type")) for x in items}
    assert "ai_followup" in types, f"ai_followup not found. types={types}"


# ── insights ────────────────────────────────────────────────────────────────
def test_insights_scan_admin(admin_token):
    r = requests.post(f"{BASE_URL}/api/ai/insights/scan",
                      headers=_headers(admin_token), timeout=60)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    for k in ("entities", "insights", "notified"):
        assert k in d, d


def test_insights_scan_sales_403(sales_token):
    r = requests.post(f"{BASE_URL}/api/ai/insights/scan",
                      headers=_headers(sales_token), timeout=15)
    assert r.status_code == 403


def test_insights_list_has_ar_and_po(admin_token):
    r = requests.get(f"{BASE_URL}/api/ai/insights", headers=_headers(admin_token), timeout=15)
    assert r.status_code == 200
    ins = r.json()
    kinds = {(i.get("kind"), i.get("entity_id")) for i in ins}
    assert ("ar_overdue", "ent_ksc") in kinds or any(k == "ar_overdue" for k, _ in kinds), \
        f"missing ar_overdue for ent_ksc; got={kinds}"
    assert ("po_late", "ent_ksc") in kinds or any(k == "po_late" for k, _ in kinds), \
        f"missing po_late for ent_ksc; got={kinds}"


def test_insights_sales_audience_filter(sales_login):
    sales_token, sales_user = sales_login
    r = requests.get(f"{BASE_URL}/api/ai/insights", headers=_headers(sales_token), timeout=15)
    assert r.status_code == 200
    sid = sales_user["id"]
    role = sales_user.get("role", "sales")
    for i in r.json():
        aud_roles = i.get("audience_roles") or []
        aud_users = i.get("audience_users") or []
        assert role in aud_roles or sid in aud_users, \
            f"insight {i.get('id')} leaked to sales: roles={aud_roles} users={aud_users}"


def test_scheduler_job_registered(admin_token):
    r = requests.get(f"{BASE_URL}/api/scheduler/jobs", headers=_headers(admin_token), timeout=10)
    assert r.status_code == 200, r.text[:200]
    jobs = r.json() if isinstance(r.json(), list) else r.json().get("jobs", [])
    ids = {(j.get("id") or j.get("job_id")) for j in jobs}
    assert "ai_anomaly_scan" in ids, f"ai_anomaly_scan not registered; got={ids}"


def test_config_catalog_has_ai_keys(admin_token):
    r = requests.get(f"{BASE_URL}/api/config/registry", headers=_headers(admin_token), timeout=15)
    assert r.status_code == 200
    body = r.json()
    entries = body.get("entries") or []
    keys = {e.get("key") for e in entries}
    for k in ("ai.glossary", "ai.anomaly_enabled", "ai.anomaly_drop_pct", "ai.anomaly_cover_days"):
        assert k in keys, f"missing config key {k}"


# ── chat with context (limited real calls) ──────────────────────────────────
def _sse_events(resp) -> list:
    events = []
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        try:
            events.append(json.loads(line[5:].strip()))
        except Exception:
            pass
    return events


def test_chat_with_customer_context(admin_token):
    payload = {"question": "Ringkas 1 kalimat: siapa pelanggan ini?",
               "context": {"type": "customer", "id": "cust_toko_kain",
                           "label": "Toko Kain Sejahtera"}}
    r = requests.post(f"{BASE_URL}/api/ai/chat", headers=_headers(admin_token),
                      json=payload, stream=True, timeout=90)
    assert r.status_code == 200
    events = _sse_events(r)
    assert events, "no SSE events"
    types = {e.get("type") for e in events}
    assert "done" in types, f"no done event; types={types}"
    # session created
    sid = next((e.get("session_id") for e in events if e.get("session_id")), None)
    if sid:
        sr = requests.get(f"{BASE_URL}/api/ai/sessions/{sid}",
                          headers=_headers(admin_token), timeout=10)
        if sr.status_code == 200:
            body = sr.json()
            found = False
            for t in body.get("turns", []):
                if (t.get("context") or {}).get("id") == "cust_toko_kain":
                    found = True
                    break
            assert found or body.get("context", {}).get("id") == "cust_toko_kain", \
                "context not stored on turn"


def test_chat_invalid_context_ignored(admin_token):
    payload = {"question": "Halo",
               "context": {"type": "not_a_thing", "id": "xxx"}}
    r = requests.post(f"{BASE_URL}/api/ai/chat", headers=_headers(admin_token),
                      json=payload, stream=True, timeout=60)
    assert r.status_code == 200
    ev = _sse_events(r)
    assert any(e.get("type") == "done" for e in ev), "no done event with invalid context"


# ── glossary ────────────────────────────────────────────────────────────────
def test_glossary_session_context(admin_token):
    # set
    r = requests.put(f"{BASE_URL}/api/config/values", headers=_headers(admin_token),
                     json={"items": [{"key": "ai.glossary",
                                      "value": "bon = piutang pelanggan",
                                      "scope_type": "global", "reason": "uji"}]},
                     timeout=15)
    assert r.status_code in (200, 204), r.text[:300]
    try:
        import sys, asyncio
        sys.path.insert(0, "C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend")
        from services import ai_chat_service as chs  # type: ignore
        user = {"id": "user_admin_01", "role": "admin", "name": "AdminTest",
                "allowed_line_codes": []}
        class _Ctx:
            allowed_entity_ids = ["ent_ksc"]
            active_entity_id = "ent_ksc"
            view_all = False
        fn = getattr(chs, "_session_context", None)
        if fn is None:
            pytest.skip("_session_context not exposed")
        loop = asyncio.new_event_loop()
        try:
            out = loop.run_until_complete(fn(user, _Ctx()))
        finally:
            loop.close()
        assert "KAMUS ISTILAH" in (out or ""), f"'KAMUS ISTILAH' not in session_context: {out!r}"
    finally:
        # reset
        rr = requests.put(f"{BASE_URL}/api/config/values", headers=_headers(admin_token),
                         json={"items": [{"key": "ai.glossary", "value": "",
                                          "scope_type": "global", "reason": "reset iter96"}]},
                         timeout=15)
        assert rr.status_code in (200, 204)


# ── number checker ──────────────────────────────────────────────────────────
def test_number_check_90_days_not_flagged():
    import sys
    sys.path.insert(0, "C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend")
    from services.ai_number_check import verify  # type: ignore
    text = "Total penjualan meningkat 10% dalam 90 hari terakhir."
    out = verify(text, [])
    unverified = out.get("unverified") or out.get("issues") or []
    joined = " ".join(str(u) for u in unverified)
    assert "90 hari" not in joined, f"'90 hari terakhir' still flagged: {out}"


# ── cleanup — cancel any POs created by confirm ─────────────────────────────
def test_zz_cleanup_created_pos(admin_token):
    if not CREATED_PO_NUMBERS:
        pytest.skip("no PO created")
    for po_no in CREATED_PO_NUMBERS:
        # find PO by number
        rr = requests.get(f"{BASE_URL}/api/purchase-orders?q={po_no}",
                          headers=_headers(admin_token), timeout=15)
        if rr.status_code != 200:
            continue
        pos = rr.json() if isinstance(rr.json(), list) else rr.json().get("items", [])
        for po in pos:
            if po.get("po_number") == po_no or po.get("number") == po_no:
                pid = po.get("id")
                if not pid:
                    continue
                cr = requests.post(f"{BASE_URL}/api/purchase-orders/{pid}/cancel",
                                   headers=_headers(admin_token),
                                   json={"reason": "cleanup iter96 test"},
                                   timeout=15)
                print(f"cancel PO {po_no} → {cr.status_code}")
                break
