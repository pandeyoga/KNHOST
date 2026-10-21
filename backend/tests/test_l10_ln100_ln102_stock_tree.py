"""L10 LN-100/LN-102 — stok per alamat (induk = jumlah anak), QC hold bukan tersedia, owner terpisah, migrasi struktur."""
import copy
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
RACK = ZONE["racks"][-1]                       # lemari kosong (Rak W11)
LV1, LV2 = RACK["levels"][0], RACK["levels"][1]
BIN = LV1["bins"][0]
PROD = DB.products.find_one({"stage": "finished", "status": "active"}, {"_id": 0, "id": 1})
ROLLS = []


def _login(email, pw="demo12345"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture(scope="module")
def adm():
    return _login("admin@kainnusantara.id", "demo12345")


def _roll(owner, qty, unit, status="available", bin_id=None):
    rid = f"roll_TEST_{TAG}_{len(ROLLS)}"
    DB.inventory_rolls.insert_one({"id": rid, "roll_no": f"TEST-{TAG}-{len(ROLLS)}", "product_id": PROD["id"], "warehouse_id": WH,
                                   "owner_entity_id": owner, "length_remaining": qty, "length_initial": qty, "unit": unit,
                                   "status": status, "bin_id": bin_id or BIN["id"], "bin_code": BIN["code"], "grade": "A"})
    ROLLS.append(rid)
    return rid


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    before = copy.deepcopy(WH_DOC["zones"])
    n_journal = DB.journal_entries.count_documents({})
    yield
    DB.inventory_rolls.delete_many({"id": {"$in": ROLLS}})
    DB.inventory_movements.delete_many({"roll_id": {"$in": ROLLS}})
    DB.location_migrations.delete_many({"reason": {"$regex": TAG}})
    DB.warehouses.update_one({"id": WH}, {"$set": {"zones": before}})
    assert DB.journal_entries.count_documents({}) == n_journal   # LN-102-T03 — movement internal tanpa jurnal


def _find(n, nid):
    if n["id"] == nid:
        return n
    for c in n["children"]:
        hit = _find(c, nid)
        if hit:
            return hit
    return None


def _sum_ok(n):
    if n["children"] and n["kind"] in ("zone", "lemari", "rak", "site"):
        for unit, v in n["by_unit"].items():
            child = sum((c["by_unit"].get(unit) or {}).get("total", 0) for c in n["children"])
            assert abs(child - v["total"]) < 0.01, (n["name"], unit, child, v["total"])
        assert sum(c["rolls"] for c in n["children"]) == n["rolls"], n["name"]
    for c in n["children"]:
        _sum_ok(c)


def test_t01_tree_parent_equals_children_and_owner_unit_split(adm):
    _roll("ent_ksc", 100, "yard")
    _roll("ent_kanda", 20, "kg", bin_id=LV2["bins"][0]["id"])
    _roll("ent_ksc", 50, "yard", status="quarantine")
    t = requests.get(f"{BASE}/warehouses/{WH}/stock-tree", headers=adm).json()["tree"]
    _sum_ok(t)
    lem = _find(t, RACK["id"])
    assert lem["rolls"] == 3 and lem["by_unit"]["yard"]["available"] == 100 and lem["by_unit"]["yard"]["qc_hold"] == 50
    assert lem["by_unit"]["kg"]["total"] == 20 and "kg" not in _find(t, LV1["id"])["by_unit"]
    b = _find(t, BIN["id"])
    assert all(x in b["address"] for x in (ZONE["name"], RACK["name"], LV1["name"], BIN["code"]))
    only = requests.get(f"{BASE}/warehouses/{WH}/stock-tree", params={"owner": "ent_kanda"}, headers=adm).json()["tree"]
    assert set(_find(only, RACK["id"])["by_unit"]) == {"kg"}
    site = WH_DOC.get("site_id")
    if site:
        st = requests.get(f"{BASE}/warehouse-sites/{site}/stock-tree", headers=adm).json()["tree"]
        _sum_ok(st)


def test_t03_move_bin_with_stock_needs_migration_reason(adm):
    zones = copy.deepcopy(DB.warehouses.find_one({"id": WH}, {"_id": 0})["zones"])
    rk = next(r for z in zones for r in z.get("racks", []) if r["id"] == RACK["id"])
    moved = rk["levels"][0]["bins"].pop(0)
    rk["levels"][1]["bins"].append(moved)
    r = requests.put(f"{BASE}/warehouses/{WH}/structure", json={"zones": zones}, headers=adm)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "LOCATION_MIGRATION_REASON", r.text
    r = requests.put(f"{BASE}/warehouses/{WH}/structure", json={"zones": zones, "migration_reason": f"pindah rak {TAG}"}, headers=adm)
    assert r.status_code == 200, r.text
    mig = DB.location_migrations.find_one({"reason": f"pindah rak {TAG}"}, {"_id": 0})
    assert mig and mig["changes"][0]["bin_id"] == BIN["id"] and mig["changes"][0]["rolls"] >= 2
    roll = DB.inventory_rolls.find_one({"id": ROLLS[0]}, {"_id": 0, "bin_id": 1})
    assert roll["bin_id"] == BIN["id"]
    t = requests.get(f"{BASE}/warehouses/{WH}/stock-tree", headers=adm).json()["tree"]
    assert _find(t, LV2["id"])["rolls"] >= 3      # alamat baru ikut struktur, roll tidak disentuh
    moved["capacity_rolls"] = 1
    r = requests.put(f"{BASE}/warehouses/{WH}/structure", json={"zones": zones}, headers=adm)
    assert r.status_code == 409 and r.json()["detail"]["changes"][0]["capacity_below_content"] is True


def test_sales_scope_and_unknown(adm):
    assert requests.get(f"{BASE}/warehouses/wh_tidak_ada/stock-tree", headers=adm).status_code == 404
    h = _login("warehouse@kainnusantara.id")
    assert requests.get(f"{BASE}/warehouses/{WH}/stock-tree", params={"owner": "ent_tidak_ada"}, headers=h).status_code in (403, 404)
