"""T7 — TX-01: setelah Faktur Pajak diganti, apakah faktur asli tetap terjumlah di rekap PPN? Dijalankan lewat API."""
import boot_app, asyncio, datetime, logging
import server, httpx
from db import db
logging.disable(logging.CRITICAL)
E1 = "ent_ksc"   # PT PKP pada seed
def P(*a): print(*a, flush=True)
async def main():
    async with server.lifespan(server.app):
        now = datetime.datetime.now(datetime.timezone.utc)
        admin = await db.users.find_one({"email": "admin@kainnusantara.id"})
        await db.sessions.insert_one({"token": "t", "user_id": admin["id"], "expires_at": now + datetime.timedelta(hours=8)})
        await db.customers.insert_one({"id": "cus_x", "name": "Toko Uji", "entity_id": E1, "status": "active", "npwp": "01.234.567.8-901.000"})
        # pesanan terkonfirmasi: DPP 1.000.000, PPN 110.000 (angka contoh; tarif tidak diuji di sini)
        await db.sales_orders.insert_one({"id": "so_x", "number": "SO-UJI-1", "entity_id": E1, "customer_id": "cus_x", "customer_name": "Toko Uji",
            "status": "confirmed", "subtotal": 1000000, "dpp": 1000000, "ppn_amount": 110000, "ppn_rate": 11, "grand_total": 1110000,
            "items": [{"product_name": "Kain Uji", "quantity": 10, "unit": "m", "price": 100000, "line_total": 1000000}],
            "payments": [], "created_at": now.isoformat()})
        tr = httpx.ASGITransport(app=server.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=tr, base_url="http://uji", timeout=60) as c:
            H = {"Authorization": "Bearer t", "X-Entity-Id": E1}
            periode = now.isoformat()[:7]
            async def rekap():
                r = await c.get("/api/tax/vat-summary", params={"period": periode, "entity_id": E1}, headers=H)
                j = r.json() if r.status_code == 200 else {}
                return r.status_code, j.get("keluaran_ppn", j.get("keluaran", {})), j.get("keluaran_count", "")
            P("rekap awal:", await rekap())
            r = await c.post("/api/sales-orders/so_x/tax-invoice", json={}, headers=H)
            P("terbit faktur:", r.status_code, r.json().get("number", str(r.json())[:200]), "| PPN:", r.json().get("ppn_amount"))
            if r.status_code != 200: return
            f1 = r.json()["id"]
            P("rekap setelah terbit:", await rekap(), "| seharusnya 110.000")
            r = await c.post(f"/api/tax-invoices/{f1}/replace", json={"reason": "koreksi alamat"}, headers=H)
            P("terbit faktur PENGGANTI:", r.status_code, r.json().get("number", str(r.json())[:200]), "| status:", r.json().get("status"))
            rows = [(d["number"], d["status"], d.get("ppn_amount"), bool(d.get("replaced_by_id"))) async for d in db.tax_invoices.find({"order_id": "so_x"}, {"_id": 0})]
            P("faktur untuk pesanan ini (nomor, status, PPN, sudah diganti?):", rows)
            P("rekap setelah diganti:", await rekap(), "| seharusnya tetap 110.000 (satu penyerahan)")
asyncio.run(main())
