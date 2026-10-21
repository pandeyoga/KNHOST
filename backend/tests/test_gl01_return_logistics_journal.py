"""GL-01 Fase D — jurnal ongkir retur: cara kirim, penanggung, akun bayar Finance, PT pembeban, jurnal balik."""
import os

import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]


def _login(email, pw="demo12345"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


FIN = _login("finance@kainnusantara.id")
SADM = _login("salesadmin@kainnusantara.id")
RET = DB.sales_returns.find_one({"status": {"$in": ["approved", "inspecting", "inspected", "received"]}, "entity_id": "ent_ksc"})


def _jes():
    return list(DB.journal_entries.find({"source_type": "return_logistics", "ref.return_id": RET["id"]}, {"_id": 0}))


def _cleanup():
    ids = [j["id"] for j in _jes()]
    DB.journal_entries.delete_many({"$or": [{"id": {"$in": ids}}, {"source_type": "reversal", "source_id": {"$in": ids}}]})
    DB.sales_returns.update_one({"id": RET["id"]}, {"$unset": {"logistics_costs": ""}})


def _put(h, costs):
    return requests.put(f"{BASE}/sales-returns/{RET['id']}/logistics", headers=h, json={"costs": costs})


def test_logistics_journals_flow():
    assert RET, "butuh retur ent_ksc berstatus approved/inspecting"
    _cleanup()
    try:
        ctx = requests.get(f"{BASE}/sales-returns/{RET['id']}/logistics", headers=FIN).json()
        assert ctx["can_post"] is True and ctx["pay_accounts"]
        r = _put(FIN, [{"type": "customer_return", "mode": "third_party", "bearer": "company", "amount": 50000, "pay_account_code": "2-1100"},
                       {"type": "replacement_shipping", "mode": "own_fleet", "bearer": "customer", "amount": 30000},
                       {"type": "qc_trip", "mode": "pickup"}])
        assert r.status_code == 200, r.text
        rows = {c["type"]: c for c in r.json()["costs"]}
        assert rows["customer_return"]["journal_entry_number"] and rows["replacement_shipping"]["journal_entry_number"]
        assert rows["qc_trip"]["journal_entry_number"] == ""
        je = DB.journal_entries.find_one({"id": rows["customer_return"]["journal_entry_id"]})
        assert {(l["account_code"], l["debit"], l["credit"]) for l in je["lines"]} == {("6-4500", 50000, 0), ("2-1100", 0, 50000)}
        # Non-Finance tidak boleh mengganti akun pembayaran.
        assert _put(SADM, [{"type": "customer_return", "mode": "third_party", "bearer": "company", "amount": 50000,
                            "pay_account_code": "1-1100"}]).status_code == 403
        # Simpan ulang identik → tidak ada jurnal baru.
        _put(FIN, [{"type": "customer_return", "mode": "third_party", "bearer": "company", "amount": 50000, "pay_account_code": "2-1100"},
                   {"type": "replacement_shipping", "mode": "own_fleet", "bearer": "customer", "amount": 30000}])
        assert len(_jes()) == 2
        # Customer bayar sendiri ke ekspedisi → jurnal lama dibalik, tanpa jurnal baru; PT pembeban lain.
        r = _put(FIN, [{"type": "customer_return", "mode": "third_party", "bearer": "customer", "amount": 50000},
                       {"type": "replacement_shipping", "mode": "own_fleet", "bearer": "customer", "amount": 30000, "charged_entity_id": "ent_kanda"}])
        assert r.status_code == 200
        live = [j for j in _jes() if not j.get("reversed_by_entry_id")]
        assert len(live) == 1 and live[0]["entity_id"] == "ent_kanda"
    finally:
        _cleanup()
