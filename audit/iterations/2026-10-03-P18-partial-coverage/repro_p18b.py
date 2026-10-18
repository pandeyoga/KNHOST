"""P18b — MASTER-01..05 + COMM-01: master ber-referensi, isolasi & lapisan setting antar-PT,
alias/satuan tak dikenal, merge pelanggan duplikat.

Usage: cd /app/backend && python ../audit/iterations/2026-10-03-P18-partial-coverage/repro_p18b.py
Self-clean: snapshot dokumen master yang diubah → dipulihkan; dokumen baru dihapus (purge_new_ids).
"""
import asyncio
import json
import sys
import uuid

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402

T = f"TEST_P18B_{uuid.uuid4().hex[:6]}"
ENT, OTHER = "ent_ksc", "ent_kanda"
results = []
NEW = ["customers", "sales_orders", "purchase_orders", "products", "audit_logs", "notifications", "config_values",
       "payment_terms", "expense_categories", "document_templates", "sales_return_policies", "incentive_rates",
       "approval_rules", "product_lines", "process_stages", "sample_types", "complaint_reasons", "length_reservations",
       "customer_prices", "price_approvals", "inventory_movements", "wms_tasks", "group_partners"]


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def login(c, email, ent=ENT):
    r = await c.post("/api/auth/login", json={"email": email, "password": "demo12345"})
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ent}


async def master01(c, h, db):
    u = await db.uoms.find_one({"code": "YRD"}, {"_id": 0})
    r1 = await c.patch(f"/api/uoms/{u['id']}", json={"data": {"code": "YDX"}}, headers=h)
    r2 = await c.patch(f"/api/uoms/{u['id']}", json={"data": {"factor_to_base": 0.95}}, headers=h)
    r3 = await c.patch(f"/api/uoms/{u['id']}", json={"data": {"aliases": ["yd"]}}, headers=h)
    r4 = await c.patch(f"/api/uoms/{u['id']}", json={"data": {"name": "Yard (internasional)"}}, headers=h)
    after = await db.uoms.find_one({"id": u["id"]}, {"_id": 0})
    check("MASTER-01", "UOM terpakai: ganti kode/faktor/hapus alias terpakai ('yard') → 409; ganti nama → 200",
          (r1.status_code, r2.status_code, r3.status_code, r4.status_code) == (409, 409, 409, 200)
          and after["code"] == "YRD" and after["factor_to_base"] == 0.9144, (r1.status_code, r2.status_code, r3.status_code, r4.status_code, r1.text[:120]))
    await db.uoms.replace_one({"id": u["id"]}, u)
    p = await db.products.find_one({"id": "prod_endek_bali"}, {"_id": 0})
    r = await c.post("/api/sales-orders", json={"customer_id": "cust_toko_kain", "shipping_address_id": "addr_001",
                                                "items": [{"product_id": p["id"], "quantity": 2, "unit": "yard"}]}, headers=h)
    so = r.json()
    rn = await c.patch(f"/api/products/{p['id']}", json={"data": {"name": f"{T} Endek", "price": float(p.get("price") or 0) + 1000}}, headers=h)
    rs = await c.patch(f"/api/products/{p['id']}", json={"data": {"sku": f"{T}-SKU"}}, headers=h)
    rb = await c.patch(f"/api/products/{p['id']}", json={"data": {"base_unit": "kg"}}, headers=h)
    so2 = await db.sales_orders.find_one({"id": so.get("id")}, {"_id": 0, "items": 1})
    check("MASTER-01", "produk dipakai SO: ubah nama/harga 200 tapi baris SO tetap snapshot; ganti SKU 409; base_unit beda induk 400",
          r.status_code == 200 and rn.status_code == 200 and rs.status_code == 409 and rb.status_code in (400, 409)
          and so2["items"][0]["product_name"] == p["name"] and float(so2["items"][0]["price"]) == float(so["items"][0]["price"]),
          (r.status_code, rn.status_code, rs.status_code, rb.status_code, so2["items"][0].get("product_name")))
    await db.products.replace_one({"id": p["id"]}, p)
    if so.get("id"):
        await c.post(f"/api/sales-orders/{so['id']}/cancel", json={"reason": f"{T} batal"}, headers=h)
    tpl = await db.product_templates.find_one({"id": p.get("template_id")}, {"_id": 0})
    rt = await c.patch(f"/api/product-templates/{tpl['id']}", json={"base_unit": "kg"}, headers=h)
    check("MASTER-01", "induk produk yang sudah punya SKU ber-stok: ganti base_unit ditolak",
          rt.status_code in (400, 409) and (await db.product_templates.find_one({"id": tpl["id"]}))["base_unit"] == tpl["base_unit"], rt.status_code)
    sup = await db.suppliers.find_one({"entity_id": ENT, "status": "active"}, {"_id": 0})
    po = await db.purchase_orders.find_one({"supplier_id": sup["id"]}, {"_id": 0, "id": 1, "supplier_name": 1})
    ru = await c.patch(f"/api/suppliers/{sup['id']}", json={"data": {"name": f"{T} Supplier"}}, headers=h)
    po2 = await db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0, "supplier_name": 1}) if po else None
    check("MASTER-01", "supplier ber-PO: ganti nama 200, PO lama mempertahankan snapshot nama supplier",
          ru.status_code == 200 and po and po2["supplier_name"] == po["supplier_name"], (ru.status_code, po and po["supplier_name"]))
    await db.suppliers.replace_one({"id": sup["id"]}, sup)


async def master02_03(c, h, hk, db):
    from services import entity_master_service as ems
    tested, bad = [], []
    for kind, s in ems.MASTERS.items():
        if not s.manage:
            continue
        g = await db[s.collection].find_one({"entity_id": {"$in": ["all", "", None]}, "status": {"$ne": "inactive"}, "active": {"$ne": False}}, {"_id": 0})
        if not g:
            continue
        key = g.get(s.key_field)
        ov = await c.post(f"/api/entity-masters/{kind}/{g['id']}/override", headers=h)
        if ov.status_code != 200:
            bad.append((kind, "override", ov.status_code, ov.text[:80]))
            continue
        row = ov.json()
        pt = await c.patch(f"/api/entity-masters/{kind}/{row['id']}", json={"data": {s.name_field: f"{T} {kind}"}}, headers=h)
        eff = lambda e: ems.effective_rows(kind, e)  # noqa: E731
        ksc = next((r for r in await eff(ENT) if r.get(s.key_field) == key), {})
        kan = next((r for r in await eff(OTHER) if r.get(s.key_field) == key), {})
        glob = await db[s.collection].find_one({"id": g["id"]}, {"_id": 0})
        ok = pt.status_code == 200 and ksc.get(s.name_field) == f"{T} {kind}" and kan.get(s.name_field) == g.get(s.name_field) \
            and glob.get(s.name_field) == g.get(s.name_field)
        rv = await c.delete(f"/api/entity-masters/{kind}/{row['id']}", headers=h)
        ksc2 = next((r for r in await eff(ENT) if r.get(s.key_field) == key), {})
        ok = ok and rv.status_code == 200 and ksc2.get(s.name_field) == g.get(s.name_field)
        (tested if ok else bad).append(kind if ok else (kind, pt.status_code, ksc.get(s.name_field), kan.get(s.name_field), rv.status_code))
    check("MASTER-02", "master berlapis (semua jenis): override & ubah di KSC tidak mengubah Kanda maupun baris global",
          tested and not bad, {"lulus": tested, "gagal": bad})
    check("MASTER-03", "master berlapis: lepas override (DELETE) → KSC kembali ke nilai global", tested and not bad, tested)
    # config resolver: global → entity → clear, beberapa kunci beragam tipe
    import config_registry as reg
    cand = [e for e in reg.all_entries() if "entity" in (e.get("scopes") or ()) and e.get("type") in ("int", "decimal", "bool")
            and e.get("status", "active") not in ("not_used",)][:6]
    keys = [e["key"] for e in cand]
    good, fail = [], []
    for k in keys:
        e = reg.get(k)
        base = (await c.get("/api/config/explain", params={"key": k, "entity_id": ENT}, headers=h)).json()
        v0 = base.get("value")
        if e["type"] == "bool":
            vg, ve = (not v0), v0
        elif e["type"] == "text":
            vg, ve = f"{v0}", f"{v0}"
            continue
        else:
            vg, ve = (v0 or 0) + 1, (v0 or 0) + 2
        put = lambda val, st, sid="": c.put("/api/config/values", json={"items": [{"key": k, "value": val, "scope_type": st, "scope_id": sid, "reason": T}]}, headers=h)  # noqa: E731
        ex = lambda ent: c.get("/api/config/explain", params={"key": k, "entity_id": ent}, headers=h)  # noqa: E731
        a = await put(vg, "global")
        b = await put(ve, "entity", ENT)
        k1, n1 = (await ex(ENT)).json(), (await ex(OTHER)).json()
        cl = await c.post("/api/config/values/clear", json={"key": k, "scope_type": "entity", "scope_id": ENT, "reason": T}, headers=h)
        k2 = (await ex(ENT)).json()
        cl2 = await c.post("/api/config/values/clear", json={"key": k, "scope_type": "global", "reason": T}, headers=h)
        back = await put(v0, "global")
        k3 = (await ex(ENT)).json()
        ok = a.status_code == b.status_code == cl.status_code == back.status_code == 200 and cl2.status_code == 400 \
            and k1.get("value") == ve and n1.get("value") == vg and k2.get("value") == vg and k3.get("value") == v0
        if a.status_code == 400 and b.status_code == 400:
            continue  # nilai uji di luar rentang sah (mis. bulan 13) — bukan kasus lapisan
        (good if ok else fail).append(k if ok else (k, a.status_code, b.status_code, cl.status_code, cl2.status_code, k1.get("value"), n1.get("value"), k2.get("value"), k3.get("value"), v0))
    check("MASTER-03", "config global → override KSC (Kanda tetap global) → clear KSC = ikut global; clear lapisan Global ditolak 400", good and not fail,
          {"lulus": good, "gagal": fail})
    check("MASTER-02", "config override KSC tidak terbaca di Kanda", good and not fail, good)


async def master04(c, h, db):
    n_so, n_po, n_pr = (await db.sales_orders.count_documents({}), await db.purchase_orders.count_documents({}),
                        await db.products.count_documents({}))
    so = await c.post("/api/sales-orders", json={"customer_id": "cust_toko_kain", "shipping_address_id": "addr_001",
                                                 "items": [{"product_id": "prod_endek_bali", "quantity": 2, "unit": "parsec"}]}, headers=h)
    sup = await db.suppliers.find_one({"entity_id": ENT, "status": "active"}, {"_id": 0, "id": 1})
    po = await c.post("/api/purchase-orders", json={"supplier_id": sup["id"], "warehouse_id": "wh_jakarta", "items": [
        {"product_id": "prod_endek_bali", "quantity": 10, "unit": "jengkal", "price": 1000, "expected_grade": "A"}]}, headers=h)
    pt = await c.post("/api/purchase-orders", json={"supplier_id": sup["id"], "warehouse_id": "wh_jakarta", "payment_term_code": "NET999X",
                                                    "items": [{"product_id": "prod_endek_bali", "quantity": 10, "unit": "yard", "price": 1000, "expected_grade": "A"}]}, headers=h)
    tpl = await db.product_templates.find_one({"status": "active"}, {"_id": 0, "id": 1})
    pr = await c.post("/api/products", json={"name": f"{T} produk", "sku": f"{T}-X", "template_id": tpl["id"], "base_unit": "furlong", "price": 1000}, headers=h)
    alias = await c.post("/api/sales-orders", json={"customer_id": "cust_toko_kain", "shipping_address_id": "addr_001",
                                                    "items": [{"product_id": "prod_endek_bali", "quantity": 1, "unit": "yd"}]}, headers=h)
    aj = alias.json() if alias.status_code == 200 else {}
    check("MASTER-04", "satuan tak dikenal di SO/PO, termin tak dikenal, base_unit produk tak dikenal → 4xx tanpa dokumen baru",
          all(400 <= x.status_code < 500 for x in (so, po, pt, pr))
          and (n_so + (1 if aj.get("id") else 0), n_po, n_pr) == (await db.sales_orders.count_documents({}),
                                                                  await db.purchase_orders.count_documents({}), await db.products.count_documents({})),
          {"so": (so.status_code, so.text[:90]), "po": (po.status_code, po.text[:90]), "term": (pt.status_code, pt.text[:90]), "prod": (pr.status_code, pr.text[:90])})
    check("MASTER-04", "alias sah 'yd' diterima & dihitung setara yard (base_quantity = qty)",
          alias.status_code == 200 and float(aj["items"][0].get("base_quantity") or 0) == 1.0, (alias.status_code, aj.get("items", [{}])[0].get("base_quantity")))
    if aj.get("id"):
        await c.post(f"/api/sales-orders/{aj['id']}/cancel", json={"reason": f"{T} batal"}, headers=h)


async def master05(c, h, hs, db):
    mk = lambda nm, phone: c.post("/api/customers", json={"name": nm, "pic_name": "Bu Sari", "phone": phone, "city": "Bandung", "type": "Retailer", "address": f"Jl. {nm} 1", "assigned_sales_id": "user_sales_01",  # noqa: E731
                                                         "addresses": [{"label": "Toko", "address": f"Jl. {nm} 1", "city": "Bandung"}]}, headers=h)
    a, b = (await mk(f"{T} Toko Maju", "081234560001")).json(), (await mk(f"{T} Toko Maju Dup", "081234560002")).json()
    addr_b = ((b.get("addresses") or [{}])[0]).get("id", "")
    so = await c.post("/api/sales-orders", json={"customer_id": b["id"], "shipping_address_id": addr_b, "items": [{"product_id": "prod_endek_bali", "quantity": 1, "unit": "yard"}]}, headers=h)
    sj = so.json() if so.status_code == 200 else {}
    check("MASTER-05", "prasyarat: SO dibuat untuk pelanggan duplikat", bool(sj.get("id")), (so.status_code, so.text[:120]))
    pv = await c.get(f"/api/customers/{a['id']}/merge-preview", params={"source_id": b["id"]}, headers=h)
    deny = await c.post(f"/api/customers/{a['id']}/merge", json={"data": {"source_id": b["id"], "reason": f"{T} dup"}}, headers=hs)
    noreason = await c.post(f"/api/customers/{a['id']}/merge", json={"data": {"source_id": b["id"]}}, headers=h)
    kanda = await db.customers.find_one({"entity_id": OTHER}, {"_id": 0, "id": 1})
    cross = await c.post(f"/api/customers/{a['id']}/merge", json={"data": {"source_id": kanda["id"], "reason": f"{T} lintas"}}, headers=h)
    check("MASTER-05", "preview menghitung referensi (SO); sales 403; tanpa alasan 400; lintas PT ditolak",
          pv.status_code == 200 and pv.json()["references"].get("sales_orders", 0) == (1 if sj else 0) and deny.status_code == 403
          and noreason.status_code == 400 and cross.status_code in (400, 403, 404), (pv.status_code, pv.text[:120], deny.status_code, noreason.status_code, cross.status_code))
    mg = await c.post(f"/api/customers/{a['id']}/merge", json={"data": {"source_id": b["id"], "reason": f"{T} duplikat"}}, headers=h)
    src = await db.customers.find_one({"id": b["id"]}, {"_id": 0})
    tgt = await db.customers.find_one({"id": a["id"]}, {"_id": 0})
    so2 = await db.sales_orders.find_one({"id": sj.get("id")}, {"_id": 0, "customer_id": 1}) if sj else {}
    check("MASTER-05", "merge: SO pindah ke target, sumber status merged + merged_into, alamat sumber ditambahkan, pemilik target tetap",
          mg.status_code == 200 and src["status"] == "merged" and src["merged_into"] == a["id"] and (not sj or so2["customer_id"] == a["id"])
          and len(tgt.get("addresses") or []) == 2 and tgt.get("assigned_sales_id") == a.get("assigned_sales_id"), (mg.status_code, mg.text[:150]))
    again = await c.post(f"/api/customers/{a['id']}/merge", json={"data": {"source_id": b["id"], "reason": f"{T} ulang"}}, headers=h)
    left = await db.sales_orders.count_documents({"customer_id": b["id"]})
    new_so = await c.post("/api/sales-orders", json={"customer_id": b["id"], "shipping_address_id": addr_b, "items": [{"product_id": "prod_endek_bali", "quantity": 1, "unit": "yard"}]}, headers=h)
    check("MASTER-05", "merge ulang 409 (idempoten), 0 dokumen tersisa di sumber, SO baru ke pelanggan merged ditolak",
          again.status_code == 409 and left == 0 and 400 <= new_so.status_code < 500, (again.status_code, left, new_so.status_code, new_so.text[:100]))
    aud = await db.audit_logs.find_one({"action": "customer_merged", "entity_id": a["id"]}, {"_id": 0})
    check("COMM-01", "duplikat pelanggan digabung dengan jejak audit (alasan) & owner target dipertahankan",
          bool(aud) and mg.status_code == 200, bool(aud))
    if sj.get("id"):
        await c.post(f"/api/sales-orders/{sj['id']}/cancel", json={"reason": f"{T} batal"}, headers=h)
    if new_so.status_code == 200:
        await c.post(f"/api/sales-orders/{new_so.json()['id']}/cancel", json={"reason": f"{T} batal"}, headers=h)


async def main():
    import httpx
    from db import db
    full = snapshot_stock(["number_sequences", "inventory_rolls", "inventory_balances", "uoms", "products", "suppliers",
                           "product_templates", "config_values", "sales_orders", "system_settings"])
    ids = snapshot_new_ids(NEW)
    async with httpx.AsyncClient(base_url="http://localhost:8001", timeout=120) as c:
        h = await login(c, "admin@kainnusantara.id")
        hk = await login(c, "admin@kainnusantara.id", OTHER)
        hs = await login(c, "sales@kainnusantara.id")
        for fn in (master01(c, h, db), master02_03(c, h, hk, db), master04(c, h, db), master05(c, h, hs, db)):
            try:
                await fn
            except Exception as exc:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check("P18B", "eksekusi", False, repr(exc)[:200])
        purge_new_ids(ids, verbose=False)
        restore_stock(full)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
