"""L10 T1 review — LN-100/LN-102 (stock-tree, migrasi, rules fabric, putaway tanpa jurnal, Meja Saya) + LN-101 opname per roll (kinds lengkap)."""
import copy
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
_env = open(os.path.join(os.path.dirname(__file__), "..", ".env")).read()
_dbn = _env.split("DB_NAME=")[1].split()[0].strip('"')
_mu = _env.split("MONGO_URL=")[1].split()[0].strip('"')
DB = MongoClient(_mu)[_dbn]
WH = "wh_jakarta"
TAG = uuid.uuid4().hex[:6]
WH_DOC = DB.warehouses.find_one({"id": WH}, {"_id": 0})
ZONES_BEFORE = copy.deepcopy(WH_DOC["zones"])
ZONE = next(z for z in WH_DOC["zones"] if z["id"] == "zone_sim_wh_jkt_w")
RACK = ZONE["racks"][-1]
LV1, LV2, LV3 = RACK["levels"][0], RACK["levels"][1], RACK["levels"][2]
B1, B2 = LV1["bins"][0], LV1["bins"][1]
WOVEN = DB.products.find_one({"fabric_type": "woven", "status": "active"}, {"_id": 0, "id": 1})
KNIT = DB.products.find_one({"fabric_type": "knit", "status": "active"}, {"_id": 0, "id": 1})
ROLLS, SESSIONS, NOTES = [], [], []


def _login(email, pw="demo12345"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _roll(qty, bin_doc, owner="ent_ksc", prod=None, wh=WH, extra=None):
    rid = f"roll_TEST_{TAG}_{len(ROLLS)}"
    DB.inventory_rolls.insert_one({"id": rid, "roll_no": f"TEST-{TAG}-{len(ROLLS)}", "rfid_epc": f"EPC{TAG}{len(ROLLS)}",
                                   "product_id": (prod or WOVEN)["id"], "warehouse_id": wh, "owner_entity_id": owner,
                                   "length_remaining": qty, "length_initial": qty, "unit": "yard", "status": "available",
                                   "bin_id": bin_doc["id"] if bin_doc else "", "bin_code": bin_doc["code"] if bin_doc else "",
                                   "grade": "A", "unit_cost": 10, **(extra or {})})
    ROLLS.append(rid)
    return rid


@pytest.fixture(scope="module")
def adm():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    DB.inventory_rolls.delete_many({"id": {"$in": ROLLS}})
    DB.inventory_movements.delete_many({"roll_id": {"$in": ROLLS}})
    if SESSIONS:
        DB.journal_entries.delete_many({"source_id": {"$regex": "|".join(SESSIONS)}})
    DB.cycle_count_sessions.delete_many({"id": {"$in": SESSIONS}})
    DB.location_migrations.delete_many({"reason": {"$regex": TAG}})
    DB.notifications.delete_many({"id": {"$in": NOTES}})
    DB.warehouses.update_one({"id": WH}, {"$set": {"zones": ZONES_BEFORE}})


def _find(n, nid):
    if n["id"] == nid:
        return n
    for c in n["children"]:
        h = _find(c, nid)
        if h:
            return h
    return None


# LN-100 — site tree & owner outside access
def test_site_tree_and_owner_scope(adm):
    site = WH_DOC.get("site_id")
    r = requests.get(f"{BASE}/warehouse-sites/{site}/stock-tree", headers=adm)
    assert r.status_code == 200, r.text
    t = r.json()["tree"]
    assert t["kind"] == "site" and any(c["id"] == WH for c in t["children"])
    total = sum(v["total"] for v in t["by_unit"].values())
    assert abs(total - sum(sum(v["total"] for v in c["by_unit"].values()) for c in t["children"])) < 0.01
    wh = _login("warehouse@kainnusantara.id")
    r = requests.get(f"{BASE}/warehouses/{WH}/stock-tree", params={"owner": "ent_7487424c3f95"}, headers=wh)
    print("warehouse@ owner CST:", r.status_code, r.text[:150])
    r2 = requests.get(f"{BASE}/warehouses/{WH}/stock-tree", params={"owner": "ent_tidak_ada"}, headers=adm)
    assert r2.status_code == 403, r2.text


# LN-100 FIX — W-OVER-01 (seed overfilled) unchanged must not trigger migration
def test_resave_unchanged_structure_no_migration(adm):
    r = requests.put(f"{BASE}/warehouses/{WH}/structure", json={"zones": copy.deepcopy(ZONES_BEFORE)}, headers=adm)
    assert r.status_code == 200, r.text


# LN-100-T02 — rules.fabric_types woven on a node of a SHARED warehouse (RCM-WOVEN): woven roll of other entity accepted, knit rejected
SHWH = DB.warehouses.find_one({"code": "RCM-WOVEN"})["id"]


def test_fabric_rule_evaluate(adm):
    doc = DB.warehouses.find_one({"id": SHWH}, {"_id": 0})
    before = copy.deepcopy(doc["zones"])
    zones = copy.deepcopy(before)
    lv = next(l for z in zones for rk in z.get("racks", []) for l in rk.get("levels", []) if l.get("bins"))
    lv["rules"] = {**(lv.get("rules") or {}), "fabric_types": ["woven"]}
    target = lv["bins"][0]["id"]
    r = requests.put(f"{BASE}/warehouses/{SHWH}/structure", json={"zones": zones}, headers=adm)
    assert r.status_code == 200, r.text
    try:
        w = _roll(10, None, owner="ent_kanda", prod=WOVEN, wh=SHWH)
        k = _roll(10, None, owner="ent_kanda", prod=KNIT, wh=SHWH)
        rw = requests.get(f"{BASE}/inventory/putaway/evaluate", params={"roll_id": w, "bin": target}, headers=adm).json()
        rk = requests.get(f"{BASE}/inventory/putaway/evaluate", params={"roll_id": k, "bin": target}, headers=adm).json()
        print("woven:", rw.get("ok"), rw.get("blocks"))
        print("knit:", rk.get("ok"), rk.get("blocks"))
        assert rw.get("ok") is True, rw
        assert rk.get("ok") is False and "knit" in str(rk.get("blocks")).lower(), rk
    finally:
        DB.warehouses.update_one({"id": SHWH}, {"$set": {"zones": before}})


# LN-102-T03 — putaway: no journals, stock-tree total unchanged
def test_putaway_no_journal(adm):
    rid = _roll(25, B1)
    def tot():
        t = requests.get(f"{BASE}/warehouses/{WH}/stock-tree", headers=adm).json()["tree"]
        return t["rolls"], round(t["by_unit"]["yard"]["total"], 3)
    before, nj = tot(), DB.journal_entries.count_documents({})
    r = requests.post(f"{BASE}/inventory/putaway", json={"roll_id": rid, "bin_id": LV2["bins"][2]["id"], "override_reason": ""}, headers=adm)
    assert r.status_code == 200, r.text
    assert DB.inventory_rolls.find_one({"id": rid})["bin_id"] == LV2["bins"][2]["id"]
    assert DB.journal_entries.count_documents({}) == nj
    assert tot() == before


# LN-102-T02 — Meja Saya: duplicate turn notifications deduped; count == rows
@pytest.mark.parametrize("email,pw,uid", [("admin@kainnusantara.id", "demo12345", "user_admin_01"),
                                          ("warehouse@kainnusantara.id", "demo12345", "user_wh_01")])
def test_my_desk_turn_dedupe(email, pw, uid):
    h = _login(email, pw)
    def turn():
        d = requests.get(f"{BASE}/desks/me", headers=h).json()
        q = next(q for q in d["queues"] if q["id"] == "giliran_saya")
        for qq in d["queues"]:
            assert qq.get("shown", len(qq["rows"])) == len(qq["rows"]) and qq["count"] >= len(qq["rows"])
        return q
    base = turn()["count"]
    for i in range(3):
        nid = f"ntf_TEST_{TAG}_{uid}_{i}"
        NOTES.append(nid)
        DB.notifications.insert_one({"id": nid, "recipient_user": uid, "type": "turn", "read": False,
                                     "title": f"Giliran Anda — uji: TEST/{TAG}", "body": "uji", "link": "purchase-orders",
                                     "action_id": f"purchase_orders:po_TEST_{TAG}" if i < 2 else f"sales_orders:so_TEST_{TAG}",
                                     "created_at": f"2026-10-19T0{i}:00:00+00:00"})
    q = turn()
    assert q["count"] == base + 2, (base, q["count"])
    row = next(r for r in q["rows"] if r["ref_id"] == f"po_TEST_{TAG}")
    assert row["ref_type"] == "purchase_order" and row["link"] == "purchase-orders"


def test_manager_desk_counts():
    h = _login("manager@kainnusantara.id")
    d = requests.get(f"{BASE}/desks/me", headers=h).json()
    assert d["total_items"] == sum(len(q["rows"]) for q in d["queues"])
    for q in d["queues"]:
        assert q["count"] == len(q["rows"])


# LN-101 — kinds: rfid lookup, tag_damaged, foreign, delta_in, moved_after_cutoff, unknown; finalize authz & reason
def test_roll_count_all_kinds(adm):
    r_match = _roll(40, B1)
    r_dmg = _roll(40, B1)
    r_moved = _roll(40, B1)
    r_foreign = _roll(40, ZONE["racks"][0]["levels"][0]["bins"][0])   # outside scope (other rack)
    s = requests.post(f"{BASE}/cycle-count/sessions", json={"warehouse_id": WH, "name": f"TEST_t1 {TAG}"}, headers=adm).json()
    SESSIONS.append(s["id"])
    snap = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scope", json={"node_id": RACK["id"]}, headers=adm)
    assert snap.status_code == 200, snap.text
    assert {r_match, r_dmg, r_moved} <= {e["roll_id"] for e in DB.cycle_count_sessions.find_one({"id": s["id"]})["roll_count"]["expected"]}
    r_delta = _roll(40, B2)   # enters scope after snapshot
    DB.inventory_rolls.update_one({"id": r_moved}, {"$set": {"bin_id": ZONE["racks"][0]["levels"][0]["bins"][1]["id"]}})
    sc = lambda code, b, q=None, tag="ok": requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scans",  # noqa: E731
                                                        json={"code": code, "bin_id": b, "measured_qty": q, "tag": tag}, headers=adm).json()
    assert "matched" in sc(f"EPC{TAG}{ROLLS.index(r_match)}", B1["id"], 40)["scan"]["kinds"]   # via rfid_epc
    assert "tag_damaged" in sc(r_dmg, B1["id"], tag="damaged")["scan"]["kinds"]
    assert "foreign" in sc(r_foreign, B1["id"])["scan"]["kinds"]
    assert "delta_in" in sc(r_delta, B2["id"])["scan"]["kinds"]
    assert "unknown" in sc(f"XX-{TAG}", B1["id"])["scan"]["kinds"]
    assert sc(f"XX-{TAG}", B1["id"])["duplicate"] is True
    bad = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scans", json={"code": r_match, "bin_id": "bin_luar", "tag": "ok"}, headers=adm)
    assert bad.status_code == 400
    bad = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scans", json={"code": r_match, "bin_id": B1["id"], "tag": "x"}, headers=adm)
    assert bad.status_code == 400
    rec = requests.get(f"{BASE}/cycle-count/sessions/{s['id']}/roll-reconcile", headers=adm).json()
    assert r_moved in {m["roll_id"] for m in rec["moved_after_cutoff"]}
    assert rec["counts"]["foreign"] == 1 and rec["counts"]["delta_in"] == 1 and rec["duplicates"] >= 1
    # rescope after scans → 409
    assert requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scope", json={"node_id": ""}, headers=adm).status_code == 409
    wh = _login("warehouse@kainnusantara.id")
    assert requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-finalize", json={"reason": "final ok"}, headers=wh).status_code == 403
    assert requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-finalize", json={"reason": "abc"}, headers=adm).status_code == 400
    r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-finalize", json={"reason": f"final {TAG}"}, headers=adm)
    assert r.status_code == 200 and r.json()["status"] == "approved_with_exceptions", r.text
    # OPS-01 (2026-10-18): roll asing dari gudang yang sama dipindah ke alamat tempat ditemukan
    assert DB.inventory_rolls.find_one({"id": r_foreign})["bin_id"] != ZONE["racks"][0]["levels"][0]["bins"][0]["id"]
    assert requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-finalize", json={"reason": f"ulang {TAG}"}, headers=adm).status_code == 400


def test_roll_count_bad_node(adm):
    s = requests.post(f"{BASE}/cycle-count/sessions", json={"warehouse_id": WH, "name": f"TEST_t1b {TAG}"}, headers=adm).json()
    SESSIONS.append(s["id"])
    r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scope", json={"node_id": "nope"}, headers=adm)
    assert r.status_code == 400
    r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scans", json={"code": "x", "bin_id": B1["id"]}, headers=adm)
    assert r.status_code == 400


# LN-101 — operator (warehouse@) counts, whadmin finalizes; invalid qty rejected
def test_roll_count_operator_and_whadmin(adm):
    wh, wa = _login("warehouse@kainnusantara.id"), _login("whadmin@kainnusantara.id")
    rid = _roll(30, B1)
    r = requests.post(f"{BASE}/cycle-count/sessions", json={"warehouse_id": WH, "name": f"TEST_t1c {TAG}"}, headers=wh)
    assert r.status_code in (200, 201), r.text
    s = r.json(); SESSIONS.append(s["id"])
    r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scope", json={"node_id": B1["id"]}, headers=wh)
    assert r.status_code == 200, r.text
    for bad in (-5, "abc"):
        r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scans", json={"code": rid, "bin_id": B1["id"], "measured_qty": bad}, headers=wh)
        assert r.status_code == 400, (bad, r.text)
    r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scans", json={"code": rid, "bin_id": B1["id"], "measured_qty": 29}, headers=wh)
    assert r.status_code == 200 and "qty_diff" in r.json()["scan"]["kinds"], r.text
    assert requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-finalize", json={"reason": "final op"}, headers=wh).status_code == 403
    r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-finalize", json={"reason": f"final whadmin {TAG}"}, headers=wa)
    assert r.status_code == 200, r.text
    assert DB.inventory_rolls.find_one({"id": rid})["length_remaining"] == 29
    je = DB.journal_entries.find_one({"source_id": f"{s['id']}:roll:{rid}"}, {"_id": 0})
    assert je is not None
    print("JE:", {k: je.get(k) for k in ("source_type", "entity_id", "total_debit", "description")})


# LN-101 — concurrent duplicate scans → 1 row; partial apply + recount → no double journal
def test_roll_count_race_and_partial(adm):
    from concurrent.futures import ThreadPoolExecutor
    a, b = _roll(20, B1), _roll(20, B1)
    s = requests.post(f"{BASE}/cycle-count/sessions", json={"warehouse_id": WH, "name": f"TEST_t1d {TAG}"}, headers=adm).json()
    SESSIONS.append(s["id"])
    requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scope", json={"node_id": B1["id"]}, headers=adm)
    f = lambda _: requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scans",  # noqa: E731
                                json={"code": a, "bin_id": B1["id"], "measured_qty": 18}, headers=adm).json()
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(f, range(6)))
    assert sum(1 for r in res if r.get("duplicate") is False) == 1, res
    sess = DB.cycle_count_sessions.find_one({"id": s["id"]})
    assert len([x for x in sess["roll_count"]["scans"] if x["roll_id"] == a]) == 1
    requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scans", json={"code": b, "bin_id": B1["id"], "measured_qty": 19}, headers=adm)
    DB.inventory_rolls.update_one({"id": b}, {"$set": {"length_remaining": 15}})
    r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-finalize", json={"reason": f"final {TAG}"}, headers=adm).json()
    assert r["status"] == "open" and r["recount"], r
    assert DB.inventory_rolls.find_one({"id": a})["length_remaining"] == 18
    requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scans", json={"code": b, "bin_id": B1["id"], "measured_qty": 14}, headers=adm)
    r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-finalize", json={"reason": f"final2 {TAG}"}, headers=adm)
    assert r.status_code == 200 and r.json()["status"] in ("approved", "approved_with_exceptions"), r.text
    assert DB.inventory_rolls.find_one({"id": a})["length_remaining"] == 18
    assert DB.inventory_rolls.find_one({"id": b})["length_remaining"] == 14
    assert DB.journal_entries.count_documents({"source_id": f"{s['id']}:roll:{a}"}) == 1
    assert DB.inventory_movements.count_documents({"source_document": f"{s['id']}:roll:{a}"}) == 1


# LN-101 (probe) — roll under active movement / QC bin target: does finalize relocate anyway?
def test_probe_relocate_active_movement_and_qc_bin(adm):
    a = _roll(20, B1, extra={"active_movement": {"id": "mv_TEST", "number": "TRF-TEST"}})
    qc_bin = "bin_p02_wh_jkt_q01_01"
    c = _roll(20, B1)
    s = requests.post(f"{BASE}/cycle-count/sessions", json={"warehouse_id": WH, "name": f"TEST_t1e {TAG}"}, headers=adm).json()
    SESSIONS.append(s["id"])
    requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scope", json={"node_id": ""}, headers=adm)
    requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scans", json={"code": a, "bin_id": B2["id"]}, headers=adm)
    requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scans", json={"code": c, "bin_id": qc_bin}, headers=adm)
    r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-finalize", json={"reason": f"probe {TAG}"}, headers=adm)
    ra, rc = DB.inventory_rolls.find_one({"id": a}), DB.inventory_rolls.find_one({"id": c})
    print("PROBE finalize", r.status_code, "active_movement roll bin:", ra["bin_id"], "| available roll -> qc bin:", rc["bin_id"], rc["status"])
