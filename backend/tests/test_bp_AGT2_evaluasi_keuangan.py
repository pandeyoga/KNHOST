"""AG-T2 U17 — di MongoDB ASLI (lingkungan A, data acuan): 60 pertanyaan Asisten Keuangan mode `engine` → 60 dari 60.

    docker compose -f docker-compose.dev.yml exec backend python -m pytest /app/backend/tests/test_bp_AGT2_evaluasi_keuangan.py -q

Menjalankan `tools/ai_eval/run_eval.py --mode engine --set keuangan` (tanpa penyedia model, tanpa kunci): alat harapan
dijalankan sebagai peran itu lewat endpoint aplikasi sendiri di dalam proses (sesi sementara 10 menit yang dihapus
sesudahnya), lalu angka `check.paths` dibandingkan dengan jawaban endpoint yang sama dalam sesi yang sama; `denied` =
alat galat DAN endpoint 403. Membaca saja; tidak menulis data bisnis (yang ditulis: hasil alat `ai_results` berumur 30
hari dan sesi sementara). Mode `model` (memakai penyedia) dijalankan pemilik sebelum menyalakan fitur (`00` §6 H8).
"""
import json
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def test_bp_AGT2_U17_evaluasi_keuangan_engine_60_dari_60():
    out = subprocess.run([sys.executable, "tools/ai_eval/run_eval.py", "--mode", "engine", "--set", "keuangan"],
                         cwd=BACKEND, capture_output=True, text=True, timeout=900)
    assert out.returncode == 0, out.stderr[-2000:]
    ringkas = json.loads(next(ln for ln in out.stdout.splitlines() if ln.startswith("{")))
    gagal = [ln for ln in out.stdout.splitlines() if ln.strip().startswith("GAGAL")]
    assert ringkas["n"] == 60 and ringkas["lulus"] == 60, (ringkas, gagal)
    assert ringkas["akses_ditolak_pct"] == 100.0, ringkas
