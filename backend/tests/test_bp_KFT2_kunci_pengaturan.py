"""KF-T2 — di MongoDB ASLI (lingkungan A) dengan data acuan: kunci baru terbaca, jalur lama mati, dan skrip pindahan
akun bank dalam mode lapor tidak menulis apa pun.

Unit ini tidak punya butir uji lapis A wajib (U1–U14 di `backend/tests_mem/test_KFT2_*.py`); berkas ini pelengkap untuk
data acuan (`scripts/dev_restore_demo.sh`), karena dokumen pengaturan data acuan bisa memuat nilai lama `returns.*` /
`interco_payment.*` dan akun bank yang tidak ada di benih lingkungan B. Keluaran mode lapor skrip dicetak (`-s`) untuk
laporan unit. Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); pembacaan langsung ke database
uji lokal (`MONGO_URL`/`DB_NAME`). Satu nilai lapisan PT ditulis lalu lapisannya dicabut. Tidak untuk database berisi data
nyata (`--apply` di data nyata = titik henti H3).
"""
import os
import subprocess
import sys
from pathlib import Path

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
ROOT = Path(__file__).resolve().parents[2]
BARU = {"returns.customer_window_days": 21, "returns.supplier_window_days": 21, "returns.supplier_reminder_days": 3,
        "returns.bill_first": True,
        "returns.grade_price_factors": {"A": 100, "A1": 95, "A2": 90, "B": 70, "B1": 60, "C": 40, "BS": 10},
        "interco_payment.allow_netting": False, "interco_payment.require_full_payment": True,
        "interco_payment.cutoff_day": 0, "interco_payment.payment_day": 0, "interco_payment.basis": "",
        "interco_payment.reminder_days": 3}
TIDAK_DIPAKAI = ("contra_bon.qty_tolerance_percent", "lot.number_format", "bank.holding_account_code",
                 "bank.charge_account_code", "bank.interest_account_code")


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _efektif(h, key, entity_id=""):
    r = requests.get(f"{BASE}/config/effective", headers=h, params={"q": key, "entity_id": entity_id}, timeout=30)
    assert r.status_code == 200, r.text
    items = [it for it in r.json()["items"] if it["key"] == key]
    assert len(items) == 1, r.json()
    return items[0]


def test_KFT2_A_registry_kunci_baru_dan_tidak_dipakai():
    r = requests.get(f"{BASE}/config/registry", headers=_login(), timeout=30)
    assert r.status_code == 200, r.text
    reg = {e["key"]: e for e in r.json()["entries"]}
    for key, bawaan in BARU.items():
        assert reg[key]["default"] == bawaan and reg[key]["status"] == "active", key
    for key in TIDAK_DIPAKAI:
        assert reg[key]["status"] == "not_used" and reg[key]["not_used_reason"], key


def test_KFT2_A_put_settings_lama_410_tanpa_menulis():
    sebelum = DB.system_settings.find_one({"scope": "global"}, {"_id": 0})
    r = requests.put(f"{BASE}/settings", headers=_login(), json={"scope": "global", "returns": {"customer_window_days": 5}},
                     timeout=30)
    assert r.status_code == 410, r.text
    assert DB.system_settings.find_one({"scope": "global"}, {"_id": 0}) == sebelum


def test_KFT2_A_batas_retur_per_pt_lewat_pusat_pengaturan():
    h = _login()
    key = "returns.customer_window_days"
    kanda = _efektif(h, key, "ent_kanda")["value"]
    try:
        r = requests.put(f"{BASE}/config/values", headers=h, timeout=30, json={"items": [
            {"key": key, "value": 30, "scope_type": "entity", "scope_id": "ent_ksc", "reason": "uji KF-T2 lapis A"}]})
        assert r.status_code == 200, r.text
        assert _efektif(h, key, "ent_ksc")["value"] == 30
        assert _efektif(h, key, "ent_kanda")["value"] == kanda
        hist = requests.get(f"{BASE}/config/history", headers=h, params={"key": key}, timeout=30).json()["rows"]
        assert hist and hist[0]["scope_id"] == "ent_ksc" and hist[0]["value"] == 30
    finally:
        requests.post(f"{BASE}/config/values/clear", headers=h, timeout=30, json={
            "key": key, "scope_type": "entity", "scope_id": "ent_ksc", "reason": "uji KF-T2 lapis A kembalikan"})


def test_KFT2_A_pemetaan_akun_bunga_bank_ada():
    r = requests.get(f"{BASE}/gl/account-mappings", headers=_login(), timeout=30)
    assert r.status_code == 200, r.text
    rows = {x["key"]: x for x in r.json()["rows"]}
    assert rows["kas_bank.pendapatan_bunga"]["default"] == "4-9000"


def test_KFT2_A_skrip_pindahan_akun_bank_mode_lapor_tidak_menulis():
    sebelum = sorted((d["key"], d.get("entity_id"), d.get("account_code"), d.get("version"))
                     for d in DB.gl_account_mappings.find({}, {"_id": 0}))
    hist = DB.gl_account_mapping_history.count_documents({})
    hasil = subprocess.run([sys.executable, str(ROOT / "scripts/migrate_kft2_akun_bank.py"), "--dry-run"], cwd=ROOT,
                           capture_output=True, text=True, timeout=120)
    print(hasil.stdout)   # keluaran mode lapor pada data acuan — dikutip di laporan unit
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr
    assert "mode lapor" in hasil.stdout
    sesudah = sorted((d["key"], d.get("entity_id"), d.get("account_code"), d.get("version"))
                     for d in DB.gl_account_mappings.find({}, {"_id": 0}))
    assert sesudah == sebelum and DB.gl_account_mapping_history.count_documents({}) == hist
    salah = subprocess.run([sys.executable, str(ROOT / "scripts/migrate_kft2_akun_bank.py"), "--tulis"], cwd=ROOT,
                           capture_output=True, text=True, timeout=60)
    assert salah.returncode == 2
