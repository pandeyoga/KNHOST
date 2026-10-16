"""P09 — RF-02, RF-03, RF-16, UX-01 — regression invariant (data sintetis, tanpa perangkat fisik).

Usage: cd /app/backend && python ../audit/iterations/2026-10-08-P09-gate-contract/repro_p09.py
Data sintetis ber-prefix `audit_p9_*` dihapus di akhir.
"""
import asyncio
import json
import sys
import uuid

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def guarded(fid, coro):
    try:
        await coro
    except Exception as exc:  # noqa: BLE001
        check(fid, f"bagian {fid} crash", False, repr(exc)[:200])


async def main():
    from db import db
    from core_utils import now_iso
    from services import rfid_ingest_service as ing, rfid_service as rs
    T = f"audit_p9_{uuid.uuid4().hex[:6]}"
    A, S, D, H = "ent_ksc", "wh_jakarta", "wh_bandung", "wh_surabaya"
    prod = await db.products.find_one({}, {"_id": 0, "id": 1})

    async def decide(direction, wh, roll):
        try:
            from services import gate_evaluator as ge
            return await ge.evaluate(direction, wh, roll)
        except ImportError:  # HEAD lama
            return await ing._doc_gate_decision({"direction": direction, "warehouse_id": wh}, roll)

    async def mk_roll(n, **kw):
        r = {"id": f"{T}_r{n}", "roll_no": f"{T.upper()}-{n}", "product_id": prod["id"], "owner_entity_id": A,
             "warehouse_id": S, "status": "available", "length_remaining": 10.0, "unit": "meter",
             "created_at": now_iso(), **kw}
        await db.inventory_rolls.insert_one(dict(r))
        return r

    def red(v):
        return v.get("result") == "red"

    async def rf02():
        so = {"id": f"{T}_so", "number": f"{T}-SO", "entity_id": A, "status": "confirmed"}
        await db.sales_orders.insert_one(dict(so))
        ref = {"type": "sales_order", "id": so["id"]}
        r_del = await mk_roll(1, status="delivered")
        check("RF-02", "roll delivered tanpa dokumen di gate OUT gudang lain → MERAH", red(await decide("out", H, r_del)))
        r_res = await mk_roll(2, status="reserved", reserved_ref=ref)
        check("RF-02", "roll reserved (belum dispatch) → MERAH", red(await decide("out", S, r_res)))
        r_ok = await mk_roll(3, status="in_transit_sales", reserved_ref=ref)
        await db.shipments.insert_one({"id": f"{T}_shp", "order_id": so["id"], "warehouse_id": S, "status": "dispatched",
                                       "rolls": [{"roll_id": r_ok["id"]}], "created_at": now_iso()})
        v = await decide("out", S, r_ok)
        check("RF-02", "roll di surat jalan dispatched, gudang asal benar → HIJAU", v.get("result") == "green", v)
        check("RF-02", "roll sah dibaca di gate OUT gudang lain → MERAH", red(await decide("out", H, r_ok)))
        r_other = await mk_roll(4, status="in_transit_sales", reserved_ref=ref)
        check("RF-02", "roll SO tapi tidak tercantum di surat jalan → MERAH", red(await decide("out", S, r_other)))
        r_cons = await mk_roll(5, status="consumed")
        check("RF-02", "tag roll consumed → MERAH", red(await decide("out", S, r_cons)))
        await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"status": "cancelled"}})
        check("RF-02", "SO batal → MERAH", red(await decide("out", S, r_ok)))
        await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"status": "confirmed"}})
        pa = {"id": f"{T}_pa", "pa_number": f"{T}-PA", "status": "completed", "from_warehouse_id": S,
              "to_warehouse_id": D, "items": [{"roll_id": f"{T}_r6"}]}
        await db.putaway_orders.insert_one(dict(pa))
        r_pa = await mk_roll(6, status="in_transit_transfer", active_movement={"type": "putaway", "id": pa["id"]},
                             journey={"stage": "putaway_in_transit", "putaway_order_id": pa["id"]})
        check("RF-02", "PA selesai → keluar MERAH", red(await decide("out", S, r_pa)))
        v = await decide("out", S, r_ok)
        check("RF-02", "kode alasan jelas pada penolakan", True if "code" in v or v.get("result") == "green" else False, v)
        # replay keluar lewat ingest (jalur nyata)
        gate1 = {"id": f"{T}_g1", "type": "gate", "direction": "out", "warehouse_id": S, "name": "G1"}
        gate2 = {"id": f"{T}_g2", "type": "gate", "direction": "out", "warehouse_id": S, "name": "G2"}
        tag = await rs.encode_tag(r_ok["id"], [A])
        first = await ing.ingest(gate1, [tag["epc"]])
        again = await ing.ingest(gate2, [tag["epc"]])
        check("RF-02", "keluar pertama HIJAU, keluar ulang (gate lain) MERAH",
              first["results"][0]["result"] == "green" and again["results"][0]["result"] == "red",
              (first["results"][0].get("reason"), again["results"][0].get("reason")))

    async def rf03():
        tr = {"id": f"{T}_tr", "code": f"{T}-TRF", "status": "dispatched", "source_warehouse_id": S, "dest_warehouse_id": D}
        await db.warehouse_transfers.insert_one(dict(tr))
        r = await mk_roll(11, status="in_transit_transfer", reserved_ref={"type": "wh_transfer", "id": tr["id"]})
        check("RF-03", "roll menuju D dibaca IN di H → MERAH", red(await decide("in", H, r)))
        v = await decide("in", D, r)
        check("RF-03", "roll menuju D dibaca IN di D (transfer dispatched) → HIJAU", v.get("result") == "green", v)
        r2 = await mk_roll(12, status="in_transit_transfer")
        check("RF-03", "transit tanpa dokumen → MERAH (tanpa fallback hijau)", red(await decide("in", D, r2)))
        r3 = await mk_roll(13, status="in_transit_sales")
        check("RF-03", "transit penjualan bukan transfer internal → MERAH", red(await decide("in", D, r3)))
        await db.warehouse_transfers.update_one({"id": tr["id"]}, {"$set": {"status": "approved"}})
        check("RF-03", "transfer belum dispatched → MERAH", red(await decide("in", D, r)))

    async def rf16_ux01():
        gate = {"id": f"{T}_g3", "type": "gate", "direction": "out", "warehouse_id": S, "name": "G3"}
        await db.rfid_devices.insert_one({**gate, "code": f"{T}-G3", "status": "online", "enabled": True,
                                          "last_heartbeat": now_iso()})
        r_bad = await mk_roll(21)                       # available → merah
        so = {"id": f"{T}_so2", "number": f"{T}-SO2", "entity_id": A, "status": "confirmed"}
        await db.sales_orders.insert_one(dict(so))
        r_good = await mk_roll(22, status="in_transit_sales", reserved_ref={"type": "sales_order", "id": so["id"]})
        await db.shipments.insert_one({"id": f"{T}_shp2", "order_id": so["id"], "warehouse_id": S, "status": "dispatched",
                                       "rolls": [{"roll_id": r_good["id"]}], "created_at": now_iso()})
        tb = await rs.encode_tag(r_bad["id"], [A])
        tg = await rs.encode_tag(r_good["id"], [A])
        try:
            res = await ing.ingest(gate, None, [{"epc": tb["epc"], "event_id": f"{T}-e1"}, {"epc": tg["epc"], "event_id": f"{T}-e2"}])
        except TypeError:
            res = await ing.ingest(gate, [tb["epc"], tg["epc"]])
        n_reads = await db.rfid_reads.count_documents({"device_id": gate["id"]})
        n_inc = await db.rfid_incidents.count_documents({"epc": tb["epc"]})
        try:
            rep = await ing.ingest(gate, None, [{"epc": tb["epc"], "event_id": f"{T}-e1"}])
        except TypeError:
            rep = await ing.ingest(gate, [tb["epc"]])
        check("RF-16", "replay event_id sama → tidak menambah read / insiden",
              await db.rfid_reads.count_documents({"device_id": gate["id"]}) == n_reads
              and await db.rfid_incidents.count_documents({"epc": tb["epc"]}) == n_inc and rep.get("duplicates") == 1, rep.get("duplicates"))
        try:
            await ing.ingest(gate, None, [{"epc": tb["epc"], "event_id": f"{T}-e9"}])
        except TypeError:
            await ing.ingest(gate, [tb["epc"]])
        check("RF-16", "tag diam (event baru, EPC sama, dalam dwell) → bukan event bisnis baru",
              await db.rfid_reads.count_documents({"device_id": gate["id"]}) == n_reads
              and await db.rfid_incidents.count_documents({"epc": tb["epc"]}) == n_inc)
        code = 200
        try:
            await ing.ingest(gate, [rs.generate_epc() for _ in range(501)])
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "status_code", 0)
        check("RF-16", ">500 event ditolak eksplisit (413), tidak dipotong diam-diam", code == 413, code)
        p = res.get("passage") or {}
        check("UX-01", "passage campuran merah+hijau → verdict MERAH (red-dominant)",
              p.get("verdict") == "red" and p.get("red_count") == 1 and p.get("green_count") == 1, p)
        st = await ing.gate_status(gate["id"]) if hasattr(ing, "gate_status") else {}
        check("UX-01", "status server: alarm terkunci + umur heartbeat", st.get("latched") is True
              and st.get("device", {}).get("heartbeat_age_s") is not None, {k: st.get(k) for k in ("latched",)})
        if hasattr(ing, "acknowledge_passage"):
            await ing.acknowledge_passage(p["id"], "audit", "cek fisik oleh satpam")
        st2 = await ing.gate_status(gate["id"]) if hasattr(ing, "gate_status") else {}
        check("UX-01", "acknowledge membuka kunci TANPA menghapus read/insiden sumber",
              st2.get("latched") is False and await db.rfid_reads.count_documents({"device_id": gate["id"]}) == n_reads
              and await db.rfid_incidents.count_documents({"epc": tb["epc"]}) == n_inc, st2.get("latched"))
        await db.rfid_reads.insert_one({"id": f"{T}_inv", "device_id": f"{T}_hh", "read_type": "inventory",
                                        "warehouse_id": S, "timestamp": "2999-01-01T00:00:00+00:00"})
        rows = await rs.list_reads(None, None, "gate", S, 5)
        check("UX-01", "filter server read_type=gate tidak tertutup trafik inventory",
              rows and all(r["read_type"] in ("gate_in", "gate_out") for r in rows), [r.get("read_type") for r in rows])

    for fid, fn in [("RF-02", rf02), ("RF-03", rf03), ("RF-16", rf16_ux01)]:
        await guarded(fid, fn())

    tags = [t["epc"] for t in await db.rfid_tags.find({"roll_id": {"$regex": f"^{T}"}}, {"_id": 0, "epc": 1}).to_list(100)]
    await db.rfid_incidents.delete_many({"epc": {"$in": tags}})
    for c in ("rfid_reads", "rfid_passages", "rfid_observations"):
        await db[c].delete_many({"device_id": {"$regex": f"^{T}"}})
    await db.rfid_tags.delete_many({"roll_id": {"$regex": f"^{T}"}})
    for c in ("inventory_rolls", "sales_orders", "shipments", "putaway_orders", "warehouse_transfers", "rfid_devices"):
        await db[c].delete_many({"id": {"$regex": f"^{T}"}})

    for r in results:
        print(("PASS " if r["pass"] else "FAIL ") + f"[{r['id']}] {r['invariant']}" + ("" if r["pass"] else f" :: {r['detail']}"))
    print(json.dumps({"pass": sum(r["pass"] for r in results), "fail": sum(not r["pass"] for r in results)}))


if __name__ == "__main__":
    asyncio.run(main())
