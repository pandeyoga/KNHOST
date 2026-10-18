"""LN-014 — lot internal vs lot supplier: dua identitas, riwayat perubahan, alias configurable (KLX-01)."""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
TAG = f"TEST_LN014_{uuid.uuid4().hex[:5]}"
SUP = f"234{uuid.uuid4().hex[:4]}"
TPL = DB.inventory_rolls.find_one({"owner_entity_id": "ent_ksc", "status": "available"})


@pytest.fixture(scope="module")
def h():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
    yield {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}
    DB.inventory_lots.delete_many({"note": TAG})
    DB.inventory_rolls.delete_many({"notes": TAG})
    DB.system_settings.update_one({"scope": "lot"}, {"$unset": {"alias_mode": "", "alias_unique_scope": ""}})


def _lot(h, supplier_lot=SUP, supplier_id="sup_x"):
    r = requests.post(f"{BASE}/lots", headers=h, json={"product_id": TPL["product_id"], "owner_entity_id": "ent_ksc",
                                                        "supplier_lot": supplier_lot, "supplier_id": supplier_id,
                                                        "note": TAG, "source": "manual"})
    assert r.status_code == 200, r.text
    DB.inventory_lots.update_one({"id": r.json()["id"]}, {"$set": {"roll_count": 2}})
    return r.json()


def test_identity_change_requires_reason_and_keeps_history(h):
    lot = _lot(h)
    r = requests.patch(f"{BASE}/lots/{lot['id']}", headers=h, json={"supplier_lot": SUP + "B"})
    assert r.status_code == 400 and "alasan" in r.json()["detail"]
    r = requests.patch(f"{BASE}/lots/{lot['id']}", headers=h, json={"supplier_lot": SUP + "B", "reason": "salah ketik SJ"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["lot_number"] == lot["lot_number"] and out["supplier_lot"] == SUP + "B"
    hist = out["identity_history"][-1]
    assert hist["field"] == "supplier_lot" and hist["before"] == SUP and hist["after"] == SUP + "B"
    r = requests.patch(f"{BASE}/lots/{lot['id']}", headers=h, json={"note": TAG})
    assert r.status_code == 400  # tidak ada perubahan


def test_alias_off_by_default_then_manual_unique(h):
    a, b = _lot(h, SUP + "X"), _lot(h, SUP + "Y")
    r = requests.patch(f"{BASE}/lots/{a['id']}", headers=h, json={"internal_alias": f"KN-{TAG}", "reason": "alias uji"})
    assert r.status_code == 400 and "KLX-01" in r.json()["detail"]
    DB.system_settings.update_one({"scope": "lot"}, {"$set": {"alias_mode": "manual"}}, upsert=True)
    r = requests.patch(f"{BASE}/lots/{a['id']}", headers=h, json={"internal_alias": f"KN-{TAG}", "reason": "alias uji"})
    assert r.status_code == 200, r.text
    dup = requests.patch(f"{BASE}/lots/{b['id']}", headers=h, json={"internal_alias": f"KN-{TAG}", "reason": "alias uji"})
    assert dup.status_code == 400 and a["lot_number"] in dup.json()["detail"]
    other_sup = _lot(h, SUP + "Z", supplier_id="sup_other")
    ok = requests.patch(f"{BASE}/lots/{other_sup['id']}", headers=h, json={"internal_alias": f"KN-{TAG}", "reason": "alias supplier lain"})
    assert ok.status_code == 200, ok.text
    DB.system_settings.update_one({"scope": "lot"}, {"$set": {"alias_unique_scope": "entity"}})
    c = _lot(h, SUP + "W", supplier_id="sup_third")
    assert requests.patch(f"{BASE}/lots/{c['id']}", headers=h,
                          json={"internal_alias": f"KN-{TAG}", "reason": "lintas supplier"}).status_code == 400


def test_trace_by_supplier_lot_shows_both_identities_and_return_rolls(h):
    lot = _lot(h, SUP + "T")
    src = f"roll_{TAG}_{uuid.uuid4().hex[:6]}"
    base = {k: v for k, v in TPL.items() if k != "_id"}
    DB.inventory_rolls.insert_many([
        {**base, "id": src, "roll_no": f"{TAG}-1", "lot_id": lot["id"], "notes": TAG, "rfid_tag": "", "tag_id": ""},
        {**base, "id": f"roll_{TAG}_{uuid.uuid4().hex[:6]}", "roll_no": f"{TAG}-R", "lot_id": "lot_other",
         "origin_type": "return", "return_id": "sret_x", "source_roll_ids": [src], "notes": TAG, "rfid_tag": "", "tag_id": ""}])
    r = requests.get(f"{BASE}/lots/identity-trace", headers=h, params={"code": SUP + "T"})
    assert r.status_code == 200, r.text
    row = next(x for x in r.json()["rows"] if x["lot_id"] == lot["id"])
    assert row["lot_number"] != row["supplier_lot"] == SUP + "T"
    assert row["matched_on"] == ["Lot supplier"]
    assert [x["roll_no"] for x in row["return_rolls"]] == [f"{TAG}-R"]
    by_internal = requests.get(f"{BASE}/lots/identity-trace", headers=h, params={"code": lot["lot_number"]}).json()
    assert by_internal["rows"][0]["matched_on"] == ["Nomor lot internal"]
    assert requests.get(f"{BASE}/lots/identity-trace", headers=h, params={"code": "x"}).status_code == 400
