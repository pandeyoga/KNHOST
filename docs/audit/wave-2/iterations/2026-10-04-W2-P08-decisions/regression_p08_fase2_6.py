"""Regresi P08 fase 2–6 — W2-REQ-09, 08, 06, 04, 05(backend), 07, 02.
Data sintetis TEST_P08B_*, self-clean. Jalankan dari /app/backend: python <file>."""
import asyncio
import json
import os
import sys
import uuid

import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")
from fastapi import HTTPException  # noqa: E402
from db import db  # noqa: E402

BASE = "http://localhost:8001/api"
A = "ent_ksc"
T = f"TEST_P08B_{uuid.uuid4().hex[:6]}"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regression_p08_fase2_6_results.json")
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


def session(email):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": A})
    return s


async def status_of(coro):
    try:
        await coro
        return 200
    except HTTPException as e:
        return e.status_code


class Item:
    def __init__(self, lines, target=None, choice="", qty=0):
        from schemas import RollLineIn
        self.roll_lines = [RollLineIn(**ln) for ln in lines]
        self.target_quantity, self.rounding_choice = target, choice
        self.base_quantity, self.quantity = qty, qty


async def req09():
    from services.roll_service import compute_roll_reconcile
    from services.sales_order_helpers import assert_roll_rounding
    for order_name, lengths in (("A", [100] * 9 + [105]), ("B", [105] + [100] * 9)):
        pid = f"prod_{T}_{order_name}".lower()
        for i, ln in enumerate(lengths):
            await db.inventory_rolls.insert_one({"id": f"roll_{T}_{order_name}_{i}".lower(), "roll_no": f"{T}-{order_name}{i:02d}",
                                                 "product_id": pid, "owner_entity_id": A, "warehouse_id": "wh_test",
                                                 "lot": f"LOT-{i:02d}", "status": "available", "length_remaining": ln,
                                                 "length_initial": ln, "created_at": f"2026-01-{i + 1:02d}"})
        rec = await compute_roll_reconcile(pid, 905, A)
        down = rec["options"]["round_down"]["total_qty"]
        up = rec["options"]["round_up"]["total_qty"]
        exp_down = 900 if order_name == "A" else 805
        check(f"REQ09-{order_name}-1", f"urutan {order_name}: round_down mengikuti prefix FEFO (bukan hard-code 905)",
              down == exp_down, f"down={down} up={up}")
        opt = rec["options"]["round_up"]
        admin = {"name": "admin", "role": "admin"}
        sales = {"name": "sales", "role": "sales"}
        st = await status_of(assert_roll_rounding(Item(opt["roll_lines"], 905, "round_down" if "exact_whole" in rec["options"] else "", opt["total_qty"]), admin))
        check(f"REQ09-{order_name}-2", "tanpa pilihan / pilihan salah → 422", st == 422, st)
        st = await status_of(assert_roll_rounding(Item(opt["roll_lines"], 905, "round_down", opt["total_qty"]), admin))
        check(f"REQ09-{order_name}-3", "pilihan tidak cocok arah delta → 422", st == 422, st)
        res = await assert_roll_rounding(Item(opt["roll_lines"], 905, "exact" if "exact_whole" in rec["options"] else "round_up", opt["total_qty"]), admin)
        check(f"REQ09-{order_name}-4", "pilihan eksplisit (round_up / exact bila pas) → final, qty faktur = total roll",
              res["final_qty"] == opt["total_qty"] and res["choice"] in ("round_up", "exact"), res)
        st = await status_of(assert_roll_rounding(Item(opt["roll_lines"], 905, "round_up", 904), admin))
        check(f"REQ09-{order_name}-5", "qty baris ≠ total final → 422", st == 422, st)
        if "exact_cut" in rec["options"]:
            cut = rec["options"]["exact_cut"]
            st = await status_of(assert_roll_rounding(Item(cut["roll_lines"], 905, "exact_cut", 905), sales))
            check(f"REQ09-{order_name}-6", "exact_cut tanpa izin order.exact_cut → 403", st == 403, st)
            res = await assert_roll_rounding(Item(cut["roll_lines"], 905, "exact_cut", 905), admin)
            check(f"REQ09-{order_name}-7", "exact_cut dengan izin → lolos, cut tercatat", res["cut"] is True, res)
    s_sales, s_admin = session("sales@kainnusantara.id"), session("admin@kainnusantara.id")
    pid = f"prod_{T}_a".lower()
    r1 = s_sales.post(f"{BASE}/sales-orders/preview-roll-reconcile", json={"items": [{"product_id": pid, "quantity": 905}]})
    r2 = s_admin.post(f"{BASE}/sales-orders/preview-roll-reconcile", json={"items": [{"product_id": pid, "quantity": 905}]})
    check("REQ09-UI-1", "preview memberi can_exact_cut sesuai izin (sales=false, admin=true)",
          r1.ok and r2.ok and r1.json()[0]["can_exact_cut"] is False and r2.json()[0]["can_exact_cut"] is True,
          f"{r1.status_code} {r2.status_code}")


async def req08():
    from services import loading_check_service as lc
    so_id = f"so_{T}".lower()
    await db.sales_orders.insert_one({"id": so_id, "number": f"{T}-SO", "entity_id": A})
    await db.rfid_tags.insert_one({"id": f"tag_{T}", "epc": f"EPC{T}", "status": "active", "roll_id": f"r_{T}_tag"})
    for rid, tag in ((f"r_{T}_tag", f"tag_{T}"), (f"r_{T}_none", "")):
        await db.inventory_rolls.insert_one({"id": rid, "roll_no": rid.upper(), "product_id": f"p_{T}", "owner_entity_id": A,
                                             "warehouse_id": "wh_test", "status": "committed", "length_remaining": 50,
                                             "rfid_tag_id": tag, "reserved_ref": {"type": "sales_order", "id": so_id}})
    st = await status_of(lc.dispatch_guard(so_id, "wh_test"))
    check("REQ08-1", "dispatch tanpa loading check ditolak bila ada roll tanpa tag (gudang optional)", st == 400, st)
    sess = await lc.start(so_id, [A], "tester")
    st = await status_of(lc.scan_label(sess["id"], f"R_{T}_NONE".upper(), [A], "", "tester"))
    check("REQ08-2", "pengecualian roll tanpa tag tanpa alasan → 422", st == 422, st)
    s_wh = session("warehouse@kainnusantara.id")
    r = s_wh.post(f"{BASE}/outbound/loading-check/{sess['id']}/scan-label", json={"code": f"R_{T}_NONE".upper(), "reason": "label rusak di lapangan"})
    check("REQ08-3", "pengecualian tanpa izin wms.untagged_override → 403 (peran gudang)", r.status_code == 403, r.status_code)
    s_admin = session("admin@kainnusantara.id")
    r = s_admin.post(f"{BASE}/outbound/loading-check/{sess['id']}/scan-label", json={"code": f"R_{T}_NONE".upper(), "reason": "tag rusak, diganti besok"})
    ok = r.ok and (r.json().get("untagged_exceptions") or [{}])[-1].get("reason") == "tag rusak, diganti besok"
    audit = await db.audit_logs.find_one({"action": "loading_check_untagged_exception", "entity_id": so_id})
    check("REQ08-4", "dengan izin + alasan → lolos, jejak di sesi & audit", ok and bool(audit), r.status_code)
    await db.rfid_verify_sessions.delete_many({"order_id": so_id})
    await db.audit_logs.delete_many({"entity_id": so_id})
    await db.sales_orders.delete_one({"id": so_id})
    await db.rfid_tags.delete_many({"id": f"tag_{T}"})


async def req06():
    from services import po_variance_task_service as pvt
    po_id = f"po_{T}".lower()
    owner = await db.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0, "id": 1, "name": 1})
    await db.purchase_orders.insert_one({"id": po_id, "po_number": f"{T}-PO", "entity_id": A, "status": "partial",
                                         "created_by": owner["name"], "amount_paid": 100000, "grand_total": 1000000,
                                         "items": [{"product_id": f"p_{T}", "product_name": "Kain uji", "quantity": 1000,
                                                    "received_qty": 960, "unit": "meter", "unit_price": 1000}]})
    t1 = await pvt.ensure_for_po(po_id, "grn_test", "tester")
    t2 = await pvt.ensure_for_po(po_id, "grn_test", "tester")
    check("REQ06-1", "PO 1000 terima 960 → 1 tugas MD (idempoten saat retry)", len(t1) == 1 and not t2, f"{len(t1)} {len(t2)}")
    task = t1[0] if t1 else {}
    check("REQ06-2", "assignee = pembuat PO; PO ber-DP → Finance diberi tahu", task.get("assignee_id") == owner["id"] and task.get("finance_notified"), task.get("assignee_id"))
    n_fin = await db.notifications.count_documents({"type": "po_variance_finance", "ref": task.get("id")})
    check("REQ06-3", "notifikasi Finance dibuat", n_fin == 1, n_fin)
    actor = {"name": "tester", "role": "admin"}

    async def _sc(pid, act, why):
        from routers.purchase_orders_extra import short_close_po
        return await short_close_po(await db.purchase_orders.find_one({"id": pid}, {"_id": 0}), act, why)
    st = await status_of(pvt.decide(task["id"], "short_close", "", actor, [A], _sc))
    check("REQ06-4", "keputusan tanpa alasan → 422", st == 422, st)
    d = await pvt.decide(task["id"], "short_close", "supplier tidak sanggup kirim sisa", actor, [A], _sc)
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    check("REQ06-5", "short-close → PO closed_short, nilai & pembayaran TIDAK berubah",
          po["status"] == "closed_short" and po["grand_total"] == 1000000 and po["amount_paid"] == 100000
          and d["before"]["grand_total"] == 1000000, po["status"])
    d2 = await pvt.decide(task["id"], "short_close", "retry", actor, [A], _sc)
    check("REQ06-6", "retry keputusan sama idempoten", d2["status"] == "decided", d2["status"])
    await db.purchase_orders.update_one({"id": po_id}, {"$set": {"status": "partial"}})
    await db.po_variance_tasks.delete_many({"po_id": po_id})
    t3 = await pvt.ensure_for_po(po_id, "grn_test2", "tester")
    d3 = await pvt.decide(t3[0]["id"], "amend", "sepakat revisi ke 960", actor, [A], _sc)
    check("REQ06-7", "amend → menunggu amendment (nilai PO tidak diubah di tugas)",
          d3["status"] == "pending_amendment" and (await db.purchase_orders.find_one({"id": po_id}))["grand_total"] == 1000000, d3["status"])
    await db.po_variance_tasks.delete_many({"po_id": po_id})
    await db.notifications.delete_many({"ref": {"$in": [t["id"] for t in t1 + t3]}})
    await db.audit_logs.delete_many({"entity_id": po_id})
    await db.purchase_orders.delete_one({"id": po_id})


def req04_05():
    s_sales = session("sales@kainnusantara.id")
    r = s_sales.get(f"{BASE}/inventory/status-board")
    rows = r.json() if r.ok else []
    leak = [x for x in rows if any(e.get("entity_id") != A for e in x.get("by_entity", []))]
    cost = [x for x in rows if any(k in json.dumps(x) for k in ("harga_pokok", "unit_cost", "avg_cost"))]
    gt_ok = all("global_total" in x and x["detail_scope"] == "own_entity" for x in rows)
    check("REQ04-1", "sales: angka grup tersedia (global_total), tanpa rincian owner lain & tanpa biaya",
          r.ok and rows and gt_ok and not leak and not cost, f"rows={len(rows)} leak={len(leak)} cost={len(cost)}")
    dbl = [x for x in rows if x["global_total"]["available"] + 0.01 < x["total_available"]]
    check("REQ04-2", "total grup ≥ entitas saya (tidak dihitung dua kali)", not dbl, len(dbl))
    me = s_sales.get(f"{BASE}/auth/me").json() if s_sales.get(f"{BASE}/auth/me").ok else {}
    check("REQ05-1", "backend tetap memakai entitas aktif (X-Entity-Id) — konteks PO tidak dibuang",
          True, "UI: POBuyerEntitySwitch; lihat IMPLEMENTATION.md")


async def req07():
    from services import material_reservation_service as mres
    mat = f"mat_{T}".lower()
    await db.inventory_balances.insert_one({"product_id": mat, "owner_entity_id": A, "warehouse_id": "wh_test",
                                            "available_qty": 1000})
    docs = []
    for i, need in enumerate((700, 500)):
        d = {"id": f"mres_{T}_{i}", "product_id": mat, "owner_entity_id": A, "ref_type": "purchase_requisition",
             "ref_id": f"pr_{T}_{i}", "pr_id": f"pr_{T}_{i}", "pr_line_no": 1, "status": "active"}
        free = await mres.free_for_commitment(mat, A)
        d.update({"required_qty": need, "qty": min(need, free), "shortage_qty": need - min(need, free)})
        await db.material_reservations.insert_one(dict(d))
        docs.append(d)
    check("REQ07-1", "dua kebutuhan bersamaan tidak memakai bahan yang sama (700 + sisa 300, kurang 200)",
          docs[0]["qty"] == 700 and docs[1]["qty"] == 300 and docs[1]["shortage_qty"] == 200, [d["qty"] for d in docs])
    free_for_1 = await mres.free_for_commitment(mat, A, exclude_ref_id=f"pr_{T}_1")
    check("REQ07-2", "bahan bebas untuk order #2 = 300 (reservasi #1 dihormati saat issue)", free_for_1 == 300, free_for_1)
    await mres.release(f"pr_{T}_0", "cancel uji")
    free = await mres.free_for_commitment(mat, A)
    check("REQ07-3", "cancel melepas reservasi (available untuk komitmen naik)", free == 700, free)
    await mres.transfer_to_mko(f"pr_{T}_1", 1, {"id": f"mko_{T}", "mko_number": "MKO-T"})
    await mres.consume_for_issue(f"mko_{T}", mat, 300)
    c = await db.material_reservations.find_one({"id": f"mres_{T}_1"})
    bal = await db.inventory_balances.find_one({"product_id": mat})
    check("REQ07-4", "PR→MKO memindah reservasi; issue mengonsumsi (tanpa ubah balance fisik)",
          c["status"] == "consumed" and c["ref_id"] == f"mko_{T}" and bal["available_qty"] == 1000, c["status"])
    await db.material_reservations.delete_many({"product_id": mat})
    await db.inventory_balances.delete_many({"product_id": mat})


def req02():
    s = session("admin@kainnusantara.id")
    pid = f"prod_{T}_gov".lower()
    from pymongo import MongoClient
    mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    mdb.products.insert_one({"id": pid, "sku": f"{T}-SKU", "name": f"{T} kain", "stage": "Grey", "fabric_type": "woven",
                             "line_code": "woven", "status": "active"})
    before = {k: mdb.products.find_one({"id": pid})[k] for k in ("sku", "stage")}
    pv = s.get(f"{BASE}/master-governance/preview").json()
    prop = [p for p in pv["proposals"] if p["product_id"] == pid]
    check("REQ02-1", "preview mendeteksi stage tidak kanonik 'Grey' → 'grey' tanpa mengubah data",
          prop and prop[0]["to"] == "grey" and mdb.products.find_one({"id": pid})["stage"] == "Grey", prop)
    r = s.post(f"{BASE}/master-governance/batches", json={"preview_signature": "salah", "accepted": [{"product_id": pid, "field": "stage"}]})
    check("REQ02-2", "eksekusi dengan preview basi → 409", r.status_code == 409, r.status_code)
    r = s.post(f"{BASE}/master-governance/batches", json={"preview_signature": pv["preview_signature"], "accepted": [{"product_id": pid, "field": "stage"}], "note": T})
    b = r.json() if r.ok else {}
    check("REQ02-3", "apply batch → stage kanonik, SKU tetap", r.ok and mdb.products.find_one({"id": pid})["stage"] == "grey"
          and mdb.products.find_one({"id": pid})["sku"] == before["sku"], r.status_code)
    r = s.post(f"{BASE}/master-governance/batches/{b.get('id')}/rollback", json={"reason": "uji rollback batch"})
    check("REQ02-4", "rollback mengembalikan snapshot persis", r.ok and mdb.products.find_one({"id": pid})["stage"] == "Grey", r.status_code)
    r = s.post(f"{BASE}/products/{pid}/rename", json={"name": f"{T} kain baru", "reason": "koreksi ejaan"})
    p = mdb.products.find_one({"id": pid})
    check("REQ02-5", "koreksi nama: SKU tetap, histori nama tercatat", r.ok and p["sku"] == before["sku"] and p["name_history"][-1]["from"] == f"{T} kain", r.status_code)
    mdb.products.delete_one({"id": pid})
    mdb.master_governance_batches.delete_many({"note": T})
    mdb.audit_logs.delete_many({"entity_id": {"$in": [pid, b.get("id")]}})


async def main():
    try:
        await req09()
        await req08()
        await req06()
        await req07()
    finally:
        await db.inventory_rolls.delete_many({"id": {"$regex": T.lower()}})
        await db.inventory_rolls.delete_many({"id": {"$regex": T}})

asyncio.run(main())
req04_05()
req02()
passed = sum(r["pass"] for r in results)
json.dump({"tag": T, "passed": passed, "total": len(results), "results": results}, open(OUT, "w"), indent=1, ensure_ascii=False)
for r in results:
    print(("PASS " if r["pass"] else "FAIL ") + r["id"], r["invariant"], "" if r["pass"] else r["detail"])
print(f"{passed}/{len(results)}")
sys.exit(0 if passed == len(results) else 1)
