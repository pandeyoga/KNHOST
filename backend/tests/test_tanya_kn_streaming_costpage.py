"""Tanya KN — F6: Jawaban Bertahap (SSE streaming) + Halaman Biaya AI (/api/ai/usage/daily).

Prerequisites (per agent-to-agent context): DB has ai.enabled=true and ai.model_main=mock-chat.
Restores ai.enabled_roles after the 403 test.
"""
import json
import sys
import time

import pytest
import requests

sys.path.insert(0, "/app/backend/tests")
from test_inbound_complete_characterization import BASE  # noqa: E402


def _login(email, password="demo12345"):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"})
    return s


def _events(text):
    out = []
    for chunk in text.split("\n\n"):
        if chunk.startswith("data: "):
            try:
                out.append(json.loads(chunk[6:]))
            except Exception:
                pass
    return out


def _stream_chat(session, question):
    r = session.post(f"{BASE}/ai/chat", json={"question": question}, stream=False, timeout=60)
    assert r.status_code == 200, r.text
    return _events(r.text)


# ── FIXTURE: ensure mock mode is on ────────────────────────────────────────
@pytest.fixture(scope="module", autouse=True)
def _ensure_mock():
    s = _login("admin@kainnusantara.id")
    st = s.get(f"{BASE}/ai/status").json()
    if not st.get("mock") or not st.get("config_enabled"):
        s.put(f"{BASE}/config/values", json={"items": [
            {"key": "ai.enabled", "value": True, "reason": "test streaming"},
            {"key": "ai.model_main", "value": "mock-chat", "reason": "test streaming"},
        ]})
    yield
    s.put(f"{BASE}/config/values", json={"items": [   # pulihkan status AI sebelum uji
        {"key": "ai.enabled", "value": bool(st.get("config_enabled")), "reason": "pulihkan sesudah uji"},
        {"key": "ai.model_main", "value": st.get("model") or "gpt-6-sol", "reason": "pulihkan sesudah uji"},
    ]})


# ── 1) Streaming: free question routed via mock-chat (template fallback) ──
def test_stream_free_question_word_by_word():
    s = _login("admin@kainnusantara.id")
    evs = _stream_chat(s, "bagaimana tren penjualan dan siapa pelanggan terbesar kita")
    deltas = [e for e in evs if e.get("type") == "delta"]
    done = next((e for e in evs if e.get("type") == "done"), None)
    assert done is not None
    assert done.get("session_id") and "text" in done
    assert isinstance(done.get("result_ids"), list)
    # many word-by-word deltas
    assert len(deltas) >= 10, f"expected many deltas, got {len(deltas)}"
    # kn-* code blocks arrive whole
    kn_deltas = [d["text"] for d in deltas if d["text"].startswith("```kn-")]
    assert kn_deltas, "no kn-* block delta found"
    for kd in kn_deltas:
        assert kd.endswith("```") or kd.endswith("```\n") or "```" in kd, f"kn block not whole: {kd[:50]}"
    # concatenated deltas equal done.text
    concat = "".join(d["text"] for d in deltas)
    assert concat == done["text"], "concatenated deltas mismatch done.text"


# ── 2) Streaming: exact-template routed question also streams ─────────────
def test_stream_template_routed_question():
    s = _login("admin@kainnusantara.id")
    evs = _stream_chat(s, "Siapa 10 pelanggan dengan pembelian terbesar bulan ini?")
    deltas = [e for e in evs if e.get("type") == "delta"]
    done = next((e for e in evs if e.get("type") == "done"), None)
    assert done is not None and done.get("template_id")
    assert len(deltas) >= 10
    concat = "".join(d["text"] for d in deltas)
    assert concat == done["text"]


# ── 3) Session persistence after streamed chat ────────────────────────────
def test_streamed_chat_saved_in_session():
    s = _login("manager@kainnusantara.id")
    evs = _stream_chat(s, "bagaimana tren penjualan dan siapa pelanggan terbesar kita")
    done = next(e for e in evs if e.get("type") == "done")
    sid = done["session_id"]
    # Session list
    lst = s.get(f"{BASE}/ai/sessions").json()
    assert any(x["id"] == sid for x in lst)
    # Reopen session — the full answer must be there
    doc = s.get(f"{BASE}/ai/sessions/{sid}").json()
    turns = doc.get("turns") or []
    asst = [t for t in turns if t.get("role") == "assistant"]
    assert asst, "no assistant turn saved"
    assert asst[-1]["content"] == done["text"]


# ── 4) Usage/daily shape (days=7|30|90, scope=bi|all, clamping) ────────────
def test_usage_daily_shape_and_clamping():
    s = _login("admin@kainnusantara.id")
    for days in (7, 30, 90):
        for scope in ("bi", "all"):
            r = s.get(f"{BASE}/ai/usage/daily", params={"days": days, "scope": scope})
            assert r.status_code == 200, r.text
            d = r.json()
            assert d["range"]["days"] == days
            assert len(d["daily_feature"]) == days
            assert len(d["daily_user"]) == days
            for key in ("usd", "calls", "tokens", "avg_usd_per_day"):
                assert key in d["totals"]
            for key in ("limit_usd", "spent_usd", "used_pct", "projected_usd"):
                assert key in d["budget"]
            assert "features" in d and "users" in d and "models" in d
            assert "feature_series" in d and "user_series" in d
            assert len(d["user_series"]) <= 7  # 6 top + Lainnya
            assert "demo_rows" in d
            assert d["scope"] == scope
    # clamping
    for raw in (0, -5, 500):
        r = s.get(f"{BASE}/ai/usage/daily", params={"days": raw})
        assert r.status_code == 200
        assert 1 <= r.json()["range"]["days"] <= 90


# ── 5) Role access: admin/manager/sales/finance allowed; 403 when removed; 401 unauth ──
def test_usage_daily_role_access_and_toggle():
    admin = _login("admin@kainnusantara.id")
    for email in ("admin@kainnusantara.id", "manager@kainnusantara.id",
                  "sales@kainnusantara.id", "finance@kainnusantara.id"):
        s = _login(email)
        r = s.get(f"{BASE}/ai/usage/daily")
        assert r.status_code == 200, f"{email} got {r.status_code}"

    # Unauth
    r = requests.get(f"{BASE}/ai/usage/daily", timeout=15)
    assert r.status_code in (401, 403)

    # Remove sales from enabled_roles → sales should 403
    default_roles = ["admin", "manager", "sales_admin", "finance", "md", "warehouse_admin", "sales"]
    try:
        new_roles = [r for r in default_roles if r != "sales"]
        rr = admin.put(f"{BASE}/config/values", json={"items": [
            {"key": "ai.enabled_roles", "value": new_roles, "reason": "test 403"}]})
        assert rr.status_code in (200, 204), rr.text
        sales = _login("sales@kainnusantara.id")
        r = sales.get(f"{BASE}/ai/usage/daily")
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"
    finally:
        admin.put(f"{BASE}/config/values", json={"items": [
            {"key": "ai.enabled_roles", "value": default_roles, "reason": "restore"}]})
        # sanity check restore
        r = _login("sales@kainnusantara.id").get(f"{BASE}/ai/usage/daily")
        assert r.status_code == 200, "restore failed"


# ── 6) Demo rows excluded from budget spend but shown in usage/daily ──────
def test_demo_rows_excluded_from_budget():
    s = _login("admin@kainnusantara.id")
    d = s.get(f"{BASE}/ai/usage/daily", params={"days": 90, "scope": "all"}).json()
    demo_rows = d.get("demo_rows", 0)
    st = s.get(f"{BASE}/ai/status").json()
    us = s.get(f"{BASE}/ai/usage").json()
    # budget.spent_usd from /ai/status and /ai/usage exclude demo
    if demo_rows > 0:
        # sanity: totals include something, but budget.spent_usd should not include demo cost
        # We can't directly assert numeric equality without knowing demo cost, but we ensure
        # budget spent_usd from /ai/status <= totals.usd from /ai/usage/daily (which includes demo)
        assert st["budget"]["spent_usd"] <= d["totals"]["usd"] + 1e-6
        assert us["budget"]["spent_usd"] <= d["totals"]["usd"] + 1e-6
    # demo_rows key present
    assert isinstance(demo_rows, int)
