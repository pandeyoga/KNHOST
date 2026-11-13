"""T2 — peran × endpoint GET: apakah gerbang server mengikuti matriks izin, termasuk untuk peran kustom."""
import boot_app, asyncio, json, sys, datetime, re, collections, logging
import server, httpx
from db import db
logging.disable(logging.CRITICAL)
OUT = sys.argv[1]
INV = json.load(open(sys.argv[2]))
E1 = "ent_ksc"

def tmpl(p): return re.sub(r"\{[^}]+\}", "{}", p)
inv = {}
for r in INV:
    inv.setdefault((r["method"], tmpl(r["path"])), r)

async def main():
    out = {"roles": {}, "results": {}, "custom": {}, "errors": []}
    async with server.lifespan(server.app):
        now = datetime.datetime.now(datetime.timezone.utc)
        admin = await db.users.find_one({"email": "admin@kainnusantara.id"})
        await db.sessions.insert_one({"token": "tok_admin", "user_id": admin["id"], "expires_at": now + datetime.timedelta(hours=8)})
        tr = httpx.ASGITransport(app=server.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=tr, base_url="http://uji", timeout=60) as c:
            HA = {"Authorization": "Bearer tok_admin", "X-Entity-Id": E1}
            mods = (await c.get("/api/access/modules", headers=HA)).json()
            mod_ids = [m["id"] for m in (mods.get("modules") or mods if isinstance(mods, (dict, list)) else [])] if not isinstance(mods, list) else [m["id"] for m in mods]
            out["modules"] = mods
            # peran kustom
            specs = [
                ("Uji Kasir Sempit", "finance", {"ar": "none", "finance_ops": "view"}),
                ("Uji Manajer Kosong", "manager", {m: "none" for m in mod_ids}),
                ("Uji Tanpa Acuan", "", {"accounting": "manage", "ar": "manage", "finance_ops": "manage", "payable": "manage", "admin": "manage"}),
                ("Uji Sales Plus", "sales", {"accounting": "view", "payable": "view"}),
            ]
            for label, base, levels in specs:
                r = await c.post("/api/access/roles", json={"label": label, "base_role": base, "levels": levels, "description": "uji audit"}, headers=HA)
                out["custom"][label] = {"status": r.status_code, "body": r.json() if r.status_code < 500 else r.text[:300]}
            roles = (await c.get("/api/access/roles", headers=HA)).json()
            roles = roles.get("roles") if isinstance(roles, dict) else roles
            tmpl_user = await db.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0})
            tokens = {}
            for ro in roles:
                rid = ro["id"]
                out["roles"][rid] = {"label": ro["label"], "custom": ro["custom"], "base_role": ro.get("base_role", ""), "permissions": ro["permissions"],
                                     "levels": {k: v.get("level") for k, v in (ro.get("levels") or {}).items()}, "rank": ro.get("rank"), "cross_entity": ro.get("cross_entity")}
                u = await db.users.find_one({"role": rid, "status": "active"}, {"_id": 0})
                if not u:
                    u = {**tmpl_user, "id": f"usr_uji_{rid}", "email": f"uji_{rid}@x.id", "name": f"Uji {ro['label']}", "role": rid}
                    await db.users.insert_one(dict(u))
                tok = f"tok_{rid}"
                await db.sessions.insert_one({"token": tok, "user_id": u["id"], "expires_at": now + datetime.timedelta(hours=8)})
                tokens[rid] = tok
            gets = []
            for rt in server.app.routes:
                methods = getattr(rt, "methods", None) or set()
                if "GET" in methods and rt.path.startswith("/api/"):
                    gets.append(rt.path)
            gets = sorted(set(gets))
            out["get_count"] = len(gets)
            for rid, tok in tokens.items():
                H = {"Authorization": f"Bearer {tok}", "X-Entity-Id": E1}
                res = {}
                for p in gets:
                    url = re.sub(r"\{[^}]+\}", "x", p)
                    try:
                        r = await c.get(url, headers=H)
                        det = ""
                        if r.status_code >= 400:
                            try: det = str(r.json().get("detail"))[:110]
                            except Exception: det = r.text[:110]
                        res[p] = [r.status_code, det]
                    except Exception as exc:
                        res[p] = [-1, f"{type(exc).__name__}: {exc}"[:110]]
                out["results"][rid] = res
                print(rid, collections.Counter(v[0] for v in res.values()).most_common(8), flush=True)
    json.dump(out, open(OUT, "w"), ensure_ascii=False, default=str)
asyncio.run(main())
