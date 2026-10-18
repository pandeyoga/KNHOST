"""Tes internal_token & percabangan main() vps_enable_ai.py TANPA memanggil AI beneran."""
import os
import subprocess
import sys
from pymongo import MongoClient

MONGO = "mongodb://127.0.0.1:27919"
DB = "knhost_data_audit_latest_pytest"


def _run(env_extra):
    env = {**os.environ, "MONGO_URL": MONGO, "DB_NAME": DB, **env_extra}
    # Sisipkan monkeypatch run() jadi no-op supaya tidak menembak OpenAI.
    code = (
        "import sys; sys.path.insert(0, 'C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend'); "
        "import scripts.vps_enable_ai as m; "
        "m.run = lambda tok: (print('  OK  (run dilewati saat tes)'), sys.exit(0)); "
        "m.main()"
    )
    return subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=30
    )


def _leftover():
    db = MongoClient(MONGO)[DB]
    return db.sessions.count_documents({"id": {"$regex": "^session_(vps|cek)_"}})


def test_wrong_password_uses_internal_session():
    r = _run({"ADMIN_PASSWORD": "salah"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "sesi admin internal (tanpa sandi)" in r.stdout, r.stdout
    assert _leftover() == 0


def test_no_password_uses_internal_session():
    env = {**os.environ}
    env.pop("ADMIN_PASSWORD", None)
    r = _run({})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "sesi admin internal (tanpa sandi)" in r.stdout, r.stdout
    assert _leftover() == 0


def test_correct_password_uses_login():
    r = _run({"ADMIN_PASSWORD": "demo12345"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK  login admin" in r.stdout, r.stdout
    assert "sesi admin internal" not in r.stdout, r.stdout
    assert _leftover() == 0


def test_internal_token_grants_admin_access_to_ai_status():
    """Uji sesi internal benar-benar memberi akses admin ke /api/ai/status."""
    import urllib.request
    import json
    sys.path.insert(0, "C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend")
    os.environ["MONGO_URL"] = MONGO
    os.environ["DB_NAME"] = DB
    from scripts.vps_enable_ai import internal_token
    tok, cleanup = internal_token("admin@kainnusantara.id")
    assert tok
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8001/api/ai/status",
            headers={"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
        assert isinstance(data, dict)
        # Endpoint ada & auth diterima
        assert "chat_enabled" in data or "has_key" in data or "model" in data, data
    finally:
        cleanup()
    assert _leftover() == 0


def test_cek_vps_python_block_runs_without_password():
    """Ekstrak heredoc python di cek_vps.sh, jalankan lokal — harus cetak 'Daftar Roll ?limit=5' & tak sisakan sesi."""
    import re
    src = open("C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/deploy/cek_vps.sh").read()
    m = re.search(r"<<'PY'[^\n]*\n(.*?)\nPY\b", src, re.S)
    assert m, "blok python cek_vps.sh tak ditemukan"
    script = m.group(1)
    env = {**os.environ, "MONGO_URL": MONGO, "DB_NAME": DB}
    r = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=60)
    assert "Daftar Roll ?limit=5" in r.stdout, r.stdout + r.stderr
    assert _leftover() == 0


def test_shell_syntax_and_no_read_rsp():
    for path in ("C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/deploy/cek_vps.sh", "C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/deploy/setup_vps_ai_import.sh"):
        r = subprocess.run(["bash", "-n", path], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    setup = open("C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/deploy/setup_vps_ai_import.sh").read()
    assert 'read -rsp "Sandi admin' not in setup
