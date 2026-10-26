"""Fase 4 · R5 (26 Okt 2026) — uji HTTP (butuh backend yang sudah di-RESTART dengan kode R5). Hanya MEMBACA data.

* `/reports/order-velocity` — sales: data miliknya (`owner_scoped`), ≤ angka admin; admin/manajer: seluruh PT.
* `/sales-orders/stats/summary` — `backorder_count` = jumlah status `waiting_stock` (keputusan pemilik #2).
* `/approvals/my-queue` — pengaju berupa NAMA (bukan email) bila akunnya ada; email asli di `requester_account`.
* `/approvals/backlog` — memuat 6 antrean baru; SO mati tidak dihitung; total = KPI beranda (cakupan sama).
* `/auth/me` — `view_resources["inventory-lots"] == ["field_visibility"]`.

Jalankan: cd /app/backend && python -m pytest tests/test_phase4_r5_http.py -p no:randomly -n 0 -q
"""
import os

import pytest
import requests
from dotenv import dotenv_values

fe = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or fe.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
ENT = "ent_ksc"
PWD = "demo12345"
NEW_QUEUES = {"design_claim", "credit_override", "od_cancel_credit_note", "makloon_loss", "po_variance",
              "sales_return_exception"}


def _login(who: str, entity: str = ENT) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "X-Entity-Id": entity})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": f"{who}@kainnusantara.id", "password": PWD}, timeout=60)
    assert r.status_code == 200, f"login {who} gagal: {r.status_code} {r.text[:200]}"
    s.headers.update({"Authorization": f"Bearer {r.json().get('token')}"})
    return s


@pytest.fixture(scope="module")
def ses():
    return {w: _login(w) for w in ("admin", "manager", "sales")}


def test_velocity_sales_hanya_miliknya(ses):
    a = ses["admin"].get(f"{BASE_URL}/api/reports/order-velocity", params={"days": 90}, timeout=60).json()
    s = ses["sales"].get(f"{BASE_URL}/api/reports/order-velocity", params={"days": 90}, timeout=60).json()
    assert a["owner_scoped"] is False and s["owner_scoped"] is True
    assert "milik Anda" in s["scope_label"]
    assert s["total_orders"] <= a["total_orders"]
    assert sum(d["count"] for d in s["velocity"]) == s["total_orders"]


def test_backorder_count_sama_dengan_tab_menunggu_stok(ses):
    for who in ("admin", "sales"):
        d = ses[who].get(f"{BASE_URL}/api/sales-orders/stats/summary", timeout=60).json()
        assert d["backorder_count"] == int((d["by_status"].get("waiting_stock") or {}).get("count", 0)), who
        assert "partial_backorder_count" in d and d["partial_backorder_count"] >= 0


def test_matriks_divisi_pengaju_nama(ses):
    body = ses["manager"].get(f"{BASE_URL}/api/approvals/my-queue", timeout=60).json()
    for it in body.get("items") or []:
        assert "requester_account" in it
        if it["requester_account"]:
            assert "@" not in it["requester"] or it["requester"] == it["requester_account"]   # akun tak dikenal → apa adanya
    raw = ses["admin"].get(f"{BASE_URL}/api/users", timeout=60).json()
    users = {u["email"].lower() for u in (raw if isinstance(raw, list) else raw.get("items") or []) if u.get("email")}
    bocor = [it["number"] for it in body.get("items") or [] if str(it.get("requester", "")).lower() in users]
    assert bocor == [], f"pengaju masih email akun yang dikenal: {bocor}"


def test_backlog_antrean_baru_dan_kpi_sama(ses):
    adm = _login("admin", "all")
    bl = adm.get(f"{BASE_URL}/api/approvals/backlog", timeout=60).json()
    keys = {r["key"] for r in bl["all_items"]}
    assert NEW_QUEUES <= keys
    home = adm.get(f"{BASE_URL}/api/home/admin", timeout=60).json()
    assert bl["total"] == home["approvals_pending"]


def test_lot_silsilah_sumber_izin(ses):
    me = ses["sales"].get(f"{BASE_URL}/api/auth/me", timeout=60).json()
    assert me["view_resources"]["inventory-lots"] == ["field_visibility"]
    assert not (me.get("permissions") or {}).get("field_visibility")
    assert ses["sales"].get(f"{BASE_URL}/api/lots", timeout=60).status_code == 403       # pintu yang memang tertutup
