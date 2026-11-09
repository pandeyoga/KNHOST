"""B2b (audit 2026-11-09) — pustaka kecil untuk menjalankan alur lewat API + memotret DB sebelum/sesudah.

HANYA untuk stack audit sementara (kn-tmp-b2b-*, DB salinan `test_database`). Dijalankan DI DALAM kontainer backend:
    docker exec kn-tmp-b2b-be python /app/scripts/audit/b2b_flows.py <skenario>
Sandi akun demo dibaca dari /app/AGENTS.md (tidak ditulis di sini).
"""
import json
import os
import re
import time
from datetime import datetime

import requests
from pymongo import MongoClient

BASE = os.environ.get("KN_BASE", "http://localhost:8001/api")
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
OUT = os.environ.get("B2B_OUT", "/tmp/b2b")
os.makedirs(OUT, exist_ok=True)
_TOK = {}
LOG = []


def _pw():
    p = os.environ.get("KN_DEMO_PASS")
    if p:
        return p
    txt = open("/app/AGENTS.md", encoding="utf-8").read()
    m = re.search(r"admin@kainnusantara\.id`\s*/\s*`([^`]+)`", txt)
    return m.group(1)


def login(email):
    if email in _TOK:
        return _TOK[email]
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": _pw()}, timeout=60)
    r.raise_for_status()
    b = r.json()
    tok = b.get("token") or b.get("access_token")
    _TOK[email] = tok
    return tok


def api(method, path, who="admin@kainnusantara.id", ent=None, params=None, body=None, files=None, data=None,
        headers=None, note="", quiet=False):
    h = {"Authorization": f"Bearer {login(who)}"} if who else {}
    if ent:
        h["X-Entity-Id"] = ent
    if headers:
        h.update(headers)
    t0 = time.time()
    r = requests.request(method, f"{BASE}{path}", params=params, json=body, files=files, data=data, headers=h,
                         timeout=120)
    try:
        js = r.json()
    except Exception:
        js = r.text[:500]
    rec = {"t": datetime.now().strftime("%H:%M:%S"), "who": who.split("@")[0] if who else "-", "ent": ent,
           "m": method, "path": path, "params": params, "body": body, "code": r.status_code,
           "ms": int((time.time() - t0) * 1000), "resp": _short(js), "note": note}
    LOG.append(rec)
    if not quiet:
        print(f"  [{r.status_code}] {method} {path} {params or ''} {note}")
        if r.status_code >= 400:
            print("     ->", json.dumps(_short(js), ensure_ascii=False)[:400])
    return r.status_code, js


def _short(js, n=1500):
    s = json.dumps(js, ensure_ascii=False, default=str)
    if len(s) <= n:
        return js
    return s[:n] + "…"


# ---------- potret DB ----------
ROLL_F = {"_id": 0, "id": 1, "roll_no": 1, "status": 1, "length_remaining": 1, "length_reserved": 1,
          "length_reservations": 1, "reserved_ref": 1, "active_movement": 1, "warehouse_id": 1, "owner_entity_id": 1,
          "parent_roll_id": 1, "rfid_tag_id": 1, "journey.stage": 1, "earmarked_for": 1, "cut": 1, "hold": 1,
          "is_remnant": 1, "lot": 1, "gate_exit": 1, "shipped_at": 1, "delivered_at": 1}


def rolls(q):
    return {r["id"]: r for r in DB.inventory_rolls.find(q, ROLL_F)}


def snap(spec):
    """spec: {nama: (koleksi, filter, proyeksi|None)} → {nama: {id: doc}}"""
    out = {}
    for name, (coll, flt, proj) in spec.items():
        p = proj or {"_id": 0}
        if "_id" not in p:
            p = dict(p, _id=0)
        docs = list(DB[coll].find(flt, p))
        out[name] = {(d.get("id") or d.get("key") or str(i)): d for i, d in enumerate(docs)}
    return out


def counts(spec):
    return {name: DB[coll].count_documents(flt) for name, (coll, flt) in spec.items()}


def diff(a, b, keys=None, path=""):
    """diff dangkal per dokumen: perubahan field level-1 (atau keys)."""
    out = []
    for name in set(a) | set(b):
        A, B = a.get(name, {}), b.get(name, {})
        for i in set(A) | set(B):
            x, y = A.get(i), B.get(i)
            if x is None:
                out.append((name, i, "+baru", _brief(y)))
                continue
            if y is None:
                out.append((name, i, "-hilang", _brief(x)))
                continue
            for k in sorted(set(x) | set(y)):
                if keys and k not in keys:
                    continue
                if x.get(k) != y.get(k):
                    out.append((name, i, k, f"{_brief(x.get(k))} → {_brief(y.get(k))}"))
    return out


def _brief(v, n=220):
    s = json.dumps(v, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[:n] + "…"


def show(d, title=""):
    if title:
        print(f"  Δ {title}: {len(d)}")
    for row in d[:60]:
        print("     ", " | ".join(str(c) for c in row))
    if len(d) > 60:
        print(f"      … +{len(d) - 60}")


def save(name, extra=None):
    fn = os.path.join(OUT, f"{name}.json")
    json.dump({"log": LOG, "extra": extra}, open(fn, "w"), ensure_ascii=False, default=str, indent=1)
    print("  disimpan", fn)


def free_rolls(product_id, ent, wh, n=5, min_len=0):
    q = {"product_id": product_id, "owner_entity_id": ent, "warehouse_id": wh, "status": "available",
         "length_remaining": {"$gt": min_len}, "$or": [{"length_reserved": {"$in": [None, 0]}},
                                                       {"length_reserved": {"$exists": False}}],
         "active_movement": None, "hold.held": {"$ne": True}}
    return list(DB.inventory_rolls.find(q, ROLL_F).sort("length_remaining", 1).limit(n))
