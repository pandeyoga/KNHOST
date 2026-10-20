"""L04 LN-042 edge cases — MDQ cut validation, roles, inspection state; restores roll state after each test."""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]


def _login(email, pw):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id", "demo12345")


def _roll(unit):
    return DB.inventory_rolls.find_one({"unit": unit, "status": "available", "length_remaining": {"$gt": 5}},
                                       {"_id": 0}, sort=[("id", -1)])


@pytest.fixture
def ctx():
    """Create a TEST inspection on a yard roll; restore roll + remove artefacts afterwards."""
    roll = _roll("yard")
    if not roll:
        pytest.skip("no yard roll")
    made = []

    def make(status="in_progress", kind="po_receipt"):
        iid, lid = f"ins_test_{uuid.uuid4().hex[:8]}", f"ln_{uuid.uuid4().hex[:6]}"
        DB.inspections.insert_one({"id": iid, "number": "TEST-L04E", "kind": kind, "status": status,
                                   "entity_id": roll["owner_entity_id"], "remark": "TEST_L04E",
                                   "lines": [{"id": lid, "roll_id": roll["id"], "product_id": roll["product_id"],
                                              "unit": "yard"}]})
        made.append((iid, lid))
        return iid, lid
    yield roll, make
    for iid, lid in made:
        DB.inventory_movements.delete_many({"source_document": iid, "movement_type": "mdq_cut"})
        DB.mdq_cuts.delete_many({"_id": f"{iid}:{lid}"})
        DB.journal_entries.delete_many({"source_id": f"mdq:{iid}:{lid}"})
        DB.inventory_rolls.update_one({"id": roll["id"]}, {"$pull": {"usage_history": {"ref": f"{iid}:{lid}"}}})
    DB.inventory_rolls.update_one({"id": roll["id"]}, {"$set": {"length_remaining": roll["length_remaining"]}})
    DB.inspections.delete_many({"remark": "TEST_L04E"})


def _hdr(tok, roll):
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": roll["owner_entity_id"]}


class TestMdqCutEdge:
    def test_cut_over_limit_400(self, admin, ctx):
        roll, make = ctx
        iid, lid = make()
        r = requests.post(f"{BASE}/api/inspections/{iid}/lines/{lid}/mdq-cut", json={"cut_yard": 6},
                          headers=_hdr(admin, roll), timeout=30)
        assert r.status_code == 400
        r = requests.post(f"{BASE}/api/inspections/{iid}/lines/{lid}/mdq-cut", json={"cut_yard": 0},
                          headers=_hdr(admin, roll), timeout=30)
        assert r.status_code == 400

    def test_unknown_line_404(self, admin, ctx):
        roll, make = ctx
        iid, _ = make()
        r = requests.post(f"{BASE}/api/inspections/{iid}/lines/nope/mdq-cut", json={},
                          headers=_hdr(admin, roll), timeout=30)
        assert r.status_code == 404
        r = requests.post(f"{BASE}/api/inspections/nope/lines/nope/mdq-cut", json={},
                          headers=_hdr(admin, roll), timeout=30)
        assert r.status_code == 404

    @pytest.mark.parametrize("email", ["md@kainnusantara.id", "mdquality@kainnusantara.id"])
    def test_md_roles_allowed(self, ctx, email):
        roll, make = ctx
        iid, lid = make()
        tok = _login(email, "demo12345")
        r = requests.post(f"{BASE}/api/inspections/{iid}/lines/{lid}/mdq-cut", json={},
                          headers=_hdr(tok, roll), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["qty"] == 0.25 and d["unit"] == "yard" and d["status"] == "posted"
        ins = DB.inspections.find_one({"id": iid})
        assert ins["lines"][0]["mdq_cut"]["qty"] == 0.25

    def test_completed_inspection_should_block(self, admin, ctx):
        """Cutting on a finished (completed) inspection should not be allowed."""
        roll, make = ctx
        iid, lid = make(status="completed")
        r = requests.post(f"{BASE}/api/inspections/{iid}/lines/{lid}/mdq-cut", json={},
                          headers=_hdr(admin, roll), timeout=30)
        assert r.status_code in (400, 409), f"cut allowed on completed inspection: {r.status_code}"

    def test_wrong_entity_forbidden(self, admin, ctx):
        roll, make = ctx
        iid, lid = make()
        other = "ent_kanda" if roll["owner_entity_id"] != "ent_kanda" else "ent_ksc"
        r = requests.post(f"{BASE}/api/inspections/{iid}/lines/{lid}/mdq-cut", json={},
                          headers={"Authorization": f"Bearer {admin}", "X-Entity-Id": other}, timeout=30)
        print("wrong entity status", r.status_code)
        assert r.status_code in (403, 404)
