"""L03 LN-030 — retest of iteration_218 fixes (redesign source rejected, item spec on design ACC,
approve returns chain, proofing_sample_id idempotency, parent_design_code)."""
import asyncio
import copy
import os
import sys
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
CUST = "cust_toko_kain"
TPL_A, TPL_B = [t["id"] for t in DB.product_templates.find({"status": "active"}, {"id": 1}).sort("name", 1).limit(2)]
TAG = uuid.uuid4().hex[:6]
D_OK = f"dsgn_TEST_fx_ok_{TAG}"
D_HOLD = f"dsgn_TEST_fx_hold_{TAG}"
D_FLIP = f"dsgn_TEST_fx_flip_{TAG}"
CREATED = []


def _design(did, code, hold=False, status="approved", entity=ENT):
    base = copy.deepcopy(DB.design_gallery.find_one({"id": {"$not": {"$regex": "^dsgn_TEST_"}}}, {"_id": 0}))
    base.update({"id": did, "code": code, "title": f"TEST_{code}", "status": status, "entity_id": entity,
                 "request_id": "", "request_number": "", "origin": "",
                 "on_hold": hold, "hold": {"reason": "TEST hold"} if hold else {}})
    DB.design_gallery.insert_one(base)


def _cleanup():
    ods = [o["id"] for o in DB.special_orders.find({"$or": [{"id": {"$in": CREATED}}, {"title": {"$regex": "^TEST_"}},
                                                             {"redesign_of.special_order_id": {"$in": CREATED}}]}, {"id": 1})]
    smp = list(DB.md_samples.find({"special_order_id": {"$in": ods}}, {"spec_id": 1}))
    spec_ids = [s.get("spec_id") for s in smp if s.get("spec_id")]
    for o in DB.special_orders.find({"id": {"$in": ods}}, {"items.spec_id": 1, "spec_id": 1}):
        spec_ids += [i.get("spec_id") for i in o.get("items") or [] if i.get("spec_id")] + [o.get("spec_id")]
    DB.md_samples.delete_many({"special_order_id": {"$in": ods}})
    DB.rnd_specs.delete_many({"id": {"$in": spec_ids}})
    DB.md_specs.delete_many({"$or": [{"id": {"$in": spec_ids}}, {"title": {"$regex": "^TEST"}}]})
    DB.design_requests.delete_many({"special_order_id": {"$in": ods}})
    DB.special_orders.delete_many({"id": {"$in": ods}})
    DB.design_gallery.delete_many({"id": {"$regex": "^dsgn_TEST_"}})


@pytest.fixture(scope="module", autouse=True)
def fixtures():
    _design(D_OK, f"TFX-OK-{TAG}")
    _design(D_HOLD, f"TFX-HOLD-{TAG}", hold=True)
    _design(D_FLIP, f"TFX-FLIP-{TAG}")
    yield
    _cleanup()


@pytest.fixture(scope="module")
def H():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


def _create(H, items, submit=True):
    body = {"customer_id": CUST, "title": f"TEST_FX_{TAG}", "entity_id": ENT, "expected_delivery": "2026-12-31",
            "items": items, "submit_for_approval": submit}
    r = requests.post(f"{BASE}/special-orders", json=body, headers=H)
    if r.status_code in (200, 201):
        CREATED.append(r.json()["id"])
    return r


# FIX 1 — client may never send source_type=redesign
@pytest.mark.parametrize("did", ["OK", "HOLD"])
def test_redesign_source_rejected(H, did):
    d = D_OK if did == "OK" else D_HOLD
    r = _create(H, [{"source_type": "redesign", "source_design_id": d, "request_types": ["printing"], "quantity": 5}])
    assert r.status_code == 400, r.text
    assert "Ubah motif" in r.text or "sumber" in r.text.lower()


# FIX 3 — approve response includes chain.items
def test_approve_returns_chain(H):
    r = _create(H, [{"source_type": "parent_product", "source_template_id": TPL_A, "description": "TEST A",
                     "request_types": ["labdip"], "quantity": 10},
                    {"source_type": "approved_artwork", "source_design_id": D_OK, "description": "TEST B",
                     "request_types": ["printing"], "quantity": 10}])
    assert r.status_code in (200, 201), r.text
    od = r.json()
    a = requests.post(f"{BASE}/special-orders/{od['id']}/approve", json={"notes": "TEST"}, headers=H)
    assert a.status_code == 200, a.text
    d = a.json()
    assert d["status"] != "pending_approval"
    assert "chain" in d and isinstance(d["chain"].get("items"), list), list(d.keys())
    assert len(d["chain"]["items"]) == 2
    item_ids = {i["id"] for i in od["items"]}
    assert {c.get("item_id") or c.get("id") for c in d["chain"]["items"]} <= item_ids | {None}


# FIX 4 — proofing retried exactly once after artwork HOLD released
def test_proofing_retry_after_hold_release(H):
    r = _create(H, [{"source_type": "approved_artwork", "source_design_id": D_FLIP, "description": "TEST flip",
                     "request_types": ["printing", "labdip"], "quantity": 10}])
    assert r.status_code in (200, 201), r.text
    od_id = r.json()["id"]
    DB.design_gallery.update_one({"id": D_FLIP}, {"$set": {"on_hold": True, "hold": {"reason": "TEST hold"}}})
    a = requests.post(f"{BASE}/special-orders/{od_id}/approve", json={"notes": "TEST"}, headers=H)
    assert a.status_code == 200, a.text
    it = DB.special_orders.find_one({"id": od_id})["items"][0]
    assert it.get("rnd_sample_id"), "labdip should succeed"
    assert not it.get("proofing_sample_id"), "proofing should fail while HOLD"
    assert DB.md_samples.count_documents({"special_order_id": od_id, "sample_types": "proofing"}) == 0
    DB.design_gallery.update_one({"id": D_FLIP}, {"$set": {"on_hold": False, "hold": {}}})
    for _ in range(2):
        rr = requests.post(f"{BASE}/special-orders/{od_id}/route", json={}, headers=H)
        assert rr.status_code == 200, rr.text
    it = DB.special_orders.find_one({"id": od_id})["items"][0]
    assert it.get("proofing_sample_id")
    prf = list(DB.md_samples.find({"special_order_id": od_id, "sample_types": "proofing", "status": {"$ne": "cancelled"}}))
    assert len(prf) == 1 and prf[0]["id"] == it["proofing_sample_id"] and prf[0]["design_id"] == D_FLIP
    assert DB.md_samples.count_documents({"special_order_id": od_id, "sample_types": "labdip"}) == 1


# FIX 5 (backend) — redesign OD design request carries parent_design_code
def test_redesign_parent_design_code(H):
    r = _create(H, [{"source_type": "approved_artwork", "source_design_id": D_OK, "request_types": ["printing"], "quantity": 5}])
    od = r.json()
    requests.post(f"{BASE}/special-orders/{od['id']}/approve", json={"notes": "TEST"}, headers=H)
    rd = requests.post(f"{BASE}/special-orders/{od['id']}/redesign",
                       json={"item_id": od["items"][0]["id"], "reason": "TEST ganti motif"}, headers=H)
    assert rd.status_code in (200, 201), rd.text
    rd = rd.json()
    CREATED.append(rd["id"])
    requests.post(f"{BASE}/special-orders/{rd['id']}/submit", json={}, headers=H)
    a = requests.post(f"{BASE}/special-orders/{rd['id']}/approve", json={"notes": "TEST"}, headers=H)
    assert a.status_code == 200, a.text
    dr = DB.design_requests.find_one({"special_order_id": rd["id"]})
    assert dr and dr.get("parent_design_id") == D_OK
    assert dr.get("parent_design_code") == f"TFX-OK-{TAG}", dr.get("parent_design_code")


# FIX 2 — on_design_approved uses item's own spec, OD spec_id untouched
def test_on_design_approved_item_spec(H):
    r = _create(H, [{"source_type": "parent_product", "source_template_id": TPL_A, "description": "TEST A labdip",
                     "request_types": ["labdip"], "quantity": 10},
                    {"source_type": "parent_product", "source_template_id": TPL_B, "description": "TEST B printing",
                     "request_types": ["printing"], "quantity": 20}])
    od_id = r.json()["id"]
    assert requests.post(f"{BASE}/special-orders/{od_id}/approve", json={}, headers=H).status_code == 200
    od = DB.special_orders.find_one({"id": od_id}, {"_id": 0})
    od_spec_before = od.get("spec_id")
    itA, itB = od["items"]
    design = {"id": f"dsgn_TEST_fx_acc_{TAG}", "code": f"TFX-ACC-{TAG}", "request_id": itB["design_request_id"], "version": 1}
    DB.design_gallery.insert_one({**design, "status": "approved", "entity_id": ENT, "title": "TEST acc"})
    sys.path.insert(0, "/app/backend")
    from services import special_order_phase2 as p2  # noqa: E402

    async def run():
        s1 = await p2.on_design_approved(dict(design), {"name": "t", "email": "t"})
        s2 = await p2.on_design_approved(dict(design), {"name": "t", "email": "t"})
        return s1, s2
    s1, s2 = asyncio.run(run())
    assert s1 and s2 is None
    smp = DB.md_samples.find_one({"id": s1["id"]})
    assert smp["special_order_item_id"] == itB["id"]
    assert smp["spec_id"] != itA.get("spec_id")
    spec = DB.rnd_specs.find_one({"id": smp["spec_id"]}) or DB.md_specs.find_one({"id": smp["spec_id"]})
    assert spec and spec.get("template_id") == TPL_B, spec and spec.get("template_id")
    after = DB.special_orders.find_one({"id": od_id})
    assert after.get("spec_id") == od_spec_before
    assert after["items"][1].get("spec_id") == smp["spec_id"]
