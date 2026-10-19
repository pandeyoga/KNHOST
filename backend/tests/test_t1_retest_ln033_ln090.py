"""T1 retest — LN-033 T08 cancel→re-realize same route; LN-090 cancel replacement SO reverses credit."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import requests  # noqa: E402
import test_l03_ln033_fulfillment as m  # noqa: E402
import test_ln090_replacement_order as r9  # noqa: E402

H = m.H
cleanup = m.cleanup
teardown_module = r9.teardown_module


# LN-033 T08 — cancel archives PO+PR, status ready, same-route realize creates new PR+PO
def test_ln033_cancel_then_rerealize_same_route(H):
    od_id, (k,) = m._od(H, [m.P_SUP])
    r = m._realize(H, od_id, k)
    assert r.status_code == 200, r.text
    po1 = r.json()["result"]["doc"]["id"]
    pr1 = m.DB.special_orders.find_one({"id": od_id})["fulfillment"][k]["pr_id"]
    assert pr1
    c = requests.post(f"{m.BASE}/special-orders/{od_id}/fulfillment/{k}/cancel", json={"reason": "TEST batal ulang"}, headers=H["admin"])
    assert c.status_code == 200, c.text
    assert m.DB.purchase_orders.find_one({"id": po1})["status"] == "cancelled"
    assert m.DB.purchase_requisitions.find_one({"id": pr1})["source_item_key"] == f"{k}#retired"
    n = m._ful(H, od_id)[k]
    assert n["status"] == "ready", n["status"]
    assert not n["active_docs"]
    hist_ids = {d["id"] for d in n["history_docs"]}
    assert po1 in hist_ids and pr1 in hist_ids
    assert all(d["id"] not in (po1,) for d in n.get("docs") or [])
    # second cancel with nothing active -> 400
    c2 = requests.post(f"{m.BASE}/special-orders/{od_id}/fulfillment/{k}/cancel", json={"reason": "TEST lagi"}, headers=H["admin"])
    assert c2.status_code == 400
    r2 = m._realize(H, od_id, k)
    assert r2.status_code == 200, r2.text
    po2 = r2.json()["result"]["doc"]["id"]
    pr2 = m.DB.special_orders.find_one({"id": od_id})["fulfillment"][k]["pr_id"]
    assert po2 != po1 and pr2 and pr2 != pr1
    assert m.DB.purchase_orders.find_one({"id": po2})["status"] != "cancelled"
    n2 = m._ful(H, od_id)[k]
    assert [d["id"] for d in n2["active_docs"]] == [po2]


# LN-090 — cancelling replacement SO voids redemption, restores balance, allows new replacement
def test_ln090_cancel_replacement_balance_restored():
    so, rid, pid = r9._seed(accepted=5.0)
    cust = m.DB.sales_returns.find_one({"id": rid})["customer_id"]
    r9._issue(rid, cust, 150000)
    r = requests.post(f"{r9.BASE}/sales-returns/{rid}/replacement-order", headers=r9.ADMIN, json={"items": [{"product_id": pid, "qty_yard": 5}]})
    assert r.status_code == 200, r.text
    new_id = r.json()["order"]["id"]
    applied1 = r.json()["summary"]["credit_applied"]
    assert applied1 > 0
    red = m.DB.store_credit_redemptions.find_one({"allocations.order_id": new_id}, {"_id": 0})
    assert red and red.get("status") != "void"
    c = requests.post(f"{r9.BASE}/sales-orders/{new_id}/cancel", headers=r9.ADMIN, json={"reason": "TEST batal pengganti"})
    assert c.status_code == 200, c.text
    red = m.DB.store_credit_redemptions.find_one({"id": red["id"]}, {"_id": 0})
    assert red["status"] == "void", red
    ret = m.DB.sales_returns.find_one({"id": rid})
    assert ret.get("replacement_order_id") in ("", None)
    assert ret["replacement_history"][-1]["order_id"] == new_id
    r2 = requests.post(f"{r9.BASE}/sales-returns/{rid}/replacement-order", headers=r9.ADMIN, json={"items": [{"product_id": pid, "qty_yard": 5}]})
    assert r2.status_code == 200, r2.text
    assert r2.json()["summary"]["credit_applied"] == applied1
    assert r2.json()["order"]["id"] != new_id
    # cleanup redemptions created here
    m.DB.store_credit_redemptions.delete_many({"allocations.order_id": {"$in": [new_id, r2.json()["order"]["id"]]}})
