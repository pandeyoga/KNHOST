"""Probe: on_design_approved for multi-item OD — proofing sample spec should belong to the routed item."""
import asyncio
import os
import sys

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv  # noqa: E402

load_dotenv("/app/backend/.env")
import requests  # noqa: E402

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"


async def main():
    from db import db
    from services import special_order_phase2 as p2
    tok = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}
    body = {"customer_id": "cust_toko_kain", "title": "TEST_probe_spec", "entity_id": "ent_ksc", "expected_delivery": "2026-12-31",
            "submit_for_approval": True, "items": [
                {"source_type": "parent_product", "source_template_id": "ptpl_609f19d3205c", "description": "TEST A labdip",
                 "request_types": ["labdip"], "quantity": 10, "target_price": 100},
                {"source_type": "parent_product", "source_template_id": "ptpl_9ca54122578e", "description": "TEST B printing",
                 "request_types": ["printing"], "quantity": 20, "target_price": 100}]}
    od = requests.post(f"{BASE}/special-orders", json=body, headers=h).json()
    requests.post(f"{BASE}/special-orders/{od['id']}/approve", json={}, headers=h)
    od = await db.special_orders.find_one({"id": od["id"]}, {"_id": 0})
    itB = od["items"][1]
    req_id = itB["design_request_id"]
    design = {"id": "dsgn_TEST_probe", "code": "TST-PROBE", "request_id": req_id, "version": 1}
    await db.design_gallery.insert_one({**design, "status": "approved", "entity_id": "ent_ksc", "title": "TEST probe"})
    try:
        s = await p2.on_design_approved(design, {"name": "probe", "email": "probe"})
        smp = await db.md_samples.find_one({"id": s["id"]}, {"_id": 0})
        spec = await db.rnd_specs.find_one({"id": smp["spec_id"]}, {"_id": 0}) or await db.md_specs.find_one({"id": smp["spec_id"]}, {"_id": 0})
        print("sample item id:", smp.get("special_order_item_id"), "expected", itB["id"])
        print("sample spec_id:", smp["spec_id"], "itemA spec_id:", od["items"][0].get("spec_id"))
        print("spec template:", (spec or {}).get("template_id"), "title:", (spec or {}).get("title"))
        print("BUG" if smp["spec_id"] == od["items"][0].get("spec_id") else "OK")
    finally:
        ids = [x["id"] async for x in db.md_samples.find({"special_order_id": od["id"]}, {"id": 1})]
        await db.md_samples.delete_many({"special_order_id": od["id"]})
        await db.design_requests.delete_many({"special_order_id": od["id"]})
        await db.special_orders.delete_one({"id": od["id"]})
        await db.design_gallery.delete_one({"id": "dsgn_TEST_probe"})
        print("cleaned", len(ids))

asyncio.run(main())
