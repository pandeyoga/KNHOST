"""Data uji TEST_: PO dengan penerimaan kurang → tugas keputusan selisih (panel `po-variance-panel`).
Jalankan: cd /app/backend && python ../scripts/seed_test_po_variance.py [--clear]"""
import asyncio
import copy
import sys

sys.path.insert(0, "/app/backend")
from db import db  # noqa: E402

PO_ID = "po_TEST_variance01"


async def clear():
    await db.purchase_orders.delete_one({"id": PO_ID})
    await db.po_variance_tasks.delete_many({"po_id": PO_ID})
    await db.notifications.delete_many({"link": {"$regex": PO_ID}})
    print("cleared")


async def main():
    if "--clear" in sys.argv:
        return await clear()
    base = await db.purchase_orders.find_one({"entity_id": "ent_ksc", "items.0": {"$exists": True}}, {"_id": 0})
    po = copy.deepcopy(base)
    it = po["items"][0]
    it.update({"quantity": 100.0, "received_qty": 60.0})
    po.update({"id": PO_ID, "po_number": "KSC/TEST_PO-VAR-01", "status": "partially_received",
               "items": [it], "amount_paid": 0, "payments": [], "notes": "TEST_ contoh selisih penerimaan"})
    for k in ("received_at", "completed_at", "closed_at"):
        po.pop(k, None)
    await db.purchase_orders.update_one({"id": PO_ID}, {"$set": po}, upsert=True)
    from services import po_variance_task_service as pvt
    tasks = await pvt.ensure_for_po(PO_ID, "TEST_seed", "TEST_seed")
    print("po", PO_ID, po["po_number"], "tasks", [t["id"] for t in tasks])


asyncio.run(main())
