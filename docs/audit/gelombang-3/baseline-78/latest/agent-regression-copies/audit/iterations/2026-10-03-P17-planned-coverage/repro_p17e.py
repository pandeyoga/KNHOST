"""P17e — COMM-05: edit/hapus/impor harga pelanggan BERSAMAAN menjaga satu harga kanonik.

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-03-P17-planned-coverage/repro_p17e.py
Record `customer_prices` + audit buatan skrip dibuang di akhir.
"""
import asyncio
import json
import sys
import uuid

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
from poc_stock_guard import purge_new_ids, snapshot_new_ids  # noqa: E402

T = f"TEST_P17E_{uuid.uuid4().hex[:6]}"
ENT = "ent_ksc"
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def current(c, h, db, cust, pid):
    q = (await c.get("/api/customer-prices/quote", headers=h, params={"customer_id": cust, "product_ids": pid,
                                                                      "include_special": "false"})).json()
    rows = await db.customer_prices.find({"customer_id": cust, "product_id": pid, "status": "active",
                                          "note": {"$regex": T}}, {"_id": 0}).to_list(100)
    from services import pricelist_service as ep
    from core_utils import now_iso
    live = ep._active_candidates(rows, now_iso())  # noqa: SLF001
    return q["prices"].get(pid, {}), live


async def run(c, h, db):
    cust = (await db.customers.find_one({"entity_id": ENT, "status": {"$ne": "inactive"}}, {"_id": 0, "id": 1}))["id"]
    prod = await db.products.find_one({"sku": {"$gt": ""}, "price": {"$gt": 0}}, {"_id": 0})
    pid, base = prod["id"], float(prod.get("price") or 100000)
    prices = [round(base * 3 + i * 1000, 2) for i in range(6)]
    day = "2026-10-03"
    reqs = [c.post("/api/customer-prices", headers=h, json={"customer_id": cust, "product_id": pid, "sell_price": p,
                                                           "valid_from": day, "note": f"{T} manual {i}"})
            for i, p in enumerate(prices[:5])]
    reqs.append(c.post("/api/customer-prices/import", headers=h, json={
        "customer_id": cust, "rows": [{"sku": prod["sku"], "sell_price": prices[5], "valid_from": day, "note": f"{T} impor"}]}))
    rs = await asyncio.gather(*reqs)
    codes = [r.status_code for r in rs]
    eff, live = await current(c, h, db, cust, pid)
    newest = max(await db.customer_prices.find({"customer_id": cust, "product_id": pid, "note": {"$regex": T}},
                                               {"_id": 0}).to_list(50), key=lambda r: r["created_at"])
    check("COMM-05", "6 penetapan harga bersamaan (5 manual + 1 impor) semuanya tersimpan", codes == [200] * 6, codes)
    check("COMM-05", "tepat SATU record harga yang berlaku sesudah balapan", len(live) == 1, [(r["sell_price"], r.get("valid_until")) for r in live])
    check("COMM-05", "harga efektif = record terakhir dibuat (sumber kanonik)",
          eff.get("source") == "customer" and eff.get("record_id") == newest["id"], (eff.get("price"), eff.get("record_id"), newest["id"]))
    # patch vs hapus bersamaan pada record yang berlaku
    tgt = newest["id"]
    rp, rd = await asyncio.gather(
        c.patch(f"/api/customer-prices/{tgt}", headers=h, json={"sell_price": round(base * 4, 2)}),
        c.delete(f"/api/customer-prices/{tgt}", headers=h))
    rec = await db.customer_prices.find_one({"id": tgt}, {"_id": 0})
    check("COMM-05", "hapus menang atas ubah bersamaan: record nonaktif", rec["status"] == "inactive" and rd.status_code == 200,
          (rp.status_code, rd.status_code, rec["status"]))
    late = await c.patch(f"/api/customer-prices/{tgt}", headers=h, json={"sell_price": round(base * 5, 2)})
    rec2 = await db.customer_prices.find_one({"id": tgt}, {"_id": 0})
    check("COMM-05", "ubah record yang sudah dihapus ditolak (bukan menulis diam-diam)",
          late.status_code in (400, 409) and rec2["sell_price"] == rec["sell_price"], (late.status_code, rec2["sell_price"]))
    eff2, live2 = await current(c, h, db, cust, pid)
    check("COMM-05", "sesudah hapus, harga efektif bukan record yang dihapus",
          eff2.get("record_id") != tgt and all(r["id"] != tgt for r in live2), (eff2.get("source"), eff2.get("record_id")))
    # dua hapus bersamaan idempoten
    other = next((r["id"] for r in await db.customer_prices.find({"customer_id": cust, "product_id": pid, "note": {"$regex": T},
                                                                  "status": "active"}, {"_id": 0}).to_list(50)), None)
    if other:
        d1, d2 = await asyncio.gather(c.delete(f"/api/customer-prices/{other}", headers=h),
                                      c.delete(f"/api/customer-prices/{other}", headers=h))
        n = await db.audit_logs.count_documents({"action": "customer_price_deactivated", "entity_id": other})
        check("COMM-05", "hapus ganda bersamaan: satu efek (satu jejak audit nonaktif)", n == 1, (d1.status_code, d2.status_code, n))


async def main():
    import httpx
    from db import db
    ids = snapshot_new_ids(["customer_prices", "audit_logs", "price_approvals", "notifications"])
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8009", timeout=120) as c:
        r = await c.post("/api/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
        h = {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}
        try:
            await run(c, h, db)
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check("COMM-05", "eksekusi skenario", False, repr(exc)[:200])
        finally:
            purge_new_ids(ids, verbose=False)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
