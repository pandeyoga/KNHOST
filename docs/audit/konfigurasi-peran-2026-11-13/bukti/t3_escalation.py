"""T3 — uji khusus: siapa bisa mengubah pengaturan; peran kustom menaikkan haknya sendiri; bocor lewat peran acuan."""
import boot_app, asyncio, json, sys, datetime, logging, traceback
import server, httpx
from db import db
import config_registry as registry
logging.disable(logging.CRITICAL)
E1 = "ent_ksc"
def P(*a): print(*a, flush=True)
async def main():
    async with server.lifespan(server.app):
        now = datetime.datetime.now(datetime.timezone.utc)
        async def session(uid, tok): await db.sessions.insert_one({"token": tok, "user_id": uid, "expires_at": now + datetime.timedelta(hours=8)})
        admin = await db.users.find_one({"email": "admin@kainnusantara.id"}); await session(admin["id"], "tok_admin")
        mgr = await db.users.find_one({"email": "manager@kainnusantara.id"}); await session(mgr["id"], "tok_mgr")
        tmpl_user = await db.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0})
        tr = httpx.ASGITransport(app=server.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=tr, base_url="http://uji", timeout=60) as c:
            def H(tok, ent=E1): return {"Authorization": f"Bearer {tok}", "X-Entity-Id": ent}
            mods = (await c.get("/api/access/modules", headers=H("tok_admin"))).json()
            mod_ids = [m["id"] for m in (mods if isinstance(mods, list) else mods.get("modules", []))]
            async def mk(label, base, levels):
                r = await c.post("/api/access/roles", json={"label": label, "base_role": base, "levels": levels}, headers=H("tok_admin"))
                rid = r.json()["id"]
                u = {**tmpl_user, "id": f"usr_{rid}", "email": f"{rid}@x.id", "name": label, "role": rid}
                await db.users.insert_one(dict(u)); await session(u["id"], f"tok_{rid}")
                return rid, u["id"], f"tok_{rid}", r.json()
            rid_a, uid_a, tok_a, role_a = await mk("Uji Admin HR", "", {"admin": "manage", "hr": "manage"})
            rid_m, uid_m, tok_m, role_m = await mk("Uji Manajer Kosong", "manager", {m: "none" for m in mod_ids})
            P("== Uji Admin HR (tanpa acuan; modul 'Pengaturan, Pengguna & Hak Akses' = Kelola penuh)")
            P("   izin:", {k: v for k, v in role_a["permissions"].items() if v})
            P("   peringkat:", role_a["rank"], "| lintas PT:", role_a["cross_entity"])
            # (a) ubah pengaturan dengan settings.manage
            keys_plain = [e for e in registry.all_entries() if e["status"] == "active" and (e.get("permission") or ["settings", "manage"])[0] == "settings" and not e.get("roles")]
            keys_mgr = [e for e in registry.all_entries() if e["status"] == "active" and "manager" in (e.get("roles") or [])]
            P("   kunci (settings.manage, tanpa roles):", len(keys_plain), "| kunci dengan roles=['manager']:", len(keys_mgr))
            e = next(x for x in keys_plain if x["type"] == "bool" and not x["requires_reason"])
            r = await c.put("/api/config/values", json={"items": [{"key": e["key"], "value": (not e["default"]), "scope_type": "global", "reason": "uji"}]}, headers=H(tok_a))
            P(f"   (a) PUT pengaturan '{e['key']}' oleh pemegang settings.manage →", r.status_code, str(r.json().get("detail", ""))[:140])
            r = await c.put("/api/config/values", json={"items": [{"key": e["key"], "value": (not e["default"]), "scope_type": "entity", "scope_id": E1, "reason": "uji"}]}, headers=H(tok_a))
            P(f"       lapisan PT →", r.status_code, str(r.json().get("detail", ""))[:140])
            ok = 0
            for x in keys_plain[:400]:
                eff = (await c.get("/api/config/effective", params={"q": x["key"]}, headers=H(tok_a))).json()
                it = [i for i in eff.get("items", []) if i["key"] == x["key"]]
                if it and it[0].get("can_edit"): ok += 1
            P(f"       can_edit=true untuk pemegang settings.manage: {ok} dari {len(keys_plain)} kunci")
            # (b) manajer bawaan
            r = await c.put("/api/config/values", json={"items": [{"key": e["key"], "value": (not e["default"]), "scope_type": "global", "reason": "uji"}]}, headers=H("tok_mgr"))
            P(f"   (b) Manajer bawaan PUT '{e['key']}' →", r.status_code, str(r.json().get("detail", ""))[:120])
            em = next((x for x in keys_mgr if x["type"] in ("bool",)), keys_mgr[0])
            val = (not em["default"]) if em["type"] == "bool" else em["default"]
            r = await c.put("/api/config/values", json={"items": [{"key": em["key"], "value": val, "scope_type": "global", "reason": "uji audit"}]}, headers=H(tok_m))
            P(f"   (c) Manajer KOSONG (semua modul 'Tidak ada') PUT '{em['key']}' (roles=['manager']) →", r.status_code, str(r.json().get("detail", ""))[:120])
            # (d) eskalasi: ubah peran sendiri, buat peran baru, jadikan diri admin
            r = await c.patch(f"/api/access/roles/{rid_a}", json={"levels": {m: "manage" for m in mod_ids}}, headers=H(tok_a))
            P("   (d1) ubah PERAN SENDIRI → semua modul Kelola penuh:", r.status_code, str(r.json().get("detail", ""))[:120] if r.status_code != 200 else f"izin kini {sum(1 for v in r.json()['permissions'].values() if v)} sumber daya")
            r = await c.patch("/api/access/roles/manager", json={"levels": {"accounting": "none"}}, headers=H(tok_a))
            P("   (d2) ubah peran MANAJER (cabut akuntansi):", r.status_code, str(r.json().get("detail", ""))[:120] if r.status_code != 200 else "berhasil")
            await c.post("/api/access/roles/manager/reset", headers=H("tok_admin"))
            r = await c.patch(f"/api/users/{uid_a}", json={"role": "admin"}, headers=H(tok_a))
            P("   (d3) jadikan AKUN SENDIRI admin:", r.status_code, str(r.json().get("detail", r.json().get("role", "")))[:140])
            me = await db.users.find_one({"id": uid_a}, {"_id": 0, "role": 1}); P("        peran akun sekarang:", me["role"])
            r = await c.post("/api/users", json={"name": "Admin Baru", "email": "adminbaru@x.id", "password": "Sandi12345!", "role": "admin", "home_entity_id": E1}, headers=H(tok_a))
            P("   (d4) BUAT akun admin baru:", r.status_code, str(r.json().get("detail", r.json().get("role", "")))[:160])
            # (e) manajer kosong: lintas PT & HPP
            r = await c.get("/api/costing/wac", headers=H(tok_m)); P("   (e1) Manajer KOSONG GET /costing/wac:", r.status_code, "baris:", len(r.json()) if r.status_code == 200 and isinstance(r.json(), list) else str(r.json())[:80])
            r = await c.get("/api/home/manager", headers=H(tok_m, "all")); P("   (e2) Manajer KOSONG GET /home/manager (semua PT):", r.status_code, list(r.json().keys())[:8] if r.status_code == 200 else r.text[:80])
            r = await c.get("/api/sales-targets", headers=H(tok_m)); P("   (e3) GET /sales-targets:", r.status_code)
            # (f) peran lain membaca semua pengaturan & riwayat
            drv = {**tmpl_user, "id": "usr_drv", "email": "drv@x.id", "name": "Sopir Uji", "role": "driver"}; await db.users.insert_one(dict(drv)); await session("usr_drv", "tok_drv")
            r = await c.get("/api/config/effective", headers=H("tok_drv")); P("   (f1) Sopir GET /config/effective:", r.status_code, "kunci terlihat:", r.json().get("total") if r.status_code == 200 else "")
            r = await c.get("/api/home/finance", headers=H("tok_drv")); P("   (f2) Sopir GET /home/finance:", r.status_code, list(r.json().keys())[:8] if r.status_code == 200 else "")
            r = await c.get("/api/sales-targets", headers=H("tok_drv")); P("   (f3) Sopir GET /sales-targets:", r.status_code, "baris:", len(r.json()) if r.status_code == 200 else "")
            r = await c.get("/api/sales-users", headers=H("tok_drv")); P("   (f4) Sopir GET /sales-users:", r.status_code, "baris:", len(r.json()) if r.status_code == 200 else "")
            r = await c.get("/api/entities", headers=H("tok_drv")); P("   (f5) Sopir GET /entities:", r.status_code, "PT:", len(r.json()) if r.status_code == 200 and isinstance(r.json(), list) else str(r.json())[:60])
            r = await c.get("/api/entities/count", headers=H("tok_admin")); P("   (g) /entities/count:", r.status_code, r.text[:160])
asyncio.run(main())
