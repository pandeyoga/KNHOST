"""P16e — DOC-02: dokumen cetak (HTML/PDF) konsisten dengan sumber & hak akses.

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-09-P16-close-coverage/repro_p16e.py
Baca-saja (dokumen yang dibuat lewat /documents/generate dihapus di akhir).
"""
import asyncio
import json
import sys

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
results = []
gen = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def login(c, email, ent="ent_ksc"):
    r = await c.post("/api/auth/login", json={"email": email, "password": "demo12345"})
    return {"Authorization": f"Bearer {r.json().get('token')}", "X-Entity-Id": ent}


async def run(c, db):
    from services import pdf_resolvers as pr
    h = await login(c, "admin@kainnusantara.id")
    so = await db.sales_orders.find_one({"entity_id": "ent_ksc", "status": "confirmed"}, {"_id": 0})
    pv = await c.get(f"/api/documents/preview/{so['id']}", params={"document_type": "invoice"}, headers=h)
    html = pv.text
    check("DOC-02", "preview faktur (admin) memuat nomor SO, pelanggan & grand total sumber",
          pv.status_code == 200 and so["number"] in html and so["customer_name"] in html
          and pr.fmt_rp(so["grand_total"]).replace("Rp ", "").split(",")[0] in html, f"{pv.status_code} len={len(html)}")
    g = await c.post("/api/documents/generate", json={"source_id": so["id"], "document_type": "invoice"}, headers=h)
    if g.status_code == 200:
        gen.append(g.json()["id"])
    pr_ = await c.get(f"/api/documents/{gen[-1]}/print", headers=h) if gen else None
    check("DOC-02", "dokumen tersimpan & tampilan cetak = hasil generate", g.status_code == 200 and pr_ is not None
          and pr_.status_code == 200 and so["number"] in pr_.text, g.status_code)
    hk = await login(c, "sales3@kainnusantara.id", "ent_kanda")
    x1 = await c.get(f"/api/documents/preview/{so['id']}", params={"document_type": "invoice"}, headers=hk)
    x2 = await c.get(f"/api/documents/{gen[-1]}/print", headers=hk) if gen else None
    check("DOC-02", "pengguna entitas lain tidak bisa preview/cetak dokumen KSC (403/404)",
          x1.status_code in (403, 404) and x2 is not None and x2.status_code in (403, 404), f"{x1.status_code}/{x2 and x2.status_code}")
    hd = await login(c, "designer@kainnusantara.id")
    d1 = await c.get(f"/api/documents/preview/{so['id']}", params={"document_type": "invoice"}, headers=hd)
    check("DOC-02", "peran tanpa izin dokumen (desainer) ditolak 403", d1.status_code == 403, d1.status_code)
    # pagar PEMILIK sales: rekan sales tidak boleh membuka SO (detail) → dokumennya pun tidak
    owner = so.get("sales_id") or ""
    other = await db.users.find_one({"role": "sales", "home_entity_id": "ent_ksc", "id": {"$ne": owner}}, {"_id": 0, "email": 1})
    hs = await login(c, other["email"])
    det = await c.get(f"/api/sales-orders/{so['id']}", headers=hs)
    doc = await c.get(f"/api/documents/preview/{so['id']}", params={"document_type": "invoice"}, headers=hs)
    check("DOC-02", "sales bukan pemilik: bila detail SO ditolak, preview dokumennya juga ditolak (tidak bocor harga nego)",
          det.status_code != 403 or doc.status_code in (403, 404), f"detail={det.status_code} doc={doc.status_code} as={other['email']}")


async def main():
    import httpx
    from db import db
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8009", timeout=120) as c:
        try:
            await run(c, db)
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check("DOC-02", "eksekusi skenario", False, repr(exc)[:200])
        finally:
            await db.generated_documents.delete_many({"id": {"$in": gen}})
            await db.audit_logs.delete_many({"entity_id": {"$in": gen}})
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
