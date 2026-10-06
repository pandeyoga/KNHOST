"""P16 — tutup cakupan: transfer antargudang/antarentitas (INV-02/INV-04), penjualan → faktur
(SALE-01/SALE-03), alur desain (DESIGN-01/03 + jalur lama galeri).

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-09-P16-close-coverage/repro_p16.py [--only=trf,sale,design]
HTTP ke backend lokal (DB demo). Semua data uji berprefiks TEST_P16 dan dikembalikan di akhir
(roll di-restore dari snapshot, dokumen/jurnal/mutasi buatan skrip dihapus, saldo dibangun ulang).
"""
import asyncio
import base64
import json
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
ENT = "ent_ksc"
T = f"TEST_P16_{uuid.uuid4().hex[:6]}"
ONLY = next((a.split("=", 1)[1].split(",") for a in sys.argv[1:] if a.startswith("--only=")), None)
START = datetime.now(timezone.utc).isoformat()
results = []
created = {"transfers": [], "orders": [], "receipts": [], "requests": [], "galleries": [],
           "products": set(), "customers": {}}
roll_snap = {}
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def login(c, email, pwd="demo12345"):
    r = await c.post("/api/auth/login", json={"email": email, "password": pwd})
    return {"Authorization": f"Bearer {r.json().get('token')}", "X-Entity-Id": ENT}


async def snap_product(db, pid):
    if pid in created["products"]:
        return
    created["products"].add(pid)
    for r in await db.inventory_rolls.find({"product_id": pid}, {"_id": 0}).to_list(None):
        roll_snap[r["id"]] = r


async def free_roll(db, pid=None, wh="wh_jakarta", owner=ENT):
    q = {"warehouse_id": wh, "owner_entity_id": owner, "status": "available",
         "length_reserved": {"$not": {"$gt": 0}}, "length_remaining": {"$gt": 0}}
    if pid:
        q["product_id"] = pid
    r = await db.inventory_rolls.find_one(q, {"_id": 0}, sort=[("length_remaining", 1)])
    if r:
        await snap_product(db, r["product_id"])
    return r


async def roll(db, rid):
    return await db.inventory_rolls.find_one({"id": rid}, {"_id": 0})


async def free_len(db, pid, wh, owner=ENT):
    rs = await db.inventory_rolls.find({"product_id": pid, "warehouse_id": wh, "owner_entity_id": owner,
                                        "status": "available"}, {"_id": 0}).to_list(None)
    return round(sum(float(r.get("length_remaining") or 0) - float(r.get("length_reserved") or 0) for r in rs), 2)


async def balance(db, pid, wh, owner=ENT):
    b = await db.inventory_balances.find_one({"product_id": pid, "warehouse_id": wh, "owner_entity_id": owner}, {"_id": 0})
    return b or {}


async def total_len(db, pid):
    rs = await db.inventory_rolls.find({"product_id": pid, "status": {"$nin": ["consumed", "shipped", "void", "merged"]}},
                                       {"_id": 0, "length_remaining": 1}).to_list(None)
    return round(sum(float(r.get("length_remaining") or 0) for r in rs), 2)


# ── INV-02: transfer antargudang (intra entitas) ─────────────────────────────
async def trf(c, h, db):
    r0 = await free_roll(db)
    if not r0:
        check("INV-02", "ada roll bebas di wh_jakarta", False)
        return
    pid, rid, L = r0["product_id"], r0["id"], float(r0["length_remaining"])
    tot0 = await total_len(db, pid)
    fj0, fb0 = await free_len(db, pid, "wh_jakarta"), await free_len(db, pid, "wh_bandung")
    bj0, bb0 = await balance(db, pid, "wh_jakarta"), await balance(db, pid, "wh_bandung")

    async def create(rids):
        body = {"source_warehouse_id": "wh_jakarta", "dest_warehouse_id": "wh_bandung", "notes": T,
                "requested_by": T, "items": [{"product_id": pid, "qty": 0, "roll_ids": rids}]}
        res = await c.post("/api/transfers", json=body, headers=h)
        if res.status_code == 200:
            created["transfers"].append(res.json()["id"])
        return res

    st = lambda tid, s: c.post(f"/api/transfers/{tid}/status", json={"status": s, "updated_by": T}, headers=h)  # noqa: E731
    cancel = lambda tid, why=f"{T} batal": c.delete(f"/api/transfers/{tid}", params={"reason": why}, headers=h)  # noqa: E731

    # 1) buat → roll dipesan, panjang bebas gudang asal turun
    r = await create([rid])
    t1 = r.json() if r.status_code == 200 else {}
    rr = await roll(db, rid)
    check("INV-02", "buat transfer 1 roll → waiting_approval, roll reserved ber-ref wh_transfer",
          r.status_code == 200 and t1.get("status") == "waiting_approval" and rr["status"] == "reserved"
          and (rr.get("reserved_ref") or {}).get("id") == t1.get("id"), f"{r.status_code} {rr.get('status')} {r.text[:120]}")
    check("INV-02", "panjang bebas gudang asal berkurang tepat sepanjang roll",
          round(fj0 - await free_len(db, pid, "wh_jakarta"), 2) == round(L, 2), f"{fj0}→{await free_len(db, pid, 'wh_jakarta')} L={L}")
    dup = await create([rid])
    check("INV-02", "roll yang sudah dipesan tidak bisa dipesan transfer lain (409)", dup.status_code == 409, dup.status_code)

    # 2) jalur status tidak boleh dipakai untuk approve/reject/cancel
    codes = {s: (await st(t1["id"], s)).status_code for s in ("approved", "rejected", "cancelled", "completed")}
    rr = await roll(db, rid)
    check("INV-02", "POST /status approved|rejected|cancelled|completed dari waiting_approval → 400, roll tetap reserved",
          all(v == 400 for v in codes.values()) and rr["status"] == "reserved", f"{codes} roll={rr['status']}")

    # 3) DELETE melepas reservasi + alasan tersimpan + audit
    r = await cancel(t1["id"])
    rr = await roll(db, rid)
    doc = await db.warehouse_transfers.find_one({"id": t1["id"]}, {"_id": 0})
    aud = await db.audit_logs.find_one({"entity_id": t1["id"], "action": "transfer_cancelled"}, {"_id": 0})
    check("INV-02", "DELETE ?reason dari waiting_approval → cancelled, roll available di wh_jakarta tanpa reserved_ref",
          r.status_code == 200 and doc["status"] == "cancelled" and rr["status"] == "available"
          and rr.get("reserved_ref") is None and rr["warehouse_id"] == "wh_jakarta", f"{r.status_code} {rr.get('status')}")
    check("INV-02", "alasan batal tersimpan di dokumen & audit log",
          doc.get("cancelled_reason", "").startswith(T) and aud and (aud.get("details") or aud.get("detail") or aud.get("after") or {}) != {},
          f"{doc.get('cancelled_reason')} audit={bool(aud)}")
    again = await cancel(t1["id"])
    check("INV-02", "batal ulang ditolak 400", again.status_code == 400, again.status_code)
    check("INV-02", "panjang bebas gudang asal pulih setelah batal", await free_len(db, pid, "wh_jakarta") == fj0,
          f"{fj0} vs {await free_len(db, pid, 'wh_jakarta')}")

    # 4) alur penuh approve → picking → staging → dispatched → completed
    r = await create([rid])
    t2 = r.json()
    ap = await c.post(f"/api/transfers/{t2['id']}/approve", json={"approved_by": T}, headers=h)
    skip = await st(t2["id"], "dispatched")
    canc_status = await st(t2["id"], "cancelled")
    seq = {}
    for s in ("picking", "staging", "dispatched"):
        seq[s] = (await st(t2["id"], s)).status_code
    rr = await roll(db, rid)
    mov_out = await db.inventory_movements.find_one({"roll_id": rid, "movement_type": "transfer_out", "timestamp": {"$gte": START}}, {"_id": 0})
    check("INV-02", "approve 200; lompat approved→dispatched & /status cancelled ditolak 400",
          ap.status_code == 200 and skip.status_code == 400 and canc_status.status_code == 400,
          f"{ap.status_code}/{skip.status_code}/{canc_status.status_code}")
    check("INV-02", "picking→staging→dispatched 200; roll in_transit_transfer + mutasi transfer_out −L",
          all(v == 200 for v in seq.values()) and rr["status"] == "in_transit_transfer" and mov_out
          and round(-float(mov_out["quantity"]), 2) == round(L, 2), f"{seq} {rr['status']} mov={bool(mov_out)}")
    b_j_mid = await balance(db, pid, "wh_jakarta")
    done = await st(t2["id"], "completed")
    rr = await roll(db, rid)
    mov_in = await db.inventory_movements.find_one({"roll_id": rid, "movement_type": "transfer_in", "timestamp": {"$gte": START}}, {"_id": 0})
    check("INV-02", "completed → roll available di wh_bandung, bin dikosongkan, last_transfer dari wh_jakarta, owner tetap",
          done.status_code == 200 and rr["status"] == "available" and rr["warehouse_id"] == "wh_bandung"
          and rr.get("bin_id") is None and (rr.get("last_transfer") or {}).get("from_warehouse_id") == "wh_jakarta"
          and rr["owner_entity_id"] == ENT and rr.get("reserved_ref") is None and mov_in,
          f"{done.status_code} {rr.get('status')} {rr.get('warehouse_id')}")
    fj1, fb1 = await free_len(db, pid, "wh_jakarta"), await free_len(db, pid, "wh_bandung")
    check("INV-02", "stok asal −L dan tujuan +L; total panjang produk tetap (tidak ada roll ganda/hilang)",
          round(fj0 - fj1, 2) == round(L, 2) and round(fb1 - fb0, 2) == round(L, 2) and await total_len(db, pid) == tot0
          and await db.inventory_rolls.count_documents({"id": rid}) == 1,
          f"jkt {fj0}→{fj1} bdg {fb0}→{fb1} total {tot0}→{await total_len(db, pid)}")
    bj, bb = await balance(db, pid, "wh_jakarta"), await balance(db, pid, "wh_bandung")
    check("INV-02", "inventory_balances dibangun ulang dari roll: on_hand asal −L, in_transit saat jalan, tujuan +L",
          bool(bb) and float(bb.get("on_hand_qty") or 0) - float(bb0.get("on_hand_qty") or 0) == round(L, 2)
          and round(float(bj0.get("on_hand_qty") or 0) - float(bj.get("on_hand_qty") or 0), 2) == round(L, 2)
          and float(b_j_mid.get("in_transit_transfer_qty") or 0) >= L,
          {"jkt": [bj0.get("on_hand_qty"), b_j_mid.get("in_transit_transfer_qty"), bj.get("on_hand_qty")], "bdg": [bb0.get("on_hand_qty"), bb.get("on_hand_qty")]})
    after_done = await cancel(t2["id"])
    check("INV-02", "transfer selesai tidak bisa dibatalkan (400)", after_done.status_code == 400, after_done.status_code)
    acts = {a["action"] for a in await db.audit_logs.find({"entity_id": t2["id"]}, {"_id": 0, "action": 1}).to_list(50)}
    check("INV-02", "jejak audit lengkap per tahap (created/approved/status_changed)",
          {"transfer_created", "transfer_approved", "transfer_status_changed"} <= acts, sorted(acts))

    # 5) batal SETELAH dispatched → roll kembali ke gudang asal & ledger seimbang
    r3 = await free_roll(db, pid, "wh_bandung")
    if r3:
        body = {"source_warehouse_id": "wh_bandung", "dest_warehouse_id": "wh_jakarta", "notes": T, "requested_by": T,
                "items": [{"product_id": pid, "qty": 0, "roll_ids": [r3["id"]]}]}
        res = await c.post("/api/transfers", json=body, headers=h)
        t3 = res.json()
        created["transfers"].append(t3.get("id"))
        await c.post(f"/api/transfers/{t3['id']}/approve", json={"approved_by": T}, headers=h)
        for s in ("picking", "staging", "dispatched"):
            await st(t3["id"], s)
        cx = await cancel(t3["id"], f"{T} truk batal")
        rr3 = await roll(db, r3["id"])
        movs = await db.inventory_movements.find({"roll_id": r3["id"], "timestamp": {"$gte": START},
                                                  "source_document": {"$in": [t3["id"], f"transfer_{t3.get('code')}"]}},
                                                 {"_id": 0, "quantity": 1, "movement_type": 1}).to_list(10)
        check("INV-02", "batal sesudah dispatched → roll available di gudang asal + mutasi transfer_cancelled menyeimbangkan transfer_out",
              cx.status_code == 200 and rr3["status"] == "available" and rr3["warehouse_id"] == "wh_bandung"
              and abs(sum(float(m["quantity"]) for m in movs)) < 0.01 and any(m["movement_type"] == "transfer_cancelled" for m in movs),
              f"{cx.status_code} {rr3['status']} {rr3['warehouse_id']} {movs}")

    # 6) tolak → lepas
    r4 = await free_roll(db, pid)
    if r4:
        res = await create([r4["id"]])
        rj = await c.post(f"/api/transfers/{res.json()['id']}/reject", json={"rejected_by": T, "reason": f"{T} tolak"}, headers=h)
        rr4 = await roll(db, r4["id"])
        check("INV-02", "tolak → roll available tanpa ref", rj.status_code == 200 and rr4["status"] == "available"
              and rr4.get("reserved_ref") is None, f"{rj.status_code} {rr4['status']}")


# ── INV-04: transfer antarentitas — reservasi dilepas saat batal ──────────────
async def inv04(c, h, db):
    r0 = await free_roll(db, wh="wh_jakarta")
    pid, L = r0["product_id"], float(r0["length_remaining"])
    fj0 = await free_len(db, pid, "wh_jakarta")
    body = {"source_entity_id": ENT, "dest_entity_id": "ent_kanda", "notes": T,
            "items": [{"product_id": pid, "quantity": min(L, 1.0), "unit": r0.get("unit", "meter")}]}
    res = await c.post("/api/transfers/inter-company", json=body, headers=h)
    t = res.json() if res.status_code == 200 else {}
    if t.get("id"):
        created["transfers"].append(t["id"])
    held = await db.inventory_rolls.find({"reserved_ref.id": t.get("id")}, {"_id": 0}).to_list(20)
    for x in held:
        await snap_product(db, x["product_id"])
    check("INV-04", "transfer antar-PT dibuat & roll entitas asal dipesan", res.status_code == 200 and len(held) >= 1,
          f"{res.status_code} {res.text[:150]} held={len(held)}")
    st = await c.post(f"/api/transfers/{t.get('id')}/status", json={"status": "cancelled"}, headers=h)
    cx = await c.delete(f"/api/transfers/{t.get('id')}", params={"reason": f"{T} batal ic"}, headers=h)
    left = await db.inventory_rolls.count_documents({"reserved_ref.id": t.get("id")})
    je = await db.journal_entries.count_documents({"source_id": t.get("id")})
    check("INV-04", "/status cancelled ditolak 400; DELETE melepas semua roll, tanpa jurnal antar-PT",
          st.status_code == 400 and cx.status_code == 200 and left == 0 and je == 0,
          f"{st.status_code}/{cx.status_code} left={left} je={je}")
    check("INV-04", "panjang bebas entitas asal pulih", await free_len(db, pid, "wh_jakarta") == fj0,
          f"{fj0} vs {await free_len(db, pid, 'wh_jakarta')}")


# ── SALE-01/03: pesanan → reservasi → picking → kirim → AR/faktur ─────────────
async def approve_confirm(c, h, db, oid):
    so = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
    if so["status"] in ("reserved", "draft"):
        await c.post(f"/api/sales-orders/{oid}/verify", json={}, headers=h)
        await c.post(f"/api/sales-orders/{oid}/submit-for-approval", json={}, headers=h)
    so = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
    for pa in so.get("pending_approvals") or []:
        if pa.get("status") == "pending":
            await c.post(f"/api/sales-orders/{oid}/approvals/{pa['id']}/decide", json={"decision": "approve", "notes": T}, headers=h)
    so = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
    if so["status"] in ("waiting_approval", "reserved"):
        await c.post(f"/api/sales-orders/{oid}/approve", json={}, headers=h)
    return await c.post(f"/api/sales-orders/{oid}/confirm", json={}, headers=h)


async def ship_task(c, h, t):
    await c.post(f"/api/outbound/tasks/{t['id']}/scan-pick", params={"actual_qty": t.get("quantity")}, json={}, headers=h)
    pc = (await c.get("/api/inventory/pending-cuts", params={"order_id": t["order_id"]}, headers=h)).json().get("items", [])
    for p in pc:
        if p.get("product_id") != t.get("product_id"):
            continue
        cr = await c.post(f"/api/inventory/rolls/{p['roll_id']}/reservations/{p['reservation_id']}/cut",
                          json={"actual_length": p.get("qty")}, headers=h)
        if cr.status_code == 200:
            ch = cr.json()["child"]
            await c.post(f"/api/inventory/rolls/{ch['id']}/verify-identity", json={"scanned_code": ch["roll_no"]}, headers=h)
    return await c.post(f"/api/outbound/tasks/{t['id']}/dispatch", json={}, headers=h)


async def new_so(c, h, db, lines):
    for pid, _ in lines:
        await snap_product(db, pid)
    cust = await db.customers.find_one({"id": "cust_toko_kain"}, {"_id": 0})
    created["customers"].setdefault(cust["id"], cust)
    body = {"customer_id": "cust_toko_kain", "shipping_address_id": "addr_001",
            "items": [{"product_id": p, "quantity": q, "unit": "yard"} for p, q in lines]}
    r = await c.post("/api/sales-orders", json=body, headers=h)
    if r.status_code == 200:
        created["orders"].append(r.json()["id"])
    return r


async def ar_lines(db, oid):
    jes = await db.journal_entries.find({"ref.order_id": oid, "source_type": "shipment_revenue", "status": "posted"},
                                        {"_id": 0, "lines": 1}).to_list(20)
    tot = {"ar": 0.0, "rev": 0.0, "ppn": 0.0}
    for j in jes:
        for ln in j["lines"]:
            k = {"1-1200": "ar", "4-1000": "rev", "2-1200": "ppn"}.get(ln["account_code"])
            if k:
                tot[k] += float(ln["debit"] if k == "ar" else ln["credit"])
    return {k: round(v, 2) for k, v in tot.items()}, len(jes)


async def sale(c, h, db):
    pid = "prod_endek_bali"
    fl_s0 = await free_len(db, pid, "wh_jakarta") + await free_len(db, pid, "wh_surabaya")
    r = await new_so(c, h, db, [(pid, 10)])
    so = r.json()
    oid = so.get("id")
    check("SALE-01", "SO dibuat & stok dipesan (reserved_qty = qty)", r.status_code == 200 and so.get("status") == "reserved"
          and so["items"][0].get("reserved_qty") == 10, f"{r.status_code} {so.get('status')}")
    net, ppn, grand = float(so["net_subtotal"]), float(so["ppn_amount"]), float(so["grand_total"])
    check("SALE-01", "total = qty×harga; PPN 12%×DPP(11/12); grand = net + PPN",
          round(so["items"][0]["price"] * 10, 2) == net and abs(ppn - round(float(so["dpp"]) * 0.12, 0)) <= 1
          and round(net + ppn, 2) == grand, {"net": net, "dpp": so["dpp"], "ppn": ppn, "grand": grand})
    cf = await approve_confirm(c, h, db, oid)
    ft = await c.post(f"/api/sales-orders/{oid}/tax-invoice", json={}, headers=h)
    fk = ft.json() if ft.status_code == 200 else {}
    check("SALE-01", "Faktur Pajak dari SO terkonfirmasi: DPP/PPN/grand = SO", cf.status_code == 200 and ft.status_code == 200
          and fk.get("dpp") == so["dpp"] and fk.get("ppn_amount") == ppn and fk.get("grand_total") == grand,
          f"{cf.status_code}/{ft.status_code} {ft.text[:120]}")
    await c.post(f"/api/wms/tasks/outbound-from-order/{oid}", json={}, headers=h)
    tasks = await db.wms_tasks.find({"order_id": oid, "flow_type": "outbound"}, {"_id": 0}).to_list(10)
    codes = [(await ship_task(c, h, t)).status_code for t in tasks]
    so2 = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
    ar, n = await ar_lines(db, oid)
    check("SALE-01", "pick → potong → verifikasi label → kirim: SO shipped + surat jalan", tasks and all(x == 200 for x in codes)
          and so2["status"] == "shipped" and await db.shipments.count_documents({"order_id": oid}) >= 1, f"{codes} {so2['status']}")
    check("SALE-01", "jurnal pengakuan: Piutang = grand, Pendapatan = net, PPN Keluaran = PPN SO",
          ar["ar"] == grand and ar["rev"] == net and ar["ppn"] == ppn, f"{ar} vs grand={grand}")
    cogs = await db.journal_entries.count_documents({"ref.order_id": oid, "source_type": "shipment_cogs", "status": "posted"})
    held = await db.inventory_rolls.count_documents({"reserved_ref.id": oid, "status": {"$in": ["reserved", "committed", "picked"]}})
    lres = await db.inventory_rolls.count_documents({"length_reservations.ref.id": oid})
    fl_s1 = await free_len(db, pid, "wh_jakarta") + await free_len(db, pid, "wh_surabaya")
    sold = await db.inventory_rolls.find({"reserved_ref.id": oid}, {"_id": 0, "status": 1, "length_remaining": 1}).to_list(20)
    check("SALE-01", "HPP terposting; tak ada sisa reservasi; roll terkirim in_transit_sales Σ=10; panjang bebas −10",
          cogs >= 1 and held == 0 and lres == 0 and sold and all(x["status"] == "in_transit_sales" for x in sold)
          and round(sum(float(x["length_remaining"]) for x in sold), 2) == 10.0 and round(fl_s0 - fl_s1, 2) == 10.0,
          f"cogs={cogs} held={held} lres={lres} sold={sold} free {fl_s0}→{fl_s1}")
    oo = (await c.get("/api/ar-receipts/open-orders", params={"customer_id": "cust_toko_kain"}, headers=h)).json()
    mine = next((o for o in oo if o.get("order_id", o.get("id")) == oid), {})
    rc = await c.post("/api/ar-receipts", json={"customer_id": "cust_toko_kain", "amount": 1000000, "method": "transfer",
                                                "notes": T, "allocations": [{"order_id": oid, "amount": 1000000}]}, headers=h)
    if rc.status_code == 200:
        created["receipts"].append(rc.json().get("id"))
    oo2 = (await c.get("/api/ar-receipts/open-orders", params={"customer_id": "cust_toko_kain"}, headers=h)).json()
    mine2 = next((o for o in oo2 if o.get("order_id", o.get("id")) == oid), {})
    check("SALE-01", "sisa tagihan: outstanding = grand, lalu grand − 1.000.000 setelah penerimaan AR",
          mine.get("outstanding") == grand and rc.status_code == 200 and mine2.get("outstanding") == round(grand - 1000000, 2),
          f"{mine.get('outstanding')} → {mine2.get('outstanding')} rc={rc.status_code} {rc.text[:120]}")
    from services import pdf_resolvers as pr
    inv = await pr.resolve_invoice(await db.sales_orders.find_one({"id": oid}, {"_id": 0}), db)
    tl = {t["label"]: t["value"] for t in inv["totals"]}
    check("SALE-01", "dokumen Faktur: subtotal, PPN, grand total = SO", tl.get("Grand Total") == pr.fmt_rp(grand)
          and tl.get("Subtotal") == pr.fmt_rp(net) and any(v == pr.fmt_rp(ppn) for v in tl.values()), tl)

    # SALE-01b — kiriman parsial 2 baris: AR per surat jalan pro-rata, total = grand setelah lengkap
    r = await new_so(c, h, db, [("prod_endek_bali", 5), ("prod_tenun_ikat", 5)])
    so = r.json()
    oid2 = so.get("id")
    await approve_confirm(c, h, db, oid2)
    await c.post(f"/api/wms/tasks/outbound-from-order/{oid2}", json={}, headers=h)
    tasks = await db.wms_tasks.find({"order_id": oid2, "flow_type": "outbound"}, {"_id": 0}).sort("product_id", 1).to_list(10)
    first = await ship_task(c, h, tasks[0]) if tasks else None
    mid = await db.sales_orders.find_one({"id": oid2}, {"_id": 0})
    ar1, _ = await ar_lines(db, oid2)
    line_val = next(float(i["line_total"]) for i in so["items"] if i["product_id"] == tasks[0]["product_id"])
    exp_ar1 = round(float(so["grand_total"]) * line_val / float(so["net_subtotal"]), 2)
    other_res = await db.inventory_rolls.count_documents({"$or": [{"reserved_ref.id": oid2}, {"length_reservations.ref.id": oid2}],
                                                         "product_id": tasks[1]["product_id"]}) if len(tasks) > 1 else 0
    check("SALE-01", "kiriman parsial: status partially_shipped, Piutang = porsi baris terkirim, baris lain tetap dipesan",
          first is not None and first.status_code == 200 and mid["status"] == "partially_shipped"
          and abs(ar1["ar"] - exp_ar1) <= 1 and other_res >= 1, f"{mid['status']} ar={ar1['ar']} exp={exp_ar1} res={other_res}")
    canc_part = await c.post(f"/api/sales-orders/{oid2}/cancel", json={}, headers=h)
    check("SALE-03", "SO terkirim sebagian tidak bisa dibatalkan (409)", canc_part.status_code == 409, canc_part.status_code)
    for t in tasks[1:]:
        await ship_task(c, h, t)
    end = await db.sales_orders.find_one({"id": oid2}, {"_id": 0})
    ar2, n2 = await ar_lines(db, oid2)
    check("SALE-01", "setelah kiriman terakhir: shipped, Σ Piutang = grand, Σ PPN = PPN SO (tanpa selisih pembulatan)",
          end["status"] == "shipped" and ar2["ar"] == float(so["grand_total"]) and ar2["ppn"] == float(so["ppn_amount"]) and n2 == len(tasks),
          f"{end['status']} {ar2} grand={so['grand_total']} je={n2}")

    # SALE-03 — batal melepas reservasi
    pid3 = "prod_tenun_ikat"
    fl0 = {w: await free_len(db, pid3, w) for w in ("wh_jakarta", "wh_surabaya")}
    r = await new_so(c, h, db, [(pid3, 4)])
    oid3 = r.json().get("id")
    fl1 = {w: await free_len(db, pid3, w) for w in fl0}
    cx = await c.post(f"/api/sales-orders/{oid3}/cancel", json={}, headers=h)
    fl2 = {w: await free_len(db, pid3, w) for w in fl0}
    left = await db.inventory_rolls.count_documents({"$or": [{"reserved_ref.id": oid3}, {"length_reservations.ref.id": oid3}]})
    check("SALE-03", "SO reserved dibatalkan → panjang bebas pulih persis, tidak ada reservasi tersisa",
          round(sum(fl0.values()) - sum(fl1.values()), 2) == 4.0 and cx.status_code == 200 and fl2 == fl0 and left == 0,
          f"{fl0}→{fl1}→{fl2} left={left} {cx.status_code}")
    # SALE-03b — SO terkonfirmasi + Faktur Pajak aktif lalu dibatalkan
    r = await new_so(c, h, db, [(pid3, 3)])
    oid4 = r.json().get("id")
    await approve_confirm(c, h, db, oid4)
    f4 = await c.post(f"/api/sales-orders/{oid4}/tax-invoice", json={}, headers=h)
    cx = await c.post(f"/api/sales-orders/{oid4}/cancel", json={}, headers=h)
    active = await db.tax_invoices.count_documents({"order_id": oid4, "status": {"$ne": "batal"}})
    so4 = await db.sales_orders.find_one({"id": oid4}, {"_id": 0, "status": 1})
    check("SALE-03", "SO dengan Faktur Pajak aktif: batal ditolak 409 (faktur pajak dibatalkan dulu) — tidak ada faktur aktif untuk SO batal",
          f4.status_code == 200 and cx.status_code == 409 and so4["status"] != "cancelled" and active == 1,
          f"fkt={f4.status_code} cancel={cx.status_code} {cx.text[:150]} so={so4['status']} active={active}")
    fid = (f4.json() or {}).get("id")
    fc = await c.post(f"/api/tax-invoices/{fid}/cancel", json={"reason": f"{T} batal faktur"}, headers=h)
    cx2 = await c.post(f"/api/sales-orders/{oid4}/cancel", json={}, headers=h)
    left = await db.inventory_rolls.count_documents({"$or": [{"reserved_ref.id": oid4}, {"length_reservations.ref.id": oid4}]})
    tasks_alive = await db.wms_tasks.count_documents({"order_id": oid4, "status": {"$nin": ["cancelled", "dispatched", "completed"]}})
    check("SALE-03", "setelah faktur pajak dibatalkan: SO batal 200, reservasi lepas, tugas gudang batal",
          fc.status_code == 200 and cx2.status_code == 200 and left == 0 and tasks_alive == 0,
          f"fc={fc.status_code} {fc.text[:100]} cx={cx2.status_code} left={left} tasks={tasks_alive}")


# ── DESIGN: request → desain → ACC → final → aktif (produksi); jalur lama; arsip/reopen ──
async def design(c, h, db):
    meta = (await c.get("/api/design-requests/meta", headers=h)).json()
    pat = (meta.get("categories", {}).get("pattern") or [{}])[0].get("code", "")
    dsg = (meta.get("categories", {}).get("design") or [{}])[0].get("code", "")
    designer = next((d for d in meta.get("designers", []) if "designer@" in str(d.get("email", ""))), (meta.get("designers") or [{}])[0])
    hd = await login(c, "designer@kainnusantara.id")
    base = {"category_code": pat, "design_category_code": dsg, "assigned_to": designer.get("id"), "submit_now": True}

    async def new_design(label):
        r = await c.post("/api/design-requests", json={**base, "brief": f"{T} {label}"}, headers=h)
        req = r.json()
        created["requests"].append(req["id"])
        r = await c.post(f"/api/design-requests/{req['id']}/create-design", json={"title": f"{T} {label}"}, headers=hd)
        gid = ((r.json() or {}).get("design") or {}).get("id")
        created["galleries"].append(gid)
        await c.post(f"/api/design-gallery/{gid}/files", headers=hd, files={"file": (f"{T}.png", PNG, "image/png")})
        return req["id"], gid

    up = lambda gid, kind, hh: c.post(f"/api/design-gallery/{gid}/files-kind/{kind}", headers=hh,  # noqa: E731
                                      files={"file": (f"{T}_{kind}.png", PNG, "image/png")})
    lc = lambda gid, act, hh, **kw: c.post(f"/api/design-gallery/{gid}/lifecycle/{act}", json={"note": f"{T} {act}", **kw}, headers=hh)  # noqa: E731
    gstat = lambda gid: db.design_gallery.find_one({"id": gid}, {"_id": 0})  # noqa: E731

    # Jalur lama galeri tidak boleh melewati aturan Studio (nilai wajib, desainer tak boleh ACC sendiri)
    rid, gid = await new_design("jalur lama")
    ls = await c.post(f"/api/design-gallery/{gid}/submit", headers=hd)
    la = await c.post(f"/api/design-gallery/{gid}/approve", json={"note": "self"}, headers=hd)
    g = await gstat(gid)
    check("DESIGN-01", "desainer tidak bisa meng-ACC desainnya sendiri lewat POST /design-gallery/{id}/approve (jalur lama)",
          la.status_code in (400, 403) and g["status"] != "approved", f"submit={ls.status_code} approve={la.status_code} status={g['status']}")
    la2 = await c.post(f"/api/design-gallery/{gid}/approve", json={"note": "tanpa nilai"}, headers=h)
    g = await gstat(gid)
    check("DESIGN-01", "ACC lewat jalur lama tanpa nilai ditolak (nilai wajib saat ACC)", la2.status_code == 400 and g["status"] != "approved",
          f"{la2.status_code} {la2.text[:120]} {g['status']}")
    lr = await c.post(f"/api/design-gallery/{gid}/reject", json={"reason": f"{T} perbaiki"}, headers=hd)
    check("DESIGN-01", "desainer tidak bisa mengembalikan (reject) desain lewat jalur lama", lr.status_code in (400, 403), lr.status_code)

    # Alur penuh sampai Aktif/Produksi + status permintaan ikut
    rid, gid = await new_design("alur produksi")
    sub = await lc(gid, "submit", hd)
    acc = await lc(gid, "approve", h, score=1.75)
    early = await lc(gid, "activate", h)
    sf_missing = await lc(gid, "submit-final", hd)
    await up(gid, "mockup", hd)
    await up(gid, "source", hd)
    sf = await lc(gid, "submit-final", hd)
    act_designer = await lc(gid, "activate", hd)
    act = await lc(gid, "activate", h)
    g = await gstat(gid)
    req = (await c.get(f"/api/design-requests/{rid}", headers=h)).json()
    check("DESIGN-01", "ajukan → ACC(nilai) → serah final (mockup+source wajib) → aktif/produksi",
          sub.status_code == 200 and acc.status_code == 200 and sf_missing.status_code == 400 and sf.status_code == 200
          and act.status_code == 200 and g["status"] == "active",
          f"sub={sub.status_code} acc={acc.status_code} sf0={sf_missing.status_code} sf={sf.status_code} act={act.status_code} {act.text[:100]} st={g['status']}")
    check("DESIGN-01", "aktivasi sebelum berkas final ditolak; desainer tidak bisa mengaktifkan sendiri",
          early.status_code == 400 and act_designer.status_code == 403, f"{early.status_code}/{act_designer.status_code}")
    check("DESIGN-01", "permintaan desain ikut berstatus disetujui & timeline mencatat tiap tahap",
          req.get("status") == "approved" and {"submit", "approve", "submit_final", "activate"} <= {e.get("event") for e in g.get("timeline", [])},
          f"req={req.get('status')} tl={[e.get('event') for e in g.get('timeline', [])]}")

    # DESIGN-03 — arsip / reopen menjaga berkas & riwayat versi
    nfiles = len(g.get("files") or [])
    nver = len(g.get("versions") or [])
    no_reason = await c.post(f"/api/design-gallery/{gid}/lifecycle/archive", json={"note": ""}, headers=h)
    ar = await lc(gid, "archive", h)
    ro_designer = await lc(gid, "reopen", hd)
    ro = await lc(gid, "reopen", h)
    g2 = await gstat(gid)
    check("DESIGN-03", "arsip wajib alasan; arsip → reopen kembali ke draf (desainer tak boleh reopen)",
          no_reason.status_code == 400 and ar.status_code == 200 and ro_designer.status_code == 403 and ro.status_code == 200
          and g2["status"] == "draft", f"{no_reason.status_code}/{ar.status_code}/{ro_designer.status_code}/{ro.status_code} {g2['status']}")
    check("DESIGN-03", "reopen tidak menghapus berkas & versi, nilai/ACC lama dikosongkan",
          len(g2.get("files") or []) == nfiles and len(g2.get("versions") or []) == nver and not g2.get("final_score")
          and not g2.get("approved_by"), f"files {nfiles}→{len(g2.get('files') or [])} ver {nver}→{len(g2.get('versions') or [])}")
    resub = await lc(gid, "submit", hd)
    check("DESIGN-03", "desain yang dibuka ulang bisa diajukan lagi", resub.status_code == 200, f"{resub.status_code} {resub.text[:120]}")


async def cleanup(db):
    from services.roll_service import rebuild_balance
    tids = [t for t in created["transfers"] if t]
    oids = [o for o in created["orders"] if o]
    rcp = [r for r in created["receipts"] if r]
    gids = [g for g in created["galleries"] if g]
    prods = list(created["products"])
    ship_ids = [s["id"] for s in await db.shipments.find({"order_id": {"$in": oids}}, {"_id": 0, "id": 1}).to_list(None)]
    task_ids = [t["id"] for t in await db.wms_tasks.find({"order_id": {"$in": oids}}, {"_id": 0, "id": 1}).to_list(None)]
    fkt_ids = [f["id"] for f in await db.tax_invoices.find({"order_id": {"$in": oids}}, {"_id": 0, "id": 1}).to_list(None)]
    src = tids + oids + rcp + ship_ids
    await db.journal_entries.delete_many({"$or": [{"source_id": {"$in": src}}, {"ref.order_id": {"$in": oids}}]})
    await db.cash_transactions.delete_many({"$or": [{"ref_id": {"$in": rcp}}, {"source_id": {"$in": rcp}}, {"reference_id": {"$in": rcp}}]})
    await db.ar_receipts.delete_many({"id": {"$in": rcp}})
    await db.warehouse_transfers.delete_many({"id": {"$in": tids}})
    await db.shipments.delete_many({"id": {"$in": ship_ids}})
    await db.wms_tasks.delete_many({"id": {"$in": task_ids}})
    await db.tax_invoices.delete_many({"id": {"$in": fkt_ids}})
    await db.sales_orders.delete_many({"id": {"$in": oids}})
    for coll in ("allocations", "order_allocations", "loading_checks", "credit_overrides", "doc_refs", "posting_failures", "saga_locks"):
        await db[coll].delete_many({"$or": [{"order_id": {"$in": oids}}, {"ref_id": {"$in": oids}}, {"doc_id": {"$in": oids}}]})
    await db.inventory_movements.delete_many({"product_id": {"$in": prods}, "timestamp": {"$gte": START}})
    if prods:
        await db.inventory_rolls.delete_many({"product_id": {"$in": prods}, "id": {"$nin": list(roll_snap)}})
        for rid, doc in roll_snap.items():
            await db.inventory_rolls.replace_one({"id": rid}, doc, upsert=True)
        whs = [w["id"] for w in await db.warehouses.find({}, {"_id": 0, "id": 1}).to_list(None)]
        owners = {r["owner_entity_id"] for r in roll_snap.values()} | {ENT}
        segs = {(p, w, o) for p in prods for w in whs for o in owners}
        for p, w, o in segs:
            await rebuild_balance(p, w, o)
    for cid, doc in created["customers"].items():
        await db.customers.replace_one({"id": cid}, doc)
    import pathlib
    for gd in await db.design_gallery.find({"id": {"$in": gids}}, {"_id": 0, "files.path": 1}).to_list(None):
        for f in gd.get("files") or []:
            if f.get("path"):
                pathlib.Path("uploads", f["path"]).unlink(missing_ok=True)
    await db.design_gallery.delete_many({"id": {"$in": gids}})
    await db.design_requests.delete_many({"id": {"$in": created["requests"]}})
    for coll in ("design_gallery_history", "design_history", "notifications"):
        await db[coll].delete_many({"$or": [{"gallery_id": {"$in": gids}}, {"request_id": {"$in": created["requests"]}}]})
    ids = src + gids + created["requests"] + task_ids + fkt_ids
    await db.audit_logs.delete_many({"$or": [{"entity_id": {"$in": ids}}, {"actor": {"$regex": T}}]})


async def main():
    import httpx
    from db import db
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8009", timeout=120) as c:
        h = await login(c, "admin@kainnusantara.id")
        try:
            for name, fn in (("trf", lambda: trf(c, h, db)), ("trf", lambda: inv04(c, h, db)),
                             ("sale", lambda: sale(c, h, db)), ("design", lambda: design(c, h, db))):
                if ONLY and name not in ONLY:
                    continue
                try:
                    await fn()
                except Exception as exc:  # noqa: BLE001
                    import traceback
                    traceback.print_exc()
                    check(name.upper(), "eksekusi skenario", False, repr(exc)[:200])
        finally:
            await cleanup(db)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
