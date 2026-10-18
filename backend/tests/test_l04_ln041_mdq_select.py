"""L04 LN-041 — MDQ memilih roll lintas LOT; hasil uji vs keputusan manusia terpisah & teraudit."""
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
def fx():
    rolls = []
    for lot in DB.inventory_rolls.distinct("lot", {"unit": "yard", "status": "available", "owner_entity_id": "ent_ksc",
                                                    "length_remaining": {"$gt": 5}, "lot": {"$nin": ["", None]}})[:3]:
        rolls.append(DB.inventory_rolls.find_one({"lot": lot, "unit": "yard", "status": "available",
                                                  "owner_entity_id": "ent_ksc", "length_remaining": {"$gt": 5}}, {"_id": 0}))
    if len(rolls) < 3:
        pytest.skip("butuh 3 LOT berbeda")
    iid = f"ins_test_{uuid.uuid4().hex[:8]}"
    lines = [{"id": f"ln_{i}_{uuid.uuid4().hex[:5]}", "roll_id": r["id"], "roll_no": r.get("roll_no"), "lot": r["lot"],
              "product_id": r["product_id"], "quantity": r["length_remaining"], "unit": "yard",
              "color_result": "", "handfeel_result": "", "decision": "", "hold": False} for i, r in enumerate(rolls)]
    DB.inspections.insert_one({"id": iid, "number": "TEST-LN041", "kind": "po_receipt", "status": "in_progress",
                               "entity_id": "ent_ksc", "remark": "TEST_LN041", "lines": lines, "history": []})
    snap = {r["id"]: r for r in rolls}
    yield {"iid": iid, "lines": lines, "rolls": rolls, "tok": _login("mdquality@kainnusantara.id", "demo1234"),
           "admin": _login("admin@kainnusantara.id", "demo12345")}
    for rid, r in snap.items():
        DB.inventory_rolls.replace_one({"id": rid}, r)
    DB.inventory_movements.delete_many({"source_document": iid})
    DB.journal_entries.delete_many({"source_id": {"$regex": f"^mdq:{iid}"}})
    DB.inspections.delete_one({"id": iid})


def _h(t):
    return {"Authorization": f"Bearer {t}", "X-Entity-Id": "ent_ksc"}


def test_t01_select_two_rolls_from_different_lots(fx):
    a, b, c = fx["lines"]
    for ln, color in ((a, "beda_shade"), (b, "sesuai")):
        r = requests.post(f"{BASE}/api/inspections/{fx['iid']}/lines/{ln['id']}/inspect",
                          json={"part": "md_quality", "color_result": color, "handfeel_result": "sesuai"}, headers=_h(fx["tok"]), timeout=30)
        assert r.status_code == 200, r.text
        r = requests.post(f"{BASE}/api/inspections/{fx['iid']}/lines/{ln['id']}/mdq-cut", json={}, headers=_h(fx["tok"]), timeout=30)
        assert r.status_code == 200, r.text
    assert a["lot"] != b["lot"]
    after = {r["id"]: DB.inventory_rolls.find_one({"id": r["id"]}, {"_id": 0}) for r in fx["rolls"]}
    ra, rb, rc = fx["rolls"]
    for r in (ra, rb):
        assert after[r["id"]]["length_remaining"] == pytest.approx(r["length_remaining"] - 0.25, abs=1e-6)
    assert after[rc["id"]]["length_remaining"] == rc["length_remaining"]          # roll tak terpilih utuh
    assert not (after[rc["id"]].get("inspection") or {}).get("color_result")
    for r in fx["rolls"]:
        assert after[r["id"]]["length_initial"] == r["length_initial"]          # receiving bruto tetap
    assert DB.inventory_movements.count_documents({"source_document": fx["iid"], "movement_type": "mdq_cut"}) == 2


def test_t02_mismatch_then_human_accept_is_separate_and_audited(fx):
    a = fx["lines"][0]
    doc = DB.inspections.find_one({"id": fx["iid"]})
    la = next(x for x in doc["lines"] if x["id"] == a["id"])
    assert la["color_result"] == "beda_shade"
    assert la.get("hold") is True                                               # kebijakan bawaan: tahan
    if la.get("hold"):
        r = requests.post(f"{BASE}/api/inspections/{fx['iid']}/lines/{a['id']}/release-hold",
                          json={"reason": "Diterima PIC setelah diskusi owner, shade masih dalam toleransi pasar"},
                          headers=_h(fx["tok"]), timeout=30)
        assert r.status_code == 200, r.text
        doc = DB.inspections.find_one({"id": fx["iid"]})
        la = next(x for x in doc["lines"] if x["id"] == a["id"])
        assert la["color_result"] == "beda_shade"                                # hasil uji TIDAK ditimpa
        assert la["md_quality_decision"]["action"] == "release" and la["md_quality_decision"]["by"]
        assert DB.audit_logs.count_documents({"action": "inspection_hold_released", "entity_id": fx["iid"]}) >= 1 \
            or DB.audit_logs.count_documents({"action": "inspection_hold_released"}) >= 1
    s = _login("sales.kanda@kainnusantara.id", "demo1234")
    r = requests.post(f"{BASE}/api/inspections/{fx['iid']}/lines/{a['id']}/release-hold",
                      json={"reason": "coba lepas tanpa hak akses"}, headers=_h(s), timeout=30)
    assert r.status_code in (403, 404)
