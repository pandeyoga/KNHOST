"""FE-01 (review 2026-10-20) — Pesanan Khusus multi-produk utuh sampai SO.

Alur lewat API resmi: buat OD multi-item → approve → ACC pelanggan → pratinjau/kunci harga per item →
konversi SO → siapkan pengiriman. Hanya HASIL R&D per item (sample `decided` + harga kontrak) yang
disiapkan langsung sebagai fixture — sama seperti reproduksi reviewer.

Jalankan di container backend:  cd /app/backend && python -m pytest tests/test_fe01_od_multi_item_so.py -p no:randomly -n 0 -q
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT, CUST = "ent_ksc", "cust_toko_kain"
TAG = uuid.uuid4().hex[:6]
SUP = DB.suppliers.find_one({}, {"_id": 0, "id": 1, "name": 1})
PRODUCT_FIELDS = ("price", "harga_pokok", "exclusive_customer_id", "exclusive_customer_name", "special_order_id",
                  "special_order_number", "catalog_scope", "status")


def _stocked(unit: str, n: int):
    rows = list(DB.inventory_rolls.aggregate([
        {"$match": {"owner_entity_id": ENT, "status": "available", "unit": unit, "grade": "A", "stage": "finished"}},
        {"$group": {"_id": "$product_id", "q": {"$sum": "$length_remaining"}}},
        {"$match": {"q": {"$gte": 400 if unit == "yard" else 100}}}, {"$sort": {"q": -1}}, {"$limit": n}]))
    return [DB.products.find_one({"id": r["_id"]}, {"_id": 0, "id": 1, "sku": 1, "base_unit": 1}) for r in rows]


A, B = _stocked("yard", 2)
K = _stocked("kg", 1)[0]
SNAP = {p["id"]: DB.products.find_one({"id": p["id"]}, {"_id": 0, **{f: 1 for f in PRODUCT_FIELDS}}) for p in (A, B, K)}
OD_IDS: list = []


def _login(email, pw="demo12345"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


@pytest.fixture(scope="module")
def H():
    return {"admin": _login("admin@kainnusantara.id", "demo12345")}


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    adm = _login("admin@kainnusantara.id", "demo12345")
    for so in DB.sales_orders.find({"source_special_order_id": {"$in": OD_IDS}, "status": {"$ne": "cancelled"}}, {"_id": 0, "id": 1}):
        requests.post(f"{BASE}/sales-orders/{so['id']}/cancel", json={"reason": "TEST FE-01 bersih-bersih"}, headers=adm)
    DB.md_samples.delete_many({"special_order_id": {"$in": OD_IDS}})
    spec_ids = [i.get("spec_id") for od in DB.special_orders.find({"id": {"$in": OD_IDS}}, {"_id": 0, "items.spec_id": 1})
                for i in od.get("items") or [] if i.get("spec_id")]
    DB.md_specs.delete_many({"$or": [{"special_order_id": {"$in": OD_IDS}}, {"id": {"$in": spec_ids}}]})
    DB.special_orders.delete_many({"id": {"$in": OD_IDS}})
    for pid, snap in SNAP.items():
        unset = {f: "" for f in PRODUCT_FIELDS if f not in snap}
        DB.products.update_one({"id": pid}, {"$set": snap, **({"$unset": unset} if unset else {})})


def _od(H, lines):
    """lines: [(product, qty, unit, cost)]. Sample R&D per item yang lahir saat approve diputus dengan
    produk hasil + harga kontrak `cost` (cost 0 = diputus tanpa harga kontrak → item belum siap)."""
    items = [{"source_type": "parent_product", "source_product_id": p["id"], "description": f"TEST FE01 {i + 1} {TAG}",
              "request_types": ["labdip"], "quantity": q, "unit": u} for i, (p, q, u, _c) in enumerate(lines)]
    r = requests.post(f"{BASE}/special-orders", json={"customer_id": CUST, "title": f"TEST_FE01_{TAG}", "entity_id": ENT,
                                                     "expected_delivery": "2026-12-31", "items": items,
                                                     "submit_for_approval": True}, headers=H["admin"])
    assert r.status_code in (200, 201), r.text
    od_id = r.json()["id"]
    OD_IDS.append(od_id)
    for _ in range(3):   # persetujuan bertingkat (bila dikonfigurasi)
        if DB.special_orders.find_one({"id": od_id}, {"status": 1})["status"] == "confirmed":
            break
        requests.post(f"{BASE}/special-orders/{od_id}/approve", json={"notes": "TEST"}, headers=H["admin"])
    od = DB.special_orders.find_one({"id": od_id}, {"_id": 0})
    assert od["status"] == "confirmed", od["status"]
    for it, (p, _q, _u, cost) in zip(od["items"], lines):
        assert it.get("rnd_sample_id"), it      # sample R&D per item lahir otomatis saat approve
        DB.md_samples.update_one({"id": it["rnd_sample_id"]}, {"$set": {
            "status": "decided", "decision": {"product_id": p["id"], "product_sku": p["sku"], "supplier_id": SUP["id"],
                                              "supplier_name": SUP["name"], "price": float(cost)}}})
    r = requests.post(f"{BASE}/special-orders/{od_id}/customer-decision", json={"decision": "acc"}, headers=H["admin"])
    assert r.status_code == 200, r.text
    return od_id, [i["id"] for i in od["items"]]


def _pricing(H, od_id, **params):
    r = requests.get(f"{BASE}/special-orders/{od_id}/pricing", params=params, headers=H["admin"])
    assert r.status_code == 200, r.text
    return r.json()


def _lock(H, od_id, **body):
    return requests.post(f"{BASE}/special-orders/{od_id}/lock-price", json={"margin_pct": 30, "auto_po": False, **body},
                         headers=H["admin"])


def _convert(H, od_id):
    return requests.post(f"{BASE}/special-orders/{od_id}/convert-to-so", json={}, headers=H["admin"])


def _sos(od_id):
    return list(DB.sales_orders.find({"source_special_order_id": od_id, "status": {"$ne": "cancelled"}}, {"_id": 0}))


def _lines(so):
    return sorted(so["items"], key=lambda i: (i.get("special_order_line_no") or 0, i["quantity"]))


# ─── Titik selesai reviewer: A100 yard + B200 yard → dua rincian SO ─────────────
def test_a100_b200_menjadi_dua_rincian_so(H):
    od_id, item_ids = _od(H, [(A, 100, "yard", 10), (B, 200, "yard", 30)])
    pv = _pricing(H, od_id, margin_pct=30)
    assert pv.get("mode") == "items" and pv["ready"] is True, pv
    assert [(i["item_id"], i["product_id"], i["quantity"], i["unit"]) for i in pv["items"]] == \
        [(item_ids[0], A["id"], 100, "yard"), (item_ids[1], B["id"], 200, "yard")]
    assert [i["total"] for i in pv["items"]] == [1300.0, 7800.0]
    assert pv["total"] == 9100.0                       # reviewer: 9.100 sebelum pajak (bukan 3.900)
    r = _lock(H, od_id)
    assert r.status_code == 200, r.text
    locked = DB.special_orders.find_one({"id": od_id}, {"_id": 0, "pricing": 1, "total_amount": 1})
    assert locked["pricing"]["locked"] and len(locked["pricing"]["items"]) == 2 and locked["total_amount"] == 9100.0
    r = _convert(H, od_id)
    assert r.status_code == 200, r.text
    sos = _sos(od_id)
    assert len(sos) == 1
    ln = _lines(sos[0])
    assert [(i["product_id"], i["quantity"], i["unit"], i["price"]) for i in ln] == \
        [(A["id"], 100, "yard", 13.0), (B["id"], 200, "yard", 39.0)]
    assert [i.get("special_order_item_id") for i in ln] == item_ids
    assert round(sum(i["quantity"] * i["price"] for i in ln), 2) == 9100.0
    # Dampak alokasi & pengiriman: kedua produk direservasi, tugas Surat Jalan per baris
    so = sos[0]
    alloc_products = {a.get("product_id") for a in so.get("allocations") or []}
    assert {A["id"], B["id"]} <= alloc_products, so.get("allocations")
    r = requests.post(f"{BASE}/special-orders/{od_id}/prepare-shipment", json={}, headers=H["admin"])
    assert r.status_code == 200, r.text
    tasks = list(DB.wms_tasks.find({"order_id": so["id"], "flow_type": "outbound"}, {"_id": 0, "product_id": 1, "items": 1}))
    task_products = {t.get("product_id") for t in tasks} | {i.get("product_id") for t in tasks for i in t.get("items") or []}
    assert {A["id"], B["id"]} <= task_products, tasks


def test_harga_satu_item_berubah(H):
    od_id, item_ids = _od(H, [(A, 100, "yard", 10), (B, 200, "yard", 30)])
    pv = _pricing(H, od_id, margin_pct=30, item_margins=f'{{"{item_ids[1]}": 50}}')
    assert [i["margin_pct"] for i in pv["items"]] == [30.0, 50.0]
    assert pv["total"] == 1300.0 + 9000.0
    assert _lock(H, od_id, item_margins={item_ids[1]: 50}).status_code == 200
    assert _convert(H, od_id).status_code == 200
    assert [i["price"] for i in _lines(_sos(od_id)[0])] == [13.0, 45.0]


def test_item_belum_siap_tidak_bisa_dikunci_dan_tidak_hilang(H):
    od_id, _ = _od(H, [(A, 100, "yard", 10), (B, 200, "yard", 0)])
    pv = _pricing(H, od_id, margin_pct=30)
    assert pv["ready"] is False and pv["items"][0]["ready"] and not pv["items"][1]["ready"]
    assert any("Item 2" in b for b in pv["blockers"]), pv["blockers"]
    r = _lock(H, od_id)
    assert r.status_code == 400 and "Item 2" in r.text, r.text
    assert not (DB.special_orders.find_one({"id": od_id}, {"pricing": 1}).get("pricing") or {}).get("locked")
    assert _convert(H, od_id).status_code == 400
    assert _sos(od_id) == []


def test_satuan_berbeda_dan_produk_kg(H):
    od_id, _ = _od(H, [(A, 100, "meter", 10), (K, 50, "kg", 20)])
    pv = _pricing(H, od_id, margin_pct=30)
    assert pv["ready"] is True, pv["blockers"]
    m, k = pv["items"]
    assert m["unit"] == "meter" and m["base_unit"] == "yard" and m["price_per_unit"] != m["final_unit_price"]
    assert k["unit"] == "kg" and k["price_per_unit"] == 26.0 and k["total"] == 1300.0
    assert _lock(H, od_id).status_code == 200
    assert _convert(H, od_id).status_code == 200
    ln = _lines(_sos(od_id)[0])
    assert [(i["unit"], i["price"]) for i in ln] == [("meter", m["price_per_unit"]), ("kg", 26.0)]
    assert round(sum(i["quantity"] * i["price"] for i in ln), 2) == pv["total"]


def test_dua_item_sku_sama_kebutuhan_berbeda(H):
    od_id, item_ids = _od(H, [(A, 50, "yard", 10), (A, 70, "yard", 10)])
    assert _lock(H, od_id, item_margins={item_ids[1]: 40}).status_code == 200
    assert _convert(H, od_id).status_code == 200
    ln = _lines(_sos(od_id)[0])
    assert [(i["product_id"], i["quantity"], i["price"], i.get("special_order_item_id")) for i in ln] == \
        [(A["id"], 50, 13.0, item_ids[0]), (A["id"], 70, 14.0, item_ids[1])]


def test_gagal_di_tengah_konversi_lalu_retry_tanpa_so_ganda(H):
    od_id, _ = _od(H, [(A, 100, "yard", 10), (B, 200, "yard", 30)])
    assert _lock(H, od_id).status_code == 200
    DB.products.update_one({"id": B["id"]}, {"$set": {"status": "inactive"}})   # gangguan: produk item 2 nonaktif
    try:
        r = _convert(H, od_id)
        assert r.status_code >= 400, r.text
        assert _sos(od_id) == []
    finally:
        DB.products.update_one({"id": B["id"]}, {"$set": {"status": SNAP[B["id"]].get("status") or "active"}})
    assert _convert(H, od_id).status_code == 200
    assert _convert(H, od_id).status_code == 400            # sudah dikonversi
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda _: _convert(H, od_id), range(4)))
    assert len(_sos(od_id)) == 1
    assert len(_lines(_sos(od_id)[0])) == 2


def test_od_satu_item_tetap_jalur_lama(H):
    od_id, item_ids = _od(H, [(A, 100, "yard", 10)])
    pv = _pricing(H, od_id, margin_pct=30)
    assert pv.get("mode") != "items" and pv["total"] == 1300.0
    assert _lock(H, od_id).status_code == 200
    assert _convert(H, od_id).status_code == 200
    ln = _lines(_sos(od_id)[0])
    assert [(i["product_id"], i["quantity"], i["price"]) for i in ln] == [(A["id"], 100, 13.0)]
