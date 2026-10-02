"""Tanya KN F2/F3 — tool, template resep, chat saat mati, pemeriksa angka, unduh Excel."""
import json
import sys

import requests

sys.path.insert(0, "/app/backend/tests")
sys.path.insert(0, "/app/backend")
from test_inbound_complete_characterization import BASE  # noqa: E402
from services.ai_number_check import extract_numbers, verify  # noqa: E402


def _login(email):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"})
    return s


def test_number_check_indonesian_formats():
    nums = {n["text"]: n["value"] for n in extract_numbers("Omzet Rp 1.250.000 naik 12,4% (10 teratas, 24 Sep 2026), stok 2.186 yd, 1,25 M")}
    assert nums["Rp 1.250.000"] == 1250000 and nums["12,4%"] == 12.4 and nums["1,25 M"] == 1.25e9
    assert not any("2026" in k for k in nums)
    res = [{"rows": [{"net_sales": 1250000.0, "pct": 12.41, "qty": 2186.0}], "totals": {"big": 1251000000.0}}]
    assert verify("Omzet Rp 1.250.000 naik 12,4%, stok 2.186 yd, total 1,25 M", res)["ok"]
    bad = verify("Omzet Rp 9.999.000", res)
    assert not bad["ok"] and bad["unmatched"] == ["Rp 9.999.000"]


def test_templates_filtered_by_role_and_all_run_for_admin():
    admin, sales = _login("admin@kainnusantara.id"), _login("sales@kainnusantara.id")
    ta = admin.get(f"{BASE}/ai/templates").json()["templates"]
    ts = sales.get(f"{BASE}/ai/templates").json()["templates"]
    assert len(ta) == 34 and len(ts) < len(ta) and "margin_by_product" not in {t["id"] for t in ts}
    for t in ta:
        params = {"product": "prod_batik_mega"} if any(p.get("required") for p in t["params"]) else {}
        r = admin.post(f"{BASE}/ai/templates/{t['id']}/run", json={"params": params})
        assert r.status_code == 200, (t["id"], r.text)
        d = r.json()
        assert all(b["result_id"] in d["results"] for b in d["blocks"])
    assert sales.post(f"{BASE}/ai/templates/margin_by_product/run", json={"params": {}}).status_code == 400


def test_period_param_overrides_template():
    d = _login("admin@kainnusantara.id").post(f"{BASE}/ai/templates/top_products/run", json={"params": {"period": "last_month"}}).json()
    first = d["results"][d["blocks"][0]["result_id"]]
    assert first["period"]["preset"] == "last_month"


def _set_ai(enabled, model="gpt-6-sol"):
    a = _login("admin@kainnusantara.id")
    r = a.put(f"{BASE}/config/values", json={"items": [
        {"key": "ai.enabled", "value": enabled, "scope_type": "global", "reason": "uji Tanya KN"},
        {"key": "ai.model_main", "value": model, "scope_type": "global", "reason": "uji Tanya KN"}]})
    assert r.status_code == 200, r.text


def test_chat_disabled_suggests_templates_and_status():
    _set_ai(False)
    s = _login("manager@kainnusantara.id")
    st = s.get(f"{BASE}/ai/status").json()
    assert st["chat_enabled"] is False and st["sales_definition"] == "net_order" and st["can_edit_rules"] is True
    r = s.post(f"{BASE}/ai/chat", json={"question": "siapa pelanggan terbesar bulan ini?"})
    assert r.status_code == 200 and '"disabled": true' in r.text and "top_customers" in r.text
    sessions = s.get(f"{BASE}/ai/sessions").json()
    assert sessions and s.get(f"{BASE}/ai/sessions/{sessions[0]['id']}").json()["turns"]


def test_tools_endpoint_and_export():
    s = _login("admin@kainnusantara.id")
    fe = s.post(f"{BASE}/ai/tools/find_entities", json={"kind": "customer", "query": "toko kain"}).json()
    assert fe["candidates"][0]["id"] == "cust_toko_kain"
    lr = s.post(f"{BASE}/ai/tools/list_records", json={"record_type": "overdue_invoices", "period": None, "filters": [],
                                                       "sort": {"by": "days_overdue", "direction": "desc"}, "limit": 20}).json()
    x = s.get(f"{BASE}/ai/results/{lr['result_id']}/export.xlsx")
    assert x.status_code == 200 and x.content[:2] == b"PK"
    assert s.post(f"{BASE}/ai/feedback", json={"rating": "up", "result_ids": [lr["result_id"]]}).json()["ok"]
    assert s.post(f"{BASE}/ai/tools/unknown", json={}).status_code == 400


def test_chat_mock_mode_returns_results_and_combined_export():
    _set_ai(True, "mock-chat")
    try:
        s = _login("admin@kainnusantara.id")
        st = s.get(f"{BASE}/ai/status").json()
        assert st["chat_enabled"] is True and st["mock"] is True and st["has_key"] is False
        r = s.post(f"{BASE}/ai/chat", json={"question": "pelanggan terbesar bulan ini"})
        evs = [json.loads(c[6:]) for c in r.text.split("\n\n") if c.startswith("data: ")]
        done = evs[-1]
        assert done["type"] == "done" and done["result_ids"] and not done.get("disabled")
        text = "".join(e["text"] for e in evs if e["type"] == "delta")
        assert "MODE UJI" in text and "kn-" in text
        x = s.get(f"{BASE}/ai/export.xlsx", params={"ids": ",".join(done["result_ids"])})
        assert x.status_code == 200 and x.content[:2] == b"PK"
        assert s.get(f"{BASE}/ai/export.xlsx", params={"ids": "r_nope"}).status_code == 404
        sales = _login("sales@kainnusantara.id")
        assert sales.get(f"{BASE}/ai/export.xlsx", params={"ids": done["result_ids"][0]}).status_code == 404
    finally:
        _set_ai(False)
