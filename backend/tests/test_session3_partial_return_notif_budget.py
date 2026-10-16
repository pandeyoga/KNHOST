"""Sesi 2026-10-16 bag.3 — retur SEBAGIAN roll makloon (roll anak), notifikasi tagihan kampanye ke Finance,
ringkasan anggaran kampanye per bulan + peringatan ≥80%."""
import pytest
import requests

import test_p05_acceptance_acc31_33_34 as P
from test_p05_acceptance_acc31_33_34 import BASE, DB, _create, _free, adm, output_is_makloon  # noqa: F401

B = f"{BASE}/api"


def test_partial_roll_return_splits_child(adm):  # noqa: F811
    t = P._tpl()
    pid, wh = t["material_product_id"], t["from_warehouse_id"]
    mko = _create(adm, 60, "LN043-PARTIAL")
    assert requests.post(f"{B}/makloon-orders/{mko['id']}/issue", json={"step_seq": 1, "doc_uom": "yard", "doc_qty": 60},
                         headers=adm, timeout=60).status_code == 200
    assert requests.post(f"{B}/makloon-orders/{mko['id']}/cancel", json={"reason": "TEST_P05ACC batal parsial"},
                         headers=adm, timeout=60).status_code == 200
    free0 = _free(pid, wh)
    rolls = requests.get(f"{B}/makloon-orders/{mko['id']}/steps/1/partner-rolls", headers=adm, timeout=30).json()["rolls"]
    big = max(rolls, key=lambda r: r["length_remaining"])
    take = round(big["length_remaining"] - 10.5, 2)
    url = f"{B}/makloon-orders/{mko['id']}/steps/1/return-material"
    assert requests.post(url, json={"reason": "TEST_P05ACC lebih", "partial": [{"roll_id": big["id"], "qty": big["length_remaining"] + 5}]},
                         headers=adm, timeout=60).status_code == 400
    assert requests.post(url, json={"reason": "TEST_P05ACC nol", "partial": [{"roll_id": big["id"], "qty": 0}]},
                         headers=adm, timeout=60).status_code == 400
    r = requests.post(url, json={"reason": "TEST_P05ACC kembali sebagian", "partial": [{"roll_id": big["id"], "qty": take}]},
                      headers=adm, timeout=60)
    assert r.status_code == 200, r.text[:300]
    ret = r.json()["steps"][0]["material_returns"][-1]
    assert ret["qty"] == pytest.approx(take) and len(ret["split"]) == 1
    child = DB.inventory_rolls.find_one({"id": ret["split"][0]["child_roll_id"]}, {"_id": 0})
    parent = DB.inventory_rolls.find_one({"id": big["id"]}, {"_id": 0})
    assert child["status"] == "available" and child["length_remaining"] == pytest.approx(take)
    assert child["roll_no"] != parent["roll_no"] and child.get("split_from_roll_id") == big["id"]
    assert parent["status"] == "subcon" and parent["length_remaining"] == pytest.approx(10.5, abs=0.01)
    assert _free(pid, wh) == pytest.approx(free0 + take, abs=0.05)
    led = requests.get(f"{B}/makloon-orders/{mko['id']}/material-ledger", headers=adm, timeout=30).json()
    st = led["steps"][0]
    assert st["returned"] == pytest.approx(take, abs=0.01) and st["reconciled"] is True
    assert st["at_partner"] == pytest.approx(60 - take, abs=0.05)
    # retur ulang roll anak yang sudah di gudang → ditolak
    assert requests.post(url, json={"reason": "TEST_P05ACC ulang", "partial": [{"roll_id": child["id"], "qty": 1}]},
                         headers=adm, timeout=60).status_code == 409


def _h(email, pw="demo1234"):
    tok = requests.post(f"{B}/auth/login", json={"email": email, "password": pw}, timeout=30).json()["token"]
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}


def test_campaign_bill_notifies_finance_and_budget_summary():
    m, f = _h("manager@kainnusantara.id"), _h("finance@kainnusantara.id")
    c = requests.post(f"{B}/marketing/campaigns", json={"name": "TEST_NOTIF", "budget": 1000000,
                                                         "start_date": "2026-09-01", "end_date": "2026-10-31"}, headers=m).json()
    try:
        sup = requests.get(f"{B}/marketing/vendor-options", headers=m).json()[0]["id"]
        bill = requests.post(f"{B}/marketing/campaigns/{c['id']}/vendor-bills", headers=m, json={
            "supplier_id": sup, "description": "Iklan TikTok", "amount": 850000, "bill_date": "2026-10-05"}).json()
        n = DB.notifications.find_one({"ref": f"mkt_bill:{bill['id']}"}, {"_id": 0})
        assert n and n["recipient_role"] == "finance" and n["action_type"] == "vendor_bill_approve" and not n["read"]
        r = requests.post(f"{B}/vendor-bills/{bill['id']}/approve", headers=f)       # aksi inline dari notifikasi
        assert r.status_code == 200 and r.json()["status"] == "posted", r.text[:200]
        assert DB.notifications.find_one({"ref": f"mkt_bill:{bill['id']}"})["read"] is True
        s = requests.get(f"{B}/marketing/campaigns/budget-summary", headers=m).json()
        months = {x["month"]: x for x in s["months"]}
        assert months["2026-09"]["budget"] >= 500000 and months["2026-10"]["realized"] >= 850000
        a = next(x for x in s["alerts"] if x["campaign_id"] == c["id"])
        assert a["level"] == "near" and a["pct"] == 85.0 and a["remaining"] == 150000
    finally:
        bills = [b["id"] for b in DB.vendor_bills.find({"campaign_id": c["id"]})]
        DB.journal_entries.delete_many({"source_id": {"$in": bills}})
        DB.vendor_bills.delete_many({"id": {"$in": bills}})
        DB.notifications.delete_many({"ref": {"$in": [f"mkt_bill:{b}" for b in bills]}})
        DB.mkt_campaigns.delete_one({"id": c["id"]})
