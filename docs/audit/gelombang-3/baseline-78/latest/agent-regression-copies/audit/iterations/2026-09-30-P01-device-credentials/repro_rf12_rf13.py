"""RF-12/RF-13 invariant check via HTTP (local synthetic DB). Usage: KN_API=http://127.0.0.1:8009/api python repro_rf12_rf13.py"""
import json
import os
import sys

import httpx

API = os.environ["KN_API"]
PWD = os.environ.get("KN_TEST_PASSWORD", "demo12345")
results = []


def check(name, ok, detail=""):
    results.append({"invariant": name, "pass": bool(ok), "detail": detail})


def login(email):
    r = httpx.post(f"{API}/auth/login", json={"email": email, "password": PWD}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def leaks(dev):
    return sorted(k for k in dev if "api_key" in k and k not in ("has_api_key", "api_key_hint", "api_key_at"))


admin, wh = login("admin@kainnusantara.id"), login("warehouse@kainnusantara.id")
c = httpx.Client(timeout=30)
wh_id = c.get(f"{API}/rfid/devices", headers=admin).json()["devices"][0]["warehouse_id"]
dev = c.post(f"{API}/rfid/devices", headers=admin, json={
    "name": "Audit RF12 Gate", "type": "gate", "direction": "in", "warehouse_id": wh_id}).json()
did = dev["id"]
try:
    key1 = c.post(f"{API}/rfid/devices/{did}/api-key", headers=admin).json().get("api_key")
    check("issue returns key once", bool(key1))
    for who, h in (("warehouse", wh), ("admin", admin)):
        lst = c.get(f"{API}/rfid/devices", headers=h).json()["devices"]
        mine = next(d for d in lst if d["id"] == did)
        check(f"list as {who} has no key/hash", not leaks(mine) and key1 not in json.dumps(lst), leaks(mine))
    health = c.get(f"{API}/rfid/device-health", headers=admin)
    if health.status_code == 200:
        check("device-health has no key/hash", key1 not in health.text and "api_key_hash" not in health.text)
    patched = c.patch(f"{API}/rfid/devices/{did}", headers=admin, json={"location": "Dock"}).json()
    check("update response has no key/hash", not leaks(patched), leaks(patched))
    again = c.post(f"{API}/rfid/devices/{did}/api-key", headers=admin)
    check("non-regenerate re-issue does not reveal existing key", key1 not in again.text, again.status_code)
    dk = {"X-Device-Key": key1}
    check("enabled device heartbeat accepted", c.post(f"{API}/rfid/heartbeat", headers=dk).status_code == 200)
    c.patch(f"{API}/rfid/devices/{did}", headers=admin, json={"status": "offline"})
    check("offline-but-enabled can reconnect", c.post(f"{API}/rfid/heartbeat", headers=dk).status_code == 200)
    c.patch(f"{API}/rfid/devices/{did}", headers=admin, json={"enabled": False, "status": "offline"})
    for path, method, body in (("/rfid/heartbeat", "post", None), ("/rfid/ingest", "post", {"epcs": []}),
                               ("/rfid/device-jobs/pending", "get", None), ("/rfid/device-jobs/x/ack", "post", None)):
        r = c.request(method.upper(), f"{API}{path}", headers=dk, json=body)
        check(f"disabled rejected on {path}", r.status_code in (401, 403), r.status_code)
    cur = next(d for d in c.get(f"{API}/rfid/devices", headers=admin).json()["devices"] if d["id"] == did)
    check("heartbeat does not re-enable disabled device", cur.get("enabled") is False and cur.get("status") != "online",
          {"enabled": cur.get("enabled"), "status": cur.get("status")})
    c.patch(f"{API}/rfid/devices/{did}", headers=admin, json={"enabled": True})
    key2 = c.post(f"{API}/rfid/devices/{did}/api-key", headers=admin, params={"regenerate": True}).json().get("api_key")
    check("rotation invalidates old key", c.post(f"{API}/rfid/heartbeat", headers=dk).status_code == 401)
    check("rotated key works", c.post(f"{API}/rfid/heartbeat", headers={"X-Device-Key": key2 or ""}).status_code == 200)
    check("viewer cannot issue key", c.post(f"{API}/rfid/devices/{did}/api-key", headers=wh).status_code == 403)
finally:
    c.delete(f"{API}/rfid/devices/{did}", headers=admin)

print(json.dumps(results, indent=1))
print(f"SUMMARY pass={sum(r['pass'] for r in results)} fail={sum(not r['pass'] for r in results)}")
sys.exit(0 if all(r["pass"] for r in results) else 1)
