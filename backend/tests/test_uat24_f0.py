"""UAT 24 Okt — fase F0 (docs/uat/2026-10-21/ANALISIS_TEMUAN_UAT_23OKT.md): bug pasti yang terbukti di uji alur nyata.

P11.5 jejak MD tidak terhapus 4-point · P16.2 PDF GRN baru · P14 sales hanya pelanggan/retur miliknya (+ walk-in) ·
P9 gudang nonaktif tidak bisa dipakai & gudang bawaan reorder · antrean "Pelanggan tanpa sales".

Jalankan: cd /app/backend && python -m pytest tests/test_uat24_f0.py -p no:randomly -n 0 -q
"""
import os
import sys
import uuid

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run as run_sync  # noqa: E402 — loop tempat klien Motor terikat
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
T = uuid.uuid4().hex[:6]


def _login(email, entity="ent_ksc"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": entity}, r.json()["user"]


ADMIN, _ = _login("admin@kainnusantara.id")
SALES2, SALES2_USER = _login("sales2@kainnusantara.id")
SALESADMIN, _ = _login("salesadmin@kainnusantara.id")


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    DB.inventory_rolls.delete_many({"id": {"$regex": f"^roll_TEST_F0_{T}"}})
    DB.goods_receipts.delete_many({"id": {"$regex": f"^grn_TEST_F0_{T}"}})
    DB.customers.delete_many({"id": {"$regex": f"^cust_TEST_F0_{T}"}})


def test_p11_5_simpan_4point_tidak_menghapus_jejak_md():
    """MD Quality lalu QC 4-point: jejak `md_quality_at/by` tetap ada di roll (dulu objek `inspection` ditimpa utuh)."""
    tmpl = DB.inventory_rolls.find_one({"owner_entity_id": "ent_ksc", "status": "available"}, {"_id": 0}) or {}
    rid = f"roll_TEST_F0_{T}_md"
    DB.inventory_rolls.insert_one({**tmpl, "id": rid, "roll_no": f"TEST-F0-{T}", "status": "quarantine", "defects": [],
                                   "inspection": {"md_quality_at": "2026-10-24T01:00:00+00:00", "md_quality_by": "MDQ Uji",
                                                  "md_quality_doc_number": "TEST/INS-1", "color_result": "sesuai",
                                                  "handfeel_result": "sesuai"}})
    from services import qc_inspection_service as qis

    async def run():
        roll = DB.inventory_rolls.find_one({"id": rid}, {"_id": 0})
        return await qis.inspect_roll(roll, [], None, None, "bersih", {"name": "QC Uji", "id": "u_qc"},
                                      quality_from_roll=True, grade_input="A")
    run_sync(run())
    insp = DB.inventory_rolls.find_one({"id": rid}, {"_id": 0, "inspection": 1})["inspection"]
    assert insp["md_quality_at"] == "2026-10-24T01:00:00+00:00" and insp["md_quality_by"] == "MDQ Uji"
    assert insp["md_quality_doc_number"] == "TEST/INS-1"
    assert insp.get("inspected_at") and insp.get("inspected_by") == "QC Uji" and insp.get("grade") == "A"
    assert insp["color_result"] == "sesuai"


def test_p16_2_pdf_grn_baru_bisa_dicetak_dan_bukti_terima_po_tetap_ada():
    po = DB.purchase_orders.find_one({"entity_id": "ent_ksc"}, {"_id": 0, "id": 1}) or DB.purchase_orders.find_one({}, {"_id": 0, "id": 1})
    gid = f"grn_TEST_F0_{T}"
    DB.goods_receipts.insert_one({
        "id": gid, "entity_id": "ent_ksc", "number": f"TEST/GRN-{T}", "status": "closed", "partner_name": "PT Uji",
        "warehouse_id": "wh_jakarta", "dn": {"number": "SJ-UJI-1", "po_refs": ["PO-UJI"]}, "created_at": "2026-10-24T01:00:00+00:00",
        "lines": [{"line_no": 1, "declared": {"qty": 100, "unit": "yard", "rolls": 4},
                   "target": {"sku": "SKU-UJI", "product_name": "Kain Uji", "unit": "yard", "po_number": "PO-UJI"},
                   "counted": {"qty": 98.5, "rolls": 4}, "recon": {"diff_qty": -1.5}}], "discrepancies": []})
    r = requests.get(f"{BASE}/pdf/render/goods_receipt/{gid}", params={"format": "pdf"}, headers=ADMIN)
    assert r.status_code == 200, r.text[:300]
    assert r.headers.get("content-type", "").startswith("application/pdf")
    if po:
        r2 = requests.get(f"{BASE}/pdf/render/po_receipt/{po['id']}", params={"format": "pdf"}, headers=ADMIN)
        assert r2.status_code == 200, r2.text[:300]


def _owned(c, uid):
    return c.get("assigned_sales_id") == uid or c.get("shared_walk_in") or any(
        m.get("sales_id") == uid for m in c.get("sales_team") or [])


def test_p14_pemilih_pelanggan_sales_hanya_miliknya_plus_walk_in():
    uid = SALES2_USER["id"]
    walk = f"cust_TEST_F0_{T}_walk"
    other = f"cust_TEST_F0_{T}_lain"
    DB.customers.insert_many([
        {"id": walk, "name": f"Walk-in Uji {T}", "entity_id": "ent_ksc", "status": "active", "shared_walk_in": True, "addresses": []},
        {"id": other, "name": f"Pelanggan Rekan {T}", "entity_id": "ent_ksc", "status": "active", "assigned_sales_id": "user_lain", "addresses": []}])
    for params in ({"for_order": "true", "with_credit": "false"}, {}):
        r = requests.get(f"{BASE}/customers", params=params, headers=SALES2)
        assert r.status_code == 200, r.text
        rows = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        ids = {c["id"] for c in rows}
        assert other not in ids, f"pelanggan rekan bocor ({params})"
        assert walk in ids, f"walk-in PT tidak tampil ({params})"
        full = {c["id"]: c for c in DB.customers.find({"id": {"$in": list(ids)}}, {"_id": 0})}
        assert all(_owned(full[i], uid) for i in ids), [full[i]["name"] for i in ids if not _owned(full[i], uid)]
    # pemilih pelanggan POS (dasbor) memakai cakupan yang sama
    d = requests.get(f"{BASE}/dashboard", headers=SALES2).json()
    dids = {c["id"] for c in d.get("customers") or []}
    assert other not in dids and walk in dids


def test_p14_retur_sales_hanya_atas_pesanan_miliknya():
    from services import sales_ownership
    owned = {o["id"] for o in DB.sales_orders.find(sales_ownership.owner_clause(SALES2_USER), {"_id": 0, "id": 1})}
    r = requests.get(f"{BASE}/sales-returns", headers=SALES2)
    assert r.status_code == 200, r.text
    items = r.json().get("items", [])
    bad = [x.get("number") for x in items if x.get("order_id") not in owned and x.get("created_by_id") != SALES2_USER["id"]]
    assert not bad, f"retur pesanan sales lain terlihat: {bad}"
    foreign = DB.sales_returns.find_one({"entity_id": "ent_ksc", "order_id": {"$nin": list(owned)},
                                         "created_by_id": {"$ne": SALES2_USER["id"]}}, {"_id": 0, "id": 1})
    if foreign:
        assert requests.get(f"{BASE}/sales-returns/{foreign['id']}", headers=SALES2).status_code == 403
    c = requests.get(f"{BASE}/sales-returns/status-counts", headers=SALES2).json()
    assert c.get("all", 0) == len(items)


def test_p9_gudang_nonaktif_tidak_ditawarkan_dan_ditolak_po():
    rows = requests.get(f"{BASE}/warehouses", headers=ADMIN).json()
    assert rows and all(w.get("active", True) is not False for w in rows), [w.get("code") for w in rows if w.get("active") is False]
    allw = requests.get(f"{BASE}/warehouses", params={"scope": "all"}, headers=ADMIN).json()
    assert any(w.get("active") is False for w in allw), "layar master tetap melihat gudang nonaktif"
    bdg = DB.warehouses.find_one({"active": False}, {"_id": 0, "id": 1})
    sup = DB.suppliers.find_one({}, {"_id": 0, "id": 1, "name": 1})
    prod = DB.products.find_one({"status": "active", "lifecycle": "produksi"}, {"_id": 0, "id": 1, "base_unit": 1})
    r = requests.post(f"{BASE}/purchase-orders", headers=ADMIN, json={
        "supplier_id": sup["id"], "supplier_name": sup["name"], "warehouse_id": bdg["id"], "entity_id": "ent_ksc",
        "items": [{"product_id": prod["id"], "quantity": 10, "unit": prod.get("base_unit") or "yard", "price": 1000}],
        "tax_mode": "ppn", "expected_delivery_date": "2026-12-01", "notes": f"TEST F0 {T}"})
    assert r.status_code == 400 and "NONAKTIF" in r.text, r.text[:300]


def test_p9_gudang_bawaan_reorder_aktif_dan_boleh_dipakai():
    from services import restock_service

    async def run():
        return await restock_service._default_warehouse({"entity_id": "ent_ksc", "allocations": []})
    wid = run_sync(run())
    wh = DB.warehouses.find_one({"id": wid}, {"_id": 0})
    assert wh and wh.get("active") is not False
    assert wh.get("sharing_mode") != "dedicated" or "ent_ksc" in (wh.get("entity_ids") or [])


def test_meja_admin_sales_punya_antrean_pelanggan_tanpa_sales():
    nid = f"cust_TEST_F0_{T}_tanpa"
    DB.customers.insert_one({"id": nid, "name": f"Tanpa Sales {T}", "code": f"T{T}", "entity_id": "ent_ksc", "status": "active",
                             "assigned_sales_id": "", "sales_team": [], "addresses": [], "created_at": "2026-10-24T00:00:00+00:00"})
    r = requests.get(f"{BASE}/sales-admin/desk", headers=SALESADMIN)
    assert r.status_code == 200, r.text[:300]
    q = next((q for q in r.json().get("queues", []) if q["id"] == "pelanggan_tanpa_sales"), None)
    assert q is not None
    assert any(row["ref_id"] == nid for row in q["rows"])
