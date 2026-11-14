"""PK-27 U12 — di MongoDB ASLI (lingkungan A): penyelesaian retur PER ROLL menilai roll yang kembali pada potret biaya
surat jalan (IV-08).

Lapis B (`tests_mem/test_PK27_biaya_roll.py::test_PK27_U12_…`) hanya bisa menguji rencana penyelesaian (`plan_event`):
eksekusinya memakai pembaruan larik bertapis (`array_filters`) yang tidak didukung database tiruan.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); fixture disisipkan langsung ke database uji
lokal (`MONGO_URL`/`DB_NAME`). Tidak untuk database berisi data nyata.

Persiapan (fixture): pesanan kredit tanpa PPN 200 m @ 20.000 di ent_ksc; surat jalan berpotret `r1` 100 m × 10.000 dan
`r2` 100 m × 14.000 (HPP 2.400.000); kedua roll `delivered`; roll lain produk itu `available` 100 m × 16.000 (rata-rata
produk kini 16.000). Retur `r2` 100 m kondisi baik, sudah diterima gudang dan di-QC (`inspected`).
Harapan: nota kredit 2.000.000, `cogs_amount` = 100 × 14.000 = 1.400.000 (bukan 1.600.000), `cogs_source="surat_jalan"`;
jurnal Dr 1-1300 / Cr 5-1000 1.400.000; roll `r2` karantina ber-`unit_cost` 14.000.
"""
import os
import uuid
from datetime import datetime, timezone

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
KSC = "ent_ksc"


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": KSC}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_U12_penyelesaian_per_roll_dinilai_potret_surat_jalan():
    h = _login()
    t = uuid.uuid4().hex[:8]
    pid, wid, so, sr = f"prd_bp27_{t}", f"wh_bp27_{t}", f"so_bp27_{t}", f"sr_bp27_{t}"
    r1, r2, lain = f"roll_bp27_r1_{t}", f"roll_bp27_r2_{t}", f"roll_bp27_lain_{t}"
    DB.products.insert_one({"id": pid, "name": "Kain Uji BP27", "sku": f"SKU-{pid}", "base_unit": "meter",
                            "price": 20_000, "is_active": True})
    DB.warehouses.insert_one({"id": wid, "name": "Gudang Uji BP27", "entity_id": KSC, "is_active": True,
                              "created_at": _now()})
    dasar = {"product_id": pid, "warehouse_id": wid, "owner_entity_id": KSC, "entity_id": KSC, "unit": "meter",
             "length": 100, "length_initial": 100, "length_remaining": 100, "grade": "A", "created_at": _now()}
    DB.inventory_rolls.insert_many([
        {**dasar, "id": r1, "roll_no": f"BP27-R1-{t}", "status": "delivered", "unit_cost": 10_000,
         "base_unit_cost": 10_000, "reserved_ref": {"type": "sales_order", "id": so}},
        {**dasar, "id": r2, "roll_no": f"BP27-R2-{t}", "status": "delivered", "unit_cost": 14_000,
         "base_unit_cost": 14_000, "reserved_ref": {"type": "sales_order", "id": so}},
        {**dasar, "id": lain, "roll_no": f"BP27-LAIN-{t}", "status": "available", "unit_cost": 16_000,
         "base_unit_cost": 16_000}])
    num = f"SO/BP27/{t}"
    DB.sales_orders.insert_one({
        "id": so, "number": num, "entity_id": KSC, "status": "shipped", "customer_id": "cus_bp27",
        "customer_name": "Pelanggan Uji BP27", "payment_method": "kredit",
        "items": [{"product_id": pid, "quantity": 200, "base_quantity": 200, "unit": "meter", "price": 20_000,
                   "line_total": 4_000_000}], "allocations": [{"warehouse_id": wid, "product_id": pid, "qty": 200}],
        "grand_total": 4_000_000, "ppn_amount": 0, "payments": [], "created_at": _now()})
    DB.shipments.insert_one({
        "id": f"shp_bp27_{t}", "shipment_no": f"SJ/BP27/{t}", "entity_id": KSC, "order_id": so, "order_number": num,
        "product_id": pid, "warehouse_id": wid, "qty": 200, "unit": "meter", "status": "dispatched",
        "created_at": _now(), "rolls": [
            {"roll_id": r1, "length": 100, "unit": "meter", "unit_cost": 10_000, "extended_cost": 1_000_000},
            {"roll_id": r2, "length": 100, "unit": "meter", "unit_cost": 14_000, "extended_cost": 1_400_000}]})
    DB.sales_returns.insert_one({
        "id": sr, "number": f"RJ/BP27/{t}", "entity_id": KSC, "status": "inspected", "order_id": so,
        "order_number": num, "customer_id": "cus_bp27", "customer_name": "Pelanggan Uji BP27",
        "attachments": [{"id": f"att_bp27_{t}", "name": "foto.jpg"}], "created_at": _now(),
        "roll_locations": {r2: {"stage": "received", "warehouse_id": wid}},
        "items": [{"product_id": pid, "product_name": "Kain Uji BP27", "quantity_returned": 100, "unit": "meter",
                   "condition": "ok", "reason": "salah warna", "roll_ids": [r2], "roll_qtys": {r2: 100},
                   "inspection": {"grade": "A", "roll_results": {r2: {"grade": "A", "actual_qty": 100,
                                                                     "condition": "ok"}}}}]})
    r = requests.post(f"{BASE}/sales-returns/{sr}/roll-settlement", headers=h,
                      json={"rolls": [{"roll_id": r2, "outcome": "refund"}]}, timeout=60)
    assert r.status_code == 200, r.text
    cn = DB.credit_notes.find_one({"return_id": sr})
    assert (cn["gross_amount"], cn["cogs_amount"], cn.get("cogs_source")) == (2_000_000, 1_400_000, "surat_jalan"), cn
    je = DB.journal_entries.find_one({"source_type": "sales_return", "source_id": f"{sr}:{cn['settlement_id']}",
                                      "status": {"$ne": "void"}})
    hpp = {(ln["account_code"], ln["debit"], ln["credit"]) for ln in je["lines"]
           if ln["account_code"] in ("1-1300", "5-1000")}
    assert hpp == {("1-1300", 1_400_000, 0), ("5-1000", 0, 1_400_000)}, je["lines"]
    rd = DB.inventory_rolls.find_one({"id": r2})
    assert (rd["status"], rd["unit_cost"]) == ("quarantine", 14_000), rd
