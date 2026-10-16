"""WM-02 lanjutan (tag roll anak sebelum muat/kirim, picker panjang bebas, beli-per-roll sebagian)
+ CX-05 (kelebihan LPJ → Hutang Reimburse) + Panel Posting Gagal (HTTP).

Usage: cd /app/backend && python ../audit/iterations/2026-10-03-WM02-identity-CX05-panel/repro_followup.py
Data sintetis ber-prefix `audit_fu_*` dihapus di akhir.
"""
import asyncio
import json
import os
import sys
import uuid

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


def err(exc):
    return getattr(exc, "status_code", type(exc).__name__), str(getattr(exc, "detail", exc))[:160]


async def main():
    from db import db
    from core_utils import now_iso
    from services import roll_service as rs
    T = f"audit_fu_{uuid.uuid4().hex[:6]}"
    A, W = "ent_ksc", "wh_jakarta"
    pid = f"{T}_prod"
    so = f"so_{T}"
    await db.products.insert_one({"id": pid, "sku": f"SKU-{T}", "name": "Synthetic FU", "base_unit": "meter"})
    r = {"id": f"{T}_r0", "roll_no": f"R-{T}-0", "product_id": pid, "warehouse_id": W, "owner_entity_id": A,
         "status": "available", "length_initial": 100.0, "length_remaining": 100.0, "unit": "meter",
         "rfid_tag_id": f"tag_{T}", "lot": "L1", "created_at": "2026-10-03T00:00:00+00:00"}
    try:
        await db.inventory_rolls.insert_one(dict(r))
        await db.sales_orders.insert_one({"id": so, "number": f"SO-{T}", "entity_id": A})
        allocs = await rs.allocate_and_reserve_rolls(pid, 30, "Jakarta", A, so)
        rid = allocs[0]["rolls"][0]["reservation_id"]
        # Picker panjang bebas
        pk = await rs.list_available_rolls(product_id=pid, owner_entity_id=A, all_entities=False, sort="fefo",
                                           skip=0, limit=50, warehouse_id="")
        it = next((i for i in pk["items"] if i["id"] == r["id"]), None)
        check("WM-02b", "picker menampilkan induk dengan panjang bebas 70 (fisik 100, dipesan 30)",
              it and it["length_remaining"] == 70 and it["physical_length"] == 100 and it["length_reserved"] == 30, it)
        # Beli-per-roll sebagian (reserve_specific_rolls, ref SO) → reservasi panjang, bukan roll anak
        so2 = f"so2_{T}"
        got = await rs.reserve_specific_rolls([{"roll_id": r["id"], "take_qty": 20}], {"type": "sales_order", "id": so2}, pid)
        n = await db.inventory_rolls.count_documents({"product_id": pid})
        p = await db.inventory_rolls.find_one({"id": r["id"]}, {"_id": 0})
        check("WM-02b", "beli 20 dari roll (mode per roll) → tanpa roll baru, dipesan 50",
              n == 1 and p["length_reserved"] == 50 and got[0]["length_remaining"] == 20, {"rolls": n, "reserved": p["length_reserved"]})
        try:
            await rs.reserve_specific_rolls([{"roll_id": r["id"], "take_qty": 60}], {"type": "sales_order", "id": so2 + "x"}, pid)
            check("WM-02b", "beli melebihi panjang bebas ditolak", False, "diterima")
        except Exception as exc:  # noqa: BLE001
            check("WM-02b", "beli melebihi panjang bebas ditolak", err(exc)[0] == 400, err(exc))
        await rs.release_order_rolls(so2)
        # Gate: dispatch sebelum potong
        try:
            await rs.ship_order_rolls(so, pid, W, 30)
            check("WM-02a", "dispatch sebelum potong → 409", False, "terkirim")
        except Exception as exc:  # noqa: BLE001
            check("WM-02a", "dispatch sebelum potong → 409", err(exc)[0] == 409, err(exc))
        out = await rs.confirm_cut(r["id"], rid, 30, 0, actor="t")
        child = out["child"]
        from services import loading_check_service as lc
        for label, coro in (("loading check", lc.start(so, [A], "t")), ("dispatch", rs.ship_order_rolls(so, pid, W, 30))):
            try:
                await coro
                check("WM-02a", f"{label} dengan roll anak belum ber-tag → 409", False, "lolos")
            except Exception as exc:  # noqa: BLE001
                check("WM-02a", f"{label} dengan roll anak belum ber-tag → 409",
                      err(exc)[0] == 409 and "belum ber-tag" in err(exc)[1], err(exc))
        n0 = await rs.mark_cut_identity_verified([child["id"]], "rfid_verify", "sess")
        check("WM-02a", "verifikasi tanpa tag tidak mengesahkan identitas", n0 == 0, n0)
        await db.inventory_rolls.update_one({"id": child["id"]}, {"$set": {"rfid_tag_id": f"tag_{T}_c"}})
        await rs.mark_cut_identity_verified([child["id"]], "rfid_verify", "sess")
        shipped = await rs.ship_order_rolls(so, pid, W, 30)
        check("WM-02a", "setelah tag baru terverifikasi → dispatch berhasil", shipped["shipped"] == 30, shipped["shipped"])
        src = open("services/rfid_print_service.py").read()
        check("WM-02a", "complete_verify mengesahkan identitas roll anak (statis)", "mark_cut_identity_verified" in src, "")

        # ── CX-05 — kelebihan LPJ ────────────────────────────────────────
        from services import gl_service as gl
        E = f"ent_audit_fu_{T[-6:]}"
        je = await gl.post_petty_cash_settlement(settlement_id=f"stl_{T}", entity_id=E, label="uji",
                                                 category_lines=[{"account_code": "6-1000", "amount": 130}],
                                                 advance_amount=100)
        lines = {(ln["account_code"], ln["credit"]) for ln in (je or {}).get("lines", []) if ln["credit"]}
        check("CX-05", "LPJ 130 atas uang muka 100 → Cr Uang Muka 100 + Cr 2-1650 Hutang Reimburse 30",
              lines == {("1-1400", 100.0), ("2-1650", 30.0)}, sorted(lines))
        await db.journal_entries.delete_many({"entity_id": E})

        # ── Panel Posting Gagal (HTTP) ─────────────────────────────────────
        import requests
        # Cookie sesi ber-flag Secure → pakai URL eksternal (https) dari frontend/.env
        base = [ln.split("=", 1)[1].strip() for ln in open("../frontend/.env") if ln.startswith("REACT_APP_BACKEND_URL")][0] + "/api"
        s = requests.Session()
        s.post(f"{base}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=20)
        s.headers["X-Entity-Id"] = A
        cid = f"cash_{T}"
        await db.cash_transactions.insert_one({"id": cid, "number": f"CASH-{T}", "cash_type": "kas_besar",
                                               "direction": "in", "amount": 777.0, "category": "audit", "entity_id": A,
                                               "status": "posted", "ref_type": "", "ref_id": "", "txn_date": now_iso(),
                                               "gl_status": "failed", "gl_error": "fault injection", "updated_at": now_iso()})
        lst = s.get(f"{base}/finance/posting-failures", timeout=30).json()
        check("PANEL", "daftar memuat kas gagal", any(i["id"] == cid for i in lst.get("items", [])), lst.get("counts"))
        rr = s.post(f"{base}/finance/posting-failures/cash_transaction/{cid}/retry", timeout=30)
        rr2 = s.post(f"{base}/finance/posting-failures/cash_transaction/{cid}/retry", timeout=30)
        njes = await db.journal_entries.count_documents({"source_type": "cash_transaction", "source_id": cid})
        check("PANEL", "ulang posting → posted, satu jurnal; ulang kedua 404 (sudah terposting)",
              rr.status_code == 200 and rr.json().get("gl_status") == "posted" and rr2.status_code == 404 and njes == 1,
              {"r1": rr.status_code, "r2": rr2.status_code, "jes": njes})
        s2 = requests.Session()
        s2.post(f"{base}/auth/login", json={"email": "sales@kainnusantara.id", "password": "demo12345"}, timeout=20)
        check("PANEL", "role sales tidak boleh melihat panel", s2.get(f"{base}/finance/posting-failures", timeout=20).status_code == 403, "")
        await db.journal_entries.delete_many({"source_id": cid})
        await db.cash_transactions.delete_one({"id": cid})
    finally:
        await db.inventory_rolls.delete_many({"product_id": pid})
        await db.inventory_balances.delete_many({"product_id": pid})
        await db.inventory_movements.delete_many({"product_id": pid})
        await db.products.delete_one({"id": pid})
        await db.sales_orders.delete_many({"id": {"$regex": f"^so_{T}"}})
    passed = sum(1 for r_ in results if r_["pass"])
    print(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"pass={passed} fail={len(results) - passed}")
    _ = os


try:
    asyncio.run(main())
except Exception as _exc:  # noqa: BLE001
    passed = sum(1 for r_ in results if r_["pass"])
    print(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"CRASH (kontrak belum ada di kode ini): {type(_exc).__name__}: {_exc}")
    print(f"pass={passed} fail={len(results) - passed} crashed=1")
