"""P16b — kasus planned: AUTH-04 (entitas diarsipkan saat operasi berjalan), MASTER-01/05
(master yang masih dipakai: nonaktif produk/supplier/UOM tidak merusak dokumen & tidak bisa dipakai baru).

Usage: cd /app/backend && python ../audit/iterations/2026-10-09-P16-close-coverage/repro_p16b.py
Data uji berprefiks TEST_P16B; semua dokumen master/entitas di-restore dari snapshot di akhir.
"""
import asyncio
import json
import sys
import uuid

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
T = f"TEST_P16B_{uuid.uuid4().hex[:6]}"
results = []
snap = {}
created = {"orders": [], "pos": []}


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def login(c, email, ent="ent_ksc", pwd="demo12345"):
    r = await c.post("/api/auth/login", json={"email": email, "password": pwd})
    return {"Authorization": f"Bearer {r.json().get('token')}", "X-Entity-Id": ent}


async def keep(db, coll, q):
    for d in await db[coll].find(q, {"_id": 0}).to_list(None):
        snap.setdefault((coll, d["id"]), d)


# ── AUTH-04 ────────────────────────────────────────────────────────────────
async def auth04(c, h, db):
    ent = "ent_kanda"
    so = await db.sales_orders.find_one({"entity_id": ent, "status": {"$nin": ["shipped", "done", "cancelled"]}}, {"_id": 0})
    await keep(db, "business_entities", {"id": ent})
    await keep(db, "sales_orders", {"id": so["id"]})
    hk = {**h, "X-Entity-Id": ent}
    plain = await c.delete(f"/api/entities/{ent}", headers=h)
    e = await db.business_entities.find_one({"id": ent}, {"_id": 0, "status": 1})
    check("AUTH-04", "arsip entitas yang masih punya operasi berjalan tanpa force → 409 + daftar blocker, status tetap aktif",
          plain.status_code == 409 and e["status"] == "active" and "blockers" in plain.text, f"{plain.status_code} {plain.text[:160]}")
    noreason = await c.delete(f"/api/entities/{ent}", params={"force": "true"}, headers=h)
    check("AUTH-04", "force tanpa alasan ditolak 400", noreason.status_code == 400, noreason.status_code)
    arc = await c.delete(f"/api/entities/{ent}", params={"force": "true", "reason": f"{T} uji arsip"}, headers=h)
    check("AUTH-04", "force + alasan (admin) → archived", arc.status_code == 200, f"{arc.status_code} {arc.text[:120]}")
    w_hdr = await c.post(f"/api/sales-orders/{so['id']}/cancel", json={}, headers=hk)
    w_ksc = await c.post(f"/api/sales-orders/{so['id']}/cancel", json={}, headers={**h, "X-Entity-Id": "ent_ksc"})
    w_all = await c.post(f"/api/sales-orders/{so['id']}/cancel", json={}, headers={**h, "X-Entity-Id": "all"})
    so2 = await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0, "status": 1})
    check("AUTH-04", "dokumen berjalan milik entitas terarsip tidak bisa diubah lewat konteks entitas itu, entitas lain, maupun 'all'",
          all(r.status_code in (403, 404, 409) for r in (w_hdr, w_ksc, w_all)) and so2["status"] == so["status"],
          f"hdr={w_hdr.status_code} ksc={w_ksc.status_code} all={w_all.status_code} status={so2['status']} {w_all.text[:120]}")
    rd = await c.get("/api/entities", params={"status": "archived"}, headers=h)
    check("AUTH-04", "entitas terarsip tetap terbaca admin lewat ?status=archived",
          rd.status_code == 200 and ent in [x.get("id") for x in rd.json()], rd.status_code)
    re_ = await c.post(f"/api/entities/{ent}/reactivate", json={}, headers=h)
    ok_after = await c.patch(f"/api/sales-orders/{so['id']}", json={"data": {"notes": f"{T} sesudah aktif"}}, headers=hk)
    check("AUTH-04", "aktifkan kembali → tulis ke dokumennya pulih", re_.status_code == 200 and ok_after.status_code == 200,
          f"{re_.status_code}/{ok_after.status_code} {ok_after.text[:100]}")


# ── MASTER-01/05 ───────────────────────────────────────────────────────────
async def master(c, h, db):
    pid = "prod_ulos_batak"
    await keep(db, "products", {"id": pid})
    rolls0 = await db.inventory_rolls.find({"product_id": pid}, {"_id": 0, "id": 1, "status": 1, "length_remaining": 1}).to_list(None)
    d = await c.delete(f"/api/products/{pid}", headers=h)
    so = await c.post("/api/sales-orders", json={"customer_id": "cust_toko_kain", "shipping_address_id": "addr_001",
                                                 "items": [{"product_id": pid, "quantity": 1, "unit": "yard"}]}, headers=h)
    if so.status_code == 200:
        created["orders"].append(so.json()["id"])
    sup = await db.suppliers.find_one({"status": "active", "partner_kind": {"$ne": "entity"}, "group_entity_id": {"$in": [None, ""]}}, {"_id": 0})
    po = await c.post("/api/purchase-orders", json={"supplier_id": sup["id"], "warehouse_id": "wh_jakarta", "notes": T,
                                                    "items": [{"product_id": pid, "quantity": 10, "unit": "yard", "price": 1000, "expected_grade": "A"}]}, headers=h)
    if po.status_code == 200:
        created["pos"].append(po.json().get("id"))
    rolls1 = await db.inventory_rolls.find({"product_id": pid}, {"_id": 0, "id": 1, "status": 1, "length_remaining": 1}).to_list(None)
    lst = (await c.get("/api/products", headers=h)).json()
    items = lst.get("items", lst) if isinstance(lst, dict) else lst
    check("MASTER-05", "produk dinonaktifkan: soft (status inactive), stok/roll tidak berubah", d.status_code == 200 and rolls0 == rolls1, d.status_code)
    check("MASTER-05", "produk nonaktif ditolak untuk SO baru", so.status_code == 400, f"{so.status_code} {so.text[:120]}")
    check("MASTER-05", "produk nonaktif ditolak untuk PO baru", po.status_code in (400, 409), f"{po.status_code} {po.text[:150]}")
    # supplier nonaktif
    await keep(db, "suppliers", {"id": sup["id"]})
    ds = await c.delete(f"/api/suppliers/{sup['id']}", headers=h)
    po2 = await c.post("/api/purchase-orders", json={"supplier_id": sup["id"], "warehouse_id": "wh_jakarta", "notes": T,
                                                     "items": [{"product_id": "prod_tenun_ikat", "quantity": 10, "unit": "yard", "price": 1000, "expected_grade": "A"}]}, headers=h)
    if po2.status_code == 200:
        created["pos"].append(po2.json().get("id"))
    open_po = await db.purchase_orders.count_documents({"supplier_id": sup["id"]})
    check("MASTER-05", "supplier nonaktif ditolak untuk PO baru; PO lamanya tetap ada", ds.status_code == 200 and po2.status_code in (400, 409),
          f"del={ds.status_code} po={po2.status_code} {po2.text[:150]} lama={open_po}")
    # UOM dipakai
    u = await db.uoms.find_one({"code": {"$in": ["yard", "YARD", "yd"]}}, {"_id": 0}) or await db.uoms.find_one({}, {"_id": 0})
    await keep(db, "uoms", {"id": u["id"]})
    du = await c.delete(f"/api/uoms/{u['id']}", headers=h)
    u2 = await db.uoms.find_one({"id": u["id"]}, {"_id": 0, "status": 1})
    check("MASTER-01", "UOM yang dipakai dokumen tidak bisa dinonaktifkan (409), status tetap", du.status_code == 409 and u2.get("status") != "inactive",
          f"{du.status_code} {du.text[:120]}")
    hs = await login(c, "sales@kainnusantara.id")
    ds2 = await c.delete(f"/api/products/prod_tenun_ikat", headers=hs)
    check("MASTER-01", "peran sales tidak bisa menonaktifkan produk (403)", ds2.status_code == 403, ds2.status_code)


async def cleanup(db):
    for (coll, _id), doc in snap.items():
        await db[coll].replace_one({"id": _id}, doc, upsert=True)
    from services import entity_lifecycle_service as lc
    lc.invalidate_status_cache()
    lc.invalidate_entity_code("ent_kanda")
    oids = [o for o in created["orders"] if o]
    if oids:
        from services.roll_service import release_order_rolls
        for o in oids:
            await release_order_rolls(o)
        await db.sales_orders.delete_many({"id": {"$in": oids}})
    await db.purchase_orders.delete_many({"id": {"$in": [p for p in created["pos"] if p]}})
    await db.wms_tasks.delete_many({"po_id": {"$in": [p for p in created["pos"] if p]}})
    await db.doc_refs.delete_many({"$or": [{"from_id": {"$in": created["pos"]}}, {"to_id": {"$in": created["pos"]}}]})
    await db.audit_logs.delete_many({"$or": [{"entity_id": {"$in": oids + created["pos"]}}, {"reason": {"$regex": T}},
                                             {"details.reason": {"$regex": T}}]})


async def main():
    import httpx
    from db import db
    async with httpx.AsyncClient(base_url="http://localhost:8001", timeout=120) as c:
        h = await login(c, "admin@kainnusantara.id")
        try:
            for name, fn in (("AUTH-04", lambda: auth04(c, h, db)), ("MASTER", lambda: master(c, h, db))):
                try:
                    await fn()
                except Exception as exc:  # noqa: BLE001
                    import traceback
                    traceback.print_exc()
                    check(name, "eksekusi skenario", False, repr(exc)[:200])
        finally:
            await cleanup(db)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
