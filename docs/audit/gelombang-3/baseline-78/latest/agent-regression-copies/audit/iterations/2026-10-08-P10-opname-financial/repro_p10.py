"""P10 — FN-14, RF-17, WM-07, WM-08 — regression invariant (in-process ASGI + data sintetis).

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-08-P10-opname-financial/repro_p10.py
Data sintetis ber-prefix `audit_p10_*` dihapus di akhir (sesi, roll, jurnal, produk, gudang).
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
    import httpx
    from server import app
    from db import db
    from core_utils import now_iso
    T = f"audit_p10_{uuid.uuid4().hex[:6]}"
    A, WH = "ent_ksc", "wh_jakarta"
    tr = httpx.ASGITransport(app=app)
    c = httpx.AsyncClient(transport=tr, base_url="http://t", timeout=60)
    tok = (await c.post("/api/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})).json()["token"]
    H = {"Authorization": f"Bearer {tok}", "X-Entity-Id": A}

    async def mk_prod(n, **kw):
        p = {"id": f"{T}_p{n}", "sku": f"{T.upper()}-{n}", "name": f"Audit P10 {n}", "unit": "meter", **kw}
        await db.products.insert_one(dict(p))
        return p

    async def mk_roll(pid, n, qty, bin_id="", status="available", cost=100.0, wh=WH, **kw):
        await db.inventory_rolls.insert_one({"id": f"{T}_r{n}", "roll_no": f"{T}-{n}", "product_id": pid,
                                             "owner_entity_id": A, "warehouse_id": wh, "bin_id": bin_id or None,
                                             "status": status, "length_remaining": float(qty), "length": float(qty),
                                             "unit": "meter", "unit_cost": cost, "created_at": now_iso(), **kw})

    async def session(name):
        r = await c.post("/api/cycle-count/sessions", json={"warehouse_id": WH, "name": f"{T}-{name}"}, headers=H)
        return r.json()["id"]

    async def add(sid, pid, bin_id=""):
        return await c.post(f"/api/cycle-count/sessions/{sid}/items", json={"product_id": pid, "bin_id": bin_id,
                                                                          "owner_entity_id": A}, headers=H)

    async def count(sid, item_id, qty):
        return await c.patch(f"/api/cycle-count/sessions/{sid}/items/{item_id}", json={"actual_qty": qty}, headers=H)

    async def wm07():
        p = await mk_prod(1)
        await mk_roll(p["id"], 1, 40, "binA")
        await mk_roll(p["id"], 2, 60, "binB")
        sid = await session("bin")
        ia = (await add(sid, p["id"], "binA")).json()
        check("WM-07", "item binA expected = 40 (bukan 100 seluruh gudang)", ia.get("expected_qty") == 40, ia.get("expected_qty"))
        r = await add(sid, p["id"], "binA")
        check("WM-07", "count key duplikat → 409", r.status_code == 409, r.status_code)
        r = await add(sid, p["id"], "")
        check("WM-07", "campur level gudang + bin untuk produk sama → 409", r.status_code == 409, r.status_code)
        ib = (await add(sid, p["id"], "binB")).json()
        r = await count(sid, ia["id"], -1)
        check("WM-07", "actual negatif ditolak (400/422)", r.status_code in (400, 422), r.status_code)
        r = await c.patch(f"/api/cycle-count/sessions/{sid}/items/{ia['id']}", content='{"actual_qty": NaN}',
                          headers={**H, "Content-Type": "application/json"})
        check("WM-07", "actual NaN ditolak", r.status_code in (400, 422), r.status_code)
        await count(sid, ia["id"], 30)
        await count(sid, ib["id"], 60)
        s = (await c.post(f"/api/cycle-count/sessions/{sid}/submit", headers=H)).json()
        check("WM-07", "binB 60/60 → tidak ada selisih binB", len(s.get("discrepancies", [])) == 1, s.get("discrepancies"))
        r = await c.post(f"/api/cycle-count/sessions/{sid}/approve", json={"reason": "audit"}, headers=H)
        a = sum(x["length_remaining"] for x in await db.inventory_rolls.find({"product_id": p["id"], "bin_id": "binA", "status": {"$ne": "consumed"}}, {"_id": 0}).to_list(10))
        b = sum(x["length_remaining"] for x in await db.inventory_rolls.find({"product_id": p["id"], "bin_id": "binB"}, {"_id": 0}).to_list(10))
        check("WM-07", "approve dua bin: binA 40→30, binB tetap 60 (tanpa double reduction)", r.status_code == 200 and a == 30 and b == 60, (r.status_code, a, b, r.text[:150]))
        je = await db.journal_entries.find_one({"source_type": "cycle_count_variance", "source_id": f"{sid}:{ia['id']}"}, {"_id": 0})
        ok = je and any(ln["account_code"] == "5-9500" and abs(ln["debit"] - 1000) < 0.01 for ln in je["lines"]) \
            and any(ln["account_code"] == "1-1300" and abs(ln["credit"] - 1000) < 0.01 for ln in je["lines"])
        check("FN-14", "kurang 10 @100 → jurnal Dr 5-9500 1.000 / Cr 1-1300 1.000", ok, je and je["lines"])
        r2 = await c.post(f"/api/cycle-count/sessions/{sid}/approve", json={"reason": "audit"}, headers=H)
        n = await db.journal_entries.count_documents({"source_type": "cycle_count_variance", "source_id": {"$regex": f"^{sid}"}})
        check("FN-14", "approve ulang ditolak & jurnal tidak dobel", r2.status_code == 400 and n == 1, (r2.status_code, n))

    async def fn14_surplus():
        p = await mk_prod(2)
        await mk_roll(p["id"], 21, 50, "", cost=80.0)
        sid = await session("surplus")
        it = (await add(sid, p["id"])).json()
        await count(sid, it["id"], 55)
        await c.post(f"/api/cycle-count/sessions/{sid}/submit", headers=H)
        r = await c.post(f"/api/cycle-count/sessions/{sid}/approve", json={"reason": "audit"}, headers=H)
        new = await db.inventory_rolls.find_one({"product_id": p["id"], "id": {"$ne": f"{T}_r21"}}, {"_id": 0})
        check("FN-14", "surplus 5 → roll baru ber-HPP WAC (80), bukan 0", r.status_code == 200 and new and float(new.get("unit_cost") or 0) == 80, (r.status_code, (new or {}).get("unit_cost"), r.text[:150]))
        je = await db.journal_entries.find_one({"source_type": "cycle_count_variance", "source_id": f"{sid}:{it['id']}"}, {"_id": 0})
        ok = je and any(ln["account_code"] == "1-1300" and abs(ln["debit"] - 400) < 0.01 for ln in je["lines"])
        check("FN-14", "surplus → jurnal Dr 1-1300 400 / Cr pendapatan lain", ok, je and je["lines"])
        # biaya nol
        p0 = await mk_prod(3)
        sid0 = await session("zero")
        it0 = (await add(sid0, p0["id"])).json()
        await count(sid0, it0["id"], 5)
        await c.post(f"/api/cycle-count/sessions/{sid0}/submit", headers=H)
        r = await c.post(f"/api/cycle-count/sessions/{sid0}/approve", json={"reason": "audit"}, headers=H)
        n = await db.inventory_rolls.count_documents({"product_id": p0["id"]})
        check("FN-14", "surplus tanpa biaya acuan & tanpa alasan → 409, tidak ada roll dibuat", r.status_code == 409 and n == 0, (r.status_code, n))
        st = (await db.cycle_count_sessions.find_one({"id": sid0}, {"_id": 0, "status": 1, "saga_lock": 1}))
        check("FN-14", "409 melepas kunci saga (sesi tetap submitted)", st["status"] == "submitted" and not st.get("saga_lock"), st)
        r = await c.post(f"/api/cycle-count/sessions/{sid0}/approve", json={"reason": "audit", "zero_cost_reason": "Barang sampel hibah, HPP nol"}, headers=H)
        s = r.json()
        adj = (s.get("items") or [{}])[0].get("adjustment") or {}
        check("FN-14", "dengan zero_cost_reason → approved, alasan tersimpan", r.status_code == 200 and adj.get("zero_cost_reason"), (r.status_code, adj))

    async def wm08():
        p = await mk_prod(4)
        await mk_roll(p["id"], 41, 10, "binC", "available")
        await mk_roll(p["id"], 42, 30, "binC", "picked", reserved_ref={"type": "sales_order", "id": f"{T}_so"})
        sid = await session("picked")
        it = (await add(sid, p["id"], "binC")).json()
        check("WM-08", "expected mencakup picked (40)", it.get("expected_qty") == 40, it.get("expected_qty"))
        await count(sid, it["id"], 0)
        await c.post(f"/api/cycle-count/sessions/{sid}/submit", headers=H)
        r = await c.post(f"/api/cycle-count/sessions/{sid}/approve", json={"reason": "audit"}, headers=H)
        s = r.json()
        adj = (s.get("items") or [{}])[0].get("adjustment") or {}
        left = sum(x["length_remaining"] for x in await db.inventory_rolls.find({"product_id": p["id"]}, {"_id": 0}).to_list(10))
        check("WM-08", "kurang 40 diterapkan penuh (applied == requested) termasuk roll picked", r.status_code == 200
              and adj.get("applied") == -40 and adj.get("unresolved") == 0 and left == 0, (r.status_code, adj, left))
        check("WM-08", "detail requested/applied/unresolved per baris tersimpan", {"requested", "applied", "unresolved"} <= set(adj))
        # stok bergerak keluar scope setelah submit → 409, tidak ada mutasi
        p2 = await mk_prod(5)
        await mk_roll(p2["id"], 51, 20, "binD")
        sid2 = await session("drift")
        it2 = (await add(sid2, p2["id"], "binD")).json()
        await count(sid2, it2["id"], 15)
        await c.post(f"/api/cycle-count/sessions/{sid2}/submit", headers=H)
        await db.inventory_rolls.update_one({"id": f"{T}_r51"}, {"$set": {"status": "in_transit_sales"}})
        r = await c.post(f"/api/cycle-count/sessions/{sid2}/approve", json={"reason": "audit"}, headers=H)
        roll = await db.inventory_rolls.find_one({"id": f"{T}_r51"}, {"_id": 0})
        st = await db.cycle_count_sessions.find_one({"id": sid2}, {"_id": 0, "status": 1})
        check("WM-08", "stok eligible tak cukup → 409 tanpa approve palsu & tanpa mutasi", r.status_code == 409
              and roll["length_remaining"] == 20 and st["status"] == "submitted", (r.status_code, roll["length_remaining"], st))

    async def rf17():
        from services import cycle_count_service as ccs, rfid_service as rs, rfid_print_service as rps
        wh = f"{T}_wh"
        await db.warehouses.insert_one({"id": wh, "name": "Audit P10 WH", "entity_id": A, "owner_entity_id": A})
        p = await mk_prod(6)
        for n, st in ((61, "available"), (62, "wip"), (63, "damaged"), (64, "in_transit_sales")):
            await mk_roll(p["id"], n, 10, status=st, wh=wh)
        for n in (61, 62, 64):
            await rs.encode_tag(f"{T}_r{n}", [A])
        await mk_roll(p["id"], 65, 10, status="available", wh=wh)   # tanpa tag
        sess = await ccs.start(wh, [A], "audit")
        exp = {e["roll_id"] for e in sess["expected"]}
        check("RF-17", "roll WIP ber-tag ikut expected; transit sales TIDAK", f"{T}_r62" in exp and f"{T}_r64" not in exp, exp)
        await rps.scan_session(sess["id"], [e["epc"] for e in sess["expected"]] + [rs.generate_epc()], [A], ["cycle_count"])
        cc = await ccs.complete(sess["id"], "audit", [A])
        check("RF-17", "semua expected terbaca + 1 EPC asing → akurasi < 100%", cc["accuracy_pct"] < 100, cc["accuracy_pct"])
        check("RF-17", "metrik terpisah: coverage tag, recall, extra rate, unresolved",
              cc.get("eligible_count") == 4 and cc.get("untagged_count") == 2 and cc.get("read_recall_pct") == 100
              and cc.get("extra_rate_pct", 0) > 0 and cc.get("unresolved_count") == 3,
              {k: cc.get(k) for k in ("eligible_count", "untagged_count", "tag_coverage_pct", "read_recall_pct", "extra_rate_pct", "unresolved_count")})

    for fid, fn in [("WM-07", wm07), ("FN-14", fn14_surplus), ("WM-08", wm08), ("RF-17", rf17)]:
        await guarded(fid, fn())

    sids = [s["id"] for s in await db.cycle_count_sessions.find({"name": {"$regex": f"^{T}"}}, {"_id": 0, "id": 1}).to_list(50)]
    for sid in sids:
        await db.journal_entries.delete_many({"source_type": "cycle_count_variance", "source_id": {"$regex": f"^{sid}"}})
    await db.cycle_count_sessions.delete_many({"id": {"$in": sids}})
    pids = [f"{T}_p{n}" for n in range(1, 8)]
    await db.inventory_movements.delete_many({"product_id": {"$in": pids}})
    await db.inventory_balances.delete_many({"product_id": {"$in": pids}})
    await db.rfid_tags.delete_many({"roll_id": {"$regex": f"^{T}"}})
    await db.rfid_verify_sessions.delete_many({"warehouse_id": f"{T}_wh"})
    await db.rfid_cycle_counts.delete_many({"warehouse_id": f"{T}_wh"})
    await db.inventory_rolls.delete_many({"product_id": {"$in": pids}})
    await db.inventory_lots.delete_many({"product_id": {"$in": pids}})
    await db.products.delete_many({"id": {"$in": pids}})
    await db.warehouses.delete_many({"id": f"{T}_wh"})
    await c.aclose()

    for r in results:
        print(("PASS " if r["pass"] else "FAIL ") + f"[{r['id']}] {r['invariant']}" + ("" if r["pass"] else f" :: {r['detail']}"))
    print(json.dumps({"pass": sum(r["pass"] for r in results), "fail": sum(not r["pass"] for r in results)}))


if __name__ == "__main__":
    asyncio.run(main())
