"""Lanjutan 2026-10-04: verifikasi label roll anak, bayar Hutang Reimburse (2-1650), match per baris PO
(+ serialisasi tagihan bersamaan), lencana jumlah posting gagal.

Usage: cd /app/backend && python ../audit/iterations/2026-10-04-label-reimburse-poline-badge/repro_followup2.py
Data sintetis ber-prefix `audit_f2_*` / entitas `ent_audit_f2_*` dihapus di akhir.
"""
import asyncio
import json
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


def err(exc):
    return getattr(exc, "status_code", type(exc).__name__), str(getattr(exc, "detail", exc))[:160]


async def main():
    import requests
    from db import db
    from core_utils import now_iso
    from services import roll_service as rs
    T = f"audit_f2_{uuid.uuid4().hex[:6]}"
    E = f"ent_audit_f2_{T[-6:]}"
    A = "ent_ksc"
    base = [ln.split("=", 1)[1].strip() for ln in open("../frontend/.env") if ln.startswith("REACT_APP_BACKEND_URL")][0] + "/api"
    s = requests.Session()
    s.post(f"{base}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=20)
    s.headers["X-Entity-Id"] = A
    try:
        # ── Verifikasi label roll anak ────────────────────────────────────
        rid = f"{T}_kid"
        so = f"so_{T}"
        await db.inventory_rolls.insert_one({"id": rid, "roll_no": f"R-{T}-1", "product_id": f"{T}_p", "warehouse_id": "wh_jakarta",
                                             "owner_entity_id": A, "status": "reserved", "length_remaining": 10.0,
                                             "length_initial": 10.0, "unit": "meter", "reserved_ref": {"type": "sales_order", "id": so},
                                             "cut": {"identity_verified": False}, "rfid_tag_id": None})
        lst = s.get(f"{base}/inventory/cut-children-unverified", timeout=20).json()
        check("LABEL", "daftar roll anak belum terverifikasi memuat roll", any(i["id"] == rid for i in lst.get("items", [])), "")
        bad = s.post(f"{base}/inventory/rolls/{rid}/verify-identity", json={"scanned_code": "R-SALAH"}, timeout=20)
        check("LABEL", "label salah → 400, identitas tetap belum sah", bad.status_code == 400, bad.status_code)
        try:
            await rs.assert_cut_identity_ready(so)
            check("LABEL", "gate muat masih menolak sebelum verifikasi", False, "lolos")
        except Exception as exc:  # noqa: BLE001
            check("LABEL", "gate muat masih menolak sebelum verifikasi", err(exc)[0] == 409, err(exc))
        ok = s.post(f"{base}/inventory/rolls/{rid}/verify-identity", json={"scanned_code": f" r-{T}-1 "}, timeout=20)
        again = s.post(f"{base}/inventory/rolls/{rid}/verify-identity", json={"scanned_code": f"R-{T}-1"}, timeout=20)
        await rs.assert_cut_identity_ready(so)
        doc = await db.inventory_rolls.find_one({"id": rid}, {"_id": 0, "cut": 1})
        check("LABEL", "label cocok → sah (label_scan), gate lolos, verifikasi ulang 409",
              ok.status_code == 200 and again.status_code == 409 and doc["cut"]["verified_via"] == "label_scan",
              {"ok": ok.status_code, "again": again.status_code})

        # ── Bayar Hutang Reimburse ────────────────────────────────────────
        from services import cash_advance_service as ca
        from services import gl_service as gl
        from entity_scope import EntityContext
        actor = {"id": "u", "name": "auditor", "role": "admin"}
        ctx = EntityContext(user=actor, active_entity_id=E, allowed_entity_ids=[E])
        ca_id = f"ca_{T}"
        await db[ca.CA_COLL].insert_one({"id": ca_id, "number": f"PD-{T}", "entity_id": E, "status": "approved",
                                         "total_amount": 100.0, "kegiatan": "audit", "approvals": []})

        class D:
            cash_type = "kas_kecil"; txn_date = None; note = ""
        await ca.disburse_cash_advance(ca_id, D, ctx, actor)

        class S:
            cash_advance_id = ca_id; expense_lines = [{"category": "petty_cash_lain", "amount": 130, "description": "x"}]
            divisi = ""; periode = ""; dibuat_oleh = ""; catatan = ""
        stl = await ca.create_settlement(S, ctx, actor)
        stl = await ca.approve_settlement(stl["id"], ctx, actor)
        check("REIMB", "LPJ 130 atas PD 100 → hutang_reimburse terbuka 30",
              stl["hutang_reimburse"] == {"amount": 30.0, "status": "open", "cash_txn_id": "", "paid_at": ""}, stl.get("hutang_reimburse"))

        class Pay:
            cash_type = "kas_besar"; txn_date = None
        orig = gl.post_cash_transaction

        async def boom(*a, **k):
            raise RuntimeError("fault injection GL")
        gl.post_cash_transaction = boom
        try:
            await ca.pay_reimburse(stl["id"], Pay, ctx, actor)
        except Exception:  # noqa: BLE001
            pass
        gl.post_cash_transaction = orig
        paid = await ca.pay_reimburse(stl["id"], Pay, ctx, actor)
        n_cash = await db.cash_transactions.count_documents({"ref_type": "reimburse_payable", "ref_id": stl["id"]})
        bal = 0.0
        async for je in db.journal_entries.find({"entity_id": E, "status": {"$ne": "void"}}, {"lines": 1}):
            for ln in je["lines"]:
                if ln["account_code"] == "2-1650":
                    bal += ln["credit"] - ln["debit"]
        check("REIMB", "bayar (setelah 1× gagal GL) → satu kas 30, status paid, saldo 2-1650 = 0",
              paid["hutang_reimburse"]["status"] == "paid" and n_cash == 1 and round(bal, 2) == 0, {"cash": n_cash, "bal": bal})
        try:
            await ca.pay_reimburse(stl["id"], Pay, ctx, actor)
            check("REIMB", "bayar kedua ditolak", False, "diterima")
        except Exception as exc:  # noqa: BLE001
            check("REIMB", "bayar kedua ditolak", err(exc)[0] == 409, err(exc))

        # ── Match per baris PO ────────────────────────────────────────────
        from services.vendor_bill_service import evaluate_match, already_billed_map
        pid = f"{T}_prod"
        po2 = {"id": f"{T}_po2", "items": [
            {"product_id": pid, "line_code": "L1", "quantity": 100, "received_qty": 100, "price": 10},
            {"product_id": pid, "line_code": "L2", "quantity": 50, "received_qty": 50, "price": 12}]}
        m = evaluate_match(po2, [{"product_id": pid, "po_line_code": "L1", "billed_qty": 100, "price": 10},
                                 {"product_id": pid, "po_line_code": "L2", "billed_qty": 50, "price": 12}], "received", {}, 0, 0)
        check("POLINE", "produk sama di dua baris/harga: 100@10 + 50@12 → matched, harga PO per baris benar",
              m["match_status"] == "matched" and [i["po_price"] for i in m["items"]] == [10, 12], m["match_status"])
        m2 = evaluate_match(po2, [{"product_id": pid, "po_line_code": "L2", "billed_qty": 60, "price": 12}], "received", {}, 0, 0)
        check("POLINE", "tagih 60 pada baris L2 (diterima 50) → blocked", m2["match_status"] == "blocked", m2["match_status"])
        await db.purchase_orders.insert_one({**po2, "entity_id": E})
        await db.vendor_bills.insert_one({"id": f"{T}_vb", "po_id": po2["id"], "status": "posted", "entity_id": E,
                                          "items": [{"product_id": pid, "po_line_code": "L1", "billed_qty": 70}]})
        bm = await already_billed_map(po2["id"])
        check("POLINE", "sisa tertagih dihitung per baris PO", bm == {"L1": 70.0}, bm)
        # HTTP: dua tagihan bersamaan atas PO yang sama tidak melebihi diterima
        prod = await db.products.find_one({}, {"_id": 0, "id": 1})
        po_http = {"id": f"{T}_poh", "po_number": f"PO-{T}", "entity_id": A, "status": "received", "supplier_id": "",
                   "items": [{"product_id": prod["id"], "line_code": "LH1", "quantity": 100, "received_qty": 100,
                              "price": 100000, "unit": "meter", "sku": "", "product_name": "x"}]}
        await db.purchase_orders.insert_one(dict(po_http))
        body = {"po_id": po_http["id"], "submit_now": True, "items": [{"product_id": prod["id"], "billed_qty": 60}]}

        def post(_):
            return s.post(f"{base}/vendor-bills", json=body, timeout=60)
        with ThreadPoolExecutor(2) as ex:
            rs_ = list(ex.map(post, [1, 2]))
        seq = s.post(f"{base}/vendor-bills", json=body, timeout=60)
        tot = 0.0
        async for b in db.vendor_bills.find({"po_id": po_http["id"], "status": {"$in": ["pending_approval", "posted", "paid"]}}):
            tot += sum(float(i.get("billed_qty") or 0) for i in b.get("items", []))
        check("POLINE", "2 tagihan 60 bersamaan + 1 berurutan → Σ tagihan aktif ≤ diterima 100",
              tot <= 100 + 1e-6, {"codes": [r.status_code for r in rs_] + [seq.status_code], "total": tot})

        # ── Lencana posting gagal ─────────────────────────────────────────
        c0 = s.get(f"{base}/finance/posting-failures/count", timeout=20).json().get("total", -1)
        cid = f"cash_{T}"
        await db.cash_transactions.insert_one({"id": cid, "number": f"CASH-{T}", "entity_id": A, "gl_status": "failed",
                                               "amount": 1.0, "status": "posted", "updated_at": now_iso()})
        c1 = s.get(f"{base}/finance/posting-failures/count", timeout=20).json().get("total", -1)
        await db.cash_transactions.delete_one({"id": cid})
        check("BADGE", "count naik 1 saat ada kas gagal", c1 == c0 + 1, {"before": c0, "after": c1})
    finally:
        await db.inventory_rolls.delete_many({"id": {"$regex": f"^{T}"}})
        for c in ("journal_entries", "cash_transactions", "cash_advances", "cash_advance_settlements", "purchase_orders",
                  "vendor_bills", "number_sequences"):
            await db[c].delete_many({"entity_id": E})
        bills = [b["id"] async for b in db.vendor_bills.find({"po_id": f"{T}_poh"}, {"id": 1})]
        await db.journal_entries.delete_many({"source_id": {"$in": bills}})
        await db.vendor_bills.delete_many({"po_id": f"{T}_poh"})
        await db.purchase_orders.delete_many({"id": f"{T}_poh"})
        await db.doc_refs.delete_many({"$or": [{"from_id": {"$in": bills}}, {"to_id": {"$in": bills}}]})
    passed = sum(1 for r in results if r["pass"])
    print(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"pass={passed} fail={len(results) - passed}")


try:
    asyncio.run(main())
except Exception as _exc:  # noqa: BLE001
    passed = sum(1 for r_ in results if r_["pass"])
    print(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"CRASH (kontrak belum ada di kode ini): {type(_exc).__name__}: {_exc}")
    print(f"pass={passed} fail={len(results) - passed} crashed=1")
