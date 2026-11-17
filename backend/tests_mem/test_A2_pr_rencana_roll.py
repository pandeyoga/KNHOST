"""A2 (pelatihan keuangan 18 Nov) — rencana roll baris PR ikut ke PO hasil konversi/realisasi.

Uji jalan alur Pengadaan sampai Bayar: Gudang mengetik "75 roll" di PR, PR dikonversi ke PO, tetapi baris PO tanpa
`qty_rolls` → tugas Barang Masuk tanpa "rencana 75 roll" dan form penerimaan tidak menawarkan "Buat 75 roll". PO manual
sudah membawa rencana roll (FASE U); jalur PR → PO kini sama. Realisasi sebagian = sebanding sisa qty.
"""
import uuid

import pytest

from core_utils import now_iso

KSC = "ent_ksc"


def uid(awalan: str) -> str:
    return f"{awalan}_a2_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
async def dunia(db):
    wh, sup, pid = uid("wh"), uid("sup"), uid("grey")
    await db.warehouses.insert_one({"id": wh, "code": f"A2-{wh[-5:]}", "name": "Gudang Uji A2", "roles": ["storage"],
                                    "sharing_mode": "shared", "entity_ids": [], "active": True, "is_active": True,
                                    "zones": [], "created_at": now_iso()})
    await db.suppliers.insert_one({"id": sup, "name": "Pemasok Grey Uji A2", "code": f"S{sup[-5:]}", "status": "active",
                                   "is_active": True, "entity_id": KSC, "created_at": now_iso()})
    await db.products.insert_one({"id": pid, "sku": f"A2-GREY-{pid[-4:]}", "name": "Grey uji A2", "stage": "grey",
                                  "fabric_type": "woven", "base_unit": "yard", "status": "active",
                                  "lifecycle": "produksi", "grade": "A", "created_at": now_iso()})
    return {"wh": wh, "sup": sup, "pid": pid}


async def _pr_disetujui(klien, kepala, d, qty_rolls):
    r = await klien.post("/api/purchase-requisitions", headers=kepala, json={
        "items": [{"product_id": d["pid"], "quantity": 1000, "unit": "yard", "est_price": 10_000, "qty_rolls": qty_rolls}],
        "warehouse_id": d["wh"], "entity_id": KSC, "reason": "uji A2", "route_reason": "uji A2", "submit_now": True})
    assert r.status_code == 200, r.text
    pr = r.json()
    if pr["status"] != "approved":
        r = await klien.post(f"/api/purchase-requisitions/{pr['id']}/approve", headers=kepala, json={})
        assert r.status_code == 200, r.text
    return pr


async def test_A2_U1_konversi_membawa_rencana_roll(klien, kepala_admin, dunia, db):
    pr = await _pr_disetujui(klien, kepala_admin, dunia, 10)
    r = await klien.post(f"/api/purchase-requisitions/{pr['id']}/convert-to-po", headers=kepala_admin,
                         json={"supplier_id": dunia["sup"], "warehouse_id": dunia["wh"]})
    assert r.status_code == 200, r.text
    po = await db.purchase_orders.find_one({"id": r.json()["po"]["id"]}, {"_id": 0})
    assert po["items"][0]["qty_rolls"] == 10
    assert po["items"][0]["received_rolls"] is None


async def test_A2_U2_realisasi_sebagian_sebanding(klien, kepala_admin, dunia, db):
    pr = await _pr_disetujui(klien, kepala_admin, dunia, 10)
    await db.purchase_requisitions.update_one({"id": pr["id"]}, {"$set": {"items.0.realized_qty": 400}})
    r = await klien.post(f"/api/purchase-requisitions/{pr['id']}/realize-po", headers=kepala_admin,
                         json={"supplier_id": dunia["sup"], "warehouse_id": dunia["wh"]})
    assert r.status_code == 200, r.text
    po = await db.purchase_orders.find_one({"id": r.json()["po"]["id"]}, {"_id": 0})
    assert po["items"][0]["quantity"] == 600
    assert po["items"][0]["qty_rolls"] == 6


async def test_A2_U3_tanpa_rencana_tetap_kosong(klien, kepala_admin, dunia, db):
    pr = await _pr_disetujui(klien, kepala_admin, dunia, None)
    r = await klien.post(f"/api/purchase-requisitions/{pr['id']}/convert-to-po", headers=kepala_admin,
                         json={"supplier_id": dunia["sup"], "warehouse_id": dunia["wh"]})
    assert r.status_code == 200, r.text
    po = await db.purchase_orders.find_one({"id": r.json()["po"]["id"]}, {"_id": 0})
    assert po["items"][0]["qty_rolls"] is None


# ── Nama pembuat tagihan pemasok & PO manual = akun yang masuk (dulu bawaan skema "Admin") ──────────────────────────
async def test_A2_U4_pembuat_po_manual_dan_tagihan_tercatat_akun_masuk(klien, akun, sesi, dunia, db):
    mgr = await akun("manager")
    h = await sesi(mgr)
    r = await klien.post("/api/purchase-orders", headers=h, json={
        "supplier_id": dunia["sup"], "entity_id": KSC, "warehouse_id": dunia["wh"], "route_reason": "uji A2",
        "items": [{"product_id": dunia["pid"], "quantity": 100, "price": 10_000, "unit": "yard", "expected_grade": "A"}]})
    assert r.status_code == 200, r.text
    po = await db.purchase_orders.find_one({"id": r.json()["id"]}, {"_id": 0})
    assert po["created_by"] == mgr["name"]
    assert po["timeline"][0]["actor"] == mgr["name"]
    # penerimaan tiruan (jalur yang sama dengan uji PK-28): qty diterima di baris PO → tagihan dari layar
    await db.purchase_orders.update_one({"id": po["id"]}, {"$set": {"status": "completed", "items.0.received_qty": 100}})
    r = await klien.post("/api/vendor-bills", headers=h, json={
        "po_id": po["id"], "supplier_invoice_no": uid("INV"), "items": [{"product_id": dunia["pid"], "billed_qty": 100,
                                                                          "price": 10_000}]})
    assert r.status_code == 200, r.text
    bill = await db.vendor_bills.find_one({"id": r.json()["id"]}, {"_id": 0})
    assert bill["created_by"] == mgr["name"]
    assert bill["timeline"][0]["actor"] == mgr["name"]
    assert bill["timeline"][0]["label"] == "Tagihan pemasok dibuat"
    assert "3-way match: cocok bersih" in bill["timeline"][0]["note"]
