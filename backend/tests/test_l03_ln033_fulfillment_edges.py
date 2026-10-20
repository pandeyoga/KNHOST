"""L03 LN-033 — edge cases rute pemenuhan Pesanan Khusus (izin, 'both', konkurensi rute, retry, create-pr, lock)."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ENT, CUST = "ent_ksc", "cust_toko_kain"
SUP = DB.suppliers.find_one({"entity_id": "all"}, {"_id": 0, "id": 1}, sort=[("name", 1)])["id"]
TPL = {m: DB.product_templates.find_one({"restock_source.mode": m}, {"_id": 0, "id": 1})["id"] for m in ("supplier", "makloon", "both")}
TAG = uuid.uuid4().hex[:6]
P_SUP = DB.products.find_one({"template_id": TPL["supplier"]}, {"_id": 0, "id": 1, "sku": 1})
P_MKL = DB.products.find_one({"template_id": TPL["makloon"]}, {"_id": 0, "id": 1, "sku": 1})
P_BOTH = DB.products.find_one({"template_id": TPL["both"]}, {"_id": 0, "id": 1, "sku": 1})
OD_IDS: list = []


def _login(email, pw="demo12345"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


@pytest.fixture(scope="module")
def H():
    return {"admin": _login("admin@kainnusantara.id", "demo12345"), "manager": _login("manager@kainnusantara.id"),
            "sales": _login("sales@kainnusantara.id"), "md": _login("md@kainnusantara.id")}


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    ids = OD_IDS
    prs = [p["id"] for p in DB.purchase_requisitions.find({"source_ref_id": {"$in": ids}}, {"id": 1})]
    DB.purchase_orders.delete_many({"special_order_id": {"$in": ids}})
    mkos = [m["id"] for m in DB.makloon_orders.find({"special_order_id": {"$in": ids}}, {"id": 1})]
    DB.makloon_orders.delete_many({"id": {"$in": mkos}})
    DB.material_reservations.delete_many({"$or": [{"ref_id": {"$in": mkos}}, {"pr_id": {"$in": prs}}]})
    DB.purchase_requisitions.delete_many({"id": {"$in": prs}})
    DB.md_samples.delete_many({"special_order_id": {"$in": ids}})
    DB.design_requests.delete_many({"special_order_id": {"$in": ids}})
    DB.special_orders.delete_many({"id": {"$in": ids}})


def _od(H, products, lock=True):
    items = [{"source_type": "parent_product", "source_product_id": p["id"], "description": f"TEST_E {i} {TAG}",
              "request_types": ["labdip"], "quantity": 5 + i, "unit": "kg"} for i, p in enumerate(products)]
    r = requests.post(f"{BASE}/special-orders", json={"customer_id": CUST, "title": f"TEST_LN033E_{TAG}", "entity_id": ENT,
                                                     "expected_delivery": "2026-12-31", "items": items,
                                                     "submit_for_approval": True}, headers=H["admin"])
    assert r.status_code in (200, 201), r.text
    od_id = r.json()["id"]
    OD_IDS.append(od_id)
    assert requests.post(f"{BASE}/special-orders/{od_id}/approve", json={"notes": "TEST"}, headers=H["admin"]).status_code == 200
    od = DB.special_orders.find_one({"id": od_id}, {"_id": 0})
    for it, p in zip(od["items"], products):
        DB.md_samples.insert_one({"id": f"smp_TEST_{uuid.uuid4().hex[:8]}", "number": f"TSE-{TAG}", "status": "decided",
                                  "special_order_id": od_id, "special_order_item_id": it["id"], "created_at": "2026-10-18T00:00:00",
                                  "decision": {"product_id": p["id"], "product_sku": p["sku"], "supplier_id": SUP,
                                               "supplier_name": "Ext", "price": 40000.0}})
    if lock:
        DB.special_orders.update_one({"id": od_id}, {"$set": {
            "status": "confirmed", "customer_decision": "acc", "price_locked": True,
            "pricing": {"locked": True, "product_id": products[0]["id"], "supplier_id": SUP, "supplier_name": "Ext",
                        "cost_price": 40000.0, "final_unit_price": 60000.0, "quantity": 5, "unit": "kg"}}})
    return od_id, [i["id"] for i in od["items"]]


def _get(H, od_id, who="admin"):
    r = requests.get(f"{BASE}/special-orders/{od_id}/fulfillment", headers=H[who])
    assert r.status_code == 200, r.text
    return r.json()


def _route(H, od_id, key, route, reason="", who="admin"):
    return requests.post(f"{BASE}/special-orders/{od_id}/fulfillment/{key}/route", json={"route": route, "reason": reason}, headers=H[who])


def _realize(H, od_id, key, who="admin", **body):
    return requests.post(f"{BASE}/special-orders/{od_id}/fulfillment/{key}/realize", json=body, headers=H[who])


# Izin: flag can per peran
def test_can_flags_per_role(H):
    od_id, (k1,) = _od(H, [P_SUP])
    can = {w: _get(H, od_id, w)["can"] for w in ("admin", "manager", "sales", "md")}
    print(can)
    assert all(can["admin"].values())
    assert can["manager"]["realize"] and can["manager"]["choose_route"]
    assert not can["sales"]["choose_route"] and not can["sales"]["realize"]


# Artikel 'both' → tanpa default, blocked sampai dipilih; pilih tanpa alasan boleh (alasan auto)
def test_both_article_requires_choice(H):
    od_id, (k1,) = _od(H, [P_BOTH])
    n = _get(H, od_id)["items"][0]
    assert n["default_route"] == "" and n["source_mode"] == "both" and n["status"] == "blocked"
    assert any("Jalur pemenuhan belum dipilih" in b for b in n["blockers"])
    assert _realize(H, od_id, k1).status_code == 400
    # create-pr manual pun menolak tanpa jalur
    r = requests.post(f"{BASE}/special-orders/{od_id}/create-pr", json={}, headers=H["admin"])
    assert r.status_code == 400 and "pilih jalur" in r.json()["detail"], r.text
    r = _route(H, od_id, k1, "purchase")
    assert r.status_code == 200, r.text
    st = r.json()["state"]
    assert st["deviation"] is False and st["reason"] and st["version"] == 1
    n = r.json()["fulfillment"]["items"][0]
    assert n["status"] == "ready"


# Rute sama dengan default → tanpa alasan OK; whitespace-only alasan saat deviasi → 400
def test_default_no_reason_and_blank_reason_deviation(H):
    od_id, (k1,) = _od(H, [P_SUP])
    assert _route(H, od_id, k1, "purchase").status_code == 200
    assert _route(H, od_id, k1, "makloon", "   ").status_code == 400
    # idempoten: pilih rute yang sama tidak menambah versi
    r = _route(H, od_id, k1, "purchase")
    assert r.status_code == 200 and r.json()["state"]["version"] == 1


# Konkurensi ubah rute: dua penyimpangan bersamaan → satu menang, lainnya 409 (bukan dua versi)
def test_concurrent_route_change(H):
    od_id, (k1,) = _od(H, [P_SUP])
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda r: _route(H, od_id, k1, r[0], r[1], r[2]),
                          [("makloon", "a", "admin"), ("makloon", "b", "manager"), ("makloon", "c", "admin"), ("makloon", "d", "manager")]))
    codes = [x.status_code for x in res]
    print(codes, [x.text[:120] for x in res if x.status_code != 200])
    assert 200 in codes and all(c in (200, 409) for c in codes)
    hist = DB.special_orders.find_one({"id": od_id})["fulfillment"][k1]["history"]
    assert len(hist) == 1, hist


# Sales tidak bisa realize/route; OD batal tidak bisa diubah rute
def test_sales_forbidden_and_cancelled_od(H):
    od_id, (k1,) = _od(H, [P_SUP])
    assert _route(H, od_id, k1, "purchase", who="sales").status_code == 403
    assert _realize(H, od_id, k1, who="sales").status_code == 403
    DB.special_orders.update_one({"id": od_id}, {"$set": {"status": "cancelled"}})
    assert _route(H, od_id, k1, "makloon", "x").status_code == 400


# Gudang tidak valid → 400, error tersimpan, kunci dilepas (realize berikutnya sukses)
def test_bad_warehouse_releases_lock(H):
    od_id, (k1,) = _od(H, [P_SUP])
    r = _realize(H, od_id, k1, warehouse_id="wh_TEST_nope")
    print(r.status_code, r.text[:200])
    assert r.status_code in (400, 403, 404), r.text
    od = DB.special_orders.find_one({"id": od_id})
    assert k1 not in (od.get("fulfillment_locks") or {})
    n = _get(H, od_id)["items"][0]
    assert n["status"] == "error" and n["error"]
    r = _realize(H, od_id, k1)
    assert r.status_code == 200 and r.json()["result"]["doc"]["type"] == "po", r.text
    assert _get(H, od_id)["items"][0]["status"] == "realized"


# needs_data (artikel supplier dipaksa makloon tanpa resep) → ganti ke purchase → PR makloon dibatalkan, PR baru purchase → PO
def test_needs_data_then_switch_back_to_purchase(H):
    od_id, (k1,) = _od(H, [P_SUP])
    assert _route(H, od_id, k1, "makloon", "coba makloon").status_code == 200
    r = _realize(H, od_id, k1)
    assert r.status_code == 200 and r.json()["result"].get("status") == "needs_data", r.text
    old_pr = DB.special_orders.find_one({"id": od_id})["fulfillment"][k1]["pr_id"]
    r = _route(H, od_id, k1, "purchase")
    assert r.status_code == 200, r.text
    pr_old = DB.purchase_requisitions.find_one({"id": old_pr})
    print("old PR status", pr_old["status"])
    assert pr_old["source_item_key"].endswith("#retired")
    r = _realize(H, od_id, k1)
    assert r.status_code == 200 and r.json()["result"]["doc"]["type"] == "po", r.text
    new_pr = r.json()["result"]["pr_id"]
    assert new_pr != old_pr
    assert DB.purchase_requisitions.find_one({"id": new_pr})["items"][0]["fulfillment_mode"] == "purchase"
    assert DB.purchase_orders.count_documents({"special_order_id": od_id}) == 1


# Kunci basi (>TTL) bisa diambil alih; kunci segar → 409
def test_fresh_lock_409_and_stale_lock_reclaimed(H):
    od_id, (k1,) = _od(H, [P_SUP])
    from datetime import datetime, timezone, timedelta
    DB.special_orders.update_one({"id": od_id}, {"$set": {f"fulfillment_locks.{k1}": {"at": datetime.now(timezone.utc).isoformat(), "by": "x"}}})
    assert _realize(H, od_id, k1).status_code == 409
    old = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    DB.special_orders.update_one({"id": od_id}, {"$set": {f"fulfillment_locks.{k1}": {"at": old, "by": "x"}}})
    r = _realize(H, od_id, k1)
    assert r.status_code == 200, r.text


# create-pr manual: per item, idempoten dgn realize (PR yang sama dipakai ulang)
def test_create_pr_manual_then_realize_reuses_pr(H):
    od_id, (k1,) = _od(H, [P_SUP])
    r = requests.post(f"{BASE}/special-orders/{od_id}/create-pr", json={"submit_now": True}, headers=H["admin"])
    print(r.status_code, r.text[:300])
    assert r.status_code == 200, r.text
    pr_id = r.json()["pr"]["id"]
    pr = DB.purchase_requisitions.find_one({"id": pr_id})
    assert pr["source_item_key"] == k1 and pr["items"][0]["fulfillment_mode"] == "purchase"
    r = _realize(H, od_id, k1)
    assert r.status_code == 200, r.text
    assert r.json()["result"]["pr_id"] == pr_id
    assert DB.purchase_requisitions.count_documents({"source_ref_id": od_id, "status": {"$ne": "cancelled"}}) == 1
    # create-pr kedua → ditolak (sudah ada PR)
    r2 = requests.post(f"{BASE}/special-orders/{od_id}/create-pr", json={}, headers=H["admin"])
    assert r2.status_code in (400, 409), r2.text


# /procure: item 'both' tanpa jalur → error, item lain tetap terealisasi
def test_procure_partial_errors(H):
    od_id, (k1, k2) = _od(H, [P_SUP, P_BOTH])
    r = requests.post(f"{BASE}/special-orders/{od_id}/procure", json={}, headers=H["admin"])
    print(r.status_code, r.text[:400])
    assert r.status_code == 200, r.text
    f = {n["key"]: n for n in _get(H, od_id)["items"]}
    assert f[k1]["status"] == "realized" and f[k2]["status"] == "blocked"
    assert DB.special_orders.find_one({"id": od_id}).get("procurement_error")
    # repeat idempoten
    requests.post(f"{BASE}/special-orders/{od_id}/procure", json={}, headers=H["admin"])
    assert DB.purchase_orders.count_documents({"special_order_id": od_id}) == 1


# OD tidak ada → 404; item tidak ada → 400
def test_not_found(H):
    assert requests.get(f"{BASE}/special-orders/sord_TEST_nope/fulfillment", headers=H["admin"]).status_code == 404
