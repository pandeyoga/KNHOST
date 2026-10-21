"""L03 LN-032 extra (iter221) — waiting_for proofing, revisi serentak printing 409, polos object=sample,
revalidation campuran proofing ditolak, kartu desain print paper X/Y."""
import copy
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ENT = "ent_ksc"
CUST = "cust_toko_kain"
TPL = DB.product_templates.find_one({"status": "active"}, {"id": 1}, sort=[("name", 1)])["id"]
TAG = uuid.uuid4().hex[:6]
D_OD = f"dsgn_TEST_x32e_{TAG}"
D_CARD = f"dsgn_TEST_x32c_{TAG}"
CREATED_OD, CREATED_SMP = [], []


def _login(email, pw="demo12345"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


@pytest.fixture(scope="module")
def H():
    return {"admin": _login("admin@kainnusantara.id", "demo12345"), "manager": _login("manager@kainnusantara.id"),
            "sales": _login("sales@kainnusantara.id")}


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    DB.md_samples.delete_many({"$or": [{"special_order_id": {"$in": CREATED_OD}}, {"id": {"$in": CREATED_SMP}}]})
    DB.special_orders.delete_many({"id": {"$in": CREATED_OD}})
    DB.design_requests.delete_many({"special_order_id": {"$in": CREATED_OD}})
    DB.design_gallery.delete_many({"id": {"$in": [D_OD, D_CARD]}})


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
    od = DB.special_orders.find_one({"id": od_id})
    DB.md_samples.update_many({"$or": [{"special_order_id": od_id}, {"id": {"$in": od.get("sample_ids") or []}}],
                               "status": {"$nin": ["cancelled", "decided"]}}, {"$set": {"status": "decided"}})


def _review(H, od_id, who="admin"):
    return (requests.get(f"{BASE}/special-orders/{od_id}", headers=H[who]).json().get("chain") or {}).get("review") or {}


def _decide(H, od_id, decision, note="TEST", who="admin"):
    return requests.post(f"{BASE}/special-orders/{od_id}/customer-decision",
                         json={"decision": decision, "note": note, "decided_at": "2026-10-18"}, headers=H[who])


def _printing_od_with_acc_design(H):
    od_id = _od(H, ["printing"], "PE32")
    od = DB.special_orders.find_one({"id": od_id})
    dr_id = od["items"][0].get("design_request_id") or od.get("design_request_id")
    src = copy.deepcopy(DB.design_gallery.find_one({"entity_id": ENT, "id": {"$not": {"$regex": "^dsgn_TEST_"}}}, {"_id": 0}))
    src.update({"id": D_OD, "code": f"T32E-{TAG}", "title": f"TEST_{D_OD}", "status": "in_review", "request_id": dr_id,
                "origin": "", "on_hold": False, "hold": {}, "version": 3,
                "versions": [{"version": 1}, {"version": 2}, {"version": 3}], "timeline": []})
    DB.design_gallery.insert_one(src)
    DB.design_requests.update_one({"id": dr_id}, {"$set": {"design_id": D_OD}, "$addToSet": {"gallery_ids": D_OD}})
    if not od.get("design_request_id"):
        DB.special_orders.update_one({"id": od_id}, {"$set": {"design_request_id": dr_id}})
    r = requests.post(f"{BASE}/design-gallery/{D_OD}/lifecycle/approve", json={"score": 1.75, "note": "ACC"}, headers=H["admin"])
    assert r.status_code == 200, r.text
    return od_id


class TestPrintingReproofing:
    def test_t01_waiting_for_and_rounds_payload(self, H):
        od_id = _printing_od_with_acc_design(H)
        pytest.od_id = od_id
        rv = _review(H, od_id, "sales")
        smp = DB.md_samples.find_one({"special_order_id": od_id, "sample_types": "proofing"})
        assert rv["ready"] is False and rv["object"] == "proofing"
        assert rv["object_label"] == "Proofing kain (printing)"
        assert smp["number"] in rv["waiting_for"]
        assert [{k: r[k] for k in ("round", "number", "status", "design_id", "design_version")}
                for r in rv["proofing_rounds"]] == [{"round": 1, "number": smp["number"], "status": smp["status"],
                                                     "design_id": D_OD, "design_version": 3}]
        for d in ("acc", "revisi", "tolak"):
            r = _decide(H, od_id, d, who="sales")
            assert r.status_code == 400, (d, r.text)

    def test_revisi_requires_note_and_concurrent_revisi_one_round(self, H):
        od_id = pytest.od_id
        _decide_all(od_id)
        assert _decide(H, od_id, "revisi", note="").status_code == 400
        with ThreadPoolExecutor(2) as ex:
            res = list(ex.map(lambda w: _decide(H, od_id, "revisi", note="warna pudar", who=w), ["admin", "manager"]))
        codes = sorted(x.status_code for x in res)
        assert codes.count(200) == 1, [x.text for x in res]
        loser = next(x for x in res if x.status_code != 200)
        assert loser.status_code in (400, 409), loser.text
        if loser.status_code == 409:
            assert "sedang dicatat pengguna lain" in loser.json().get("detail", "")
        rounds = list(DB.md_samples.find({"special_order_id": od_id, "sample_types": "proofing"}))
        assert len(rounds) == 2
        new = next(s for s in rounds if s.get("proofing_round") == 2)
        assert new["design_id"] == D_OD and new["design_version"] == 3 and new["sample_types"] == ["proofing"]
        rv = _review(H, od_id)
        assert rv["ready"] is False and rv["object"] == "proofing" and rv["waiting_for"] == [new["number"]]
        assert [r["round"] for r in rv["proofing_rounds"]] == [1, 2]
        doc = DB.special_orders.find_one({"id": od_id})
        assert doc.get("decision_lock") in ("", None)
        assert doc.get("customer_decision") == ""

    def test_tolak_cancels_od(self, H):
        od_id = pytest.od_id
        _decide_all(od_id)
        r = _decide(H, od_id, "tolak", note="pelanggan batal")
        assert r.status_code == 200, r.text
        assert r.json()["decision"]["object"] == "proofing"
        assert DB.special_orders.find_one({"id": od_id})["status"] == "cancelled"
        assert _decide(H, od_id, "acc").status_code == 400


class TestPlainOrder:
    def test_plain_revisi_waiting_object_sample(self, H):
        od_id = _od(H, ["labdip", "handfeel"], "NE32")
        rv0 = _review(H, od_id)
        _decide_all(od_id)
        r = _decide(H, od_id, "revisi", note="warna kurang")
        assert r.status_code == 200, r.text
        assert r.json()["decision"]["object"] == "sample"
        rv = _review(H, od_id)
        new_no = r.json()["decision"]["revision_sample_number"]
        assert rv["ready"] is False and rv["object"] == "sample" and new_no in rv["waiting_for"]
        assert rv["object_label"] == "Sample labdip/handfeel" and rv["proofing_rounds"] == []
        assert rv0.get("proofing_rounds") == []


class TestRevalidation:
    def test_mixed_proofing_rejected(self, H):
        prod = DB.products.find_one({"status": "active", "sku": {"$nin": ["", None]}}, {"_id": 0, "id": 1})
        r = requests.post(f"{BASE}/rnd/samples", json={"product_id": prod["id"], "sample_types": ["handfeel", "proofing"],
                                                        "title": "TEST_mix"}, headers=H["admin"])
        assert r.status_code == 400, r.text
        if r.status_code in (200, 201):
            CREATED_SMP.append(r.json()["id"])


class TestDesignCardPaperCount:
    def test_list_has_paper_counts_and_increment(self, H):
        src = copy.deepcopy(DB.design_gallery.find_one({"entity_id": ENT, "id": {"$not": {"$regex": "^dsgn_TEST_"}}}, {"_id": 0}))
        src.update({"id": D_CARD, "code": f"T32C-{TAG}", "title": f"TEST_{D_CARD}", "status": "draft", "request_id": "",
                    "origin": "", "on_hold": False, "hold": {}, "version": 2, "versions": [{"version": 1}, {"version": 2}],
                    "timeline": [], "round_paper_history": {}})
        DB.design_gallery.insert_one(src)

        def card():
            rows = requests.get(f"{BASE}/design-gallery", params={"q": f"TEST_{D_CARD}"}, headers=H["admin"]).json()
            return next(x for x in rows if x["id"] == D_CARD)
        c = card()
        assert c["rounds_total"] == 2 and c["paper_rounds_done"] == 0
        assert requests.post(f"{BASE}/design-gallery/{D_CARD}/rounds/1/paper", json={"checked": True}, headers=H["admin"]).status_code == 200
        assert card()["paper_rounds_done"] == 1
        assert requests.post(f"{BASE}/design-gallery/{D_CARD}/rounds/2/paper", json={"checked": True}, headers=H["admin"]).status_code == 200
        assert card()["paper_rounds_done"] == 2
        assert requests.post(f"{BASE}/design-gallery/{D_CARD}/rounds/2/paper", json={"checked": False}, headers=H["admin"]).status_code == 200
        assert card()["paper_rounds_done"] == 1
