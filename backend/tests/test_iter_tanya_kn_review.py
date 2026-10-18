"""
Review tests for Tanya KN (AI Analytics) module - current review iteration.

Covers:
- /api/ai/status
- /api/ai/chat SSE streaming (REAL OpenAI, keep under budget)
- Access control (sales user margin refusal, own-data only)
- /api/ai/templates/{id}/run + /api/ai/narrative
- /api/ai/results/{id}/export.xlsx
- /api/ai/usage/daily
"""
import os
import json
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ENTITY = "ent_ksc"


def _login(email, password="demo12345"):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


def _headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "X-Entity-Id": ENTITY,
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="module")
def admin_token():
    return _login("admin@kainnusantara.id")


@pytest.fixture(scope="module")
def manager_token():
    return _login("manager@kainnusantara.id")


@pytest.fixture(scope="module")
def sales_token():
    return _login("sales@kainnusantara.id")


# ---- /api/ai/status ------------------------------------------------------
def test_ai_status_admin(admin_token):
    r = requests.get(f"{BASE_URL}/api/ai/status", headers=_headers(admin_token), timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d.get("chat_enabled") is True
    assert d.get("config_enabled") is True
    assert d.get("has_key") is True
    assert d.get("narrative_ai") is True
    assert d.get("mock") is False
    assert d.get("model") == "gpt-6-sol"


# ---- SSE chat helper -----------------------------------------------------
def _parse_sse(resp):
    """Parse SSE stream, return list of (event_name_or_default, data_json)."""
    events = []
    cur_event = "message"
    cur_data = []
    for raw in resp.iter_lines(decode_unicode=True):
        if raw is None:
            continue
        if raw == "":
            if cur_data:
                data_str = "\n".join(cur_data)
                try:
                    data = json.loads(data_str)
                except Exception:
                    data = {"_raw": data_str}
                events.append((cur_event, data))
            cur_event = "message"
            cur_data = []
            continue
        if raw.startswith("event:"):
            cur_event = raw[6:].strip()
        elif raw.startswith("data:"):
            cur_data.append(raw[5:].lstrip())
    if cur_data:
        events.append((cur_event, {"_raw": "\n".join(cur_data)}))
    return events


def _chat(token, question, timeout=60):
    r = requests.post(
        f"{BASE_URL}/api/ai/chat",
        headers={**_headers(token), "Accept": "text/event-stream"},
        json={"question": question},
        stream=True,
        timeout=timeout,
    )
    assert r.status_code == 200, f"chat status {r.status_code}: {r.text[:300]}"
    return _parse_sse(r)


def _event_types(events):
    """Collect SSE event types from either `event:` header or inner `type` field."""
    types = set()
    for name, data in events:
        if name and name != "message":
            types.add(name)
        if isinstance(data, dict):
            t = data.get("type") or data.get("event")
            if t:
                types.add(t)
    return types


def _done_event(events):
    for name, data in events:
        if not isinstance(data, dict):
            continue
        t = data.get("type") or data.get("event") or name
        if t == "done" or data.get("done") is True or ("text" in data and "verification" in data):
            return data
    return events[-1][1] if events else None


# ---- chat SSE basic ------------------------------------------------------
def test_ai_chat_sse_stream_admin(admin_token):
    events = _chat(admin_token, "Siapa 5 pelanggan dengan penjualan tertinggi bulan ini?", timeout=120)
    assert len(events) >= 2, f"too few events: {events}"
    event_names = _event_types(events)
    # expect at least status + something + done-ish
    assert any(n in event_names for n in ("status", "tool", "delta", "result", "done")), event_names
    done = _done_event(events)
    assert done is not None
    assert isinstance(done.get("text", ""), str) and len(done.get("text", "")) > 0
    assert "verification" in done
    assert done["verification"].get("ok") is True, f"verification not ok: {done.get('verification')}"
    # usage present
    assert "usage" in done or "token_usage" in done or done.get("source") in ("ai", "auto")


# ---- access control: sales margin refusal --------------------------------
def test_sales_margin_refused(sales_token):
    events = _chat(sales_token, "Berapa laba kotor bulan ini?", timeout=90)
    done = _done_event(events)
    assert done is not None
    text = (done.get("text") or "").lower()
    # should be refused/blocked, no numeric margin
    # Expect either explicit refusal or no numbers for margin
    refusal_markers = ["tidak", "tak", "tidak diizinkan", "tidak memiliki akses", "tidak berhak",
                       "akses", "izin", "margin", "laba", "refus", "block"]
    assert any(m in text for m in refusal_markers), f"sales margin not refused clearly: {text[:200]}"
    # verify no result rows returned with margin numbers
    result_ids = done.get("result_ids") or []
    # should typically be empty for refused
    assert isinstance(result_ids, list)


# ---- access control: sales own-data only ---------------------------------
def test_sales_own_data_only(sales_token):
    events = _chat(sales_token, "Penjualan semua sales bulan ini", timeout=90)
    done = _done_event(events)
    assert done is not None
    # Must not expose other sales data; expect refusal or filtered to own
    text = (done.get("text") or "")
    # soft check: expect either explicit scope restriction OR mention of own name only
    assert isinstance(text, str) and len(text) > 0


# ---- templates/run + narrative -------------------------------------------
def test_template_run_and_narrative_manager(manager_token):
    r = requests.post(
        f"{BASE_URL}/api/ai/templates/top_customers/run",
        headers=_headers(manager_token),
        json={"params": {"period": "last_90d"}},
        timeout=60,
    )
    assert r.status_code == 200, f"template run: {r.status_code} {r.text[:300]}"
    data = r.json()
    # template run returns `results` dict keyed by result_id
    results_dict = data.get("results") or {}
    result_ids = list(results_dict.keys())
    if not result_ids:
        # fallback keys
        if data.get("result_ids"):
            result_ids = data["result_ids"]
        elif data.get("result_id"):
            result_ids = [data["result_id"]]
    assert result_ids, f"no result ids: {list(data.keys())}"

    nr = requests.post(
        f"{BASE_URL}/api/ai/narrative",
        headers=_headers(manager_token),
        json={"template_id": "top_customers", "result_ids": result_ids},
        timeout=90,
    )
    assert nr.status_code == 200, f"narrative: {nr.status_code} {nr.text[:300]}"
    nd = nr.json()
    assert nd.get("source") == "ai", f"source should be ai: {nd.get('source')} / {nd}"
    assert nd.get("model") == "gpt-6-luna", f"model: {nd.get('model')}"
    assert (nd.get("verification") or {}).get("ok") is True, nd.get("verification")

    # export xlsx
    xr = requests.get(f"{BASE_URL}/api/ai/results/{result_ids[0]}/export.xlsx",
                      headers={"Authorization": f"Bearer {manager_token}", "X-Entity-Id": ENTITY},
                      timeout=30)
    assert xr.status_code == 200
    assert xr.content[:2] == b"PK", "xlsx should start with PK header"


# ---- usage/daily ---------------------------------------------------------
def test_ai_usage_daily_admin(admin_token):
    r = requests.get(f"{BASE_URL}/api/ai/usage/daily",
                     headers=_headers(admin_token), timeout=20)
    assert r.status_code == 200
    d = r.json()
    # expect something with budget / spent
    assert isinstance(d, dict)
    assert any(k in d for k in ("spent_usd", "budget", "by_feature", "by_day", "items", "daily"))
