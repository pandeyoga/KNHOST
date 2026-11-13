import boot_app, asyncio, datetime, logging, traceback
import server, httpx
from db import db
logging.disable(logging.CRITICAL)
E1 = "ent_ksc"
def P(*a): print(*a, flush=True)
async def main():
    async with server.lifespan(server.app):
        now = datetime.datetime.now(datetime.timezone.utc)
        async def session(uid, tok): await db.sessions.insert_one({"token": tok, "user_id": uid, "expires_at": now + datetime.timedelta(hours=8)})
        admin = await db.users.find_one({"email": "admin@kainnusantara.id"}); await session(admin["id"], "tok_admin")
        tmpl_user = await db.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0})
        tr = httpx.ASGITransport(app=server.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=tr, base_url="http://uji", timeout=60) as c:
            def H(tok, ent=E1): return {"Authorization": f"Bearer {tok}", "X-Entity-Id": ent}
            r = await c.post("/api/access/roles", json={"label": "Uji Admin HR", "base_role": "", "levels": {"admin": "manage"}}, headers=H("tok_admin"))
            rid = r.json()["id"]
            u = {**tmpl_user, "id": "usr_hr", "email": "hr@x.id", "name": "Uji Admin HR", "role": rid}
            await db.users.insert_one(dict(u)); await session("usr_hr", "tok_hr")
            r = await c.patch("/api/users/usr_hr", json={"data": {"role": "admin"}}, headers=H("tok_hr"))
            P("(d3) jadikan AKUN SENDIRI admin:", r.status_code, str(r.json().get("detail", r.json().get("role", "")))[:160])
            me = await db.users.find_one({"id": "usr_hr"}, {"_id": 0, "role": 1}); P("     peran akun sekarang:", me["role"])
            await db.users.update_one({"id": "usr_hr"}, {"$set": {"role": rid}}); await session("usr_hr", "tok_hr2")
            r = await c.post(f"/api/users/{admin['id']}/reset-password", json={"new_password": "Baru12345!x"}, headers=H("tok_hr2"))
            P("(d5) reset sandi akun ADMIN oleh peran kustom:", r.status_code, str(r.json())[:160])
            r = await c.patch(f"/api/users/{admin['id']}", json={"data": {"status": "inactive"}}, headers=H("tok_hr2"))
            P("(d6) nonaktifkan akun ADMIN (satu-satunya):", r.status_code, str(r.json().get("detail", ""))[:140])
            r = await c.post("/api/access/roles", json={"label": "Uji Super", "base_role": "manager", "levels": {}}, headers=H("tok_hr2"))
            P("(d7) peran kustom membuat peran baru beracuan Manajer:", r.status_code, r.json().get("id", r.json().get("detail")))
            try:
                from routers import entities as ent_router
                import inspect
            except Exception as e: P("impor", e)
            tr2 = httpx.ASGITransport(app=server.app, raise_app_exceptions=True)
            async with httpx.AsyncClient(transport=tr2, base_url="http://uji") as c2:
                try:
                    r = await c2.get("/api/entities/count", headers=H("tok_admin")); P("(g)", r.status_code, r.text[:100])
                except Exception:
                    tb = traceback.format_exc().strip().splitlines(); P("(g) galat:", " | ".join(tb[-4:])[:420])
asyncio.run(main())
