# Harness uji API UAT — dijalankan di dalam container backend (httpx tersedia).
import json, sys, time
import httpx

BASE = "http://localhost:8001/api"
PW = {"admin@kainnusantara.id": "demo12345", "wh.admin@kainnusantara.id": "demo12345"}
LOG = []


class Api:
    def __init__(self, email, entity="ent_ksc"):
        self.email = email
        self.c = httpx.Client(base_url=BASE, timeout=180)
        r = self.c.post("/auth/login", json={"email": email, "password": PW.get(email, "demo1234")})
        r.raise_for_status()
        self.token = r.json()["token"]
        self.user = r.json()["user"]
        self.c.headers["Authorization"] = f"Bearer {self.token}"
        if entity:
            self.c.headers["X-Entity-Id"] = entity

    def _do(self, m, path, **kw):
        r = self.c.request(m, path, **kw)
        try:
            body = r.json()
        except Exception:
            body = r.text[:500]
        return r.status_code, body

    def get(self, p, **kw):
        return self._do("GET", p, **kw)

    def post(self, p, js=None, **kw):
        return self._do("POST", p, json=js, **kw)

    def patch(self, p, js=None, **kw):
        return self._do("PATCH", p, json=js, **kw)


def short(b, n=400):
    s = json.dumps(b, ensure_ascii=False, default=str) if not isinstance(b, str) else b
    return s[:n]


def step(name, code, body, expect=(200,)):
    ok = code in expect
    print(("OK  " if ok else "!!  ") + f"[{code}] {name}: " + short(body, 300))
    LOG.append({"step": name, "code": code, "ok": ok, "body": short(body, 1500)})
    return ok


def need(name, code, body, expect=(200,)):
    if not step(name, code, body, expect):
        print("BERHENTI:", name)
        dump()
        sys.exit(1)
    return body


def dump(path="/tmp/uat_log.json"):
    with open(path, "w") as f:
        json.dump(LOG, f, ensure_ascii=False, indent=1)
