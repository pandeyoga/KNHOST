"""Bukti audit keuangan 13 Nov 2026 — menjalankan kode laporan/posting KNHOST apa adanya
di atas MongoDB TIRUAN dalam memori (mongomock). Tidak menyentuh database mana pun.

Bukan bagian aplikasi dan bukan gate. Lihat README.md di folder ini.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:1/tidak-dipakai")
os.environ.setdefault("DB_NAME", "audit_mem")
BACKEND = Path(__file__).resolve().parents[3] / "backend"
sys.path.insert(0, str(BACKEND))

import motor.motor_asyncio as _m  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

_m.AsyncIOMotorClient = AsyncMongoMockClient      # backend/db.py membuat klien dari kelas ini
import db as _db  # noqa: E402

db = _db.db
