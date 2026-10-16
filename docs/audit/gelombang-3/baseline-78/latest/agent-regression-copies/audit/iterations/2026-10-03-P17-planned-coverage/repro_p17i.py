"""P17i — keputusan pemilik: dokumen badan usaha TERARSIP tetap bisa DIBUKA (baca saja), tulis tetap dikunci.

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-03-P17-planned-coverage/repro_p17i.py
Entitas uji: ent_d1772c5f5ced (tanpa dokumen) diarsipkan lalu diaktifkan kembali; pelanggan fixture dibuang.
"""
import asyncio
import json
import sys
import uuid

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
from poc_stock_guard import purge_new_ids, snapshot_new_ids  # noqa: E402

T = f"TEST_P17I_{uuid.uuid4().hex[:6]}"
ARC = "ent_d1772c5f5ced"
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def login(c, email):
    r = await c.post("/api/auth/login", json={"email": email, "password": "demo12345"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


async def run(c, db):
    await db.customers.insert_one({"id": f"cust_{T.lower()}", "code": T, "name": f"{T} Pelanggan Arsip",
                                   "entity_id": ARC, "status": "active", "created_at": "2026-10-03T00:00:00+00:00"})
    ha = await login(c, "admin@kainnusantara.id")
    r = await c.post(f"/api/entities/{ARC}/archive", headers={**ha, "X-Entity-Id": "ent_ksc"},
                     json={"reason": f"{T} uji arsip baca saja", "force": True})
    check("ARCHIVE-RO", "badan usaha diarsipkan (force + alasan)", r.status_code == 200 and r.json().get("status") == "archived", r.text[:150])
    from services.entity_lifecycle_service import invalidate_status_cache  # noqa: F401 — cache backend terpisah
    await asyncio.sleep(21)    # TTL cache status di proses backend
    ha = await login(c, "admin@kainnusantara.id")
    me = (await c.get("/api/auth/me", headers={**ha, "X-Entity-Id": "ent_ksc"})).json()
    arc_ids = [e["id"] for e in (me.get("entity_context") or {}).get("archived_entities") or []]
    check("ARCHIVE-RO", "konteks admin memuat daftar badan usaha terarsip (untuk pemilih 'baca saja')", ARC in arc_ids, arc_ids)
    h = {**ha, "X-Entity-Id": ARC}
    lst = await c.get("/api/customers", headers=h)
    body = lst.json()
    items = body if isinstance(body, list) else body.get("items") or body.get("customers") or []
    check("ARCHIVE-RO", "GET data entitas terarsip dengan X-Entity-Id-nya → 200 & berisi dokumennya",
          lst.status_code == 200 and any(x.get("id") == f"cust_{T.lower()}" for x in items), (lst.status_code, len(items)))
    leak = [x for x in items if x.get("entity_id") not in (ARC, None, "")]
    check("ARCHIVE-RO", "isi baca terarsip tidak bercampur data badan usaha lain", not leak, [x.get("entity_id") for x in leak[:3]])
    w = await c.post("/api/customers", headers=h, json={"name": f"{T} baru", "pic_name": "Uji", "city": "Bandung",
                                                       "phone": "081234567890", "address": "Jl. Uji 1"})
    p = await c.patch(f"/api/customers/cust_{T.lower()}", headers=h, json={"data": {"city": "Y"}})
    cur = await db.customers.find_one({"id": f"cust_{T.lower()}"}, {"_id": 0, "city": 1})
    check("ARCHIVE-RO", "tulis (POST/PATCH) ke entitas terarsip ditolak 403/409, data tidak berubah",
          w.status_code in (403, 409) and p.status_code in (403, 409) and "city" not in cur
          and not await db.customers.find_one({"name": f"{T} baru"}), (w.status_code, p.status_code))
    hs = {**(await login(c, "sales@kainnusantara.id")), "X-Entity-Id": ARC}
    s = await c.get("/api/customers", headers=hs)
    check("ARCHIVE-RO", "pengguna yang tidak pernah ditugaskan di entitas itu tetap 403", s.status_code == 403, s.status_code)
    rr = await c.post(f"/api/entities/{ARC}/reactivate", headers={**ha, "X-Entity-Id": "ent_ksc"})
    check("ARCHIVE-RO", "aktifkan kembali berhasil", rr.status_code == 200 and rr.json().get("status") == "active", rr.status_code)


async def main():
    import httpx
    from db import db
    ids = snapshot_new_ids(["audit_logs", "notifications"])
    snap = await db.business_entities.find_one({"id": ARC})
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8009", timeout=120) as c:
        try:
            await run(c, db)
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check("ARCHIVE-RO", "eksekusi skenario", False, repr(exc)[:200])
        finally:
            await db.customers.delete_many({"name": {"$regex": f"^{T}"}})
            await db.business_entities.replace_one({"id": ARC}, snap)
            purge_new_ids(ids, verbose=False)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
