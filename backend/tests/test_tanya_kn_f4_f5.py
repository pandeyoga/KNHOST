"""Tanya KN F3 sisa / F4 / F5 — riwayat sesi, narasi, cache, routing, template pribadi, jadwal, snapshot, biaya."""
import json
import sys

import requests

sys.path.insert(0, "/app/backend/tests")
from test_inbound_complete_characterization import BASE  # noqa: E402


def _login(email):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"})
    return s


def _events(r):
    return [json.loads(c[6:]) for c in r.text.split("\n\n") if c.startswith("data: ")]


def test_template_auto_narrative_and_cache():
    s = _login("manager@kainnusantara.id")
    a = s.post(f"{BASE}/ai/templates/top_customers/run", json={"params": {"period": "last_90d"}}).json()
    assert a["narrative"] and "Rp" in a["narrative"] and a["narrative_source"] == "auto"
    b = s.post(f"{BASE}/ai/templates/top_customers/run", json={"params": {"period": "last_90d"}}).json()
    assert b["cached"] is True and b["results"].keys() == a["results"].keys()
    n = s.post(f"{BASE}/ai/narrative", json={"template_id": "top_customers", "result_ids": list(a["results"])}).json()
    assert n["source"] in ("auto", "ai") and n["text"]   # "ai" bila kunci OpenAI aktif
    if n["source"] == "ai":
        assert n["verification"]["ok"] is True
    other = _login("finance@kainnusantara.id")
    assert other.post(f"{BASE}/ai/narrative", json={"template_id": "top_customers", "result_ids": list(a["results"])}).status_code == 404


def test_routing_exact_template_question_runs_template_without_ai():
    s = _login("admin@kainnusantara.id")
    tpl = s.get(f"{BASE}/ai/templates").json()["templates"]
    q = next(t for t in tpl if t["id"] == "top_customers")["prompt"]
    evs = _events(s.post(f"{BASE}/ai/chat", json={"question": q}))
    done = evs[-1]
    assert done["type"] == "done" and done.get("template_id") == "top_customers" and done["result_ids"] and not done.get("disabled")


def test_sessions_search_open_continue_delete():
    s = _login("admin@kainnusantara.id")
    first = _events(s.post(f"{BASE}/ai/chat", json={"question": "uji riwayat zebra penjualan"}))[-1]
    sid = first["session_id"]
    _events(s.post(f"{BASE}/ai/chat", json={"question": "lanjutan zebra", "session_id": sid}))
    found = s.get(f"{BASE}/ai/sessions", params={"q": "zebra"}).json()
    row = next(x for x in found if x["id"] == sid)
    assert row["questions"] == 2
    turns = s.get(f"{BASE}/ai/sessions/{sid}").json()["turns"]
    assert [t["role"] for t in turns] == ["user", "assistant", "user", "assistant"]
    assert _login("manager@kainnusantara.id").delete(f"{BASE}/ai/sessions/{sid}").status_code == 404
    assert s.delete(f"{BASE}/ai/sessions/{sid}").json()["ok"]
    assert s.get(f"{BASE}/ai/sessions/{sid}").status_code == 404


def test_my_templates_crud():
    s = _login("sales@kainnusantara.id")
    t = s.post(f"{BASE}/ai/my-templates", json={"question": "Penjualan saya minggu ini dibanding minggu lalu?"}).json()
    assert t["mode"] == "llm" and any(x["id"] == t["id"] for x in s.get(f"{BASE}/ai/my-templates").json())
    assert s.post(f"{BASE}/ai/my-templates", json={"question": "a"}).status_code == 400
    assert _login("admin@kainnusantara.id").delete(f"{BASE}/ai/my-templates/{t['id']}").status_code == 404
    assert s.delete(f"{BASE}/ai/my-templates/{t['id']}").json()["ok"]


def test_schedule_create_run_notify_and_validation():
    s = _login("manager@kainnusantara.id")
    assert s.post(f"{BASE}/ai/schedules", json={"template_id": "top_customers", "time": "25:00"}).status_code == 400
    assert s.post(f"{BASE}/ai/schedules", json={"template_id": "nope"}).status_code == 400
    sc = s.post(f"{BASE}/ai/schedules", json={"template_id": "top_customers", "frequency": "weekly", "weekday": 4,
                                              "time": "08:15", "params": {"period": "mtd"}}).json()
    assert sc["active"] and sc["entity_id"] == "ent_ksc" and sc["next_run_at"]
    run = s.post(f"{BASE}/ai/schedules/{sc['id']}/run").json()
    assert run["status"] == "ok" and run["result_ids"] and run["narrative"]
    detail = s.get(f"{BASE}/ai/schedule-runs/{run['id']}").json()
    assert set(detail["results"]) == set(run["result_ids"]) and detail["template"]["id"] == "top_customers"
    notifs = s.get(f"{BASE}/notifications").json()
    items = notifs.get("items", notifs) if isinstance(notifs, dict) else notifs
    assert any("Laporan terjadwal" in (n.get("title") or "") for n in items)
    off = s.patch(f"{BASE}/ai/schedules/{sc['id']}", json={"active": False}).json()
    assert off["active"] is False
    assert _login("sales@kainnusantara.id").post(f"{BASE}/ai/schedules/{sc['id']}/run").status_code == 404
    assert s.delete(f"{BASE}/ai/schedules/{sc['id']}").json()["ok"]


def test_sales_cannot_schedule_margin_template():
    s = _login("sales@kainnusantara.id")
    assert s.post(f"{BASE}/ai/schedules", json={"template_id": "margin_by_product"}).status_code == 400


def test_snapshot_status_usage_budget_and_roles():
    a = _login("admin@kainnusantara.id")
    r = a.post(f"{BASE}/ai/snapshots/run").json()
    assert r["created"] > 0
    st = a.get(f"{BASE}/ai/snapshots/status").json()
    assert st["fact_stock_daily"]["last_date"] and st["fact_ar_daily"]["days"] >= 1
    assert _login("sales@kainnusantara.id").post(f"{BASE}/ai/snapshots/run").status_code == 403
    u = a.get(f"{BASE}/ai/usage").json()
    assert u["budget"]["limit_usd"] == 100 and "items" in u
    status = a.get(f"{BASE}/ai/status").json()
    live = status["config_enabled"] and status["has_key"] and not status["mock"]
    assert status["budget"]["exceeded"] is False and status["narrative_ai"] is live
