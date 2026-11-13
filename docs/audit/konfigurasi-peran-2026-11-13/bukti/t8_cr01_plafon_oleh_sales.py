"""T8 — CR-01: bisakah akun Sales menaikkan plafon dan membuka blokir pelanggannya sendiri? Dijalankan lewat API."""
import boot_app, asyncio, datetime, logging
import server, httpx
from db import db
logging.disable(logging.CRITICAL)
E1 = "ent_ksc"
def P(*a): print(*a, flush=True)
async def main():
    async with server.lifespan(server.app):
        now = datetime.datetime.now(datetime.timezone.utc)
        sales = await db.users.find_one({"email": "sales@kainnusantara.id"})
        await db.sessions.insert_one({"token": "ts", "user_id": sales["id"], "expires_at": now + datetime.timedelta(hours=8)})
        await db.customers.insert_one({"id": "cus_s", "name": "Toko Milik Sales", "entity_id": E1, "status": "blocked", "credit_limit": 5000000,
                                       "assigned_sales_id": sales["id"], "assigned_sales_name": sales.get("name", ""), "created_at": now.isoformat()})
        tr = httpx.ASGITransport(app=server.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=tr, base_url="http://uji", timeout=60) as c:
            H = {"Authorization": "Bearer ts", "X-Entity-Id": E1}
            P("sebelum: plafon 5.000.000, status blocked")
            r = await c.patch("/api/customers/cus_s", json={"data": {"credit_limit": 900000000, "status": "active"}}, headers=H)
            P("Sales PATCH plafon → 900.000.000 dan status → active:", r.status_code, str(r.json().get("detail", ""))[:160])
            d = await db.customers.find_one({"id": "cus_s"}, {"_id": 0, "credit_limit": 1, "status": 1})
            P("sesudah di database:", d)
asyncio.run(main())
