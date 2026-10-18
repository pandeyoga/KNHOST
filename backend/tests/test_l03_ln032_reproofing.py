"""L03 LN-032 — proofing berulang artwork sama, ACC sekali, revalidation tidak ganda, polos tetap labdip/handfeel."""
import copy
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
CUST = "cust_toko_kain"
TPL = DB.product_templates.find_one({"status": "active"}, {"id": 1}, sort=[("name", 1)])["id"]
TAG = uuid.uuid4().hex[:6]
D_OD = f"dsgn_TEST_x32_{TAG}"
CREATED_OD, CREATED_SMP = [], []


def _login(email, pw="demo1234"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


@pytest.fixture(scope="module")
def H():
    return {"admin": _login("admin@kainnusantara.id", "demo12345"), "manager": _login("manager@kainnusantara.id")}


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    DB.md_samples.delete_many({"$or": [{"special_order_id": {"$in": CREATED_OD}}, {"id": {"$in": CREATED_SMP}}]})
    DB.special_orders.delete_many({"id": {"$in": CREATED_OD}})
    DB.design_requests.delete_many({"special_order_id": {"$in": CREATED_OD}})
    DB.design_gallery.delete_many({"id": D_OD})


def _od(H, types, title):
    body = {"customer_id": CUST, "title": f"TEST_{title}_{TAG}", "entity_id": ENT, "expected_delivery": "2026-12-31",
            "items": [{"source_type": "parent_product", "source_template_id": TPL, "description": f"TEST {title}",
                       "request_types": types, "quantity": 20}], "submit_for_approval": True}
    r = requests.post(f"{BASE}/special-orders", json=body, headers=H["admin"])
    assert r.status_code in (200, 201), r.text
    od_id = r.json()["id"]
    CREATED_OD.append(od_id)
    assert requests.post(f"{BASE}/special-orders/{od_id}/approve", json={"notes": "TEST"}, headers=H["admin"]).status_code == 200
    return od_id


def _decide_all(od_id):
    DB.md_samples.update_many({"special_order_id": od_id, "status": {"$nin": ["cancelled", "decided"]}},
                              {"$set": {"status": "decided"}})
    od = DB.special_orders.find_one({"id": od_id})
    DB.md_samples.update_many({"id": {"$in": od.get("sample_ids") or []}, "status": {"$nin": ["cancelled", "decided"]}},
                              {"$set": {"status": "decided"}})


def _review(H, od_id):
    return (requests.get(f"{BASE}/special-orders/{od_id}", headers=H["admin"]).json().get("chain") or {}).get("review") or {}


def _decide(H, od_id, decision, note="TEST", who="admin"):
    return requests.post(f"{BASE}/special-orders/{od_id}/customer-decision",
                         json={"decision": decision, "note": note, "decided_at": "2026-10-18"}, headers=H[who])


def test_printing_reproofing_two_rejections_then_acc_same_artwork(H):
    od_id = _od(H, ["printing"], "P32")
    od = DB.special_orders.find_one({"id": od_id})
    dr_id = od["items"][0].get("design_request_id") or od.get("design_request_id")
    src = copy.deepcopy(DB.design_gallery.find_one({"entity_id": ENT, "id": {"$not": {"$regex": "^dsgn_TEST_"}}}, {"_id": 0}))
    src.update({"id": D_OD, "code": f"T32-{TAG}", "title": f"TEST_{D_OD}", "status": "in_review", "request_id": dr_id,
                "origin": "", "on_hold": False, "hold": {}, "version": 2,
                "versions": [{"version": 1}, {"version": 2}], "timeline": []})
    DB.design_gallery.insert_one(src)
    DB.design_requests.update_one({"id": dr_id}, {"$set": {"design_id": D_OD}, "$addToSet": {"gallery_ids": D_OD}})
    if not od.get("design_request_id"):
        DB.special_orders.update_one({"id": od_id}, {"$set": {"design_request_id": dr_id}})
    assert requests.post(f"{BASE}/design-gallery/{D_OD}/lifecycle/approve", json={"score": 1.75, "note": "ACC"},
                         headers=H["admin"]).status_code == 200
    # T01 — desain ACC tidak langsung jadi dasar ACC pelanggan; proofing dibuat.
    rv = _review(H, od_id)
    assert rv["ready"] is False and rv["object"] == "proofing" and len(rv["proofing_rounds"]) == 1
    assert _decide(H, od_id, "acc").status_code == 400

    for rnd in (2, 3):
        _decide_all(od_id)
        r = _decide(H, od_id, "revisi", note=f"warna kurang tajam #{rnd}")
        assert r.status_code == 200, r.text
        rv = _review(H, od_id)
        assert rv["ready"] is False and len(rv["proofing_rounds"]) == rnd
    rounds = list(DB.md_samples.find({"special_order_id": od_id, "sample_types": "proofing"}).sort("created_at", 1))
    assert [s.get("proofing_round") for s in rounds] == [1, 2, 3]
    assert {s.get("design_id") for s in rounds} == {D_OD}
    assert {s.get("design_version") for s in rounds} == {2}
    assert all(s["sample_types"] == ["proofing"] for s in rounds)

    _decide_all(od_id)
    with ThreadPoolExecutor(2) as ex:
        res = list(ex.map(lambda w: _decide(H, od_id, "acc", who=w), ["admin", "manager"]))
    assert sorted(x.status_code for x in res)[0] == 200 and [x.status_code for x in res].count(200) == 1, [x.text for x in res]
    assert _decide(H, od_id, "acc").status_code == 400
    doc = DB.special_orders.find_one({"id": od_id})
    accs = [d for d in doc["customer_decisions"] if d["decision"] == "acc"]
    assert len(accs) == 1 and accs[0]["object"] == "proofing"
    assert len([d for d in doc["customer_decisions"] if d["decision"] == "revisi"]) == 2


def test_concurrent_revisi_creates_one_round(H):
    od_id = _od(H, ["labdip"], "C32")
    _decide_all(od_id)
    with ThreadPoolExecutor(2) as ex:
        res = list(ex.map(lambda w: _decide(H, od_id, "revisi", note="kurang", who=w), ["admin", "manager"]))
    assert [x.status_code for x in res].count(200) == 1, [x.text for x in res]
    doc = DB.special_orders.find_one({"id": od_id})
    assert len(doc.get("customer_decisions") or []) == 1


def test_plain_order_keeps_line_tests_no_proofing(H):
    od_id = _od(H, ["labdip", "handfeel"], "N32")
    _decide_all(od_id)
    assert _review(H, od_id)["ready"] is True
    r = _decide(H, od_id, "revisi", note="handfeel kurang lembut")
    assert r.status_code == 200, r.text
    new = DB.md_samples.find_one({"id": r.json()["decision"]["revision_sample_id"]})
    assert "proofing" not in new["sample_types"] and set(new["sample_types"]) <= {"labdip", "handfeel"}
    assert not new.get("design_id") and not new.get("proofing_round")
    rv = _review(H, od_id)
    assert rv["ready"] is False and rv["object"] == "sample" and rv["proofing_rounds"] == []
    assert DB.md_samples.count_documents({"special_order_id": od_id, "sample_types": "proofing"}) == 0


def test_concurrent_revalidation_existing_sku_no_duplicate(H):
    prod = DB.products.find_one({"status": "active", "sku": {"$nin": ["", None]}}, {"_id": 0, "id": 1, "sku": 1, "line_code": 1})
    DB.md_samples.update_many({"product_id": prod["id"], "purpose": "revalidation", "status": {"$nin": ["decided", "cancelled"]}},
                              {"$set": {"status": "cancelled"}, "$unset": {"open_reval_keys": ""}})
    body = {"product_id": prod["id"], "sample_types": ["handfeel"], "title": f"TEST_reval_{TAG}", "qty_requested": 1,
            "revalidation_supplier_id": DB.suppliers.find_one({"entity_id": "all"}, {"_id": 0, "id": 1}, sort=[("name", 1)])["id"],
            "revalidation_reason": f"TEST_reval_{TAG}"}
    with ThreadPoolExecutor(3) as ex:
        res = list(ex.map(lambda _: requests.post(f"{BASE}/rnd/samples", json=body, headers=H["admin"]), range(3)))
    ok = [x for x in res if x.status_code in (200, 201)]
    CREATED_SMP.extend(x.json().get("id") for x in ok)
    assert len(ok) == 1, [x.text for x in res]
    assert all(x.status_code in (400, 409) for x in res if x not in ok)
    s = DB.md_samples.find_one({"id": ok[0].json()["id"]})
    assert s["purpose"] == "revalidation" and s.get("product_sku") == prod["sku"]
    assert proofing_rejected(H, prod["id"])


def proofing_rejected(H, pid):
    r = requests.post(f"{BASE}/rnd/samples", json={"product_id": pid, "sample_types": ["proofing"], "title": "TEST_x"}, headers=H["admin"])
    return r.status_code == 400
