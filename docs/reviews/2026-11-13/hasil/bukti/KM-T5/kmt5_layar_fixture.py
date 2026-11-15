"""Data contoh uji jalan layar KM-T5 (turunan fixture KM-T4) di database UJI lokal (data acuan): PT ent_ksc mode `sheet`, satu Lembar Insentif
sah (jurnal + masukan gaji), tiga tagihan insentif antar-PT contoh (hanya untuk tata letak tabel). Tidak dibersihkan
(restore_demo sebelum gate). Jangan untuk data nyata.
"""
import datetime
import os
import uuid

import pymongo
import requests

BASE = "http://localhost:8001/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()


def login(email, ent="ent_ksc"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ent}


adm, mgr = login("admin@kainnusantara.id"), login("manager@kainnusantara.id")
sales = DB.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0, "id": 1})
r = requests.post(f"{BASE}/incentive/components", headers=adm, timeout=30, json={
    "code": "KMT4LYR", "name": "Insentif Bulanan", "basis_period_type": "month", "columns": ["omzet"]})
print("komponen", r.status_code, r.text[:160] if r.status_code != 200 else "")
komp = r.json() if r.status_code == 200 else next(c for c in requests.get(f"{BASE}/incentive/components", headers=adm).json()["items"] if c["code"] == "KMT4LYR")
r = requests.put(f"{BASE}/config/values", headers=adm, timeout=30, json={"items": [{
    "key": "hr.payroll_commission_mode", "value": "sheet", "scope_type": "entity", "scope_id": "ent_ksc",
    "reason": "Uji jalan layar KM-T5 (lokal)"}]})
print("mode", r.status_code, r.text[:160] if r.status_code != 200 else "")
r = requests.post(f"{BASE}/incentive/sheets", headers=mgr, timeout=60, json={"pay_period": "2026-11", "lines": [
    {"sales_id": sales["id"], "component_id": komp["id"], "basis_period_type": "month", "basis_period": "2026-10"}]})
print("lembar", r.status_code, r.text[:200] if r.status_code != 200 else "")
s = r.json()
r = requests.patch(f"{BASE}/incentive/sheets/{s['id']}/lines/{s['lines'][0]['id']}", headers=mgr, timeout=60,
                   json={"amount": 2_500_000})
print("nominal", r.status_code, r.text[:160] if r.status_code != 200 else "")
print("ajukan", requests.post(f"{BASE}/incentive/sheets/{s['id']}/submit", headers=mgr, timeout=60).status_code)
r = requests.post(f"{BASE}/incentive/sheets/{s['id']}/approve", headers=adm, timeout=60, json={})
print("sahkan", r.status_code, r.text[:200] if r.status_code != 200 else "")
d = DB.incentive_sheets.find_one({"id": s["id"]}, {"_id": 0, "number": 1, "status": 1, "gl_status": 1, "payroll_linked": 1})
print("lembar", d)
