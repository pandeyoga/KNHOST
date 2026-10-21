"""L03 LN-030 — Special Order multi-produk, sumber desain per item, HOLD, redesign, origin desain."""
import copy
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
CUST = "cust_toko_kain"
TPL = DB.product_templates.find_one({"status": "active"}, {"id": 1}, sort=[("name", 1)])["id"]
TAG = uuid.uuid4().hex[:6]
D_OK = f"dsgn_TEST_ok_{TAG}"
D_HOLD = f"dsgn_TEST_hold_{TAG}"
D_OTHER = f"dsgn_TEST_other_{TAG}"
D_DRAFT = f"dsgn_TEST_draft_{TAG}"
D_REL = f"dsgn_TEST_rel_{TAG}"
D_LINK = f"dsgn_TEST_link_{TAG}"
ALL_D = [D_OK, D_HOLD, D_OTHER, D_DRAFT, D_REL, D_LINK]
CREATED_OD = []


def _login(email, pwd):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pwd})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


def _design(did, code, status="approved", entity=ENT, hold=False):
    base = copy.deepcopy(DB.design_gallery.find_one({"id": {"$not": {"$regex": "^dsgn_TEST_"}}}, {"_id": 0}))
    base.update({"id": did, "code": code, "title": f"TEST_{code}", "status": status, "entity_id": entity,
                 "request_id": "", "request_number": "", "origin": "",
                 "on_hold": hold, "hold": {"reason": "TEST hold reason"} if hold else {}})
    DB.design_gallery.insert_one(base)


def _cleanup():
    ods = [o["id"] for o in DB.special_orders.find({"$or": [{"id": {"$in": CREATED_OD}}, {"title": {"$regex": "^TEST_"}},
                                                             {"redesign_of.special_order_id": {"$in": CREATED_OD}}]}, {"id": 1})]
    smp = [s for s in DB.md_samples.find({"special_order_id": {"$in": ods}}, {"id": 1, "spec_id": 1})]
    DB.md_samples.delete_many({"special_order_id": {"$in": ods}})
    DB.rnd_specs.delete_many({"id": {"$in": [s.get("spec_id") for s in smp if s.get("spec_id")]}})
    DB.md_specs.delete_many({"id": {"$in": [s.get("spec_id") for s in smp if s.get("spec_id")]}})
    DB.design_requests.delete_many({"special_order_id": {"$in": ods}})
    DB.special_orders.delete_many({"id": {"$in": ods}})
    DB.design_gallery.delete_many({"$or": [{"id": {"$in": ALL_D}}, {"id": {"$regex": "^dsgn_TEST_"}}]})


@pytest.fixture(scope="module", autouse=True)
def fixtures():
    _design(D_OK, f"TST-OK-{TAG}")
    _design(D_HOLD, f"TST-HOLD-{TAG}", hold=True)
    _design(D_OTHER, f"TST-OTH-{TAG}", entity="ent_kanda")
    _design(D_DRAFT, f"TST-DRF-{TAG}", status="draft")
    _design(D_REL, f"TST-REL-{TAG}", hold=True)
    _design(D_LINK, f"TST-LNK-{TAG}", status="draft")
    yield
    _cleanup()


@pytest.fixture(scope="module")
def H():
    return {"admin": _login("admin@kainnusantara.id", "demo12345"),
            "manager": _login("manager@kainnusantara.id", "demo12345"),
            "md": _login("md@kainnusantara.id", "demo12345"),
            "sales": _login("sales@kainnusantara.id", "demo12345"),
            "designer": _login("designer@kainnusantara.id", "demo12345")}


def _create(H, items, submit=True, title=None, who="admin"):
    body = {"customer_id": CUST, "title": title or f"TEST_OD_{TAG}", "entity_id": ENT,
            "expected_delivery": "2026-12-31", "items": items, "submit_for_approval": submit}
    r = requests.post(f"{BASE}/special-orders", json=body, headers=H[who])
    if r.status_code == 200 or r.status_code == 201:
        CREATED_OD.append(r.json()["id"])
    return r


def _approve(H, od_id):
    r = requests.post(f"{BASE}/special-orders/{od_id}/approve", json={"notes": "TEST"}, headers=H["admin"])
    assert r.status_code == 200, r.text
    return r.json()


def _get(H, od_id):
    r = requests.get(f"{BASE}/special-orders/{od_id}", headers=H["admin"])
    assert r.status_code == 200, r.text
    return r.json()


MULTI = [
    {"source_type": "parent_product", "source_template_id": TPL, "description": "TEST item parent",
     "request_types": ["printing", "labdip"], "quantity": 100, "unit": "meter", "target_price": 25000},
    {"source_type": "approved_artwork", "source_design_id": D_OK, "description": "TEST item artwork",
     "request_types": ["printing"], "quantity": 50, "unit": "meter", "target_price": 30000},
]


# ── T01: multi-item create + per item routing ─────────────────────────────────
class TestMultiItem:
    state = {}

    def test_create_multi(self, H):
        pc = DB.products.count_documents({})
        r = _create(H, MULTI)
        assert r.status_code in (200, 201), r.text
        od = r.json()
        assert od["origin"] == "special_order"
        assert len(od["items"]) == 2
        assert od["total_amount"] == 100 * 25000 + 50 * 30000
        assert od["request_types"] == ["labdip", "printing"]
        assert od["items"][0]["source_template_id"] == TPL
        assert od["items"][1]["source_design_id"] == D_OK
        assert od["items"][1]["source_design_code"] == f"TST-OK-{TAG}"
        assert DB.products.count_documents({}) == pc
        self.state.update(od=od, pc=pc)

    def test_approve_routes_per_item(self, H):
        od = self.state["od"]
        _approve(H, od["id"])
        assert DB.products.count_documents({}) == self.state["pc"], "approve must not create products"
        d = _get(H, od["id"])
        it0, it1 = d["items"]
        # item 1 parent+printing → design request with item id; labdip → sample with item id
        assert it0["design_request_id"], it0
        dr = DB.design_requests.find_one({"id": it0["design_request_id"]})
        assert dr["special_order_item_id"] == it0["id"] and dr["special_order_id"] == od["id"]
        assert dr.get("origin") == "special_order"
        s0 = list(DB.md_samples.find({"special_order_item_id": it0["id"]}))
        assert len(s0) == 1 and set(s0[0]["sample_types"]) == {"labdip"}
        # item 2 artwork+printing → proofing sample with design_id, NO design request
        assert not it1.get("design_request_id")
        s1 = list(DB.md_samples.find({"special_order_item_id": it1["id"]}))
        assert len(s1) == 1 and s1[0]["sample_types"] == ["proofing"] and s1[0]["design_id"] == D_OK
        # chain.items
        ch = {i["id"]: i for i in d["chain"]["items"]}
        assert ch[it0["id"]]["design_request"]["id"] == it0["design_request_id"]
        assert [s["id"] for s in ch[it0["id"]]["samples"]] == [s0[0]["id"]]
        assert [s["id"] for s in ch[it1["id"]]["samples"]] == [s1[0]["id"]]
        assert ch[it1["id"]]["can_redesign"] is True
        assert not d["chain"].get("routing_errors") and not d.get("routing_errors"), d.get("routing_errors")
        self.state["d"] = d

    def test_reroute_no_duplicates(self, H):
        od = self.state["od"]
        n_s = DB.md_samples.count_documents({"special_order_id": od["id"]})
        n_r = DB.design_requests.count_documents({"special_order_id": od["id"]})
        r = requests.post(f"{BASE}/special-orders/{od['id']}/route", headers=H["admin"])
        assert r.status_code == 200, r.text
        r = requests.post(f"{BASE}/special-orders/{od['id']}/approve", json={}, headers=H["admin"])
        assert r.status_code in (400, 403, 409), r.text
        assert DB.md_samples.count_documents({"special_order_id": od["id"]}) == n_s
        assert DB.design_requests.count_documents({"special_order_id": od["id"]}) == n_r

    # ── T03 redesign ──
    def test_redesign(self, H):
        d = self.state["d"]
        it1 = d["items"][1]
        before = DB.special_orders.find_one({"id": d["id"]}, {"_id": 0})
        r = requests.post(f"{BASE}/special-orders/{d['id']}/redesign",
                          json={"item_id": it1["id"], "reason": "TEST ganti motif"}, headers=H["admin"])
        assert r.status_code == 200, r.text
        rd = r.json()
        CREATED_OD.append(rd["id"])
        assert rd["id"] != d["id"] and rd["status"] == "draft" and rd["origin"] == "redesign"
        ro = rd["redesign_of"]
        assert ro["special_order_id"] == d["id"] and ro["number"] == d["number"]
        assert ro["item_id"] == it1["id"] and ro["design_id"] == D_OK
        assert len(rd["items"]) == 1 and rd["items"][0]["source_type"] == "redesign"
        after = DB.special_orders.find_one({"id": d["id"]}, {"_id": 0})
        assert [x["id"] for x in after["redesigns"]] == [rd["id"]]
        assert after["items"] == before["items"], "original items must stay unchanged"
        assert DB.md_samples.count_documents({"special_order_item_id": it1["id"]}) == 1
        self.state["rd"] = rd

    def test_redesign_dup_409(self, H):
        d = self.state["d"]
        r = requests.post(f"{BASE}/special-orders/{d['id']}/redesign",
                          json={"item_id": d["items"][1]["id"], "reason": "TEST lagi dong"}, headers=H["admin"])
        assert r.status_code == 409, r.text

    def test_redesign_short_reason_422(self, H):
        d = self.state["d"]
        r = requests.post(f"{BASE}/special-orders/{d['id']}/redesign",
                          json={"item_id": d["items"][0]["id"], "reason": "ab"}, headers=H["admin"])
        assert r.status_code == 422, r.text

    def test_redesign_item_without_artwork_400(self, H):
        d = self.state["d"]
        r = requests.post(f"{BASE}/special-orders/{d['id']}/redesign",
                          json={"item_id": d["items"][0]["id"], "reason": "TEST tanpa artwork"}, headers=H["admin"])
        assert r.status_code == 400, r.text

    def test_origin_filter(self, H):
        rd = self.state["rd"]
        r = requests.get(f"{BASE}/special-orders?origin=redesign", headers=H["admin"])
        assert r.status_code == 200, r.text
        ids = [o["id"] for o in r.json()["items"]]
        assert rd["id"] in ids and self.state["d"]["id"] not in ids
        r = requests.get(f"{BASE}/special-orders?origin=special_order", headers=H["admin"])
        ids = [o["id"] for o in r.json()["items"]]
        assert self.state["d"]["id"] in ids and rd["id"] not in ids

    def test_redesign_approve_routes_design_request_with_origin(self, H):
        rd = self.state["rd"]
        r = requests.post(f"{BASE}/special-orders/{rd['id']}/submit", headers=H["admin"])
        assert r.status_code == 200, r.text
        _approve(H, rd["id"])
        d = _get(H, rd["id"])
        it = d["items"][0]
        assert it["design_request_id"], d.get("routing_errors")
        dr = DB.design_requests.find_one({"id": it["design_request_id"]})
        assert dr["origin"] == "redesign" and dr["parent_design_id"] == D_OK
        self.state["rd_req"] = dr

    def test_link_design_sets_origin(self, H):
        """Design linked to a design request of the redesign OD gets origin=redesign + SO number + parent."""
        dr = self.state["rd_req"]
        uid = DB.users.find_one({"email": "designer@kainnusantara.id"})["id"]
        if dr["status"] not in ("assigned", "in_progress", "revision"):
            r = requests.post(f"{BASE}/design-requests/{dr['id']}/assign", json={"assigned_to": uid}, headers=H["admin"])
            assert r.status_code == 200, r.text
        r = requests.post(f"{BASE}/design-requests/{dr['id']}/link-design", json={"gallery_id": D_LINK}, headers=H["admin"])
        assert r.status_code == 200, r.text
        g = DB.design_gallery.find_one({"id": D_LINK})
        assert g["origin"] == "redesign" and g["special_order_number"] == self.state["rd"]["number"]
        assert g["parent_design_id"] == D_OK
        r = requests.get(f"{BASE}/design-gallery?origin=redesign", headers=H["admin"])
        assert r.status_code == 200
        rows = {x["id"]: x for x in r.json()}
        assert D_LINK in rows and rows[D_LINK]["origin_label"]
        r = requests.get(f"{BASE}/design-gallery?origin=internal", headers=H["admin"])
        ids = [x["id"] for x in r.json()]
        assert D_LINK not in ids and D_OK in ids


# ── T02 validation ────────────────────────────────────────────────────────────
class TestArtworkValidation:
    @pytest.mark.parametrize("did,needle", [(D_HOLD, "HOLD"), (D_DRAFT, "ACC"), (D_OTHER, "badan usaha"),
                                            ("dsgn_nope_x", "tidak ditemukan")], ids=["hold", "draft", "other", "missing"])
    def test_invalid_artwork_400(self, H, did, needle):
        pc = DB.products.count_documents({})
        r = _create(H, [{"source_type": "approved_artwork", "source_design_id": did,
                         "request_types": ["printing"], "quantity": 10}])
        assert r.status_code == 400, r.text
        assert needle.lower() in r.json()["detail"].lower(), r.text
        assert DB.products.count_documents({}) == pc

    def test_bad_source_type_and_no_types(self, H):
        r = _create(H, [{"source_type": "xx", "request_types": ["printing"], "quantity": 1}])
        assert r.status_code == 400
        r = _create(H, [{"source_type": "customer_reference", "request_types": [], "quantity": 1}])
        assert r.status_code == 400

    def test_redesign_source_type_cannot_bypass_hold(self, H):
        """Client could submit source_type=redesign directly with a HOLD artwork (bypass)."""
        r = _create(H, [{"source_type": "redesign", "source_design_id": D_HOLD,
                         "request_types": ["printing"], "quantity": 1}])
        assert r.status_code == 400, f"HOLD bypass via source_type=redesign: {r.status_code} {r.text[:200]}"

    def test_legacy_payload(self, H):
        body = {"customer_id": CUST, "title": f"TEST_legacy_{TAG}", "entity_id": ENT, "expected_delivery": "2026-12-31",
                "request_types": ["labdip"],
                "custom_item": {"description": "TEST legacy", "quantity": 10, "unit": "meter", "target_price": 1000}}
        r = requests.post(f"{BASE}/special-orders", json=body, headers=H["admin"])
        assert r.status_code in (200, 201), r.text
        CREATED_OD.append(r.json()["id"])
        assert r.json()["total_amount"] == 10000 and r.json()["items"] == []
        assert r.json()["request_types"] == ["labdip"]

    def test_customer_reference_labdip_handfeel(self, H):
        r = _create(H, [{"source_type": "customer_reference", "description": "TEST ref",
                         "request_types": ["labdip", "handfeel"], "quantity": 5, "target_price": 100}])
        assert r.status_code in (200, 201), r.text
        od = r.json()
        _approve(H, od["id"])
        s = list(DB.md_samples.find({"special_order_item_id": od["items"][0]["id"]}))
        assert len(s) == 1 and set(s[0]["sample_types"]) == {"labdip", "handfeel"}
        assert DB.design_requests.count_documents({"special_order_id": od["id"]}) == 0


# ── HOLD release permission ───────────────────────────────────────────────────
class TestHoldRelease:
    @pytest.mark.parametrize("who", ["designer", "sales"])
    def test_release_forbidden(self, H, who):
        r = requests.post(f"{BASE}/design-gallery/{D_REL}/lifecycle/release-hold", json={"note": "TEST"}, headers=H[who])
        assert r.status_code == 403, r.text
        assert DB.design_gallery.find_one({"id": D_REL})["on_hold"] is True

    def test_meta_can_release(self, H):
        exp = {"admin": True, "manager": True, "md": True, "designer": False, "sales": False}
        for who, v in exp.items():
            r = requests.get(f"{BASE}/design-studio/meta", headers=H[who])
            if r.status_code == 403:
                assert not v, f"{who} meta 403"
                continue
            assert r.status_code == 200, r.text
            m = r.json()
            assert m["hold"]["can_release"] is v, (who, m["hold"])
            assert {o["value"] for o in m["origins"]} >= {"internal", "special_order", "redesign"}

    @pytest.mark.parametrize("who", ["md", "manager", "admin"])
    def test_release_allowed_then_rehold(self, H, who):
        r = requests.post(f"{BASE}/design-gallery/{D_REL}/lifecycle/release-hold", json={"note": "TEST lepas"}, headers=H[who])
        assert r.status_code == 200, r.text
        assert not DB.design_gallery.find_one({"id": D_REL}).get("on_hold")
        r = requests.post(f"{BASE}/design-gallery/{D_REL}/lifecycle/hold", json={"note": "TEST hold lagi"}, headers=H["manager"])
        assert r.status_code == 200, r.text
        assert DB.design_gallery.find_one({"id": D_REL})["on_hold"] is True

    def test_released_artwork_usable(self, H):
        r = requests.post(f"{BASE}/design-gallery/{D_REL}/lifecycle/release-hold", json={"note": "TEST"}, headers=H["md"])
        assert r.status_code == 200
        r = _create(H, [{"source_type": "approved_artwork", "source_design_id": D_REL,
                         "request_types": ["printing"], "quantity": 1}], submit=False)
        assert r.status_code in (200, 201), r.text
