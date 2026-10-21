"""F-01 (uji pra-UAT 2026-10-21) — tombol login cepat per peran gagal "Email atau password tidak sesuai".

Akar: tombol mengirim `demo12345` sedangkan data acuan (`seed_demo_lengkap_kn`) menyandikan akun peran
`demo1234`; hanya admin@ & wh.admin@ (bootstrap) yang `demo12345`. Kini SATU sandi untuk semua akun seed.
Tes: konstanta seed = konstanta tombol frontend; setiap tombol peran dan setiap akun seed berhasil masuk
(jalankan sesudah restore data acuan: `bash scripts/dev_restore_demo.sh`).
Jalankan: cd /app/backend && python -m pytest tests/test_f01_demo_login.py -p no:randomly -n 0 -q
"""
import os
import re
import sys
from pathlib import Path

import requests
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from scripts.demo_api import BATCH, DEMO_PASSWORD  # noqa: E402

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
LOGIN_SCREEN = ROOT / "frontend" / "src" / "components" / "LoginScreen.jsx"
BOOTSTRAP_ACCOUNTS = ["admin@kainnusantara.id", "wh.admin@kainnusantara.id"]


def _login_screen():
    src = LOGIN_SCREEN.read_text(encoding="utf-8")
    pw = re.search(r'const DEMO_PASSWORD = "([^"]+)"', src)
    return (pw.group(1) if pw else None), re.findall(r'mail: "([^"]+@kainnusantara\.id)"', src)


def _gagal_masuk(emails, password):
    out = {}
    for e in emails:
        r = requests.post(f"{BASE}/auth/login", json={"email": e, "password": password}, timeout=30)
        if r.status_code != 200:
            out[e] = (r.status_code, r.text[:80])
    return out


def test_tombol_login_cepat_memakai_sandi_seed():
    pw, mails = _login_screen()
    assert pw == DEMO_PASSWORD, (pw, DEMO_PASSWORD)
    assert len(mails) >= 6, mails


def test_semua_tombol_peran_berhasil_masuk():
    pw, mails = _login_screen()
    assert not _gagal_masuk(mails, pw)


def test_semua_akun_seed_berhasil_masuk_dengan_satu_sandi():
    seeded = sorted(u["email"] for u in DB.users.find({"demo_batch": BATCH, "status": "active"}, {"_id": 0, "email": 1}))
    assert len(seeded) >= 15, f"akun data acuan belum ada ({len(seeded)}) — jalankan restore data acuan"
    assert not _gagal_masuk(seeded + BOOTSTRAP_ACCOUNTS, DEMO_PASSWORD)
