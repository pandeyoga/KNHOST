#!/usr/bin/env bash
# cek_vps.sh — pastikan VPS benar-benar aktif: kontainer, API, HTTPS, data, perbaikan Daftar Roll, AI.
#   cd /opt/kainnusantara && bash deploy/cek_vps.sh
set -uo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$APP_DIR/deploy/.env"
compose() { docker compose --env-file "$ENV_FILE" -f "$APP_DIR/deploy/docker-compose.yml" "$@"; }
getenv() { grep "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2- || true; }
FAIL=0
ok() { printf '\033[1;32m OK \033[0m %s\n' "$*"; }
bad() { printf '\033[1;31mGAGAL\033[0m %s\n' "$*"; FAIL=1; }

DOMAIN="$(getenv DOMAIN)"
echo "== Kontainer"
for s in mongo backend web; do
  if [ -n "$(compose ps --status running -q "$s" 2>/dev/null)" ]; then ok "$s berjalan"; else bad "$s tidak berjalan"; fi
done

echo "== API & HTTPS"
compose exec -T backend curl -fsS http://127.0.0.1:8001/api/ >/dev/null 2>&1 && ok "backend /api/ menjawab" || bad "backend /api/ tidak menjawab"
if [ -n "$DOMAIN" ]; then
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "https://$DOMAIN/")
  [ "$code" = 200 ] && ok "https://$DOMAIN → 200" || bad "https://$DOMAIN → $code (cek DNS / bash deploy/edge.sh)"
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "https://$DOMAIN/api/")
  [ "$code" = 200 ] && ok "https://$DOMAIN/api/ → 200" || bad "https://$DOMAIN/api/ → $code"
fi

echo "== Data, Daftar Roll & AI"
compose exec -T backend python - <<'PY' || FAIL=1
import json, os, sys, urllib.request
from pymongo import MongoClient
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
bad = 0
def show(ok, msg):
    global bad
    print((" OK  " if ok else "GAGAL ") + msg); bad |= (not ok)
n_prod = db.products.count_documents({"sku": {"$regex": "^KN"}})
n_roll = db.inventory_rolls.count_documents({"acquired.ref_id": "STOK_AWAL_KN"})
show(n_prod >= 268, f"master produk KN: {n_prod} SKU")
show(n_roll > 0, f"stok awal: {n_roll} roll")
key_env = bool(os.environ.get("OPENAI_API_KEY"))
integ = (db.system_settings.find_one({"scope": "integrations"}, {"_id": 0, "openai": 1}) or {}).get("openai") or {}
show(key_env, "OPENAI_API_KEY diteruskan ke backend")
show(bool(integ.get("verified_at")), f"integrasi OpenAI terverifikasi ({integ.get('verified_at') or '-'})")
# Sesi admin internal 1 jam (tanpa sandi — kebal salah sandi/lockout), dihapus sesudahnya.
import secrets
from datetime import datetime, timedelta, timezone
admin = db.users.find_one({"status": "active", "role": "admin"}, {"id": 1})
tok = secrets.token_urlsafe(32)
if admin:
    db.sessions.insert_one({"id": f"session_cek_{secrets.token_hex(6)}", "token": tok, "user_id": admin["id"],
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)})
try:
    req = urllib.request.Request("http://127.0.0.1:8001/api/inventory/rolls?limit=5",
                                 headers={"Authorization": f"Bearer {tok}"})
    rows = json.load(urllib.request.urlopen(req, timeout=30))
    show(isinstance(rows, list) and len(rows) <= 5, f"Daftar Roll ?limit=5 → {len(rows)} baris (perbaikan limit aktif)")
except Exception as e:
    show(False, f"Daftar Roll: {e}" + ("" if admin else " (tidak ada akun admin aktif)"))
finally:
    db.sessions.delete_one({"token": tok})
sys.exit(1 if bad else 0)
PY

echo
if [ "$FAIL" = 0 ]; then printf '\033[1;32mVPS AKTIF — semua pemeriksaan OK.\033[0m https://%s\n' "$DOMAIN"
else printf '\033[1;31mAda pemeriksaan GAGAL — lihat baris di atas.\033[0m Log: cd %s/deploy && docker compose logs --tail=80 backend\n' "$APP_DIR"; exit 1; fi
