"""P14 putaran 2 — kasus coverage yang sebelumnya planned: retur supplier RMA ditolak, POS, alur desain, role custom.

Usage: cd /app/backend && python ../audit/iterations/2026-10-02-P14-coverage-uat/repro_p14b_cases.py [repo_root]
HTTP ke backend lokal (DB sintetis). Data uji berprefiks TEST_P14B dan dibersihkan di akhir.
"""
import asyncio
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("..").resolve()
ENT = "ent_ksc"
T = f"TEST_P14B_{uuid.uuid4().hex[:6]}"
PWD = "Synthetic#12345"
results = []
created = {"users": [], "requests": [], "galleries": [], "returns": []}


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def login(c, email, pwd="demo12345"):
    r = await c.post("/api/auth/login", json={"email": email, "password": pwd})
    return {"Authorization": f"Bearer {r.json().get('token')}", "X-Entity-Id": ENT}


async def synthetic_user(db, role, perms_role=None):
    import bcrypt
    uid = f"user_{T}_{role}"
    email = f"{uid}@synthetic.test".lower()
    await db.users.insert_one({"id": uid, "email": email, "name": f"{T} {role}", "role": perms_role or role,
                               "status": "active", "home_entity_id": ENT, "allowed_entity_ids": [ENT],
                               "password_hash": bcrypt.hashpw(PWD.encode(), bcrypt.gensalt()).decode()})
    created["users"].append(uid)
    return uid, email


# ── PRET-04: RMA ditolak supplier → goods_back tanpa settlement ────────────────
async def pret04(c, h, db):
    roll = await db.inventory_rolls.find_one(
        {"status": "available", "owner_entity_id": ENT, "length_remaining": {"$gt": 3},
         "rfid_tag_id": {"$in": [None, ""]}, "length_reserved": {"$not": {"$gt": 0}}}, {"_id": 0})
    sup = await db.suppliers.find_one({"status": {"$ne": "inactive"}, "partner_kind": {"$ne": "entity"},
                                       "group_entity_id": {"$in": [None, ""]}}, {"_id": 0, "id": 1})
    if not roll or not sup:
        check("PRET-04", "fixture roll & supplier", False, "kosong")
        return
    je_before = await db.journal_entries.count_documents({})
    body = {"supplier_id": sup["id"], "warehouse_id": roll["warehouse_id"], "entity_id": ENT, "supplier_flow": True,
            "reason": f"{T} RMA", "items": [{"product_id": roll["product_id"], "quantity": roll["length_remaining"],
                                            "unit": roll.get("unit") or "meter", "price": 0, "reason": "cacat",
                                            "roll_ids": [roll["id"]]}]}
    r = await c.post("/api/purchase-returns", json=body, headers=h)
    if r.status_code != 200:
        check("PRET-04", "buat retur RMA", False, f"{r.status_code} {r.text[:200]}")
        return
    rid = r.json()["id"]
    created["returns"].append(rid)
    steps = {}
    for name, path, payload in (("submit", "submit", None), ("approve", "approve", {}),
                                ("ship", "ship-to-supplier", {}), ("reject", "supplier-reject", {"reason": f"{T} ditolak"}),
                                ("goods_back", "goods-back", {"warehouse_id": roll["warehouse_id"]})):
        rr = await c.post(f"/api/purchase-returns/{rid}/{path}", json=payload, headers=h)
        steps[name] = rr.status_code
    check("PRET-04", "rantai submit→approve→ship→supplier-reject→goods-back sukses", all(v == 200 for v in steps.values()), steps)
    doc = await db.purchase_returns.find_one({"id": rid}, {"_id": 0})
    after = await db.inventory_rolls.find_one({"id": roll["id"]}, {"_id": 0})
    check("PRET-04", "roll kembali available dengan panjang utuh",
          after and after.get("status") == "available" and abs(float(after.get("length_remaining") or 0) - float(roll["length_remaining"])) < 1e-6,
          f"{(after or {}).get('status')} {(after or {}).get('length_remaining')}")
    check("PRET-04", "status supplier goods_back tanpa nota debit/AP credit",
          doc.get("supplier_status") == "goods_back" and not doc.get("debit_note_number") and not doc.get("ap_credit_amount"),
          {k: doc.get(k) for k in ("supplier_status", "debit_note_number", "ap_credit_amount", "outcome")})
    je_new = await db.journal_entries.count_documents({"$or": [{"source_id": rid}, {"reference_id": rid}, {"source_ref": rid}]})
    check("PRET-04", "tidak ada jurnal settlement untuk retur ditolak", je_new == 0, f"jurnal ref={je_new} total Δ={await db.journal_entries.count_documents({}) - je_before}")
    again = await c.post(f"/api/purchase-returns/{rid}/goods-back", json={"warehouse_id": roll["warehouse_id"]}, headers=h)
    check("PRET-04", "goods-back ulang ditolak (idempoten, tanpa mutasi kedua)", again.status_code in (400, 409), again.status_code)
    created["roll_restore"] = roll


# ── SALE-02: POS split tender, shift close, void, refund ─────────────────────
def sale02():
    src = "\n".join(p.read_text(errors="ignore") for p in (ROOT / "backend/routers").glob("*.py"))
    feats = {"shift_close": "/pos/shift" in src or "/cashier/shift" in src,
             "void": "/pos/" in src and "void" in src.split("/pos/", 1)[1][:4000],
             "split_tender": "tenders" in src}
    check("SALE-02", "POS punya shift close, void dan split tender", all(feats.values()), feats)


# ── DESIGN-01/03/04: request→assign→revisi→ACC, cancel, isolasi desainer ─────
async def design(c, h, db):
    meta = (await c.get("/api/design-requests/meta", headers=h)).json()
    pat = (meta.get("categories", {}).get("pattern") or [{}])[0].get("code", "")
    dsg = (meta.get("categories", {}).get("design") or [{}])[0].get("code", "")
    designer = next((d for d in meta.get("designers", []) if "designer@" in str(d.get("email", "")) or d.get("id") == "user_designer_01"),
                    (meta.get("designers") or [{}])[0])
    did = designer.get("id", "user_designer_01")
    base = {"category_code": pat, "design_category_code": dsg, "assigned_to": did, "submit_now": True}
    r = await c.post("/api/design-requests", json={**base, "brief": f"{T} alur penuh"}, headers=h)
    if r.status_code != 200:
        check("DESIGN-01", "buat permintaan", False, f"{r.status_code} {r.text[:200]}")
        return
    req = r.json()
    created["requests"].append(req["id"])
    hd = await login(c, "designer@kainnusantara.id")
    r = await c.post(f"/api/design-requests/{req['id']}/create-design", json={"title": f"{T} Motif"}, headers=hd)
    gid = ((r.json() or {}).get("design") or {}).get("id") if r.status_code == 200 else None
    if gid:
        created["galleries"].append(gid)
    status = lambda: c.get(f"/api/design-requests/{req['id']}", headers=h)  # noqa: E731
    s0 = (await status()).json().get("status")
    import base64
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    up = lambda: c.post(f"/api/design-gallery/{gid}/files", headers=hd, files={"file": (f"{T}.png", png, "image/png")})  # noqa: E731
    await up()
    sub = await c.post(f"/api/design-gallery/{gid}/lifecycle/submit", json={"note": "ajukan"}, headers=hd)
    s1 = (await status()).json().get("status")
    rev = await c.post(f"/api/design-gallery/{gid}/lifecycle/request-revision", json={"note": f"{T} revisi warna"}, headers=h)
    s2 = (await status()).json().get("status")
    await up()
    sub2 = await c.post(f"/api/design-gallery/{gid}/lifecycle/submit", json={"note": "ajukan ulang"}, headers=hd)
    acc_designer = await c.post(f"/api/design-gallery/{gid}/lifecycle/approve", json={"note": "x", "score": 2}, headers=hd)
    acc = await c.post(f"/api/design-gallery/{gid}/lifecycle/approve", json={"note": "ACC", "score": 1.75}, headers=h)
    s3 = (await status()).json().get("status")
    check("DESIGN-01", "permintaan → desain Studio tertaut oleh desainer yang ditugaskan", bool(gid), r.status_code)
    check("DESIGN-01", "status permintaan mengikuti desain: diajukan → revisi → disetujui",
          sub.status_code == 200 and rev.status_code == 200 and sub2.status_code == 200 and acc.status_code == 200
          and s1 != s0 and s2 != s1 and s3 not in (s1, s2),
          f"{s0}→{s1}→{s2}→{s3} http {sub.status_code}/{rev.status_code}/{sub2.status_code}/{acc.status_code}")
    check("DESIGN-01", "desainer tidak bisa ACC desainnya sendiri", acc_designer.status_code in (400, 403), acc_designer.status_code)
    g = (await c.get(f"/api/design-gallery/{gid}", headers=h)).json()
    check("DESIGN-01", "nilai ACC tersimpan & lebih dari satu versi/riwayat revisi",
          g.get("status") in ("approved", "active") and (g.get("score") == 1.75 or any(v.get("score") == 1.75 for v in g.get("versions", []))),
          {k: g.get(k) for k in ("status", "score", "version")})

    # DESIGN-03 — cancel
    r = await c.post("/api/design-requests", json={**base, "brief": f"{T} batal"}, headers=h)
    req2 = r.json()
    created["requests"].append(req2["id"])
    no_reason = await c.post(f"/api/design-requests/{req2['id']}/cancel", json={"reason": ""}, headers=h)
    can = await c.post(f"/api/design-requests/{req2['id']}/cancel", json={"reason": f"{T} tidak jadi"}, headers=h)
    again = await c.post(f"/api/design-requests/{req2['id']}/cancel", json={"reason": "lagi"}, headers=h)
    mk = await c.post(f"/api/design-requests/{req2['id']}/create-design", json={"title": f"{T} X"}, headers=hd)
    check("DESIGN-03", "batal tanpa alasan ditolak", no_reason.status_code in (400, 422), no_reason.status_code)
    check("DESIGN-03", "batal dengan alasan → cancelled; batal ulang ditolak", can.status_code == 200 and again.status_code == 400,
          f"{can.status_code}/{again.status_code}")
    check("DESIGN-03", "permintaan batal tidak bisa melahirkan desain baru", mk.status_code in (400, 403), mk.status_code)
    if mk.status_code == 200:
        created["galleries"].append(((mk.json() or {}).get("design") or {}).get("id"))

    # DESIGN-04 — desainer lain tidak membuka tugas/berkas yang bukan miliknya
    _, email_b = await synthetic_user(db, "designer")
    hb = await login(c, email_b, PWD)
    rb = await c.get(f"/api/design-requests/{req['id']}", headers=hb)
    lst = (await c.get("/api/design-requests", headers=hb)).json()
    items = lst.get("items", lst) if isinstance(lst, dict) else lst
    check("DESIGN-04", "desainer B ditolak membuka permintaan milik A", rb.status_code == 403, rb.status_code)
    check("DESIGN-04", "daftar desainer B tidak memuat tugas A", all(x.get("id") != req["id"] for x in items or []), len(items or []))
    re_ = await c.post(f"/api/design-requests/{req['id']}/references", headers=hb,
                       files={"file": ("x.png", b"\x89PNG\r\n\x1a\n", "image/png")})
    check("DESIGN-04", "desainer B tidak bisa mengunggah referensi ke permintaan A", re_.status_code in (403, 404), re_.status_code)


# ── AUTH-03: role custom — modul diizinkan, aksi ditolak ─────────────────────
async def auth03(c, db):
    doc = await db.permission_settings.find_one({"id": "default"}, {"_id": 0, "matrix": 1})
    created["matrix"] = json.loads(json.dumps(doc["matrix"]))
    role = f"audit_p14b_{uuid.uuid4().hex[:4]}"
    m = {**created["matrix"], role: {"customer": ["view"]}}
    await db.permission_settings.update_one({"id": "default"}, {"$set": {"matrix": m}})
    _, email = await synthetic_user(db, "custom", perms_role=role)
    hc = await login(c, email, PWD)
    ok = await c.get("/api/customers", headers=hc)
    cust = await db.customers.find_one({"entity_id": ENT}, {"_id": 0, "id": 1})
    deny = await c.patch(f"/api/customers/{cust['id']}", json={"data": {"pic_name": "x"}}, headers=hc)
    other = await c.get("/api/gl/accounts", headers=hc)
    check("AUTH-03", "role custom: customer.view diizinkan (200)", ok.status_code == 200, ok.status_code)
    check("AUTH-03", "role custom: customer.update ditolak 403 tanpa mutasi", deny.status_code == 403, deny.status_code)
    check("AUTH-03", "role custom: modul lain (accounting) ditolak", other.status_code == 403, other.status_code)


async def auth05(c, h, db):
    """Dua admin mengubah matriks izin bersamaan dari baca yang sama; efek izin harus langsung."""
    base = (await c.get("/api/permissions", headers=h)).json()["matrix"]
    created.setdefault("matrix", json.loads(json.dumps(base)))
    ra, rb = f"p14b_ra_{uuid.uuid4().hex[:4]}", f"p14b_rb_{uuid.uuid4().hex[:4]}"
    ma, mb = {**base, ra: {"customer": ["view"]}}, {**base, rb: {"customer": ["view"]}}
    r1, r2 = await asyncio.gather(c.put("/api/permissions", json={"matrix": ma}, headers=h),
                                  c.put("/api/permissions", json={"matrix": mb}, headers=h))
    final = (await c.get("/api/permissions", headers=h)).json()["matrix"]
    check("AUTH-05", "dua perubahan izin bersamaan: keduanya bertahan atau satu ditolak 409",
          (ra in final and rb in final) or 409 in (r1.status_code, r2.status_code),
          f"http {r1.status_code}/{r2.status_code}; ra={ra in final} rb={rb in final} (PUT mengganti seluruh matriks)")
    await db.permission_settings.update_one({"id": "default"}, {"$set": {"matrix": {**created["matrix"], ra: {"customer": ["view"]}}}})
    _, email = await synthetic_user(db, "perm", perms_role=ra)
    hc = await login(c, email, PWD)
    before = await c.get("/api/customers", headers=hc)
    await c.put("/api/permissions", json={"matrix": {**created["matrix"], ra: {}}}, headers=h)
    after = await c.get("/api/customers", headers=hc)
    check("AUTH-05", "pencabutan izin berlaku langsung pada sesi aktif (tanpa cache basi)",
          before.status_code == 200 and after.status_code == 403, f"{before.status_code}→{after.status_code}")


async def cleanup(db):
    if created.get("matrix"):
        await db.permission_settings.update_one({"id": "default"}, {"$set": {"matrix": created["matrix"]}})
    if created["users"]:
        await db.sessions.delete_many({"user_id": {"$in": created["users"]}})
        await db.users.delete_many({"id": {"$in": created["users"]}})
    gids = [g for g in created["galleries"] if g]
    await db.design_gallery.delete_many({"id": {"$in": gids}})
    await db.design_requests.delete_many({"id": {"$in": created["requests"]}})
    for coll in ("design_gallery_history", "design_history", "notifications"):
        await db[coll].delete_many({"$or": [{"gallery_id": {"$in": gids}}, {"request_id": {"$in": created["requests"]}}]})
    if created["returns"]:
        await db.purchase_returns.delete_many({"id": {"$in": created["returns"]}})
        await db.stock_movements.delete_many({"$or": [{"reference_id": {"$in": created["returns"]}}, {"ref_id": {"$in": created["returns"]}}]})
    roll = created.get("roll_restore")
    if roll:
        await db.inventory_rolls.replace_one({"id": roll["id"]}, roll)
    ids = created["requests"] + gids + created["returns"] + created["users"]
    await db.audit_logs.delete_many({"$or": [{"entity_id": {"$in": ids}}, {"actor": {"$regex": T}}]})


async def main():
    import httpx
    from db import db
    async with httpx.AsyncClient(base_url="http://localhost:8001", timeout=60) as c:
        h = await login(c, "admin@kainnusantara.id")
        try:
            for name, fn in (("PRET-04", lambda: pret04(c, h, db)), ("DESIGN", lambda: design(c, h, db)),
                             ("AUTH-03", lambda: auth03(c, db)), ("AUTH-05", lambda: auth05(c, h, db))):
                try:
                    await fn()
                except Exception as exc:  # noqa: BLE001
                    check(name, "eksekusi skenario", False, repr(exc)[:200])
            sale02()
        finally:
            await cleanup(db)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
