#!/usr/bin/env bash
# setup_vps_ai_import.sh — SEKALI JALAN di VPS:
#   1) simpan kunci OpenAI + kunci enkripsi ke deploy/.env   2) tarik kode terbaru, build, restart
#   3) impor master produk dari Excel                          4) aktifkan & uji AI (OCR SJ + Tanya KN)
#
#   cd /opt/kainnusantara && git fetch origin main && git reset --hard origin/main \
#     && OPENAI_API_KEY='sk-...' bash deploy/setup_vps_ai_import.sh
#   (JANGAN `git pull`: riwayat GitHub ditulis ulang oleh Save to GitHub → "divergent branches")
#   (tanpa OPENAI_API_KEY → ditanyakan; bila sudah pernah disimpan di deploy/.env → dipakai ulang)
#   Excel lain: XLSX=/root/MASTER.xlsx OPENAI_API_KEY=... bash deploy/setup_vps_ai_import.sh
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$APP_DIR/deploy/.env"
compose() { docker compose --env-file "$ENV_FILE" -f "$APP_DIR/deploy/docker-compose.yml" "$@"; }
log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\033[1;31mXX  %s\033[0m\n' "$*" >&2; exit 1; }
setenv() { sed -i "/^$1=/d" "$ENV_FILE"; echo "$1=$2" >> "$ENV_FILE"; }
getenv() { grep "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2- || true; }

[ -f "$ENV_FILE" ] || die "deploy/.env belum ada — jalankan dulu: bash deploy/install_vps.sh"

log "1/4 Rahasia di deploy/.env"
KEY="${OPENAI_API_KEY:-$(getenv OPENAI_API_KEY)}"
if [ -z "$KEY" ]; then read -rsp "Tempel OpenAI API key (sk-...): " KEY; echo; fi
KEY="$(printf '%s' "$KEY" | tr -d '[:space:]"')"
[[ "$KEY" == sk-* ]] || die "OpenAI API key tidak valid (harus diawali sk-)."
[[ "$KEY" != *KUNCI* && "$KEY" != *XXXX* && "$KEY" != "sk-proj-..." && "$KEY" != "sk-..." && ${#KEY} -ge 40 ]] \
  || die "OpenAI API key masih contoh/terlalu pendek — tempel kunci asli dari https://platform.openai.com/api-keys"
setenv OPENAI_API_KEY "$KEY"
[ -n "$(getenv KN_SECRETS_KEY)" ] || setenv KN_SECRETS_KEY "$(openssl rand 32 | base64 | tr '+/' '-_' | tr -d '\n')"
chmod 600 "$ENV_FILE"
echo "OPENAI_API_KEY & KN_SECRETS_KEY tersimpan (chmod 600)."

log "2/4 Tarik kode terbaru + build + restart"
bash "$APP_DIR/deploy/update.sh"

log "3/4 Impor master produk dari Excel"
IMPORT_ARG=""
if [ -n "${XLSX:-}" ]; then
  [ -f "$XLSX" ] || die "Berkas $XLSX tidak ada."
  compose cp "$XLSX" backend:/tmp/master_produk.xlsx
  IMPORT_ARG="/tmp/master_produk.xlsx"
fi
compose exec -T backend python scripts/import_master_produk_kn.py $IMPORT_ARG --dry-run | tail -3
compose exec -T backend python scripts/import_master_produk_kn.py $IMPORT_ARG | tail -2
echo "--- stok awal MOCK (1.000–2.000 roll per artikel, dibagi ke SKU & entitas) ---"
compose exec -T backend python scripts/import_stok_awal_kn.py | tail -2

log "4/4 Aktifkan & uji AI"
# Sandi admin OPSIONAL: bila salah/kosong, skrip memakai sesi admin internal 1 jam (lalu dihapus).
ADMIN_PASSWORD="${ADMIN_PASSWORD:-$(getenv ADMIN_PASSWORD)}"
compose exec -T -e ADMIN_PASSWORD="$ADMIN_PASSWORD" -e OPENAI_API_KEY="$KEY" backend python scripts/vps_enable_ai.py

log "5/5 Pemeriksaan akhir VPS"
ADMIN_PASSWORD="$ADMIN_PASSWORD" bash "$APP_DIR/deploy/cek_vps.sh" || die "Pemeriksaan akhir gagal (lihat di atas)."

DOMAIN="$(getenv DOMAIN)"
printf '\n\033[1;32mSelesai.\033[0m Buka https://%s → Master Produk (cari KNKNT0007) · Tanya KN · Kedatangan Barang → Baca otomatis.\n' "$DOMAIN"
