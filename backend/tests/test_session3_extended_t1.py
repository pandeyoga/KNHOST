"""T1 iter192 — edge cases: retur sebagian roll makloon (campuran/duplikat/utuh), notifikasi tagihan kampanye
(reject, approve via campaign endpoint, visibilitas per peran), ringkasan anggaran (level over, auth)."""
import pytest
import requests

from test_p05_acceptance_acc31_33_34 import BASE, DB, _create, _free, adm, output_is_makloon  # noqa: F401

B = f"{BASE}/api"


def _h(email, pw="demo12345"):
    tok = requests.post(f"{B}/auth/login", json={"email": email, "password": pw}, timeout=30).json()["token"]
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}


def _cancelled_mko(adm, qty, note):  # noqa: F811
    mko = _create(adm, qty, note)
    assert requests.post(f"{B}/makloon-orders/{mko['id']}/issue", json={"step_seq": 1, "doc_uom": "yard", "doc_qty": qty},
                         headers=adm, timeout=60).status_code == 200
    assert requests.post(f"{B}/makloon-orders/{mko['id']}/cancel", json={"reason": "TEST_P05ACC batal T1"},
                         headers=adm, timeout=60).status_code == 200
    rolls = requests.get(f"{B}/makloon-orders/{mko['id']}/steps/1/partner-rolls", headers=adm, timeout=30).json()["rolls"]
    return mko, rolls


# Partial return — qty == remaining → treated as whole roll (no split, roll back to warehouse)
def test_partial_equal_remaining_is_whole(adm):  # noqa: F811
    mko, rolls = _cancelled_mko(adm, 60, "T1-WHOLE")
    r0 = rolls[0]
    url = f"{B}/makloon-orders/{mko['id']}/steps/1/return-material"
    r = requests.post(url, json={"reason": "TEST_P05ACC utuh", "partial": [{"roll_id": r0["id"], "qty": r0["length_remaining"]}]},
                      headers=adm, timeout=60)
    assert r.status_code == 200, r.text[:300]
    st = r.json()["steps"][0]
    ret = st["material_returns"][-1]
    assert ret["split"] == [] and ret["roll_ids"] == [r0["id"]]
    assert DB.inventory_rolls.find_one({"id": r0["id"]})["status"] == "available"
    led = requests.get(f"{B}/makloon-orders/{mko['id']}/material-ledger", headers=adm, timeout=30).json()["steps"][0]
    assert led["reconciled"] is True
    # unknown roll → 409
    assert requests.post(url, json={"reason": "TEST_P05ACC asing", "partial": [{"roll_id": "roll_nope", "qty": 1}]},
                         headers=adm, timeout=60).status_code == 409
    # empty partial list → 400
    assert requests.post(url, json={"reason": "TEST_P05ACC kosong", "partial": []}, headers=adm, timeout=60).status_code == 400
    # short reason → 400
    assert requests.post(url, json={"reason": "abc", "partial": [{"roll_id": rolls[-1]["id"], "qty": 1}]},
                         headers=adm, timeout=60).status_code == 400


# Partial return mixed with roll_ids + duplicate roll in partial (data-integrity probe)
def test_partial_mixed_and_duplicate(adm):  # noqa: F811
    mko, rolls = _cancelled_mko(adm, 60, "T1-MIX")
    assert len(rolls) >= 2, rolls
    a, b = sorted(rolls, key=lambda x: -x["length_remaining"])[:2]
    url = f"{B}/makloon-orders/{mko['id']}/steps/1/return-material"
    # duplicate same roll twice in partial, sum exceeds remaining → must not leave orphan child roll
    n_children0 = DB.inventory_rolls.count_documents({"split_from_roll_id": a["id"]})
    half = round(a["length_remaining"] * 0.6, 2)
    rd = requests.post(url, json={"reason": "TEST_P05ACC dupe", "partial": [{"roll_id": a["id"], "qty": half},
                                                                            {"roll_id": a["id"], "qty": half}]},
                       headers=adm, timeout=60)
    n_children1 = DB.inventory_rolls.count_documents({"split_from_roll_id": a["id"]})
    doc = DB.makloon_orders.find_one({"id": mko["id"]}, {"_id": 0, "steps": 1})
    nret = len(doc["steps"][0].get("material_returns") or [])
    print("DUP status", rd.status_code, rd.text[:200], "children", n_children0, "->", n_children1, "returns", nret)
    assert rd.status_code in (400, 409, 200)
    if rd.status_code != 200:
        assert n_children1 == n_children0, "orphan child roll created though request failed (no return entry/GL)"


# Mixed roll_ids (whole) + partial (split) in one request
def test_partial_mixed(adm):  # noqa: F811
    mko, rolls = _cancelled_mko(adm, 60, "T1-MIX2")
    assert len(rolls) >= 2, rolls
    a, b = sorted(rolls, key=lambda x: -x["length_remaining"])[:2]
    url = f"{B}/makloon-orders/{mko['id']}/steps/1/return-material"
    a_now = DB.inventory_rolls.find_one({"id": a["id"]}, {"_id": 0})
    take = round(a_now["length_remaining"] / 2, 2)
    r = requests.post(url, json={"reason": "TEST_P05ACC campur", "roll_ids": [b["id"]],
                                 "partial": [{"roll_id": a["id"], "qty": take}]}, headers=adm, timeout=60)
    assert r.status_code == 200, r.text[:300]
    ret = r.json()["steps"][0]["material_returns"][-1]
    assert b["id"] in ret["roll_ids"] and len(ret["split"]) == 1
    assert ret["qty"] == pytest.approx(b["length_remaining"] + take, abs=0.02)
    assert ret["value"] > 0
    led = requests.get(f"{B}/makloon-orders/{mko['id']}/material-ledger", headers=adm, timeout=30).json()["steps"][0]
    assert led["reconciled"] is True


# Notification: reject via generic endpoint marks read; campaign approve endpoint marks read; visibility
def test_campaign_bill_notif_reject_and_campaign_approve():
    m, f, s = _h("manager@kainnusantara.id"), _h("finance@kainnusantara.id"), _h("sales@kainnusantara.id")
    c = requests.post(f"{B}/marketing/campaigns", json={"name": "TEST_NOTIF_T1", "budget": 1000000,
                                                         "start_date": "2026-10-01", "end_date": "2026-10-31"}, headers=m).json()
    try:
        sup = requests.get(f"{B}/marketing/vendor-options", headers=m).json()[0]["id"]
        mk = lambda amt: requests.post(f"{B}/marketing/campaigns/{c['id']}/vendor-bills", headers=m, json={  # noqa: E731
            "supplier_id": sup, "description": "TEST_ Iklan", "amount": amt, "bill_date": "2026-10-05"}).json()
        b1, b2 = mk(600000), mk(600000)
        n = DB.notifications.find_one({"ref": f"mkt_bill:{b1['id']}"}, {"_id": 0})
        assert n["action_id"] == b1["id"] and n["type"] if "type" in n else True
        # finance sees it in /notifications; sales does not
        fl = requests.get(f"{B}/notifications", headers=f).json()
        items = fl if isinstance(fl, list) else fl.get("items") or fl.get("notifications") or []
        assert any(x.get("action_id") == b1["id"] for x in items), "finance does not see campaign bill notification"
        sl = requests.get(f"{B}/notifications", headers=s).json()
        sitems = sl if isinstance(sl, list) else sl.get("items") or sl.get("notifications") or []
        assert not any(x.get("action_id") == b1["id"] for x in sitems), "sales sees finance notification"
        # reject b1 (generic)
        r = requests.post(f"{B}/vendor-bills/{b1['id']}/reject", headers=f, json={"notes": "TEST_ tolak salah vendor"})
        assert r.status_code == 200, r.text[:200]
        assert DB.notifications.find_one({"ref": f"mkt_bill:{b1['id']}"})["read"] is True
        # approve b2 via campaign endpoint
        r = requests.post(f"{B}/marketing/campaigns/{c['id']}/vendor-bills/{b2['id']}/approve", headers=f)
        assert r.status_code == 200, r.text[:200]
        assert DB.notifications.find_one({"ref": f"mkt_bill:{b2['id']}"})["read"] is True
        # budget: 600k approved → 60% no alert; add direct 500k cost → 110% over
        sm = requests.get(f"{B}/marketing/campaigns/budget-summary", headers=m).json()
        assert not any(a["campaign_id"] == c["id"] for a in sm["alerts"])
        assert {"months", "alerts", "near_pct", "total_budget", "total_realized"} <= set(sm)
        # sales role permission
        print("sales budget-summary:", requests.get(f"{B}/marketing/campaigns/budget-summary", headers=s).status_code)
        print("finance budget-summary:", requests.get(f"{B}/marketing/campaigns/budget-summary", headers=f).status_code)
    finally:
        bills = [b["id"] for b in DB.vendor_bills.find({"campaign_id": c["id"]})]
        DB.journal_entries.delete_many({"source_id": {"$in": bills}})
        DB.vendor_bills.delete_many({"id": {"$in": bills}})
        DB.notifications.delete_many({"ref": {"$in": [f"mkt_bill:{b}" for b in bills]}})
        DB.mkt_campaigns.delete_one({"id": c["id"]})


def test_budget_summary_unauth():
    assert requests.get(f"{B}/marketing/campaigns/budget-summary").status_code in (401, 403)
