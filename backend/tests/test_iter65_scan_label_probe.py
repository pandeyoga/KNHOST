"""GRN Fase 1 — scan-label behavior probe (unchanged after refactor).

Verifies: 200 OK first, 409 DUPLICATE same roll no, 400 OVER_PO, 400 UNMAPPED.
Cleans up via DELETE /inbound/rolls/{roll_id}/scan and restores task doc.
"""
import os, sys, uuid, copy
import pytest, requests
from dotenv import load_dotenv
from pymongo import MongoClient
load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api" if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE:
    for ln in open("/app/frontend/.env"):
        if ln.startswith("REACT_APP_BACKEND_URL="):
            BASE = ln.split("=", 1)[1].strip().rstrip("/") + "/api"


@pytest.fixture(scope="module")
def wh():
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": "warehouse@kainnusantara.id", "password": "demo12345"}, timeout=30)
    assert r.status_code == 200
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"})
    return s


@pytest.fixture(scope="module")
def mdb():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def test_scan_label_behaviour(wh, mdb):
    seed = mdb.wms_tasks.find_one({"flow_type": "inbound", "product_id": "prod_batik_mega",
                                   "status": {"$in": ["waiting_goods", "receiving"]},
                                   "po_id": {"$gt": ""}, "entity_id": "ent_ksc"}, {"_id": 0})
    assert seed, "seed missing inbound task for prod_batik_mega"
    original = copy.deepcopy(seed)
    tid = seed["id"]
    tag = uuid.uuid4().hex[:5]
    created_rolls = []
    try:
        # 1) unknown supplier code → 400 UNMAPPED
        r = wh.post(f"{BASE}/inbound/tasks/{tid}/scan-label",
                    json={"raw": f"UNKNOWN-CODE|DL-X|R{tag}|50"}, timeout=30)
        assert r.status_code == 400, r.text
        assert "UNMAPPED" in r.text or "unmapped" in r.text.lower() or "tidak dikenal" in r.text.lower(), r.text

        # 2) valid → 200
        rno = f"R{tag}A"
        r = wh.post(f"{BASE}/inbound/tasks/{tid}/scan-label",
                    json={"raw": f"CBN-MEGA-PREM|DL-X|{rno}|50"}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        roll = body.get("roll") or body
        rid = roll.get("id") or roll.get("roll_id")
        assert rid, body
        created_rolls.append(rid)
        # data assertions
        rd = mdb.inventory_rolls.find_one({"id": rid}, {"_id": 0})
        assert rd["status"] == "receiving", rd
        assert float(rd.get("declared_length") or rd.get("length_initial") or 0) == 50.0, rd
        assert "rfid_epc" in roll or ("rfid_epc" in rd), "rfid_epc field missing on API response and roll doc"  # value depends on auto_rfid_on_scan config
        t2 = mdb.wms_tasks.find_one({"id": tid}, {"_id": 0})
        assert t2["status"] == "receiving", t2["status"]
        assert float(t2.get("received_qty") or 0) >= 50.0

        # 3) duplicate roll_no → 409
        r = wh.post(f"{BASE}/inbound/tasks/{tid}/scan-label",
                    json={"raw": f"CBN-MEGA-PREM|DL-X|{rno}|50"}, timeout=30)
        assert r.status_code == 409, r.text
        assert "DUP" in r.text.upper() or "ganda" in r.text.lower()

        # 4) qty over remaining → 400 OVER_PO
        po = mdb.purchase_orders.find_one({"id": seed["po_id"]}, {"_id": 0, "items": 1})
        line = next(i for i in po["items"] if i["product_id"] == seed["product_id"])
        huge = float(line.get("qty") or line.get("quantity") or line.get("qty_ordered") or 1000) * 10
        r = wh.post(f"{BASE}/inbound/tasks/{tid}/scan-label",
                    json={"raw": f"CBN-MEGA-PREM|DL-X|R{tag}B|{huge:g}"}, timeout=30)
        assert r.status_code == 400, r.text
        assert "OVER" in r.text.upper() or "melebihi" in r.text.lower(), r.text
    finally:
        for rid in created_rolls:
            try:
                wh.delete(f"{BASE}/inbound/rolls/{rid}/scan", timeout=30)
            except Exception:
                pass
            mdb.inventory_rolls.delete_one({"id": rid})
        # restore task doc exactly
        mdb.wms_tasks.replace_one({"id": tid}, original)
