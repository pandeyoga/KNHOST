"""W2-05 RFID gate/security audit against real ASGI + isolated local Mongo.

The scheduling barriers wrap Motor collection calls only; business functions and
HTTP routes remain unmodified. Assertions describe the observed baseline, so a
fixed implementation should use corrected expected outcomes on revalidation.
"""
import asyncio
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import wave2_env as e
from services import rfid_incident_service as incident

db = e.db
results = []


def record(sid, observed, condition, kind="control", related=None):
    assert condition, (sid, observed)
    row = {"id": sid, "kind": kind, "observed": observed}
    if related:
        row["related"] = related
    results.append(row)
    print(sid, json.dumps(observed), flush=True)


async def device(did, wh, direction="out", kind="gate", status="online"):
    doc = {"id": did, "code": did, "name": did, "type": kind,
           "direction": direction, "warehouse_id": wh, "warehouse_name": wh,
           "status": status, "api_key": "fixture-key-" + did,
           "last_heartbeat": e.now_iso() if hasattr(e, "now_iso") else datetime.now(timezone.utc).isoformat()}
    await db.rfid_devices.insert_one(doc)
    return doc


async def tag_roll(name, owner="A", wh="WA", status="available", journey=None, ref=None):
    rid, epc = "ROLL-" + name, "EPC-" + name
    roll = {"id": rid, "roll_no": rid, "product_id": "P", "owner_entity_id": owner,
            "warehouse_id": wh, "status": status, "journey": journey or {},
            "reserved_ref": ref}
    tag = {"id": "TAG-" + name, "roll_id": rid, "epc": epc,
           "status": "active", "sku": "P", "product_name": "Synthetic"}
    await db.inventory_rolls.insert_one(roll)
    await db.rfid_tags.insert_one(tag)
    return epc


async def ingest(http, dev, epcs):
    return await http.post("/api/rfid/ingest", json={"epcs": epcs},
                           headers={"X-Device-Key": dev["api_key"]})


async def main():
    await e.seed()
    await db.permission_settings.update_one({"id": "default"},
        {"$set": {"matrix.finance.wms": ["view", "update"]}})
    await db.warehouses.insert_many([
        {"id": "WA", "name": "Audit A", "entity_id": "A", "status": "active"},
        {"id": "WB", "name": "Audit B", "entity_id": "B", "status": "active"},
        {"id": "WX", "name": "Wrong warehouse", "entity_id": "A", "status": "active"},
    ])
    a_out = await device("A-OUT", "WA")
    b_out = await device("B-OUT", "WB")
    wrong_out = await device("X-OUT", "WX")
    wrong_in = await device("X-IN", "WX", "in")
    correct_in = await device("B-IN", "WB", "in")
    off = await device("A-OFF", "WA", status="offline")
    printer = await device("A-PRINTER", "WA", kind="printer")

    async with e.httpx.AsyncClient(
        transport=e.httpx.ASGITransport(app=e.server.app, raise_app_exceptions=False),
        base_url="http://audit.local",
        headers={"Authorization": "Bearer audit-local-session", "X-Entity-Id": "A"},
    ) as http:
        r = await http.post("/api/rfid/ingest", json={"epcs": ["UNKNOWN"]})
        record("W2-R-C01", {"http": r.status_code}, r.status_code == 401)
        r = await http.post("/api/rfid/ingest", json={"epcs": ["UNKNOWN"]},
                            headers={"X-Device-Key": "invalid-fixture"})
        record("W2-R-C02", {"http": r.status_code}, r.status_code == 401)
        r = await ingest(http, printer, ["UNKNOWN"])
        record("W2-R-C03", {"http": r.status_code}, r.status_code == 400)

        available = await tag_roll("AVAILABLE")
        r = await ingest(http, a_out, [available]); d = r.json()
        record("W2-R-C04", {"http": r.status_code, "result": d["results"][0]["result"]},
               r.status_code == 200 and d["results"][0]["result"] == "red")
        quarantine = await tag_roll("QUARANTINE", status="quarantine")
        r = await ingest(http, a_out, [quarantine]); d = r.json()
        record("W2-R-C05", {"http": r.status_code, "result": d["results"][0]["result"]},
               r.status_code == 200 and d["results"][0]["result"] == "red")
        unknown = "UNKNOWN-BATCH"
        before = await db.rfid_reads.count_documents({"epc": unknown})
        r = await ingest(http, a_out, [unknown, unknown.lower(), " " + unknown + " "])
        after = await db.rfid_reads.count_documents({"epc": unknown})
        record("W2-R-C06", {"http": r.status_code, "count": r.json()["count"],
               "reads_delta": after - before}, r.status_code == 200 and r.json()["count"] == 1 and after - before == 1)
        inc_before = await db.rfid_incidents.find_one({"epc": unknown})
        r = await ingest(http, a_out, [unknown])
        inc_after = await db.rfid_incidents.find_one({"epc": unknown})
        after2 = await db.rfid_reads.count_documents({"epc": unknown})
        record("W2-R-E01", {"http": r.status_code, "reads": after2,
               "incidents": await db.rfid_incidents.count_documents({"epc": unknown}),
               "hits_before": inc_before["hits"], "hits_after": inc_after["hits"]},
               r.status_code == 200 and after2 == 2 and inc_after["hits"] == 2,
               "wave1_extension", "RF-16")

        reserved = await tag_roll("RESERVED", status="reserved")
        r = await ingest(http, wrong_out, [reserved]); d = r.json()
        record("W2-R-E02", {"http": r.status_code, "result": d["results"][0]["result"],
               "gate_warehouse": "WX", "roll_warehouse": "WA", "document": None},
               r.status_code == 200 and d["results"][0]["result"] == "green",
               "wave1_extension", "RF-02")
        transit = await tag_roll("TRANSIT", status="in_transit_transfer")
        r = await ingest(http, wrong_in, [transit]); d = r.json()
        record("W2-R-E03", {"http": r.status_code, "result": d["results"][0]["result"],
               "gate_warehouse": "WX", "destination_document": None},
               r.status_code == 200 and d["results"][0]["result"] == "green",
               "wave1_extension", "RF-03")
        await db.putaway_orders.insert_one({"id": "PA-1", "pa_number": "PA-1",
                                            "status": "open", "to_warehouse_id": "WB",
                                            "to_warehouse_name": "Audit B", "from_warehouse_id": "WA"})
        with_pa = await tag_roll("PA", status="in_transit_transfer",
                                 journey={"putaway_order_id": "PA-1"})
        r = await ingest(http, correct_in, [with_pa]); d = r.json()
        record("W2-R-C07", {"result": d["results"][0]["result"]},
               r.status_code == 200 and d["results"][0]["result"] == "green")
        r = await ingest(http, wrong_in, [with_pa]); d = r.json()
        record("W2-R-C08", {"result": d["results"][0]["result"]},
               r.status_code == 200 and d["results"][0]["result"] == "red")
        r = await ingest(http, off, [available]); persisted = await db.rfid_devices.find_one({"id": "A-OFF"})
        record("W2-R-E04", {"http": r.status_code, "status_after": persisted["status"]},
               r.status_code == 200 and persisted["status"] == "online", "wave1_extension", "RF-13")
        epcs = ["BULK-" + str(i).zfill(3) for i in range(501)]
        r = await ingest(http, a_out, epcs); d = r.json()
        record("W2-R-E05", {"http": r.status_code, "submitted": 501,
               "acknowledged": d["count"], "last_persisted": await db.rfid_reads.count_documents({"epc": epcs[-1]})},
               r.status_code == 200 and d["count"] == 500 and await db.rfid_reads.count_documents({"epc": epcs[-1]}) == 0,
               "wave1_extension", "RF-16")

        b_tag = await tag_roll("B-ALARM", owner="B", wh="WB")
        r = await ingest(http, b_out, [b_tag]); b_inc = await db.rfid_incidents.find_one({"epc": b_tag})
        assert r.status_code == 200 and b_inc["owner_entity_id"] == "B"
        r = await http.get("/api/rfid/reads", params={"warehouse_id": "WB"}); body = r.json()
        record("W2-R-F01", {"http": r.status_code, "caller_scope": ["A"],
               "foreign_read_owner": body["reads"][0]["owner_entity_id"]},
               r.status_code == 200 and any(x.get("owner_entity_id") == "B" for x in body["reads"]),
               "defect")
        r = await http.get("/api/rfid/incidents", params={"warehouse_id": "WB"}); body = r.json()
        record("W2-R-F02", {"http": r.status_code, "caller_scope": ["A"],
               "foreign_incident_owner": body["incidents"][0]["owner_entity_id"]},
               r.status_code == 200 and any(x.get("owner_entity_id") == "B" for x in body["incidents"]),
               "defect")
        r = await http.post(f"/api/rfid/incidents/{b_inc['id']}/acknowledge", json={"note": "Synthetic"})
        b_state = await db.rfid_incidents.find_one({"id": b_inc["id"]})
        record("W2-R-F03", {"http": r.status_code, "caller_scope": ["A"],
               "foreign_owner": b_state["owner_entity_id"], "status": b_state["status"]},
               r.status_code == 200 and b_state["status"] == "acknowledged", "defect")
        r = await http.post(f"/api/rfid/incidents/{b_inc['id']}/resolve", json={"note": "Synthetic"})
        b_state = await db.rfid_incidents.find_one({"id": b_inc["id"]})
        record("W2-R-F04", {"http": r.status_code, "foreign_owner": b_state["owner_entity_id"],
               "status": b_state["status"]},
               r.status_code == 200 and b_state["status"] == "resolved", "defect")
        r = await http.get("/api/rfid/shrinkage-report"); body = r.json()
        record("W2-R-F05", {"http": r.status_code, "caller_scope": ["A"],
               "foreign_warehouses": [x["warehouse_id"] for x in body["per_warehouse"] if x["warehouse_id"] == "WB"]},
               r.status_code == 200 and any(x["warehouse_id"] == "WB" for x in body["per_warehouse"]),
               "defect")
        r = await http.get("/api/rfid/device-health"); body = r.json()
        record("W2-R-F06", {"http": r.status_code, "caller_scope": ["A"],
               "foreign_devices": [x["id"] for x in body["devices"] if x["id"] == "B-OUT"]},
               r.status_code == 200 and any(x["id"] == "B-OUT" for x in body["devices"]), "defect")
        r = await http.get("/api/rfid/incidents", params={"warehouse_id": "WA"}); body = r.json()
        record("W2-R-C09", {"http": r.status_code, "foreign_owners": sorted(set(
               x.get("owner_entity_id") for x in body["incidents"] if x.get("owner_entity_id")))},
               r.status_code == 200 and all(x.get("owner_entity_id") != "B" for x in body["incidents"]))
        r = await http.get("/api/rfid/incidents"); body = r.json()
        record("W2-R-F07", {"http": r.status_code, "foreign_count": sum(
               x.get("owner_entity_id") == "B" for x in body["incidents"])},
               r.status_code == 200 and any(x.get("owner_entity_id") == "B" for x in body["incidents"]),
               "defect")

        # Sequential lifecycle control and retry control.
        aid = (await db.rfid_incidents.find_one({"epc": "UNKNOWN-BATCH"}))["id"]
        a = await http.post(f"/api/rfid/incidents/{aid}/acknowledge", json={"note": "A"})
        b = await http.post(f"/api/rfid/incidents/{aid}/resolve", json={"note": "B"})
        c = await http.post(f"/api/rfid/incidents/{aid}/acknowledge", json={"note": "C"})
        state = await db.rfid_incidents.find_one({"id": aid})
        record("W2-R-C10", {"http": [a.status_code, b.status_code, c.status_code],
               "final_status": state["status"]},
               [a.status_code, b.status_code, c.status_code] == [200, 200, 400] and state["status"] == "resolved")

        # Force ack to read open, pause before write, allow resolve to commit, then resume ack.
        race_id = "RACE-ACK-RESOLVE"
        await db.rfid_incidents.insert_one({"id": race_id, "epc": race_id, "device_id": "A-OUT",
            "warehouse_id": "WA", "owner_entity_id": "A", "status": "open", "hits": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_at": datetime.now(timezone.utc).isoformat(), "notes": []})
        real_db = incident.db
        arrived, release = asyncio.Event(), asyncio.Event()

        class TransitionCollection:
            def __getattr__(self, name):
                return getattr(db.rfid_incidents, name)

            async def update_one(self, query, update, *args, **kwargs):
                if query.get("id") == race_id and update.get("$set", {}).get("status") == "acknowledged":
                    arrived.set()
                    await release.wait()
                return await db.rfid_incidents.update_one(query, update, *args, **kwargs)

        class DatabaseProxy:
            def __getattr__(self, name):
                return TransitionCollection() if name == "rfid_incidents" else getattr(db, name)

        incident.db = DatabaseProxy()
        try:
            ack_task = asyncio.create_task(http.post(f"/api/rfid/incidents/{race_id}/acknowledge", json={"note": "ack"}))
            await asyncio.wait_for(arrived.wait(), 5)
            resolved = await http.post(f"/api/rfid/incidents/{race_id}/resolve", json={"note": "resolve"})
            release.set()
            acknowledged = await ack_task
        finally:
            release.set()
            incident.db = real_db
        state = await db.rfid_incidents.find_one({"id": race_id})
        record("W2-R-F08", {"http_ack": acknowledged.status_code,
               "http_resolve": resolved.status_code, "final_status": state["status"],
               "resolved_at_present": bool(state.get("resolved_at")),
               "ack_at_present": bool(state.get("ack_at"))},
               acknowledged.status_code == 200 and resolved.status_code == 200
               and state["status"] == "acknowledged" and bool(state.get("resolved_at")), "defect")

        # Two concurrent red reads both observe no open incident; each inserts one.
        dedupe_epc = "RACE-DEDUPE"
        real_db = incident.db
        arrived_count, release = 0, asyncio.Event()

        class DedupeCollection:
            def __getattr__(self, name):
                return getattr(db.rfid_incidents, name)

            async def find_one(self, query, *args, **kwargs):
                nonlocal arrived_count
                if query.get("epc") == dedupe_epc:
                    value = await db.rfid_incidents.find_one(query, *args, **kwargs)
                    arrived_count += 1
                    if arrived_count == 2:
                        release.set()
                    await release.wait()
                    return value
                return await db.rfid_incidents.find_one(query, *args, **kwargs)

        class DedupeDB:
            def __getattr__(self, name):
                return DedupeCollection() if name == "rfid_incidents" else getattr(db, name)

        incident.db = DedupeDB()
        try:
            rd = {"id": "READ-RACE", "epc": dedupe_epc, "device_id": "A-OUT",
                  "device_name": "A-OUT", "warehouse_id": "WA", "owner_entity_id": "A",
                  "read_type": "gate_out", "result": "red", "reason": "Synthetic race"}
            await asyncio.wait_for(asyncio.gather(incident.create_from_read(rd),
                                                  incident.create_from_read(rd)), 10)
        finally:
            release.set()
            incident.db = real_db
        rows = await db.rfid_incidents.find({"epc": dedupe_epc}).to_list(10)
        record("W2-R-F09", {"open_incidents": len(rows), "hits": [x["hits"] for x in rows]},
               len(rows) == 2 and all(x["status"] == "open" and x["hits"] == 1 for x in rows), "defect")


async def run():
    try:
        await main()
    finally:
        sha = subprocess.check_output(["git", "-C", str(e.REPO), "rev-parse", "HEAD"], text=True).strip()
        output = Path(os.environ.get("RFID_AUDIT_OUTPUT", str(Path(__file__).parent.parent / "rfid-results.json")))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({
            "commit": sha, "database": e.DBNAME,
            "level": "ASGI HTTP plus direct incident service race; Motor/Mongo; isolated synthetic fixtures; no app lifespan or physical device",
            "scenarios": results,
        }, indent=2), encoding="utf-8")
        e.client.close()


asyncio.run(run())
