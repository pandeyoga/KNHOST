"""P18a — AUTH-01 (TTL sesi: kedaluwarsa, sliding renewal, sesi pra-TTL, user nonaktif, revoke)
dan AUTH-02 (sweep IDOR: SEMUA GET ber-satu-parameter diuji dengan id dokumen PT lain).

Usage: cd /app/backend && python ../audit/iterations/2026-10-03-P18-partial-coverage/repro_p18a.py
Self-clean: user sintetis & sesinya dihapus.
"""
import asyncio
import json
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
T = f"TEST_P18A_{uuid.uuid4().hex[:6]}"
PWD = "Demo-p18a-12345"
results = []
users = []
SKIP = re.compile(r"/(enums|wilayah|esign/verify|entity-masters|process-stages/for-line|pdf/sample|pdf/templates|"
                  r"pdf/branding|pdf/documents|entities|users|access/roles|approvals/queue-board|config|settings|help)\b")


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def synthetic(db, role, ents):
    import bcrypt
    uid = f"user_{T}_{role}".lower()
    await db.users.insert_one({"id": uid, "email": f"{uid}@synthetic.test", "name": f"{T} {role}", "role": role,
                               "status": "active", "home_entity_id": ents[0], "allowed_entity_ids": ents,
                               "password_hash": bcrypt.hashpw(PWD.encode(), bcrypt.gensalt()).decode()})
    users.append(uid)
    return f"{uid}@synthetic.test"


async def login(c, email, ent="ent_ksc", pwd=PWD):
    r = await c.post("/api/auth/login", json={"email": email, "password": pwd})
    tok = r.json().get("token")
    return tok, {"Authorization": f"Bearer {tok}", "X-Entity-Id": ent}


async def auth01(c, db):
    email = await synthetic(db, "sales", ["ent_ksc"])
    tok, h = await login(c, email)
    s = await db.sessions.find_one({"token": tok}, {"_id": 0})
    me = await c.get("/api/auth/me", headers=h)
    check("AUTH-01", "login valid → sesi ber-expires_at & /auth/me 200", me.status_code == 200 and s and s.get("expires_at"), me.status_code)
    bad = await c.post("/api/auth/login", json={"email": email, "password": "salah-total"})
    check("AUTH-01", "password salah → 401 tanpa sesi baru", bad.status_code in (400, 401) and not bad.json().get("token"), bad.status_code)
    # sliding renewal: sisa < setengah TTL → diperpanjang
    near = datetime.now(timezone.utc) + timedelta(minutes=5)
    await db.sessions.update_one({"token": tok}, {"$set": {"expires_at": near}})
    r = await c.get("/api/auth/me", headers=h)
    s = await db.sessions.find_one({"token": tok}, {"_id": 0})
    exp = s["expires_at"].replace(tzinfo=timezone.utc) if s["expires_at"].tzinfo is None else s["expires_at"]
    check("AUTH-01", "sisa TTL 5 menit → request 200 & expires_at diperpanjang (sliding)", r.status_code == 200 and exp > near + timedelta(hours=1), exp)
    # sesi pra-TTL (tanpa expires_at) → diberi masa berlaku
    await db.sessions.update_one({"token": tok}, {"$unset": {"expires_at": ""}})
    r = await c.get("/api/auth/me", headers=h)
    s = await db.sessions.find_one({"token": tok}, {"_id": 0})
    check("AUTH-01", "sesi lama tanpa expires_at → 200 lalu distempel expires_at", r.status_code == 200 and s.get("expires_at"), s.get("expires_at"))
    # time-travel: kedaluwarsa
    await db.sessions.update_one({"token": tok}, {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}})
    r = await c.get("/api/auth/me", headers=h)
    r2 = await c.get("/api/sales-orders", headers=h)
    check("AUTH-01", "expires_at lewat → 401 'kedaluwarsa' & sesi dihapus; request berikutnya tetap 401",
          r.status_code == 401 and "kedaluwarsa" in r.text.lower() and await db.sessions.count_documents({"token": tok}) == 0
          and r2.status_code == 401, f"{r.status_code} {r.text[:80]} / {r2.status_code}")
    # user dinonaktifkan → sesi aktif tak berlaku
    tok2, h2 = await login(c, email)
    await db.users.update_one({"email": email}, {"$set": {"status": "inactive"}})
    r = await c.get("/api/auth/me", headers=h2)
    check("AUTH-01", "user dinonaktifkan → sesi yang masih berlaku ditolak 401", r.status_code == 401, r.status_code)
    await db.users.update_one({"email": email}, {"$set": {"status": "active"}})
    lo = await c.post("/api/auth/logout", headers=h2)
    r = await c.get("/api/auth/me", headers=h2)
    check("AUTH-01", "logout me-revoke token (401 sesudahnya)", lo.status_code == 200 and r.status_code == 401, f"{lo.status_code}/{r.status_code}")
    idx = await db.sessions.index_information()
    ttl = [v for v in idx.values() if "expireAfterSeconds" in v]
    check("AUTH-01", "indeks TTL Mongo pada sessions.expires_at ada (pembersihan otomatis)", bool(ttl), list(idx))


def _blob(doc):
    # id saja sering DIGEMAKAN balik (mis. {"product_id": id, "items": []}) → bukan bocor.
    keys = [doc.get(k) for k in ("number", "code", "name", "roll_no", "debit_note_number", "invoice_number") if doc.get(k)]
    return [k for k in keys if isinstance(k, str) and len(k) >= 4]


async def auth02(c, db):
    from entity_scope import SCOPED_COLLECTIONS
    spec = (await c.get("/openapi.json")).json()["paths"]
    routes = [p for p, v in spec.items() if "get" in v and len(re.findall(r"\{", p)) == 1 and not SKIP.search(p)]
    other, own = {}, {}
    for coll in sorted(SCOPED_COLLECTIONS):
        if coll in ("audit_logs", "notifications") or coll.startswith("interco_"):
            continue  # interco_* = dokumen PASANGAN (penjual & pembeli sama-sama pihak) → sah dibaca kedua PT
        for ent, bag in (("ent_kanda", other), ("ent_ksc", own)):
            d = await db[coll].find_one({"$or": [{"entity_id": ent}, {"owner_entity_id": ent}], "id": {"$exists": True}}, {"_id": 0})
            if d:
                bag[coll] = d
    # admin/manager = CROSS_ENTITY_ROLES (lintas PT by design) → sweep memakai peran ber-penugasan.
    hs = []
    for role in ("finance", "warehouse_admin", "sales_admin", "md"):
        hs.append((role, (await login(c, await synthetic(db, role, ["ent_ksc"])))[1]))
    h = hs[0][1]
    sem = asyncio.Semaphore(16)
    leaks, hits200, tried = [], 0, 0

    async def probe(path, coll, doc, hdr):
        async with sem:
            url = re.sub(r"\{[^}]+\}", doc["id"], path)
            try:
                r = await c.get(url, headers=hdr)
            except Exception:  # noqa: BLE001
                return None
            return r.status_code, (r.text if r.status_code == 200 else "")

    jobs = [(p, coll, d, role, hh) for role, hh in hs for p in routes for coll, d in other.items()]
    outs = await asyncio.gather(*(probe(p, coll, d, hh) for p, coll, d, _, hh in jobs))
    for (p, coll, d, role, _), out in zip(jobs, outs):
        if not out:
            continue
        tried += 1
        code, body = out
        if code == 200:
            hits200 += 1
            if any(k in body for k in _blob(d)):
                leaks.append(f"{role}: {p} ← {coll}:{d['id']}")
    print("LEAKS:", json.dumps(leaks, indent=0))
    check("AUTH-02", f"sweep {len(routes)} GET × {len(other)} koleksi ter-scope × {len(hs)} peran KSC-saja: tidak pernah menerima dokumen PT lain",
          not leaks and tried > 1000, {"tried": tried, "200_tanpa_isi": hits200, "bocor": leaks[:15]})
    pos = await asyncio.gather(*(probe(p, coll, d, hh) for _, hh in hs for p in routes for coll, d in own.items()))
    pos_ok = sum(1 for o in pos if o and o[0] == 200)
    check("AUTH-02", "kontrol positif: id dokumen PT sendiri terbaca di rute pemiliknya (sweep tidak hampa)", pos_ok >= 25, pos_ok)
    # IDOR antar-pemilik (sales lain di PT yang sama)
    _, hs1 = await login(c, "sales@kainnusantara.id", pwd="demo12345")
    _, hs2 = await login(c, "sales2@kainnusantara.id", pwd="demo12345")
    u1 = await db.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0, "id": 1})
    so = await db.sales_orders.find_one({"entity_id": "ent_ksc", "created_by": u1["id"]}, {"_id": 0})
    if so:
        own_r = await c.get(f"/api/sales-orders/{so['id']}", headers=hs1)
        oth = await c.get(f"/api/sales-orders/{so['id']}", headers=hs2)
        upd = await c.patch(f"/api/sales-orders/{so['id']}", json={"data": {"notes": T}}, headers=hs2)
        after = await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0, "notes": 1})
        check("AUTH-02", "SO milik sales A: A 200; sales B baca 403/404 & ubah ditolak tanpa mutasi",
              own_r.status_code == 200 and oth.status_code in (403, 404) and upd.status_code in (403, 404, 405)
              and after.get("notes") != T, f"{own_r.status_code}/{oth.status_code}/{upd.status_code}")
    else:
        check("AUTH-02", "ada SO milik sales A untuk uji antar-pemilik", False)
    # body/query: entity_id PT lain lewat query & body ditolak
    q = await c.get("/api/sales-orders", params={"entity_id": "ent_kanda"}, headers=h)
    body = await c.post("/api/purchase-returns", json={"entity_id": "ent_kanda", "items": [{"product_id": "x", "quantity": 1}]}, headers=h)
    check("AUTH-02", "entity_id PT lain lewat query (list) & body (create) → 403", q.status_code == 403 and body.status_code == 403,
          f"{q.status_code}/{body.status_code}")


async def main():
    import httpx
    from db import db
    async with httpx.AsyncClient(base_url="http://localhost:8001", timeout=60) as c:
        try:
            await auth01(c, db)
            await auth02(c, db)
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check("P18A", "eksekusi", False, repr(exc)[:200])
        finally:
            for uid in users:
                await db.sessions.delete_many({"user_id": uid})
                await db.users.delete_one({"id": uid})
                await db.audit_logs.delete_many({"actor_id": uid})
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
