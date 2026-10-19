"""GL-01 Fase A/C — Pemetaan Akun: resolver, API, remap jurnal otomatis, hak akses."""
import asyncio
import os
import sys

import requests
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
LOOP = asyncio.new_event_loop()


def _login(email, pw="demo1234"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


ADMIN = _login("admin@kainnusantara.id", "demo12345")
FIN = _login("finance@kainnusantara.id")
SALES = _login("sales@kainnusantara.id")
KEY = "retur.ongkir_perusahaan"


def _cleanup():
    DB.gl_account_mappings.delete_many({"key": {"$in": [KEY, "persediaan.penghapusan"]}})


def test_list_defaults_and_permissions():
    _cleanup()
    r = requests.get(f"{BASE}/gl/account-mappings", headers=ADMIN)
    assert r.status_code == 200
    rows = {x["key"]: x for x in r.json()["rows"]}
    assert rows[KEY]["account_code"] == "6-4500" and rows[KEY]["source"] == "default"
    assert requests.get(f"{BASE}/gl/account-mappings", headers=SALES).status_code == 403


def test_type_validation_reason_and_history():
    _cleanup()
    bad = requests.put(f"{BASE}/gl/account-mappings/{KEY}", headers=FIN, json={"account_code": "1-1100", "reason": "uji salah jenis"})
    assert bad.status_code == 400
    short = requests.put(f"{BASE}/gl/account-mappings/{KEY}", headers=FIN, json={"account_code": "6-4600", "reason": "x"})
    assert short.status_code == 400
    ok = requests.put(f"{BASE}/gl/account-mappings/{KEY}", headers=FIN,
                      json={"account_code": "6-4600", "entity_id": "ent_ksc", "reason": "uji khusus PT"})
    assert ok.status_code == 200, ok.text
    pt = {x["key"]: x for x in requests.get(f"{BASE}/gl/account-mappings?entity_id=ent_ksc", headers=ADMIN).json()["rows"]}
    gl = {x["key"]: x for x in requests.get(f"{BASE}/gl/account-mappings", headers=ADMIN).json()["rows"]}
    assert pt[KEY]["account_code"] == "6-4600" and pt[KEY]["source"] == "entity"
    assert gl[KEY]["account_code"] == "6-4500"
    h = requests.get(f"{BASE}/gl/account-mappings/history?key={KEY}&entity_id=ent_ksc", headers=ADMIN).json()
    assert h and h[0]["from_code"] == "6-4500" and h[0]["to_code"] == "6-4600"
    rs = requests.post(f"{BASE}/gl/account-mappings/{KEY}/reset", headers=FIN, json={"entity_id": "ent_ksc", "reason": "kembali global"})
    assert rs.status_code == 200 and rs.json()["account_code"] == "6-4500"
    _cleanup()


def test_remap_identical_without_mapping_and_follows_mapping():
    _cleanup()
    from services import gl_mapping_service as svc
    lines = [{"account_code": "5-9500", "debit": 10, "credit": 0}, {"account_code": "1-1300", "debit": 0, "credit": 10}]
    svc.invalidate()
    same = LOOP.run_until_complete(svc.remap_lines(lines, "ent_ksc", "inventory_writeoff"))
    assert [x["account_code"] for x in same] == ["5-9500", "1-1300"]
    DB.gl_account_mappings.insert_one({"id": "glm_TEST", "key": "persediaan.penghapusan", "scope_type": "entity",
                                       "entity_id": "ent_ksc", "account_code": "6-9000"})
    svc.invalidate()
    moved = LOOP.run_until_complete(svc.remap_lines(lines, "ent_ksc", "inventory_writeoff"))
    assert moved[0]["account_code"] == "6-9000" and moved[0]["mapping_key"] == "persediaan.penghapusan"
    other = LOOP.run_until_complete(svc.remap_lines(lines, "ent_kanda", "inventory_writeoff"))
    assert other[0]["account_code"] == "5-9500"
    rev = LOOP.run_until_complete(svc.remap_lines(lines, "ent_ksc", "reversal"))
    assert rev[0]["account_code"] == "5-9500"
    _cleanup()
    svc.invalidate()
