"""LN-015-T03/T05/T06 — ACC teknis per jenis uji (PIC Proofing ≠ labdip/handfeel/kontrak) + konflik versi peran."""
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
import requests

from tests.test_p05_acceptance_acc31_33_34 import BASE, DB, _login

TAG = uuid.uuid4().hex[:6]
ENT = "ent_ksc"
S_PROOF, S_LAB, S_REVAL = (f"smp_TEST_ln015_{k}_{TAG}" for k in ("proof", "lab", "reval"))


@pytest.fixture(scope="module")
def adm():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def pic(adm):
    perms = {"rnd": ["view", "assess_proofing", "decide_proofing"], "product": ["view"]}
    r = requests.post(f"{BASE}/api/access/roles", json={"label": f"TEST_LN015 PIC Proofing {TAG}", "permissions": perms},
                      headers=adm, timeout=30)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    email = f"test_ln015_{TAG}@kainnusantara.id"
    admin = DB.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0})
    DB.users.insert_one({"id": f"user_TEST_{TAG}", "email": email, "name": "TEST_LN015 PIC", "role": rid, "status": "active",
                         "home_entity_id": ENT, "entity_ids": admin.get("entity_ids") or [ENT],
                         "password_hash": bcrypt.hashpw(b"demo12345", bcrypt.gensalt()).decode(),
                         "created_at": datetime.now(timezone.utc).isoformat()})
    base = {"entity_id": ENT, "status": "in_progress", "rounds": [], "timeline": [], "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()}
    DB.md_samples.insert_many([
        {**base, "id": S_PROOF, "number": f"TEST-PRF-{TAG}", "sample_types": ["proofing"]},
        {**base, "id": S_LAB, "number": f"TEST-LAB-{TAG}", "sample_types": ["labdip"]},
        {**base, "id": S_REVAL, "number": f"TEST-RV-{TAG}", "sample_types": ["proofing"], "purpose": "revalidation",
         "revalidation": {"supplier_id": "sup_TEST", "cycle_no": 1}}])
    yield {"rid": rid, "h": _login(email, "demo12345")}
    DB.md_samples.delete_many({"id": {"$in": [S_PROOF, S_LAB, S_REVAL]}})
    DB.users.delete_many({"email": email})
    requests.delete(f"{BASE}/api/access/roles/{rid}", headers=adm, timeout=30)


def _assess(h, sid):
    return requests.post(f"{BASE}/api/rnd/samples/{sid}/rounds/rnd_nope/assess", json={"result": "pass", "score": 80, "note": "x"},
                         headers=h, timeout=30)


def test_t03_pic_proofing_can_assess_proofing_only(pic):
    assert _assess(pic["h"], S_PROOF).status_code != 403
    r = _assess(pic["h"], S_LAB)
    assert r.status_code == 403 and "assess_labdip" in r.text


def test_t03_typed_decide_never_opens_contract(pic):
    r = requests.post(f"{BASE}/api/rnd/samples/{S_PROOF}/decide", json={"supplier_id": "sup_x", "price": 1000, "note": "x"},
                      headers=pic["h"], timeout=30)
    assert r.status_code == 403 and "kontrak" in r.text
    r2 = requests.post(f"{BASE}/api/rnd/samples/{S_LAB}/decide", json={"note": "x"}, headers=pic["h"], timeout=30)
    assert r2.status_code == 403 and "decide_labdip" in r2.text


def test_t03_typed_decide_allowed_on_revalidation_technical_result(pic):
    r = requests.post(f"{BASE}/api/rnd/samples/{S_REVAL}/decide", json={"result": "pass", "note": "x"}, headers=pic["h"], timeout=30)
    assert r.status_code != 403, r.text


def test_t03_pic_queue_and_contract_options_still_denied(pic):
    assert requests.get(f"{BASE}/api/rnd/samples/{S_REVAL}/contract-options", headers=pic["h"], timeout=30).status_code == 403
    assert requests.post(f"{BASE}/api/rnd/samples/{S_REVAL}/pic-decision", json={"action": "retest", "reason": "ulang uji"},
                         headers=pic["h"], timeout=30).status_code == 403


def test_generic_assess_still_covers_all_types(adm):
    assert _assess(adm, S_LAB).status_code != 403


def test_typed_actions_listed_with_work_labels(adm):
    cat = requests.get(f"{BASE}/api/access/modules", headers=adm, timeout=30)
    if cat.status_code != 200:
        pytest.skip("catalog endpoint berbeda")
    assert "Setujui hasil proofing" in cat.text and "Catat hasil handfeel" in cat.text


def test_t06_role_version_conflict_409(adm, pic):
    role = requests.get(f"{BASE}/api/access/roles/{pic['rid']}", headers=adm, timeout=30).json()
    v1 = role["version"]
    ok = requests.patch(f"{BASE}/api/access/roles/{pic['rid']}", json={"hidden_views": ["rnd-labdip"], "expected_version": v1},
                        headers=adm, timeout=30)
    assert ok.status_code == 200 and ok.json()["version"] != v1
    stale = requests.patch(f"{BASE}/api/access/roles/{pic['rid']}", json={"hidden_views": [], "expected_version": v1},
                           headers=adm, timeout=30)
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "ROLE_VERSION_CONFLICT"
    assert requests.get(f"{BASE}/api/access/roles/{pic['rid']}", headers=adm, timeout=30).json()["hidden_views"] == ["rnd-labdip"]


def test_t06_permission_change_applies_next_request(adm, pic):
    requests.patch(f"{BASE}/api/access/roles/{pic['rid']}", json={"permissions": {"rnd": ["view"], "product": ["view"]}},
                   headers=adm, timeout=30)
    assert _assess(pic["h"], S_PROOF).status_code == 403
    requests.patch(f"{BASE}/api/access/roles/{pic['rid']}",
                   json={"permissions": {"rnd": ["view", "assess_proofing", "decide_proofing"], "product": ["view"]}}, headers=adm, timeout=30)
    assert _assess(pic["h"], S_PROOF).status_code != 403


def test_t06_cannot_edit_own_role(pic):
    r = requests.patch(f"{BASE}/api/access/roles/{pic['rid']}", json={"hidden_views": []}, headers=pic["h"], timeout=30)
    assert r.status_code == 403
