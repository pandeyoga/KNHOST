"""T5 — perubahan pengaturan berjadwal ("berlaku sejak" di masa depan): kapan mesin mulai memakainya?"""
import boot_app, asyncio, datetime, logging
import server, httpx
from db import db
from services import config_resolver as resolver, config_service
logging.disable(logging.CRITICAL)
KEY = "ar.grace_days"
def P(*a): print(*a, flush=True)
async def main():
    async with server.lifespan(server.app):
        admin = await db.users.find_one({"email": "admin@kainnusantara.id"})
        await db.sessions.insert_one({"token": "t", "user_id": admin["id"],
            "expires_at": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)})
        tr = httpx.ASGITransport(app=server.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=tr, base_url="http://uji", timeout=60) as c:
            H = {"Authorization": "Bearer t", "X-Entity-Id": "ent_ksc"}
            async def lama(): return ((await config_service.get_effective_settings(None)).get("ar") or {}).get("grace_days")
            awal = await resolver.value_of(KEY)
            eff = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=2)).isoformat()
            r = await c.put("/api/config/values", json={"items": [{"key": KEY, "value": int(awal) + 5, "scope_type": "global", "reason": "uji jadwal", "effective_from": eff}]}, headers=H)
            P("tulis berjadwal (+2 detik):", r.status_code, "| nilai awal:", awal, "→ dijadwalkan:", int(awal) + 5)
            P("  segera sesudahnya   → pembaca baru:", await resolver.value_of(KEY), "| pembaca lama (get_effective_settings):", await lama())
            await asyncio.sleep(3)
            P("  3 detik kemudian    → pembaca baru:", await resolver.value_of(KEY), "| pembaca lama:", await lama(), " (belum ada yang membuka layar Pengaturan)")
            await c.get("/api/config/effective", params={"q": KEY}, headers=H)
            P("  setelah layar Pengaturan dibuka → pembaca lama:", await lama())
asyncio.run(main())
