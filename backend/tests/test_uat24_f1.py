"""UAT 24 Okt — fase F1 (ANALISIS_TEMUAN_UAT_23OKT.md P8/P9): LOKASI (site) sebagai tujuan kirim & konteks jualan.

Lokasi uji sementara (1 gudang transit + 1 gudang simpan, bersama) dibuat & dibersihkan di modul ini.

Jalankan: cd /app/backend && python -m pytest tests/test_uat24_f1.py -p no:randomly -n 0 -q
"""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
T = uuid.uuid4().hex[:6]
SITE = f"site_TEST_F1_{T}"
WH_T = f"wh_TEST_F1_{T}_tr"
WH_S = f"wh_TEST_F1_{T}_st"


def _login(email, entity="ent_ksc"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": entity}, r.json()["user"]


ADMIN, _ = _login("admin@kainnusantara.id")
SALES2, SALES2_USER = _login("sales2@kainnusantara.id")


@pytest.fixture(scope="module", autouse=True)
def _site():
    DB.warehouse_sites.insert_one({"id": SITE, "name": f"Uji Lokasi {T}", "city": "Bandung"})
    DB.warehouses.insert_many([
        {"id": WH_T, "code": f"UJ-TR-{T}", "name": f"Uji Transit {T}", "site_id": SITE, "roles": ["transit", "central_inbound"],
         "sharing_mode": "shared", "entity_ids": [], "active": True, "city": "Bandung"},
        {"id": WH_S, "code": f"UJ-ST-{T}", "name": f"Uji Simpan {T}", "site_id": SITE, "roles": ["storage"],
         "sharing_mode": "shared", "entity_ids": [], "active": True, "city": "Bandung"}])
    yield
    pos = [p["id"] for p in DB.purchase_orders.find({"notes": {"$regex": f"TEST F1 {T}"}}, {"id": 1})]
    DB.wms_tasks.delete_many({"po_id": {"$in": pos}})
    DB.goods_receipts.delete_many({"source.po_ids": {"$in": pos}})
    DB.purchase_orders.delete_many({"id": {"$in": pos}})
    DB.purchase_requisitions.delete_many({"reason": {"$regex": f"TEST F1 {T}"}})
    DB.inventory_rolls.delete_many({"id": {"$regex": f"^roll_TEST_F1_{T}"}})
    for so in DB.sales_orders.find({"notes": f"TEST F1 {T}"}, {"id": 1}):   # batal lewat API → cadangan roll dilepas
        requests.post(f"{BASE}/sales-orders/{so['id']}/cancel", headers=ADMIN, json={"reason": "uji F1 selesai"})
    DB.warehouses.delete_many({"id": {"$in": [WH_T, WH_S]}})
    DB.warehouse_sites.delete_one({"id": SITE})


def _po_payload(**dest):
    sup = DB.suppliers.find_one({"group_entity_id": {"$in": [None, ""]}}, {"_id": 0, "id": 1, "name": 1})
    prod = DB.products.find_one({"status": "active", "lifecycle": "produksi"}, {"_id": 0, "id": 1, "base_unit": 1})
    return {"supplier_id": sup["id"], "supplier_name": sup["name"], "entity_id": "ent_ksc", "tax_mode": "ppn",
            "items": [{"product_id": prod["id"], "quantity": 10, "unit": prod.get("base_unit") or "yard", "price": 1000,
                       "expected_grade": "A"}],
            "expected_delivery_date": "2026-12-01", "notes": f"TEST F1 {T}", **dest}


def test_lokasi_kirim_menurunkan_gudang_penerimaan():
    r = requests.get(f"{BASE}/warehouse-sites/{SITE}/receiving", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["warehouse"]["id"] == WH_T


def test_po_ke_lokasi_masuk_lewat_gudang_transit():
    r = requests.post(f"{BASE}/purchase-orders", headers=ADMIN, json=_po_payload(ship_to_site_id=SITE))
    assert r.status_code == 200, r.text
    po = DB.purchase_orders.find_one({"id": r.json()["id"]}, {"_id": 0})
    assert po["warehouse_id"] == WH_T and po["ship_to_site_id"] == SITE and po["ship_to_site_name"].startswith("Uji Lokasi")


def test_po_klien_lama_ke_gudang_simpan_dialihkan_ke_transit_lokasinya():
    r = requests.post(f"{BASE}/purchase-orders", headers=ADMIN, json=_po_payload(warehouse_id=WH_S))
    assert r.status_code == 200, r.text
    po = DB.purchase_orders.find_one({"id": r.json()["id"]}, {"_id": 0})
    assert po["warehouse_id"] == WH_T and po["ship_to_site_id"] == SITE


def test_pr_ke_lokasi_menyimpan_lokasi_dan_gudang_penerimaan():
    prod = DB.products.find_one({"status": "active", "lifecycle": "produksi"}, {"_id": 0, "id": 1, "base_unit": 1})
    r = requests.post(f"{BASE}/purchase-requisitions", headers=ADMIN, json={
        "items": [{"product_id": prod["id"], "quantity": 5, "unit": prod.get("base_unit") or "yard", "est_price": 1000}],
        "ship_to_site_id": SITE, "entity_id": "ent_ksc", "reason": f"TEST F1 {T}"})
    assert r.status_code == 200, r.text
    pr = DB.purchase_requisitions.find_one({"id": r.json()["id"]}, {"_id": 0})
    assert pr["warehouse_id"] == WH_T and pr["ship_to_site_id"] == SITE


def test_grn_dari_po_selalu_di_gudang_penerimaan_po():
    po = requests.post(f"{BASE}/purchase-orders", headers=ADMIN, json=_po_payload(ship_to_site_id=SITE)).json()
    if DB.purchase_orders.find_one({"id": po["id"]}, {"_id": 0, "status": 1})["status"] in ("pending_approval", "waiting_approval", "draft"):
        assert requests.post(f"{BASE}/purchase-orders/{po['id']}/approve", headers=ADMIN, json={}).status_code == 200
    r = requests.post(f"{BASE}/goods-receipts", headers=ADMIN, json={
        "partner_type": "supplier", "partner_id": po["supplier_id"], "warehouse_id": WH_S, "po_ids": [po["id"]]})
    assert r.status_code == 200, r.text
    g = r.json().get("grn") or r.json()
    assert g["warehouse_id"] == WH_T


def test_stok_per_lokasi_memisahkan_milik_pt_dan_pt_lain():
    tmpl = DB.inventory_rolls.find_one({"owner_entity_id": "ent_ksc", "status": "available"}, {"_id": 0})
    pid = tmpl["product_id"]
    DB.inventory_rolls.insert_many([
        {**tmpl, "id": f"roll_TEST_F1_{T}_a", "roll_no": f"TF1-{T}-A", "warehouse_id": WH_S, "owner_entity_id": "ent_ksc",
         "status": "available", "length_remaining": 30.0},
        {**tmpl, "id": f"roll_TEST_F1_{T}_b", "roll_no": f"TF1-{T}-B", "warehouse_id": WH_S, "owner_entity_id": "ent_kanda",
         "status": "available", "length_remaining": 20.0}])
    r = requests.get(f"{BASE}/pos/site-stock", headers=ADMIN, params={"site_id": SITE, "entity_id": "ent_ksc", "product_ids": pid})
    assert r.status_code == 200, r.text
    st = r.json()["stock"][pid]
    assert st["own_qty"] == 30.0 and st["group_qty"] == 20.0 and st["rolls"] == 1


def test_so_menyimpan_lokasi_pemenuhan():
    cust = DB.customers.find_one({"entity_id": "ent_ksc", "$or": [{"assigned_sales_id": SALES2_USER["id"]}, {"shared_walk_in": True}],
                                  "addresses.0": {"$exists": True}}, {"_id": 0})
    if not cust:
        pytest.skip("DB uji tanpa pelanggan milik sales2 beralamat")
    roll = DB.inventory_rolls.find_one({"owner_entity_id": "ent_ksc", "status": "available", "length_remaining": {"$gte": 5}}, {"_id": 0})
    unit = (DB.products.find_one({"id": roll["product_id"]}, {"_id": 0, "base_unit": 1}) or {}).get("base_unit") or roll.get("unit")
    r = requests.post(f"{BASE}/sales-orders", headers=SALES2, json={
        "customer_id": cust["id"], "shipping_address_id": cust["addresses"][0]["id"], "entity_id": "ent_ksc", "allow_backorder": True,
        "confirm_mixed_lot": True, "fulfillment_site_id": SITE, "items": [{"product_id": roll["product_id"], "quantity": 1, "unit": unit}]})
    assert r.status_code == 200, r.text
    so = DB.sales_orders.find_one({"id": r.json()["id"]}, {"_id": 0, "fulfillment_site_id": 1})
    DB.sales_orders.update_one({"id": r.json()["id"]}, {"$set": {"notes": f"TEST F1 {T}"}})
    assert so["fulfillment_site_id"] == SITE
