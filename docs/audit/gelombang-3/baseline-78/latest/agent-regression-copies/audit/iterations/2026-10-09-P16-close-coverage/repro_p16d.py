"""P16d — COMM-03: harga khusus — persetujuan, kedaluwarsa, cakupan pesanan vs standing.

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-09-P16-close-coverage/repro_p16d.py
Data uji TEST_P16D; SO/approval dihapus & reservasi dilepas di akhir.
"""
import asyncio
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
T = f"TEST_P16D_{uuid.uuid4().hex[:6]}"
results = []
orders, pras = [], []
CUST, ADDR, PID = "cust_toko_kain", "addr_001", "prod_tenun_ikat"


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def so(c, h, qty=1, appr=""):
    item = {"product_id": PID, "quantity": qty, "unit": "yard", **({"price_approval_id": appr} if appr else {})}
    r = await c.post("/api/sales-orders", json={"customer_id": CUST, "shipping_address_id": ADDR, "items": [item]}, headers=h)
    if r.status_code == 200:
        orders.append(r.json()["id"])
    return r


async def run(c, h, db):
    a = (await so(c, h, 2)).json()
    normal = a["items"][0]["price"]
    req = round(normal * 0.9, 2)
    rq = await c.post(f"/api/sales-orders/{a['id']}/request-special-price",
                      json={"item_index": 0, "requested_price": req, "reason": f"{T} nego"}, headers=h)
    a2 = await db.sales_orders.find_one({"id": a["id"]}, {"_id": 0})
    pa = next(p for p in a2["pending_approvals"] if p.get("type") == "special_price")
    pras.append(pa.get("ref_id"))
    hm = h
    dec = await c.post(f"/api/sales-orders/{a['id']}/approvals/{pa['id']}/decide", json={"decision": "approve", "notes": T}, headers=hm)
    a3 = await db.sales_orders.find_one({"id": a["id"]}, {"_id": 0})
    it = a3["items"][0]
    check("COMM-03", "harga khusus disetujui → harga baris SO = harga khusus & total dihitung ulang",
          rq.status_code == 200 and dec.status_code == 200 and it["price"] == req
          and round(float(a3["net_subtotal"]), 2) == round(req * 2, 2), f"{rq.status_code}/{dec.status_code} price={it['price']} net={a3['net_subtotal']}")
    reuse = await so(c, h, 2, appr=pa.get("ref_id"))
    check("COMM-03", "harga khusus lingkup pesanan TIDAK bisa dipakai SO lain lewat price_approval_id (400)",
          reuse.status_code == 400, f"{reuse.status_code} {reuse.text[:150]}")
    eff = await c.get("/api/price-approvals/effective", params={"customer_id": CUST, "product_id": PID, "quantity": 2}, headers=h)
    eff_j = eff.json() if eff.status_code == 200 else {}
    check("COMM-03", "harga khusus lingkup pesanan tidak muncul sebagai harga efektif standing",
          eff.status_code in (200, 404) and (eff_j or {}).get("id") != pa.get("ref_id")
          and (eff_j or {}).get("price_approval_id") != pa.get("ref_id"), f"{eff.status_code} {eff.text[:150]}")
    # standing kedaluwarsa & min qty
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    fut = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    base = {"customer_id": CUST, "product_id": PID, "entity_id": "ent_ksc", "status": "approved", "scope": "standing",
            "normal_price": normal, "requested_price": round(normal * 0.8, 2), "reason": T, "decided_at": "2026-10-01T00:00:00+00:00",
            "created_at": "2026-10-01T00:00:00+00:00"}
    exp_id, ok_id = f"pra_{T.lower()}_exp", f"pra_{T.lower()}_ok"
    await db.price_approvals.insert_many([{**base, "id": exp_id, "valid_until": past, "min_quantity": 0},
                                          {**base, "id": ok_id, "valid_until": fut, "min_quantity": 5}])
    pras.extend([exp_id, ok_id])
    e1 = await so(c, h, 6, appr=exp_id)
    e2 = await so(c, h, 2, appr=ok_id)
    e3 = await so(c, h, 6, appr=ok_id)
    check("COMM-03", "standing kedaluwarsa ditolak; di bawah min qty ditolak; berlaku & qty cukup → harga khusus",
          e1.status_code == 400 and e2.status_code == 400 and e3.status_code == 200
          and e3.json()["items"][0]["price"] == base["requested_price"], f"{e1.status_code}/{e2.status_code}/{e3.status_code}")


async def cleanup(db):
    from services.roll_service import release_order_rolls
    for o in orders:
        await release_order_rolls(o)
    await db.sales_orders.delete_many({"id": {"$in": orders}})
    await db.price_approvals.delete_many({"id": {"$in": [p for p in pras if p]}})
    await db.credit_overrides.delete_many({"consumed_order_id": {"$in": orders}})
    await db.audit_logs.delete_many({"entity_id": {"$in": orders + pras}})


async def main():
    import httpx
    from db import db
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8009", timeout=120) as c:
        r = await c.post("/api/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
        h = {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}
        try:
            await run(c, h, db)
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check("COMM-03", "eksekusi skenario", False, repr(exc)[:200])
        finally:
            await cleanup(db)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
