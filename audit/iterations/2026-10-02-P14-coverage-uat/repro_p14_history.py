"""P14 — riwayat perubahan per sumber daya, gaji disamarkan, secret-scan CI/hook, login/revoke, indeks.

Usage: cd /app/backend && python ../audit/iterations/2026-10-02-P14-coverage-uat/repro_p14_history.py [repo_root]
HTTP ke backend lokal http://localhost:8001 (DB sintetis). Data uji berprefiks TEST_P14 dan dibersihkan.
"""
import asyncio
import json
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("..").resolve()
ENT = "ent_ksc"
T = f"TEST_P14_{uuid.uuid4().hex[:6]}"
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def login(c, email):
    r = await c.post("/api/auth/login", json={"email": email, "password": "demo12345"})
    return r, (r.json().get("token") if r.status_code == 200 else None)


def hdr(tok):
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": ENT}


async def history(c, h, etype, eid):
    r = await c.get("/api/audit-logs/resource", params={"entity_type": etype, "entity_id": eid}, headers=h)
    return r, (r.json() if r.status_code == 200 else {})


async def gl_checks(c, h, db):
    code = f"9-{uuid.uuid4().int % 90000 + 10000}"
    await c.post("/api/gl/accounts", json={"code": code, "name": f"{T} Lama", "type": "expense", "is_postable": True}, headers=h)
    await c.patch(f"/api/gl/accounts/{code}", json={"name": f"{T} Baru"}, headers=h)
    r, body = await history(c, h, "gl_account", code)
    upd = next((x for x in body.get("items", []) if x["action"] == "gl_account_updated"), None)
    d = next((x for x in (upd or {}).get("diff", []) if x["field"] == "name"), {})
    check("AUDIT-01", "riwayat akun GL: nilai lama → baru per field", r.status_code == 200 and d.get("from") == f"{T} Lama" and d.get("to") == f"{T} Baru", d)
    check("AUDIT-01", "riwayat akun GL: sidik isi utuh (integrity ok)", upd and upd.get("integrity") == "ok", (upd or {}).get("integrity"))
    check("AUDIT-01", "riwayat akun GL: pelaku & sumber tercatat", upd and upd.get("actor_id") and upd.get("source"), (upd or {}).get("actor_id"))
    if upd:
        await db.audit_logs.update_one({"id": upd["id"]}, {"$set": {"after.name": "diubah diam-diam"}})
        _, body2 = await history(c, h, "gl_account", code)
        t = next((x for x in body2.get("items", []) if x["id"] == upd["id"]), {})
        check("AUDIT-01", "baris audit yang diubah sesudahnya terdeteksi (mismatch)", t.get("integrity") == "mismatch", t.get("integrity"))
    await c.delete(f"/api/gl/accounts/{code}", headers=h)
    await db.audit_logs.delete_many({"entity_id": code})
    await db.gl_accounts.delete_many({"code": code})


async def customer_checks(c, h, db):
    cust = await db.customers.find_one({"entity_id": ENT, "status": {"$ne": "inactive"}}, {"_id": 0, "id": 1, "pic_name": 1})
    if not cust:
        check("AUDIT-01", "pelanggan uji tersedia", False, "tidak ada pelanggan ent_ksc")
        return
    old = cust.get("pic_name") or ""
    new = f"{T} PIC"
    r = await c.patch(f"/api/customers/{cust['id']}", json={"data": {"pic_name": new}}, headers=h)
    new = (r.json() or {}).get("pic_name", new) if r.status_code == 200 else new  # EYD otomatis K-1
    _, body = await history(c, h, "customer", cust["id"])
    row = next((x for x in body.get("items", []) if x["action"] == "customer_updated"
                and any(d["field"] == "pic_name" and d.get("to") == new for d in x.get("diff", []))), None)
    d = next((x for x in (row or {}).get("diff", []) if x["field"] == "pic_name"), {})
    check("AUDIT-01", "riwayat pelanggan: nilai lama → baru", r.status_code == 200 and d.get("from") == old and d.get("to") == new, f"{r.status_code} {d}")
    await c.patch(f"/api/customers/{cust['id']}", json={"data": {"pic_name": old}}, headers=h)
    await db.audit_logs.delete_many({"entity_type": "customer", "entity_id": cust["id"],
                                     "$or": [{"after.pic_name": new}, {"before.pic_name": new}]})


async def salary_checks(c, h, db):
    emp = await db.hr_employees.find_one({"entity_id": ENT, "status": {"$ne": "resigned"}, "base_salary": {"$gt": 0}},
                                         {"_id": 0, "id": 1, "base_salary": 1})
    if not emp:
        check("AUDIT-02", "karyawan uji tersedia", False, "tidak ada karyawan bergaji")
        return
    old = emp["base_salary"]
    new = round(float(old) + 1234.0, 2)
    r = await c.patch(f"/api/hr/employees/{emp['id']}", json={"data": {"base_salary": new}}, headers=h)
    row = await db.audit_logs.find_one({"entity_id": emp["id"], "action": "hr_employee_updated"}, {"_id": 0}, sort=[("timestamp", -1)])
    d = next((x for x in (row or {}).get("diff", []) if x["field"] == "base_salary"), {})
    raw = json.dumps(row or {}, default=str)
    check("AUDIT-02", "perubahan gaji pokok tercatat sebagai field berubah", r.status_code == 200 and d.get("masked") is True, f"{r.status_code} {d}")
    check("AUDIT-02", "nilai gaji lama/baru disamarkan [REDACTED]", d.get("from") == "[REDACTED]" and d.get("to") == "[REDACTED]", d)
    check("AUDIT-02", "angka gaji tidak bocor ke baris audit", str(new) not in raw and str(int(new)) not in raw.replace(".0", ""), "")
    await c.patch(f"/api/hr/employees/{emp['id']}", json={"data": {"base_salary": old}}, headers=h)
    r2 = await c.patch(f"/api/hr/employees/{emp['id']}", json={"data": {"base_salary": old}}, headers=h)
    row2 = await db.audit_logs.find_one({"entity_id": emp["id"], "action": "hr_employee_updated"}, {"_id": 0}, sort=[("timestamp", -1)])
    check("AUDIT-02", "gaji sama (tanpa perubahan) tidak dicatat sebagai berubah",
          r2.status_code == 200 and not any(x["field"] == "base_salary" for x in (row2 or {}).get("diff", [])), (row2 or {}).get("diff"))


async def auth_checks(c, db):
    bad = await c.post("/api/auth/login", json={"email": "admin@kainnusantara.id", "password": "salah-sekali"})
    check("AUTH-01", "login sandi salah ditolak 401", bad.status_code == 401, bad.status_code)
    r, tok = await login(c, "sales@kainnusantara.id")
    me = await c.get("/api/auth/me", headers=hdr(tok))
    check("AUTH-01", "login valid → /auth/me 200", r.status_code == 200 and me.status_code == 200, f"{r.status_code}/{me.status_code}")
    hist, _ = await history(c, hdr(tok), "customer", "x")
    check("AUDIT-01", "sales tanpa audit.view ditolak 403 pada riwayat", hist.status_code == 403, hist.status_code)
    await c.post("/api/auth/logout", headers=hdr(tok))
    me2 = await c.get("/api/auth/me", headers=hdr(tok))
    check("AUTH-01", "token dicabut setelah logout → 401", me2.status_code == 401, me2.status_code)


async def index_checks(db):
    from indexes import INDEX_SPECS, _index_name
    missing = []
    for coll, specs in INDEX_SPECS.items():
        have = set((await db[coll].index_information()).keys())
        missing += [f"{coll}.{_index_name(k)}" for k in specs if _index_name(k) not in have]
    check("OPS-01", "seluruh indeks INDEX_SPECS ada di DB sesudah bootstrap", not missing, missing[:10])


async def rf09_checks(db):
    """RF-09 diadaptasi ke kontrak RF-10 (P08): sesi cycle count discan lewat kind cycle_count, seperti endpoint."""
    from fastapi import HTTPException
    from services import cycle_count_service as cc
    from services import rfid_print_service as ps
    a, b = "ent_ksc", "ent_kanda"
    roll = await db.inventory_rolls.find_one({"owner_entity_id": a, "rfid_tag_id": {"$nin": [None, ""]}}, {"_id": 0, "warehouse_id": 1})
    if not roll:
        check("RF-09", "roll ber-tag entitas A tersedia", False, "fixture kosong")
        return
    sess = await cc.start(roll["warehouse_id"], [a, b], "audit-p14")
    try:
        await ps.scan_session(sess["id"], [], [a, b], ["print_verify", "cycle_count"], "manual", "audit-p14")
        check("RF-09", "sesi cycle count multi-entitas dapat discan oleh scope pembuatnya", True)
    except HTTPException as exc:
        check("RF-09", "sesi cycle count multi-entitas dapat discan oleh scope pembuatnya", False, exc.detail)
    try:
        await ps.scan_session(sess["id"], [], [a], ["print_verify", "cycle_count"], "manual", "audit-p14")
        check("RF-08", "user A-saja tidak dapat memindai sesi A+B", False, "lolos")
    except HTTPException as exc:
        check("RF-08", "user A-saja tidak dapat memindai sesi A+B", exc.status_code in (403, 404), exc.status_code)
    await db.rfid_verify_sessions.delete_one({"id": sess["id"]})


def static_checks():
    scan = subprocess.run([sys.executable, "scripts/guardrails/verify_no_secrets.py"], cwd=ROOT, capture_output=True, text=True)
    check("AUDIT-03", "pemindai secret: 0 temuan (exit 0)", scan.returncode == 0, scan.stdout.strip()[-120:])
    wf = ROOT / ".github/workflows/secret-scan.yml"
    check("AUDIT-03", "workflow CI menjalankan pemindai secret", wf.exists() and "verify_no_secrets.py" in wf.read_text())
    hook = (ROOT / "scripts/install_hooks.sh").read_text()
    check("AUDIT-03", "pre-commit hook memblokir bila secret terdeteksi", "verify_no_secrets.py" in hook and "exit 1" in hook)


async def main():
    import httpx
    from db import db
    async with httpx.AsyncClient(base_url="http://localhost:8001", timeout=60) as c:
        _, tok = await login(c, "admin@kainnusantara.id")
        h = hdr(tok)
        for fn in (gl_checks, customer_checks, salary_checks):
            try:
                await fn(c, h, db)
            except Exception as exc:  # noqa: BLE001
                check("P14", fn.__name__, False, repr(exc)[:200])
        await auth_checks(c, db)
    await index_checks(db)
    try:
        await rf09_checks(db)
    except Exception as exc:  # noqa: BLE001
        check("RF-09", "rf09_checks", False, repr(exc)[:200])
    static_checks()
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
