#!/usr/bin/env bash
# Pulihkan data acuan (urutan deploy/setup_demo_lengkap.sh) di preview lokal.
#   bash scripts/restore_local_demo.sh              # Emergent: drop DB + restart backend + seed
#   bash scripts/restore_local_demo.sh --seed-only  # hanya rantai seed (Docker: dipanggil dari
#                                                   # scripts/dev_restore_demo.sh sesudah drop+restart)
set -uo pipefail
LOG=/app/.restore_local.log
cd /app/backend
step() { echo "=== $* $(date +%T)" >> "$LOG"; }
FAILED=()
run() { step "$1"; python "$1" >> "$LOG" 2>&1; local rc=$?; echo "EXIT $1=$rc" >> "$LOG"; [ $rc -eq 0 ] || FAILED+=("$1"); }
if [ "${1:-}" != "--seed-only" ]; then
  step "drop db + restart backend"
  python -c "import os; from pymongo import MongoClient; MongoClient(os.environ.get('MONGO_URL') or 'mongodb://localhost:27017').drop_database(os.environ.get('DB_NAME') or 'test_database')"
  supervisorctl restart backend >> "$LOG" 2>&1
  for i in $(seq 1 40); do [ "$(curl -s -o /dev/null -w '%{http_code}' localhost:8001/api/)" = 200 ] && break; sleep 3; done
  sleep 10
fi
run scripts/import_master_produk_kn.py
run scripts/import_stok_awal_kn.py
run scripts/seed_demo_lengkap_kn.py
run scripts/seed_demo_transaksi_kn.py
run scripts/seed_demo_harga_internal_kn.py
run scripts/seed_simulasi_bin_kn.py
run scripts/seed_p01_kn.py
run scripts/seed_p02_kn.py
run scripts/migrate_p02_lokasi.py
run scripts/seed_p03_kn.py
run scripts/seed_p04_kn.py
run scripts/seed_p05_kn.py
step "RESTORE DONE"
if [ ${#FAILED[@]} -gt 0 ]; then
  echo "RESTORE SELESAI DENGAN GAGAL: ${FAILED[*]} (lihat $LOG)"
  exit 1
fi
echo "RESTORE OK (log: $LOG)"
