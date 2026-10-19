"""LN-140 temuan uji rantai: supplier grup terlihat, gudang retur benar, SJ supplier di lot/roll."""
import os
import sys
import uuid

import requests
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
CST = DB.business_entities.find_one({"doc_prefix": "CST"})["id"]
TAG = f"TEST_LN140_{uuid.uuid4().hex[:5]}"


def _h(ent):
    t = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}).json()["token"]
    return {"Authorization": f"Bearer {t}", "X-Entity-Id": ent}


def test_group_suppliers_visible_in_each_entity():
    sup = DB.suppliers.find_one({"entity_id": "all"})
    rows = requests.get(f"{BASE}/suppliers", headers=_h(CST)).json()
    assert sup["id"] in {s["id"] for s in rows}
    own = DB.suppliers.find_one({"entity_id": "ent_kanda"})
    assert own["id"] not in {s["id"] for s in rows}


sys.path.insert(0, "/app/backend/tests")
from _shared_loop import run as _run  # noqa: E402


def test_return_warehouse_uses_outbound_task_then_entity_default():
    from services.return_service import _resolve_return_warehouse
    so_id, wh = f"so_{TAG}", DB.warehouses.find_one({"code": "RCM-WOVEN"})["id"]
    DB.sales_orders.insert_one({"id": so_id, "entity_id": CST, "notes": TAG, "allocations": []})
    DB.wms_tasks.insert_one({"id": f"wms_{TAG}", "order_id": so_id, "flow_type": "outbound", "warehouse_id": wh,
                             "created_at": "2026-10-18", "notes": TAG})
    try:
        async def both():
            first = await _resolve_return_warehouse(so_id)
            await __import__("db").db.wms_tasks.delete_one({"id": f"wms_{TAG}"})
            return first, await _resolve_return_warehouse(so_id)
        first, second = _run(both())
        assert first == wh
        cst_whs = {w["id"] for w in DB.warehouses.find({"entity_ids": CST})} | {
            w["id"] for w in DB.warehouses.find({"$or": [{"entity_ids": []}, {"entity_ids": {"$exists": False}}]})}
        assert second in cst_whs
    finally:
        DB.sales_orders.delete_one({"id": so_id})
        DB.wms_tasks.delete_many({"notes": TAG})


def test_backfill_supplier_dn_to_lot_and_roll():
    from services.lot_trace_service import backfill_supplier_dn
    tid, lid, rid = f"wms_{TAG}_g", f"lot_{TAG}", f"roll_{TAG}"
    DB.wms_tasks.insert_one({"id": tid, "supplier_dn_number": f"SJ-{TAG}", "lot_ids": [lid], "notes": TAG})
    DB.inventory_lots.insert_one({"id": lid, "lot_number": f"{TAG}-LOT", "note": TAG})
    DB.inventory_rolls.insert_one({"id": rid, "grn_task_id": tid, "supplier_dn_number": "", "notes": TAG})
    try:
        async def twice():
            await backfill_supplier_dn()
            await backfill_supplier_dn()
        _run(twice())
        assert DB.inventory_rolls.find_one({"id": rid})["supplier_dn_number"] == f"SJ-{TAG}"
        assert DB.inventory_lots.find_one({"id": lid})["supplier_dn_numbers"] == [f"SJ-{TAG}"]
    finally:
        DB.wms_tasks.delete_many({"notes": TAG})
        DB.inventory_lots.delete_many({"note": TAG})
        DB.inventory_rolls.delete_many({"notes": TAG})
