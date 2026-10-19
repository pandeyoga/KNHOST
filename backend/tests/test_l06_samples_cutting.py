"""L06 — sample 3 jenis + catalogue terurai (LN-060), cutting lintas lokasi/owner + Admin Cutting (LN-061),
ecer berbayar potong roll (LN-062). Data uji: artikel 9 warna buatan sendiri (dibersihkan di teardown)."""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ENT, OTHER = "ent_ksc", "ent_kanda"
CUST, ADDR = "cust_butik_bali", "addr_002"
WH_A, WH_B = "wh_bandung", "wh_surabaya"
TAG = uuid.uuid4().hex[:6]
TPL = f"ptpl_l06_{TAG}"
COLORS = ["MERAH", "BIRU", "HIJAU", "KUNING", "HITAM", "PUTIH", "ABU", "UNGU", "COKLAT"]


def _login():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


@pytest.fixture(scope="module")
def h():
    return _login()


def _roll(pid, wh, length, owner=ENT):
    tpl = DB.inventory_rolls.find_one({"owner_entity_id": ENT, "status": "available"}, {"_id": 0})
    rid = f"roll_l06_{uuid.uuid4().hex[:8]}"
    doc = {**tpl, "id": rid, "roll_no": f"L06-{rid[-6:]}", "product_id": pid, "warehouse_id": wh, "owner_entity_id": owner,
           "length_initial": length, "length_remaining": length, "length_reserved": 0, "length_reservations": [],
           "status": "available", "reserved_ref": None, "active_movement": None, "rfid_tag_id": None, "unit": "yard",
           "pending_cut_ops": [], "created_at": "2000-01-01T00:00:00+00:00", "is_remnant": False, "_l06": TAG}
    doc.pop("weight_kg", None)
    DB.inventory_rolls.insert_one(dict(doc))
    return rid


@pytest.fixture(scope="module")
def art():
    base = DB.products.find_one({"fabric_type": "woven", "base_unit": "yard", "price": {"$gt": 0}}, {"_id": 0})
    pids = []
    for i, c in enumerate(COLORS):
        pid = f"prod_l06_{TAG}_{i}"
        DB.products.insert_one({**base, "id": pid, "variant_key": f"TEST_{pid}", "sku": f"L06{TAG}-{c}", "name": f"ARTIKEL L06 {c}", "color": c, "color_name": c,
                                "template_id": TPL, "_l06": TAG, "price": 10000})
        pids.append(pid)
    rolls = {}
    for i in range(5):   # 5 dari 9 warna tersedia; warna 3-4 di gudang B (dua lokasi)
        rolls[pids[i]] = _roll(pids[i], WH_A if i < 3 else WH_B, 100.0)
    other_pid = pids[8]
    other_roll = _roll(other_pid, WH_A, 50.0, owner=OTHER)   # warna 8 hanya stok PT lain
    caps_before = {w["id"]: w.get("cutting_caps") for w in DB.warehouses.find({"id": {"$in": [WH_A, WH_B]}}, {"_id": 0})}
    yield {"pids": pids, "rolls": rolls, "other_pid": other_pid, "other_roll": other_roll, "orders": []}
    h = _login()
    for oid in art_orders:
        requests.post(f"{BASE}/sales-orders/{oid}/cancel", json={"reason": "TEST L06 cleanup"}, headers=h, timeout=60)
    DB.wms_tasks.delete_many({"order_id": {"$in": art_orders}})
    DB.sales_orders.delete_many({"id": {"$in": art_orders}})
    DB.inventory_rolls.delete_many({"$or": [{"_l06": TAG}, {"product_id": {"$in": pids}}]})
    DB.inventory_movements.delete_many({"product_id": {"$in": pids}})
    DB.products.delete_many({"_l06": TAG})
    for wid, caps in caps_before.items():
        DB.warehouses.update_one({"id": wid}, {"$set": {"cutting_caps": caps}} if caps is not None else {"$unset": {"cutting_caps": ""}})


art_orders = []


def _so(h, items, order_type="sample", billing="free", **extra):
    r = requests.post(f"{BASE}/sales-orders", json={"customer_id": CUST, "shipping_address_id": ADDR, "entity_id": ENT,
                                                     "order_type": order_type, "sample_billing": billing if order_type == "sample" else "",
                                                     "items": items, **extra}, headers=h, timeout=120)
    if r.status_code == 200:
        art_orders.append(r.json()["id"])
    return r


def _line(pid, qty, kind="standard", **kw):
    return {"product_id": pid, "quantity": qty, "unit": "yard", "base_quantity": qty, "is_sample": True, "sample_kind": kind, **kw}


# ── LN-060 ──
def test_ln060_t01_catalogue_counts_available_colors(h, art):
    r = requests.get(f"{BASE}/sample-orders/catalogue/preview", params={"template_id": TPL, "soft_product_id": art["pids"][0]},
                     headers=h, timeout=30)
    assert r.status_code == 200, r.text[:300]
    c = r.json()
    assert c["colors_total"] == 9 and c["colors_available"] == 5
    assert len(c["base"]) == 5 and all(x["quantity"] == 1.0 for x in c["base"])
    assert c["soft"]["quantity"] == 2.0 and c["total_qty"] == 7.0


def test_ln060_t02_change_soft_keeps_base(h, art):
    p = art["pids"]
    r = _so(h, [], catalogue={"template_id": TPL, "soft_product_id": p[0]})
    assert r.status_code == 200, r.text[:300]
    so = r.json()
    qty = {i["product_id"]: i["quantity"] for i in so["items"]}
    assert qty[p[0]] == 3.0 and sum(qty.values()) == 7.0
    art["cat_so"] = so["id"]
    r2 = requests.post(f"{BASE}/sample-orders/{so['id']}/catalogue/soft", json={"product_id": p[1]}, headers=h, timeout=60)
    assert r2.status_code == 200, r2.text[:300]
    s2 = r2.json()
    assert s2["catalogue"]["base"] == so["catalogue"]["base"]
    assert s2["catalogue"]["soft"]["product_id"] == p[1]
    q2 = {i["product_id"]: i["quantity"] for i in s2["items"]}
    assert q2[p[0]] == 1.0 and q2[p[1]] == 3.0 and sum(q2.values()) == 7.0


def test_ln060_t03_standard_limit_and_ecer(h, art):
    r = _so(h, [_line(art["pids"][0], 6.0)])
    assert r.status_code == 400 and "SAMPLE_LIMIT" in r.text, r.text[:300]
    e = _so(h, [{"product_id": art["pids"][0], "quantity": 6.0, "unit": "yard", "base_quantity": 6.0}], order_type="regular")
    assert e.status_code == 200, e.text[:300]
    assert e.json()["number"].split("/")[-1].startswith("SO-")


def test_ln060_t04_hanger_not_forced_up(h, art):
    r = _so(h, [_line(art["pids"][1], 0.25, "hanger")])
    assert r.status_code == 200, r.text[:300]
    assert r.json()["items"][0]["quantity"] == 0.25 and r.json()["items"][0]["sample_kind"] == "hanger"
    bad = _so(h, [_line(art["pids"][1], 0.6, "hanger")])
    assert bad.status_code == 400 and "SAMPLE_LIMIT" in bad.text
    knit = DB.products.find_one({"fabric_type": "knit", "base_unit": "kg", "price": {"$gt": 0}, "lifecycle": {"$in": [None, "produksi"]}, "exclusive_customer_id": {"$in": [None, ""]}}, {"_id": 0})
    ok = _so(h, [{"product_id": knit["id"], "quantity": 2.0, "unit": "kg", "base_quantity": 2.0, "is_sample": True, "sample_kind": "hanger"}])
    assert ok.status_code == 200, ok.text[:300]
    over = _so(h, [{"product_id": knit["id"], "quantity": 2.5, "unit": "kg", "base_quantity": 2.5, "is_sample": True, "sample_kind": "hanger"}])
    assert over.status_code == 400 and "SAMPLE_LIMIT" in over.text


# ── LN-061 ──
def test_ln061_t03_location_caps_same_on_api(h, art):
    r = requests.put(f"{BASE}/cutting/locations/{WH_B}", json={"caps": ["standard"]}, headers=h, timeout=30)
    assert r.status_code == 200 and r.json()["cutting_caps"] == ["standard"]
    bad = _so(h, [_line(art["pids"][3], 0.5, "hanger", cut_warehouse_id=WH_B)])
    assert bad.status_code == 400 and "LOCATION_KIND_NOT_ALLOWED" in bad.text, bad.text[:300]
    prev = requests.get(f"{BASE}/sample-orders/catalogue/preview", params={"template_id": TPL}, headers=h, timeout=30).json()
    assert prev["colors_available"] == 3   # warna di gudang B tidak ikut catalogue
    std = _so(h, [_line(art["pids"][3], 1.0, "standard", cut_warehouse_id=WH_B)])
    assert std.status_code == 200, std.text[:300]
    requests.put(f"{BASE}/cutting/locations/{WH_B}", json={"caps": ["standard", "hanger", "catalogue"]}, headers=h, timeout=30)


def test_ln061_t01_other_owner_needs_internal_purchase(h, art):
    before = DB.inventory_rolls.find_one({"id": art["other_roll"]})["length_remaining"]
    r = _so(h, [_line(art["other_pid"], 2.0)])
    assert r.status_code == 200, r.text[:300]
    so = r.json()
    assert so["items"][0]["sample_cut_status"] == "awaiting_internal"
    assert so["items"][0]["source_owner_entity_id"] == OTHER
    doc = DB.sales_orders.find_one({"id": so["id"]})
    assert doc.get("internal_supply") and doc["internal_supply"][0]["seller_entity_id"] == OTHER
    assert requests.post(f"{BASE}/sample-orders/{so['id']}/confirm", headers=h, timeout=60).status_code == 200
    task = DB.wms_tasks.find_one({"order_id": so["id"], "task_subtype": "sample_cut"})
    c = requests.post(f"{BASE}/outbound/tasks/{task['id']}/cut-sample", json={"roll_id": art["other_roll"], "actual_length": 2.0,
                                                                              "reason": "uji lintas owner"}, headers=h, timeout=60)
    assert c.status_code == 400 and "ROLL_WRONG_ENTITY" in c.text, c.text[:300]
    assert DB.inventory_rolls.find_one({"id": art["other_roll"]})["length_remaining"] == before


def test_ln061_t02_catalogue_two_locations_handoff(h, art):
    sid = art["cat_so"]
    assert requests.post(f"{BASE}/sample-orders/{sid}/confirm", headers=h, timeout=60).status_code == 200
    tasks = list(DB.wms_tasks.find({"order_id": sid, "task_subtype": "sample_cut"}, {"_id": 0}))
    assert len(tasks) == 5 and {t["warehouse_id"] for t in tasks} == {WH_A, WH_B}
    for t in tasks:
        c = requests.post(f"{BASE}/outbound/tasks/{t['id']}/cut-sample",
                          json={"roll_id": art["rolls"][t["product_id"]], "actual_length": t["quantity"], "reason": "uji"}, headers=h, timeout=60)
        assert c.status_code == 200, c.text[:300]
    desk = requests.get(f"{BASE}/cutting/desk", headers=h, timeout=30).json()
    to_recv = [r for q in desk["queues"] if q["key"] == "to_receive" for r in q["rows"] if r["order_id"] == sid]
    assert len(to_recv) == 5
    from_b = next(t for t in tasks if t["warehouse_id"] == WH_B)
    adv = requests.post(f"{BASE}/wms/tasks/{from_b['id']}/advance", headers=h, timeout=60)
    print("advance packing:", adv.status_code, adv.text[:200])
    DB.wms_tasks.update_many({"order_id": sid, "task_subtype": "sample_cut"}, {"$set": {"status": "staging"}})
    d = requests.post(f"{BASE}/outbound/tasks/{from_b['id']}/dispatch", headers=h, timeout=60)
    assert d.status_code == 400 and "Admin Cutting" in d.text, d.text[:300]
    for t in tasks:
        rv = requests.post(f"{BASE}/cutting/tasks/{t['id']}/receive", json={"to_warehouse_id": WH_A}, headers=h, timeout=60)
        assert rv.status_code == 200, rv.text[:300]
    again = requests.post(f"{BASE}/cutting/tasks/{from_b['id']}/receive", json={"to_warehouse_id": WH_A}, headers=h, timeout=60)
    assert again.status_code == 200
    moved = DB.wms_tasks.find_one({"id": from_b["id"]})
    assert moved["cutting_handoff"]["from_warehouse_id"] == WH_B and moved["warehouse_id"] == WH_A
    child = DB.inventory_rolls.find_one({"id": moved["roll_id"]})
    assert child["warehouse_id"] == WH_A and child["parent_roll_id"] == art["rolls"][from_b["product_id"]]
    mv = list(DB.inventory_movements.find({"roll_id": child["id"], "movement_type": {"$in": ["cutting_handoff_out", "cutting_handoff_in"]}}))
    assert len(mv) == 2
    d2 = requests.post(f"{BASE}/outbound/tasks/{from_b['id']}/dispatch", headers=h, timeout=60)
    assert "Admin Cutting" not in d2.text, d2.text[:300]


# ── LN-062 ──
def test_ln062_t01_t02_ecer_cut_and_retry(h, art):
    pid = art["pids"][2]
    roll = art["rolls"][pid]
    DB.inventory_rolls.update_one({"id": roll}, {"$set": {"length_remaining": 100.0, "length_initial": 100.0}})
    DB.inventory_rolls.update_many({"product_id": pid, "id": {"$ne": roll}, "status": "available"}, {"$set": {"status": "hold"}})
    r = _so(h, [{"product_id": pid, "quantity": 12.0, "unit": "yard", "base_quantity": 12.0}], order_type="regular")
    assert r.status_code == 200, r.text[:300]
    so = r.json()
    assert so["items"][0]["reserved_qty"] == 12.0 and abs(so["total_amount"] - 12 * 10000) < 1
    parent = DB.inventory_rolls.find_one({"id": roll})
    rsv = next(x for x in parent["length_reservations"] if x["ref"]["id"] == so["id"])
    url = f"{BASE}/inventory/rolls/{roll}/reservations/{rsv['id']}/cut"
    c1 = requests.post(url, json={"actual_length": 12.0}, headers=h, timeout=60)
    assert c1.status_code == 200, c1.text[:300]
    c2 = requests.post(url, json={"actual_length": 12.0}, headers=h, timeout=60)   # retry → tidak potong dua kali
    assert c2.status_code in (404, 409)
    p2 = DB.inventory_rolls.find_one({"id": roll})
    assert p2["length_remaining"] == 88.0
    kids = list(DB.inventory_rolls.find({"parent_roll_id": roll, "reserved_ref.id": so["id"]}))
    if not kids:
        kids = list(DB.inventory_rolls.find({"id": c1.json()["child"]["id"]}))
    assert len(kids) == 1 and kids[0]["length_remaining"] == 12.0
    assert DB.inventory_movements.count_documents({"parent_roll_id": roll, "movement_type": "roll_cut", "source_document": so["id"]}) == 1
