"""Menyalakan aplikasi KNHOST utuh di database tiruan pada port nyata, supaya layar bisa dibuka di peramban.

    python serve_mem.py            # http://127.0.0.1:8001 ; semua akun seed bersandi demo12345

Frontend: salin `frontend/` ke folder kerja, `yarn install`, lalu
    REACT_APP_BACKEND_URL=http://localhost:8001 BROWSER=none PORT=3000 yarn start:dev
Data hilang saat proses dimatikan. Batas database tiruan: lihat boot_app.py.
"""
import os

os.environ.setdefault("KN_INITIAL_PASSWORD", "demo12345")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")

import boot_app  # noqa: E402,F401  (harus sebelum server)
import server  # noqa: E402
import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(server.app, host="127.0.0.1", port=int(os.environ.get("PORT", "8001")), log_level="warning")
