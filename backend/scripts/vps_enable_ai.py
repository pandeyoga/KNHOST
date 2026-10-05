"""VPS: aktifkan AI (OCR SJ + Tanya KN) lewat API resmi & verifikasi end-to-end. Dijalankan di kontainer backend.

Env: ADMIN_EMAIL (bawaan admin@kainnusantara.id), ADMIN_PASSWORD, OPENAI_API_KEY (opsional bila sudah tersimpan).
Keluar kode 1 bila ada langkah wajib gagal.
"""
import json
import os
import sys
import urllib.error
import urllib.request

API = "http://127.0.0.1:8001/api"
ENT = os.environ.get("KN_ENTITY", "ent_ksc")
FAIL = []


def call(method, path, token=None, body=None, stream=False, timeout=180):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "X-Entity-Id": ENT,
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        return e.code, (json.loads(raw) if raw.startswith("{") else raw)
    if stream:
        return 200, [json.loads(ln[6:]) for ln in raw.splitlines() if ln.startswith("data: ")]
    return 200, json.loads(raw) if raw else {}


def step(name, ok, info=""):
    print(f"  {'OK ' if ok else 'XX '} {name}{' — ' + str(info) if info else ''}")
    if not ok:
        FAIL.append(name)


def internal_token(email):
    """Sesi admin 1 jam langsung di DB (skrip jalan DI DALAM kontainer) — tak bergantung sandi/lockout."""
    import secrets
    from datetime import datetime, timedelta, timezone
    from pymongo import MongoClient
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    user = db.users.find_one({"email": email, "status": "active", "role": "admin"}, {"id": 1}) \
        or db.users.find_one({"status": "active", "role": "admin"}, {"id": 1})
    if not user:
        return "", None
    tok = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.sessions.insert_one({"id": f"session_vps_{secrets.token_hex(6)}", "token": tok, "user_id": user["id"],
                            "created_at": now.isoformat(), "expires_at": now + timedelta(hours=1)})
    return tok, lambda: db.sessions.delete_one({"token": tok})


def main():
    email = os.environ.get("ADMIN_EMAIL", "admin@kainnusantara.id")
    cleanup = None
    code, r = (0, {})
    if os.environ.get("ADMIN_PASSWORD"):
        code, r = call("POST", "/auth/login", body={"email": email, "password": os.environ["ADMIN_PASSWORD"]})
    if code == 200 and "token" in r:
        tok = r["token"]
        step("login admin", True)
    else:
        tok, cleanup = internal_token(email)
        step("sesi admin internal (tanpa sandi)", bool(tok), "tidak ada akun admin aktif" if not tok else "")
        if not tok:
            sys.exit(1)
    try:
        run(tok)
    finally:
        if cleanup:
            cleanup()


def run(tok):
    key = os.environ.get("OPENAI_API_KEY", "").strip().strip('"')
    if key and not key.startswith("sk-") or any(c.isspace() for c in key):
        step("format kunci OpenAI", False, "harus diawali sk- dan tanpa spasi/baris baru")
        sys.exit(1)
    if key:
        code, r = call("PUT", "/admin/integrations", tok, {"openai_api_key": key})
        step("simpan kunci OpenAI (terenkripsi)", code == 200 and (r.get("openai") or {}).get("has_key"), "" if code == 200 else r)
    code, r = call("POST", "/admin/integrations/openai/test", tok)
    step("uji koneksi OpenAI", code == 200 and r.get("ok"), r.get("detail") or r.get("error") or f"{r.get('models_seen')} model")
    items = [{"key": k, "value": True, "scope_type": "global", "reason": "Aktivasi AI di VPS (setup_vps_ai_import.sh)"}
             for k in ("receiving.ocr_enabled", "receiving.ocr_photo_check", "ai.enabled", "ai.anomaly_enabled")]
    code, r = call("PUT", "/config/values", tok, {"items": items})
    step("aktifkan OCR SJ + Tanya KN + peringatan", code == 200, "" if code == 200 else r)
    code, r = call("POST", "/ai/facts/rebuild?from=2024-01-01", tok, timeout=600)
    step("bangun ulang data analitik", code == 200, r if code != 200 else f"{r.get('orders')} pesanan")
    code, r = call("POST", "/ai/insights/scan", tok)
    step("pindai peringatan anomali", code == 200, r)
    code, st = call("GET", "/ai/status", tok)
    step("status Tanya KN", code == 200 and st.get("chat_enabled") and st.get("has_key") and not st.get("mock"),
         {k: st.get(k) for k in ("chat_enabled", "has_key", "model") if k in st})
    code, evs = call("POST", "/ai/chat", tok, {"question": "Berapa jumlah produk aktif per kategori?"}, stream=True, timeout=240)
    done = next((e for e in evs if e.get("type") == "done"), {}) if code == 200 else {}
    ok = bool(done) and not done.get("disabled") and not done.get("error")
    step("uji tanya jawab AI (model nyata)", ok, (done.get("text") or done.get("error") or evs)[:200] if code == 200 else evs)
    print("\nSELESAI — semua langkah OK" if not FAIL else f"\nADA YANG GAGAL: {', '.join(FAIL)}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
