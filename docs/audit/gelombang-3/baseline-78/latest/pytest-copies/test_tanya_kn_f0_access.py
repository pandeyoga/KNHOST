"""Tanya KN F0.4 — celah hak akses laporan lama sudah ditutup."""
import os
import sys

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, "C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/tests")
from test_inbound_complete_characterization import BASE  # noqa: E402


def _login(email, ent="ent_ksc"):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ent})
    return s


@pytest.fixture(scope="module")
def mdb():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def test_reports_summary_scoped_to_sales_owner():
    admin = _login("admin@kainnusantara.id").get(f"{BASE}/reports/summary").json()
    sales = _login("sales2@kainnusantara.id").get(f"{BASE}/reports/summary").json()
    assert sales["monthly_revenue"] <= admin["monthly_revenue"]
    assert sales["pending_approvals"] <= admin["pending_approvals"]


def test_sales_kpi_and_commission_need_permission_and_entity():
    driver = _login("driver@kainnusantara.id")
    assert driver.get(f"{BASE}/sales/kpi").status_code == 403
    assert driver.get(f"{BASE}/sales/commission", params={"period": "2026-09"}).status_code == 403
    sales = _login("sales@kainnusantara.id")
    assert sales.get(f"{BASE}/sales/kpi", params={"entity_id": "ent_kanda"}).status_code == 403
    assert sales.get(f"{BASE}/sales/commission", params={"period": "2026-09", "entity_id": "ent_kanda"}).status_code == 403
    assert sales.get(f"{BASE}/sales/kpi").status_code == 200


def _keys(obj, acc=None):
    acc = set() if acc is None else acc
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.add(k)
            _keys(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _keys(v, acc)
    return acc


def test_profitability_hides_cost_for_finance():
    fin = _login("finance@kainnusantara.id").get(f"{BASE}/finance/profitability")
    assert fin.status_code == 200
    assert not ({"cogs", "cogs_base", "cogs_landed", "margin", "margin_pct"} & _keys(fin.json()))
    adm = _login("admin@kainnusantara.id").get(f"{BASE}/finance/profitability").json()
    assert {"cogs", "margin"} <= _keys(adm)


def test_invoices_list_is_entity_scoped(mdb):
    mdb.invoices.insert_one({"id": "TEST_inv_kanda", "invoice_number": "TEST-INV-K", "entity_id": "ent_kanda",
                             "created_at": "2026-09-01T00:00:00+00:00"})
    try:
        ksc = _login("manager@kainnusantara.id", "ent_ksc").get(f"{BASE}/invoices").json()
        kanda = _login("manager@kainnusantara.id", "ent_kanda").get(f"{BASE}/invoices").json()
        assert "TEST_inv_kanda" not in {i["id"] for i in ksc}
        assert "TEST_inv_kanda" in {i["id"] for i in kanda}
    finally:
        mdb.invoices.delete_one({"id": "TEST_inv_kanda"})
