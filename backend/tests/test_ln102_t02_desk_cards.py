"""LN-102-T02 — kartu antrean Meja Saya: hitungan = isi daftar, tanpa duplikat, tiap baris bisa dibuka."""
import os

import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ROLES = {"admin": "demo12345", "manager": "demo1234", "sales": "demo1234", "warehouse": "demo1234"}
OWN_DESKS = {"salesadmin": "/sales-admin/desk", "md": "/md/desk", "whadmin": "/warehouse-admin/desk"}
OPENABLE = {"sales_order", "purchase_order", "sales_return", "internal_request", "customer", "special_order",
            "design_request", "sample_request", "price_approval", "purchase_return", "md_sample",
            "purchase_requisition", "inspection", "shipment", "wms_task", "cycle_count", "warehouse_transfer",
            "logistics_delivery"}


def _login(role, pw):
    for p in (pw, "demo12345", "demo1234"):
        r = requests.post(f"{BASE}/auth/login", json={"email": f"{role}@kainnusantara.id", "password": p})
        if r.status_code == 200:
            return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}
    pytest.skip(f"login {role} gagal")


@pytest.mark.parametrize("role", list(ROLES))
def test_card_count_equals_rows_and_rows_openable(role):
    h = _login(role, ROLES[role])
    d = requests.get(f"{BASE}/desks/me", headers=h).json()
    for q in d["queues"]:
        rows = q.get("rows") or []
        assert q["count"] == len(rows), (role, q["id"], q["count"], len(rows))
        refs = [(r["ref_type"], r["ref_id"]) for r in rows]
        assert len(refs) == len(set(refs)), (role, q["id"], "duplikat")
        for r in rows:
            assert r["ref_type"] in OPENABLE and r["ref_id"], (role, q["id"], r["ref_type"])
            if r["ref_type"] == "wms_task" and q["id"] == "tugas_wms":
                assert "flow_type" in r and "po_id" in r
    assert d["total_items"] >= 0


@pytest.mark.parametrize("role", list(OWN_DESKS))
def test_own_desk_cards_match_rows(role):
    h = _login(role, "demo1234")
    d = requests.get(f"{BASE}{OWN_DESKS[role]}", headers=h).json()
    for q in d["queues"]:
        rows = q.get("rows") or []
        assert q["count"] == len(rows), (role, q["id"], q["count"], len(rows))
        refs = [(r["ref_type"], r["ref_id"]) for r in rows]
        assert len(refs) == len(set(refs)), (role, q["id"], "duplikat")
