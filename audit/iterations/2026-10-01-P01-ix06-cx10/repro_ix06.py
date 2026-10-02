"""IX-06 invariants — payroll settings global vs entity layer (HTTP, LOCAL synthetic DB).

Usage: KN_API=https://<preview>/api MONGO_URL=... DB_NAME=... python repro_ix06.py
Fixture: role `audit_payroll_tester` (hr.view, hr.manage_payroll) + user ONLY in A=ent_ksc; B=ent_kanda.
Snapshots config_values + system_settings (hr/A/B) and restores them in `finally`.
"""
import json
import os
import sys
import uuid

import bcrypt
import httpx
from pymongo import MongoClient

API = os.environ["KN_API"]
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
A, B = "ent_ksc", "ent_kanda"
TAG = f"audit_ix06_{uuid.uuid4().hex[:6]}"
EMAIL, PWD = f"{TAG}@synthetic.test", "Synthetic#12345"
KEY = "hr.overtime.multiplier"
results = []


def check(name, ok, detail=""):
    results.append({"id": "IX-06", "invariant": name, "pass": bool(ok), "detail": detail})


def login(email, pwd="demo12345"):
    c = httpx.Client(timeout=30)
    r = c.post(f"{API}/auth/login", json={"email": email, "password": pwd})
    r.raise_for_status()
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return c


def eff(c, ent):
    r = c.get(f"{API}/hr/payroll/settings", headers={"X-Entity-Id": ent})
    return (r.json().get("overtime") or {}).get("multiplier") if r.status_code == 200 else f"HTTP{r.status_code}"


snap_cv = list(db.config_values.find({}))
snap_ss = {s: db.system_settings.find_one({"scope": s}) for s in ("hr", A, B)}
matrix_doc = db.permission_settings.find_one({"id": "default"}, {"_id": 0, "matrix": 1})
orig_matrix = json.loads(json.dumps(matrix_doc["matrix"]))
m = json.loads(json.dumps(orig_matrix))
m["audit_payroll_tester"] = {"hr": ["view", "manage_payroll"]}
db.permission_settings.update_one({"id": "default"}, {"$set": {"matrix": m}})
db.users.insert_one({"id": f"user_{TAG}", "email": EMAIL, "name": "Audit Payroll Tester", "role": "audit_payroll_tester",
                     "status": "active", "home_entity_id": A, "allowed_entity_ids": [A],
                     "password_hash": bcrypt.hashpw(PWD.encode(), bcrypt.gensalt()).decode()})
try:
    adm = login("admin@kainnusantara.id")
    u = login(EMAIL, PWD)
    u.headers["X-Entity-Id"] = A
    b0, a0 = eff(adm, B), eff(adm, A)
    new_a = 2.75 if a0 != 2.75 else 2.5
    r = u.put(f"{API}/hr/payroll/settings", json={"settings": {"overtime": {"multiplier": new_a}}})
    resp_val = (r.json().get("overtime") or {}).get("multiplier") if r.status_code == 200 else None
    check("A-only edit (default layer) succeeds on A", r.status_code == 200 and eff(adm, A) == new_a, f"{r.status_code} A={eff(adm, A)}")
    check("A-only edit does NOT change B", eff(adm, B) == b0, f"B before={b0} after={eff(adm, B)}")
    check("PUT response == reload (same scope)", resp_val == eff(u, A), f"resp={resp_val} reload={eff(u, A)}")
    r = u.put(f"{API}/hr/payroll/settings", json={"settings": {"overtime": {"multiplier": 2.0}}, "scope": "global"})
    check("A-only cannot write global baseline", r.status_code == 403 and eff(adm, B) == b0, f"{r.status_code} B={eff(adm, B)}")
    r = u.put(f"{API}/config/values", json={"items": [{"key": KEY, "value": 2.0, "scope_type": "entity", "scope_id": B, "reason": "synthetic"}]})
    check("A-only cannot write entity layer of B via Pusat Pengaturan", r.status_code == 403 and eff(adm, B) == b0, f"{r.status_code} B={eff(adm, B)}")
    r = u.put(f"{API}/config/values", json={"items": [{"key": KEY, "value": 2.0, "scope_type": "global", "reason": "synthetic"}]})
    check("A-only cannot write global via Pusat Pengaturan", r.status_code == 403 and eff(adm, B) == b0, f"{r.status_code} B={eff(adm, B)}")
    r = u.put(f"{API}/config/values", json={"items": [{"key": KEY, "value": new_a, "scope_type": "entity", "scope_id": A, "reason": "synthetic"}]})
    check("A-only can still write own entity layer via Pusat Pengaturan (control)", r.status_code == 200, f"{r.status_code} {r.text[:150]}")
    g_new = 1.9 if b0 != 1.9 else 1.8
    adm.headers["X-Entity-Id"] = A
    r = adm.put(f"{API}/hr/payroll/settings", json={"settings": {"overtime": {"multiplier": g_new}}, "scope": "global"})
    check("admin global edit changes inheriting B", r.status_code == 200 and eff(adm, B) == g_new, f"{r.status_code} B={eff(adm, B)}")
    check("admin global edit keeps A override", eff(adm, A) == new_a, f"A={eff(adm, A)}")
    r = adm.put(f"{API}/hr/payroll/settings", json={"settings": {"overtime": {"multiplier": "x"}}, "scope": "entity"})
    check("invalid value rejected 400", r.status_code == 400, f"{r.status_code}")
    r = adm.put(f"{API}/hr/payroll/settings", json={"settings": {"overtime": {"bogus_leaf": 1}}, "scope": "entity"})
    check("unknown leaf rejected 400", r.status_code == 400, f"{r.status_code}")
finally:
    db.config_values.delete_many({})
    if snap_cv:
        db.config_values.insert_many(snap_cv)
    for s, doc in snap_ss.items():
        db.system_settings.delete_many({"scope": s})
        if doc:
            db.system_settings.insert_one(doc)
    db.permission_settings.update_one({"id": "default"}, {"$set": {"matrix": orig_matrix}})
    db.users.delete_one({"email": EMAIL})
    db.sessions.delete_many({"user_id": f"user_{TAG}"})

print(json.dumps(results, indent=1, ensure_ascii=False))
print(f"SUMMARY pass={sum(r['pass'] for r in results)} fail={sum(not r['pass'] for r in results)}")
sys.exit(0 if all(r["pass"] for r in results) else 1)
