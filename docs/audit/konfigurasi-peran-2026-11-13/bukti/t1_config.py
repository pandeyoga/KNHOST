"""T1 — setiap kunci Pusat Pengaturan: tulis lewat API → baca lewat 3 jalur → lapisan PT → nilai tak sah → pulihkan."""
import boot_app, asyncio, json, sys, datetime, copy, traceback
import server, httpx
from db import db
import config_registry as registry
from services import config_resolver as resolver, config_service

OUT = sys.argv[1]
E1, E2 = "ent_ksc", "ent_kanda"

def dig(doc, path):
    cur = doc
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur: return ("<tak ada>",)
        cur = cur[p]
    return cur

def alt_value(e, base):
    t = e["type"]; lo, hi = e.get("min"), e.get("max")
    if e.get("value_format"): return None
    if t == "bool": return (not bool(base))
    if t in ("int", "duration"):
        v = int(base or 0) + 1
        if hi is not None and v > hi: v = int(base or 0) - 1
        if lo is not None and v < lo: return None
        return v
    if t == "pct":
        v = float(base or 0) + 1
        if v > (hi if hi is not None else 100): v = float(base or 0) - 1
        if v < (lo if lo is not None else 0): return None
        return v
    if t in ("money", "decimal"):
        v = float(base or 0) + 1
        if hi is not None and v > hi: v = float(base or 0) - 1
        if lo is not None and v < lo: return None
        return v
    if t == "enum":
        opts = [o["value"] if isinstance(o, dict) else o for o in (e.get("options") or [])]
        others = [o for o in opts if o != base]
        return others[0] if others else None
    if t == "text": return (str(base or "") + " uji").strip()
    return None

def bad_value(e):
    t = e["type"]; hi = e.get("max"); lo = e.get("min")
    if t == "bool": return "bukan-bool"
    if t in ("int", "duration", "money", "decimal"):
        if hi is not None: return hi + 1000000
        if lo is not None: return lo - 1000000
        return "abc"
    if t == "pct": return 150
    if t == "enum": return "__tidak_ada__"
    if t in ("list", "table"): return "bukan-daftar"
    return None

def same(a, b):
    if isinstance(a, tuple) or isinstance(b, tuple): return False
    try:
        if isinstance(a, bool) or isinstance(b, bool): return bool(a) == bool(b) and type(a) == type(b) or (a in (0,1) and b in (0,1) and bool(a)==bool(b))
        if isinstance(a, (int, float)) and isinstance(b, (int, float)): return abs(float(a) - float(b)) < 1e-9
    except Exception: pass
    return a == b

async def legacy_read(key, entity):
    scope_doc, path = registry.legacy_target(key)
    if scope_doc == "global":
        eff = await config_service.get_effective_settings(entity)
        return dig(eff, path)
    doc = await db.system_settings.find_one({"scope": scope_doc}, {"_id": 0}) or {}
    val = dig(doc, path)
    if entity:
        ov = await resolver.entity_overlay(scope_doc, entity) or {}
        v2 = dig(ov, path)
        if not isinstance(v2, tuple): val = v2
    return val

async def main():
    res = []
    async with server.lifespan(server.app):
        admin = await db.users.find_one({"email": "admin@kainnusantara.id"})
        await db.sessions.insert_one({"token": "tok_admin", "user_id": admin["id"],
                                      "expires_at": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)})
        tr = httpx.ASGITransport(app=server.app)
        async with httpx.AsyncClient(transport=tr, base_url="http://uji") as c:
            H = {"Authorization": "Bearer tok_admin"}
            r = await c.get("/api/config/registry", headers=H)
            reg_api = r.json()
            print("registry API:", r.status_code, "kunci:", len(reg_api.get("items", reg_api.get("entries", []))), list(reg_api.keys())[:6])
            async def api_eff(key, entity=""):
                r = await c.get("/api/config/effective", params={"q": key, "entity_id": entity}, headers=H)
                if r.status_code != 200: return ("<API %s>" % r.status_code,)
                for it in r.json().get("items", []):
                    if it["key"] == key: return it.get("value")
                return ("<tak tampil>",)
            async def put(key, value, scope_type="global", scope_id="", reason="uji audit"):
                r = await c.put("/api/config/values", json={"items": [{"key": key, "value": value, "scope_type": scope_type, "scope_id": scope_id, "reason": reason}]}, headers=H)
                return r.status_code, (r.json().get("detail") if r.status_code != 200 else "")
            for e in registry.all_entries():
                key = e["key"]
                row = {"key": key, "group": e["group"], "type": e["type"], "scopes": e["scopes"], "status": e["status"],
                       "risk": e["risk"], "label": e["label"], "owner_role": e.get("owner_role"), "permission": e.get("permission"),
                       "roles": e.get("roles"), "requires_reason": e.get("requires_reason"), "consumers": e.get("consumers"),
                       "min": e.get("min"), "max": e.get("max"), "unit": e.get("unit"), "default": e.get("default"),
                       "help": e.get("help"), "impact": e.get("impact"), "example": e.get("example"), "value_format": e.get("value_format"),
                       "tests": {}}
                T = row["tests"]
                try:
                    base_api = await api_eff(key)
                    base_res = await resolver.value_of(key)
                    base_leg = await legacy_read(key, None)
                    T["awal_sama_api_resolver"] = same(base_api, base_res)
                    T["awal_sama_legacy"] = same(base_res, base_leg)
                    T["awal"] = {"api": base_api if not isinstance(base_api, tuple) else base_api[0], "legacy": base_leg if not isinstance(base_leg, tuple) else base_leg[0]}
                    if e["status"] != "active":
                        st, det = await put(key, e.get("default"))
                        T["tulis_not_used_ditolak"] = (st == 400)
                        res.append(row); continue
                    v1 = alt_value(e, base_res)
                    if v1 is None:
                        # tipe kompleks: simpan ulang nilai yang sama
                        st, det = await put(key, base_res)
                        T["simpan_ulang_nilai_sama"] = st; T["catatan"] = "tipe kompleks — hanya simpan-ulang" + (f" ({det})" if det else "")
                    else:
                        st, det = await put(key, v1)
                        T["tulis_global"] = st
                        if st == 200:
                            a, b, l = await api_eff(key), await resolver.value_of(key), await legacy_read(key, None)
                            T["global_terbaca_api"] = same(a, v1); T["global_terbaca_resolver"] = same(b, v1); T["global_terbaca_legacy"] = same(l, v1)
                            if not T["global_terbaca_legacy"]: T["legacy_dapat"] = l if not isinstance(l, tuple) else l[0]
                        else: T["tulis_global_galat"] = str(det)[:200]
                        if "entity" in e["scopes"]:
                            v2 = alt_value(e, v1)
                            if v2 is not None and not same(v2, v1):
                                st2, det2 = await put(key, v2, "entity", E2)
                                T["tulis_pt"] = st2
                                if st2 == 200:
                                    b2 = await resolver.value_of(key, {"entity_id": E2}); b1 = await resolver.value_of(key, {"entity_id": E1})
                                    l2 = await legacy_read(key, E2); l1 = await legacy_read(key, E1)
                                    a2 = await api_eff(key, E2)
                                    T["pt_terbaca_resolver"] = same(b2, v2); T["pt_lain_tetap_resolver"] = same(b1, v1)
                                    T["pt_terbaca_legacy"] = same(l2, v2); T["pt_lain_tetap_legacy"] = same(l1, v1)
                                    T["pt_terbaca_api"] = same(a2, v2)
                                    if not T["pt_terbaca_legacy"]: T["legacy_pt_dapat"] = l2 if not isinstance(l2, tuple) else l2[0]
                                    r = await c.post("/api/config/values/clear", json={"key": key, "scope_type": "entity", "scope_id": E2, "reason": "uji"}, headers=H)
                                    T["cabut_pt"] = r.status_code
                                    T["setelah_cabut_kembali"] = same(await resolver.value_of(key, {"entity_id": E2}), v1)
                                    T["setelah_cabut_legacy"] = same(await legacy_read(key, E2), v1)
                                else: T["tulis_pt_galat"] = str(det2)[:200]
                        bv = bad_value(e)
                        if bv is not None:
                            st3, det3 = await put(key, bv)
                            T["nilai_tak_sah_ditolak"] = (st3 == 400); T["nilai_tak_sah_status"] = st3
                    if e.get("requires_reason"):
                        st4, _ = await put(key, base_res, reason="")
                        T["tanpa_alasan_ditolak"] = (st4 == 400)
                    r = await c.post("/api/config/values/reset", json={"key": key, "scope_type": "global", "reason": "pulihkan"}, headers=H)
                    T["pulihkan"] = r.status_code
                    T["setelah_pulih_default"] = same(await resolver.value_of(key), e.get("default"))
                except Exception as exc:
                    T["GALAT"] = f"{type(exc).__name__}: {exc}"[:300]
                res.append(row)
    json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1, default=str)
    print("kunci diuji:", len(res))
asyncio.run(main())
