"""T1 — LN-033 T08 edge: cancel MKO path + re-realize same route after cancel."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pytest  # noqa: E402
import requests  # noqa: E402
import test_l03_ln033_fulfillment as m  # noqa: E402

H = m.H
cleanup = m.cleanup


def test_cancel_mko_then_history(H):
    m._recipe()
    od_id, (k,) = m._od(H, [m.P_MKL])
    r = m._realize(H, od_id, k)
    assert r.status_code == 200, r.text
    doc = r.json()["result"]["doc"]
    assert doc.get("type", "mko") == "mko" or m.DB.makloon_orders.find_one({"id": doc["id"]})
    c = requests.post(f"{m.BASE}/special-orders/{od_id}/fulfillment/{k}/cancel", json={"reason": "TEST makloon batal"}, headers=H["admin"])
    assert c.status_code == 200, c.text
    mko = m.DB.makloon_orders.find_one({"id": doc["id"]}, {"_id": 0, "status": 1})
    assert mko and mko["status"] == "cancelled", mko
    assert m.DB.material_reservations.count_documents({"ref_id": doc["id"], "status": "active"}) == 0
    n = m._ful(H, od_id)[k]
    assert not n["active_docs"]


def test_rerealize_same_route_after_cancel(H):
    od_id, (k,) = m._od(H, [m.P_SUP])
    assert m._realize(H, od_id, k).status_code == 200
    c = requests.post(f"{m.BASE}/special-orders/{od_id}/fulfillment/{k}/cancel", json={"reason": "TEST batal ulang"}, headers=H["admin"])
    assert c.status_code == 200
    n = m._ful(H, od_id)[k]
    if n["status"] in ("ready", "error"):
        r = m._realize(H, od_id, k)
        assert r.status_code == 200, f"UI offers realize but API fails: {r.status_code} {r.text[:200]}"
