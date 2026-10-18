"""L10 OPS-01 T1 review — 'Terisi di Rak' (binned_rolls) + SOP opname: hilang (hitung ulang → hapus),
roll asing (pindah alamat / beda gudang = exception), kode tak dikenal → roll baru."""
import copy
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
_env = open(os.path.join(os.path.dirname(__file__), "..", ".env")).read()
DB = MongoClient(_env.split("MONGO_URL=")[1].split()[0].strip('"'))[_env.split("DB_NAME=")[1].split()[0].strip('"')]
WH = "wh_jakarta"
TAG = uuid.uuid4().hex[:6]
WH_DOC = DB.warehouses.find_one({"id": WH}, {"_id": 0})
ZONES_BEFORE = copy.deepcopy(WH_DOC["zones"])
ZONE = next(z for z in WH_DOC["zones"] if z["id"] == "zone_sim_wh_jkt_w")
RACK = ZONE["racks"][-1]
B1, B2 = RACK["levels"][0]["bins"][0], RACK["levels"][0]["bins"][1]
OTHER_BIN = ZONE["racks"][0]["levels"][0]["bins"][0]
PROD = DB.products.find_one({"fabric_type": "woven", "status": "active"}, {"_id": 0, "id": 1})
ROLLS, SESSIONS = [], []


def _login(email, pw="demo1234"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _roll(qty, bin_doc, owner="ent_ksc", wh=WH, extra=None, bin_id=None):
    rid = f"roll_TEST_{TAG}_{len(ROLLS)}"
    DB.inventory_rolls.insert_one({"id": rid, "roll_no": f"TEST-{TAG}-{len(ROLLS)}", "product_id": PROD["id"],
                                   "warehouse_id": wh, "owner_entity_id": owner, "length_remaining": qty,
                                   "length_initial": qty, "unit": "yard", "status": "available",
                                   "bin_id": bin_id if bin_id is not None else (bin_doc["id"] if bin_doc else ""),
                                   "bin_code": bin_doc["code"] if bin_doc else "", "grade": "A", "unit_cost": 10,
                                   **(extra or {})})
    ROLLS.append(rid)
    return rid


@pytest.fixture(scope="module")
def adm():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    found = [r["id"] for r in DB.inventory_rolls.find({"acquired.via": "cycle_count_found", "acquired.ref_id": {"$in": SESSIONS}}, {"id": 1, "lot_id": 1})]
    lots = [r.get("lot_id") for r in DB.inventory_rolls.find({"id": {"$in": found}}, {"lot_id": 1})]
    ids = ROLLS + found
    DB.inventory_rolls.delete_many({"id": {"$in": ids}})
    DB.inventory_movements.delete_many({"roll_id": {"$in": ids}})
    if SESSIONS:
        DB.journal_entries.delete_many({"source_id": {"$regex": "|".join(SESSIONS)}})
    DB.cycle_count_sessions.delete_many({"id": {"$in": SESSIONS}})
    DB.warehouses.update_one({"id": WH}, {"$set": {"zones": ZONES_BEFORE}})
    # found rolls may join an EXISTING lot (do not delete lots) — recompute counters
    import asyncio, sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    try:
        from services import lot_service as ls
        asyncio.run(ls.recompute_many([x for x in set(lots) if x]))
        for lid in set(lots):
            if lid and DB.inventory_rolls.count_documents({"lot_id": lid}) == 0:
                DB.inventory_lots.delete_one({"id": lid, "source_ref.type": "cycle_count_found"})
    except Exception as e:  # noqa: BLE001
        print("lot recompute skipped:", e)


def _session(h, node):
    s = requests.post(f"{BASE}/cycle-count/sessions", json={"warehouse_id": WH, "name": f"TEST_ops01t1 {TAG}"}, headers=h).json()
    SESSIONS.append(s["id"])
    r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scope", json={"node_id": node}, headers=h)
    assert r.status_code == 200, r.text
    return s["id"]


def _scan(sid, h, **body):
    r = requests.post(f"{BASE}/cycle-count/sessions/{sid}/roll-scans", json={"tag": "ok", **body}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


# Terisi di Rak — binned_rolls only counts master bins (not unassigned / orphan)
def test_locations_binned_rolls(adm):
    before = requests.get(f"{BASE}/warehouses/{WH}/locations", headers=adm).json()
    assert "binned_rolls" in before and "binned_by_unit" in before
    _roll(5, B1); _roll(5, None, bin_id=""); _roll(5, None, bin_id=f"bin_ghost_{TAG}")
    after = requests.get(f"{BASE}/warehouses/{WH}/locations", headers=adm).json()
    assert after["binned_rolls"] == before["binned_rolls"] + 1
    assert after["unassigned"]["rolls"] == before["unassigned"]["rolls"] + 1
    assert after["orphan"]["rolls"] == before["orphan"]["rolls"] + 1
    assert after["total_rolls"] == before["total_rolls"] + 3
    assert after["binned_rolls"] == after["total_rolls"] - after["unassigned"]["rolls"] - after["orphan"]["rolls"]
    assert round(after["binned_by_unit"].get("yard", 0) - before["binned_by_unit"].get("yard", 0), 2) == 5
    print("binned", after["binned_rolls"], "total", after["total_rolls"], "unassigned", after["unassigned"]["rolls"], "orphan", after["orphan"]["rolls"])


# missing recount permissions & validation
def test_missing_recount_validation(adm):
    wh = _login("warehouse@kainnusantara.id")
    lost, matched = _roll(40, B1), _roll(30, B1)
    sid = _session(adm, B1["id"])
    _scan(sid, adm, code=matched, bin_id=B1["id"])
    u = lambda rid, h: requests.post(f"{BASE}/cycle-count/sessions/{sid}/roll-missing-recount", json={"roll_id": rid}, headers=h)  # noqa: E731
    assert u(matched, adm).status_code == 400
    assert u("roll_nope", adm).status_code == 400
    r = u(lost, wh)
    assert r.status_code == 200, r.text
    m = next(x for x in r.json()["missing"] if x["roll_id"] == lost)
    assert m["recount"] and m["recount"]["by"]
    assert "OPS-01" in r.json()["policy"]
    # unauthenticated
    assert requests.post(f"{BASE}/cycle-count/sessions/{sid}/roll-missing-recount", json={"roll_id": lost}).status_code in (401, 403)


# write-off: consumed, movement, journal once, balance; unconfirmed untouched
def test_missing_writeoff_full(adm):
    lost, keep = _roll(40, B1), _roll(30, B1)
    others = [e["roll_id"] for e in []]
    sid = _session(adm, B1["id"])
    # scan every other expected roll so they are not 'missing'
    sess = DB.cycle_count_sessions.find_one({"id": sid})
    for e in sess["roll_count"]["expected"]:
        if e["roll_id"] not in (lost, keep):
            _scan(sid, adm, code=e["roll_id"], bin_id=e["bin_id"])
    requests.post(f"{BASE}/cycle-count/sessions/{sid}/roll-missing-recount", json={"roll_id": lost}, headers=adm)
    r = requests.post(f"{BASE}/cycle-count/sessions/{sid}/roll-finalize", json={"reason": f"wo {TAG}"}, headers=adm)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "approved_with_exceptions"
    ro = DB.inventory_rolls.find_one({"id": lost})
    assert ro["status"] == "consumed" and ro["length_remaining"] == 0 and ro["lost_in_count"]["qty"] == 40
    mv = list(DB.inventory_movements.find({"roll_id": lost, "movement_type": "cycle_count_write_off"}))
    assert len(mv) == 1 and mv[0]["quantity"] == -40
    je = list(DB.journal_entries.find({"source_type": "cycle_count_variance", "source_id": f"{sid}:missing:{lost}"}))
    assert len(je) == 1
    print("JE missing:", je[0].get("total_debit"), je[0].get("entity_id"))
    assert DB.inventory_rolls.find_one({"id": keep})["length_remaining"] == 30
    sess = DB.cycle_count_sessions.find_one({"id": sid})
    assert sess["roll_exceptions"].get("missing_unconfirmed") == 1
    m = next(x for x in body["missing"] if x["roll_id"] == lost)
    assert m.get("adjustment", {}).get("status") == "applied"
    # re-finalize rejected, no 2nd journal
    assert requests.post(f"{BASE}/cycle-count/sessions/{sid}/roll-finalize", json={"reason": "ulang lagi"}, headers=adm).status_code == 400
    assert DB.journal_entries.count_documents({"source_id": f"{sid}:missing:{lost}"}) == 1
    # recount after closed → 400
    assert requests.post(f"{BASE}/cycle-count/sessions/{sid}/roll-missing-recount", json={"roll_id": keep}, headers=adm).status_code == 400


# PROBE: missing roll recounted, then qty cut in place before finalize → stuck in recount loop?
def test_probe_missing_changed_qty_after_recount(adm):
    lost = _roll(40, B2)
    sid = _session(adm, B2["id"])
    for e in DB.cycle_count_sessions.find_one({"id": sid})["roll_count"]["expected"]:
        if e["roll_id"] != lost:
            _scan(sid, adm, code=e["roll_id"], bin_id=e["bin_id"])
    requests.post(f"{BASE}/cycle-count/sessions/{sid}/roll-missing-recount", json={"roll_id": lost}, headers=adm)
    DB.inventory_rolls.update_one({"id": lost}, {"$set": {"length_remaining": 35}})
    r1 = requests.post(f"{BASE}/cycle-count/sessions/{sid}/roll-finalize", json={"reason": f"p1 {TAG}"}, headers=adm).json()
    r2 = requests.post(f"{BASE}/cycle-count/sessions/{sid}/roll-finalize", json={"reason": f"p2 {TAG}"}, headers=adm).json()
    still = [m for m in r2.get("missing", []) if m["roll_id"] == lost]
    print("PROBE qty-changed missing: r1", r1.get("status"), r1.get("recount"), "| r2", r2.get("status"), r2.get("recount"),
          "| still missing:", bool(still), "| roll qty", DB.inventory_rolls.find_one({"id": lost})["length_remaining"])
    # record result for report; deadlock if r2 still open with same recount
    pytest.deadlock = r2.get("status") == "open" and bool(r2.get("recount"))


# PROBE: missing roll that is committed to a SO → written off silently?
def test_probe_missing_committed_roll(adm):
    lost = _roll(20, B2, extra={"status": "committed", "allocated_to": {"order_id": f"so_TEST_{TAG}"}, "length_reserved": 5})
    sid = _session(adm, B2["id"])
    for e in DB.cycle_count_sessions.find_one({"id": sid})["roll_count"]["expected"]:
        if e["roll_id"] != lost:
            _scan(sid, adm, code=e["roll_id"], bin_id=e["bin_id"])
    requests.post(f"{BASE}/cycle-count/sessions/{sid}/roll-missing-recount", json={"roll_id": lost}, headers=adm)
    r = requests.post(f"{BASE}/cycle-count/sessions/{sid}/roll-finalize", json={"reason": f"p {TAG}"}, headers=adm)
    ro = DB.inventory_rolls.find_one({"id": lost})
    print("PROBE committed missing:", r.status_code, r.json().get("status"), "roll status", ro["status"], ro["length_remaining"],
          "reserved", ro.get("length_reserved"))


# foreign: same wh → relocated (movement cycle_count_relocation); other wh → exception
def test_foreign_same_and_other_warehouse(adm):
    same = _roll(25, OTHER_BIN)
    other = _roll(25, None, wh="wh_bandung", bin_id="")
    sid = _session(adm, B1["id"])
    for e in DB.cycle_count_sessions.find_one({"id": sid})["roll_count"]["expected"]:
        _scan(sid, adm, code=e["roll_id"], bin_id=e["bin_id"])
    assert "foreign" in _scan(sid, adm, code=same, bin_id=B1["id"])["scan"]["kinds"]
    assert "foreign" in _scan(sid, adm, code=other, bin_id=B1["id"])["scan"]["kinds"]
    r = requests.post(f"{BASE}/cycle-count/sessions/{sid}/roll-finalize", json={"reason": f"fr {TAG}"}, headers=adm)
    assert r.status_code == 200, r.text
    assert DB.inventory_rolls.find_one({"id": same})["bin_id"] == B1["id"]
    assert DB.inventory_movements.count_documents({"roll_id": same, "movement_type": "cycle_count_relocation"}) == 1
    o = DB.inventory_rolls.find_one({"id": other})
    assert o["warehouse_id"] == "wh_bandung" and o["bin_id"] == ""
    sess = DB.cycle_count_sessions.find_one({"id": sid})
    ln = next(s for s in sess["roll_count"]["scans"] if s["roll_id"] == other)
    assert ln["adjustment"]["status"] == "exception" and "transfer" in ln["adjustment"]["message"].lower()
    assert sess["status"] == "approved_with_exceptions" and sess["roll_exceptions"].get("relocation_blocked", 0) >= 1


# unknown code → validation + new roll with qty override + surplus journal
def test_unknown_code_new_roll(adm):
    wa = _login("whadmin@kainnusantara.id")
    sid = _session(adm, B1["id"])
    for e in DB.cycle_count_sessions.find_one({"id": sid})["roll_count"]["expected"]:
        _scan(sid, adm, code=e["roll_id"], bin_id=e["bin_id"])
    u1 = _scan(sid, adm, code=f"UNK1-{TAG}", bin_id=B1["id"], measured_qty=12)["scan"]
    u2 = _scan(sid, adm, code=f"UNK2-{TAG}", bin_id=B1["id"])["scan"]
    u3 = _scan(sid, adm, code=f"UNK3-{TAG}", bin_id=B1["id"], measured_qty=4)["scan"]
    fin = lambda body, h=adm: requests.post(f"{BASE}/cycle-count/sessions/{sid}/roll-finalize", json={"reason": f"unk {TAG}", "zero_cost_reason": "uji", **body}, headers=h)  # noqa: E731
    sp = lambda u, **k: {"scan_id": u["id"], "product_id": PROD["id"], "owner_entity_id": "ent_ksc", **k}  # noqa: E731
    assert fin({"new_rolls": [sp(u1, product_id="prod_nope")]}).status_code == 400
    assert fin({"new_rolls": [sp(u2)]}).status_code == 400            # no qty & no measured
    assert fin({"new_rolls": [sp(u1, qty=0)]}).status_code in (400,)
    assert fin({"new_rolls": [sp(u1, qty=-3)]}).status_code == 400
    assert fin({"new_rolls": [sp(u1, owner_entity_id="ent_7487424c3f95")]}, wa).status_code == 403
    assert DB.cycle_count_sessions.find_one({"id": sid})["status"] == "open"
    r = fin({"new_rolls": [sp(u1, qty=7), sp(u2, qty=3)]})
    assert r.status_code == 200, r.text
    n1 = DB.inventory_rolls.find_one({"opname_found_code": f"UNK1-{TAG}"})
    n2 = DB.inventory_rolls.find_one({"opname_found_code": f"UNK2-{TAG}"})
    assert n1 and n1["length_remaining"] == 7 and n1["bin_id"] == B1["id"] and n1["acquired"]["via"] == "cycle_count_found"
    assert n2 and n2["length_remaining"] == 3
    assert not DB.inventory_rolls.find_one({"opname_found_code": f"UNK3-{TAG}"})
    sess = DB.cycle_count_sessions.find_one({"id": sid})
    assert sess["roll_exceptions"].get("unknown_unresolved") == 1
    ln = next(s for s in sess["roll_count"]["scans"] if s["id"] == u1["id"])
    print("found roll adj:", {k: ln["adjustment"].get(k) for k in ("new_roll_no", "unit_cost", "cost_basis", "value", "journal_id")})
    assert fin({"new_rolls": [sp(u3)]}).status_code == 400
    assert DB.inventory_rolls.count_documents({"opname_found_code": {"$regex": TAG}}) == 2


# PROBE: admin (view_all) creates found roll with non-existent owner entity
def test_probe_found_roll_bad_owner(adm):
    sid = _session(adm, B2["id"])
    for e in DB.cycle_count_sessions.find_one({"id": sid})["roll_count"]["expected"]:
        _scan(sid, adm, code=e["roll_id"], bin_id=e["bin_id"])
    u = _scan(sid, adm, code=f"UNKX-{TAG}", bin_id=B2["id"], measured_qty=2)["scan"]
    r = requests.post(f"{BASE}/cycle-count/sessions/{sid}/roll-finalize", headers=adm, json={
        "reason": f"bad owner {TAG}", "zero_cost_reason": "uji",
        "new_rolls": [{"scan_id": u["id"], "product_id": PROD["id"], "owner_entity_id": "ent_TIDAK_ADA"}]})
    n = DB.inventory_rolls.find_one({"opname_found_code": f"UNKX-{TAG}"})
    print("PROBE bad owner:", r.status_code, "roll created:", bool(n), (n or {}).get("owner_entity_id"))
