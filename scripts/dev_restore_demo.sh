#!/usr/bin/env bash
# Pulihkan DATA ACUAN di lingkungan Docker lokal (docker-compose.dev.yml) — jalankan dari HOST,
# di root repo (Git Bash / WSL / macOS / Linux):
#   bash scripts/dev_restore_demo.sh
# Urutan sama dengan scripts/restore_local_demo.sh (satu sumber daftar seed):
#   1) drop DB  2) restart backend → bootstrap fondasi menulis ke DB yang hidup  3) rantai seed
#   4) verifikasi fondasi (gagal berisik — pelajaran .restore_env.sh)
set -uo pipefail
export MSYS_NO_PATHCONV=1   # Git Bash: jangan ubah /app/... menjadi path Windows
C="docker compose -f docker-compose.dev.yml"
DB="${DB_NAME:-test_database}"

# Backend DIHENTIKAN dulu: bila DB di-drop saat backend hidup, bootstrap/penjadwal yang sedang
# berjalan bisa menulis akun peran (md, wh.admin, …) ke DB kosong → bootstrap berikutnya melihat
# `users` tidak kosong dan TIDAK membuat akun admin awal.
echo "[1/4] hentikan backend + drop database $DB"
$C stop backend >/dev/null || exit 1
$C exec -T mongo mongosh --quiet "$DB" --eval 'db.dropDatabase().ok' || exit 1

echo "[2/4] nyalakan backend (bootstrap fondasi)"
$C start backend >/dev/null || exit 1
for i in $(seq 1 60); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://localhost:8001/api/)" = 200 ] && break
  sleep 3
done
sleep 10

echo "[3/4] rantai seed data acuan (±4 menit)"
$C exec -T backend bash /app/scripts/restore_local_demo.sh --seed-only
SEED_RC=$?

echo "[4/4] verifikasi fondasi"
$C exec -T mongo mongosh --quiet "$DB" --eval '
  let bad = [];
  for (const c of ["gl_accounts", "uoms", "expense_categories", "business_entities", "users"]) {
    const n = db[c].countDocuments({}); print(c.padEnd(20), n); if (!n) bad.push(c);
  }
  if (bad.length) { print("FONDASI KOSONG: " + bad.join(", ") + " — jalankan: docker compose -f docker-compose.dev.yml restart backend"); quit(1); }'
FOUND_RC=$?

[ $SEED_RC -eq 0 ] && [ $FOUND_RC -eq 0 ] && echo "SELESAI — login admin@kainnusantara.id / demo12345" && exit 0
echo "SELESAI DENGAN MASALAH (seed=$SEED_RC fondasi=$FOUND_RC) — log: .restore_local.log di root repo"
exit 1
