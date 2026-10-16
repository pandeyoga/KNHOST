"""Lanjutan 2026-10-05: FN-02 kunci baris PO (line_code = LINI, bukan id baris), konteks tagihan per
baris, label roll anak, laporan Hutang Reimburse.

Usage: cd /app/backend && python ../audit/iterations/2026-10-05-P05-coa-reports-close/repro_followup3.py
Data sintetis ber-prefix `audit_f3_*` dihapus di akhir. Memanggil server lokal (REACT_APP_BACKEND_URL).
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


async def main():
    import requests
    from db import db
    from core_utils import now_iso
    from services import vendor_bill_service as vbs
    T = f"audit_f3_{uuid.uuid4().hex[:6]}"
    A = "ent_ksc"
    base = [ln.split("=", 1)[1].strip() for ln in open("../frontend/.env") if ln.startswith("REACT_APP_BACKEND_URL")][0] + "/api"
    s = requests.Session()
    s.post(f"{base}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=20)
    s.headers["X-Entity-Id"] = A
    sup = await db.suppliers.find_one({"entity_id": A}, {"_id": 0, "id": 1, "name": 1}) or \
        await db.suppliers.find_one({}, {"_id": 0, "id": 1, "name": 1})
    po_id = f"{T}_po"
    try:
        # ── FN-02: dua produk BERBEDA dengan lini sama + satu produk di dua baris ───
        await db.purchase_orders.insert_one({
            "id": po_id, "po_number": f"PO-{T}", "entity_id": A, "supplier_id": sup["id"], "supplier_name": sup["name"],
            "status": "received", "tax_mode": "exclude", "created_at": now_iso(), "items": [
                {"product_id": f"{T}_a", "product_name": "A", "line_code": "woven", "quantity": 10, "received_qty": 10, "price": 100000},
                {"product_id": f"{T}_b", "product_name": "B", "line_code": "woven", "quantity": 20, "received_qty": 20, "price": 900000},
                {"product_id": f"{T}_c", "product_name": "C1", "line_code": "printing", "quantity": 5, "received_qty": 5, "price": 50000},
                {"product_id": f"{T}_c", "product_name": "C2", "line_code": "printing", "quantity": 7, "received_qty": 7, "price": 80000}]})
        po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
        m = vbs.evaluate_match(po, [{"product_id": f"{T}_b", "billed_qty": 20, "price": 900000}], "received", {}, 0, 5)
        mi = m["items"][0]["match"]
        check("FN-02", "produk B tidak tertukar dgn produk A berlini sama (sisa = qty baris B)",
              m["match_status"] == "matched" and mi["qty_remaining"] == 20 and mi["price_variance_pct"] == 0, (m["match_status"], mi))
        ctx = s.get(f"{base}/purchase-orders/{po_id}/billing-context", timeout=20).json()
        ids = [i["po_line_id"] for i in ctx["items"]]
        check("FN-02", "konteks tagihan memberi id baris unik per baris PO", len(set(ids)) == 4, ids)
        check("FN-02", "produk ganda ditandai same_product_lines=2", [i["same_product_lines"] for i in ctx["items"]] == [1, 1, 2, 2], "")
        stored = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0, "items.line_id": 1})
        check("FN-02", "line_id tersimpan permanen di PO", [i.get("line_id") for i in stored["items"]] == ids, stored)
        body = {"po_id": po_id, "match_mode": "received", "entity_id": A, "submit_now": False, "items": [
            {"product_id": f"{T}_a", "billed_qty": 10, "price": 100000},
            {"product_id": f"{T}_c", "po_line_id": ids[3], "billed_qty": 7, "price": 80000}]}
        r1 = s.post(f"{base}/vendor-bills", json={**body, "submit_now": True}, timeout=30)  # draf tidak me-reserve qty
        check("FN-02", "tagihan dgn pilihan baris PO diterima & cocok", r1.status_code == 200 and r1.json().get("match_status") == "matched" and r1.json().get("status") != "draft",
              (r1.status_code, r1.text[:200]))
        ctx2 = s.get(f"{base}/purchase-orders/{po_id}/billing-context", timeout=20).json()
        rem = {i["po_line_id"]: i["billable_received"] for i in ctx2["items"]}
        check("FN-02", "sisa tagih per baris: A 0, B 20 (tidak ikut berkurang), C1 5, C2 0",
              rem == {ids[0]: 0, ids[1]: 20, ids[2]: 5, ids[3]: 0}, rem)
        r2 = s.post(f"{base}/vendor-bills", json={**body, "items": [{"product_id": f"{T}_c", "billed_qty": 1, "price": 50000}]}, timeout=30)
        check("FN-02", "produk di >1 baris tanpa po_line_id → 400", r2.status_code == 400, r2.status_code)
        r3 = s.post(f"{base}/vendor-bills", json={**body, "items": [{"product_id": f"{T}_c", "po_line_id": ids[3], "billed_qty": 7, "price": 80000}]}, timeout=30)
        rj = r3.json() if r3.status_code == 200 else {}
        check("FN-02", "tagih ulang baris C2 yang sudah penuh → over-billed", r3.status_code == 400 or rj.get("match_status") == "blocked",
              (r3.status_code, rj.get("match_status")))
        if r3.status_code == 200:
            await db.vendor_bills.delete_one({"id": rj["id"]})

        # ── Label roll anak: konteks label ─────────────────────────────────
        rid = f"{T}_kid"
        prod = await db.products.find_one({}, {"_id": 0, "id": 1, "name": 1})
        await db.inventory_rolls.insert_many([
            {"id": f"{T}_par", "roll_no": f"R-{T}", "product_id": prod["id"], "warehouse_id": "wh_jakarta", "owner_entity_id": A,
             "status": "available", "length_remaining": 40.0, "unit": "meter"},
            {"id": rid, "roll_no": f"R-{T}-1", "product_id": prod["id"], "warehouse_id": "wh_jakarta", "owner_entity_id": A,
             "status": "reserved", "length_remaining": 10.0, "unit": "meter", "parent_roll_id": f"{T}_par",
             "cut": {"identity_verified": False}, "rfid_tag_id": None}])
        kid = next((i for i in s.get(f"{base}/inventory/cut-children-unverified", timeout=20).json()["items"] if i["id"] == rid), {})
        check("LABEL", "roll anak memuat nama produk & no. roll induk untuk label", kid.get("product_name") == prod["name"]
              and kid.get("parent_roll_no") == f"R-{T}", kid)

        # ── Laporan Hutang Reimburse ───────────────────────────────────────
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        mk = lambda n, emp, amt, days, st="open": {  # noqa: E731
            "id": f"{T}_stl{n}", "number": f"STL-{T}-{n}", "entity_id": A, "status": "posted_to_gl", "dibuat_oleh": emp,
            "approved_at": (now - timedelta(days=days)).isoformat(), "hutang_reimburse": {"amount": amt, "status": st}}
        await db.cash_advance_settlements.insert_many([mk(1, f"{T} Andi", 100, 3), mk(2, f"{T} Andi", 50, 20),
                                                       mk(3, f"{T} Sari", 70, 45), mk(4, f"{T} Sari", 999, 2, "paid")])
        rp = s.get(f"{base}/cash-advance-settlements/reimburse-payables", timeout=20).json()
        mine = {e["employee"]: e for e in rp["by_employee"] if e["employee"].startswith(T)}
        check("REIMB", "hanya hutang terbuka dihitung (yang dibayar tidak)", mine.get(f"{T} Sari", {}).get("outstanding") == 70, mine)
        check("REIMB", "umur 0-7 / 15-30 per karyawan", mine.get(f"{T} Andi", {}).get("aging") == {"0-7": 100, "8-14": 0, "15-30": 50, ">30": 0},
              mine.get(f"{T} Andi"))
        check("REIMB", "hutang terlama (>30) Sari 45 hari", mine.get(f"{T} Sari", {}).get("oldest_days") == 45
              and mine[f"{T} Sari"]["aging"][">30"] == 70, mine.get(f"{T} Sari"))
        fin = requests.Session()
        fin.post(f"{base}/auth/login", json={"email": "warehouse@kainnusantara.id", "password": "demo12345"}, timeout=20)
        r = fin.get(f"{base}/cash-advance-settlements/reimburse-payables", headers={"X-Entity-Id": A}, timeout=20)
        check("REIMB", "role gudang tidak boleh melihat laporan (403)", r.status_code == 403, r.status_code)
    finally:
        await db.vendor_bills.delete_many({"po_id": po_id})
        await db.purchase_orders.delete_many({"id": po_id})
        await db.inventory_rolls.delete_many({"id": {"$regex": f"^{T}"}})
        await db.cash_advance_settlements.delete_many({"id": {"$regex": f"^{T}"}})
    npass = sum(r["pass"] for r in results)
    print(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"pass={npass} fail={len(results) - npass}")


asyncio.run(main())
