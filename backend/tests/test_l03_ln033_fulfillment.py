"""L03 LN-033 — rute pemenuhan per item Pesanan Khusus (supplier → PR/PO, makloon → PR/MKO)."""
import os
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT, CUST = "ent_ksc", "cust_toko_kain"
SUP = DB.suppliers.find_one({"entity_id": "all"}, {"_id": 0, "id": 1}, sort=[("name", 1)])["id"]
TPL = {m: DB.product_templates.find_one({"restock_source.mode": m}, {"_id": 0, "id": 1})["id"] for m in ("supplier", "makloon", "both")}
TAG = uuid.uuid4().hex[:6]
P_SUP = DB.products.find_one({"template_id": TPL["supplier"]}, {"_id": 0, "id": 1, "sku": 1})       # artikel default supplier
P_MKL = DB.products.find_one({"template_id": TPL["makloon"]}, {"_id": 0, "id": 1, "sku": 1})       # artikel default makloon
P_GREY = DB.products.find_one({"stage": "grey"}, {"_id": 0, "id": 1})
MKL = DB.makloons.find_one({}, {"_id": 0, "id": 1, "name": 1})
RECIPE = f"rcp_TEST_{TAG}"
OD_IDS: list = []


def _login(email, pw="demo1234"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


@pytest.fixture(scope="module")
def H():
    return {"admin": _login("admin@kainnusantara.id", "demo12345"), "manager": _login("manager@kainnusantara.id"),
            "sales": _login("sales@kainnusantara.id")}


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    ods = list(DB.special_orders.find({"id": {"$in": OD_IDS}}, {"_id": 0, "id": 1}))
    ids = [o["id"] for o in ods]
    prs = [p["id"] for p in DB.purchase_requisitions.find({"source_ref_id": {"$in": ids}}, {"id": 1})]
    DB.purchase_orders.delete_many({"special_order_id": {"$in": ids}})
    mkos = [m["id"] for m in DB.makloon_orders.find({"special_order_id": {"$in": ids}}, {"id": 1})]
    DB.makloon_orders.delete_many({"id": {"$in": mkos}})
    DB.material_reservations.delete_many({"$or": [{"ref_id": {"$in": mkos}}, {"pr_id": {"$in": prs}}]})
    DB.wms_tasks.delete_many({"$or": [{"po_id": {"$exists": True}, "special_order_id": {"$in": ids}}, {"pr_id": {"$in": prs}}]})
    DB.purchase_requisitions.delete_many({"id": {"$in": prs}})
    DB.md_samples.delete_many({"special_order_id": {"$in": ids}})
    DB.design_requests.delete_many({"special_order_id": {"$in": ids}})
    DB.special_orders.delete_many({"id": {"$in": ids}})
    DB.process_recipes.delete_many({"id": RECIPE})


def _recipe():
    DB.process_recipes.update_one({"id": RECIPE}, {"$set": {
        "id": RECIPE, "name": f"TEST rajut {TAG}", "status": "active", "entity_id": ENT, "process_type": "rajut",
        "output_product_id": P_MKL["id"], "input_product_id": P_GREY["id"], "default_makloon_id": MKL["id"],
        "yield_factor": 1.0, "waste_pct": 0}}, upsert=True)


def _od(H, products, lock=True):
    items = [{"source_type": "parent_product", "source_product_id": p["id"], "description": f"TEST LN033 {i} {TAG}",
              "request_types": ["labdip"], "quantity": 10 + i, "unit": "kg"} for i, p in enumerate(products)]
    r = requests.post(f"{BASE}/special-orders", json={"customer_id": CUST, "title": f"TEST_LN033_{TAG}", "entity_id": ENT,
                                                     "expected_delivery": "2026-12-31", "items": items,
                                                     "submit_for_approval": True}, headers=H["admin"])
    assert r.status_code in (200, 201), r.text
    od_id = r.json()["id"]
    OD_IDS.append(od_id)
    assert requests.post(f"{BASE}/special-orders/{od_id}/approve", json={"notes": "TEST"}, headers=H["admin"]).status_code == 200
    od = DB.special_orders.find_one({"id": od_id}, {"_id": 0})
    for it, p in zip(od["items"], products):
        DB.md_samples.insert_one({"id": f"smp_TEST_{uuid.uuid4().hex[:8]}", "number": f"TS-{TAG}", "status": "decided",
                                  "special_order_id": od_id, "special_order_item_id": it["id"], "created_at": "2026-10-18T00:00:00",
                                  "decision": {"product_id": p["id"], "product_sku": p["sku"], "supplier_id": SUP,
                                               "supplier_name": "PT Benang Sejahtera Abadi", "price": 50000.0}})
    if lock:
        DB.special_orders.update_one({"id": od_id}, {"$set": {
            "status": "confirmed", "customer_decision": "acc", "price_locked": True,
            "pricing": {"locked": True, "product_id": products[0]["id"], "supplier_id": SUP, "supplier_name": "PT Benang Sejahtera Abadi",
                        "cost_price": 50000.0, "final_unit_price": 65000.0, "quantity": 10, "unit": "kg"}}})
    return od_id, [i["id"] for i in od["items"]]


def _ful(H, od_id, who="admin"):
    r = requests.get(f"{BASE}/special-orders/{od_id}/fulfillment", headers=H[who])
    assert r.status_code == 200, r.text
    return {n["key"]: n for n in r.json()["items"]}


def _route(H, od_id, key, route, reason="", who="admin"):
    return requests.post(f"{BASE}/special-orders/{od_id}/fulfillment/{key}/route", json={"route": route, "reason": reason}, headers=H[who])


def _realize(H, od_id, key, who="admin"):
    return requests.post(f"{BASE}/special-orders/{od_id}/fulfillment/{key}/realize", json={}, headers=H[who])


def test_t03_t04_t05_mixed_two_items_supplier_and_makloon(H):
    _recipe()
    od_id, (k1, k2) = _od(H, [P_SUP, P_MKL])
    f = _ful(H, od_id)
    assert f[k1]["default_route"] == "purchase" and f[k2]["default_route"] == "makloon"
    # T03 — menyimpang dari default wajib alasan; jejak audit tersimpan.
    assert _route(H, od_id, k1, "makloon").status_code == 400
    r = _route(H, od_id, k1, "makloon", "uji kapasitas mitra")
    assert r.status_code == 200 and r.json()["state"]["deviation"] is True
    assert _route(H, od_id, k1, "purchase").status_code == 200
    hist = DB.special_orders.find_one({"id": od_id})["fulfillment"][k1]["history"]
    assert [h["after"] for h in hist] == ["makloon", "purchase"] and hist[0]["reason"] == "uji kapasitas mitra"
    # T04 — supplier: PR purchase → PO produk/qty/supplier/entitas/harga benar; tanpa MKO.
    r1 = _realize(H, od_id, k1)
    assert r1.status_code == 200, r1.text
    doc1 = r1.json()["result"]["doc"]
    assert doc1["type"] == "po"
    po = DB.purchase_orders.find_one({"id": doc1["id"]})
    line = next(i for i in po["items"] if i["product_id"] == P_SUP["id"])
    assert po["supplier_id"] == SUP and po["entity_id"] == ENT and float(line["quantity"]) == 10 and float(line["price"]) == 50000
    assert po["special_order_item_key"] == k1
    pr1 = DB.purchase_requisitions.find_one({"id": doc1["pr_id"]})
    assert pr1["items"][0]["fulfillment_mode"] == "purchase" and pr1["source_item_key"] == k1
    # T05 — makloon: PR makloon → MKO produk hasil benar; tanpa PO barang jadi.
    r2 = _realize(H, od_id, k2)
    assert r2.status_code == 200, r2.text
    doc2 = r2.json()["result"]["doc"]
    assert doc2["type"] == "mko"
    mko = DB.makloon_orders.find_one({"id": doc2["id"]})
    assert mko["steps"][-1]["output_product_id"] == P_MKL["id"] and mko["special_order_item_key"] == k2
    assert DB.purchase_orders.count_documents({"special_order_id": od_id, "items.product_id": P_MKL["id"]}) == 0
    pr2 = DB.purchase_requisitions.find_one({"id": doc2["pr_id"]})
    assert pr2["items"][0]["fulfillment_mode"] == "makloon"
    od = DB.special_orders.find_one({"id": od_id})
    assert od["linked_po_id"] == doc1["id"] and od["linked_mko_id"] == doc2["id"] and od["status"] == "in_production"
    # T06 — bahan kurang: tercatat menunggu bahan, cadangan tidak melebihi stok bebas.
    res = DB.material_reservations.find_one({"ref_id": doc2["id"]})
    assert res and res["qty"] + res["shortage_qty"] == pytest.approx(res["required_qty"]) and res["qty"] >= 0
    f = _ful(H, od_id)
    assert f[k2]["status"] == ("waiting_material" if res["shortage_qty"] > 0 else "realized")
    assert f[k1]["status"] == "realized"
    # T07 — klik ulang: dokumen ditemukan kembali, tidak dobel.
    again = _realize(H, od_id, k1)
    assert again.status_code == 200 and again.json()["result"].get("skipped")
    assert DB.purchase_orders.count_documents({"special_order_id": od_id}) == 1
    assert DB.purchase_requisitions.count_documents({"source_ref_id": od_id, "status": {"$ne": "cancelled"}}) == 2
    # T08 — ganti jalur saat dokumen aktif → 409.
    assert _route(H, od_id, k1, "makloon", "ganti").status_code == 409
    # Auto-procure (retry) idempoten — tidak melahirkan dokumen baru.
    assert requests.post(f"{BASE}/special-orders/{od_id}/procure", json={}, headers=H["admin"]).status_code == 200
    assert DB.purchase_orders.count_documents({"special_order_id": od_id}) == 1
    assert DB.makloon_orders.count_documents({"special_order_id": od_id}) == 1


def test_t07_concurrent_realize_one_document(H):
    od_id, (k1,) = _od(H, [P_SUP])
    with ThreadPoolExecutor(3) as ex:
        res = list(ex.map(lambda w: _realize(H, od_id, k1, w), ["admin", "manager", "admin"]))
    assert any(x.status_code == 200 for x in res), [x.text for x in res]
    assert all(x.status_code in (200, 409) for x in res), [x.text for x in res]
    assert DB.purchase_orders.count_documents({"special_order_id": od_id}) == 1
    assert DB.purchase_requisitions.count_documents({"source_ref_id": od_id, "status": {"$ne": "cancelled"}}) == 1


def test_needs_data_then_retry_reuses_pr(H):
    DB.process_recipes.delete_many({"id": RECIPE})
    # resep lain (mis. resep demo rcp_TEST_* untuk OD demo) disingkirkan sementara agar uji needs_data deterministik
    others = list(DB.process_recipes.find({"output_product_id": P_MKL["id"]}, {"_id": 0}))
    DB.process_recipes.delete_many({"output_product_id": P_MKL["id"]})
    try:
        _needs_data_body(H)
    finally:
        for o in others:
            DB.process_recipes.update_one({"id": o["id"]}, {"$set": o}, upsert=True)


def _needs_data_body(H):
    od_id, (k1,) = _od(H, [P_MKL])
    r = _realize(H, od_id, k1)
    assert r.status_code == 200 and r.json()["result"]["status"] == "needs_data"
    f = _ful(H, od_id)[k1]
    assert f["status"] == "needs_data" and "Resep" in f["error"] and not f["active_docs"]
    assert DB.makloon_orders.count_documents({"special_order_id": od_id}) == 0
    _recipe()
    r = _realize(H, od_id, k1)
    assert r.status_code == 200 and r.json()["result"]["doc"]["type"] == "mko", r.text
    assert DB.purchase_requisitions.count_documents({"source_ref_id": od_id}) == 1


def test_t08_route_change_after_cancel_keeps_history(H):
    od_id, (k1,) = _od(H, [P_SUP])
    doc = _realize(H, od_id, k1).json()["result"]["doc"]
    DB.purchase_orders.update_one({"id": doc["id"]}, {"$set": {"status": "cancelled"}})   # pembatalan lewat modul PO
    _recipe()
    r = _route(H, od_id, k1, "makloon", "supplier batal kirim")
    assert r.status_code == 200, r.text
    st = DB.special_orders.find_one({"id": od_id})["fulfillment"][k1]
    assert st["docs"] == [] and {d["id"] for d in st["history_docs"]} >= {doc["id"], doc["pr_id"]}
    assert DB.purchase_requisitions.find_one({"id": doc["pr_id"]})["source_item_key"].endswith("#retired")
    r = _realize(H, od_id, k1)   # artikel supplier tanpa resep makloon → data master kurang, PR baru ber-mode makloon
    assert r.status_code == 200 and r.json()["result"]["status"] == "needs_data", r.text
    st = DB.special_orders.find_one({"id": od_id})["fulfillment"][k1]
    assert st["pr_id"] != doc["pr_id"]
    assert DB.purchase_requisitions.find_one({"id": st["pr_id"]})["items"][0]["fulfillment_mode"] == "makloon"
    assert DB.purchase_orders.count_documents({"special_order_id": od_id, "status": {"$ne": "cancelled"}}) == 0


def test_t08_cancel_endpoint_cancels_active_po_keeps_history(H):
    od_id, (k1,) = _od(H, [P_SUP])
    doc = _realize(H, od_id, k1).json()["result"]["doc"]
    url = f"{BASE}/special-orders/{od_id}/fulfillment/{k1}/cancel"
    assert requests.post(url, json={"reason": "uji batal oleh sales"}, headers=H["sales"]).status_code == 403
    assert requests.post(url, json={"reason": "x"}, headers=H["admin"]).status_code == 422
    r = requests.post(url, json={"reason": "supplier tidak sanggup"}, headers=H["admin"])
    assert r.status_code == 200, r.text
    assert DB.purchase_orders.find_one({"id": doc["id"]})["status"] == "cancelled"
    st = DB.special_orders.find_one({"id": od_id})["fulfillment"][k1]
    assert st["history"][-1]["action"] == "cancel_docs"
    assert requests.post(url, json={"reason": "ulang batal lagi"}, headers=H["admin"]).status_code == 400
    _recipe()
    assert _route(H, od_id, k1, "makloon", "ganti ke makloon").status_code == 200



def test_t01_release_guard_no_fallback(H):
    prod = DB.products.find_one({"template_id": TPL["supplier"], "id": {"$ne": P_SUP["id"]}}, {"_id": 0, "id": 1, "sku": 1, "lifecycle": 1, "spec_id": 1})
    DB.products.update_one({"id": prod["id"]}, {"$set": {"lifecycle": "labdip", "spec_id": ""}})
    try:
        od_id, (k1,) = _od(H, [prod])
        r = _realize(H, od_id, k1)
        assert r.status_code == 400 and "dirilis" in r.json()["detail"], r.text
        assert DB.products.find_one({"id": prod["id"]})["lifecycle"] == "labdip"
        assert DB.purchase_requisitions.count_documents({"source_ref_id": od_id}) == 0
        assert DB.special_orders.find_one({"id": od_id})["fulfillment"][k1]["error"]
    finally:
        DB.products.update_one({"id": prod["id"]}, {"$set": {"lifecycle": prod.get("lifecycle") or "produksi", "spec_id": prod.get("spec_id") or ""}})


def test_t09_permissions_backend(H):
    od_id, (k1,) = _od(H, [P_SUP])
    assert _ful(H, od_id, "sales")[k1]["product_id"] == P_SUP["id"]
    assert _route(H, od_id, k1, "makloon", "x", who="sales").status_code == 403
    assert _realize(H, od_id, k1, who="sales").status_code == 403
    assert _route(H, od_id, k1, "bogus").status_code == 400
    assert requests.post(f"{BASE}/special-orders/{od_id}/fulfillment/nope/realize", json={}, headers=H["admin"]).status_code == 400


def test_blocked_without_price_lock(H):
    od_id, (k1,) = _od(H, [P_SUP], lock=False)
    f = _ful(H, od_id)[k1]
    assert f["status"] == "blocked" and any("Harga final" in b for b in f["blockers"])
    assert _realize(H, od_id, k1).status_code == 400


def test_t10_migration_dry_run_reports():
    out = subprocess.run(["python", "../scripts/migrate_l03_ln033_fulfillment.py"], capture_output=True, text=True,
                         cwd=os.path.dirname(os.path.dirname(__file__)), timeout=120)
    assert out.returncode == 0, out.stderr
    assert '"mode": "dry_run"' in out.stdout and '"counts"' in out.stdout
