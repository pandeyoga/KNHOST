"""UAT 24 Okt — fase F4 (ANALISIS_TEMUAN_UAT_23OKT.md P15 gabung PR, P2 harga OD).

Jalankan: cd /app/backend && python -m pytest tests/test_uat24_f4.py -p no:randomly -n 0 -q
"""
import os
import sys
import uuid

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
T = uuid.uuid4().hex[:6]
ENT = "ent_ksc"


def _login(email, entity=ENT):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": entity}, r.json()["user"]


ADMIN, _ = _login("admin@kainnusantara.id")


def _site(name):
    return DB.warehouse_sites.find_one({"name": name}, {"_id": 0, "id": 1})["id"]


def _supplier():
    return DB.suppliers.find_one({"group_entity_id": {"$in": [None, ""]}, "status": {"$ne": "inactive"}},
                                 {"_id": 0, "id": 1, "name": 1})


def _products(n=2):
    rows = list(DB.products.find({"status": "active", "lifecycle": "produksi", "base_unit": {"$in": ["yard", "meter"]}},
                                 {"_id": 0, "id": 1, "sku": 1, "name": 1, "base_unit": 1}).limit(n))
    assert len(rows) == n
    return rows


def _pr(suffix, items, site="Jakarta", supplier="", entity=ENT):
    pid = f"pr_TEST_F4_{T}_{suffix}"
    DB.purchase_requisitions.insert_one({
        "id": pid, "number": f"UJ/PR-F4-{T}-{suffix}", "status": "approved", "entity_id": entity,
        "ship_to_site_id": _site(site), "warehouse_id": "", "preferred_supplier_id": supplier, "source": "manual",
        "needed_by_date": "2026-11-10", "created_at": "2026-10-24T00:00:00",
        "items": [{"line_no": i + 1, "product_id": p["id"], "sku": p["sku"], "product_name": p["name"], "quantity": q,
                   "unit": p["base_unit"], "est_price": 10000, "fulfillment_mode": "purchase", "realized_qty": 0,
                   "realizations": []} for i, (p, q) in enumerate(items)]})
    return pid


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    pos = [p["id"] for p in DB.purchase_orders.find({"pr_ids": {"$elemMatch": {"$regex": f"^pr_TEST_F4_{T}"}}}, {"id": 1})]
    DB.wms_tasks.delete_many({"po_id": {"$in": pos}})
    DB.purchase_orders.delete_many({"id": {"$in": pos}})
    DB.purchase_requisitions.delete_many({"id": {"$regex": f"^pr_TEST_F4_{T}"}})


# ─── P15 — gabung PR → 1 PO ─────────────────────────────────────────────────
def test_p15_dua_pr_supplier_lokasi_sama_jadi_satu_po_sku_kembar_satu_baris():
    sup = _supplier()
    a, b = _products(2)
    p1 = _pr("a", [(a, 100), (b, 50)], supplier=sup["id"])
    p2 = _pr("b", [(a, 40)], supplier=sup["id"])
    r = requests.post(f"{BASE}/purchase-requisitions/realize-many", headers=ADMIN,
                      json={"pr_refs": [{"pr_id": p1}, {"pr_id": p2}], "supplier_id": sup["id"]})
    assert r.status_code == 200, r.text
    po = DB.purchase_orders.find_one({"id": r.json()["po"]["id"]}, {"_id": 0})
    assert sorted(po["pr_ids"]) == sorted([p1, p2]) and po["merged_from_prs"] is True
    line_a = [it for it in po["items"] if it["product_id"] == a["id"]]
    assert len(line_a) == 1 and line_a[0]["quantity"] == 140                     # dilebur jadi satu baris
    assert sorted(x["qty"] for x in line_a[0]["pr_allocations"]) == [40, 100]
    for pid in (p1, p2):
        pr = DB.purchase_requisitions.find_one({"id": pid}, {"_id": 0})
        assert po["id"] in pr["po_ids"] and pr["status"] == "converted"
    linked = {r.get("doc_id") for r in po.get("refs") or []}
    assert {p1, p2} <= linked                                                     # Jejak Dokumen ke kedua PR


def test_p15_pr_beda_lokasi_atau_badan_usaha_ditolak():
    sup = _supplier()
    a = _products(1)[0]
    j = _pr("j", [(a, 10)], site="Jakarta", supplier=sup["id"])
    r_ = _pr("r", [(a, 10)], site="Rancamalang", supplier=sup["id"])
    r = requests.post(f"{BASE}/purchase-requisitions/realize-many", headers=ADMIN,
                      json={"pr_refs": [{"pr_id": j}, {"pr_id": r_}], "supplier_id": sup["id"]})
    assert r.status_code == 400 and "lokasi" in r.text
    k = _pr("k", [(a, 10)], site="Soreang", supplier=sup["id"], entity="ent_kanda")
    r2 = requests.post(f"{BASE}/purchase-requisitions/realize-many", headers=ADMIN,
                       json={"pr_refs": [{"pr_id": j}, {"pr_id": k}], "supplier_id": sup["id"]})
    assert r2.status_code in (400, 403)
    # tidak ada yang terkunci / terealisasi setelah penolakan
    assert not DB.purchase_requisitions.find_one({"id": j}, {"_id": 0}).get("saga_lock")


def test_p15_saran_gabung_menampilkan_kelompok_supplier_lokasi_sama():
    sup = _supplier()
    a, b = _products(2)
    s1 = _pr("s1", [(a, 5)], site="Rancamalang", supplier=sup["id"])
    s2 = _pr("s2", [(b, 7)], site="Rancamalang", supplier=sup["id"])
    r = requests.get(f"{BASE}/purchase-requisitions/merge-suggestions", headers=ADMIN)
    assert r.status_code == 200, r.text
    grp = [g for g in r.json()["groups"] if g["supplier_id"] == sup["id"] and {s1, s2} <= {p["pr_id"] for p in g["prs"]}]
    assert grp and grp[0]["pr_count"] >= 2 and grp[0]["site_name"]


# ─── P2 — harga Pesanan Khusus (SO-12) + nego lewat harga khusus SO ─────────
from _shared_loop import run  # noqa: E402 — loop tempat klien Motor terikat

SALES, SALES_U = _login("sales@kainnusantara.id")
SADM, _ = _login("salesadmin@kainnusantara.id")
MGR, _ = _login("manager@kainnusantara.id")
P2_ODS: list = []
P2_PRODS: list = []
P2_CUST = f"cust_TEST_F4_{T}"
COST_KEYS = {"cost_price", "margin_pct", "supplier_name", "supplier_id", "contract_number", "comparator_unit_price"}


def _parent():
    return DB.products.find_one({"status": "active", "grade": "A", "base_unit": "yard", "price": {"$gt": 15000},
                                 "special_order_id": {"$in": [None, ""]}, "template_id": {"$nin": [None, ""]},
                                 "lifecycle": {"$in": [None, "", "produksi"]}},
                                {"_id": 0, "id": 1, "sku": 1, "price": 1, "template_id": 1})


def _result_product(tag):
    """SKU hasil R&D item OD (tiruan) — klon produk aktif ber-kunci varian unik (indeks kombinasi)."""
    tpl = [t["id"] for t in DB.product_templates.find({"restock_source.mode": "supplier"}, {"id": 1})]
    src = DB.products.find_one({"status": "active", "base_unit": "yard", "template_id": {"$in": tpl}}, {"_id": 0})
    pid = f"prod_TEST_F4_{T}_{tag}"
    doc = {k: v for k, v in src.items() if k not in ("variant_options", "variant_attrs", "exclusive_customer_id",
                                                     "special_order_id", "grade")}
    doc.update({"id": pid, "sku": f"TF4-{T}-{tag}".upper(), "name": f"TEST F4 {tag} {T}", "lifecycle": "produksi",
                "status": "active", "price": 1000, "variant_key": f"TEST-F4-{T}-{tag}"})
    DB.products.insert_one(doc)
    P2_PRODS.append(pid)
    return doc


@pytest.fixture(scope="module", autouse=True)
def _p2_cleanup():
    base = DB.customers.find_one({"id": "cust_toko_kain"}, {"_id": 0})
    DB.customers.insert_one({**base, "id": P2_CUST, "name": f"TEST F4 Pelanggan {T}", "code": f"TF4{T}".upper(),
                             "assigned_sales_id": "user_sales_01", "credit_limit": 0})
    yield
    sos = [s["id"] for s in DB.sales_orders.find({"source_special_order_id": {"$in": P2_ODS}}, {"id": 1})]
    pos = [p["id"] for p in DB.purchase_orders.find({"special_order_id": {"$in": P2_ODS}}, {"id": 1})]
    DB.wms_tasks.delete_many({"$or": [{"po_id": {"$in": pos}}, {"order_id": {"$in": sos}}]})
    DB.purchase_orders.delete_many({"id": {"$in": pos}})
    DB.purchase_requisitions.delete_many({"source_ref_id": {"$in": P2_ODS}})
    DB.price_approvals.delete_many({"so_id": {"$in": sos}})
    DB.sales_orders.delete_many({"id": {"$in": sos}})
    DB.md_samples.delete_many({"special_order_id": {"$in": P2_ODS}})
    DB.md_specs.delete_many({"special_order_id": {"$in": P2_ODS}})
    DB.special_orders.delete_many({"id": {"$in": P2_ODS}})
    DB.products.delete_many({"id": {"$in": P2_PRODS}})
    DB.customers.delete_one({"id": P2_CUST})


def _od2(items, cost_by_line):
    """items: daftar dict item OD (API). Sample R&D per item diputus: produk hasil + harga kontrak."""
    sup = _supplier()
    r = requests.post(f"{BASE}/special-orders", headers=ADMIN, json={
        "customer_id": P2_CUST, "title": f"TEST_F4_P2_{T}", "entity_id": ENT, "expected_delivery": "2026-12-31",
        "items": items, "submit_for_approval": True})
    assert r.status_code in (200, 201), r.text
    od_id = r.json()["id"]
    P2_ODS.append(od_id)
    for _ in range(3):
        if DB.special_orders.find_one({"id": od_id}, {"status": 1})["status"] == "confirmed":
            break
        requests.post(f"{BASE}/special-orders/{od_id}/approve", json={"notes": "TEST"}, headers=ADMIN)
    od = DB.special_orders.find_one({"id": od_id}, {"_id": 0})
    assert od["status"] == "confirmed", od["status"]
    for it, (prod, cost) in zip(od["items"], cost_by_line):
        DB.md_samples.update_one({"id": it["rnd_sample_id"]}, {"$set": {
            "status": "decided", "decision": {"product_id": prod["id"], "product_sku": prod["sku"], "supplier_id": sup["id"],
                                              "supplier_name": sup["name"], "price": float(cost),
                                              "contract_number": f"KTR-{T}"}}})
    assert requests.post(f"{BASE}/special-orders/{od_id}/customer-decision", json={"decision": "acc"},
                         headers=ADMIN).status_code == 200
    return od_id, [i["id"] for i in od["items"]]


def _keys(obj, out=None):
    out = set() if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(k)
            _keys(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _keys(v, out)
    return out


def _pending(resp):
    return next(p for p in resp.json()["pending_approvals"] if p["type"] == "special_price" and p["status"] == "pending")


def test_p2_harga_induk_grade_a_pic_kunci_admin_sales_so_lahir_tanpa_po_dan_biaya_tersembunyi():
    from services import customer_price_service as cps
    par = _parent()
    r1, r2 = _result_product("r1"), _result_product("r2")
    od_id, (i1, i2) = _od2([
        {"source_type": "parent_product", "source_product_id": par["id"], "description": f"TEST F4 induk {T}",
         "request_types": ["labdip"], "quantity": 100, "unit": "yard"},
        {"source_type": "customer_reference", "description": f"TEST F4 tanpa induk {T}",
         "request_types": ["labdip"], "quantity": 50, "unit": "yard"}], [(r1, 10000), (r2, 12000)])
    grade_a = run(cps.resolve_many(ENT, P2_CUST, [par["id"]], {par["id"]: par}))[par["id"]]["price"]
    pv = requests.get(f"{BASE}/special-orders/{od_id}/pricing", headers=SADM).json()
    a, b = pv["items"]
    assert a["basis"] == "parent_grade_a" and a["final_unit_price"] == grade_a and a["ref_sku"] == par["sku"]
    assert b["basis"] == "cost_margin" and b["needs_pic"] and b["final_unit_price"] == 15600.0
    # Harga item tanpa induk = keputusan PIC Special Order; sales tidak bisa mengisi / mengunci.
    assert requests.post(f"{BASE}/special-orders/{od_id}/pic-prices", headers=SALES,
                         json={"item_prices": {i2: 20000}}).status_code == 403
    r = requests.post(f"{BASE}/special-orders/{od_id}/pic-prices", headers=SADM, json={"item_prices": {i2: 20000}})
    assert r.status_code == 200, r.text
    assert requests.post(f"{BASE}/special-orders/{od_id}/lock-price", headers=SALES, json={}).status_code == 403
    r = requests.post(f"{BASE}/special-orders/{od_id}/lock-price", headers=SADM, json={})
    assert r.status_code == 200, r.text
    od = DB.special_orders.find_one({"id": od_id}, {"_id": 0})
    lines = {ln["item_id"]: ln for ln in od["pricing"]["items"]}
    assert lines[i1]["final_unit_price"] == grade_a and lines[i2]["basis"] == "pic" and lines[i2]["final_unit_price"] == 20000
    assert od.get("linked_sales_order_id"), od.get("shipping_error")          # SO lahir saat kunci
    assert not DB.purchase_requisitions.find_one({"source_ref_id": od_id})    # belum ada PR/PO
    assert not DB.purchase_orders.find_one({"special_order_id": od_id})
    # Sales melihat harga final, tanpa biaya/margin/supplier/kontrak (API detail OD, pricing, pemenuhan, SO).
    for url in (f"/special-orders/{od_id}", f"/special-orders/{od_id}/pricing", f"/special-orders/{od_id}/fulfillment"):
        body = requests.get(f"{BASE}{url}", headers=SALES)
        assert body.status_code == 200, body.text
        assert not (_keys(body.json()) & COST_KEYS), (url, _keys(body.json()) & COST_KEYS)
    pv_s = requests.get(f"{BASE}/special-orders/{od_id}/pricing", headers=SALES).json()
    assert [ln["final_unit_price"] for ln in pv_s["items"]] == [grade_a, 20000]
    so = requests.get(f"{BASE}/sales-orders/{od['linked_sales_order_id']}", headers=SALES).json()
    assert all("cost_price" not in it for it in so["items"])
    assert requests.get(f"{BASE}/special-orders/{od_id}/pricing", headers=SADM).json()["items"][0]["cost_price"] == 10000


def test_p2_nego_lantai_kontrak_gerbang_pengadaan_acc_mengubah_od_dan_sku_lalu_po_gabungan():
    r1, r2 = _result_product("n1"), _result_product("n2")
    od_id, (i1, i2) = _od2([
        {"source_type": "customer_reference", "description": f"TEST F4 nego A {T}", "request_types": ["labdip"],
         "quantity": 100, "unit": "yard"},
        {"source_type": "customer_reference", "description": f"TEST F4 nego B {T}", "request_types": ["labdip"],
         "quantity": 40, "unit": "yard"}], [(r1, 10000), (r2, 12000)])
    assert requests.post(f"{BASE}/special-orders/{od_id}/lock-price", headers=SADM, json={"margin_pct": 30}).status_code == 200
    so_id = DB.special_orders.find_one({"id": od_id}, {"linked_sales_order_id": 1})["linked_sales_order_id"]
    nego = {"special_order_item_id": i2, "product_id": r2["id"], "reason": "Pelanggan minta harga"}
    r = requests.post(f"{BASE}/sales-orders/{so_id}/request-special-price", headers=SALES, json={**nego, "requested_price": 11000})
    assert r.status_code == 400 and "lantai" in r.text and "12.000" not in r.text   # di bawah kontrak; angka biaya tak bocor
    r = requests.post(f"{BASE}/sales-orders/{so_id}/request-special-price", headers=SALES, json={**nego, "requested_price": 14000})
    assert r.status_code == 200, r.text
    entry = _pending(r)
    assert entry["special_order_item_id"] == i2
    # Selama nego belum diputus, pengadaan ditahan.
    r = requests.post(f"{BASE}/special-orders/{od_id}/procure", headers=MGR, json={})
    assert r.status_code == 400 and "Nego" in r.text, r.text
    r = requests.post(f"{BASE}/sales-orders/{so_id}/approvals/{entry['id']}/decide", headers=MGR,
                      json={"decision": "approve", "notes": "ok"})
    assert r.status_code == 200, r.text
    so = DB.sales_orders.find_one({"id": so_id}, {"_id": 0})
    by_item = {it["special_order_item_id"]: it for it in so["items"]}
    assert by_item[i2]["price"] == 14000 and by_item[i1]["price"] == 13000
    od = DB.special_orders.find_one({"id": od_id}, {"_id": 0})
    ln2 = next(x for x in od["pricing"]["items"] if x["item_id"] == i2)
    assert ln2["final_unit_price"] == 14000 and ln2["negotiated"]["previous_price_per_unit"] == 15600
    assert od["pricing"]["total"] == 100 * 13000 + 40 * 14000 == od["total_amount"]
    assert DB.products.find_one({"id": r2["id"]}, {"price": 1})["price"] == 14000
    # Nego beres → pengadaan jalan; dua item supplier sama → SATU PO berharga kontrak.
    r = requests.post(f"{BASE}/special-orders/{od_id}/procure", headers=MGR, json={})
    assert r.status_code == 200, r.text
    pos = list(DB.purchase_orders.find({"special_order_id": od_id, "status": {"$ne": "cancelled"}}, {"_id": 0}))
    assert len(pos) == 1, [p.get("po_number") for p in pos]
    po = pos[0]
    assert sorted(po["special_order_item_keys"]) == sorted([i1, i2])
    assert sorted((it["product_id"], it["price"]) for it in po["items"]) == sorted([(r1["id"], 10000), (r2["id"], 12000)])
    od = DB.special_orders.find_one({"id": od_id}, {"_id": 0})
    assert {d["id"] for k in (i1, i2) for d in od["fulfillment"][k]["docs"]} == {po["id"]}


def test_p2_nego_ditolak_lanjut_harga_normal_dan_dua_item_sku_sama_tertarget_benar():
    r = _result_product("s1")
    od_id, (i1, i2) = _od2([
        {"source_type": "customer_reference", "description": f"TEST F4 kembar 1 {T}", "request_types": ["labdip"],
         "quantity": 30, "unit": "yard"},
        {"source_type": "customer_reference", "description": f"TEST F4 kembar 2 {T}", "request_types": ["labdip"],
         "quantity": 70, "unit": "yard"}], [(r, 10000), (r, 10000)])
    assert requests.post(f"{BASE}/special-orders/{od_id}/lock-price", headers=SADM, json={"margin_pct": 30}).status_code == 200
    so_id = DB.special_orders.find_one({"id": od_id}, {"linked_sales_order_id": 1})["linked_sales_order_id"]
    # Item KEDUA (SKU sama dengan item pertama) yang dinego.
    rr = requests.post(f"{BASE}/sales-orders/{so_id}/request-special-price", headers=SALES, json={
        "special_order_item_id": i2, "product_id": r["id"], "requested_price": 12000, "reason": "Volume"})
    assert rr.status_code == 200, rr.text
    entry = _pending(rr)
    rr = requests.post(f"{BASE}/sales-orders/{so_id}/approvals/{entry['id']}/decide", headers=MGR,
                       json={"decision": "reject", "notes": "terlalu rendah"})
    assert rr.status_code == 200, rr.text
    assert "ditolak" in requests.post(f"{BASE}/special-orders/{od_id}/procure", headers=MGR, json={}).text
    rr = requests.post(f"{BASE}/sales-orders/{so_id}/approvals/{entry['id']}/continue-normal-price", headers=SALES, json={})
    assert rr.status_code == 200, rr.text
    od = DB.special_orders.find_one({"id": od_id}, {"_id": 0})
    assert [x["final_unit_price"] for x in od["pricing"]["items"]] == [13000, 13000]    # harga OD tetap
    # Nego ulang item kedua → ACC → hanya baris item kedua yang berubah.
    rr = requests.post(f"{BASE}/sales-orders/{so_id}/request-special-price", headers=SALES, json={
        "special_order_item_id": i2, "product_id": r["id"], "requested_price": 12500, "reason": "Volume 2"})
    assert rr.status_code == 200, rr.text
    entry = _pending(rr)
    assert requests.post(f"{BASE}/sales-orders/{so_id}/approvals/{entry['id']}/decide", headers=MGR,
                         json={"decision": "approve"}).status_code == 200
    so = DB.sales_orders.find_one({"id": so_id}, {"_id": 0})
    assert {it["special_order_item_id"]: it["price"] for it in so["items"]} == {i1: 13000, i2: 12500}
    od = DB.special_orders.find_one({"id": od_id}, {"_id": 0})
    assert {x["item_id"]: x["final_unit_price"] for x in od["pricing"]["items"]} == {i1: 13000, i2: 12500}
