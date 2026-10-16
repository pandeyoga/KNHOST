"""WM-02 invariants — reservasi parsial tidak melahirkan roll anak sebelum potong fisik.

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-02-P02-wm02-reservation/repro_wm02.py
Data sintetis ber-prefix `audit_wm02_*` dihapus di akhir.
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
    from db import db
    from services import roll_service as rs
    T = f"audit_wm02_{uuid.uuid4().hex[:6]}"
    A, W = "ent_ksc", "wh_jakarta"
    pid = f"{T}_prod"
    so1, so2 = f"so_{T}_1", f"so_{T}_2"
    await db.products.insert_one({"id": pid, "sku": f"SKU-{T}", "name": "Synthetic WM02", "base_unit": "meter"})
    r = {"id": f"{T}_r0", "roll_no": f"R-{T}-0", "product_id": pid, "warehouse_id": W, "owner_entity_id": A,
         "status": "available", "length_initial": 100.0, "length_remaining": 100.0, "unit": "meter",
         "rfid_tag_id": f"tag_{T}", "lot": "L1", "created_at": "2026-10-02T00:00:00+00:00"}
    try:
        await db.inventory_rolls.insert_one(dict(r))
        allocs = await rs.allocate_and_reserve_rolls(pid, 30, "Jakarta", A, so1)
        n_rolls = await db.inventory_rolls.count_documents({"product_id": pid})
        parent = await db.inventory_rolls.find_one({"id": r["id"]}, {"_id": 0})
        check("WM-02", "reserve 30 dari roll 100 TIDAK membuat roll baru", n_rolls == 1, {"rolls": n_rolls})
        check("WM-02", "induk tetap 100 fisik, 30 dipesan, tag induk tetap",
              parent["length_remaining"] == 100 and parent.get("length_reserved") == 30 and parent["rfid_tag_id"],
              {k: parent.get(k) for k in ("length_remaining", "length_reserved", "rfid_tag_id", "status")})
        bal = await db.inventory_balances.find_one({"product_id": pid, "warehouse_id": W, "owner_entity_id": A}, {"_id": 0})
        check("WM-02", "saldo: available 70 + reserved 30, on_hand 100",
              round(bal["available_qty"], 2) == 70 and round(bal["reserved_qty"], 2) == 30 and bal["on_hand_qty"] == 100,
              {k: bal.get(k) for k in ("available_qty", "reserved_qty", "on_hand_qty")})
        rid = allocs[0]["rolls"][0]
        check("WM-02", "alokasi menandai pending_cut + reservation_id", rid.get("pending_cut") and rid.get("reservation_id"), rid)

        # Konkurensi: dua order berebut 80 m dari sisa bebas 70 → hanya satu dapat
        outs = await asyncio.gather(rs._reserve_length(parent, 50, so2), rs._reserve_length(parent, 50, so2 + "b"))
        ok = [o for o in outs if o]
        p2 = await db.inventory_rolls.find_one({"id": r["id"]}, {"_id": 0})
        check("WM-02", "reservasi panjang bersamaan tidak melebihi panjang bebas", len(ok) == 1 and p2["length_reserved"] == 80,
              {"ok": len(ok), "reserved": p2["length_reserved"]})
        await rs.release_order_rolls(so2)
        await rs.release_order_rolls(so2 + "b")
        p3 = await db.inventory_rolls.find_one({"id": r["id"]}, {"_id": 0})
        check("WM-02", "release reservasi panjang mengembalikan panjang bebas tanpa fragmen roll",
              p3["length_reserved"] == 30 and await db.inventory_rolls.count_documents({"product_id": pid}) == 1,
              p3.get("length_reserved"))

        # Loading sebelum potong ditolak
        from services import loading_check_service as lc
        await db.sales_orders.insert_one({"id": so1, "number": f"SO-{T}", "entity_id": A})
        try:
            await lc.start(so1, [A], "tester")
            check("WM-02", "loading check ditolak sebelum potong", False, "tidak ditolak")
        except Exception as exc:  # noqa: BLE001
            check("WM-02", "loading check ditolak sebelum potong", "potong" in str(getattr(exc, "detail", exc)), getattr(exc, "detail", exc))

        # Konfirmasi potong: aktual 29.5 + waste 0.5
        out = await rs.confirm_cut(r["id"], rid["reservation_id"], 29.5, 0.5, actor="tester")
        child, p4 = out["child"], out["parent"]
        check("WM-02", "potong 100 → induk 70 + anak 29.5 + waste 0.5 (konservasi)",
              p4["length_remaining"] == 70 and child["length_remaining"] == 29.5 and p4.get("length_reserved") == 0,
              {"parent": p4["length_remaining"], "child": child["length_remaining"], "reserved": p4.get("length_reserved")})
        check("WM-02", "anak lahir reserved utk SO, tanpa tag, parent langsung benar",
              child["status"] == "reserved" and child["reserved_ref"]["id"] == so1 and not child.get("rfid_tag_id")
              and child["parent_roll_id"] == r["id"] and child["roll_no"] != parent["roll_no"],
              {k: child.get(k) for k in ("status", "rfid_tag_id", "parent_roll_id", "roll_no")})
        try:
            await rs.confirm_cut(r["id"], rid["reservation_id"], 29.5, 0)
            check("WM-02", "potong ulang reservasi sama ditolak", False, "diterima")
        except Exception as exc:  # noqa: BLE001
            check("WM-02", "potong ulang reservasi sama ditolak", getattr(exc, "status_code", 0) == 404, getattr(exc, "detail", exc))

        # Kebijakan diperbarui 2026-10-03: dispatch TIDAK lagi memotong otomatis — wajib potong + tag anak dulu
        so3 = f"so_{T}_3"
        await rs.allocate_and_reserve_rolls(pid, 20, "Jakarta", A, so3)
        try:
            await rs.ship_order_rolls(so3, pid, W, 20)
            check("WM-02", "dispatch dengan reservasi belum dipotong ditolak (kebijakan 2026-10-03)", False, "terkirim")
        except Exception as exc:  # noqa: BLE001
            check("WM-02", "dispatch dengan reservasi belum dipotong ditolak (kebijakan 2026-10-03)",
                  getattr(exc, "status_code", 0) == 409, getattr(exc, "detail", exc))
    finally:
        await db.inventory_rolls.delete_many({"product_id": pid})
        await db.inventory_balances.delete_many({"product_id": pid})
        await db.inventory_movements.delete_many({"product_id": pid})
        await db.products.delete_one({"id": pid})
        await db.sales_orders.delete_many({"id": {"$regex": f"^so_{T}"}})
    passed = sum(1 for r_ in results if r_["pass"])
    print(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"pass={passed} fail={len(results) - passed}")


try:
    asyncio.run(main())
except Exception as _exc:  # noqa: BLE001 — HEAD tanpa kontrak baru: cetak hasil parsial + titik crash
    passed = sum(1 for r_ in results if r_["pass"])
    print(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"CRASH (kontrak belum ada di kode ini): {type(_exc).__name__}: {_exc}")
    print(f"pass={passed} fail={len(results) - passed} crashed=1")
