"""L03 LN-031 — checklist print paper per ronde, ACC PIC atomik (sekali), objek keputusan pelanggan."""
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
TAG = uuid.uuid4().hex[:6]
D_PAPER = f"dsgn_TEST_p31_{TAG}"
D_RACE = f"dsgn_TEST_r31_{TAG}"


def _login(email, pw="demo12345"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


def _design(did, status, versions):
    src = DB.design_gallery.find_one({"entity_id": ENT}, {"_id": 0}) or {}
    base = copy.deepcopy(src)
    base.update({"id": did, "code": f"T31-{did[-6:]}", "title": f"TEST_{did}", "status": status, "entity_id": ENT,
                 "request_id": "", "origin": "", "on_hold": False, "hold": {}, "version": len(versions),
                 "versions": versions, "timeline": [], "created_by_id": ""})
    DB.design_gallery.insert_one(base)


@pytest.fixture(scope="module", autouse=True)
def fixtures():
    _design(D_PAPER, "draft", [{"version": 1, "note": "awal"}, {"version": 2, "note": "rev 1"}])
    _design(D_RACE, "in_review", [{"version": 1, "note": "awal"}])
    yield
    DB.design_gallery.delete_many({"id": {"$in": [D_PAPER, D_RACE]}})


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id", "demo12345")


def test_paper_check_records_round_actor_time_without_approval(admin):
    r = requests.post(f"{BASE}/design-gallery/{D_PAPER}/rounds/1/paper", json={"checked": True}, headers=admin)
    assert r.status_code == 200, r.text
    d = r.json()
    rnd = next(x for x in d["rounds"] if x["version"] == 1)
    assert rnd["paper"]["checked"] is True and rnd["paper"]["by"] and rnd["paper"]["at"]
    assert next(x for x in d["rounds"] if x["version"] == 2)["paper"] == {}
    assert d["status"] == "draft", "paper tidak boleh mengubah status/ACC"
    # klik ulang tidak menggandakan riwayat
    requests.post(f"{BASE}/design-gallery/{D_PAPER}/rounds/1/paper", json={"checked": True}, headers=admin)
    doc = DB.design_gallery.find_one({"id": D_PAPER})
    assert len(doc["round_paper_history"]["1"]) == 1
    assert sum(1 for e in doc["timeline"] if e["event"] == "paper_check") == 1


def test_paper_uncheck_and_unknown_round(admin):
    r = requests.post(f"{BASE}/design-gallery/{D_PAPER}/rounds/1/paper", json={"checked": False}, headers=admin)
    assert r.status_code == 200 and next(x for x in r.json()["rounds"] if x["version"] == 1)["paper"]["checked"] is False
    assert requests.post(f"{BASE}/design-gallery/{D_PAPER}/rounds/9/paper", json={"checked": True}, headers=admin).status_code == 400


def test_paper_check_forbidden_for_sales():
    h = _login("sales@kainnusantara.id")
    r = requests.post(f"{BASE}/design-gallery/{D_PAPER}/rounds/1/paper", json={"checked": True}, headers=h)
    assert r.status_code == 403, r.text


def test_concurrent_pic_acc_only_once(admin):
    h2 = _login("manager@kainnusantara.id")

    def go(h):
        return requests.post(f"{BASE}/design-gallery/{D_RACE}/lifecycle/approve", json={"score": 1.75, "note": "ACC"}, headers=h)
    with ThreadPoolExecutor(2) as ex:
        res = list(ex.map(go, [admin, h2]))
    codes = sorted(r.status_code for r in res)
    assert codes[0] == 200 and codes[1] in (200, 400, 409), [r.text for r in res]
    assert codes.count(200) == 1, [r.text for r in res]
    doc = DB.design_gallery.find_one({"id": D_RACE})
    assert doc["status"] == "approved"
    assert sum(1 for e in doc["timeline"] if e["event"] == "approve") == 1
    again = go(h2)
    assert again.status_code in (400, 409)
