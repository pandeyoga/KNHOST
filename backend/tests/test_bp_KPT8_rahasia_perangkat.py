"""KP-T8 — di MongoDB ASLI (lingkungan A) dengan data acuan: token mesin absen aman, rahasia terbungkus, satu koneksi WhatsApp.

Butir U1–U15 diuji di lingkungan B (`backend/tests_mem/test_KPT8_rahasia_perangkat.py`). Berkas ini pelengkap yang hanya
sah di aplikasi utuh: (1) indeks unik parsial `hr_devices.uq_device_token_hash` benar-benar terpasang (database tiruan
tidak mendukungnya); (2) backend yang berjalan tidak pernah mengirim token/hash perangkat, menampilkan token baru sekali,
ingest mencocokkan hash, ganti token memutus token lama; (3) skrip `scripts/migrate_kpt8_rahasia.py` mode lapor di data
acuan tidak menulis apa pun (keluaran dicetak, `-s`, untuk laporan unit); (4) layar Integrasi melapor status kunci
enkripsi dan koneksi WhatsApp tanpa token.

Uji HTTP terhadap backend yang berjalan (`REACT_APP_BACKEND_URL`); pembacaan langsung ke database uji lokal
(`MONGO_URL`/`DB_NAME`). Satu perangkat uji dibuat lalu dinonaktifkan. Tidak untuk database berisi data nyata
(menjalankan skrip di data nyata = titik henti H3).
"""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
ROOT = Path(__file__).resolve().parents[2]


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _ingest(token):
    return requests.post(f"{BASE}/hr/attendance/ingest", json={"device_token": token, "records": []}, timeout=30)


def test_KPT8_A_indeks_unik_parsial_hash_token_terpasang():
    info = DB.hr_devices.index_information()
    assert "uq_device_token_hash" in info, sorted(info)
    ix = info["uq_device_token_hash"]
    assert ix.get("unique") is True
    assert ix.get("partialFilterExpression") == {"device_token_hash": {"$type": "string"}}


def test_KPT8_A_token_tampil_sekali_hash_dicocokkan_ganti_memutus():
    h = _login()
    rows = requests.get(f"{BASE}/hr/devices", headers=h, timeout=30)
    assert rows.status_code == 200, rows.text
    assert all("device_token" not in x and "device_token_hash" not in x for x in rows.json())
    r = requests.post(f"{BASE}/hr/devices", headers=h, json={"name": "Mesin uji KP-T8 (lapis A)"}, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    dev, tok = j["id"], j["device_token"]
    try:
        assert tok.startswith("at_") and j["shown_once"] is True
        doc = DB.hr_devices.find_one({"id": dev}, {"_id": 0})
        assert "device_token" not in doc and doc["device_token_hash"] == hashlib.sha256(tok.encode()).hexdigest()
        assert _ingest(tok).status_code == 200
        r = requests.post(f"{BASE}/hr/devices/{dev}/rotate-token", headers=h, timeout=30)
        assert r.status_code == 200, r.text
        baru = r.json()["device_token"]
        assert _ingest(tok).status_code == 401 and _ingest(baru).status_code == 200
    finally:
        requests.delete(f"{BASE}/hr/devices/{dev}", headers=h, timeout=30)


def test_KPT8_A_skrip_migrasi_mode_lapor_tidak_menulis():
    sebelum = (list(DB.hr_devices.find({}, {"_id": 0}).sort("id", 1)),
               DB.system_settings.find_one({"scope": "integrations"}, {"_id": 0}),
               DB.system_settings.find_one({"scope": "alerts"}, {"_id": 0, "wa": 1}),
               DB.integration_settings.find_one({"id": "whatsapp"}, {"_id": 0}),
               DB.permission_settings.find_one({"id": "default"}, {"_id": 0, "matrix": 1}))
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "migrate_kpt8_rahasia.py")],
                         capture_output=True, text=True, timeout=300, cwd=str(ROOT))
    print(out.stdout)
    assert out.returncode == 0, out.stderr
    assert "mode lapor" in out.stdout and "1. Perangkat absen ber-token polos" in out.stdout
    sesudah = (list(DB.hr_devices.find({}, {"_id": 0}).sort("id", 1)),
               DB.system_settings.find_one({"scope": "integrations"}, {"_id": 0}),
               DB.system_settings.find_one({"scope": "alerts"}, {"_id": 0, "wa": 1}),
               DB.integration_settings.find_one({"id": "whatsapp"}, {"_id": 0}),
               DB.permission_settings.find_one({"id": "default"}, {"_id": 0, "matrix": 1}))
    assert sebelum == sesudah


def test_KPT8_A_integrasi_melapor_kunci_enkripsi_dan_koneksi_tanpa_token():
    h = _login()
    r = requests.get(f"{BASE}/admin/integrations", headers=h, timeout=30)
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["secrets_key_configured"], bool)
    r = requests.get(f"{BASE}/admin/integrations/whatsapp", headers=h, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert set(j["used_by"]) == {"alerts", "documents"} and "access_token" not in j and "fonnte_token" not in j
    r = requests.put(f"{BASE}/admin/integrations", headers=h, json={"anthropic_enabled": True}, timeout=30)
    assert r.status_code == 400, r.text
