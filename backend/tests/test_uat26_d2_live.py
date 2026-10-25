"""Keputusan pemilik 26 Okt 2026 (audit UI tahap 2) — wilayah D2, uji HTTP (butuh server hidup + data acuan).

Jalankan (koordinator, sesudah restart backend):
    cd /app/backend && python -m pytest tests/test_uat26_d2_live.py -p no:randomly -n 0 -q
HANYA MEMBACA (GET).
"""
import os

import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
ADMIN = ("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def admin_h():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]}, timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}


def _get(path, h, **params):
    r = requests.get(f"{BASE}/api{path}", headers=h, params=params, timeout=90)
    assert r.status_code == 200, f"{path}: {r.status_code} {r.text[:300]}"
    return r.json()


# ── K-06 + B2 ─────────────────────────────────────────────────────────────────
def test_k06_pending_is_waiting_approval_only(admin_h):
    s = _get("/sales-orders/stats/summary", admin_h)
    assert s["pending_count"] == int((s["by_status"].get("waiting_approval") or {}).get("count", 0))
    assert "Menunggu persetujuan" in s["pending_basis"]


def test_k06_funnel_same_population_as_order_list(admin_h):
    s = _get("/sales-orders/stats/summary", admin_h)
    f = _get("/reports/reservation-funnel", admin_h)
    assert f["total_orders"] == s["total_orders"], (f["total_orders"], s["total_orders"])
    assert "sample_excluded" in f and "scope_label" in f
    summ = _get("/reports/summary", admin_h)
    assert summ["pending_approvals"] == s["pending_count"]


# ── K-04 ──────────────────────────────────────────────────────────────────────
def test_k04_low_stock_single_definition(admin_h):
    low = _get("/inventory/low-stock-summary", admin_h, limit=500)
    assert low["threshold"] == 100 and low["count"] >= len(low["items"])
    assert all(0 < it["available"] < 100 for it in low["items"])
    summ = _get("/reports/summary", admin_h)
    assert summ["low_stock_items"] == low["count"]
    # papan stok (status board) = definisi yang sama per produk & badan usaha
    board = {r["product_id"]: r for r in _get("/inventory/status-board", admin_h, owner_entity_id="ent_ksc")}
    for it in low["items"][:20]:
        if it["entity_id"] != "ent_ksc":
            continue
        ent = next((e for e in board[it["product_id"]]["by_entity"] if e["entity_id"] == "ent_ksc"), None)
        assert ent and abs(ent["available"] - it["available"]) < 0.01, it["sku"]


def test_k04_reorder_available_matches_status_board(admin_h):
    rs = _get("/purchase-requisitions/reorder-suggestions", admin_h, entity_id="ent_ksc")
    board = {r["product_id"]: r for r in _get("/inventory/status-board", admin_h, owner_entity_id="ent_ksc")}
    for row in (rs.get("items") or [])[:20]:
        ent = next((e for e in (board.get(row["product_id"]) or {}).get("by_entity", [])
                    if e["entity_id"] == "ent_ksc"), {"available": 0.0})
        assert abs(float(row["available"]) - max(float(ent["available"]), 0.0)) < 0.01, row["sku"]


# ── K-05 ──────────────────────────────────────────────────────────────────────
def test_k05_stock_analytics_moving_average_shape(admin_h):
    d = _get("/inventory/stock-analytics", admin_h, entity_id="ent_ksc")
    th = d["thresholds"]
    for k in ("velocity_window_days", "best_seller_pct", "slow_moving_pct", "new_sku_age_days"):
        assert k in th
    assert set(d["summary"]["by_class"]) == {"best", "normal", "slow", "dead", "new"}
    assert d["method"]["basis"] == "moving_average_so"
    for r in d["rows"][:50]:
        assert r["classification"] in ("best", "normal", "slow", "dead", "new")
        if r["percentile"] is not None:
            assert 0 <= r["percentile"] <= 100 and r["rank_group_size"] >= 1
        if r["classification"] == "dead":
            assert r["sold_qty_window"] == 0 and r["on_hand_qty"] > 0


# ── B1 ────────────────────────────────────────────────────────────────────────
def test_b1_inspection_meta_policy(admin_h):
    m = _get("/inspections/meta", admin_h)
    assert m["policy"]["accept_all_with_hold_action"] in ("peringatkan", "blokir")
    assert m["policy"]["accept_all_with_hold_label"]
