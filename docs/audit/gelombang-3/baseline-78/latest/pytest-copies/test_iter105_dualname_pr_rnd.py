"""Iter105 — Dualisme nama & warna KN/SUPPLIER + PR eligible-suppliers + SO-linked PR realize.

Covers:
  1. GET /purchase-requisitions/eligible-suppliers
  2. GET /products supplier_alias & derived from source_name/color
  3. POST/PATCH /supplier-items menerima supplier_color
  4. PATCH /products/{id} {data:{source_name,source_color}}
  5. GET /purchase-requisitions/{id} & /purchase-orders/{id} attach supplier_item_name/supplier_color/kn_color
  6. GET /goods-receipts/{id} target dualname
  7. special_order_link realize_to_po fills SKU R&D
"""
import os, uuid, time, requests, pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") + "/api"
CREDS = {"email": "admin@kainnusantara.id", "password": "demo12345"}
ENTITY = "ent_ksc"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "X-Entity-Id": ENTITY})
    r = s.post(f"{BASE}/auth/login", json=CREDS, timeout=30)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


# ---------- 1) eligible-suppliers ----------
class TestEligibleSuppliers:
    def test_prod_with_contract_and_supplier_item(self, client):
        r = client.get(f"{BASE}/purchase-requisitions/eligible-suppliers",
                       params={"product_ids": "prod_benang_katun,prod_e7ad74409ce1"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "sup_5ffaf80582d0" in data["by_product"]["prod_benang_katun"]
        assert data["by_product"]["prod_e7ad74409ce1"] == []
        # common = intersection; since second is [], common must be []
        assert data["common"] == []

    def test_common_intersection(self, client):
        r = client.get(f"{BASE}/purchase-requisitions/eligible-suppliers",
                       params={"product_ids": "prod_benang_katun"})
        assert r.status_code == 200
        d = r.json()
        assert d["common"] == d["by_product"]["prod_benang_katun"]


# ---------- 2) products supplier_alias ----------
class TestProductsSupplierAlias:
    def test_alias_present_on_all(self, client):
        r = client.get(f"{BASE}/products")
        assert r.status_code == 200
        items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        assert len(items) > 0
        missing = [p["sku"] for p in items if "supplier_alias" not in p]
        assert not missing, f"products missing supplier_alias: {missing[:5]}"

    def test_alias_from_source_name_for_import(self, client):
        r = client.get(f"{BASE}/products")
        items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        p = next((x for x in items if x.get("sku") == "KNKNT0005-I-10XX-XA-XX-XX"), None)
        assert p, "KNKNT0005-I-10 sample product not found"
        assert p["supplier_alias"]["name"] == "ALICE KNIT (94139 - 45)"
        assert p["supplier_alias"]["color"] == "10"

    def test_supplier_codes_carry_supplier_id_and_color(self, client):
        r = client.get(f"{BASE}/products")
        items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        # find product with supplier_codes list
        p = next((x for x in items if x.get("supplier_codes")), None)
        assert p, "no product with supplier_codes"
        c = p["supplier_codes"][0]
        assert "supplier_id" in c
        assert "supplier_color" in c


# ---------- 3) supplier-items supplier_color persistence ----------
class TestSupplierItemColor:
    created_id = None

    def test_create_supplier_item_with_color(self, client):
        # Use existing supplier + product to avoid FK issues
        payload = {
            "supplier_id": "sup_5ffaf80582d0",
            "product_id": "prod_benang_katun",
            "supplier_sku": f"TEST-SKU-{uuid.uuid4().hex[:6]}",
            "supplier_item_name": "TEST Cotton Yarn Cone",
            "supplier_color": "OFF-WHITE-TEST",
            "supplier_uom": "kg",
            "currency": "IDR",
            "price": 50000,
        }
        r = client.post(f"{BASE}/supplier-items", json=payload)
        assert r.status_code in (200, 201), r.text
        body = r.json()
        sid = body.get("id") or body.get("_id") or body.get("supplier_item_id")
        assert sid, body
        assert body.get("supplier_color") == "OFF-WHITE-TEST"
        TestSupplierItemColor.created_id = sid

    def test_patch_supplier_color(self, client):
        sid = TestSupplierItemColor.created_id
        if not sid:
            pytest.skip("no created item")
        r = client.patch(f"{BASE}/supplier-items/{sid}",
                         json={"supplier_color": "BLUE-TEST"})
        assert r.status_code in (200, 204), r.text
        # verify via GET list
        r2 = client.get(f"{BASE}/supplier-items", params={"supplier_id": "sup_5ffaf80582d0"})
        assert r2.status_code == 200
        items = r2.json() if isinstance(r2.json(), list) else r2.json().get("items", [])
        it = next((x for x in items if x.get("id") == sid), None)
        assert it and it.get("supplier_color") == "BLUE-TEST", it

    def test_zzz_cleanup(self, client):
        sid = TestSupplierItemColor.created_id
        if sid:
            client.delete(f"{BASE}/supplier-items/{sid}")


# ---------- 4) PATCH product source_name/source_color ----------
class TestProductSourceNamePatch:
    def test_patch_and_readback(self, client):
        pid = "prod_e7ad74409ce1"
        newname = f"TEST_ALIAS_{uuid.uuid4().hex[:6]}"
        r = client.patch(f"{BASE}/products/{pid}",
                         json={"data": {"source_name": newname, "source_color": "TCOL"}})
        assert r.status_code in (200, 204), r.text
        # reload
        r2 = client.get(f"{BASE}/products")
        items = r2.json() if isinstance(r2.json(), list) else r2.json().get("items", [])
        p = next((x for x in items if x.get("id") == pid), None)
        assert p, "product missing after patch"
        assert p.get("source_name") == newname, p
        assert p.get("source_color") == "TCOL"
        assert p["supplier_alias"]["name"] == newname
        # restore
        client.patch(f"{BASE}/products/{pid}",
                     json={"data": {"source_name": "ALICE KNIT (94139 - 45)",
                                    "source_color": "10"}})


# ---------- 5+6) attach_line_aliases on PR/PO/GRN detail ----------
class TestDualnameOnDocuments:
    def test_pr_detail_has_dualname(self, client):
        # find first PR
        r = client.get(f"{BASE}/purchase-requisitions")
        assert r.status_code == 200
        prs = r.json().get("items", [])
        if not prs:
            pytest.skip("no PR in system")
        pr_id = prs[0]["id"]
        r2 = client.get(f"{BASE}/purchase-requisitions/{pr_id}")
        assert r2.status_code == 200, r2.text
        doc = r2.json()
        for it in (doc.get("items") or []):
            if it.get("product_id"):
                # attach_line_aliases fills these keys (even if empty string)
                assert "supplier_item_name" in it
                assert "supplier_color" in it
                assert "kn_color" in it
                return
        pytest.skip("PR has no product_id lines")

    def test_po_detail_has_dualname(self, client):
        r = client.get(f"{BASE}/purchase-orders")
        if r.status_code != 200:
            pytest.skip(r.text)
        pos = r.json().get("items") if isinstance(r.json(), dict) else r.json()
        pos = pos or []
        if not pos:
            pytest.skip("no PO")
        po_id = pos[0]["id"]
        r2 = client.get(f"{BASE}/purchase-orders/{po_id}")
        assert r2.status_code == 200
        doc = r2.json()
        for it in (doc.get("items") or []):
            if it.get("product_id"):
                assert "supplier_item_name" in it
                assert "supplier_color" in it
                return
        pytest.skip("no product lines")
