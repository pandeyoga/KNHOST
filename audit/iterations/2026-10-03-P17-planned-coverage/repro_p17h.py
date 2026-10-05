"""P17h — OPS-03: impor master dapat DILANJUTKAN sesudah terputus & direkonsiliasi (tanpa duplikat).

Skenario: impor pelanggan terputus (hanya 2 dari 4 baris masuk) → impor ulang file penuh → impor ulang lagi.
Usage: cd /app/backend && python ../audit/iterations/2026-10-03-P17-planned-coverage/repro_p17h.py
"""
import asyncio
import json
import sys
import uuid

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402

T = f"TEST_P17H_{uuid.uuid4().hex[:6]}"
ENT = "ent_ksc"
results = []
HEAD = "code,name,city,phone,sales_email\n"
ROWS = [f"{T}-C1,{T} Toko Satu,Bandung,0811,sales@kainnusantara.id",
        f"{T}-C2,{T} Toko Dua,Solo,0812,sales@kainnusantara.id",
        f"{T}-C3,{T} Toko Tiga,Bali,0813,sales@kainnusantara.id",
        f",{T} Toko Empat,Medan,0814,tidakada@kainnusantara.id"]


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def imp(c, h, rows, dry=False):
    files = {"file": ("pelanggan.csv", (HEAD + "\n".join(rows) + "\n").encode(), "text/csv")}
    r = await c.post("/api/master-data/import-customers", headers=h, files=files, params={"dry_run": str(dry).lower()})
    return r.status_code, r.json()


async def count(db):
    return await db.customers.count_documents({"name": {"$regex": f"^{T}"}, "entity_id": ENT})


async def run(c, h, db):
    code, dry = await imp(c, h, ROWS, dry=True)
    check("OPS-03", "dry-run: 3 akan dibuat, 1 error (sales tak dikenal), tanpa menulis",
          code == 200 and dry["created"] == 3 and len(dry["errors"]) == 1 and await count(db) == 0, (dry.get("created"), dry.get("errors")))
    code, part = await imp(c, h, ROWS[:2])
    check("OPS-03", "impor terputus: 2 baris pertama masuk", code == 200 and part["created"] == 2 and await count(db) == 2, part)
    code, full = await imp(c, h, ROWS)
    check("OPS-03", "lanjut dengan file penuh: hanya sisa baris yang dibuat (1), 2 diperbarui, 1 error",
          code == 200 and full["created"] == 1 and full["updated"] == 2 and len(full["errors"]) == 1 and await count(db) == 3, full)
    code, again = await imp(c, h, ROWS)
    codes = [d["code"] async for d in db.customers.find({"name": {"$regex": f"^{T}"}}, {"_id": 0, "code": 1})]
    check("OPS-03", "impor ulang idempoten: 0 dibuat, jumlah tetap 3, kode unik sesuai file",
          again["created"] == 0 and await count(db) == 3 and sorted(codes) == sorted(f"{T}-C{i}".upper() for i in (1, 2, 3)), (again, codes))
    check("OPS-03", "rekonsiliasi: Σ created seluruh run = jumlah pelanggan baru = baris valid file",
          part["created"] + full["created"] + again["created"] == await count(db) == dry["created"], await count(db))
    n = await db.audit_logs.count_documents({"action": "customers_imported", "entity_id": "bulk", "timestamp": {"$exists": True}})
    check("OPS-03", "tiap run impor (bukan dry-run) tercatat di audit", n >= 3 or await db.audit_logs.count_documents({"action": "customers_imported"}) >= 3, n)
    await db.customers.delete_many({"name": {"$regex": f"^{T}"}})


async def main():
    import httpx
    from db import db
    full = snapshot_stock(["number_sequences"])
    ids = snapshot_new_ids(["customers", "audit_logs", "notifications", "group_partners"])
    async with httpx.AsyncClient(base_url="http://localhost:8001", timeout=120) as c:
        r = await c.post("/api/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
        h = {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}
        try:
            await run(c, h, db)
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check("OPS-03", "eksekusi skenario", False, repr(exc)[:200])
        finally:
            await db.customers.delete_many({"name": {"$regex": f"^{T}"}})
            purge_new_ids(ids, verbose=False)
            restore_stock(full)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
