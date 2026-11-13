"""T4 — (a) perubahan izin peran bawaan bertahan setelah server dinyalakan ulang? (b) pindah-massal akun dari peran Admin."""
import boot_app, asyncio, datetime, logging
import server, httpx
from db import db
import bootstrap
logging.disable(logging.CRITICAL)
E1 = "ent_ksc"
def P(*a): print(*a, flush=True)
async def main():
    async with server.lifespan(server.app):
        admin = await db.users.find_one({"email": "admin@kainnusantara.id"})
        await db.sessions.insert_one({"token": "tok_admin", "user_id": admin["id"],
            "expires_at": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)})
        tr = httpx.ASGITransport(app=server.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=tr, base_url="http://uji", timeout=60) as c:
            H = {"Authorization": "Bearer tok_admin", "X-Entity-Id": E1}
            before = (await c.get("/api/access/roles/sales", headers=H)).json()["permissions"]
            P("(a) sales.ar_receipt sebelum:", before.get("ar_receipt"), "| level modul 'ar':", (await c.get("/api/access/roles/sales", headers=H)).json()["levels"].get("ar"))
            r = await c.patch("/api/access/roles/sales", json={"levels": {"ar": "none"}}, headers=H)
            P("    admin mencabut modul Uang Masuk dari Sales →", r.status_code, "| ar_receipt kini:", r.json()["permissions"].get("ar_receipt"))
            # nyalakan ulang: jalankan lagi proses awal aplikasi (sama seperti restart server)
            await bootstrap.run_bootstrap()
            after = (await c.get("/api/access/roles/sales", headers=H)).json()["permissions"]
            P("    setelah proses awal dijalankan ulang (= restart): ar_receipt =", after.get("ar_receipt"))
            n_admin = await db.users.count_documents({"role": "admin", "status": "active"})
            r = await c.post("/api/access/roles/admin/move-users", json={"to_role": "sales"}, headers=H)
            P("(b) pindah massal semua akun Admin → Sales:", r.status_code, str(r.json())[:160])
            P("    admin aktif sebelum:", n_admin, "| sesudah:", await db.users.count_documents({"role": "admin", "status": "active"}))
asyncio.run(main())
