"""L10 LN-101 — opname per roll: scan ganda, hilang, salah rak, cutoff/delta, otorisasi & retry sekali."""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
WH = "wh_jakarta"
TAG = uuid.uuid4().hex[:6]
WH_DOC = DB.warehouses.find_one({"id": WH}, {"_id": 0})
ZONE = next(z for z in WH_DOC["zones"] if z["id"] == "zone_sim_wh_jkt_w")
LEVEL = ZONE["racks"][-1]["levels"][0]
B1, B2 = LEVEL["bins"][0], LEVEL["bins"][1]
LEVEL_OTHER_BIN = ZONE["racks"][-1]["levels"][1]["bins"][0]
PROD = DB.products.find_one({"stage": "finished", "status": "active"}, {"_id": 0, "id": 1})
ROLLS, SESSIONS = [], []


def _login(email, pw="demo12345"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _roll(qty, bin_doc):
    rid = f"roll_TEST_{TAG}_{len(ROLLS)}"
    DB.inventory_rolls.insert_one({"id": rid, "roll_no": f"TEST-{TAG}-{len(ROLLS)}", "product_id": PROD["id"], "warehouse_id": WH,
                                   "owner_entity_id": "ent_ksc", "length_remaining": qty, "length_initial": qty, "unit": "yard",
                                   "status": "available", "bin_id": bin_doc["id"], "bin_code": bin_doc["code"], "grade": "A", "unit_cost": 10})
    ROLLS.append(rid)
    return rid


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    DB.inventory_rolls.delete_many({"id": {"$in": ROLLS}})
    DB.inventory_movements.delete_many({"roll_id": {"$in": ROLLS}})
    DB.journal_entries.delete_many({"source_type": "cycle_count_variance", "source_id": {"$regex": "|".join(SESSIONS) or "x^"}})
    DB.cycle_count_sessions.delete_many({"id": {"$in": SESSIONS}})
    DB.inventory_rolls.delete_many({"acquired_via": "cycle_count_found", "ref_id": {"$in": SESSIONS}})
    DB.inventory_movements.delete_many({"source_document": {"$regex": "|".join(SESSIONS) or "x^"}})


def test_ln101_full_flow():
    adm, wh = _login("admin@kainnusantara.id", "demo12345"), _login("warehouse@kainnusantara.id")
    r_ok, r_twice, r_missing, r_wrong, r_cut = (_roll(50, B1) for _ in range(5))
    s = requests.post(f"{BASE}/cycle-count/sessions", json={"warehouse_id": WH, "name": f"TEST_roll {TAG}"}, headers=adm).json()
    SESSIONS.append(s["id"])
    snap = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scope", json={"node_id": LEVEL["id"]}, headers=adm).json()
    assert snap["expected_rolls"] >= 5
    scan = lambda code, b, q=None, tag="ok": requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scans",  # noqa: E731
                                                          json={"code": code, "bin_id": b, "measured_qty": q, "tag": tag}, headers=adm).json()
    assert "matched" in scan(r_ok, B1["id"])["scan"]["kinds"]
    first = scan(f"TEST-{TAG}-1", B1["id"], 50)
    assert first["duplicate"] is False
    assert scan(r_twice, B1["id"], 50)["duplicate"] is True                    # T01 — scan ganda
    assert "wrong_address" in scan(r_wrong, B2["id"])["scan"]["kinds"]         # T01 — salah rak
    # T02 — gerakan setelah snapshot (sebelum scan): potong 10 → fisik 35 → selisih vs live (40) = -5
    DB.inventory_rolls.update_one({"id": r_cut}, {"$set": {"length_remaining": 40}})
    assert "qty_diff" in scan(r_cut, B1["id"], 35)["scan"]["kinds"]
    assert "unknown" in scan(f"ASING-{TAG}", B1["id"], tag="unreadable")["scan"]["kinds"]
    rec = requests.get(f"{BASE}/cycle-count/sessions/{s['id']}/roll-reconcile", headers=adm).json()
    assert r_missing in {m["roll_id"] for m in rec["missing"]} and rec["duplicates"] >= 1
    # T03 — counter tanpa ACC ditolak
    r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-finalize", json={"reason": "coba langsung"}, headers=wh)
    assert r.status_code in (403, 404), r.text
    r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-finalize", json={"reason": f"final {TAG}"}, headers=adm)
    assert r.status_code == 200 and r.json()["status"] == "approved_with_exceptions", r.text
    assert DB.inventory_rolls.find_one({"id": r_cut})["length_remaining"] == 35
    assert DB.inventory_rolls.find_one({"id": r_wrong})["bin_id"] == B2["id"]
    assert DB.inventory_rolls.find_one({"id": r_missing})["length_remaining"] == 50   # hilang tidak auto-adjust (OPS-01)
    assert DB.journal_entries.count_documents({"source_id": f"{s['id']}:roll:{r_cut}"}) == 1
    r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-finalize", json={"reason": f"ulang {TAG}"}, headers=adm)
    assert r.status_code == 400                                                     # retry tidak mengulang
    assert DB.inventory_rolls.find_one({"id": r_cut})["length_remaining"] == 35
    assert DB.journal_entries.count_documents({"source_id": f"{s['id']}:roll:{r_cut}"}) == 1


def test_ln101_changed_after_scan_requires_recount():
    adm = _login("admin@kainnusantara.id", "demo12345")
    rid = _roll(30, B1)
    s = requests.post(f"{BASE}/cycle-count/sessions", json={"warehouse_id": WH, "name": f"TEST_roll2 {TAG}"}, headers=adm).json()
    SESSIONS.append(s["id"])
    requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scope", json={"node_id": B1["id"]}, headers=adm)
    requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scans", json={"code": rid, "bin_id": B1["id"], "measured_qty": 28}, headers=adm)
    DB.inventory_rolls.update_one({"id": rid}, {"$set": {"length_remaining": 25}})   # dipotong sesudah discan
    r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-finalize", json={"reason": f"final {TAG}"}, headers=adm).json()
    assert r["status"] == "open" and r["recount"]
    assert DB.inventory_rolls.find_one({"id": rid})["length_remaining"] == 25
    requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scans", json={"code": rid, "bin_id": B1["id"], "measured_qty": 24}, headers=adm)
    r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-finalize", json={"reason": f"final2 {TAG}"}, headers=adm).json()
    assert r["status"] in ("approved", "approved_with_exceptions")
    assert DB.inventory_rolls.find_one({"id": rid})["length_remaining"] == 24


def test_ln101_relocation_into_qc_area_is_exception_not_applied():
    adm = _login("admin@kainnusantara.id", "demo12345")
    q1, q2 = {"id": "bin_p02_wh_jkt_q01_01", "code": "Q01-T1-01"}, "bin_p02_wh_jkt_q01_02"
    rid = _roll(20, q1)
    s = requests.post(f"{BASE}/cycle-count/sessions", json={"warehouse_id": WH, "name": f"TEST_roll3 {TAG}"}, headers=adm).json()
    SESSIONS.append(s["id"])
    requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scope", json={"node_id": "zone_p02_wh_jkt_qc"}, headers=adm)
    requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scans", json={"code": rid, "bin_id": q2}, headers=adm)
    r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-finalize", json={"reason": f"final {TAG}"}, headers=adm).json()
    assert r["status"] == "approved_with_exceptions"
    assert DB.inventory_rolls.find_one({"id": rid})["bin_id"] == q1["id"]
    assert DB.cycle_count_sessions.find_one({"id": s["id"]})["roll_exceptions"]["relocation_blocked"] == 1


def test_ops01_missing_recount_writeoff_foreign_relocate_unknown_new_roll():
    adm, wh = _login("admin@kainnusantara.id", "demo12345"), _login("warehouse@kainnusantara.id")
    r_lost, r_noconf = _roll(40, B1), _roll(30, B1)
    r_foreign = _roll(25, LEVEL_OTHER_BIN)           # di gudang sama, di luar scope
    s = requests.post(f"{BASE}/cycle-count/sessions", json={"warehouse_id": WH, "name": f"TEST_ops01 {TAG}"}, headers=adm).json()
    SESSIONS.append(s["id"])
    requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scope", json={"node_id": B1["id"]}, headers=adm)
    sc = lambda body: requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scans", json=body, headers=adm).json()  # noqa: E731
    assert "foreign" in sc({"code": r_foreign, "bin_id": B1["id"]})["scan"]["kinds"]
    unk = sc({"code": f"NODATA-{TAG}", "bin_id": B1["id"], "measured_qty": 12})["scan"]
    # hitung ulang: counter boleh mencatat; roll di luar daftar hilang → 400
    r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-missing-recount", json={"roll_id": r_lost}, headers=wh)
    assert r.status_code == 200, r.text
    assert requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-missing-recount", json={"roll_id": r_foreign}, headers=adm).status_code == 400
    n_before = DB.inventory_rolls.count_documents({"opname_found_code": f"NODATA-{TAG}"})
    r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-finalize", headers=adm, json={
        "reason": f"ops01 {TAG}", "zero_cost_reason": "uji",
        "new_rolls": [{"scan_id": unk["id"], "product_id": PROD["id"], "owner_entity_id": "ent_ksc"}]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "approved_with_exceptions"            # r_noconf belum dihitung ulang
    lost = DB.inventory_rolls.find_one({"id": r_lost})
    assert lost["status"] == "consumed" and lost["length_remaining"] == 0 and lost["lost_in_count"]["session_id"] == s["id"]
    assert DB.inventory_rolls.find_one({"id": r_noconf})["length_remaining"] == 30
    assert DB.inventory_rolls.find_one({"id": r_foreign})["bin_id"] == B1["id"]
    new = DB.inventory_rolls.find_one({"opname_found_code": f"NODATA-{TAG}"})
    assert n_before == 0 and new and new["length_remaining"] == 12 and new["bin_id"] == B1["id"]
    ROLLS.append(new["id"])
    assert DB.journal_entries.count_documents({"source_id": f"{s['id']}:missing:{r_lost}"}) <= 1
    assert DB.cycle_count_sessions.find_one({"id": s["id"]})["roll_exceptions"]["missing_unconfirmed"] >= 1
    assert requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-finalize", json={"reason": "ulang lagi"}, headers=adm).status_code == 400
    assert DB.inventory_rolls.count_documents({"opname_found_code": f"NODATA-{TAG}"}) == 1
