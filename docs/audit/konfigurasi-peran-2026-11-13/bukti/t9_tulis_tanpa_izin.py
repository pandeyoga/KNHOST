"""T9 — endpoint TULIS × peran tanpa izin: apakah gerbang izin benar-benar menolak.

    python t9_tulis_tanpa_izin.py <keluaran.json> <inventaris.json>

Isi permintaan dibuat otomatis dari skema OpenAPI aplikasi (field wajib diisi nilai contoh), supaya permintaan lolos
validasi bentuk dan sampai ke gerbang izin di dalam handler. Tiap endpoint dipanggil oleh tiga akun:

  kosong  : peran kustom TANPA acuan, semua modul "Tidak ada"         → harapan: 403 di semua endpoint berizin
  mgr0    : peran kustom beracuan Manajer, semua modul "Tidak ada"    → yang lolos = gerbang nama peran
  sopir   : peran bawaan driver                                        → pembanding

Jawaban 422 berarti isi buatan tidak lolos validasi sehingga gerbangnya TIDAK teruji (dihitung terpisah).
Jawaban selain 401/403/422 berarti permintaan melewati gerbang izin.
"""
import boot_app  # noqa: F401  (harus paling dulu)
import asyncio
import collections
import datetime
import json
import logging
import re
import sys

import httpx
import server
from db import db

logging.disable(logging.CRITICAL)
OUT = sys.argv[1]
INV = json.load(open(sys.argv[2]))
E1 = "ent_ksc"


def tmpl(p):
    return re.sub(r"\{[^}]+\}", "{}", p)


inv = {}
for r in INV:
    inv.setdefault((r["method"], tmpl(r["path"])), r)

SPEC = server.app.openapi()
COMP = SPEC.get("components", {}).get("schemas", {})


def deref(s):
    seen = 0
    while isinstance(s, dict) and "$ref" in s and seen < 20:
        s = COMP.get(s["$ref"].split("/")[-1], {})
        seen += 1
    return s or {}


def contoh(s, nama="", depth=0):
    """Nilai contoh yang lolos validasi bentuk untuk satu skema."""
    s = deref(s)
    if depth > 6:
        return None
    for k in ("anyOf", "oneOf"):
        if k in s:
            pil = [deref(x) for x in s[k]]
            non_null = [x for x in pil if x.get("type") != "null"]
            return contoh(non_null[0], nama, depth + 1) if non_null else None
    if "allOf" in s:
        gab = {}
        for x in s["allOf"]:
            v = contoh(x, nama, depth + 1)
            if isinstance(v, dict):
                gab.update(v)
            else:
                return v
        return gab
    if "enum" in s:
        return s["enum"][0]
    if "const" in s:
        return s["const"]
    t = s.get("type")
    if t == "object" or "properties" in s:
        out = {}
        req = set(s.get("required", []))
        for k, v in (s.get("properties") or {}).items():
            if k in req:
                out[k] = contoh(v, k, depth + 1)
        return out
    if t == "array":
        n = s.get("minItems", 1)
        return [contoh(s.get("items", {}), nama, depth + 1) for _ in range(max(1, n))]
    if t == "integer":
        lo = s.get("minimum", s.get("exclusiveMinimum", 0) + (1 if "exclusiveMinimum" in s else 0))
        return int(max(lo, 1))
    if t == "number":
        lo = s.get("minimum", 0)
        if "exclusiveMinimum" in s:
            lo = s["exclusiveMinimum"] + 1
        return float(max(lo, 1))
    if t == "boolean":
        return True
    if t == "string":
        fmt = s.get("format", "")
        n = nama.lower()
        if fmt == "date" or n.endswith("_date") or n in ("date", "tanggal", "as_of", "due_date"):
            return "2026-11-13"
        if fmt == "date-time" or n.endswith("_at"):
            return "2026-11-13T08:00:00+00:00"
        if fmt == "email" or "email" in n:
            return "uji@contoh.id"
        if "period" in n or n in ("month", "bulan"):
            return "2026-11"
        if s.get("pattern"):
            p = s["pattern"]
            if "\\d{4}-\\d{2}-\\d{2}" in p:
                return "2026-11-13"
            if "\\d{4}-\\d{2}" in p:
                return "2026-11"
        v = "uji"
        ml = s.get("minLength", 0)
        if ml > len(v):
            v = v + "x" * (ml - len(v))
        return v
    return {}


def isi_dan_query(path, method):
    op = (SPEC["paths"].get(path) or {}).get(method.lower()) or {}
    body, kind = None, None
    rb = (op.get("requestBody") or {}).get("content") or {}
    if "application/json" in rb:
        body, kind = contoh(rb["application/json"].get("schema", {})), "json"
    elif "multipart/form-data" in rb:
        kind = "multipart"
    elif "application/x-www-form-urlencoded" in rb:
        body, kind = contoh(rb["application/x-www-form-urlencoded"].get("schema", {})), "form"
    q = {}
    for p in op.get("parameters") or []:
        if p.get("in") == "query" and p.get("required"):
            q[p["name"]] = contoh(p.get("schema", {}), p["name"])
    return body, kind, q


async def main():
    out = {"hasil": {}, "peran": {}}
    async with server.lifespan(server.app):
        now = datetime.datetime.now(datetime.timezone.utc)
        admin = await db.users.find_one({"email": "admin@kainnusantara.id"})
        await db.sessions.insert_one({"token": "tok_admin", "user_id": admin["id"],
                                      "expires_at": now + datetime.timedelta(hours=8)})
        tr = httpx.ASGITransport(app=server.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=tr, base_url="http://uji", timeout=60) as c:
            HA = {"Authorization": "Bearer tok_admin", "X-Entity-Id": E1}
            mods = (await c.get("/api/access/modules", headers=HA)).json()
            mod_ids = [m["id"] for m in (mods.get("modules") if isinstance(mods, dict) else mods)]
            ids = {}
            for kode, label, base in (("kosong", "Uji Tanpa Acuan Kosong", ""), ("mgr0", "Uji Manajer Kosong", "manager")):
                r = await c.post("/api/access/roles", headers=HA, json={
                    "label": label, "base_role": base, "levels": {m: "none" for m in mod_ids}, "description": "uji T9"})
                assert r.status_code == 200, (r.status_code, r.text[:200])
                j = r.json()
                ids[kode] = (j.get("role") or j).get("id")
            ids["sopir"] = "driver"
            tmpl_user = await db.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0})
            tokens = {}
            for kode, rid in ids.items():
                u = {**tmpl_user, "id": f"usr_t9_{kode}", "email": f"t9_{kode}@x.id", "name": f"T9 {kode}", "role": rid}
                await db.users.insert_one(dict(u))
                await db.sessions.insert_one({"token": f"tok_t9_{kode}", "user_id": u["id"],
                                              "expires_at": now + datetime.timedelta(hours=8)})
                tokens[kode] = f"tok_t9_{kode}"
            roles = (await c.get("/api/access/roles", headers=HA)).json()
            roles = roles.get("roles") if isinstance(roles, dict) else roles
            for ro in roles:
                if ro["id"] in ids.values():
                    out["peran"][ro["id"]] = {"label": ro["label"], "base_role": ro.get("base_role", ""),
                                              "permissions": ro["permissions"]}
            rute = []
            for rt in server.app.routes:
                for m in (getattr(rt, "methods", None) or set()) - {"GET", "HEAD", "OPTIONS"}:
                    if rt.path.startswith("/api/"):
                        rute.append((m, rt.path))
            rute = sorted(set(rute))
            # Urutan: akun paling lemah dulu, supaya tulisannya (bila lolos) tidak mengubah hasil akun berikutnya.
            for kode in ("kosong", "sopir", "mgr0"):
                H = {"Authorization": f"Bearer {tokens[kode]}", "X-Entity-Id": E1}
                res = {}
                for m, p in rute:
                    if p in ("/api/auth/logout", "/api/auth/logout-all"):
                        continue
                    body, kind, q = isi_dan_query(p, m)
                    url = re.sub(r"\{[^}]+\}", "x", p)
                    kw = {"params": q, "headers": H}
                    if kind == "json":
                        kw["json"] = body
                    elif kind == "form":
                        kw["data"] = body
                    elif kind == "multipart":
                        kw["files"] = {"file": ("uji.txt", b"uji", "text/plain")}
                    try:
                        r = await c.request(m, url, **kw)
                        det = ""
                        if r.status_code >= 400:
                            try:
                                det = str(r.json().get("detail"))[:140]
                            except Exception:  # noqa: BLE001
                                det = r.text[:140]
                        res[f"{m} {p}"] = [r.status_code, det]
                    except Exception as exc:  # noqa: BLE001
                        res[f"{m} {p}"] = [-1, f"{type(exc).__name__}: {exc}"[:140]]
                out["hasil"][kode] = res
                print(kode, collections.Counter(v[0] for v in res.values()).most_common(10), flush=True)
            # sesi uji masih hidup? (memastikan tidak ada endpoint yang mematikan akun uji di tengah jalan)
            for kode in tokens:
                r = await c.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens[kode]}"})
                out.setdefault("sesi_akhir", {})[kode] = r.status_code
    out["inv"] = {f"{k[0]} {k[1]}": {"cat": v["cat"], "file": v["file"], "line": v["line"], "func": v["func"],
                                     "guards": v["guards"]} for k, v in inv.items() if k[0] != "GET"}
    json.dump(out, open(OUT, "w"), ensure_ascii=False, default=str)


asyncio.run(main())
