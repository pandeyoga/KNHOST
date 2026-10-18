"""L03 LN-031 (iter220) — paper check: ownership/role/archived/concurrency; ACC race on OD-linked design
(proofing tidak ganda); objek keputusan pelanggan di chain.review & customer_decisions."""
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
DESIGNER_ID = DB.users.find_one({"email": "designer@kainnusantara.id"})["id"]
D_OWN = f"dsgn_TEST_x31own_{TAG}"
D_OTHER = f"dsgn_TEST_x31oth_{TAG}"
D_ARCH = f"dsgn_TEST_x31arc_{TAG}"
D_CONC = f"dsgn_TEST_x31con_{TAG}"
D_OD = f"dsgn_TEST_x31od_{TAG}"
CREATED_OD = []


def _login(email, pw="demo1234"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


def _design(did, status="draft", owner="", versions=None, request_id=""):
    src = DB.design_gallery.find_one({"entity_id": ENT, "id": {"$not": {"$regex": "^dsgn_TEST_"}}}, {"_id": 0}) or {}
    base = copy.deepcopy(src)
    versions = versions or [{"version": 1, "note": "awal"}]
    base.update({"id": did, "code": f"TX31-{did[-10:]}", "title": f"TEST_{did}", "status": status, "entity_id": ENT,
                 "request_id": request_id, "origin": "", "on_hold": False, "hold": {}, "version": len(versions),
                 "versions": versions, "timeline": [], "created_by_id": owner})
    DB.design_gallery.insert_one(base)


def _cleanup():
    ods = [o["id"] for o in DB.special_orders.find({"$or": [{"id": {"$in": CREATED_OD}}, {"title": {"$regex": f"^TEST_X31_{TAG}"}}]}, {"id": 1})]
    smp = list(DB.md_samples.find({"special_order_id": {"$in": ods}}, {"spec_id": 1}))
    spec_ids = [s.get("spec_id") for s in smp if s.get("spec_id")]
    for o in DB.special_orders.find({"id": {"$in": ods}}, {"items.spec_id": 1, "spec_id": 1}):
        spec_ids += [i.get("spec_id") for i in o.get("items") or [] if i.get("spec_id")] + [o.get("spec_id")]
    DB.md_samples.delete_many({"special_order_id": {"$in": ods}})
    DB.rnd_specs.delete_many({"id": {"$in": spec_ids}})
    DB.md_specs.delete_many({"id": {"$in": spec_ids}})
    DB.design_requests.delete_many({"special_order_id": {"$in": ods}})
    DB.special_orders.delete_many({"id": {"$in": ods}})
    DB.design_gallery.delete_many({"id": {"$regex": f"^dsgn_TEST_x31.*_{TAG}$"}})


@pytest.fixture(scope="module", autouse=True)
def fixtures():
    _design(D_OWN, owner=DESIGNER_ID)
    _design(D_OTHER, owner="user_someone_else")
    _design(D_ARCH, status="archived")
    _design(D_CONC, versions=[{"version": 1}, {"version": 2}])
    yield
    _cleanup()


@pytest.fixture(scope="module")
def H():
    return {"admin": _login("admin@kainnusantara.id", "demo12345"), "manager": _login("manager@kainnusantara.id"),
            "designer": _login("designer@kainnusantara.id"), "sales": _login("sales@kainnusantara.id"),
            "md": _login("md@kainnusantara.id")}


def _paper(h, did, v, checked=True, note=""):
    return requests.post(f"{BASE}/design-gallery/{did}/rounds/{v}/paper", json={"checked": checked, "note": note}, headers=h)


# Paper — meta can_paper_check per role
def test_meta_can_paper_check(H):
    for role, exp in (("admin", True), ("manager", True), ("designer", True), ("sales", False)):
        r = requests.get(f"{BASE}/design-studio/meta", headers=H[role])
        if r.status_code == 403:
            assert not exp, f"{role} cannot read meta"
            continue
        assert r.status_code == 200, (role, r.text)
        assert r.json()["can_paper_check"] is exp, role


# Paper — designer owns vs foreign design
def test_designer_ownership(H):
    r = _paper(H["designer"], D_OWN, 1, True, "TEST cetak A4")
    assert r.status_code == 200, r.text
    p = r.json()["rounds"][0]["paper"]
    assert p["checked"] is True and p["note"] == "TEST cetak A4" and p["user_id"] == DESIGNER_ID
    r2 = _paper(H["designer"], D_OTHER, 1, True)
    assert r2.status_code == 403, r2.text


def test_md_role_forbidden(H):
    r = _paper(H["md"], D_OWN, 1, False)
    assert r.status_code == 403, r.text


def test_archived_and_missing(H):
    assert _paper(H["admin"], D_ARCH, 1).status_code == 400
    assert _paper(H["admin"], f"dsgn_TEST_nope_{TAG}", 1).status_code == 404


# Paper — concurrent double click: exactly one history entry/timeline event
def test_concurrent_paper_clicks(H):
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda _: _paper(H["admin"], D_CONC, 2, True), range(6)))
    assert all(r.status_code == 200 for r in res), [r.text for r in res]
    doc = DB.design_gallery.find_one({"id": D_CONC})
    assert len((doc.get("round_paper_history") or {}).get("2") or []) == 1
    assert sum(1 for e in doc["timeline"] if e["event"] == "paper_check") == 1
    assert not (doc.get("round_papers") or {}).get("1")
    # uncheck recorded, status unchanged, no acc
    r = _paper(H["admin"], D_CONC, 2, False)
    assert r.status_code == 200
    doc = DB.design_gallery.find_one({"id": D_CONC})
    v2 = next(v for v in doc["versions"] if v["version"] == 2)
    assert [h["checked"] for h in doc["round_paper_history"]["2"]] == [True, False]
    assert sum(1 for e in doc["timeline"] if e["event"] == "paper_uncheck") == 1
    assert doc["status"] == "draft" and not v2.get("acc")


# ACC race on OD-linked design → one 200, one proofing sample; then review object & customer decision object
def test_od_design_acc_race_and_decision_object(H):
    body = {"customer_id": CUST, "title": f"TEST_X31_{TAG}", "entity_id": ENT, "expected_delivery": "2026-12-31",
            "items": [{"source_type": "parent_product", "source_template_id": TPL, "description": "TEST printing",
                       "request_types": ["printing"], "quantity": 20}], "submit_for_approval": True}
    r = requests.post(f"{BASE}/special-orders", json=body, headers=H["admin"])
    assert r.status_code in (200, 201), r.text
    od_id = r.json()["id"]
    CREATED_OD.append(od_id)
    a = requests.post(f"{BASE}/special-orders/{od_id}/approve", json={"notes": "TEST"}, headers=H["admin"])
    assert a.status_code == 200, a.text
    od = DB.special_orders.find_one({"id": od_id})
    dr_id = od["items"][0].get("design_request_id") or od.get("design_request_id")
    assert dr_id, "design request expected for printing item"
    _design(D_OD, status="in_review", request_id=dr_id)
    DB.design_requests.update_one({"id": dr_id}, {"$set": {"design_id": D_OD}, "$addToSet": {"gallery_ids": D_OD}})
    if not od.get("design_request_id"):
        DB.special_orders.update_one({"id": od_id}, {"$set": {"design_request_id": dr_id}})

    def go(h):
        return requests.post(f"{BASE}/design-gallery/{D_OD}/lifecycle/approve", json={"score": 1.75, "note": "ACC"}, headers=h)
    with ThreadPoolExecutor(2) as ex:
        res = list(ex.map(go, [H["admin"], H["manager"]]))
    codes = sorted(x.status_code for x in res)
    assert codes.count(200) == 1 and codes[1] in (400, 409), [x.text for x in res]
    doc = DB.design_gallery.find_one({"id": D_OD})
    assert sum(1 for e in doc["timeline"] if e["event"] == "approve") == 1
    prf = DB.md_samples.count_documents({"special_order_id": od_id, "sample_types": "proofing", "status": {"$ne": "cancelled"}})
    assert prf == 1, prf

    g = requests.get(f"{BASE}/special-orders/{od_id}", headers=H["admin"])
    assert g.status_code == 200, g.text
    rv = (g.json().get("chain") or {}).get("review") or {}
    print("review:", {k: rv.get(k) for k in ("ready", "object", "object_label")})
    # Printing: proofing kain masih berjalan → ACC desain PIC belum jadi dasar keputusan pelanggan.
    assert rv.get("ready") is False and rv.get("object") == "proofing" and rv.get("waiting_for")
    blocked = requests.post(f"{BASE}/special-orders/{od_id}/customer-decision",
                            json={"decision": "acc", "note": "TEST"}, headers=H["admin"])
    assert blocked.status_code == 400, blocked.text
    DB.md_samples.update_many({"special_order_id": od_id, "sample_types": "proofing"}, {"$set": {"status": "decided"}})
    rv = (requests.get(f"{BASE}/special-orders/{od_id}", headers=H["admin"]).json().get("chain") or {}).get("review") or {}
    assert rv.get("ready") is True and rv.get("object") == "proofing", rv
    exp_label = rv["object_label"]
    d = requests.post(f"{BASE}/special-orders/{od_id}/customer-decision",
                      json={"decision": "acc", "note": "TEST via WA", "decided_at": "2026-01-10", "contact_name": "TEST"},
                      headers=H["sales"])
    if d.status_code == 403:
        d = requests.post(f"{BASE}/special-orders/{od_id}/customer-decision",
                          json={"decision": "acc", "note": "TEST via WA", "decided_at": "2026-01-10"}, headers=H["admin"])
    assert d.status_code == 200, d.text
    hist = DB.special_orders.find_one({"id": od_id})["customer_decisions"]
    assert hist[-1]["object"] == rv["object"] and hist[-1]["object_label"] == exp_label
