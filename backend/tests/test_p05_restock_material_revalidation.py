"""P05 — jalur restock (ACC-35), reservasi bahan MKO (ACC-32/33 sebagian), uji tambahan SKU existing (ACC-30).

Data acuan: scripts/seed_p05_kn.py (RIVERA RIB=makloon, ALICE KNIT=supplier, AUDIA KNIT=both,
BAMBU KNIT belum diatur, kebijakan unknown=block, KANDA/SO-00006 → PR → MKO bahan grey 300 kg dikunci).
Data uji berprefix TEST_ dan dibersihkan di akhir sesi.
"""
import os

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "http://localhost:8001"
ENT = "ent_kanda"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]


def _login(email, password="demo1234"):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


def _prod(tpl_prefix):
    t = DB.product_templates.find_one({"name": {"$regex": f"^{tpl_prefix}"}}, {"_id": 0, "id": 1})
    return DB.products.find_one({"template_id": t["id"], "stage": "finished"}, {"_id": 0, "id": 1, "sku": 1})


@pytest.fixture(scope="session")
def mgr():
    return _login("manager@kainnusantara.id")


@pytest.fixture(scope="session")
def admin():
    h = _login("admin@kainnusantara.id", "demo12345")
    return {**h, "X-Entity-Id": "ent_ksc"}


@pytest.fixture(scope="session")
def wh_id():
    return DB.makloon_orders.find_one({"entity_id": ENT}, {"_id": 0, "target_warehouse_id": 1})["target_warehouse_id"]


@pytest.fixture(scope="session", autouse=True)
def cleanup():
    yield
    DB.purchase_requisitions.delete_many({"reason": {"$regex": "^TEST_P05"}})
    ids = [s["id"] for s in DB.md_samples.find({"brief": {"$regex": "^TEST_P05"}}, {"_id": 0, "id": 1})]
    DB.md_samples.delete_many({"id": {"$in": ids}})


def _pr(h, wh, prod, mode, route_reason=""):
    body = {"items": [{"product_id": prod["id"], "quantity": 10, "unit": "kg", "fulfillment_mode": mode}],
            "warehouse_id": wh, "entity_id": ENT, "reason": "TEST_P05 jalur restock", "route_reason": route_reason}
    return requests.post(f"{BASE}/api/purchase-requisitions", json=body, headers=h, timeout=30)


class TestRestockRoute:
    def test_list_counts(self, mgr):
        r = requests.get(f"{BASE}/api/restock-sources", params={"status": "mapped"}, headers=mgr, timeout=30)
        assert r.status_code == 200, r.text
        modes = {i["name"].split(" (")[0]: i["restock_source"]["mode"] for i in r.json()["items"]}
        assert modes.get("RIVERA RIB") == "makloon" and modes.get("AUDIA KNIT") == "both"
        assert r.json()["unmapped"] > 0

    # L01 LN-013 (owner 2026-10-16) menggantikan ACC-35 lama: default bukan hard block —
    # menyimpang dari default wajib alasan, lalu diterima & tercatat sebagai deviation.
    def test_supplier_default_makloon_needs_reason(self, mgr, wh_id):
        r = _pr(mgr, wh_id, _prod("ALICE KNIT"), "makloon")
        assert r.status_code == 400 and "default" in r.text
        r = _pr(mgr, wh_id, _prod("ALICE KNIT"), "makloon", "TEST_P05 supplier kosong")
        assert r.status_code == 200, r.text
        assert r.json()["restock_route"]["routes"][0]["deviation"] is True

    def test_makloon_default_purchase_needs_reason(self, mgr, wh_id):
        r = _pr(mgr, wh_id, _prod("RIVERA RIB"), "purchase")
        assert r.status_code == 400 and "makloon" in r.text
        r = _pr(mgr, wh_id, _prod("RIVERA RIB"), "purchase", "TEST_P05 mitra penuh")
        assert r.status_code == 200, r.text

    def test_both_needs_reason(self, mgr, wh_id):
        p = _prod("AUDIA KNIT")
        assert _pr(mgr, wh_id, p, "purchase").status_code == 400
        r = _pr(mgr, wh_id, p, "purchase", "TEST_P05 makloon penuh")
        assert r.status_code == 200, r.text
        route = r.json()["restock_route"]["routes"][0]
        assert route["mode"] == "both" and route["reason"]

    def test_unmapped_blocked(self, mgr, wh_id):
        r = _pr(mgr, wh_id, _prod("BAMBU KNIT"), "purchase")
        assert r.status_code == 400 and "belum diatur" in r.text

    def test_sales_cannot_edit_mapping(self):
        h = _login("sales.kanda@kainnusantara.id")
        tpl = DB.product_templates.find_one({"name": {"$regex": "^BAMBU KNIT"}}, {"_id": 0, "id": 1})
        r = requests.put(f"{BASE}/api/product-templates/{tpl['id']}/restock-source", json={"mode": "supplier"},
                         headers=h, timeout=30)
        assert r.status_code == 403

    def test_md_can_edit_mapping_and_restore(self):
        # P05 — MD punya hak mengatur sumber restock; kembalikan ke semula (unset).
        h = _login("md@kainnusantara.id")
        tpl = DB.product_templates.find_one({"name": {"$regex": "^BAMBU KNIT"}}, {"_id": 0, "id": 1, "restock_source": 1})
        before = (tpl or {}).get("restock_source") or {}
        try:
            r = requests.put(f"{BASE}/api/product-templates/{tpl['id']}/restock-source",
                             json={"mode": "supplier", "note": "TEST_P05"}, headers=h, timeout=30)
            assert r.status_code == 200, r.text
            cur = DB.product_templates.find_one({"id": tpl["id"]}, {"_id": 0, "restock_source": 1})
            assert cur.get("restock_source", {}).get("mode") == "supplier"
        finally:
            # Kembalikan ke keadaan sebelum uji (hapus field agar kembali 'belum diatur').
            if before:
                DB.product_templates.update_one({"id": tpl["id"]}, {"$set": {"restock_source": before}})
            else:
                DB.product_templates.update_one({"id": tpl["id"]}, {"$unset": {"restock_source": ""}})

    def test_po_manual_rejects_makloon_only_item(self, mgr, wh_id):
        # P05 DEC-07 — PO manual untuk artikel makloon-only (RIVERA RIB) ditolak 409.
        prod = _prod("RIVERA RIB")
        supplier = DB.suppliers.find_one({"entity_id": "all",
                                          "name": {"$not": {"$regex": "Kanda|Cipta Sandang|Sukacita"}}},
                                         {"_id": 0, "id": 1})
        body = {
            "supplier_id": supplier["id"], "warehouse_id": wh_id, "entity_id": ENT,
            "items": [{"product_id": prod["id"], "quantity": 10, "unit": "kg",
                       "price": 1000, "expected_grade": "A"}],
            "notes": "TEST_P05 po-makloon-only",
        }
        r = requests.post(f"{BASE}/api/purchase-orders", json=body, headers=mgr, timeout=30)
        assert r.status_code == 409, f"{r.status_code} {r.text[:300]}"
        assert "makloon" in r.text.lower()


class TestMakloonMaterial:
    def test_mko_material_locked_once(self):
        mko = DB.makloon_orders.find_one({"entity_id": ENT, "pr_id": {"$nin": ["", None]}}, {"_id": 0, "id": 1})
        rows = list(DB.material_reservations.find({"ref_id": mko["id"]}, {"_id": 0}))
        assert len(rows) == 1 and rows[0]["status"] == "active"
        assert rows[0]["qty"] + rows[0]["shortage_qty"] == pytest.approx(rows[0]["required_qty"])

    def test_pending_shows_mko(self):
        h = _login("salesadmin.kanda@kainnusantara.id")
        r = requests.get(f"{BASE}/api/sales/keep-pending", headers=h, timeout=60)
        assert r.status_code == 200, r.text
        assert "makloon_orders" in r.text and "MKO-" in r.text


class TestExistingSkuRevalidation:
    def test_create_keeps_identity_and_no_duplicate(self, admin):
        prod = DB.products.find_one({"stage": "finished", "status": "active"}, {"_id": 0, "id": 1, "sku": 1})
        n_specs, n_products = DB.md_specs.count_documents({}), DB.products.count_documents({})
        body = {"product_id": prod["id"], "sample_types": ["handfeel"], "brief": "TEST_P05 uji ulang"}
        r = requests.post(f"{BASE}/api/rnd/samples", json=body, headers=admin, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["purpose"] == "revalidation" and d["product_id"] == prod["id"] and d["product_sku"] == prod["sku"]
        assert DB.md_specs.count_documents({}) == n_specs and DB.products.count_documents({}) == n_products
        again = requests.post(f"{BASE}/api/rnd/samples", json=body, headers=admin, timeout=30)
        assert again.status_code in (400, 422) and d["number"] in again.text
        lab = requests.post(f"{BASE}/api/rnd/samples", json={**body, "sample_types": ["labdip"]}, headers=admin, timeout=30)
        assert lab.status_code == 200, lab.text
        hist = requests.get(f"{BASE}/api/rnd/labdip-history", params={"product_id": prod["id"], "type_code": ""},
                            headers=admin, timeout=30)
        assert hist.status_code == 200 and hist.json()["summary"]["samples"] >= 2, (
            hist.status_code, hist.text[:200])

    def test_proofing_and_unknown_rejected(self, admin):
        prod = DB.products.find_one({"stage": "finished", "status": "active"}, {"_id": 0, "id": 1})
        r = requests.post(f"{BASE}/api/rnd/samples", json={"product_id": prod["id"], "sample_types": ["proofing"],
                                                           "brief": "TEST_P05"}, headers=admin, timeout=30)
        assert r.status_code in (400, 422) and "Proofing" in r.text
        r = requests.post(f"{BASE}/api/rnd/samples", json={"product_id": "prod_tidak_ada", "sample_types": ["labdip"],
                                                           "brief": "TEST_P05"}, headers=admin, timeout=30)
        assert r.status_code in (400, 422) and "tidak ditemukan" in r.text
